#!/usr/bin/env python3
"""Scrape Australian Competition Tribunal matter pages into tribunal_appeals.json.

Background
----------
When an ACCC merger decision is taken to the Australian Competition Tribunal,
the tribunal publishes a matter page listing the documents filed in the
review. ``data/processed/tribunal_appeals.json`` holds one hand-maintained
record per merger (keyed by ACCC merger_id) with the tribunal number, URL,
appeal type, appellant, status and a ``documents[]`` list that is folded into
the merger's event timeline (see ``static_data.enrichment.link_tribunal_appeals``).

Until now the ``documents[]`` list was maintained by hand. This script fills
it in from the live tribunal pages. The "list of pages to scrape" is simply the
set of entries in tribunal_appeals.json that carry a ``tribunal_url`` — that
file is the manual list, maintained by hand when a new matter is added.

Getting past Cloudflare — a real browser, in CI
-----------------------------------------------
The tribunal site sits behind Cloudflare's "managed challenge": a plain curl
or ``requests.get()`` only ever sees the "Just a moment..." interstitial,
because the challenge requires a real browser to run JavaScript (and sometimes
click a Turnstile checkbox). That is why the old curl-based scraper could not
run from GitHub Actions at all.

This version drives a real Chrome via `nodriver <https://github.com/ultrafunkamsterdam/nodriver>`_,
waits for the challenge to clear, then parses the filings table(s). Because a
genuine (headful, under Xvfb) browser solves the challenge, this runs
unattended in CI — see ``.github/workflows/scrape-tribunal.yml``. We launch
Chrome ourselves with a remote-debugging port and wait until the DevTools
endpoint is actually ready before attaching nodriver (nodriver's own launcher
only waits ~2.5s, which loses a race against Chrome's cold start on CI runners).

The browser is launched once and reused across every matter page in one run,
so the Cloudflare cookies obtained solving the first challenge carry over to
the rest. Those same cookies (and the browser's User-Agent) are reused when
downloading each linked document, so the document requests aren't bounced back
to the challenge either.

Page format
-----------
Each matter page contains one or more document tables:

  * the **first** table is the main set of documents and is not preceded by a
    heading; and
  * any **later** tables are each preceded by an ``<h3>`` naming the group
    (e.g. "Submissions by interested party"). That heading is stored on each of
    that table's documents as ``section``.

Columns are matched by header text (date / document / filed by / confidential),
so column order can vary. The document link is taken from the ``<a>`` in the row.

Each linked document is also downloaded into ``data/raw/matters/{merger_id}/``
(the same tree the ACCC scraper uses) and its local serve path recorded as
``url_gh`` (``/mergers/{merger_id}/{file}``), so tribunal filings are mirrored
and served exactly like ACCC attachments. Files already present are not
re-downloaded; off-domain links are kept but not mirrored.

Usage
-----
Normally this runs from CI on a schedule (the "Scrape Tribunal" workflow), but
it works anywhere a Chrome/Chromium binary is available::

  pip install -r scripts/requirements-tribunal.txt   # nodriver, requests, bs4, lxml
  python scripts/scrape_tribunal.py                 # scrape + download every entry with a tribunal_url
  python scripts/scrape_tribunal.py MN-01068 ...    # scrape only these merger_ids
  python scripts/scrape_tribunal.py --no-download   # record metadata only, skip file downloads
  python scripts/scrape_tribunal.py --dry-run       # parse and report, don't write or download
  git add data/processed/tribunal_appeals.json data/raw/matters
  git commit -m "Update scraped tribunal data" && git push

On a headless machine (a CI runner) run it under an X server so Chrome runs
headful, which is far less likely to be flagged than headless::

  xvfb-run -a python scripts/scrape_tribunal.py

Existing ``url_gh`` local-mirror paths are preserved across a re-scrape (matched
by document URL). If a page yields no rows (e.g. the layout changed) or its
Cloudflare challenge never clears, that entry is left untouched rather than
wiped.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import time
import unicodedata
import urllib.request
from datetime import datetime
from pathlib import Path
from shutil import which
from urllib.parse import unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

# nodriver is only needed to actually fetch pages (it drives Chrome). Import it
# lazily so the parsing/download helpers below stay importable — and unit
# testable — in environments that only install requests + bs4 + lxml (e.g. the
# main test job), without pulling in a browser-automation dependency.
try:
    import nodriver as uc
except ImportError:  # pragma: no cover - exercised only where nodriver is absent
    uc = None

SCRIPT_DIR = Path(__file__).parent
REPO_ROOT = SCRIPT_DIR.parent
TRIBUNAL_APPEALS_JSON = REPO_ROOT / "data" / "processed" / "tribunal_appeals.json"
# Downloaded documents are mirrored under data/raw/matters/{merger_id}/, the same
# tree the ACCC scraper uses, so the DOCX→PDF convert workflow and the Cloudflare
# /mergers/{id}/{file} route pick them up with no extra wiring.
MATTERS_DIR = REPO_ROOT / "data" / "raw" / "matters"

USER_AGENT = "Mozilla/5.0 (compatible; mergers-fyi/1.0; +https://mergers.fyi)"
REQUEST_TIMEOUT = 60

# Header-text keyword → document field. Matched case-insensitively as a
# substring of the (stripped) column header, so slight wording changes on the
# tribunal site don't break the mapping. Order matters: the first field whose
# keyword matches wins for a given column.
_COLUMN_KEYWORDS = [
    ("date", "date"),
    ("filed_by", "filed"),
    ("filed_by", "lodged"),
    ("filed_by", "submitted"),
    ("filed_by", "party"),
    ("filed_by", "author"),
    ("confidentiality", "confiden"),
    ("description", "document"),
    ("description", "description"),
    ("description", "title"),
    ("description", "name"),
]

# Trailing file annotation the tribunal appends to a document link's text, e.g.
# "Application for review (PDF, 537.8 KB)" or "... (PDF 1.01 MB)". Stripped from
# the description so it reads like the hand-curated entries ("Application for
# review"). The link URL is kept regardless.
_FILE_ANNOTATION_RE = re.compile(
    r"\s*\((?:PDF|DOCX?|XLSX?|PPTX?|RTF|ZIP|TXT|HTML?)\b[^)]*\)\s*$",
    re.IGNORECASE,
)

# Common date formats seen on tribunal pages, normalised to YYYY-MM-DD.
_DATE_FORMATS = [
    "%d %B %Y",   # 15 July 2026
    "%d %b %Y",   # 15 Jul 2026
    "%d/%m/%Y",   # 15/07/2026
    "%d-%m-%Y",   # 15-07-2026
    "%Y-%m-%d",   # 2026-07-15
]

# --- Cloudflare challenge / browser handling ---------------------------------

# Markers that indicate we're still looking at the Cloudflare challenge rather
# than the real matter page.
CHALLENGE_MARKERS = (
    "Just a moment",
    "challenge-platform",
    "cf_chl_opt",
    "Enable JavaScript and cookies to continue",
    "Verifying you are human",
)

# How long to wait for a single page's challenge to clear before giving up.
MAX_WAIT_SECONDS = 90

# nodriver's default args, which help the browser look like a normal user
# session rather than an automated one.
CHROME_ARGS = [
    "--remote-allow-origins=*",
    "--no-first-run",
    "--no-service-autorun",
    "--no-default-browser-check",
    "--homepage=about:blank",
    "--no-pings",
    "--password-store=basic",
    "--disable-infobars",
    "--disable-breakpad",
    "--disable-dev-shm-usage",
    "--disable-session-crashed-bubble",
    "--disable-search-engine-choice-screen",
    "--disable-features=IsolateOrigins,site-per-process",
    "--disable-gpu",
    "--window-size=1920,1080",
    "--no-sandbox",  # CI runs as root
]


# --- Attachment download helpers ---------------------------------------------
# These mirror the ACCC scraper's conventions in extract_mergers.py (filename
# safety, DOCX→PDF serve name, /mergers/{id}/{file} url_gh) so tribunal
# documents live in the same tree and are served the same way. They're copied
# rather than imported to keep this script's dependencies to requests + bs4.


def is_safe_filename(filename: str) -> bool:
    """Validate a filename to prevent path traversal (see extract_mergers)."""
    if not filename or not isinstance(filename, str) or not filename.strip():
        return False
    if ".." in filename or "/" in filename or "\\" in filename:
        return False
    if "  " in filename:
        return False
    if not re.match(
        r"^[a-zA-Z0-9À-ÿ][\wÀ-ÿ-–—'’. (),]*\.[a-zA-Z0-9]+$",
        filename,
    ):
        return False
    return len(filename) <= 255


def sanitize_filename(filename: str) -> str | None:
    """Make a filename safe, preserving the extension, or None if impossible."""
    if not filename or not isinstance(filename, str):
        return None
    filename = unicodedata.normalize("NFKC", filename)
    if not filename.strip():
        return None
    if ".." in filename or "/" in filename or "\\" in filename:
        return None
    sanitized = filename.replace(":", " -").replace("&", "and").replace("%", "pct")
    while "  " in sanitized:
        sanitized = sanitized.replace("  ", " ")
    sanitized = sanitized.strip()
    if len(sanitized) > 255:
        name, ext = os.path.splitext(sanitized)
        sanitized = name[: 255 - len(ext)] + ext
    return sanitized if is_safe_filename(sanitized) else None


def get_serve_filename(original_filename: str) -> str:
    """DOCX files are served as the PDF the convert workflow produces."""
    if original_filename.lower().endswith(".docx"):
        return os.path.splitext(original_filename)[0] + ".pdf"
    return original_filename


def is_safe_document_url(url: str) -> bool:
    """Only download from the tribunal's own domain (SSRF guard)."""
    parsed = urlparse(url)
    host = parsed.hostname
    return (
        parsed.scheme in ("http", "https")
        and host is not None
        and (
            host == "competitiontribunal.gov.au"
            or host.endswith(".competitiontribunal.gov.au")
        )
    )


