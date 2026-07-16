"""Phase 1 timeline-extension tracker — ``extensions.json``.

Under the merger regime the ACCC has a 30-business-day statutory clock to make
its Phase 1 determination. That clock can be stretched: the register publishes
a "Timeline extended by N business days" notice each time, giving a reason. This
output surfaces every such extension so the frontend can show how often, how
long, and why the Phase 1 clock gets pushed out — and how strongly an extension
foreshadows a Phase 2 escalation.

Extension day counts and reasons are only available in the event *title* string
(there is no structured field on the register), so they are parsed here.
"""

import re

from constants import merger_status
from merger_filters import filter_notifications
from static_data.enrichment import is_phase_2_referral_event

# The standard Phase 1 statutory window, in business days, before any extension.
STATUTORY_PHASE_1_BD = 30

# "Timeline extended by 6 business days – following request for further information"
# and the earlier long-form "ACCC decided to extend the Phase 1 determination
# period ...". The day count is optional — the very first extension notice (Nov
# 2025) predates the standardised "extended by N business days" wording.
_EXTENSION_RE = re.compile(r'extended by (\d+)\s+business day', re.IGNORECASE)


def is_extension_event(title: str) -> bool:
    """Return True if an event title marks a Phase 1 timeline extension."""
    if not title:
        return False
    lower = title.lower()
    return 'extended by' in lower or 'extend the phase 1' in lower


def _parse_business_days(title: str):
    match = _EXTENSION_RE.search(title or '')
    return int(match.group(1)) if match else None


def _classify_reason(title: str) -> str:
    """Bucket an extension notice into a human-readable reason category.

    Order matters: an ACCC information request is phrased "request for further
    information", which also contains "request", so it must be tested before the
    generic party-request bucket.
    """
    lower = (title or '').lower()
    if 'further information' in lower:
        return 'ACCC information request'
    if 'remedy' in lower:
        return 'Remedy under consideration'
    if (
        'request by' in lower
        or 'request from' in lower
        or 'notifying party' in lower
        or 'by parties' in lower
        or 'extension request' in lower
    ):
        return 'Requested by the merger parties'
    return 'Other'


def _reason_detail(title: str) -> str:
    """The 'following ...' clause of an extension notice, trimmed for display."""
    match = re.search(r'following\s+(.*)$', title or '', re.IGNORECASE)
    if not match:
        return ''
    return re.sub(r'\s+', ' ', match.group(1)).strip().rstrip('.')


def _escalated_to_phase_2(merger: dict) -> bool:
    if (merger.get('stage') or '').startswith(merger_status.PHASE_2):
        return True
    if merger.get('phase_1_determination') == merger_status.REFERRED_TO_PHASE_2:
        return True
    return any(
        is_phase_2_referral_event(event.get('title', ''))
        for event in merger.get('events', [])
    )


def _matter_entry(merger: dict, extensions: list) -> dict:
    parsed = [e['business_days'] for e in extensions if e['business_days'] is not None]
    return {
        'merger_id': merger.get('merger_id'),
        'merger_name': merger.get('merger_name'),
        'stage': merger.get('stage'),
        'status': merger.get('status'),
        'notification_date': merger.get('effective_notification_datetime'),
        'phase_1_determination': merger.get('phase_1_determination'),
        'phase_1_determination_date': merger.get('phase_1_determination_date'),
        'escalated_to_phase_2': _escalated_to_phase_2(merger),
        'total_extension_bd': sum(parsed) if parsed else None,
        'extension_count': len(extensions),
        'extensions': extensions,
    }


def _median(values: list):
    if not values:
        return None
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return round((ordered[mid - 1] + ordered[mid]) / 2, 1)


def generate(mergers: list) -> dict:
    """Return the extensions.json payload."""
    notifications = filter_notifications(mergers)

    matters = []
    for merger in notifications:
        extensions = []
        for event in merger.get('events', []):
            title = event.get('title', '')
            if not is_extension_event(title):
                continue
            extensions.append({
                'date': event.get('date'),
                'business_days': _parse_business_days(title),
                'reason_category': _classify_reason(title),
                'reason_detail': _reason_detail(title),
                'title': title,
            })
        if extensions:
            extensions.sort(key=lambda e: e['date'] or '')
            matters.append(_matter_entry(merger, extensions))

    # Longest single extension first, then most recently notified.
    matters.sort(
        key=lambda m: (m['total_extension_bd'] or 0, m['notification_date'] or ''),
        reverse=True,
    )

    all_events = [e for m in matters for e in m['extensions']]
    parsed_days = [e['business_days'] for e in all_events if e['business_days'] is not None]
    per_matter_totals = [m['total_extension_bd'] for m in matters if m['total_extension_bd']]

    # Reason breakdown (events + business days), largest first.
    reason_events, reason_days = {}, {}
    for event in all_events:
        cat = event['reason_category']
        reason_events[cat] = reason_events.get(cat, 0) + 1
        reason_days[cat] = reason_days.get(cat, 0) + (event['business_days'] or 0)
    reasons = [
        {'category': cat, 'events': reason_events[cat], 'business_days': reason_days[cat]}
        for cat in reason_events
    ]
    reasons.sort(key=lambda r: (-r['events'], -r['business_days']))

    # Extension notices by calendar month.
    month_counts = {}
    for event in all_events:
        if event['date']:
            month = event['date'][:7]
            month_counts[month] = month_counts.get(month, 0) + 1
    by_month = [{'month': m, 'count': c} for m, c in sorted(month_counts.items())]

    phase_2_total = sum(1 for m in notifications if _escalated_to_phase_2(m))
    extended_escalated = sum(1 for m in matters if m['escalated_to_phase_2'])

    summary = {
        'notifications_total': len(notifications),
        'matters_extended': len(matters),
        'share_extended_pct': (
            round(len(matters) / len(notifications) * 100, 1) if notifications else None
        ),
        'extension_events_total': len(all_events),
        'total_extension_bd': sum(parsed_days),
        'median_matter_extension_bd': _median(per_matter_totals),
        'longest_single_bd': max(parsed_days) if parsed_days else None,
        'phase_2_total': phase_2_total,
        'extended_escalated_to_phase_2': extended_escalated,
        # Of matters that were extended, the share that went on to Phase 2.
        'escalation_rate_given_extension_pct': (
            round(extended_escalated / len(matters) * 100, 1) if matters else None
        ),
        # Of all Phase 2 escalations, the share that had been extended first.
        'phase_2_preceded_by_extension_pct': (
            round(extended_escalated / phase_2_total * 100, 1) if phase_2_total else None
        ),
        # Base rate: share of all notifications that reach Phase 2.
        'base_phase_2_rate_pct': (
            round(phase_2_total / len(notifications) * 100, 1) if notifications else None
        ),
        'statutory_phase_1_bd': STATUTORY_PHASE_1_BD,
    }

    return {
        'summary': summary,
        'reasons': reasons,
        'by_month': by_month,
        'matters': matters,
    }
