#!/usr/bin/env python3
"""Detect mergers with no notification date on the ACCC register page and
suggest freezing today's date as the default in known_notification_dates.json.

Background
----------
The ACCC page occasionally never publishes a notification date (see
MN-50030). ``extract_mergers.py`` loads confirmed dates for these mergers from
``data/known_notification_dates.json`` (see ``KNOWN_NOTIFICATION_DATES``) so
the pipeline stops treating them as missing on every scrape.

This script finds mergers with no notification date that aren't already in
that file, defaults each to today's date, and can write both the JSON update
and a PR body so a human can review/correct the guessed date before it lands.

Usage
-----
  python scripts/fix_missing_notification_dates.py [--summary]
  python scripts/fix_missing_notification_dates.py --apply-suggestions --pr-markdown pr_body.md

Exit code is 1 if new candidates are found (useful in CI), 0 otherwise.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
REPO_ROOT = SCRIPT_DIR.parent
DEFAULT_MERGERS = REPO_ROOT / "data" / "processed" / "mergers.json"
DEFAULT_KNOWN_DATES = REPO_ROOT / "data" / "known_notification_dates.json"

_REPO = "nwbort/accc-mergers"
_MERGERS_FYI_BASE = "https://mergers.fyi/mergers"
_KNOWN_DATES_PATH = "data/known_notification_dates.json"


def find_candidates(mergers: list[dict], known_dates: dict, today_iso: str) -> list[dict]:
    """Return one candidate per merger with no notification date that isn't
    already recorded in known_dates."""
    candidates = []
    for merger in mergers:
        merger_id = merger.get("merger_id")
        if not merger_id or merger_id in known_dates:
            continue
        if merger.get("effective_notification_datetime"):
            continue
        candidates.append({
            "merger_id": merger_id,
            "merger_name": merger.get("merger_name", ""),
            "url": merger.get("url", ""),
            "date": today_iso,
        })
    return candidates


def apply_suggestions(known_dates_path: Path, candidates: list[dict]) -> int:
    """Add each candidate's default date to known_notification_dates.json in-place.

    Returns the number of entries added.
    """
    if known_dates_path.exists():
        with known_dates_path.open() as fh:
            data = json.load(fh)
    else:
        data = {}

    for c in candidates:
        data[c["merger_id"]] = {
            "date": c["date"],
            "note": (
                f"{c['merger_name']}: notification date missing from ACCC page "
                f"as of {c['date'][:10]}; confirm and correct if wrong."
            ),
        }

    known_dates_path.parent.mkdir(parents=True, exist_ok=True)
    with known_dates_path.open("w") as fh:
        json.dump(data, fh, indent=2, sort_keys=True)
        fh.write("\n")
    return len(candidates)


def print_summary(candidates: list[dict]) -> None:
    if not candidates:
        print("No mergers with missing notification dates found.")
        return
    print(f"Found {len(candidates)} merger(s) with no notification date:")
    print()
    for c in candidates:
        print(f"  {c['merger_name']} ({c['merger_id']}) -> defaulting to {c['date']}")


def build_pr_body(candidates: list[dict], date: str) -> str:
    """Build a markdown PR body recommending the default notification dates."""
    lines = [
        f"Found **{len(candidates)}** merger(s) on **{date}** with no notification "
        f"date on the ACCC register page. This PR freezes **{date}** (today) as the "
        f"default notification date for each, recorded in "
        f"[`{_KNOWN_DATES_PATH}`](https://github.com/{_REPO}/blob/main/{_KNOWN_DATES_PATH}).",
        "",
        "**Check each merger's actual notification date** (the questionnaire or "
        "another early attachment often has it even when the page field is empty) "
        "**and correct the date below if today isn't right**, then merge.",
        "",
        "---",
        "",
    ]
    for c in candidates:
        lines.append(f"### [{c['merger_name']}]({c['url']})  ·  `{c['merger_id']}`")
        lines.append("")
        lines.append(f"Defaulted notification date: **{c['date']}**")
        lines.append("")
        lines.append(f"[View on mergers.fyi]({_MERGERS_FYI_BASE}/{c['merger_id']})")
        lines.append("")
    lines.extend([
        "---",
        "",
        f"*Generated automatically by the [Fix Missing Notification Dates]"
        f"(https://github.com/{_REPO}/actions/workflows/fix-missing-notification-dates.yml) workflow.*",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mergers", type=Path, default=DEFAULT_MERGERS)
    parser.add_argument("--known-dates", type=Path, default=DEFAULT_KNOWN_DATES)
    parser.add_argument(
        "--summary", action="store_true", help="Print a human-readable summary"
    )
    parser.add_argument(
        "--apply-suggestions", action="store_true", dest="apply_suggestions",
        help="Add default dates to known_notification_dates.json in-place",
    )
    parser.add_argument(
        "--pr-markdown", type=Path, default=None, dest="pr_markdown",
        help="Write a PR body (markdown) describing the candidates to this path",
    )
    args = parser.parse_args()

    if not args.mergers.exists():
        print(f"ERROR: mergers file not found: {args.mergers}", file=sys.stderr)
        return 2

    with args.mergers.open() as fh:
        mergers = json.load(fh)

    known_dates = {}
    if args.known_dates.exists():
        with args.known_dates.open() as fh:
            known_dates = json.load(fh)

    today_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT12:00:00Z")
    candidates = find_candidates(mergers, known_dates, today_iso)

    if args.summary or not (args.apply_suggestions or args.pr_markdown):
        print_summary(candidates)

    if args.pr_markdown and candidates:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        args.pr_markdown.parent.mkdir(parents=True, exist_ok=True)
        with args.pr_markdown.open("w") as fh:
            fh.write(build_pr_body(candidates, today))

    if args.apply_suggestions and candidates:
        added = apply_suggestions(args.known_dates, candidates)
        print(f"Added {added} default notification date(s) to {args.known_dates}", file=sys.stderr)

    return 1 if candidates else 0


if __name__ == "__main__":
    sys.exit(main())
