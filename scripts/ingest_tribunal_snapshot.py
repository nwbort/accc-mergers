#!/usr/bin/env python3
"""Ingest browser-bookmarklet snapshots into tribunal_appeals.json.

Background
----------
``scrape_tribunal.py`` fetches tribunal matter pages itself, but the
tribunal site's Cloudflare bot management JS-challenges anything that isn't
a real browser (see that module's docstring) — including, on a bad day, curl
from a residential IP. ``scripts/bookmarklet/`` provides an alternative: a
bookmarklet you click while actually looking at the matter page in your
browser (so the challenge is already solved), which downloads a JSON
snapshot of that page's document table(s) using the exact same parsing
rules as ``scrape_tribunal.py``'s ``parse_matter_page()`` (ported to JS).

This script is the other half: it takes one or more of those downloaded
snapshot files, matches each to the ``tribunal_appeals.json`` entry with the
same ``tribunal_url``, and folds the documents in — mirroring/reusing
``scrape_tribunal.py``'s own ``merge_documents()`` (carries over any
existing ``url_gh`` local-mirror path) and ``download_document()`` (mirrors
each linked file into ``data/raw/matters/{merger_id}/``, same as a normal
scrape). Individual document files aren't behind the same Cloudflare
challenge as the matter pages, so those downloads work the same as always.

Usage
-----
  python scripts/ingest_tribunal_snapshot.py ~/Downloads/tribunal-act-1-of-2026.json
  python scripts/ingest_tribunal_snapshot.py snapshot1.json snapshot2.json
  python scripts/ingest_tribunal_snapshot.py --dry-run snapshot.json
  python scripts/ingest_tribunal_snapshot.py --no-download snapshot.json

  git add data/processed/tribunal_appeals.json data/raw/matters
  git commit -m "Update scraped tribunal data" && git push

See scripts/bookmarklet/README.md for how to install and use the
bookmarklet itself.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import scrape_tribunal

# Accessed as scrape_tribunal.TRIBUNAL_APPEALS_JSON (module-qualified, not
# imported as a plain name) so a test's monkeypatch of that one attribute is
# also what this module's write-back step sees — there'd otherwise be two
# separate name bindings to keep in sync.
from scrape_tribunal import download_document, load_appeals, merge_documents


def find_merger_id(records: dict, tribunal_url: str) -> str | None:
    """Return the merger_id whose record's tribunal_url matches, or None."""
    normalised = tribunal_url.rstrip("/")
    for merger_id, record in records.items():
        url = (record.get("tribunal_url") or "").rstrip("/")
        if url and url == normalised:
            return merger_id
    return None


def ingest_snapshot(
    path: Path, records: dict, dry_run: bool, download: bool = True
) -> tuple[str | None, bool]:
    """Fold one snapshot file into ``records`` in place.

    Returns (merger_id, changed). merger_id is None if the snapshot couldn't
    be matched to a tribunal_appeals.json entry, in which case nothing is
    changed.
    """
    try:
        snapshot = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        print(f"  Skipping {path}: {e}", file=sys.stderr)
        return None, False

    tribunal_url = snapshot.get("tribunal_url")
    documents = snapshot.get("documents")
    if not tribunal_url or not documents:
        print(
            f"  Skipping {path}: missing tribunal_url or documents "
            "(is this a bookmarklet snapshot?)",
            file=sys.stderr,
        )
        return None, False

    merger_id = find_merger_id(records, tribunal_url)
    if merger_id is None:
        known = ", ".join(sorted(
            rec["tribunal_url"] for rec in records.values() if rec.get("tribunal_url")
        )) or "(none)"
        print(
            f"  Skipping {path}: no tribunal_appeals.json entry has "
            f"tribunal_url={tribunal_url!r}. Known tribunal_urls: {known}",
            file=sys.stderr,
        )
        return None, False

    record = records[merger_id]
    print(f"Ingesting {path.name} -> {merger_id} ({tribunal_url})")

    if download and not dry_run:
        for doc in documents:
            if doc.get("url"):
                url_gh = download_document(merger_id, doc["url"])
                if url_gh:
                    doc["url_gh"] = url_gh

    merged = merge_documents(record.get("documents"), documents)
    changed = merged != record.get("documents")
    if changed and not dry_run:
        record["documents"] = merged

    sections = sorted({d["section"] for d in merged if d.get("section")})
    summary = f"  Parsed {len(merged)} document(s)"
    if sections:
        summary += f" across sections: {', '.join(sections)}"
    print(summary)

    return merger_id, changed


def ingest(paths: list[str], dry_run: bool, download: bool = True) -> int:
    raw, records = load_appeals()

    changed = 0
    missing = 0
    for raw_path in paths:
        path = Path(raw_path)
        if not path.exists():
            print(f"Skipping {path}: file not found", file=sys.stderr)
            missing += 1
            continue
        merger_id, was_changed = ingest_snapshot(path, records, dry_run, download)
        if merger_id is None:
            missing += 1
        elif was_changed:
            changed += 1

    if dry_run:
        print(f"\nDry run: {changed} entr(y/ies) would change; nothing written.")
    elif changed:
        with open(scrape_tribunal.TRIBUNAL_APPEALS_JSON, "w", encoding="utf-8") as f:
            json.dump(raw, f, indent=2, ensure_ascii=False)
            f.write("\n")
        print(f"\nUpdated {changed} entr(y/ies) in {scrape_tribunal.TRIBUNAL_APPEALS_JSON}")
    else:
        print("\nNo changes.")

    return 2 if missing else 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "snapshots", nargs="+", help="Path(s) to bookmarklet-downloaded JSON snapshot(s)."
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
    return ingest(args.snapshots, args.dry_run, download=not args.no_download)


if __name__ == "__main__":
    raise SystemExit(main())