def _document_local_path(merger_id: str, url: str) -> tuple[Path, str] | None:
    """Derive (local_path, url_gh) for a document URL, or None if no safe
    filename can be derived. Shared by download_document and the browser
    session download path."""
    decoded = unquote(urlparse(url).path)
    original = os.path.basename(decoded).strip()
    filename = original if is_safe_filename(original) else sanitize_filename(original)
    if not filename:
        return None
    matter_dir = MATTERS_DIR / merger_id
    return matter_dir / filename, f"/mergers/{merger_id}/{get_serve_filename(filename)}"


def download_document(
    merger_id: str, url: str, extra_headers: dict | None = None
) -> str | None:
    """Download a tribunal document into data/raw/matters/{merger_id}/.

    Returns the ``url_gh`` serve path (``/mergers/{id}/{file}``) on success, or
    None if the link is off-domain, unsafe, or the download fails. Existing
    files are left in place (never re-downloaded).

    ``extra_headers`` carries the live browser's Cookie + User-Agent (see
    ``browser_session_headers``); passing them lets the request reuse the
    Cloudflare clearance the browser already obtained, so the document fetch
    isn't bounced back to the challenge the way a bare ``requests.get()`` would
    be.
    """
    if not is_safe_document_url(url):
        # Off-domain link (e.g. a party's own site) — keep the url, no mirror.
        return None

    result = _document_local_path(merger_id, url)
    if result is None:
        print(f"    Warning: unsafe document filename for {url}", file=sys.stderr)
        return None
    local_path, url_gh = result

    if local_path.exists():
        return url_gh

    headers = {"User-Agent": USER_AGENT}
    if extra_headers:
        headers.update(extra_headers)

    try:
        local_path.parent.mkdir(parents=True, exist_ok=True)
        resp = requests.get(
            url, headers=headers, stream=True, timeout=REQUEST_TIMEOUT
        )
        resp.raise_for_status()
        # A challenge page comes back as 200 text/html, not the PDF we asked
        # for — peek at the first chunk and don't save it under a .pdf name.
        chunks = resp.iter_content(chunk_size=8192)
        first = next(chunks, b"")
        if b"Just a moment" in first[:2048] or b"challenge-platform" in first:
            print(
                f"    Warning: {url} returned a Cloudflare challenge, not saving",
                file=sys.stderr,
            )
            return None
        with open(local_path, "wb") as f:
            if first:
                f.write(first)
            for chunk in chunks:
                f.write(chunk)
    except requests.RequestException as e:
        print(f"    Warning: failed to download {url}: {e}", file=sys.stderr)
        return None
    except OSError as e:
        print(f"    Warning: failed to save {local_path}: {e}", file=sys.stderr)
        return None

    print(f"    Downloaded {local_path.name}")
    return url_gh


