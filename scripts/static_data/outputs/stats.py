"""Aggregated statistics — ``stats.json``."""

from collections import defaultdict
from statistics import median

from constants import merger_status

from ..durations import collect_phase_1_durations, collect_waiver_durations
from ..enrichment import is_phase_2_referral_event
from ..filters import filter_notifications, filter_waivers
from ..loaders import BACKWARD_REFILE_RELATIONSHIPS


def _as_event_datetime(value: str | None) -> str | None:
    """Promote a bare ``YYYY-MM-DD`` to the event datetime format.

    Tribunal dates are recorded as plain dates; padding them to midday UTC lets
    them sort cleanly against the ISO notification datetimes.
    """
    if value and len(value) == 10 and value[4] == '-' and value[7] == '-':
        return f"{value}T12:00:00Z"
    return value


def _appeal_filed_date(appeal: dict) -> str | None:
    """When the appeal was lodged with the tribunal.

    Both what the card labels "Appeal filed" and how it ranks among the recent
    cards, so it must be the application's own filing date rather than its
    latest activity — a document filed weeks later must neither move the stated
    filing date nor refloat a stale appeal to the top of the dashboard. Falls
    back to the earliest document date when the overlay records no
    ``filed_date``.
    """
    filed = appeal.get('filed_date')
    if not filed:
        doc_dates = [d.get('date') for d in appeal.get('documents', []) if d.get('date')]
        filed = min(doc_dates) if doc_dates else None
    return _as_event_datetime(filed)


def _appeal_card(merger: dict) -> dict | None:
    """A dashboard "recent activity" card for a merger's tribunal appeal.

    Returns ``None`` when the merger has no appeal. The card links to the merger
    detail page and carries the lifecycle fields the frontend needs to label it
    (under-appeal vs concluded, and the effective determination).
    """
    appeal = merger.get('appeal')
    if not appeal:
        return None
    filed_date = _appeal_filed_date(appeal)
    if not filed_date:
        return None
    return {
        "merger_id": merger['merger_id'],
        "merger_name": merger['merger_name'],
        "status": merger.get('status'),
        "accc_determination": merger.get('accc_determination'),
        # The lodgement date doubles as the sort key so the appeal interleaves
        # with notification cards by when it was filed, then ages off the
        # dashboard like any other card.
        "effective_notification_datetime": filed_date,
        # Same same-day tie-break as notification cards (see _merger_sort_key).
        "page_modified_datetime": merger.get('page_modified_datetime', ''),
        "is_appeal": True,
        "under_appeal": bool(merger.get('under_appeal')),
        "appeal_type": appeal.get('appeal_type'),
        "appeal_status": appeal.get('status'),
        "effective_determination": appeal.get('effective_determination'),
        "tribunal_number": appeal.get('tribunal_number'),
        # Displayed on the card as "Appeal filed".
        "appeal_date": filed_date,
    }


