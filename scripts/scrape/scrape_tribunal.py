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
the rest.

Linked documents are downloaded *by the browser itself*, via a ``fetch()``
evaluated in the matter page's own context (``download_document_via_browser``).
Handing the browser's cookies and User-Agent to ``requests`` is not enough:
Cloudflare ties the clearance to the client that earned it, down to its TLS
fingerprint, so a Python-side fetch carrying those cookies is still answered
with 403. That requests-based path survives only as a fallback.

Cloudflare judges each request on its own, and now and then it decides to
challenge one of those document fetches. A subresource request has nowhere to
display a challenge, so it is refused with a 403 (``cf-mitigated: challenge``)
that no amount of cookie-passing can satisfy — which is how a single document
ended up recorded but unmirrored while the seventeen alongside it downloaded
fine. Two things answer that: the fetch is retried a few seconds apart
(Cloudflare usually waves the next one through), and if it is still refused the
scraper *navigates* to the document, because a top-level request can be
challenged and cleared, and then comes back and fetches it again.

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
  python -m scripts.scrape.scrape_tribunal                 # scrape + download every entry with a tribunal_url
  python -m scripts.scrape.scrape_tribunal MN-01068 ...    # scrape only these merger_ids
  python -m scripts.scrape.scrape_tribunal --no-download   # record metadata only, skip file downloads
  python -m scripts.scrape.scrape_tribunal --dry-run       # parse and report, don't write or download
  git add data/processed/tribunal_appeals.json data/raw/matters
  git commit -m "Update scraped tribunal data" && git push

On a headless machine (a CI runner) run it under an X server so Chrome runs
headful, which is far less likely to be flagged than headless::

  xvfb-run -a python -m scripts.scrape.scrape_tribunal

The merge is additive. Existing ``url_gh`` local-mirror paths are preserved
across a re-scrape (matched by document URL), and so is any document the
tribunal has since removed from its table — it keeps its place in the list
relative to the filings around it. The tribunal does prune its own tables (a
superseded documentary index, say), but those filings remain part of the
matter's history, are still mirrored under ``data/raw/matters/`` and are still
rendered as merger timeline events, so dropping them would silently erase
events from the site. Removals are reported on each run; to drop a document for
good, delete it from ``tribunal_appeals.json`` by hand.

If a page yields no rows (e.g. the layout changed) or its Cloudflare challenge
never clears, that entry is left untouched rather than wiped.

A document whose file can't be downloaded is still recorded (with its tribunal
``url``, just no ``url_gh``) and raises a ``::warning::`` annotation, so it is
visible on the run summary rather than hiding behind a green run. The next run
retries it, since anything without a local file is re-fetched.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import binascii
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

from scripts.paths import REPO_ROOT

# nodriver is only needed to actually fetch pages (it drives Chrome). Import it
# lazily so the parsing/download helpers below stay importable — and unit
# testable — in environments that only install requests + bs4 + lxml (e.g. the
# main test job), without pulling in a browser-automation dependency.
try:
    import nodriver as uc
except ImportError:  # pragma: no cover - exercised only where nodriver is absent
    uc = None

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

# Ceiling on any single nodriver/CDP call (navigate, get_content, evaluate, ...).
# The 2026-08-26 run got stuck on exactly this: tab.get_content() inside
# fetch_page()'s wait loop never returned, so the loop's own MAX_WAIT_SECONDS
# deadline (only checked *between* iterations) was never reached, and the job
# ran until GitHub's 6-hour default job timeout killed it. Every awaited
# nodriver call is wrapped in _with_timeout() below so a stalled CDP round-trip
# raises instead of hanging forever.
CDP_CALL_TIMEOUT_SECONDS = 30


async def _with_timeout(coro, what: str, seconds: float = CDP_CALL_TIMEOUT_SECONDS):
    """Await ``coro``, converting a hang into a TimeoutError after ``seconds``."""
    try:
        return await asyncio.wait_for(coro, timeout=seconds)
    except asyncio.TimeoutError:
        raise TimeoutError(f"{what} did not respond within {seconds}s")