def load_appeals() -> tuple[dict, dict]:
    """Return (full raw dict incl. metadata keys, records-only dict).

    The raw dict is kept so metadata keys (``_comment``) and key order survive a
    round-trip; the records-only view drops keys starting with ``_``.
    """
    with open(TRIBUNAL_APPEALS_JSON, "r", encoding="utf-8") as f:
        raw = json.load(f)
    records = {k: v for k, v in raw.items() if not k.startswith("_")}
    return raw, records


def clean_description(value: str | None) -> str | None:
    """Strip the trailing '(PDF, 537.8 KB)'-style file annotation from a title."""
    if not value:
        return None
    text = " ".join(value.split())
    return _FILE_ANNOTATION_RE.sub("", text).strip() or None


def normalise_date(value: str | None) -> str | None:
    """Normalise a human date string to YYYY-MM-DD, or return it unchanged."""
    if not value:
        return None
    text = " ".join(value.split())
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return text or None


def normalise_confidentiality(value: str | None) -> str | None:
    """Map free text to 'Confidential' / 'Non-confidential', else pass through."""
    if not value:
        return None
    text = " ".join(value.split()).lower()
    if "non" in text and "confiden" in text:
        return "Non-confidential"
    if "confiden" in text:
        return "Confidential"
    return " ".join(value.split()) or None


