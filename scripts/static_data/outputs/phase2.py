"""Phase 2 mergers feed — ``phase-2-mergers.json``.

A lightweight list of every notification that has reached the ACCC's Phase 2
(detailed) review. The frontend uses this feed to auto-track mergers that
*become* Phase 2 going forward: it diffs the current set against a stored
baseline and starts tracking any newly-referred matter (see
``TrackingContext.jsx``). Because the auto-track is driven off this diff, the
feed only needs to identify which mergers are in Phase 2, plus enough context
(name, status, referral date) to render a notification.

A merger is considered Phase 2 when :data:`constants.merger_status.PHASE_2`
appears in its ``stage`` (e.g. ``"Phase 2 - detailed assessment"``) or its
``accc_determination`` is :data:`constants.merger_status.REFERRED_TO_PHASE_2`.
"""

from constants import merger_status

from date_utils import parse_iso_datetime


def _is_phase_2(merger: dict) -> bool:
    """Return True if the merger has reached Phase 2 review."""
    stage = merger.get('stage') or ''
    if merger_status.PHASE_2 in stage:
        return True
    return merger.get('accc_determination') == merger_status.REFERRED_TO_PHASE_2


def _referral_date(merger: dict) -> str | None:
    """Return the date the merger entered Phase 2, if discoverable.

    Uses the earliest timeline event tagged as Phase 2 (the referral decision
    precedes the Phase 2 determination), falling back to ``None`` so the
    frontend can degrade to the notification date.
    """
    phase_2_dates = [
        event['date']
        for event in merger.get('events', [])
        if event.get('date') and merger_status.PHASE_2 in (event.get('phase') or '')
    ]
    if not phase_2_dates:
        return None
    return min(phase_2_dates, key=lambda d: parse_iso_datetime(d) or d)


def generate(mergers: list) -> dict:
    """Return the phase-2-mergers.json payload."""
    entries = []
    for m in mergers:
        if not _is_phase_2(m):
            continue
        entries.append({
            "merger_id": m['merger_id'],
            "merger_name": m['merger_name'],
            "status": m.get('status'),
            "stage": m.get('stage'),
            "accc_determination": m.get('accc_determination'),
            "phase_2_date": _referral_date(m),
            "effective_notification_datetime": m.get('effective_notification_datetime'),
        })

    # Most-recently-referred first where we know the date; undated entries last.
    entries.sort(
        key=lambda e: e.get('phase_2_date') or e.get('effective_notification_datetime') or '',
        reverse=True,
    )

    return {
        "mergers": entries,
        "count": len(entries),
    }
