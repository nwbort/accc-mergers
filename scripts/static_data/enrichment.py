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


def enrich_merger(merger: dict, commentary: dict = None, questionnaire_data: dict = None) -> dict:
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
        title = event.get('title', '')
        if 'subject to Phase 2 review' in title:
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

    return m


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