def _content_root(soup: BeautifulSoup):
    """Best-effort main-content container, to avoid header/footer tables."""
    for selector in ("main", '[role="main"]', ".region-content", "#content"):
        node = soup.select_one(selector)
        if node is not None:
            return node
    return soup


def _header_row(table):
    """Return the row whose cells are the column headers.

    Prefers an explicit ``<thead>`` row; otherwise the table's first ``<tr>``,
    which on the tribunal site lives inside ``<tbody>`` (there's no separate
    ``<thead>``). Returned so the caller can both read the header for column
    mapping and exclude that exact row from the data rows.
    """
    thead = table.find("thead")
    if thead is not None:
        tr = thead.find("tr")
        if tr is not None:
            return tr
    return table.find("tr")


def _header_field_map(table) -> tuple[dict[int, str], object]:
    """Return (column index → document field name, header row element)."""
    header_row = _header_row(table)
    field_map: dict[int, str] = {}
    if header_row is None:
        return field_map, None
    for idx, cell in enumerate(header_row.find_all(["th", "td"])):
        header = " ".join(cell.get_text(" ", strip=True).split()).lower()
        for field, keyword in _COLUMN_KEYWORDS:
            if keyword in header and idx not in field_map:
                field_map[idx] = field
                break
    return field_map, header_row


def _body_rows(table, header_row=None):
    """Yield a table's data rows, excluding the header row.

    The header row is excluded by identity, which matters on the tribunal site:
    its header row sits inside ``<tbody>`` (no ``<thead>``), so a naive "all
    tbody rows" would return the header as a bogus data row.
    """
    body = table.find("tbody")
    rows = body.find_all("tr") if body is not None else table.find_all("tr")
    return [row for row in rows if row is not header_row]


def parse_document_row(row, field_map: dict[int, str], base_url: str) -> dict | None:
    """Parse one table row into a document dict, or None if it's empty."""
    cells = row.find_all(["td", "th"])
    if not cells:
        return None

    doc: dict = {
        "date": None,
        "filed_by": None,
        "description": None,
        "confidentiality": None,
        "url": None,
    }

    for idx, cell in enumerate(cells):
        field = field_map.get(idx)
        text = " ".join(cell.get_text(" ", strip=True).split())
        # The document link can live in any cell; take the first one we see.
        if doc["url"] is None:
            link = cell.find("a", href=True)
            if link is not None:
                doc["url"] = urljoin(base_url, link["href"])
                if not text:
                    text = " ".join(link.get_text(" ", strip=True).split())
        if field and not doc.get(field):
            doc[field] = text

    doc["date"] = normalise_date(doc["date"])
    doc["description"] = clean_description(doc["description"])
    doc["confidentiality"] = normalise_confidentiality(doc["confidentiality"])

    # A row with no link and no description is noise (spacer / empty row).
    if not doc["url"] and not doc["description"]:
        return None
    return doc


