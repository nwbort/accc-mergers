"""
Cutoff logic for determining which mergers should be skipped during scraping/extraction.

Mergers are cut off (no longer actively scraped/processed) 3 weeks after:
1. An approved notification (accc_determination = "Approved" with determination_publication_date)
2. A waiver decision (merger_id starts with "WA-" or stage contains "Waiver") - regardless of outcome

This module can be used by:
- extract_mergers.py (imported as a module)
- scrape.sh (called as a standalone script to output merger IDs to skip)
"""

import json
import os
import sys
from datetime import datetime, timedelta
from date_utils import parse_iso_datetime

# Default cutoff period after determination/waiver decision
CUTOFF_WEEKS = 3


def is_waiver_merger(merger: dict) -> bool:
    """Check if a merger is a waiver application."""
    merger_id = merger.get('merger_id', '')
    stage = merger.get('stage', '')
    return merger_id.startswith('WA-') or 'Waiver' in stage


def get_cutoff_date(merger: dict, cutoff_weeks: int = CUTOFF_WEEKS) -> datetime:
    """
    Get the cutoff date for a merger (date after which it should no longer be scraped).

    Returns None if the merger should still be actively processed.
    Returns a datetime if the merger has a cutoff date.
    """
    determination_date = parse_iso_datetime(merger.get('determination_publication_date'))

    if determination_date is None:
        # No determination yet, keep processing
        return None

    # For waivers: cut off after any determination (approved or denied)
    if is_waiver_merger(merger):
        return determination_date + timedelta(weeks=cutoff_weeks)

    # For regular notifications: only cut off if approved
    determination = merger.get('accc_determination', '')
    if determination == 'Approved':
        return determination_date + timedelta(weeks=cutoff_weeks)

    # Not approved or no determination - keep processing
    return None


def should_skip_merger(merger: dict, reference_date: datetime = None, cutoff_weeks: int = CUTOFF_WEEKS) -> bool:
    """
    Determine if a merger should be skipped during scraping/extraction.

    Args:
        merger: Merger data dictionary
        reference_date: Date to compare against (defaults to now)
        cutoff_weeks: Number of weeks after determination to cut off (default: 3)

    Returns:
        True if the merger should be skipped, False if it should be processed
    """
    if reference_date is None:
        reference_date = datetime.now(tz=None)

    cutoff_date = get_cutoff_date(merger, cutoff_weeks)

    if cutoff_date is None:
        return False

    # Make reference_date timezone-naive for comparison if cutoff_date is timezone-aware
    if cutoff_date.tzinfo is not None and reference_date.tzinfo is None:
        cutoff_date = cutoff_date.replace(tzinfo=None)
    elif cutoff_date.tzinfo is None and reference_date.tzinfo is not None:
        reference_date = reference_date.replace(tzinfo=None)

    return reference_date > cutoff_date


def get_active_merger_ids(mergers_json_path: str, cutoff_weeks: int = CUTOFF_WEEKS) -> set:
    """
    Get the set of merger IDs that should still be actively processed.

    Args:
        mergers_json_path: Path to the mergers.json file
        cutoff_weeks: Number of weeks after determination to cut off (default: 3)

    Returns:
        Set of merger IDs that should be processed
    """
    if not os.path.exists(mergers_json_path):
        return set()

    try:
        with open(mergers_json_path, 'r', encoding='utf-8') as f:
            mergers = json.load(f)
    except (json.JSONDecodeError, IOError):
        return set()

    active_ids = set()
    for merger in mergers:
        merger_id = merger.get('merger_id')
        if merger_id and not should_skip_merger(merger, cutoff_weeks=cutoff_weeks):
            active_ids.add(merger_id)

    return active_ids


def get_skipped_merger_ids(mergers_json_path: str, cutoff_weeks: int = CUTOFF_WEEKS) -> set:
    """
    Get the set of merger IDs that should be skipped (past cutoff).

    Args:
        mergers_json_path: Path to the mergers.json file
        cutoff_weeks: Number of weeks after determination to cut off (default: 3)

    Returns:
        Set of merger IDs that should be skipped
    """
    if not os.path.exists(mergers_json_path):
        return set()

    try:
        with open(mergers_json_path, 'r', encoding='utf-8') as f:
            mergers = json.load(f)
    except (json.JSONDecodeError, IOError):
        return set()

    skipped_ids = set()
    for merger in mergers:
        merger_id = merger.get('merger_id')
        if merger_id and should_skip_merger(merger, cutoff_weeks=cutoff_weeks):
            skipped_ids.add(merger_id)

    return skipped_ids


def get_skipped_url_paths(mergers_json_path: str, cutoff_weeks: int = CUTOFF_WEEKS) -> set:
    """
    Get the set of URL paths for mergers that should be skipped.

    The paths are relative (e.g., '/public-registers/.../merger-name').

    Args:
        mergers_json_path: Path to the mergers.json file
        cutoff_weeks: Number of weeks after determination to cut off (default: 3)

    Returns:
        Set of URL paths for mergers that should be skipped
    """
    from urllib.parse import urlparse

    if not os.path.exists(mergers_json_path):
        return set()

    try:
        with open(mergers_json_path, 'r', encoding='utf-8') as f:
            mergers = json.load(f)
    except (json.JSONDecodeError, IOError):
        return set()

    skipped_paths = set()
    for merger in mergers:
        if should_skip_merger(merger, cutoff_weeks=cutoff_weeks):
            url = merger.get('url', '')
            if url:
                # Extract path from full URL
                parsed = urlparse(url)
                if parsed.path:
                    skipped_paths.add(parsed.path)

    return skipped_paths


def main():
    """
    Command-line interface for the cutoff module.

    Usage:
        python cutoff.py [--active|--skipped|--paths] [mergers.json path]

    Options:
        --active   Output merger IDs that should still be processed (default)
        --skipped  Output merger IDs that should be skipped
        --paths    Output URL paths for mergers that should be skipped

    Output is one item per line.
    """
    import argparse

    parser = argparse.ArgumentParser(
        description='Determine which mergers should be processed based on cutoff logic.'
    )
    parser.add_argument(
        'mergers_json',
        nargs='?',
        default='data/processed/mergers.json',
        help='Path to mergers.json file (default: data/processed/mergers.json)'
    )
    parser.add_argument(
        '--active',
        action='store_true',
        help='Output merger IDs that should still be processed (default)'
    )
    parser.add_argument(
        '--skipped',
        action='store_true',
        help='Output merger IDs that should be skipped'
    )
    parser.add_argument(
        '--paths',
        action='store_true',
        help='Output URL paths for mergers that should be skipped (for use with scraper)'
    )
    parser.add_argument(
        '--cutoff-weeks',
        type=int,
        default=CUTOFF_WEEKS,
        help=f'Number of weeks after determination to cut off (default: {CUTOFF_WEEKS})'
    )

    args = parser.parse_args()

    if args.paths:
        paths = get_skipped_url_paths(args.mergers_json, cutoff_weeks=args.cutoff_weeks)
        for path in sorted(paths):
            print(path)
    elif args.skipped:
        ids = get_skipped_merger_ids(args.mergers_json, cutoff_weeks=args.cutoff_weeks)
        for merger_id in sorted(ids):
            print(merger_id)
    else:
        ids = get_active_merger_ids(args.mergers_json, cutoff_weeks=args.cutoff_weeks)
        for merger_id in sorted(ids):
            print(merger_id)


if __name__ == '__main__':
    main()