# How many times to ask the browser for one document, and how long to wait
# between tries. Cloudflare decides per request: the same file that downloads
# first go on one run is sometimes answered with a 403 carrying
# ``cf-mitigated: challenge`` on the next. A challenge can only be *solved* by
# a request that can display it, so a fetch() answered that way is simply
# refused — but the refusal is transient, and asking again a few seconds later
# usually goes straight through.
BROWSER_FETCH_ATTEMPTS = 3
BROWSER_FETCH_RETRY_SECONDS = 5

# Statuses worth another try. 403 is here because that is how Cloudflare turns
# away a request it wanted to challenge, not because these public documents are
# actually forbidden. 404/410 are deliberately absent: a link that points at
# nothing will still point at nothing in five seconds.
RETRYABLE_FETCH_STATUSES = frozenset({403, 408, 425, 429, 500, 502, 503, 504})

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


def _is_challenge_payload(data: bytes) -> bool:
    """True if downloaded bytes are a Cloudflare interstitial, not the file.

    A challenge comes back as 200 text/html, so without this check it would be
    saved under the document's .pdf name.
    """
    return b"Just a moment" in data[:2048] or b"challenge-platform" in data


def _resolve_download_target(merger_id: str, url: str) -> tuple[Path, str] | None:
    """Shared preflight for both download paths.

    Returns (local_path, url_gh) when the URL should be fetched, or None when it
    must be skipped — off-domain, an unsafe filename, or already mirrored (in
    which case the caller's ``already_have`` check applies).
    """
    if not is_safe_document_url(url):
        # Off-domain link (e.g. a party's own site) — keep the url, no mirror.
        return None

    result = _document_local_path(merger_id, url)
    if result is None:
        print(f"    Warning: unsafe document filename for {url}", file=sys.stderr)
        return None
    return result


# Fetches a document from inside the page's own JS context and hands the bytes
# back base64-encoded. %s is the JSON-quoted URL. Same-origin with the matter
# page, so the browser attaches its Cloudflare cookies automatically.
#
# The result is a single prefixed *string* rather than an object on purpose:
# nodriver asks CDP for deep serialization, which (per the protocol) overrides
# returnByValue, so an object comes back as a nested RemoteObject tree instead
# of a dict. A plain string passes through Tab.evaluate untouched.
_BROWSER_FETCH_OK = "ok:"
_BROWSER_FETCH_ERROR = "error:"
_BROWSER_FETCH_JS = """
(async () => {
  try {
    const resp = await fetch(%s, {credentials: 'include', redirect: 'follow'});
    if (!resp.ok) {
      const mitigated = resp.headers.get('cf-mitigated');
      return 'error:HTTP ' + resp.status + (mitigated ? ' (cf-mitigated: ' + mitigated + ')' : '');
    }
    const bytes = new Uint8Array(await resp.arrayBuffer());
    let binary = '';
    const CHUNK = 0x8000;
    for (let i = 0; i < bytes.length; i += CHUNK) {
      binary += String.fromCharCode.apply(null, bytes.subarray(i, i + CHUNK));
    }
    return 'ok:' + btoa(binary);
  } catch (e) {
    return 'error:' + String(e);
  }
})()
"""


def _retryable_fetch_failure(detail: str) -> bool:
    """True if a failed in-page fetch is worth repeating.

    ``detail`` is whatever the page reported — ``HTTP 403 (cf-mitigated:
    challenge)``, a network-level ``TypeError: Failed to fetch``, or a note that
    evaluate() handed back something unexpected. Only a status we know to be
    durable (a 404 for a link that points at nothing) stops the retries.
    """
    status = re.match(r"HTTP (\d{3})", detail)
    if status:
        return int(status.group(1)) in RETRYABLE_FETCH_STATUSES
    # A network error or a CDP hiccup: no status to judge, so try again.
    return True