def parse_matter_page(html: str, base_url: str) -> list[dict]:
    """Parse a tribunal matter page into an ordered list of document dicts.

    The first table's documents have ``section`` = None; each later table's
    documents carry the text of the nearest preceding ``<h3>`` as ``section``.
    """
    soup = BeautifulSoup(html, "lxml")
    root = _content_root(soup)

    documents: list[dict] = []
    current_section: str | None = None
    table_index = 0

    for node in root.find_all(["h3", "table"]):
        if node.name == "h3":
            current_section = " ".join(node.get_text(" ", strip=True).split()) or None
            continue

        # node is a <table>. The first table is always the main document set.
        section = None if table_index == 0 else current_section
        table_index += 1

        field_map, header_row = _header_field_map(node)
        if not field_map:
            # Not a recognisable document table (no matching headers); skip it.
            continue

        for row in _body_rows(node, header_row):
            doc = parse_document_row(row, field_map, base_url)
            if doc is None:
                continue
            if section is not None:
                doc["section"] = section
            documents.append(doc)

    return documents


def looks_like_challenge(html: str) -> bool:
    return any(marker in html for marker in CHALLENGE_MARKERS)


def gha_warning(message: str) -> None:
    """Emit a GitHub Actions warning annotation (visible on the run summary).

    A no-op outside Actions (GITHUB_ACTIONS unset) so local runs aren't spammed
    with workflow-command syntax.
    """
    if os.environ.get("GITHUB_ACTIONS") == "true":
        print(f"::warning::{message}")


def find_chrome() -> str:
    """Locate a Chrome/Chromium binary (CHROME_PATH env wins)."""
    env = os.environ.get("CHROME_PATH")
    if env and os.path.exists(env):
        return env
    for candidate in (
        "google-chrome",
        "google-chrome-stable",
        "chromium-browser",
        "chromium",
    ):
        path = which(candidate)
        if path:
            return path
    raise FileNotFoundError("Could not find a Chrome/Chromium binary")


def free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def launch_chrome(chrome_path: str, port: int, user_data_dir: str):
    args = [
        chrome_path,
        *CHROME_ARGS,
        f"--user-data-dir={user_data_dir}",
        "--remote-debugging-host=127.0.0.1",
        f"--remote-debugging-port={port}",
        "about:blank",
    ]
    print(f"Launching Chrome: {chrome_path} (port {port})", flush=True)
    return subprocess.Popen(
        args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )


def wait_for_devtools(port: int, timeout: float = 30.0) -> bool:
    """Wait until Chrome's DevTools endpoint answers before attaching nodriver.

    nodriver's own launcher only waits ~2.5s for the port, which loses a race
    against Chrome's ~3s cold start on CI runners, so we manage the readiness
    wait ourselves.
    """
    deadline = time.time() + timeout
    url = f"http://127.0.0.1:{port}/json/version"
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as r:
                data = json.load(r)
                print(f"DevTools ready: {data.get('Browser')}", flush=True)
                return True
        except Exception:
            time.sleep(0.5)
    return False


async def try_click_turnstile(tab) -> bool:
    """Best-effort click of the Cloudflare Turnstile / 'Verify you are human'
    checkbox. Managed challenges often auto-clear, but some render a checkbox
    that must be clicked."""
    for text in ("Verify you are human", "Verify you are a human", "human"):
        try:
            el = await tab.find(text, best_match=True, timeout=3)
            if el:
                await el.mouse_click()
                print(f"    clicked element matching '{text}'", flush=True)
                return True
        except Exception:
            pass
    try:
        iframe = await tab.find("challenges.cloudflare.com", best_match=True, timeout=3)
        if iframe:
            await iframe.mouse_click()
            print("    clicked cloudflare iframe", flush=True)
            return True
    except Exception:
        pass
    return False


