#!/usr/bin/env python3
"""
Detect duplicate or likely-duplicate events within merger records.

The ACCC website sometimes temporarily publishes documents that later disappear
and are replaced, causing the scraper to accumulate multiple event entries that
represent the same real-world event.  This script reports those cases so they
can be inspected and resolved by hand-editing the processed JSON.

Two categories are reported:

  CERTAIN  – events in the same merger with an identical (date, title) pair.
  LIKELY   – events in the same merger with the same date and a title whose
             normalised form shares ≥ 80 % similarity (catches minor wording
             differences, trailing punctuation, etc.).

Usage
-----
  python scripts/detect_duplicates.py [--input PATH] [--output PATH] [--json]

Options
-------
  --input   Path to mergers JSON (default: data/processed/mergers.json)
  --output  Write a JSON report to this path (default: no file written)
  --json    Print JSON report to stdout instead of human-readable text
"""

import argparse
import json
import re
import sys
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
REPO_ROOT = SCRIPT_DIR.parent
DEFAULT_INPUT = REPO_ROOT / "data" / "processed" / "mergers.json"

SIMILARITY_THRESHOLD = 0.80


def normalise_title(title: str) -> str:
    """Strip leading/trailing whitespace and punctuation for fuzzy comparison."""
    return re.sub(r"[\s\W]+$", "", title.strip()).lower()


def title_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, normalise_title(a), normalise_title(b)).ratio()


def parse_date(raw: str):
    """Return a date-only string (YYYY-MM-DD) or None."""
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).strftime("%Y-%m-%d")
    except ValueError:
        return None


def find_duplicates(merger: dict) -> list[dict]:
    """
    Return a list of duplicate groups for one merger.

    Each group is a dict:
      {
        "kind":    "certain" | "likely",
        "indices": [int, ...],
        "date":    "YYYY-MM-DD",
        "titles":  [str, ...],         # may differ for "likely"
        "events":  [event_dict, ...]
      }
    """
    events = merger.get("events", [])
    grouped: list[dict] = []
    used: set[int] = set()

    # --- pass 1: exact (date, title) matches ---
    from collections import defaultdict
    exact: dict[tuple, list[int]] = defaultdict(list)
    for idx, ev in enumerate(events):
        date = parse_date(ev.get("date", ""))
        title = ev.get("title", "")
        if date and title:
            exact[(date, title)].append(idx)

    for (date, title), indices in exact.items():
        if len(indices) > 1:
            grouped.append({
                "kind": "certain",
                "indices": indices,
                "date": date,
                "titles": [title],
                "events": [events[i] for i in indices],
            })
            used.update(indices)

    # --- pass 2: same-date, similar title (not already marked certain) ---
    remaining = [i for i in range(len(events)) if i not in used]
    checked: set[tuple[int, int]] = set()

    for i in remaining:
        ev_i = events[i]
        date_i = parse_date(ev_i.get("date", ""))
        title_i = ev_i.get("title", "")
        if not date_i or not title_i:
            continue
        group_indices = [i]
        for j in remaining:
            if j == i or (min(i, j), max(i, j)) in checked:
                continue
            ev_j = events[j]
            date_j = parse_date(ev_j.get("date", ""))
            title_j = ev_j.get("title", "")
            if not date_j or not title_j:
                continue
            if date_i == date_j and title_similarity(title_i, title_j) >= SIMILARITY_THRESHOLD:
                group_indices.append(j)
                checked.add((min(i, j), max(i, j)))

        if len(group_indices) > 1:
            # Avoid re-reporting subsets of an already-found group
            key = frozenset(group_indices)
            if not any(frozenset(g["indices"]) == key for g in grouped):
                titles = [events[k].get("title", "") for k in group_indices]
                grouped.append({
                    "kind": "likely",
                    "indices": group_indices,
                    "date": date_i,
                    "titles": titles,
                    "events": [events[k] for k in group_indices],
                })
                used.update(group_indices)

    return grouped


def event_summary(ev: dict) -> dict:
    """Return a compact representation of an event for reporting."""
    return {
        "date": ev.get("date", ""),
        "title": ev.get("title", ""),
        "url": ev.get("url", ""),
        "url_gh": ev.get("url_gh", ""),
        "status": ev.get("status", ""),
    }


def build_report(mergers: list[dict]) -> dict:
    """Build the full duplicate report structure."""
    findings: list[dict] = []
    certain_count = 0
    likely_count = 0

    for merger in mergers:
        groups = find_duplicates(merger)
        if not groups:
            continue
        merger_entry = {
            "merger_id": merger.get("merger_id", ""),
            "merger_name": merger.get("merger_name", ""),
            "duplicate_groups": [],
        }
        for g in groups:
            if g["kind"] == "certain":
                certain_count += 1
            else:
                likely_count += 1
            merger_entry["duplicate_groups"].append({
                "kind": g["kind"],
                "date": g["date"],
                "titles": g["titles"],
                "indices": g["indices"],
                "events": [event_summary(e) for e in g["events"]],
            })
        findings.append(merger_entry)

    return {
        "summary": {
            "mergers_with_duplicates": len(findings),
            "certain_duplicate_groups": certain_count,
            "likely_duplicate_groups": likely_count,
        },
        "findings": findings,
    }


def print_human_report(report: dict) -> None:
    s = report["summary"]
    print("=" * 70)
    print("ACCC Merger Duplicate Event Report")
    print("=" * 70)
    print(
        f"Mergers with duplicates : {s['mergers_with_duplicates']}\n"
        f"Certain duplicate groups: {s['certain_duplicate_groups']}\n"
        f"Likely  duplicate groups: {s['likely_duplicate_groups']}"
    )
    print()

    for entry in report["findings"]:
        print(f"{'─' * 70}")
        print(f"  {entry['merger_id']}  {entry['merger_name']}")
        for g in entry["duplicate_groups"]:
            kind_tag = "[CERTAIN]" if g["kind"] == "certain" else "[LIKELY ]"
            print(f"\n  {kind_tag}  date: {g['date']}")
            for idx, ev in zip(g["indices"], g["events"]):
                print(f"    event[{idx}]")
                print(f"      title  : {ev['title']}")
                if ev["url"]:
                    print(f"      url    : {ev['url']}")
                if ev["url_gh"]:
                    print(f"      url_gh : {ev['url_gh']}")
                if ev["status"]:
                    print(f"      status : {ev['status']}")
        print()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Detect duplicate or likely-duplicate events in merger data."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT,
        help="Path to mergers JSON (default: data/processed/mergers.json)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Write JSON report to this file",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print JSON report to stdout instead of human-readable text",
    )
    args = parser.parse_args()

    if not args.input.exists():
        print(f"ERROR: input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    with args.input.open() as fh:
        raw = json.load(fh)

    # Support both a bare list and the { "mergers": [...] } wrapper
    mergers: list[dict] = raw if isinstance(raw, list) else raw.get("mergers", [])

    report = build_report(mergers)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print_human_report(report)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("w") as fh:
            json.dump(report, fh, indent=2)
        print(f"JSON report written to {args.output}")

    # Exit with a non-zero code if any duplicates were found (useful in CI)
    total = (
        report["summary"]["certain_duplicate_groups"]
        + report["summary"]["likely_duplicate_groups"]
    )
    sys.exit(1 if total else 0)


if __name__ == "__main__":
    main()
