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

Usage
-----
  python scripts/scrape_tribunal.py                 # scrape every entry with a tribunal_url
  python scripts/scrape_tribunal.py MN-01068 ...    # scrape only these merger_ids
  python scripts/scrape_tribunal.py --dry-run       # parse and report, don't write

Existing ``url_gh`` local-mirror paths are preserved across a re-scrape (matched
by document URL). If a page yields no rows (e.g. the layout changed), that
entry is left untouched rather than wiped.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

SCRIPT_DIR = Path(__file__).parent
REPO_ROOT = SCRIPT_DIR.parent
TRIBUNAL_APPEALS_JSON = REPO_ROOT / "data" / "processed" / "tribunal_appeals.json"

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

# Common date formats seen on tribunal pages, normalised to YYYY-MM-DD.
_DATE_FORMATS = [
    "%d %B %Y",   # 15 July 2026
    "%d %b %Y",   # 15 Jul 2026
    "%d/%m/%Y",   # 15/07/2026
    "%d-%m-%Y",   # 15-07-2026
    "%Y-%m-%d",   # 2026-07-15
]


def load_appeals() -> tuple[dict, dict]:
    """Return (full raw dict incl. metadata keys, records-only dict).

    The raw dict is kept so metadata keys (``_comment``) and key order survive a
    round-trip; the records-only view drops keys starting with ``_``.
    """
    with open(TRIBUNAL_APPEALS_JSON, "r", encoding="utf-8") as f:
        raw = json.load(f)
    records = {k: v for k, v in raw.items() if not k.startswith("_")}
    return raw, records


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


def fetch(url: str) -> str:
    resp = requests.get(
        url, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT
    )
    resp.raise_for_status()
    return resp.text


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


def scrape(merger_ids: list[str] | None, dry_run: bool) -> int:
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
        except requests.RequestException as e:
            print(f"  FAILED to fetch {url}: {e}", file=sys.stderr)
            continue

        scraped = parse_matter_page(html, url)
        if not scraped:
            print(
                f"  Warning: no documents parsed for {mid}; leaving existing "
                f"entry untouched (the page layout may have changed).",
                file=sys.stderr,
            )
            continue

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
        help="Parse and report changes without writing the JSON file.",
    )
    args = parser.parse_args()
    return scrape(args.merger_ids or None, args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
