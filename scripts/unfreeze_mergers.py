#!/usr/bin/env python3
"""Remove entries from data/frozen_events_mergers.json.

frozen_events_mergers.json lets the scraper (extract_mergers.py) preserve
existing event data instead of overwriting it from the ACCC page — either for
an entire merger (the whole key) or for specific event titles
(``freeze_events: [...]``). This script is the inverse: it unfreezes a
merger, either completely (deleting its key) or by removing individual event
titles from its ``freeze_events`` list.

Usage:
    # Remove the whole entry for a merger (unfreeze everything).
    python -m scripts.unfreeze_mergers MN-65005

    # Remove only specific frozen event titles, leaving the rest frozen.
    python -m scripts.unfreeze_mergers MN-65026 \\
        --event "McCarroll's - Kinghorn Motors and Country Motors - Questionnaire"

    # Preview the change without writing the file.
    python -m scripts.unfreeze_mergers MN-65005 --dry-run

    # Show what's currently frozen.
    python -m scripts.unfreeze_mergers --list
"""

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
FROZEN_EVENTS_MERGERS_PATH = REPO_ROOT / 'data' / 'frozen_events_mergers.json'


def _load(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def _save(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)


def list_frozen(data):
    entries = {k: v for k, v in data.items() if not k.startswith('_')}
    if not entries:
        print("No mergers are currently frozen.")
        return
    for merger_id, entry in sorted(entries.items()):
        if not isinstance(entry, dict) or not entry or entry.get('freeze_events') is True:
            print(f"{merger_id}: ALL events frozen")
            continue
        freeze = entry.get('freeze_events')
        if isinstance(freeze, list) and freeze:
            print(f"{merger_id}: {len(freeze)} event(s) frozen")
            for title in freeze:
                print(f"    - {title}")
        else:
            print(f"{merger_id}: field overrides only (no frozen events)")


def unfreeze(data, merger_id, event_titles, dry_run=False):
    """Remove ``merger_id`` entirely, or just the given ``event_titles``.

    Returns the (possibly mutated) data dict. Raises SystemExit(1) on
    unrecoverable errors (unknown merger, event not frozen, etc.).
    """
    if merger_id not in data:
        print(f"Error: {merger_id} is not in {FROZEN_EVENTS_MERGERS_PATH.name}", file=sys.stderr)
        raise SystemExit(1)

    entry = data[merger_id]

    if not event_titles:
        # Full unfreeze: drop the entire key.
        del data[merger_id]
        print(f"{'Would remove' if dry_run else 'Removed'} entire entry for {merger_id}.")
        return data

    if not isinstance(entry, dict) or not entry or entry.get('freeze_events') is True:
        print(
            f"Error: {merger_id} freezes ALL events (not a specific list), so individual "
            "events can't be removed. Run without --event to unfreeze it entirely.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    freeze = entry.get('freeze_events')
    if not isinstance(freeze, list):
        print(f"Error: {merger_id} has no freeze_events list to remove events from.", file=sys.stderr)
        raise SystemExit(1)

    to_remove = set(event_titles)
    removed = [t for t in freeze if t in to_remove]
    not_found = sorted(to_remove - set(freeze))

    if not removed:
        print(f"Error: none of the given event(s) are frozen for {merger_id}.", file=sys.stderr)
        raise SystemExit(1)

    if not_found:
        print(
            f"Warning: {', '.join(not_found)} not currently frozen for {merger_id}; skipping.",
            file=sys.stderr,
        )

    remaining = [t for t in freeze if t not in to_remove]

    for title in removed:
        print(f"{'Would unfreeze' if dry_run else 'Unfroze'} event for {merger_id}: {title}")

    if remaining:
        entry['freeze_events'] = remaining
    else:
        entry.pop('freeze_events', None)
        # Nothing left but a comment (or nothing at all) -> drop the entry.
        if not any(k for k in entry if not k.startswith('_')):
            del data[merger_id]
            print(f"{'Would remove' if dry_run else 'Removed'} now-empty entry for {merger_id}.")

    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('merger_id', nargs='?', help="Merger ID to unfreeze, e.g. MN-65026")
    parser.add_argument(
        '--event', action='append', default=[], metavar='TITLE',
        help="Event title to unfreeze (repeatable). Omit to unfreeze the entire merger.",
    )
    parser.add_argument('--dry-run', action='store_true', help="Show what would change without writing the file.")
    parser.add_argument('--list', action='store_true', help="List currently frozen mergers/events and exit.")
    parser.add_argument('--file', default=str(FROZEN_EVENTS_MERGERS_PATH), help=argparse.SUPPRESS)
    args = parser.parse_args()

    path = Path(args.file)
    data = _load(path)

    if args.list:
        list_frozen(data)
        return

    if not args.merger_id:
        parser.error("merger_id is required unless --list is given")

    data = unfreeze(data, args.merger_id, args.event, dry_run=args.dry_run)

    if not args.dry_run:
        _save(path, data)
        print(f"Saved {path}")


if __name__ == '__main__':
    main()
