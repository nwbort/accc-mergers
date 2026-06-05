"""Enrich a raw merger record with computed fields.

``enrich_merger`` is called once per merger, up-front, by the orchestrator.
All downstream generators consume the already-enriched objects.
"""

from constants import merger_status
from cutoff import is_waiver_merger
from date_utils import parse_iso_datetime
from normalization import normalize_determination

from .business_days import add_business_days, subtract_business_days


def extract_phase_from_event(event_title: str) -> str | None:
    """Extract phase information from event title."""
    if not event_title:
        return None
    if merger_status.PHASE_1 in event_title:
        return merger_status.PHASE_1
    elif merger_status.PHASE_2 in event_title:
        return merger_status.PHASE_2
    elif merger_status.PUBLIC_BENEFITS in event_title or 'public benefits' in event_title:
        return merger_status.PUBLIC_BENEFITS
    elif merger_status.WAIVER in event_title or 'waiver' in event_title:
        return merger_status.WAIVER
    elif 'notified' in event_title:
        return merger_status.PHASE_1  # Notification always starts Phase 1
    return None


def is_phase_2_referral_event(event_title: str) -> bool:
    """Return True if ``event_title`` marks the Phase 1 → Phase 2 transition.

    The ACCC has used several phrasings on the public register:
      - "ACCC decided notification is subject to Phase 2 review" (2025)
      - "Decision to Proceed to a Phase 2 review" (from 2026)
      - "<name> - Phase 2 Notice" (the notice that moves a matter into Phase 2)
    """
    if not event_title:
        return False
    lower = event_title.lower()
    return (
        'subject to phase 2 review' in lower
        or 'proceed to a phase 2' in lower
        or 'proceed to phase 2' in lower
        or 'phase 2 notice' in lower
    )


# Stage label applied when we infer Phase 2 from a notice event before the
# ACCC register's own stage field has caught up. Mirrors the value the ACCC
# uses for matters it has already moved into Phase 2.
INFERRED_PHASE_2_STAGE = 'Phase 2 - detailed assessment'


def enrich_merger(
    merger: dict,
    commentary: dict = None,
    questionnaire_data: dict = None,
    nocc_data: dict = None,
) -> dict:
    """Add computed fields to a merger (phase determinations, etc.)."""
    m = merger.copy()

    # Normalize the determination
    m['accc_determination'] = normalize_determination(m.get('accc_determination'))

    # Add is_waiver flag
    m['is_waiver'] = is_waiver_merger(merger)

    # Add user commentary if available
    merger_id = m.get('merger_id', '')
    if commentary and merger_id in commentary:
        m['comments'] = commentary[merger_id].get('comments', [])

    # Compute phase-specific determinations based on stage and events
    phase_1_det = None
    phase_1_det_date = None
    phase_2_det = None
    phase_2_det_date = None
    pb_det = None
    pb_det_date = None

    # Check events for Phase 2 review decision (indicates Phase 1 completion)
    for event in m.get('events', []):
        if is_phase_2_referral_event(event.get('title', '')):
            phase_1_det = merger_status.REFERRED_TO_PHASE_2
            phase_1_det_date = event.get('date')
            break

    if m.get('accc_determination') and m.get('determination_publication_date'):
        stage = m.get('stage', merger_status.PHASE_1)
        det = m['accc_determination']
        det_date = m['determination_publication_date']

        if merger_status.PHASE_1 in stage:
            phase_1_det = det
            phase_1_det_date = det_date
        elif merger_status.PHASE_2 in stage:
            phase_2_det = det
            phase_2_det_date = det_date
        elif 'Public' in stage or 'Benefits' in stage:
            pb_det = det
            pb_det_date = det_date

    m['phase_1_determination'] = phase_1_det
    m['phase_1_determination_date'] = phase_1_det_date
    m['phase_2_determination'] = phase_2_det
    m['phase_2_determination_date'] = phase_2_det_date
    m['public_benefits_determination'] = pb_det
    m['public_benefits_determination_date'] = pb_det_date

    # Compute competition concerns notice date for Phase 2 mergers
    # The notice is due by BD 25 of Phase 2 (Phase 2 BD 1 = end_of_determination_period - 90 BDs)
    stage = m.get('stage', '')
    phase2_end = m.get('end_of_determination_period')
    notice_already_issued = any(
        'competition concern' in event.get('title', '').lower()
        for event in m.get('events', [])
    )
    if stage and merger_status.PHASE_2 in stage and phase2_end and not notice_already_issued:
        try:
            phase2_end_date = parse_iso_datetime(phase2_end)
            if phase2_end_date is None:
                raise ValueError("unparseable date")
            phase2_end_date = phase2_end_date.replace(tzinfo=None)
            phase2_start_date = subtract_business_days(phase2_end_date, 90)
            notice_date = add_business_days(phase2_start_date, 25)
            m['competition_concerns_notice_date'] = notice_date.strftime('%Y-%m-%dT12:00:00Z')
        except (ValueError, AttributeError):
            pass

    # Infer Phase 2 when the ACCC register lags behind a Phase 2 notice.
    # The register sometimes issues a Phase 2 notice (or a "subject to / proceed
    # to Phase 2" decision) before updating the matter's stage field, leaving it
    # showing "Phase 1" even though the merger has moved into Phase 2. When that
    # happens, treat the merger as Phase 2 so the site reflects reality.
    #
    # Parties can still drop out before Phase 2 formally begins, so this is only
    # an inference: the pipeline opens a tracking issue whenever it applies (see
    # detect_inferred_phase_2 in extract_mergers.py), which auto-closes once the
    # register's own stage catches up. The override is done last so every
    # stage-dependent computation above uses the genuine ACCC stage.
    if merger_status.PHASE_2 not in (m.get('stage') or '') and any(
        is_phase_2_referral_event(event.get('title', '')) for event in m.get('events', [])
    ):
        m['phase_2_inferred'] = True
        m['stage'] = INFERRED_PHASE_2_STAGE

    # Ensure anzsic_codes exists
    if 'anzsic_codes' not in m:
        m['anzsic_codes'] = []

    # Add phase to events
    if 'events' in m:
        for event in m['events']:
            if 'phase' not in event:
                event['phase'] = extract_phase_from_event(event.get('title', ''))

    # Flag whether questionnaire data exists for this merger
    if questionnaire_data and merger_id in questionnaire_data:
        q_data = questionnaire_data[merger_id]
        if q_data.get('questions'):
            m['has_questionnaire'] = True

    # Flag whether a parsed NOCC summary exists for this merger
    if nocc_data and merger_id in nocc_data:
        n_data = nocc_data[merger_id]
        if n_data.get('sections'):
            m['has_nocc'] = True

    return m