def generate(mergers: list) -> dict:
    """Return the stats.json payload for pre-enriched mergers."""
    notification_mergers = filter_notifications(mergers)
    waiver_mergers = filter_waivers(mergers)

    total_notifications = len(notification_mergers)
    total_waivers = len(waiver_mergers)
    total_conditional_approvals = sum(
        1 for m in mergers if m.get('has_conditions')
    )

    # By status (notifications only)
    by_status = defaultdict(int)
    for m in notification_mergers:
        status = m.get('status', 'Unknown')
        by_status[status] += 1

    # By Phase 1 determination (notifications only)
    # Use pre-enriched phase_1_determination which correctly identifies "Referred to phase 2"
    by_determination = defaultdict(int)
    for m in notification_mergers:
        det = m.get('phase_1_determination')
        if det:
            by_determination[det] += 1

    # By waiver determination
    by_waiver_determination = defaultdict(int)
    for m in waiver_mergers:
        det = m.get('accc_determination')
        if det:
            by_waiver_determination[det] += 1

    # Clearance rate: share of notifications with a published final
    # determination that were cleared (Approved / Not opposed) rather than
    # blocked (Not approved / Declined). Still-open matters are excluded from
    # both the numerator and denominator; determinations reached after a
    # Phase 2 referral are included once published, since accc_determination
    # holds the merger's final outcome regardless of which phase concluded it.
    cleared = not_cleared = 0
    for m in notification_mergers:
        det = m.get('accc_determination')
        if not (det and m.get('determination_publication_date')):
            continue
        if det in merger_status.CLEARED_DETERMINATIONS:
            cleared += 1
        elif det in merger_status.BLOCKED_DETERMINATIONS:
            not_cleared += 1
    clearance_total = cleared + not_cleared
    clearance_rate_data = {
        "cleared": cleared,
        "not_cleared": not_cleared,
        "total": clearance_total,
        "rate": round(cleared / clearance_total, 3) if clearance_total else None,
    }

    # Phase 1 durations (notifications only). Matters referred to Phase 2 are
    # measured to the referral date, not the later Phase 2 determination, so the
    # Phase 2 clock never inflates the Phase 1 figures.
    durations, business_durations = collect_phase_1_durations(notification_mergers)

    avg_duration = sum(durations) / len(durations) if durations else None
    median_duration = round(median(durations), 1) if durations else None

    avg_business = sum(business_durations) / len(business_durations) if business_durations else None
    median_business = round(median(business_durations), 1) if business_durations else None

    # Pre-compute percentile statistics for business days
    total_completed = len(business_durations)
    percentile_stats = None
    if total_completed > 0:
        day15_count = sum(1 for d in business_durations if d <= 15)
        day20_count = sum(1 for d in business_durations if d <= 20)
        day30_count = sum(1 for d in business_durations if d <= 30)

        percentile_stats = {
            "day15": {
                "count": day15_count,
                "percentage": round((day15_count / total_completed) * 100, 1),
            },
            "day20": {
                "count": day20_count,
                "percentage": round((day20_count / total_completed) * 100, 1),
            },
            "day30": {
                "count": day30_count,
                "percentage": round((day30_count / total_completed) * 100, 1),
            },
        }

    # Top industries (including waivers)
    industry_counts = defaultdict(int)
    for m in mergers:
        codes = m.get('anzsic_codes') or []
        for code in codes:
            industry_counts[code.get('name', 'Unknown')] += 1

    top_industries = [
        {"name": name, "count": count}
        for name, count in sorted(industry_counts.items(), key=lambda x: -x[1])[:10]
    ]

    # Recent mergers (include all but mark waivers). Tribunal appeals are folded
    # in as their own activity cards (see _appeal_card) so a freshly-lodged appeal
    # surfaces on the dashboard alongside recent notifications, ranked by its
    # filing date. A card slice of 12 is taken after merging the two streams.
    # Notification datetimes are stored at a nominal midday, so same-day
    # notifications all tie on effective_notification_datetime. Break the tie by
    # page_modified_datetime — the real register timestamp — so a merger that
    # lands later on the same day sorts above one added earlier, rather than
    # falling back to insertion (roughly name) order.
    def _merger_sort_key(x: dict) -> tuple:
        return (
            x.get('effective_notification_datetime') or '',
            x.get('page_modified_datetime') or '',
        )

    sorted_mergers = sorted(mergers, key=_merger_sort_key, reverse=True)
    merger_cards = [
        {
            "merger_id": m['merger_id'],
            "merger_name": m['merger_name'],
            "status": m.get('status'),
            "accc_determination": m.get('accc_determination'),
            "effective_notification_datetime": m.get('effective_notification_datetime'),
            "page_modified_datetime": m.get('page_modified_datetime', ''),
            "is_waiver": m.get('is_waiver', False),
            "is_refiled": (m.get('related_merger') or {}).get('relationship') in BACKWARD_REFILE_RELATIONSHIPS,
        }
        for m in sorted_mergers[:12]
    ]
    appeal_cards = [card for card in (_appeal_card(m) for m in mergers) if card]
    recent_mergers = sorted(
        merger_cards + appeal_cards,
        key=_merger_sort_key,
        reverse=True,
    )[:12]

    # Recent determinations (approvals, declines, stage transitions)
    determination_events = []

    for m in mergers:
        merger_id = m['merger_id']
        merger_name = m['merger_name']
        is_waiver = m.get('is_waiver', False)

        # Check for final determination
        det = m.get('accc_determination')
        det_date = m.get('determination_publication_date')
        page_modified = m.get('page_modified_datetime', '')
        if det and det_date:
            determination_events.append({
                "merger_id": merger_id,
                "merger_name": merger_name,
                "determination": det,
                "determination_date": det_date,
                "page_modified_datetime": page_modified,
                "determination_type": "final",
                "is_waiver": is_waiver,
                "stage": m.get('stage'),
            })

        # Check for Phase 2 referrals (stage transitions)
        for event in m.get('events', []):
            if is_phase_2_referral_event(event.get('title', '')):
                determination_events.append({
                    "merger_id": merger_id,
                    "merger_name": merger_name,
                    "determination": merger_status.REFERRED_TO_PHASE_2,
                    "determination_date": event.get('date'),
                    "page_modified_datetime": page_modified,
                    "determination_type": "phase_transition",
                    "is_waiver": is_waiver,
                    "stage": "Phase 2 - detailed assessment",
                })
                break

        # Check for ceased assessments
        ceased_date = m.get('ceased_date')
        if m.get('status') == merger_status.ASSESSMENT_CEASED and ceased_date:
            determination_events.append({
                "merger_id": merger_id,
                "merger_name": merger_name,
                "determination": merger_status.ASSESSMENT_CEASED,
                "determination_date": ceased_date,
                "page_modified_datetime": page_modified,
                "determination_type": "ceased",
                "is_waiver": is_waiver,
                "stage": m.get('stage'),
            })

    # Sort by determination date descending, then by page modification time descending
    # This ensures determinations on the same day are sorted by the time they were added to the register
    determination_events.sort(
        key=lambda x: (x.get('determination_date', ''), x.get('page_modified_datetime', '')),
        reverse=True,
    )
    recent_determinations = determination_events[:12]

    # Build phase_duration object with pre-computed stats
    phase_duration_data = {
        "average_days": avg_duration,
        "median_days": median_duration,
        "average_business_days": avg_business,
        "median_business_days": median_business,
    }
    if percentile_stats:
        phase_duration_data["percentiles"] = percentile_stats

    # Waiver durations (notification → determination publication) for the
    # all-mergers baseline the industry/party pages compare against.
    waiver_cal, waiver_business = collect_waiver_durations(waiver_mergers)
    waiver_duration_data = {
        "average_days": sum(waiver_cal) / len(waiver_cal) if waiver_cal else None,
        "median_days": round(median(waiver_cal), 1) if waiver_cal else None,
        "average_business_days": (
            sum(waiver_business) / len(waiver_business) if waiver_business else None
        ),
        "median_business_days": round(median(waiver_business), 1) if waiver_business else None,
    }

    return {
        "total_mergers": total_notifications,
        "total_waivers": total_waivers,
        "total_conditional_approvals": total_conditional_approvals,
        "by_status": dict(by_status),
        "by_determination": dict(by_determination),
        "by_waiver_determination": dict(by_waiver_determination),
        "clearance_rate": clearance_rate_data,
        "phase_duration": phase_duration_data,
        "waiver_duration": waiver_duration_data,
        "top_industries": top_industries,
        "recent_mergers": recent_mergers,
        "recent_determinations": recent_determinations,
    }
