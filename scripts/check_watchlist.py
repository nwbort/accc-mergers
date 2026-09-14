"""CI check: has a personally-watched merger changed this pipeline run?

Lets the repo owner track a handful of matters they have a personal stake in
(without that list ever being visible in the public repo or its public
Actions logs) and get a push notification via ntfy the moment one of them
changes.

The watched merger IDs come from the ``WATCHLIST_MATTER_IDS`` environment
variable — a GitHub Actions secret in CI, comma/whitespace separated (e.g.
``MN-40039, MN-45024``) — never a tracked file. A record counts as changed if
its dict in ``mergers.json`` differs at all from the same matter's dict
before this run (new event, status flip, date change, anything).

This module is deliberately quiet: it never prints which IDs are configured
or which ones matched, on stdout or otherwise, because the only consumer of
that information should be the pipeline step's GITHUB_OUTPUT capture (never
the visible log or step summary — both public). The single content-bearing
line it *does* print, one per changed matter, is meant to be captured
straight into a shell variable by ``$(...)`` and forwarded to a private ntfy
topic; it must never be echoed back into the workflow log. See
docs/notifications.md for the full design rationale.

Usage:
    python -m scripts.check_watchlist --before /path/to/mergers-before.json \
        [--after data/processed/mergers.json]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

from scripts.merger_filters import load_mergers

SITE_URL = "https://mergers.fyi"


def parse_watched_ids(raw: str) -> list[str]:
    """Split a comma/whitespace-separated env var into unique uppercase IDs."""
    return sorted({token.upper() for token in re.split(r"[,\s]+", raw.strip()) if token})


def _index_by_id(mergers: list[dict]) -> dict[str, dict]:
    return {
        merger["merger_id"].upper(): merger
        for merger in mergers
        if merger.get("merger_id")
    }


def changed_watched_mergers(
    watched_ids: list[str], before: list[dict], after: list[dict]
) -> list[dict]:
    """Return the ``after`` records among ``watched_ids`` that changed at all.

    A watched ID missing from ``after`` (e.g. a matter number that was never
    real, or was pruned) is silently skipped rather than reported as changed.
    """
    before_by_id = _index_by_id(before)
    after_by_id = _index_by_id(after)
    changed = []
    for matter_id in watched_ids:
        record = after_by_id.get(matter_id)
        if record is not None and record != before_by_id.get(matter_id):
            changed.append(record)
    return changed


def format_notification(record: dict) -> str:
    matter_id = record["merger_id"]
    name = record.get("merger_name") or matter_id
    return f"{name} ({matter_id}) — {SITE_URL}/mergers/{matter_id}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--before", required=True, help="Path to a prior mergers.json snapshot"
    )
    parser.add_argument(
        "--after",
        default=None,
        help="Path to the current mergers.json (default: data/processed/mergers.json)",
    )
    args = parser.parse_args(argv)

    watched_ids = parse_watched_ids(os.environ.get("WATCHLIST_MATTER_IDS", ""))
    if not watched_ids:
        return 0

    try:
        before = load_mergers(args.before)
    except (OSError, ValueError, json.JSONDecodeError):
        # No usable prior snapshot (first-ever run, or the before-copy step
        # was skipped) — treat every watched matter present now as new.
        before = []
    after = load_mergers(args.after) if args.after else load_mergers()

    changed = changed_watched_mergers(watched_ids, before, after)
    if changed:
        print("\n".join(format_notification(record) for record in changed))
    return 0


if __name__ == "__main__":
    sys.exit(main())
