"""Enrich a raw merger record with computed fields.

``enrich_merger`` is called once per merger, up-front, by the orchestrator.
All downstream generators consume the already-enriched objects.
"""

import re
from datetime import timedelta

from scripts.constants import merger_status, tribunal
from scripts.cutoff import is_waiver_merger
from scripts.date_utils import parse_iso_datetime
from scripts.normalization import normalize_determination
from scripts.detect.party_matching import build_group_lookups, match_party

from .business_days import add_business_days, subtract_business_days

# Case-insensitive phrases indicating an ACCC approval was subject to
# conditions (a s 87B undertaking, divestiture, etc.), used by
# detect_has_conditions. Not exhaustive; refine as new phrasings are seen.
_CONDITION_PHRASES = (
    'subject to conditions',
    'conditions of approval',
    's 87b',
    'section 87b',
    '87b undertaking',
)


def _collect_determination_text(merger: dict) -> str:
    """Flatten the raw determination string and parsed determination-PDF
    content (table rows, statement of reasons) into one string for phrase
    matching in detect_has_conditions."""
    parts = [merger.get('accc_determination_raw') or '']

    for event in merger.get('events', []):
        # Events like "ACCC accepted s87B undertaking" carry the signal in
        # their title rather than in any parsed PDF content.
        parts.append(str(event.get('title') or ''))

        for row in event.get('determination_table_content') or []:
            if isinstance(row, dict):
                parts.append(str(row.get('item') or ''))
                parts.append(str(row.get('details') or ''))

        for block in event.get('determination_statement_of_reasons') or []:
            if not isinstance(block, dict):
                continue
            parts.append(str(block.get('text') or ''))
            for item in block.get('items') or []:
                if isinstance(item, dict):
                    parts.append(str(item.get('text') or ''))
                else:
                    parts.append(str(item))

    return '\n'.join(parts)


def detect_has_conditions(merger: dict) -> bool:
    """Detect whether an ACCC approval was granted subject to conditions.

    Matches case-insensitive phrases against the raw (pre-normalisation)
    determination string, event titles (e.g. "ACCC accepted s87B
    undertaking"), and the parsed determination PDF content. Negated
    phrasing such as "no conditions were imposed" is not distinguished from
    a genuine match — a documented limitation rather than a bug.
    """
    text = _collect_determination_text(merger).lower()
    return any(phrase in text for phrase in _CONDITION_PHRASES)


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


def phase_2_outcome(merger: dict) -> tuple:
    """Return ``(determination, date)`` for a Phase 2 review that has concluded.

    A ceased assessment ends the review without a formal determination, so the
    cessation itself is treated as the outcome (mirroring how stats.py's
    "recent determinations" handles ceased assessments). Returns ``(None, None)``
    while a matter is still in Phase 2. Shared by phase2.json's completed-matter
    cards and stats.json's Phase 2 outcome counts so the two can't drift.
    """
    determination = merger.get('phase_2_determination')
    determination_date = merger.get('phase_2_determination_date')
    if not determination and merger.get('status') == merger_status.ASSESSMENT_CEASED:
        determination = merger_status.ASSESSMENT_CEASED
        determination_date = merger.get('ceased_date')
    return determination, determination_date


def strip_event_status(merger: dict) -> dict:
    """Return a copy of ``merger`` with each event's 'status' key dropped.

    The event-level 'live'/'removed' flag is backend-only: it drives dedup in
    data/processed/mergers.json (detect_duplicates / resolver) and the scraper's
    merge cleanup, but nothing downstream of the source reads it. Keeping it out
    of the generated datasets avoids churning those committed files every time a
    document link drops off the ACCC register. The input merger is left
    unmutated because the same object feeds other outputs.
    """
    events = merger.get('events')
    if not events:
        return merger
    return {
        **merger,
        'events': [
            {k: v for k, v in event.items() if k != 'status'}
            for event in events
        ],
    }


# Fields carried by an enriched merger that no page on the site reads. They
# stay in data/output/mergers.json (the offline artifact, and the CLI bundle's
# source) and are dropped from the deployed per-merger files by
# :func:`slim_for_site`.
SITE_UNUSED_MERGER_FIELDS = frozenset({
    'accc_determination_raw',        # normalised into accc_determination
    'page_modified_datetime',        # register bookkeeping
    'public_benefits_determination',
    'public_benefits_determination_date',
})