async def _browser_fetch(tab, url: str) -> tuple[bytes | None, str]:
    """Run one in-page fetch. Returns ``(bytes, "")`` or ``(None, detail)``."""
    try:
        payload = await _with_timeout(
            tab.evaluate(_BROWSER_FETCH_JS % json.dumps(url), await_promise=True),
            "tab.evaluate (document fetch)",
            seconds=REQUEST_TIMEOUT,
        )
    except Exception as e:
        return None, f"evaluate raised {e}"

    if not isinstance(payload, str) or not payload.startswith(_BROWSER_FETCH_OK):
        # Either the page reported a failure ("error:HTTP 403") or evaluate gave
        # back something other than our string (a CDP ExceptionDetails, say).
        if isinstance(payload, str) and payload.startswith(_BROWSER_FETCH_ERROR):
            return None, payload[len(_BROWSER_FETCH_ERROR):]
        return None, f"unexpected result {type(payload).__name__}"

    try:
        data = base64.b64decode(payload[len(_BROWSER_FETCH_OK):], validate=True)
    except (ValueError, binascii.Error) as e:
        return None, f"undecodable payload: {e}"

    if not data:
        return None, "no bytes returned"
    if _is_challenge_payload(data):
        # A challenge served with a 200, which the status check can't catch.
        return None, "Cloudflare challenge instead of the file"
    return data, ""


async def download_document_via_browser(tab, merger_id: str, url: str) -> str | None:
    """Download a tribunal document by fetching it from inside the live browser.

    This is the primary download path. Cloudflare binds the clearance it issues
    to the client that solved the challenge — its TLS/HTTP fingerprint, not just
    the ``cf_clearance`` cookie — so replaying that cookie from ``requests`` is
    still answered with 403 even when the browser's User-Agent is sent along.
    Running the fetch in the page's own context means the request comes from
    Chrome itself, and is served normally.

    Cloudflare still turns a fetch away now and then: it answers with a 403
    carrying ``cf-mitigated: challenge``, a challenge no subresource request can
    display and therefore none can solve. That verdict is per request and not
    sticky, so the fetch is simply repeated (:data:`BROWSER_FETCH_ATTEMPTS`
    times, :data:`BROWSER_FETCH_RETRY_SECONDS` apart) before giving up. Without
    that, one unlucky request left a document recorded but unmirrored for a
    whole day, until the next scheduled run happened to be luckier.

    Returns the ``url_gh`` serve path on success, or None so the caller can fall
    back to :func:`download_document`.
    """
    result = _resolve_download_target(merger_id, url)
    if result is None:
        return None
    local_path, url_gh = result

    if local_path.exists():
        return url_gh

    for attempt in range(1, BROWSER_FETCH_ATTEMPTS + 1):
        data, detail = await _browser_fetch(tab, url)
        if data is not None:
            break

        retryable = _retryable_fetch_failure(detail)
        last = attempt == BROWSER_FETCH_ATTEMPTS
        print(
            f"    Warning: browser fetch of {url} failed"
            f" (attempt {attempt}/{BROWSER_FETCH_ATTEMPTS}): {detail}",
            file=sys.stderr,
        )
        if last or not retryable:
            return None
        await asyncio.sleep(BROWSER_FETCH_RETRY_SECONDS)

    try:
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_bytes(data)
    except OSError as e:
        print(f"    Warning: failed to save {local_path}: {e}", file=sys.stderr)
        return None

    print(f"    Downloaded {local_path.name}")
    return url_gh


def download_document(
    merger_id: str, url: str, extra_headers: dict | None = None
) -> str | None:
    """Download a tribunal document into data/raw/matters/{merger_id}/.

    Fallback for :func:`download_document_via_browser`, used when the in-page
    fetch is unavailable or fails. Returns the ``url_gh`` serve path
    (``/mergers/{id}/{file}``) on success, or None if the link is off-domain,
    unsafe, or the download fails. Existing files are left in place (never
    re-downloaded).

    ``extra_headers`` carries the live browser's Cookie + User-Agent (see
    ``browser_session_headers``). Note that these are not always enough on their
    own: Cloudflare fingerprints the client, so a document fetch replaying the
    browser's cookies from ``requests`` can still be answered with 403 — which
    is exactly why the browser path above is tried first.
    """
    result = _resolve_download_target(merger_id, url)
    if result is None:
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
        if _is_challenge_payload(first):
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


