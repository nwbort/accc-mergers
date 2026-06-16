"""Industries index + per-industry merger files.

``generate_index`` returns the ``industries.json`` payload.
``generate_detail_files`` writes one file per industry code into
``<output_dir>/industries/{code}.json``.
"""

import json
from collections import defaultdict
from pathlib import Path

from constants import merger_status

from ..business_days import calculate_business_days, calculate_calendar_days
from ..filters import filter_notifications


def classify_phase(m: dict) -> str:
    """Bucket a merger into Phase 2 / Phase 1 / Waiver.

    Mirrors the Phase/Waiver split used on the Mergers page: waivers first,
    then anything currently in Phase 2, with everything else treated as
    Phase 1. Returns one of ``merger_status.WAIVER``/``PHASE_2``/``PHASE_1``.
    """
    if m.get('is_waiver'):
        return merger_status.WAIVER
    stage = m.get('stage') or ''
    if merger_status.PHASE_2 in stage:
        return merger_status.PHASE_2
    return merger_status.PHASE_1


def is_active(m: dict) -> bool:
    """Whether the review is still open (under assessment / suspended)."""
    return m.get('status') in (
        merger_status.UNDER_ASSESSMENT,
        merger_status.ASSESSMENT_SUSPENDED,
    )


def _avg(values: list):
    return sum(values) / len(values) if values else None


def _median(values: list):
    return sorted(values)[len(values) // 2] if values else None


def _phase_duration(unique_mergers: list) -> dict | None:
    """Phase 1 duration stats for an industry, mirroring the dashboard stats.

    Measures notification → determination for completed notification (non-waiver)
    mergers. Returns ``None`` when the industry has no completed Phase 1 reviews.
    """
    durations = []
    business_durations = []

    for m in filter_notifications(unique_mergers):
        start = m.get('effective_notification_datetime')
        end = m.get('determination_publication_date')
        if not (start and end):
            continue
        cal_days = calculate_calendar_days(start, end)
        if cal_days is not None:
            durations.append(cal_days)
        bus_days = calculate_business_days(start, end)
        if bus_days is not None:
            business_durations.append(bus_days)

    if not durations and not business_durations:
        return None

    return {
        "average_days": _avg(durations),
        "median_days": _median(durations),
        "average_business_days": _avg(business_durations),
        "median_business_days": _median(business_durations),
        "completed_count": len(business_durations),
    }


def _industry_stats(unique_mergers: list) -> dict:
    """Compute the per-industry stat counts shown on the detail page."""
    phase_2 = sum(1 for m in unique_mergers if classify_phase(m) == merger_status.PHASE_2)
    waivers = sum(1 for m in unique_mergers if classify_phase(m) == merger_status.WAIVER)
    phase_1 = len(unique_mergers) - phase_2 - waivers
    active = sum(1 for m in unique_mergers if is_active(m))
    return {
        "phase_1_count": phase_1,
        "phase_2_count": phase_2,
        "waiver_count": waivers,
        "active_count": active,
    }


def generate_index(mergers: list) -> dict:
    """Return the industries.json payload (codes + merger counts)."""
    # Group unique mergers by (code, name). Dedupe by merger_id so a merger
    # tagged with the same code twice isn't counted more than once.
    industry_mergers = defaultdict(set)  # key -> {merger_id}
    all_merger_ids = set()

    for m in mergers:
        merger_id = m['merger_id']
        codes = m.get('anzsic_codes') or m.get('anszic_codes') or []
        for code in codes:
            key = (code.get('code', ''), code.get('name', ''))
            industry_mergers[key].add(merger_id)
            all_merger_ids.add(merger_id)

    industries = [
        {
            "code": code,
            "name": name,
            "merger_count": len(merger_ids),
        }
        for (code, name), merger_ids in industry_mergers.items()
    ]

    # Sort by merger count descending
    industries.sort(key=lambda x: -x['merger_count'])

    return {
        "industries": industries,
        # Number of distinct mergers tagged to at least one industry. Used as
        # the denominator for each industry's "share" so it reflects the share
        # of all mergers (shares may sum to >100% since mergers span industries).
        "total_mergers": len(all_merger_ids),
        "total_industries": len(industries),
    }


def _sort_mergers(records: list) -> list:
    """Order an industry's mergers for display.

    Open reviews (under assessment / suspended) come first, most recently
    notified first. Concluded reviews follow, most recent decision first.
    ``records`` is a list of ``(summary, full_merger)`` tuples.
    """
    active = [r for r in records if is_active(r[1])]
    decided = [r for r in records if not is_active(r[1])]
    active.sort(key=lambda r: r[1].get('effective_notification_datetime') or '', reverse=True)
    decided.sort(key=lambda r: r[1].get('determination_publication_date') or '', reverse=True)
    return [summary for summary, _ in active + decided]


def generate_detail_files(mergers: list, output_dir: Path) -> int:
    """Write one JSON file per industry code. Returns the number of industries written."""
    industries_dir = Path(output_dir) / "industries"
    industries_dir.mkdir(parents=True, exist_ok=True)

    # Group mergers by industry, deduping by merger_id within each industry.
    # code -> {merger_id: (summary, full_merger)}
    industry_map = defaultdict(dict)

    for m in mergers:
        merger_id = m.get('merger_id')
        summary = {
            "merger_id": merger_id,
            "merger_name": m.get('merger_name'),
            "is_waiver": m.get('is_waiver', False),
            "status": m.get('status'),
            "phase": classify_phase(m),
        }

        codes = m.get('anzsic_codes') or m.get('anszic_codes') or []
        for code_obj in codes:
            code = code_obj.get('code', '')
            if code:  # Only add if code exists
                industry_map[code][merger_id] = (summary, m)

    for code, records in industry_map.items():
        record_list = list(records.values())
        full_mergers = [full for _, full in record_list]

        output_data = {
            "code": code,
            "mergers": _sort_mergers(record_list),
            "count": len(record_list),
            **_industry_stats(full_mergers),
            "phase_duration": _phase_duration(full_mergers),
        }

        safe_code = code.replace('/', '-').replace('\\', '-')
        out_path = industries_dir / f"{safe_code}.json"

        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2)

    return len(industry_map)