async def fetch_page(browser, url: str):
    """Navigate the browser to ``url`` and wait for the Cloudflare challenge to
    clear. Returns ``(tab, html)`` — ``html`` is None if the challenge never
    cleared within ``MAX_WAIT_SECONDS``."""
    tab = await browser.get(url)

    deadline = time.time() + MAX_WAIT_SECONDS
    html = ""
    cleared = False
    attempt = 0
    while time.time() < deadline:
        attempt += 1
        await tab.sleep(3)
        try:
            html = await tab.get_content()
        except Exception as e:
            print(f"    get_content failed: {e}", flush=True)
            continue

        title = ""
        m = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
        if m:
            title = m.group(1).strip()
        print(
            f"    attempt {attempt}: {len(html)} bytes, title={title!r}",
            flush=True,
        )

        if not looks_like_challenge(html):
            cleared = True
            break

        await try_click_turnstile(tab)

    if not cleared:
        return tab, None

    try:
        html = await tab.get_content()
    except Exception:
        pass
    return tab, html


async def browser_session_headers(browser, tab) -> dict:
    """Build the Cookie + User-Agent headers from the live browser session.

    Reused for the document downloads so they carry the same Cloudflare
    clearance the browser obtained solving the challenge.
    """
    headers: dict = {}
    try:
        cookies = await browser.cookies.get_all()
        cookie_header = "; ".join(
            f"{c.name}={c.value}" for c in cookies if getattr(c, "name", None)
        )
        if cookie_header:
            headers["Cookie"] = cookie_header
    except Exception as e:
        print(f"    could not read cookies: {e}", flush=True)
    try:
        user_agent = await tab.evaluate("navigator.userAgent")
        if user_agent:
            headers["User-Agent"] = user_agent
    except Exception:
        pass
    return headers


def merge_documents(existing: list[dict], scraped: list[dict]) -> list[dict]:
    """Return the scraped documents, carrying over url_gh from existing docs.

    Existing documents are matched to scraped ones by URL so hand-added local
    mirror paths (``url_gh``) survive a re-scrape. The scraped list is otherwise
    authoritative for the page's contents and ordering.
    """
    gh_by_url = {
        doc.get("url"): doc.get("url_gh")
        for doc in (existing or [])
        if doc.get("url") and doc.get("url_gh")
    }
    for doc in scraped:
        url_gh = gh_by_url.get(doc.get("url"))
        if url_gh:
            doc["url_gh"] = url_gh
    return scraped