def summarise_urls(urls: list[str], limit: int = 5) -> str:
    """Render document URLs as a short, readable list for a warning message.

    Uses just the filename — the tribunal's ``/__data/assets/pdf_file/0008/...``
    URLs are far too long to read in a run annotation — and truncates so one
    badly-broken matter can't flood the summary.
    """
    names = [os.path.basename(unquote(urlparse(url).path)) or url for url in urls]
    shown = ", ".join(names[:limit])
    if len(names) > limit:
        shown += f", and {len(names) - limit} more"
    return shown


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
            el = await _with_timeout(
                tab.find(text, best_match=True, timeout=3), "tab.find"
            )
            if el:
                await _with_timeout(el.mouse_click(), "mouse_click")
                print(f"    clicked element matching '{text}'", flush=True)
                return True
        except Exception:
            pass
    try:
        iframe = await _with_timeout(
            tab.find("challenges.cloudflare.com", best_match=True, timeout=3),
            "tab.find",
        )
        if iframe:
            await _with_timeout(iframe.mouse_click(), "mouse_click")
            print("    clicked cloudflare iframe", flush=True)
            return True
    except Exception:
        pass
    return False


async def fetch_page(browser, url: str):
    """Navigate the browser to ``url`` and wait for the Cloudflare challenge to
    clear. Returns ``(tab, html)`` — both None if the page couldn't even be
    navigated to; ``html`` alone is None if the challenge never cleared within
    ``MAX_WAIT_SECONDS``."""
    try:
        tab = await _with_timeout(browser.get(url), "browser.get")
    except Exception as e:
        print(f"    browser.get failed: {e}", flush=True)
        return None, None

    deadline = time.time() + MAX_WAIT_SECONDS
    html = ""
    cleared = False
    attempt = 0
    while time.time() < deadline:
        attempt += 1
        try:
            await _with_timeout(tab.sleep(3), "tab.sleep")
            html = await _with_timeout(tab.get_content(), "tab.get_content")
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
        html = await _with_timeout(tab.get_content(), "tab.get_content")
    except Exception:
        pass
    return tab, html


async def clear_challenge_by_visiting(browser, doc_url: str, matter_url: str):
    """Visit a document directly so Cloudflare can challenge a request that is
    able to answer, then come back to the matter page.

    A fetch() issued from the matter page is a subresource request: when
    Cloudflare decides to challenge it there is nowhere to render the challenge,
    so it is refused outright with a 403. A top-level navigation to the same URL
    *can* be challenged — and cleared, by the same wait-and-click loop that gets
    us onto the matter pages — after which the fetch is served normally.

    Returns the tab showing the matter page again, or None if that page could
    not be re-loaded, in which case the caller keeps the tab it already had.
    """
    print(f"    Visiting {doc_url} directly to clear the challenge", flush=True)
    try:
        _, doc_html = await fetch_page(browser, doc_url)
        if doc_html is None:
            print(
                f"    Warning: the challenge on {doc_url} did not clear either",
                file=sys.stderr,
            )
        tab, html = await fetch_page(browser, matter_url)
    except Exception as e:
        # Navigating to a document is best-effort: some of them are served as a
        # download rather than a page, which Chrome reports as an aborted
        # navigation. Never let that take the rest of the matter down with it.
        print(f"    Warning: visiting {doc_url} failed: {e}", file=sys.stderr)
        return None

    if html is None:
        print(
            f"    Warning: could not return to {matter_url} after visiting the "
            f"document",
            file=sys.stderr,
        )
        return None
    return tab


async def browser_session_headers(browser, tab) -> dict:
    """Build the Cookie + User-Agent headers from the live browser session.

    Reused for the document downloads so they carry the same Cloudflare
    clearance the browser obtained solving the challenge.
    """
    headers: dict = {}
    try:
        cookies = await _with_timeout(browser.cookies.get_all(), "cookies.get_all")
        cookie_header = "; ".join(
            f"{c.name}={c.value}" for c in cookies if getattr(c, "name", None)
        )
        if cookie_header:
            headers["Cookie"] = cookie_header
    except Exception as e:
        print(f"    could not read cookies: {e}", flush=True)
    try:
        user_agent = await _with_timeout(
            tab.evaluate("navigator.userAgent"), "tab.evaluate (user agent)"
        )
        if user_agent:
            headers["User-Agent"] = user_agent
    except Exception:
        pass
    return headers


