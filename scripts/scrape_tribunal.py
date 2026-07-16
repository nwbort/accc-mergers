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

Until now the ``documents[]`` list has been edited by hand. This script fills
it in from the live tribunal pages. The "list of pages to scrape" is simply the
set of entries in tribunal_appeals.json that carry a ``tribunal_url`` — that
file is the manual list, maintained by hand when a new matter is added.

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

Usage — run this locally, not from CI
--------------------------------------
The tribunal site sits behind Cloudflare bot management, which serves
GitHub Actions' hosted-runner IPs a JS challenge page ("Just a moment...",
``cf-mitigated: challenge``) instead of the real content. No amount of
User-Agent or header tweaking gets past that — it requires an actual
JS-executing browser to solve, which nothing in this script does. A normal
residential/office IP is not challenged, so **run this from your own
machine**, then commit and push the result:

  pip install -r scripts/requirements.txt   # requests, beautifulsoup4, lxml
  python scripts/scrape_tribunal.py                 # scrape + download every entry with a tribunal_url
  python scripts/scrape_tribunal.py MN-01068 ...    # scrape only these merger_ids
  python scripts/scrape_tribunal.py --no-download   # record metadata only, skip file downloads
  python scripts/scrape_tribunal.py --dry-run       # parse and report, don't write or download
  git add data/processed/tribunal_appeals.json data/raw/matters
  git commit -m "Update scraped tribunal data" && git push

Also requires ``curl`` on PATH (see "Fetching via curl" below) — already
present on macOS/Linux; on Windows use Git Bash or WSL.

The ``scrape-tribunal.yml`` workflow (``workflow_dispatch``) still exists and
can be triggered from the Actions tab, but expect it to fail with the
Cloudflare challenge diagnostics described below rather than actually
scraping anything — it's kept mainly so a run makes the failure visible
(``::warning::`` annotation) rather than silent, in case Cloudflare's
treatment of the runner IPs ever changes.

Existing ``url_gh`` local-mirror paths are preserved across a re-scrape (matched
by document URL). If a page yields no rows (e.g. the layout changed), that
entry is left untouched rather than wiped.