def link_similar_mergers(enriched_mergers: list, similar_map: dict) -> int:
    """Attach compact similar_mergers cards to each merger in-place.

    similar_map: {merger_id: [similar_merger_id, ...]}

    Each card contains the fields needed to render a summary tile without
    requiring a separate fetch: merger_id, merger_name, status,
    accc_determination, acquirers (first 2), targets (first 2).

    Returns the number of mergers that had at least one similar merger linked.
    """
    def _make_card(m: dict) -> dict:
        return {
            'merger_id': m.get('merger_id'),
            'merger_name': m.get('merger_name'),
            'status': m.get('status'),
            'accc_determination': m.get('accc_determination'),
            'acquirers': m.get('acquirers', [])[:2],
            'targets': m.get('targets', [])[:2],
        }

    card_lookup = {m['merger_id']: _make_card(m) for m in enriched_mergers if m.get('merger_id')}

    linked = 0
    for merger in enriched_mergers:
        mid = merger.get('merger_id', '')
        similar_ids = similar_map.get(mid, [])
        if not similar_ids:
            continue
        # Safety net: never surface the merger's own waiver/notification partner
        # (already shown via the related_merger link).
        related_mid = (merger.get('related_merger') or {}).get('merger_id')
        cards = [
            card_lookup[sid]
            for sid in similar_ids
            if sid in card_lookup and sid != related_mid
        ]
        if cards:
            merger['similar_mergers'] = cards
            linked += 1
    return linked


def link_related_mergers(enriched_mergers: list, related_mergers: dict) -> int:
    """Attach ``related_merger`` entries to each merger in-place, with resolved names.

    Returns the number of mergers that had a relationship linked.
    """
    name_lookup = {m['merger_id']: m['merger_name'] for m in enriched_mergers if m.get('merger_id')}
    linked = 0
    for m in enriched_mergers:
        mid = m.get('merger_id', '')
        if mid in related_mergers:
            related = related_mergers[mid]
            m['related_merger'] = {
                'merger_id': related['merger_id'],
                'relationship': related['relationship'],
                'merger_name': name_lookup.get(related['merger_id'], ''),
            }
            linked += 1
    return linked