def document_key(doc: dict) -> tuple:
    """Identity of a tribunal document, for matching across runs.

    The document URL is the identity where there is one — the tribunal's
    ``/__data/assets/pdf_file/0008/...`` paths are stable once published. A row
    without a link (rare, but the tables do carry the occasional link-less
    entry) falls back to the text fields that describe it.
    """
    url = doc.get("url")
    if url:
        return ("url", url)
    return (
        "text",
        doc.get("date"),
        doc.get("filed_by"),
        doc.get("description"),
    )


def _apply_scraped(existing: dict, scraped: dict) -> dict:
    """Fold a freshly scraped row onto the document already on file.

    The page is authoritative for the fields it publishes, but a blank cell
    never wipes a value we already hold, and keys the parser does not produce
    (``url_gh``, anything hand-added) are carried through. ``section`` is the
    exception: the parser only sets it for documents under a later table, so
    its absence is meaningful and it is dropped when the page no longer files
    the document under a heading.
    """
    merged = dict(existing)
    for key, value in scraped.items():
        if value is not None and value != "":
            merged[key] = value
    if "section" not in scraped:
        merged.pop("section", None)
    return merged


def merge_documents(existing: list[dict], scraped: list[dict]) -> list[dict]:
    """Merge a freshly scraped document list onto the one already on file.

    The scraped list drives the contents and ordering, but the merge is
    **additive**: a document that has dropped off the tribunal's table is kept,
    re-inserted where it used to sit relative to the documents that remain.
    The tribunal routinely prunes its filings table — superseded indexes, say —
    and those filings are still part of the matter's history, still mirrored
    under ``data/raw/matters/`` and still linked from the merger timeline, so
    losing them from the record would silently erase timeline events.

    Documents that survive on the page are refreshed from the scrape (see
    :func:`_apply_scraped`), which is what carries hand-added local mirror
    paths (``url_gh``) over a re-scrape.

    To drop a document for good, delete it from ``tribunal_appeals.json`` by
    hand — it will not come back unless the tribunal republishes it.
    """
    existing = list(existing or [])
    scraped_by_key = {document_key(doc): doc for doc in scraped}

    # Start from the scraped list, refreshed with anything we already held.
    existing_by_key = {document_key(doc): doc for doc in existing}
    merged = [
        _apply_scraped(existing_by_key[document_key(doc)], doc)
        if document_key(doc) in existing_by_key
        else doc
        for doc in scraped
    ]
    merged_index = {document_key(doc): i for i, doc in enumerate(merged)}

    # Walk the old list backwards re-inserting whatever the page dropped, each
    # one immediately before the nearest document that followed it and is still
    # listed (or at the end, when nothing after it survived). Going backwards
    # keeps runs of consecutive dropped documents in their original order,
    # since each insert lands at the same index as the one before it.
    anchor = len(merged)
    for doc in reversed(existing):
        key = document_key(doc)
        if key in scraped_by_key:
            anchor = merged_index[key]
            continue
        merged.insert(anchor, doc)
        merged_index = {document_key(d): i for i, d in enumerate(merged)}

    return merged


def dropped_documents(existing: list[dict], scraped: list[dict]) -> list[dict]:
    """Return the documents on file that the scraped page no longer lists."""
    scraped_keys = {document_key(doc) for doc in scraped}
    return [
        doc for doc in (existing or []) if document_key(doc) not in scraped_keys
    ]