SITE_UNUSED_EVENT_FIELDS = frozenset({
    'determination_commission_division',
    'phase2_notice_commission_division',
})

# The only determination-table rows the site renders. MergerDetail shows the
# ACCC's reasoning through DeterminationExplanationSection, which scans for a
# row whose label starts with one of these and renders its ``details``; the
# remaining rows (the parties, the acquisition, the determination itself) are
# already on the page as structured fields. The label is whitespace-collapsed
# before matching because it comes out of a PDF with layout newlines in it —
# the same normalisation findExplanationDetails applies in the browser.
RENDERED_DETERMINATION_ROWS = ('explanation for determination', 'reasons for determination')


def _is_rendered_determination_row(row) -> bool:
    if not isinstance(row, dict):
        return False
    item = row.get('item')
    if not isinstance(item, str):
        return False
    return re.sub(r'\s+', ' ', item).strip().lower().startswith(RENDERED_DETERMINATION_ROWS)


def slim_for_site(merger: dict) -> dict:
    """Return a copy of ``merger`` carrying only what the site renders.

    The deployed per-merger file is the merger detail page's payload and
    nothing else — ``data/output/mergers.json`` keeps the complete record for
    offline analysis and for the CLI bundle (generate-cli-data.sh), which
    indexes every determination row into its full-text search. So the deployed
    copy drops the fields no page reads and, from each event, the
    determination-table rows the page never renders. The input merger is left
    unmutated because the same object feeds other outputs.
    """
    slim = {k: v for k, v in merger.items() if k not in SITE_UNUSED_MERGER_FIELDS}

    events = slim.get('events')
    if not events:
        return slim

    slim_events = []
    for event in events:
        slim_event = {k: v for k, v in event.items() if k not in SITE_UNUSED_EVENT_FIELDS}
        rows = slim_event.get('determination_table_content')
        if isinstance(rows, list):
            kept = [row for row in rows if _is_rendered_determination_row(row)]
            if kept:
                slim_event['determination_table_content'] = kept
            else:
                del slim_event['determination_table_content']
        slim_events.append(slim_event)
    slim['events'] = slim_events
    return slim


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

    # Flag approvals granted subject to conditions (e.g. a s 87B undertaking
    # or divestiture) — normalize_determination collapses these to a bare
    # "Approved", so surface the distinction separately.
    m['has_conditions'] = (
        m['accc_determination'] == merger_status.APPROVED and detect_has_conditions(m)
    )

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
    phase_2_referral_date = None
    for event in m.get('events', []):
        if is_phase_2_referral_event(event.get('title', '')):
            phase_1_det = merger_status.REFERRED_TO_PHASE_2
            phase_1_det_date = event.get('date')
            phase_2_referral_date = event.get('date')
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

    # For ceased mergers, find the cessation event and treat it as a determination event.
    if m.get('status') == merger_status.ASSESSMENT_CEASED:
        for event in m.get('events', []):
            if 'ceased' in event.get('title', '').lower():
                m['ceased_date'] = event.get('date')
                event['is_determination_event'] = True
                break

    # Derive the Phase 2 end_of_determination_period after a referral.
    # The register issues the referral notice before refreshing the date
    # field, which meanwhile still holds the superseded Phase 1 deadline
    # (e.g. MN-05013), so the site would keep advertising a determination
    # due date that no longer exists. A genuine Phase 2 period ends ~90
    # business days after the referral while the leftover Phase 1 date sits
    # within days of it, so a period end before BD 45 of Phase 2 can only be
    # the stale Phase 1 date. That stale date pins down the real Phase 2
    # deadline: the Phase 2 clock runs for 90 business days counted from the
    # first business day after the Phase 1 determination was *due* — not
    # from the referral, which may land a few days early (verified against
    # MN-01072/MN-90009/MN-30002, whose published Phase 2 ends all equal
    # BD 90 from the day after their Phase 1 due dates). The derived value
    # is superseded once the register publishes its own Phase 2 date, which
    # also folds in any Phase 2 extensions.
    if phase_2_referral_date and m.get('end_of_determination_period'):
        try:
            referral_dt = parse_iso_datetime(phase_2_referral_date)
            period_end_dt = parse_iso_datetime(m['end_of_determination_period'])
            if referral_dt is not None and period_end_dt is not None:
                referral_dt = referral_dt.replace(tzinfo=None)
                period_end_dt = period_end_dt.replace(tzinfo=None)
                if period_end_dt < add_business_days(referral_dt, 45):
                    # add_business_days treats the first business day on or
                    # after its start as BD 1, so starting from the day after
                    # the Phase 1 due date lands BD 90 of Phase 2.
                    phase_2_end = add_business_days(period_end_dt + timedelta(days=1), 90)
                    m['end_of_determination_period'] = phase_2_end.strftime('%Y-%m-%dT12:00:00Z')
                    m['end_of_determination_period_derived'] = True
        except (ValueError, AttributeError):
            pass

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

    Each card carries only what the tile renders (see the "You might be
    interested in" block in MergerDetail.jsx): merger_id, merger_name, the
    names of the first 2 acquirers and targets, and one outcome label —
    accc_determination when the matter is decided, otherwise status. Party
    entries are bare name strings, not the full party dicts: identifiers and
    party_page links are never read here and each card would otherwise repeat
    them for up to 4 parties. Empty fields are omitted entirely.

    Returns the number of mergers that had at least one similar merger linked.
    """
    def _party_names(parties: list) -> list:
        return [p.get('name') for p in parties[:2] if p.get('name')]

    def _make_card(m: dict) -> dict:
        card = {
            'merger_id': m.get('merger_id'),
            'merger_name': m.get('merger_name'),
        }
        acquirers = _party_names(m.get('acquirers') or [])
        if acquirers:
            card['acquirers'] = acquirers
        targets = _party_names(m.get('targets') or [])
        if targets:
            card['targets'] = targets
        # The tile shows the determination when there is one and falls back to
        # the status, so only ever one of the two is worth carrying.
        if m.get('accc_determination'):
            card['accc_determination'] = m['accc_determination']
        elif m.get('status'):
            card['status'] = m['status']
        return card

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


def link_related_parties(enriched_mergers: list, party_groups: list) -> int:
    """Attach a ``canonical`` link to each party that belongs to a known group.

    ``party_groups`` is the list loaded from ``related_parties.json``. For every
    acquirer / target / other party whose name or ABN matches a group member, a
    ``canonical`` field ``{"id": ..., "name": ...}`` is added to the party dict
    in-place. The frontend turns this into a link to the mergers list filtered by
    the canonical name, and folds the canonical name into the search index so the
    filter surfaces every merger involving the same entity.

    Returns the number of party records that were linked.
    """
    if not party_groups:
        return 0

    by_identifier, by_name = build_group_lookups(party_groups)
    linked = 0
    for merger in enriched_mergers:
        for field in ('acquirers', 'targets', 'other_parties'):
            for party in merger.get(field) or []:
                group = match_party(party, by_identifier, by_name)
                if group:
                    party['canonical'] = {
                        'id': group.get('id'),
                        'name': group.get('canonical_name'),
                    }
                    linked += 1
    return linked


def _normalise_appeal_date(value: str | None) -> str | None:
    """Normalise a tribunal document date to the event datetime format.

    Tribunal dates are recorded as plain ``YYYY-MM-DD``; the merger event
    timeline uses ``YYYY-MM-DDT12:00:00Z``. A bare date is promoted to that
    form so appeal events sort and render alongside ACCC events; anything
    already carrying a time component is left untouched.
    """
    if not value:
        return value
    if len(value) == 10 and value[4] == '-' and value[7] == '-':
        return f"{value}T12:00:00Z"
    return value


def _normalise_appeal_filed_by(value: str | None) -> str:
    """Resolve a tribunal document's "filed by" to a display value.

    Tribunal matter pages leave the "filed by" column blank — or fill it with a
    placeholder dash — for documents the Tribunal itself issues (orders,
    directions, reasons). Those show up scraped as ``None``, an empty string or
    a lone dash. Treat any such value as filed by the Tribunal so the event
    timeline never shows a bare "–".
    """
    text = (value or '').strip()
    if not text or text.strip('-–—') == '':
        return 'Tribunal'
    return text


def _appeal_event(doc: dict, appeal: dict) -> dict:
    """Turn a tribunal appeal document into a merger timeline event."""
    description = doc.get('description') or 'Tribunal document'
    return {
        'date': _normalise_appeal_date(doc.get('date')),
        'title': description,
        'display_title': f"Tribunal appeal – {description}",
        'url': doc.get('url'),
        'url_gh': doc.get('url_gh'),
        # Flags the event as originating from the tribunal appeal rather than
        # the ACCC register, so the frontend can style/label it distinctly.
        'is_appeal': True,
        'appeal_filed_by': _normalise_appeal_filed_by(doc.get('filed_by')),
        'appeal_confidentiality': doc.get('confidentiality'),
        'tribunal_number': appeal.get('tribunal_number'),
        'phase': None,
    }


def link_tribunal_appeals(enriched_mergers: list, appeals: dict) -> int:
    """Attach Australian Competition Tribunal appeal data to mergers in-place.

    For every merger with an entry in ``appeals`` (keyed by merger_id):

      * ``appeal`` holds the full appeal record (tribunal number, tribunal URL,
        appeal type, appellant, lifecycle status, outcome, filed date and
        documents), so the tribunal link and filings stay visible on the detail
        page even after an appeal has finished;
      * ``under_appeal`` is set to ``True`` only while the appeal is *current*
        (see :func:`constants.tribunal.is_current_appeal`) — a concluded or
        withdrawn appeal leaves an appeal record but is not "under appeal", so
        the badge does not linger. This flag is propagated to the
        list/phase2/timeline outputs; and
      * each appeal document is folded into the merger's event timeline so the
        filings surface alongside ACCC events.

    The ACCC-scraped ``status`` / ``accc_determination`` fields are left
    untouched — the appeal is layered on top rather than replacing the
    underlying outcome. Returns the number of mergers linked.
    """
    if not appeals:
        return 0

    linked = 0
    for merger in enriched_mergers:
        mid = merger.get('merger_id', '')
        appeal = appeals.get(mid)
        if not appeal:
            continue

        status = appeal.get('status', tribunal.DEFAULT_APPEAL_STATUS)
        merger['under_appeal'] = tribunal.is_current_appeal(appeal)
        merger['appeal'] = {
            'tribunal_number': appeal.get('tribunal_number'),
            'tribunal_url': appeal.get('tribunal_url'),
            'appeal_type': appeal.get('appeal_type'),
            'appellant': appeal.get('appellant'),
            'status': status,
            'outcome': appeal.get('outcome'),
            # The ACCC-style determination that stands once the appeal is
            # decided — the same as the ACCC's when affirmed, the opposite when
            # set aside. Stored explicitly (never derived) and used to render an
            # appeal-aware status badge, e.g. "Approved · on appeal".
            'effective_determination': appeal.get('effective_determination'),
            'filed_date': appeal.get('filed_date'),
            # Scheduled tribunal hearing start date (bare 'YYYY-MM-DD', optional).
            # Surfaced as a future "Tribunal hearing" event while the appeal is
            # current — see static_data.outputs.upcoming_events and the frontend
            # TrackingContext.
            'hearing_date': appeal.get('hearing_date'),
            'concluded_date': appeal.get('concluded_date'),
            'documents': appeal.get('documents', []),
        }

        appeal_events = [_appeal_event(doc, appeal) for doc in appeal.get('documents', [])]
        if appeal_events:
            merger['events'] = list(merger.get('events') or []) + appeal_events

        linked += 1
    return linked


def link_judicial_reviews(enriched_mergers: list, judicial_reviews: dict) -> int:
    """Attach Federal Court judicial review data to mergers in-place.

    For every merger with an entry in ``judicial_reviews`` (keyed by
    merger_id), sets ``judicial_review`` to the review record (applicant,
    filed date, case number, case URL) so a link-out card to the court's
    Commonwealth Courts Portal case page can be rendered on the detail page.

    Unlike tribunal appeals, no documents are scraped or mirrored, and no
    lifecycle status is tracked — this is deliberately a much lighter overlay.
    Returns the number of mergers linked.
    """
    if not judicial_reviews:
        return 0

    linked = 0
    for merger in enriched_mergers:
        mid = merger.get('merger_id', '')
        review = judicial_reviews.get(mid)
        if not review:
            continue

        merger['judicial_review'] = {
            'applicant': review.get('applicant'),
            'filed_date': review.get('filed_date'),
            'case_number': review.get('case_number'),
            'case_url': review.get('case_url'),
        }
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
