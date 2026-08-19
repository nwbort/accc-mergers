"""Waiver → notification refile tracker — ``refiled-notifications.json``.

Surfaces every merger originally filed as a waiver application, declined,
and later re-filed as a formal notification — the ``waiver_refiled`` pairs
recorded in ``related_mergers.json``. Companion view to the Phase 2 tracker
(``phase2.py``). Relies on ``link_related_mergers`` having already attached
``related_merger`` to each merger (see :func:`static_data.enrichment`).
"""

from constants import merger_status

from ..durations import collect_phase_1_durations, median_or_none
from ..filters import filter_notifications

#: Determinations that count as the merger being allowed to proceed, mirroring
#: the cleared/declined split used elsewhere (e.g. OUTCOME_DOT_COLORS on the
#: frontend, deals_cleared in the weekly digest).
CLEARED_DETERMINATIONS = merger_status.CLEARED_DETERMINATIONS


def _entry(waiver: dict, notification: dict) -> dict:
    return {
        'waiver_id': waiver.get('merger_id'),
        'waiver_name': waiver.get('merger_name'),
        'waiver_filed_date': waiver.get('effective_notification_datetime'),
        'waiver_declined_date': waiver.get('determination_publication_date'),
        'notification_id': notification.get('merger_id'),
        'notification_name': notification.get('merger_name'),
        'notification_filed_date': notification.get('effective_notification_datetime'),
        'notification_status': notification.get('status'),
        'notification_determination': notification.get('accc_determination'),
        'notification_determination_date': notification.get('determination_publication_date'),
        # How Phase 1 ended and when: 'Referred to phase 2' plus the referral
        # date for a matter sent to Phase 2, the Phase 1 determination
        # otherwise, both None while Phase 1 is still running. The timeline
        # card draws its Phase 2 leg from these.
        'notification_phase_1_determination': notification.get('phase_1_determination'),
        'notification_phase_1_end_date': notification.get('phase_1_determination_date'),
        # Statutory Phase 2 deadline — the right-hand end of the timeline for a
        # referred matter that hasn't been determined yet.
        'notification_end_of_determination_period': notification.get('end_of_determination_period'),
    }


def _phase_1_clearance_rate(notifications: list) -> dict:
    """Cleared-at-Phase-1 vs referred-to-Phase-2 split for concluded reviews.

    Counts every notification whose Phase 1 has ended — ``phase_1_determination``
    holds the referral for matters sent to Phase 2 and the determination for the
    rest, and is None while Phase 1 is still running. Measuring the Phase 1
    outcome (rather than the final determination) means a referral counts
    against the rate as soon as it happens instead of waiting months for the
    Phase 2 result, and puts the rate on the same denominator as
    :func:`_phase_duration`. Outcomes that are neither a clearance nor a
    referral are skipped: Phase 1 does not block a merger, so a stray value
    can't silently distort the rate.
    """
    cleared = sum(
        1 for m in notifications
        if m.get('phase_1_determination') in CLEARED_DETERMINATIONS
    )
    referred = sum(
        1 for m in notifications
        if m.get('phase_1_determination') == merger_status.REFERRED_TO_PHASE_2
    )
    total = cleared + referred
    return {
        'cleared': cleared,
        'referred': referred,
        'total': total,
        'rate': round(cleared / total, 3) if total else None,
    }


def _phase_duration(unique_mergers: list) -> dict | None:
    """Phase 1 duration stats for a set of notification mergers.

    Mirrors :func:`static_data.outputs.industries._phase_duration`. Measures
    notification → Phase 1 end (referral date for matters sent to Phase 2, so
    the Phase 2 clock never inflates the figures). Returns ``None`` when
    there are no completed Phase 1 reviews in the set.
    """
    durations, business_durations = collect_phase_1_durations(unique_mergers)

    if not durations and not business_durations:
        return None

    def _avg(values):
        return sum(values) / len(values) if values else None

    return {
        "average_days": _avg(durations),
        "median_days": median_or_none(durations),
        "average_business_days": _avg(business_durations),
        "median_business_days": median_or_none(business_durations),
        "completed_count": len(business_durations),
    }


def generate(mergers: list) -> dict:
    """Return the refiled-notifications.json payload.

    ``current`` holds pairs whose notification hasn't been determined yet;
    ``completed`` holds pairs where the notification has a determination.
    ``phase_duration`` / ``straight_phase_duration`` let the page compare how
    long refiled notifications' concluded Phase 1 reviews took against
    notifications that were filed as a Phase 1 review from the outset (i.e.
    everything else). Both sides use the same rule: any matter whose Phase 1
    has concluded counts, including referrals still awaiting a Phase 2 outcome.
    ``phase_1_clearance_rate`` / ``straight_phase_1_clearance_rate`` split the
    same two populations by Phase 1 outcome — cleared in Phase 1 vs referred to
    Phase 2.
    """
    by_id = {m.get('merger_id'): m for m in mergers if m.get('merger_id')}

    current = []
    completed = []
    refiled_notifications = []
    for merger in mergers:
        related = merger.get('related_merger')
        if not related or related.get('relationship') != 'refiled_as':
            continue
        notification = by_id.get(related.get('merger_id'))
        if not notification:
            continue
        entry = _entry(merger, notification)
        # Every paired notification counts towards the Phase 1 duration stats:
        # collect_phase_1_durations only measures matters whose Phase 1 has
        # concluded, which includes a referral to Phase 2 even while the final
        # determination is pending — the same rule the straight baseline uses.
        refiled_notifications.append(notification)
        if entry['notification_determination'] and entry['notification_determination_date']:
            completed.append(entry)
        else:
            current.append(entry)

    # Current: most recently filed notification first (freshest matter on top).
    current.sort(key=lambda e: e['notification_filed_date'] or '', reverse=True)
    # Completed: most recently determined first.
    completed.sort(key=lambda e: e['notification_determination_date'] or '', reverse=True)

    refiled_ids = {e['notification_id'] for e in current} | {e['notification_id'] for e in completed}
    straight_notifications = [
        m for m in filter_notifications(mergers) if m.get('merger_id') not in refiled_ids
    ]

    return {
        'current': current,
        'completed': completed,
        'count': {'current': len(current), 'completed': len(completed)},
        'phase_1_clearance_rate': _phase_1_clearance_rate(refiled_notifications),
        'straight_phase_1_clearance_rate': _phase_1_clearance_rate(straight_notifications),
        'phase_duration': _phase_duration(refiled_notifications),
        'straight_phase_duration': _phase_duration(straight_notifications),
    }
