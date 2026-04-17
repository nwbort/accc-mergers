#!/usr/bin/env python3
"""
Generate a weekly digest of ACCC merger activity.

This script creates a summary showing:
- New deals notified (but not yet determined) in the last week
- Deals cleared in the last week
- Deals declined/not approved in the last week
- Ongoing phase 1 deals
- Ongoing phase 2 deals

To account for the discrepancy between when a decision is "made" and when it
appears on the ACCC's acquisitions register (a decision dated Friday often
doesn't appear on the site until the following Monday afternoon, after the
Sunday-morning digest has already been generated), the three time-scoped
buckets are built from a two-week window and then deduplicated against the
previous week's digest. Anything that was already surfaced last week is
removed; anything newly-visible in the last two weeks is included.

The "previous week's digest" is loaded from a dated archive snapshot written
by the last scheduled run, falling back to the current digest.json only when
the archive is unavailable. That isolation means a mid-week manual re-run of
this script won't spoil the dedup baseline for next week's scheduled run.

Outputs:
- digest.json in the frontend public data directory (the live digest)
- data/digest-archive/digest-<YYYY-MM-DD>.json (dated snapshot, keyed by the
  Monday of the period it covers)
"""

import json
from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import Dict, List, Any, Optional, Set
from constants import merger_status
from date_utils import parse_iso_datetime
from merger_filters import filter_active, load_mergers


OUTPUT_PATH = (
    Path(__file__).parent.parent
    / 'merger-tracker' / 'frontend' / 'public' / 'data' / 'digest.json'
)

# Dated snapshots of each week's digest. Reading last week's snapshot from
# here (rather than the current digest.json) means that an ad-hoc mid-week
# re-run — for example, to pick up a decision that only appeared on the
# ACCC register after Sunday's scheduled run — won't corrupt the dedup
# baseline for the next scheduled run.
DIGEST_ARCHIVE_DIR = Path(__file__).parent.parent / 'data' / 'digest-archive'

# How far back to look for items that should appear in this digest.
# Two weeks means: the prior Mon-Sun week plus the current Mon-Sun week.
# Items from the prior week that already appeared in last week's digest are
# deduplicated out.
LOOKBACK_WEEKS = 2


def get_last_week_range() -> tuple[datetime, datetime]:
    """
    Get the Monday-Sunday date range for the most recent completed week in Australian time.

    Returns:
        tuple: (period_start, period_end) where:
            - period_start is Monday 00:00:00 AEST/AEDT
            - period_end is Sunday 23:59:59.999999 AEST/AEDT
    """
    sydney_tz = ZoneInfo('Australia/Sydney')
    now_sydney = datetime.now(sydney_tz)

    # Calculate days since last Monday
    # Monday = 0, Sunday = 6
    days_since_monday = now_sydney.weekday()

    # If it's currently Sunday (weekday = 6) and after midnight,
    # we want the current week (this Monday to today)
    # Otherwise, we want the previous complete week
    if now_sydney.weekday() == 6:  # Sunday
        # Current week: this Monday to this Sunday
        days_to_subtract = days_since_monday
    else:
        # Previous complete week: last Monday to last Sunday
        days_to_subtract = days_since_monday + 7

    # Calculate Monday at 00:00:00
    monday = (now_sydney - timedelta(days=days_to_subtract)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    # Calculate Sunday at 23:59:59.999999
    sunday = monday + timedelta(days=6, hours=23, minutes=59, seconds=59, microseconds=999999)

    return monday, sunday


def is_in_week_range(date_str: str, period_start: datetime, period_end: datetime) -> bool:
    """Check if a date falls within the specified week range."""
    if not date_str:
        return False

    dt = parse_iso_datetime(date_str)
    if not dt:
        return False

    # Convert to Sydney timezone for comparison
    sydney_tz = ZoneInfo('Australia/Sydney')
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=sydney_tz)
    else:
        dt = dt.astimezone(sydney_tz)

    return period_start <= dt <= period_end


def archive_path_for(period_start: datetime, archive_dir: Optional[Path] = None) -> Path:
    """The dated archive path for a digest whose period starts on ``period_start``.

    ``archive_dir`` defaults to the module-level :data:`DIGEST_ARCHIVE_DIR`
    *at call time*, so tests can monkeypatch that constant to redirect writes.
    """
    if archive_dir is None:
        archive_dir = DIGEST_ARCHIVE_DIR
    return archive_dir / f'digest-{period_start.date().isoformat()}.json'