async def scrape_matters(
    targets: list[str], records: dict, do_download: bool
) -> tuple[dict[str, list[dict]], list[str]]:
    """Drive one Chrome across every target matter page.

    Returns ``(scraped_by_id, failed)`` where ``scraped_by_id`` maps merger_id →
    parsed document list (already carrying ``url_gh`` for anything downloaded),
    and ``failed`` lists the merger_ids whose page couldn't be fetched. Matters
    whose page parsed to zero documents are omitted from both (left untouched).
    """
    if uc is None:
        raise RuntimeError(
            "nodriver is not installed; run "
            "`pip install -r scripts/requirements-tribunal.txt`"
        )

    chrome_path = find_chrome()
    port = free_port()
    user_data_dir = tempfile.mkdtemp(prefix="cf-tribunal-")
    proc = launch_chrome(chrome_path, port, user_data_dir)

    if not wait_for_devtools(port):
        print("ERROR: Chrome DevTools endpoint never became ready", flush=True)
        try:
            proc.terminate()
        except Exception:
            pass
        # Nothing could be fetched — every target is a failure.
        return {}, list(targets)

    browser = await uc.start(
        host="127.0.0.1", port=port, browser_executable_path=chrome_path
    )

    scraped_by_id: dict[str, list[dict]] = {}
    failed: list[str] = []
    session_headers: dict | None = None

    try:
        for mid in targets:
            url = records[mid].get("tribunal_url")
            if not url:
                print(f"Skipping {mid}: no tribunal_url")
                continue

            print(f"Scraping {mid}: {url}", flush=True)
            tab, html = await fetch_page(browser, url)
            if html is None:
                print(
                    f"  FAILED: challenge did not clear for {mid} ({url})",
                    file=sys.stderr,
                )
                gha_warning(
                    f"scrape_tribunal: Cloudflare challenge did not clear for "
                    f"{mid} ({url})"
                )
                failed.append(mid)
                continue

            scraped = parse_matter_page(html, url)
            if not scraped:
                print(
                    f"  Warning: no documents parsed for {mid}; leaving existing "
                    f"entry untouched (the page layout may have changed).",
                    file=sys.stderr,
                )
                continue

            # Mirror each document into data/raw/matters/{mid}/, reusing the
            # browser's Cloudflare cookies + user-agent so the file requests
            # aren't bounced back to the challenge.
            if do_download:
                if session_headers is None:
                    session_headers = await browser_session_headers(browser, tab)
                for doc in scraped:
                    if doc.get("url"):
                        url_gh = download_document(mid, doc["url"], session_headers)
                        if url_gh:
                            doc["url_gh"] = url_gh

            scraped_by_id[mid] = scraped
            sections = sorted({d["section"] for d in scraped if d.get("section")})
            summary = f"  Parsed {len(scraped)} document(s)"
            if sections:
                summary += f" across sections: {', '.join(sections)}"
            print(summary, flush=True)
    finally:
        try:
            browser.stop()
        except Exception:
            pass
        try:
            proc.terminate()
        except Exception:
            pass

    return scraped_by_id, failed


def scrape(
    merger_ids: list[str] | None, dry_run: bool, download: bool = True
) -> int:
    raw, records = load_appeals()

    if merger_ids:
        unknown = [mid for mid in merger_ids if mid not in records]
        for mid in unknown:
            print(f"Warning: {mid} is not in tribunal_appeals.json", file=sys.stderr)
        targets = [mid for mid in merger_ids if mid in records]
    else:
        targets = [
            mid for mid, rec in records.items() if rec.get("tribunal_url")
        ]

    if not targets:
        print("No tribunal matters with a tribunal_url to scrape.")
        return 0

    scraped_by_id, failed = uc.loop().run_until_complete(
        scrape_matters(targets, records, do_download=download and not dry_run)
    )

    changed = 0
    for mid, scraped in scraped_by_id.items():
        record = records[mid]
        merged = merge_documents(record.get("documents"), scraped)
        if merged != record.get("documents"):
            record["documents"] = merged
            changed += 1

    if dry_run:
        print(f"\nDry run: {changed} entr(y/ies) would change; nothing written.")
    elif changed:
        with open(TRIBUNAL_APPEALS_JSON, "w", encoding="utf-8") as f:
            json.dump(raw, f, indent=2, ensure_ascii=False)
            f.write("\n")
        print(f"\nUpdated {changed} entr(y/ies) in {TRIBUNAL_APPEALS_JSON}")
    else:
        print("\nNo changes.")

    if failed:
        # A distinct, non-zero exit so callers (the workflow, in particular)
        # can tell "ran clean, genuinely nothing new" apart from "one or more
        # fetches failed". See the FAILED lines above (and any GitHub Actions
        # ::warning:: annotations) for per-matter diagnostics.
        print(
            f"\n{len(failed)} of {len(targets)} matter(s) failed to fetch: "
            f"{', '.join(failed)}",
            file=sys.stderr,
        )
        return 2

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "merger_ids",
        nargs="*",
        help="Optional merger_ids to scrape (default: all entries with a tribunal_url).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and report changes without writing the JSON or downloading files.",
    )
    parser.add_argument(
        "--no-download",
        action="store_true",
        help="Record document metadata only; do not download the linked files.",
    )
    args = parser.parse_args()

    if uc is None:
        print(
            "ERROR: nodriver is not installed; run "
            "`pip install -r scripts/requirements-tribunal.txt`",
            file=sys.stderr,
        )
        return 1

    return scrape(args.merger_ids or None, args.dry_run, download=not args.no_download)


if __name__ == "__main__":
    raise SystemExit(main())