Fetching via curl
------------------
Matter pages are fetched by shelling out to ``curl`` rather than using the
``requests`` library (``download_document`` still uses ``requests`` for the
document files themselves, which aren't behind the same protection) because
curl's TLS fingerprint gets past a plain block/reputation check the way
``scrape.sh``'s curl-based ACCC fetch does — but it can't solve a Cloudflare
JS challenge either way, which is what's actually happening here (see above).
If a fetch fails, the response status, a few identifying response headers
(``server``, ``cf-*``, ``x-akamai-*``, etc.) and a body snippet are logged,
and a ``::warning::`` annotation is emitted under GitHub Actions so the
failure is visible on the run summary rather than only in the raw logs.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import unicodedata
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

SCRIPT_DIR = Path(__file__).parent
REPO_ROOT = SCRIPT_DIR.parent
TRIBUNAL_APPEALS_JSON = REPO_ROOT / "data" / "processed" / "tribunal_appeals.json"
# Downloaded documents are mirrored under data/raw/matters/{merger_id}/, the same
# tree the ACCC scraper uses, so the DOCX→PDF convert workflow and the Cloudflare
# /mergers/{id}/{file} route pick them up with no extra wiring.
MATTERS_DIR = REPO_ROOT / "data" / "raw" / "matters"

USER_AGENT = "Mozilla/5.0 (compatible; mergers-fyi/1.0; +https://mergers.fyi)"
REQUEST_TIMEOUT = 30

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


def download_document(merger_id: str, url: str) -> str | None:
    """Download a tribunal document into data/raw/matters/{merger_id}/.

    Returns the ``url_gh`` serve path (``/mergers/{id}/{file}``) on success, or
    None if the link is off-domain, unsafe, or the download fails. Existing
    files are left in place (never re-downloaded).
    """
    if not is_safe_document_url(url):
        # Off-domain link (e.g. a party's own site) — keep the url, no mirror.
        return None

    decoded = unquote(urlparse(url).path)
    original = os.path.basename(decoded).strip()
    if is_safe_filename(original):
        filename = original
    else:
        filename = sanitize_filename(original)
    if not filename:
        print(f"    Warning: unsafe document filename for {url}", file=sys.stderr)
        return None

    matter_dir = MATTERS_DIR / merger_id
    local_path = matter_dir / filename
    url_gh = f"/mergers/{merger_id}/{get_serve_filename(filename)}"

    if local_path.exists():
        return url_gh

    try:
        matter_dir.mkdir(parents=True, exist_ok=True)
        resp = requests.get(
            url, headers={"User-Agent": USER_AGENT}, stream=True, timeout=REQUEST_TIMEOUT
        )
        resp.raise_for_status()
        with open(local_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
    except requests.RequestException as e:
        print(f"    Warning: failed to download {url}: {e}", file=sys.stderr)
        return None
    except OSError as e:
        print(f"    Warning: failed to save {local_path}: {e}", file=sys.stderr)
        return None

    print(f"    Downloaded {filename}")
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


def _header_field_map(table) -> dict[int, str]:
    """Map column index → document field name from a table's header row."""
    header_cells = table.select("thead th")
    if not header_cells:
        first_row = table.find("tr")
        if first_row is not None:
            header_cells = first_row.find_all(["th", "td"])
    field_map: dict[int, str] = {}
    for idx, cell in enumerate(header_cells):
        header = " ".join(cell.get_text(" ", strip=True).split()).lower()
        for field, keyword in _COLUMN_KEYWORDS:
            if keyword in header and idx not in field_map:
                field_map[idx] = field
                break
    return field_map


def _body_rows(table):
    """Yield the data rows of a table (skipping the header row if there's no tbody)."""
    body = table.find("tbody")
    if body is not None:
        return body.find_all("tr")
    rows = table.find_all("tr")
    # No explicit tbody: assume the first row was the header.
    return rows[1:] if rows else []


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

        field_map = _header_field_map(node)
        if not field_map:
            # Not a recognisable document table (no matching headers); skip it.
            continue

        for row in _body_rows(node):
            doc = parse_document_row(row, field_map, base_url)
            if doc is None:
                continue
            if section is not None:
                doc["section"] = section
            documents.append(doc)

    return documents


# Response headers worth echoing on a failed fetch: they're the cheapest way
# to tell a WAF/bot-protection block (cf-*, x-akamai-*, server: cloudflare...)
# apart from an ordinary server error.
_DIAGNOSTIC_HEADER_PREFIXES = ("server:", "cf-", "x-akamai", "x-waf", "retry-after:")


def gha_warning(message: str) -> None:
    """Emit a GitHub Actions warning annotation (visible on the run summary).

    A no-op outside Actions (GITHUB_ACTIONS unset) so local runs aren't spammed
    with workflow-command syntax.
    """
    if os.environ.get("GITHUB_ACTIONS") == "true":
        print(f"::warning::{message}")


def fetch(url: str) -> str:
    """Fetch a tribunal page via curl.

    Uses curl rather than ``requests`` — see the "Fetching via curl" note in
    the module docstring for why. Raises RuntimeError on any non-2xx/transport
    failure, with diagnostics (status, relevant headers, body snippet)
    attached to the message.
    """
    with tempfile.TemporaryDirectory() as tmp:
        body_path = os.path.join(tmp, "body")
        headers_path = os.path.join(tmp, "headers")
        result = subprocess.run(
            [
                "curl", "-sS", "-L", "--compressed",
                "-A", USER_AGENT,
                "--max-time", str(REQUEST_TIMEOUT),
                "--retry", "1", "--retry-delay", "5", "--retry-max-time", "90",
                "-D", headers_path,
                "-o", body_path,
                "-w", "%{http_code}",
                url,
            ],
            capture_output=True,
            text=True,
        )
        status = result.stdout.strip()
        body = Path(body_path).read_text(encoding="utf-8", errors="replace") if os.path.exists(body_path) else ""
        headers_text = Path(headers_path).read_text(encoding="utf-8", errors="replace") if os.path.exists(headers_path) else ""

        if result.returncode == 0 and status.startswith("2"):
            return body

        interesting_headers = [
            line.strip()
            for line in headers_text.splitlines()
            if line.strip().lower().startswith(_DIAGNOSTIC_HEADER_PREFIXES)
        ]
        snippet = " ".join(body.split())[:300]
        detail = (
            f"curl exit={result.returncode} http={status or 'n/a'}"
            f" curl_stderr={result.stderr.strip()[:200]!r}"
            f" headers=[{'; '.join(interesting_headers) or 'none'}]"
            f" body={snippet!r}"
        )
        raise RuntimeError(detail)


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

    changed = 0
    for mid in targets:
        record = records[mid]
        url = record.get("tribunal_url")
        if not url:
            print(f"Skipping {mid}: no tribunal_url")
            continue

        print(f"Scraping {mid}: {url}")
        try:
            html = fetch(url)
        except (RuntimeError, OSError) as e:
            print(f"  FAILED to fetch {url}: {e}", file=sys.stderr)
            gha_warning(f"scrape_tribunal: failed to fetch {mid} ({url}): {e}")
            continue

        scraped = parse_matter_page(html, url)
        if not scraped:
            print(
                f"  Warning: no documents parsed for {mid}; leaving existing "
                f"entry untouched (the page layout may have changed).",
                file=sys.stderr,
            )
            continue

        # Mirror each document's PDF into data/raw/matters/{mid}/ and record its
        # url_gh serve path. Skipped on a dry run so the run stays side-effect
        # free. merge_documents then carries over any existing url_gh for docs
        # that weren't (or couldn't be) downloaded.
        if download and not dry_run:
            for doc in scraped:
                if doc.get("url"):
                    url_gh = download_document(mid, doc["url"])
                    if url_gh:
                        doc["url_gh"] = url_gh

        merged = merge_documents(record.get("documents"), scraped)
        sections = sorted({d["section"] for d in merged if d.get("section")})
        summary = f"  Parsed {len(merged)} document(s)"
        if sections:
            summary += f" across sections: {', '.join(sections)}"
        print(summary)

        if merged != record.get("documents"):
            record["documents"] = merged
            changed += 1

    if dry_run:
        print(f"\nDry run: {changed} entr(y/ies) would change; nothing written.")
        return 0

    if changed:
        with open(TRIBUNAL_APPEALS_JSON, "w", encoding="utf-8") as f:
            json.dump(raw, f, indent=2, ensure_ascii=False)
            f.write("\n")
        print(f"\nUpdated {changed} entr(y/ies) in {TRIBUNAL_APPEALS_JSON}")
    else:
        print("\nNo changes.")
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
    return scrape(args.merger_ids or None, args.dry_run, download=not args.no_download)


if __name__ == "__main__":
    raise SystemExit(main())