def resolve_previous_digest_path(
    period_start: datetime,
    archive_dir: Optional[Path] = None,
    fallback: Optional[Path] = None,
) -> Optional[Path]:
    """Pick the path to load as last week's digest for dedup purposes.

    Resolution order:

    1. The dated archive snapshot for the immediately preceding Monday
       (``<archive_dir>/digest-<last_week_monday>.json``). This is the
       authoritative record of what last Sunday's scheduled run committed
       and emailed, unaffected by any mid-week manual reruns of the
       generator.
    2. The current ``digest.json`` on disk, as a fallback for cases where
       the dated archive isn't available (most notably the first run after
       this archive mechanism is introduced).
    3. ``None`` — treated as "no previous digest".

    ``archive_dir`` / ``fallback`` default to the module-level constants
    *at call time*.
    """
    if archive_dir is None:
        archive_dir = DIGEST_ARCHIVE_DIR
    if fallback is None:
        fallback = OUTPUT_PATH
    last_week_start = period_start - timedelta(days=7)
    archived = archive_path_for(last_week_start, archive_dir)
    if archived.exists():
        return archived
    if fallback.exists():
        return fallback
    return None


def load_previous_digest(path: Optional[Path]) -> Dict[str, Any]:
    """Load a digest JSON file, or return an empty dict.

    Used to deduplicate the time-scoped buckets: anything that was already
    surfaced in last week's digest is not repeated this week, even if its
    primary date falls inside the widened lookback window.
    """
    if path is None or not path.exists():
        return {}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def bucket_ids(digest: Dict[str, Any], bucket: str) -> Set[str]:
    """Return the set of merger IDs in a given bucket of a digest."""
    items = digest.get(bucket) or []
    return {m.get('merger_id') for m in items if m.get('merger_id')}


def get_first_paragraph(description: str) -> str:
    """Extract the first paragraph from a description."""
    if not description:
        return ''

    paragraphs = description.split('\n\n')
    paragraphs = [p.strip() for p in paragraphs if p.strip()]

    for para in paragraphs:
        # Remove markdown formatting for word count
        plain_text = para.replace('**', '').replace('*', '').strip()
        word_count = len(plain_text.split())

        # Only return paragraphs with more than 1 word
        if word_count > 1:
            return para

    # Fallback to first paragraph if no substantial one found
    return paragraphs[0] if paragraphs else ''


def create_merger_summary(merger: Dict[str, Any]) -> Dict[str, Any]:
    """Create a lightweight summary of a merger for the digest."""
    # Truncate description to first paragraph to reduce payload size
    full_description = merger.get('merger_description', '')
    truncated_description = get_first_paragraph(full_description)

    return {
        'merger_id': merger.get('merger_id'),
        'merger_name': merger.get('merger_name'),
        'url': merger.get('url'),
        'acquirers': merger.get('acquirers', []),
        'targets': merger.get('targets', []),
        'effective_notification_datetime': merger.get('effective_notification_datetime'),
        'determination_publication_date': merger.get('determination_publication_date'),
        'end_of_determination_period': merger.get('end_of_determination_period'),
        'accc_determination': merger.get('accc_determination'),
        'stage': merger.get('stage'),
        'status': merger.get('status'),
        'is_waiver': merger.get('is_waiver', False),
        'phase_1_determination': merger.get('phase_1_determination'),
        'phase_2_determination': merger.get('phase_2_determination'),
        'merger_description': truncated_description,
        'events': merger.get('events', []),
    }


