"""Pre-computed analysis data for the Analysis page — ``analysis.json``."""

from collections import defaultdict
from statistics import median as stat_median

from constants import merger_status

from ..business_days import calculate_business_days, calculate_calendar_days
from ..filters import filter_notifications, filter_waivers


def generate(mergers: list) -> dict:
    """Return the analysis.json payload for pre-enriched mergers."""
    notification_mergers = filter_notifications(mergers)
    waiver_mergers = filter_waivers(mergers)

    # --- Phase 1 duration analysis (notifications only) ---
    phase1_scatter = []
    phase1_business_days = []

    for m in notification_mergers:
        start = m.get('effective_notification_datetime')
        end = m.get('determination_publication_date')
        phase_1_det = m.get('phase_1_determination')

        if not start:
            continue

        # Include 'Referred to phase 2' mergers using the date the phase 2 notice was issued
        if not end:
            if phase_1_det == merger_status.REFERRED_TO_PHASE_2 and m.get('phase_1_determination_date'):
                end = m['phase_1_determination_date']
            else:
                continue

        bus_days = calculate_business_days(start, end)
        cal_days = calculate_calendar_days(start, end)
        if bus_days is None:
            continue

        in_progress = m.get('determination_publication_date') is None
        if not in_progress:
            phase1_business_days.append(bus_days)
        phase1_scatter.append({
            "notification_date": start[:10],
            "business_days": bus_days,
            "calendar_days": cal_days,
            "merger_name": m.get('merger_name'),
            "merger_id": m.get('merger_id'),
            "determination": phase_1_det,
            "in_progress": in_progress,
        })

    phase1_scatter.sort(key=lambda x: x['notification_date'])

    phase1_stats = {}
    if phase1_business_days:
        phase1_stats = {
            "average": round(sum(phase1_business_days) / len(phase1_business_days), 1),
            "median": stat_median(phase1_business_days),
            "min": min(phase1_business_days),
            "max": max(phase1_business_days),
            "count": len(phase1_business_days),
        }

    # --- Waiver duration analysis ---
    waiver_scatter = []
    waiver_business_days = []

    for m in waiver_mergers:
        start = m.get('effective_notification_datetime')
        end = m.get('determination_publication_date')
        if not start or not end:
            continue

        bus_days = calculate_business_days(start, end)
        cal_days = calculate_calendar_days(start, end)
        if bus_days is None:
            continue

        waiver_business_days.append(bus_days)
        waiver_scatter.append({
            "application_date": start[:10],
            "business_days": bus_days,
            "calendar_days": cal_days,
            "merger_name": m.get('merger_name'),
            "merger_id": m.get('merger_id'),
            "determination": m.get('accc_determination'),
        })

    waiver_scatter.sort(key=lambda x: x['application_date'])

    waiver_stats = {}
    if waiver_business_days:
        waiver_stats = {
            "average": round(sum(waiver_business_days) / len(waiver_business_days), 1),
            "median": stat_median(waiver_business_days),
            "min": min(waiver_business_days),
            "max": max(waiver_business_days),
            "count": len(waiver_business_days),
        }

    # --- Monthly notification volume ---
    monthly_counts = defaultdict(lambda: {"notifications": 0, "waivers": 0})
    for m in mergers:
        start = m.get('effective_notification_datetime')
        if not start:
            continue
        month_key = start[:7]  # YYYY-MM
        if m.get('is_waiver', False):
            monthly_counts[month_key]["waivers"] += 1
        else:
            monthly_counts[month_key]["notifications"] += 1

    sorted_months = sorted(monthly_counts.keys())
    monthly_volume = {
        "labels": sorted_months,
        "notifications": [monthly_counts[m]["notifications"] for m in sorted_months],
        "waivers": [monthly_counts[m]["waivers"] for m in sorted_months],
    }

    return {
        "phase1_duration": {
            "scatter_data": phase1_scatter,
            "stats": phase1_stats,
        },
        "waiver_duration": {
            "scatter_data": waiver_scatter,
            "stats": waiver_stats,
        },
        "monthly_volume": monthly_volume,
    }
