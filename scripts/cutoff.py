"""
Cutoff logic for determining which mergers should be skipped during scraping/extraction.

Mergers are cut off (no longer actively scraped/processed) 3 weeks after:
1. An approved notification (accc_determination = "Approved" with determination_publication_date)
2. A waiver decision (merger_id starts with "WA-" or stage contains "Waiver") - regardless of outcome

This module can be used by:
- extract_mergers.py and scrape/scrape_targets.py (imported as a module)
- the command line (``python -m scripts.cutoff``), to list IDs or paths
"""

import re
from datetime import datetime, timedelta
from scripts.date_utils import parse_iso_datetime
from scripts.constants import merger_status
from scripts.merger_filters import load_mergers_or_empty

# Default cutoff period after determination/waiver decision
CUTOFF_WEEKS = 3

# Floor on the cutoff for a clearance granted on conditions. The parties can
# apply for a public benefit determination within 21 calendar days of it, and
# the ACCC publishes the application on the register a business day or so
# later — which a three-week cutoff would only just miss. (A refusal is never
# cut off at all, so it needs no floor.)
CONDITIONAL_CUTOFF_WEEKS = 5


# A register case number, e.g. MN-01016 or WA-30046.
CASE_NUMBER = re.compile(r'^(?:MN|WA)-\d{4,6}$')


def parse_matter_ids(raw) -> list:
    """Split a list of matter IDs into unique, well-formed case numbers.

    For IDs taken from an ACCC register email (regex-extracted by the
    accc-register-watcher Worker), which name the matters to process even
    past cutoff. They are inbound-email content, so anything not shaped like
    ``MN-12345`` or ``WA-12345`` is dropped. Accepts any mix of commas and
    whitespace as separators and keeps first-seen order.
    """
    ids = []
    for token in re.split(r'[\s,]+', raw or ''):
        token = token.strip().upper()
        if CASE_NUMBER.match(token) and token not in ids:
            ids.append(token)
    return ids


def is_waiver_merger(merger: dict) -> bool:
    """Check if a merger is a waiver application."""
    merger_id = merger.get('merger_id', '')
    stage = merger.get('stage', '')
    return merger_id.startswith('WA-') or merger_status.WAIVER in stage


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
    if determination == merger_status.APPROVED:
        # Imported here: enrichment imports this module.
        from scripts.generate.static_data.enrichment import detect_has_conditions
        if detect_has_conditions(merger):
            cutoff_weeks = max(cutoff_weeks, CONDITIONAL_CUTOFF_WEEKS)
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


def active_merger_ids(mergers: list, cutoff_weeks: int = CUTOFF_WEEKS) -> set:
    """Return the IDs of the ``mergers`` that should still be actively processed."""
    return {
        merger['merger_id']
        for merger in mergers
        if merger.get('merger_id') and not should_skip_merger(merger, cutoff_weeks=cutoff_weeks)
    }


def skipped_merger_ids(mergers: list, cutoff_weeks: int = CUTOFF_WEEKS) -> set:
    """Return the IDs of the ``mergers`` that should be skipped (past cutoff)."""
    return {
        merger['merger_id']
        for merger in mergers
        if merger.get('merger_id') and should_skip_merger(merger, cutoff_weeks=cutoff_weeks)
    }


def skipped_url_paths(mergers: list, cutoff_weeks: int = CUTOFF_WEEKS) -> set:
    """Return the register URL paths of the ``mergers`` that should be skipped.

    The paths are relative (e.g., '/public-registers/.../merger-name').
    """
    from urllib.parse import urlparse

    skipped_paths = set()
    for merger in mergers:
        if should_skip_merger(merger, cutoff_weeks=cutoff_weeks):
            url = merger.get('url', '')
            if url:
                parsed = urlparse(url)
                if parsed.path:
                    skipped_paths.add(parsed.path)
    return skipped_paths


# Path-taking wrappers for the CLI below. A missing or unreadable file counts
# as no mergers (load_mergers_or_empty), so nothing is past cutoff. Code that
# already holds the list should call the functions above instead of having
# the file parsed again.

def get_active_merger_ids(mergers_json_path: str, cutoff_weeks: int = CUTOFF_WEEKS) -> set:
    """:func:`active_merger_ids` of the mergers in ``mergers_json_path``."""
    return active_merger_ids(load_mergers_or_empty(mergers_json_path), cutoff_weeks)


def get_skipped_merger_ids(mergers_json_path: str, cutoff_weeks: int = CUTOFF_WEEKS) -> set:
    """:func:`skipped_merger_ids` of the mergers in ``mergers_json_path``."""
    return skipped_merger_ids(load_mergers_or_empty(mergers_json_path), cutoff_weeks)


def get_skipped_url_paths(mergers_json_path: str, cutoff_weeks: int = CUTOFF_WEEKS) -> set:
    """:func:`skipped_url_paths` of the mergers in ``mergers_json_path``."""
    return skipped_url_paths(load_mergers_or_empty(mergers_json_path), cutoff_weeks)


def main():
    """
    Command-line interface for the cutoff module.

    Usage:
        python -m scripts.cutoff [--active|--skipped|--paths] [mergers.json path]

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
