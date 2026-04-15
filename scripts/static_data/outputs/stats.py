"""Aggregated statistics — ``stats.json``."""

from collections import defaultdict

from constants import merger_status

from ..business_days import calculate_business_days, calculate_calendar_days
from ..filters import filter_notifications, filter_waivers


def generate(mergers: list) -> dict:
    """Return the stats.json payload for pre-enriched mergers."""
    notification_mergers = filter_notifications(mergers)
    waiver_mergers = filter_waivers(mergers)

    total_notifications = len(notification_mergers)
    total_waivers = len(waiver_mergers)

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

    # Phase durations (notifications only)
    durations = []
    business_durations = []

    for m in notification_mergers:
        start = m.get('effective_notification_datetime')
        end = m.get('determination_publication_date')

        if start and end:
            cal_days = calculate_calendar_days(start, end)
            if cal_days is not None:
                durations.append(cal_days)

            bus_days = calculate_business_days(start, end)
            if bus_days is not None:
                business_durations.append(bus_days)

    avg_duration = sum(durations) / len(durations) if durations else None
    median_duration = sorted(durations)[len(durations) // 2] if durations else None

    avg_business = sum(business_durations) / len(business_durations) if business_durations else None
    median_business = sorted(business_durations)[len(business_durations) // 2] if business_durations else None

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
        codes = m.get('anzsic_codes') or m.get('anszic_codes') or []
        for code in codes:
            industry_counts[code.get('name', 'Unknown')] += 1

    top_industries = [
        {"name": name, "count": count}
        for name, count in sorted(industry_counts.items(), key=lambda x: -x[1])[:10]
    ]

    # Recent mergers (include all but mark waivers)
    sorted_mergers = sorted(
        mergers,
        key=lambda x: x.get('effective_notification_datetime', ''),
        reverse=True,
    )
    recent_mergers = [
        {
            "merger_id": m['merger_id'],
            "merger_name": m['merger_name'],
            "status": m.get('status'),
            "accc_determination": m.get('accc_determination'),
            "effective_notification_datetime": m.get('effective_notification_datetime'),
            "is_waiver": m.get('is_waiver', False),
        }
        for m in sorted_mergers[:5]
    ]

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
            title = event.get('title', '')
            if 'subject to Phase 2 review' in title:
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

    # Sort by determination date descending, then by page modification time descending
    # This ensures determinations on the same day are sorted by the time they were added to the register
    determination_events.sort(
        key=lambda x: (x.get('determination_date', ''), x.get('page_modified_datetime', '')),
        reverse=True,
    )
    recent_determinations = determination_events[:6]

    # Build phase_duration object with pre-computed stats
    phase_duration_data = {
        "average_days": avg_duration,
        "median_days": median_duration,
        "average_business_days": avg_business,
        "median_business_days": median_business,
    }
    if percentile_stats:
        phase_duration_data["percentiles"] = percentile_stats

    return {
        "total_mergers": total_notifications,
        "total_waivers": total_waivers,
        "by_status": dict(by_status),
        "by_determination": dict(by_determination),
        "by_waiver_determination": dict(by_waiver_determination),
        "phase_duration": phase_duration_data,
        "top_industries": top_industries,
        "recent_mergers": recent_mergers,
        "recent_determinations": recent_determinations,
    }
