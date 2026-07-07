"""Phase 2 tracker — ``phase2.json``.

See docs/repo-review-specs.md #20 for the spec this implements. Surfaces the
small set of matters currently in Phase 2 plus completed Phase 2 matters, with
the statutory milestones needed to render a timeline: referral date, NOCC
due/issued, and end of determination period. All milestone inputs are already
computed by :func:`static_data.enrichment.enrich_merger`.
"""

from constants import merger_status

from ..enrichment import is_phase_2_referral_event
from ..filters import filter_notifications


def _referral_date(merger: dict) -> str | None:
    for event in merger.get('events', []):
        if is_phase_2_referral_event(event.get('title', '')):
            return event.get('date')
    return None


def _nocc(merger: dict) -> tuple:
    """Return ``(date, issued)`` for the Notice of Competition Concerns.

    ``issued`` is True when the ACCC has actually published a "competition
    concern" event; otherwise falls back to the computed due date
    (``competition_concerns_notice_date``, BD 25 of Phase 2).
    """
    for event in merger.get('events', []):
        if 'competition concern' in event.get('title', '').lower():
            return event.get('date'), True
    return merger.get('competition_concerns_notice_date'), False


def _entry(merger: dict) -> dict:
    nocc_date, nocc_issued = _nocc(merger)

    # A ceased assessment ends the Phase 2 review without a formal
    # determination, so treat the cessation itself as the outcome (mirrors
    # stats.py's "recent determinations" handling of ceased assessments).
    determination = merger.get('phase_2_determination')
    determination_date = merger.get('phase_2_determination_date')
    if not determination and merger.get('status') == merger_status.ASSESSMENT_CEASED:
        determination = merger_status.ASSESSMENT_CEASED
        determination_date = merger.get('ceased_date')

    return {
        'merger_id': merger.get('merger_id'),
        'merger_name': merger.get('merger_name'),
        'referral_date': _referral_date(merger),
        'nocc_date': nocc_date,
        'nocc_issued': nocc_issued,
        'end_of_determination_period': merger.get('end_of_determination_period'),
        'determination': determination,
        'determination_date': determination_date,
        'phase_2_inferred': bool(merger.get('phase_2_inferred')),
    }


def generate(mergers: list) -> dict:
    """Return the phase2.json payload: current + completed Phase 2 matters."""
    current = []
    completed = []

    # Waivers are never Phase 2 matters, but ceased assessments must stay in
    # so their cessation can surface as a completed Phase 2 outcome below.
    for merger in filter_notifications(mergers):
        stage = merger.get('stage') or ''
        if merger_status.PHASE_2 not in stage:
            continue

        entry = _entry(merger)
        if entry['determination'] and entry['determination_date']:
            completed.append(entry)
        else:
            current.append(entry)

    # Current matters: soonest determination deadline first.
    current.sort(key=lambda e: e['end_of_determination_period'] or '')
    # Completed matters: most recently determined first.
    completed.sort(key=lambda e: e['determination_date'] or '', reverse=True)

    return {
        'current': current,
        'completed': completed,
        'count': {'current': len(current), 'completed': len(completed)},
    }
