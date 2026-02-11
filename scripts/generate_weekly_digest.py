#!/usr/bin/env python3
"""
Generate a weekly digest of ACCC merger activity.

This script creates a summary showing:
- New deals notified (but not yet determined) in the last week
- Deals cleared in the last week
- Deals declined/not approved in the last week
- Ongoing phase 1 deals
- Ongoing phase 2 deals

Output: digest.json in the frontend public data directory
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Any


def load_mergers_data() -> List[Dict[str, Any]]:
    """Load the processed mergers data."""
    data_path = Path(__file__).parent.parent / 'data' / 'processed' / 'mergers.json'

    with open(data_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Handle both wrapped and unwrapped data formats
    if isinstance(data, dict) and 'mergers' in data:
        return data['mergers']
    return data


def parse_datetime(date_str: str) -> datetime:
    """Parse ISO 8601 datetime string to datetime object."""
    if not date_str:
        return None

    try:
        # Handle both with and without timezone
        if date_str.endswith('Z'):
            return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        return datetime.fromisoformat(date_str)
    except (ValueError, AttributeError):
        return None


def is_in_last_week(date_str: str, reference_date: datetime = None) -> bool:
    """Check if a date falls within the last week."""
    if not date_str:
        return False

    dt = parse_datetime(date_str)
    if not dt:
        return False

    if reference_date is None:
        reference_date = datetime.now(timezone.utc)

    one_week_ago = reference_date - timedelta(days=7)
    return one_week_ago <= dt <= reference_date


def create_merger_summary(merger: Dict[str, Any]) -> Dict[str, Any]:
    """Create a lightweight summary of a merger for the digest."""
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
        'merger_description': merger.get('merger_description'),
        'events': merger.get('events', []),
    }


def generate_weekly_digest() -> Dict[str, Any]:
    """Generate the weekly digest data."""
    mergers = load_mergers_data()
    reference_date = datetime.now(timezone.utc)

    digest = {
        'generated_at': reference_date.isoformat(),
        'period_start': (reference_date - timedelta(days=7)).isoformat(),
        'period_end': reference_date.isoformat(),
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

        # New deals notified in the last week (not yet determined)
        if (is_in_last_week(notification_date, reference_date) and
            status == 'Under assessment'):
            digest['new_deals_notified'].append(create_merger_summary(merger))

        # Deals cleared in the last week
        if is_in_last_week(determination_date, reference_date):
            if accc_determination in ['Approved'] or phase_1_determination == 'Approved' or phase_2_determination == 'Approved':
                digest['deals_cleared'].append(create_merger_summary(merger))
            # Deals declined/not approved in the last week
            elif accc_determination in ['Not approved'] or phase_1_determination == 'Not approved' or phase_2_determination == 'Not approved':
                digest['deals_declined'].append(create_merger_summary(merger))

        # Ongoing phase 1 deals (under assessment, in phase 1)
        if (status == 'Under assessment' and
            stage == 'Phase 1 - initial assessment'):
            digest['ongoing_phase_1'].append(create_merger_summary(merger))

        # Ongoing phase 2 deals (under assessment, in phase 2)
        if (status == 'Under assessment' and
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


def main():
    """Main entry point."""
    print("Generating weekly digest...")

    digest = generate_weekly_digest()

    # Output to frontend public data directory
    output_path = Path(__file__).parent.parent / 'merger-tracker' / 'frontend' / 'public' / 'data' / 'digest.json'
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(digest, f, indent=2, ensure_ascii=False)

    print(f"Digest generated: {output_path}")
    print(f"\nSummary:")
    print(f"  New deals notified (last week): {len(digest['new_deals_notified'])}")
    print(f"  Deals cleared (last week): {len(digest['deals_cleared'])}")
    print(f"  Deals declined (last week): {len(digest['deals_declined'])}")
    print(f"  Ongoing phase 1 deals: {len(digest['ongoing_phase_1'])}")
    print(f"  Ongoing phase 2 deals: {len(digest['ongoing_phase_2'])}")


if __name__ == '__main__':
    main()
