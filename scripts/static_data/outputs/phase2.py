"""Phase 2 tracker — ``phase2.json``.

Surfaces the small set of matters currently in Phase 2 plus completed Phase 2
matters, with the statutory milestones needed to render a timeline: referral
date, NOCC due/issued, and end of determination period. All milestone inputs
are already computed by :func:`static_data.enrichment.enrich_merger`.
"""

from constants import merger_status

from ..enrichment import is_phase_2_referral_event, phase_2_outcome
from ..filters import filter_notifications
from ..loaders import FORWARD_REFILE_RELATIONSHIPS


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
    # determination, so the cessation counts as the outcome — see
    # enrichment.phase_2_outcome, shared with stats.json's outcome counts.
    determination, determination_date = phase_2_outcome(merger)

    return {
        'merger_id': merger.get('merger_id'),
        'merger_name': merger.get('merger_name'),
        'referral_date': _referral_date(merger),
        'nocc_date': nocc_date,
        'nocc_issued': nocc_issued,
        'end_of_determination_period': merger.get('end_of_determination_period'),
        'determination': determination,
        'determination_date': determination_date,
        # The register records a conditional clearance as a plain "Approved";
        # the completed-matter card flags the difference.
        'has_conditions': bool(merger.get('has_conditions', False)),
        'phase_2_inferred': bool(merger.get('phase_2_inferred')),
        # Whether the matter is under review at the Australian Competition
        # Tribunal — surfaces an "Under appeal" chip on the completed card.
        'under_appeal': bool(merger.get('under_appeal')),
        # True for a matter (typically a ceased assessment) later re-filed as
        # a separate notification — the opposite direction to stats.py's
        # "recent mergers" is_refiled flag, which marks the re-filed matter.
        'is_refiled': (merger.get('related_merger') or {}).get('relationship') in FORWARD_REFILE_RELATIONSHIPS,
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
