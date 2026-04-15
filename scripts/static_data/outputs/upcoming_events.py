"""Upcoming events feed — ``upcoming-events.json``.

Surfaces future consultation deadlines, competition concern notices, and
determination period ends within ``days_ahead`` days. Excludes waivers and
suspended mergers using :func:`static_data.filters.exclude_for_public_output`.
"""

from collections import defaultdict  # noqa: F401  (kept for parity with original module)
from datetime import datetime, timedelta, timezone

from constants import merger_status  # noqa: F401  (kept for parity)

from ..business_days import add_business_days, subtract_business_days
from ..filters import exclude_for_public_output
from date_utils import parse_iso_datetime


def generate(mergers: list, days_ahead: int = 60) -> dict:
    """Return the upcoming-events.json payload."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    future = now + timedelta(days=days_ahead)

    events = []

    # Skip waivers + suspended assessments and already-determined mergers
    candidate_mergers = [
        m for m in exclude_for_public_output(mergers)
        if not m.get('determination_publication_date')
    ]

    for m in candidate_mergers:
        merger_id = m['merger_id']
        merger_name = m['merger_name']
        status = m.get('status')
        stage = m.get('stage')
        notification_date = m.get('effective_notification_datetime')

        # Consultation response due
        consultation_due = m.get('consultation_response_due_date')
        if consultation_due:
            try:
                due_date = parse_iso_datetime(consultation_due)
                if due_date is None:
                    raise ValueError("unparseable date")
                due_date = due_date.replace(tzinfo=None)
                if now <= due_date <= future:
                    events.append({
                        "type": "consultation_due",
                        "event_type_display": "Consultation responses due",
                        "date": consultation_due,
                        "merger_id": merger_id,
                        "merger_name": merger_name,
                        "status": status,
                        "stage": stage,
                        "effective_notification_datetime": notification_date,
                    })
            except (ValueError, AttributeError):
                pass

        # Phase 2 - Notice of competition concerns (issued by business day 25 of Phase 2)
        # Phase 2 BD 1 is derived by subtracting 89 BDs from end_of_determination_period
        # (BD 90 of Phase 2), not from the date the referral notice was issued.
        if stage and merger_status.PHASE_2 in stage:
            notice_already_issued = any(
                'competition concern' in event.get('title', '').lower()
                for event in m.get('events', [])
            )
            phase2_end = m.get('end_of_determination_period')
            if phase2_end and not notice_already_issued:
                try:
                    phase2_end_date = parse_iso_datetime(phase2_end)
                    if phase2_end_date is None:
                        raise ValueError("unparseable date")
                    phase2_end_date = phase2_end_date.replace(tzinfo=None)
                    phase2_start_date = subtract_business_days(phase2_end_date, 90)  # BD 1 of Phase 2
                    notice_date = add_business_days(phase2_start_date, 25)
                    notice_date_str = notice_date.strftime('%Y-%m-%dT12:00:00Z')
                    if now <= notice_date <= future:
                        events.append({
                            "type": "notice_of_competition_concerns",
                            "event_type_display": "Notice of competition concerns",
                            "date": notice_date_str,
                            "merger_id": merger_id,
                            "merger_name": merger_name,
                            "status": status,
                            "stage": stage,
                            "effective_notification_datetime": notification_date,
                        })
                except (ValueError, AttributeError):
                    pass

        # Determination period end
        determination_due = m.get('end_of_determination_period')
        if determination_due:
            try:
                due_date = parse_iso_datetime(determination_due)
                if due_date is None:
                    raise ValueError("unparseable date")
                due_date = due_date.replace(tzinfo=None)
                if now <= due_date <= future:
                    events.append({
                        "type": "determination_due",
                        "event_type_display": "Determination due",
                        "date": determination_due,
                        "merger_id": merger_id,
                        "merger_name": merger_name,
                        "status": status,
                        "stage": stage,
                        "effective_notification_datetime": notification_date,
                    })
            except (ValueError, AttributeError):
                pass

    events.sort(key=lambda x: x['date'])

    return {
        "events": events,
        "count": len(events),
        "days_ahead": days_ahead,
    }
