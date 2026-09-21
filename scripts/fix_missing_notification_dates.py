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

Carrying a suggestion forward
-----------------------------
The detector runs on a fix branch rebuilt from ``main`` on every pipeline run,
so nothing it wrote last run survives into this one. Left to itself it would
therefore re-date every still-unreviewed candidate to *today*, every run — the
guess drifting further from the date the merger was actually first seen without
one, which is the whole basis for guessing "today" in the first place.

``--previous-known-dates`` points at the copy of the file this detector wrote on
its last run (recovered from the fix branch by the ``detection-pr`` action).
Any candidate already recorded there keeps that entry verbatim, so:

* the first guess stays pinned to the day the merger turned up without a date; and
* a date a human corrected on the branch, but hasn't merged yet, is preserved
  rather than overwritten on the next run.

Usage
-----
  python -m scripts.fix_missing_notification_dates [--summary]
  python -m scripts.fix_missing_notification_dates --apply-suggestions --pr-markdown pr_body.md

Exit code is 1 if new candidates are found (useful in CI), 0 otherwise.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from scripts.constants.site import REPO as _REPO, mergers_fyi_url
from scripts.merger_filters import load_mergers

SCRIPT_DIR = Path(__file__).parent
REPO_ROOT = SCRIPT_DIR.parent
DEFAULT_MERGERS = REPO_ROOT / "data" / "processed" / "mergers.json"
DEFAULT_KNOWN_DATES = REPO_ROOT / "data" / "known_notification_dates.json"

_KNOWN_DATES_PATH = "data/known_notification_dates.json"


def load_previous_suggestions(path: Path | None) -> dict:
    """Read the copy of known_notification_dates.json this detector wrote on its
    last run, as recovered from the fix branch.

    Best-effort by design: the file is absent on the detector's first run and
    whenever the fix branch has been merged or deleted, and a truncated or
    unparseable one means only that the carry-forward below falls back to
    today's date. Neither is worth failing the run over.
    """
    if not path or not path.is_file():
        return {}
    try:
        text = path.read_text().strip()
        return json.loads(text) if text else {}
    except (OSError, ValueError) as exc:
        print(f"WARNING: ignoring unreadable previous suggestions {path}: {exc}",
              file=sys.stderr)
        return {}


def _carried_entry(previous: dict, merger_id: str) -> dict | None:
    """The entry this detector already suggested for merger_id, if there is a
    usable one. Anything without a date is treated as absent, so a malformed
    hand-edit on the branch falls back to a fresh suggestion instead of
    propagating."""
    entry = previous.get(merger_id)
    if isinstance(entry, dict) and entry.get("date"):
        return entry
    return None


def find_candidates(
    mergers: list[dict],
    known_dates: dict,
    today_iso: str,
    previous: dict | None = None,
) -> list[dict]:
    """Return one candidate per merger with no notification date that isn't
    already recorded in known_dates.

    ``previous`` is this detector's own output from its last run (see the module
    docstring). A candidate already recorded there carries that entry forward
    instead of being re-dated to ``today_iso``.
    """
    previous = previous or {}
    candidates = []
    for merger in mergers:
        merger_id = merger.get("merger_id")
        if not merger_id or merger_id in known_dates:
            continue
        if merger.get("effective_notification_datetime"):
            continue
        carried = _carried_entry(previous, merger_id)
        candidates.append({
            "merger_id": merger_id,
            "merger_name": merger.get("merger_name", ""),
            "url": merger.get("url", ""),
            "date": carried["date"] if carried else today_iso,
            # The whole previous entry, so a note a human rewrote on the branch
            # survives alongside the date. None for a first-time candidate.
            "carried_entry": carried,
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
        # A carried-over entry is written back exactly as it was, so neither the
        # first-seen date nor a note a human corrected on the branch is reset by
        # a later run. Only a first-time candidate gets a freshly-built entry.
        carried = c.get("carried_entry")
        data[c["merger_id"]] = carried if carried else {
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
        if c.get("carried_entry"):
            suffix = " (carried over from an earlier run, not re-dated to today)"
        else:
            suffix = ""
        print(f"  {c['merger_name']} ({c['merger_id']}) -> defaulting to {c['date']}{suffix}")


def build_pr_body(candidates: list[dict], date: str) -> str:
    """Build a markdown PR body recommending the default notification dates."""
    carried = [c for c in candidates if c.get("carried_entry")]
    lines = [
        f"Found **{len(candidates)}** merger(s) as of **{date}** with no "
        f"notification date on the ACCC register page. This PR records a default "
        f"notification date for each in "
        f"[`{_KNOWN_DATES_PATH}`](https://github.com/{_REPO}/blob/main/{_KNOWN_DATES_PATH}).",
        "",
        "**Check each merger's actual notification date** (the questionnaire or "
        "another early attachment often has it even when the page field is empty) "
        "**and correct the date below if it isn't right**, then merge.",
        "",
    ]
    if carried:
        # Worth saying explicitly: the dates below are not all "today", and an
        # edit made here is not about to be overwritten by the next run.
        if len(carried) == 1:
            carried_line = (
                "1 of these was first suggested on an earlier run and keeps the "
                "date it was given then, rather than being re-dated to today."
            )
        else:
            carried_line = (
                f"{len(carried)} of these were first suggested on earlier runs and "
                "keep the dates they were given then, rather than being re-dated "
                "to today."
            )
        lines.extend([
            carried_line
            + " A correction made on this branch is preserved the same way, so you "
              "can fix a date here and come back to it.",
            "",
        ])
    lines.extend(["---", ""])
    for c in candidates:
        lines.append(f"### [{c['merger_name']}]({c['url']})  ·  `{c['merger_id']}`")
        lines.append("")
        suffix = " *(carried over from an earlier run)*" if c.get("carried_entry") else ""
        lines.append(f"Defaulted notification date: **{c['date']}**{suffix}")
        lines.append("")
        lines.append(f"[View on mergers.fyi]({mergers_fyi_url(c['merger_id'])})")
        lines.append("")
    lines.extend([
        "---",
        "",
        f"*Generated automatically by the missing-notification-date step of the "
        f"[merger pipeline](https://github.com/{_REPO}/actions/workflows/pipeline.yml).*",
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
    parser.add_argument(
        "--previous-known-dates", type=Path, default=None,
        dest="previous_known_dates",
        help=(
            "This detector's own output from its last run, recovered from the "
            "fix branch. Candidates already recorded there keep that entry "
            "instead of being re-dated to today. Missing or unreadable is fine "
            "(see the module docstring)."
        ),
    )
    args = parser.parse_args()

    if not args.mergers.exists():
        print(f"ERROR: mergers file not found: {args.mergers}", file=sys.stderr)
        return 2

    mergers = load_mergers(args.mergers)

    known_dates = {}
    if args.known_dates.exists():
        with args.known_dates.open() as fh:
            known_dates = json.load(fh)

    previous = load_previous_suggestions(args.previous_known_dates)

    today_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT12:00:00Z")
    candidates = find_candidates(mergers, known_dates, today_iso, previous)

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
