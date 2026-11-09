"""Recent events feed — ``recent-events.json``.

The backward-looking twin of :mod:`upcoming_events`: every event on every
matter's register timeline dated within the last ``days_back`` calendar days
(Sydney), newest first, each tagged with a ``type`` by :func:`classify`.

Every type is published, including the notifications and determinations the
dashboard already shows in its own cards — which of them the dashboard's
"Recent events" table displays is the frontend's call
(``frontend/src/constants/recentEventTypes.js``), so narrowing the table is a
one-line change there rather than a regeneration.

Suspended assessments are left out, as everywhere else in the public
activity streams; waivers and ceased matters are kept (their events are what
happened, whatever the matter's status now).
"""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from scripts.date_utils import parse_iso_datetime
from scripts.merger_filters import is_suspended

# The register is Australian, so "the last two weeks" is counted on the
# Sydney calendar, as upcoming_events counts "today".
_SYDNEY = ZoneInfo('Australia/Sydney')

# Every type classify() can return, in the order the frontend lists them.
TYPES = (
    'notified',
    'materially_incomplete',
    'notification_completed',
    'questionnaire',
    'timeline_extension',
    'phase_1_determination',
    'phase_2_referral',
    'competition_concerns',
    'remedy_offer',
    'remedy_questionnaire',
    'undertaking_accepted',
    'phase_2_determination',
    'reasons',
    'public_benefit',
    'ceased',
    'waiver_determination',
    'tribunal',
    'federal_court',
    'other',
)


def classify(event: dict) -> str:
    """Which kind of register event ``event`` is.

    Reads the flags extraction and enrichment set first and falls back to the
    title, whose wording is the ACCC's and varies (see the tests for the
    variants seen so far). Order matters: a remedy questionnaire is a remedy
    before it is a questionnaire, and a cessation is flagged as a
    determination event.
    """
    if event.get('is_appeal'):
        return 'federal_court' if event.get('review_forum') == 'federal_court' else 'tribunal'

    title = (event.get('title') or '').lower()
    phase = event.get('phase')

    if title.startswith('merger notified'):
        return 'notified'
    if 'ceased' in title:
        return 'ceased'
    if phase == 'Waiver' and event.get('is_determination_event'):
        return 'waiver_determination'
    if '51abz' in title or 'materially incomplete' in title:
        return 'materially_incomplete'
    if '51aby' in title or 'effective notification date is' in title:
        return 'notification_completed'
    if 'extended by' in title or 'extend the phase' in title:
        return 'timeline_extension'
    if 'remedy' in title and 'questionnaire' in title:
        return 'remedy_questionnaire'
    if 'remedy offer' in title or ('undertaking' in title and 'draft' in title):
        return 'remedy_offer'
    if 'undertaking' in title and 'accept' in title:
        return 'undertaking_accepted'
    if ('statement of reasons' in title or 'summary of reasons' in title
            or 'annexure' in title):
        return 'reasons'
    if 'competition concern' in title:
        return 'competition_concerns'
    if ('phase 2 notice' in title or 'proceed to a phase 2' in title
            or 'subject to phase 2' in title):
        return 'phase_2_referral'
    if 'public benefit' in title or phase == 'Public benefit':
        return 'public_benefit'
    if event.get('is_determination_event'):
        return 'phase_2_determination' if phase == 'Phase 2' else 'phase_1_determination'
    # 'quesionnaire': the ACCC's own typo, on MN-60025.
    if (event.get('is_questionnaire_event') or 'questionnaire' in title
            or 'quesionnaire' in title or 'consultation' in title):
        return 'questionnaire'
    return 'other'


def generate(mergers: list, days_back: int = 14, now: datetime | None = None) -> dict:
    """Return the recent-events.json payload."""
    today = (now or datetime.now(_SYDNEY)).astimezone(_SYDNEY).date()
    earliest = today - timedelta(days=days_back)

    events = []
    for m in mergers:
        if is_suspended(m):
            continue
        for event in m.get('events') or []:
            parsed = parse_iso_datetime(event.get('date'))
            if parsed is None:
                continue
            day = parsed.date()
            if not earliest <= day <= today:
                continue
            entry = {
                'type': classify(event),
                'title': event.get('display_title') or event.get('title'),
                'date': event['date'],
                'merger_id': m['merger_id'],
                'merger_name': m['merger_name'],
                'stage': m.get('stage'),
                'is_waiver': bool(m.get('is_waiver')),
            }
            if event.get('url_gh'):
                entry['url_gh'] = event['url_gh']
            events.append(entry)

    # Newest first; within a day, by type then matter so the order is stable
    # between runs.
    order = {t: i for i, t in enumerate(TYPES)}
    events.sort(key=lambda e: (e['merger_id'], order.get(e['type'], len(order))))
    events.sort(key=lambda e: e['date'][:10], reverse=True)

    return {
        'events': events,
        'count': len(events),
        'days_back': days_back,
    }