async def scrape_matters(
    targets: list[str], records: dict, do_download: bool
) -> tuple[dict[str, list[dict]], list[str], list[tuple[str, str]]]:
    """Drive one Chrome across every target matter page.

    Returns ``(scraped_by_id, failed, unmirrored)`` where ``scraped_by_id`` maps
    merger_id → parsed document list (already carrying ``url_gh`` for anything
    downloaded), ``failed`` lists the merger_ids whose page couldn't be fetched,
    and ``unmirrored`` holds ``(merger_id, url)`` for each tribunal-hosted
    document that was recorded but couldn't be downloaded. Matters whose page
    parsed to zero documents are omitted from all three (left untouched).
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
        return {}, list(targets), []

    try:
        browser = await _with_timeout(
            uc.start(host="127.0.0.1", port=port, browser_executable_path=chrome_path),
            "uc.start",
        )
    except Exception as e:
        print(f"ERROR: could not attach to Chrome: {e}", flush=True)
        try:
            proc.terminate()
        except Exception:
            pass
        # Nothing could be fetched — every target is a failure.
        return {}, list(targets), []

    scraped_by_id: dict[str, list[dict]] = {}
    failed: list[str] = []
    unmirrored: list[tuple[str, str]] = []
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

            # Mirror each document into data/raw/matters/{mid}/. The fetch runs
            # inside the page that just cleared the challenge, so Cloudflare
            # serves it as an ordinary browser request; the requests-based path
            # is only a fallback, since replaying the browser's cookies from
            # Python is fingerprinted and answered with 403.
            if do_download:
                missing: list[str] = []
                # Visiting a document to clear a challenge costs a page load
                # each way, and one clearance covers the whole origin, so it is
                # worth doing at most once per matter: if it doesn't help the
                # first document it won't help the next.
                visited_to_clear = False
                for doc in scraped:
                    if not doc.get("url"):
                        continue
                    url_gh = await download_document_via_browser(tab, mid, doc["url"])
                    if (
                        url_gh is None
                        and not visited_to_clear
                        and is_safe_document_url(doc["url"])
                    ):
                        visited_to_clear = True
                        tab = (
                            await clear_challenge_by_visiting(
                                browser, doc["url"], url
                            )
                            or tab
                        )
                        url_gh = await download_document_via_browser(
                            tab, mid, doc["url"]
                        )
                    if url_gh is None:
                        if session_headers is None:
                            session_headers = await browser_session_headers(
                                browser, tab
                            )
                        url_gh = download_document(mid, doc["url"], session_headers)
                    if url_gh:
                        doc["url_gh"] = url_gh
                    elif is_safe_document_url(doc["url"]):
                        # Off-domain links are deliberately never mirrored, so
                        # only a tribunal-hosted file that didn't land counts.
                        missing.append(doc["url"])

                if missing:
                    unmirrored.extend((mid, url) for url in missing)
                    gha_warning(
                        f"scrape_tribunal: {len(missing)} document(s) for {mid} "
                        f"were recorded without a local mirror: "
                        f"{summarise_urls(missing)}"
                    )

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

    return scraped_by_id, failed, unmirrored


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

    scraped_by_id, failed, unmirrored = uc.loop().run_until_complete(
        scrape_matters(targets, records, do_download=download and not dry_run)
    )

    changed = 0
    delisted: list[tuple[str, dict]] = []
    for mid, scraped in scraped_by_id.items():
        record = records[mid]
        dropped = dropped_documents(record.get("documents"), scraped)
        delisted.extend((mid, doc) for doc in dropped)
        if dropped:
            gha_warning(
                f"scrape_tribunal: {len(dropped)} document(s) for {mid} are no "
                f"longer listed on the tribunal page and have been kept: "
                f"{summarise_urls([d['url'] for d in dropped if d.get('url')])}"
            )
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

    if delisted:
        # Kept, not dropped — see merge_documents. Reported so a document
        # disappearing from the tribunal's table is a visible event rather than
        # something only a diff of the raw JSON would reveal (there won't be
        # one: the record is unchanged).
        print(
            f"\n{len(delisted)} document(s) are no longer listed on the "
            f"tribunal page and were kept on file:",
            file=sys.stderr,
        )
        for mid, doc in delisted:
            label = doc.get("description") or doc.get("url") or "(untitled)"
            print(f"  {mid}: {doc.get('date') or '?'} — {label}", file=sys.stderr)

    if unmirrored:
        # Not fatal: the document is still recorded with its tribunal ``url``,
        # and the next run retries anything without a local file. Surfaced so a
        # persistently unmirrored document doesn't sit unnoticed behind a green
        # run — each one also raised a ::warning:: annotation above.
        print(
            f"\n{len(unmirrored)} document(s) recorded without a local mirror "
            f"(will be retried next run):",
            file=sys.stderr,
        )
        for mid, url in unmirrored:
            print(f"  {mid}: {url}", file=sys.stderr)

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