def generate_weekly_digest(
    previous_digest: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Generate the weekly digest data.

    Applies :func:`merger_filters.filter_active`, which excludes suspended
    assessments but *includes* waivers. Waiver grants and denials count as
    substantive ACCC activity and belong in the weekly summary; suspended
    mergers are paused and are not meaningful week-to-week activity.

    Args:
        previous_digest: The previously generated digest, used to deduplicate
            the time-scoped buckets so mergers already surfaced in last
            week's digest are not repeated. Defaults to reading the
            currently-on-disk digest.json.
    """
    mergers = filter_active(load_mergers())

    # Get the Monday-Sunday week range in Australian time (for display) and
    # the widened lookback window that actually drives inclusion.
    period_start, period_end = get_last_week_range()
    lookback_start = period_start - timedelta(days=7 * (LOOKBACK_WEEKS - 1))

    if previous_digest is None:
        previous_digest = load_previous_digest(resolve_previous_digest_path(period_start))
    already_notified = bucket_ids(previous_digest, 'new_deals_notified')
    already_cleared = bucket_ids(previous_digest, 'deals_cleared')
    already_declined = bucket_ids(previous_digest, 'deals_declined')

    sydney_tz = ZoneInfo('Australia/Sydney')
    now_sydney = datetime.now(sydney_tz)

    digest = {
        'generated_at': now_sydney.isoformat(),
        'period_start': period_start.isoformat(),
        'period_end': period_end.isoformat(),
        'new_deals_notified': [],
        'deals_cleared': [],
        'deals_declined': [],
        'ongoing_phase_1': [],
        'ongoing_phase_2': [],
    }

    for merger in mergers:
        status = merger.get('status')
        stage = merger.get('stage', '')
        notification_date = merger.get('effective_notification_datetime')
        determination_date = merger.get('determination_publication_date')
        accc_determination = merger.get('accc_determination')
        phase_1_determination = merger.get('phase_1_determination')
        phase_2_determination = merger.get('phase_2_determination')
        merger_id = merger.get('merger_id')

        # New deals notified within the lookback window, minus anything already
        # surfaced in last week's digest.
        if (is_in_week_range(notification_date, lookback_start, period_end) and
            status == merger_status.UNDER_ASSESSMENT and
            merger_id not in already_notified):
            digest['new_deals_notified'].append(create_merger_summary(merger))

        # Deals cleared / declined within the lookback window, minus anything
        # already surfaced in last week's digest. This is how a Friday
        # determination that only appeared on the register the following
        # Monday — too late for last week's digest — gets caught here.
        if is_in_week_range(determination_date, lookback_start, period_end):
            if (accc_determination == merger_status.APPROVED or
                phase_1_determination == merger_status.APPROVED or
                phase_2_determination == merger_status.APPROVED):
                if merger_id not in already_cleared:
                    digest['deals_cleared'].append(create_merger_summary(merger))
            elif (accc_determination == merger_status.NOT_APPROVED or
                  phase_1_determination == merger_status.NOT_APPROVED or
                  phase_2_determination == merger_status.NOT_APPROVED):
                if merger_id not in already_declined:
                    digest['deals_declined'].append(create_merger_summary(merger))

        # Ongoing phase 1/2 lists are always a current snapshot, not a
        # week-scoped activity list, so dedup does not apply.
        if (status == merger_status.UNDER_ASSESSMENT and
            stage == 'Phase 1 - initial assessment'):
            digest['ongoing_phase_1'].append(create_merger_summary(merger))

        if (status == merger_status.UNDER_ASSESSMENT and
            stage == 'Phase 2 - detailed assessment'):
            digest['ongoing_phase_2'].append(create_merger_summary(merger))

    # Sort new deals by notification date (ascending)
    digest['new_deals_notified'].sort(
        key=lambda x: x.get('effective_notification_datetime') or ''
    )

    # Sort cleared and declined by determination date (ascending)
    digest['deals_cleared'].sort(
        key=lambda x: x.get('determination_publication_date') or ''
    )
    digest['deals_declined'].sort(
        key=lambda x: x.get('determination_publication_date') or ''
    )

    # Sort ongoing deals by notification date (ascending)
    digest['ongoing_phase_1'].sort(
        key=lambda x: x.get('effective_notification_datetime') or ''
    )
    digest['ongoing_phase_2'].sort(
        key=lambda x: x.get('effective_notification_datetime') or ''
    )

    return digest


def _write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def main():
    """Main entry point."""
    print("Generating weekly digest...")

    digest = generate_weekly_digest()

    _write_json(OUTPUT_PATH, digest)

    # Also write a dated snapshot keyed by the Monday of the period. Next
    # week's run will dedup against this archived copy rather than the
    # live digest.json, so an ad-hoc mid-week re-run doesn't silently
    # spoil the next scheduled digest.
    period_start = datetime.fromisoformat(digest['period_start'])
    archive_path = archive_path_for(period_start)
    _write_json(archive_path, digest)

    print(f"Digest generated: {OUTPUT_PATH}")
    print(f"Archive snapshot: {archive_path}")
    print(f"\nSummary:")
    print(f"  New deals notified (last week): {len(digest['new_deals_notified'])}")
    print(f"  Deals cleared (last week): {len(digest['deals_cleared'])}")
    print(f"  Deals declined (last week): {len(digest['deals_declined'])}")
    print(f"  Ongoing phase 1 deals: {len(digest['ongoing_phase_1'])}")
    print(f"  Ongoing phase 2 deals: {len(digest['ongoing_phase_2'])}")


if __name__ == '__main__':
    main()
