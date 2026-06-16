"""Industries index + per-industry merger files.

``generate_index`` returns the ``industries.json`` payload.
``generate_detail_files`` writes one file per industry code into
``<output_dir>/industries/{code}.json``.
"""

import json
from collections import defaultdict
from pathlib import Path

from constants import merger_status


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


def _industry_stats(unique_mergers: list) -> dict:
    """Compute the per-industry stat counts shared by index and detail files."""
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
    """Return the industries.json payload (codes, counts + a stat breakdown)."""
    # Group unique mergers by (code, name). Dedupe by merger_id so a merger
    # tagged with the same code twice isn't counted more than once.
    industry_mergers = defaultdict(dict)  # key -> {merger_id: merger}
    all_merger_ids = set()

    for m in mergers:
        merger_id = m['merger_id']
        codes = m.get('anzsic_codes') or m.get('anszic_codes') or []
        for code in codes:
            key = (code.get('code', ''), code.get('name', ''))
            industry_mergers[key][merger_id] = m
            all_merger_ids.add(merger_id)

    industries = [
        {
            "code": code,
            "name": name,
            "merger_count": len(merger_map),
            **_industry_stats(list(merger_map.values())),
        }
        for (code, name), merger_map in industry_mergers.items()
    ]

    # Sort by merger count descending
    industries.sort(key=lambda x: -x['merger_count'])

    return {
        "industries": industries,
        # Number of distinct mergers tagged to at least one industry. The
        # frontend can't derive this by summing merger_count because a merger
        # spanning N industries would be counted N times.
        "total_mergers": len(all_merger_ids),
        "total_industries": len(industries),
    }


def generate_detail_files(mergers: list, output_dir: Path) -> int:
    """Write one JSON file per industry code. Returns the number of industries written."""
    industries_dir = Path(output_dir) / "industries"
    industries_dir.mkdir(parents=True, exist_ok=True)

    # Group mergers by industry, deduping by merger_id within each industry.
    industry_mergers_map = defaultdict(dict)  # code -> {merger_id: summary}
    # Keep the full enriched record alongside so we can compute stats.
    industry_full_map = defaultdict(dict)  # code -> {merger_id: merger}

    for m in mergers:
        merger_id = m.get('merger_id')
        merger_name = m.get('merger_name')
        status = m.get('status')
        is_waiver = m.get('is_waiver', False)
        phase = classify_phase(m)
        determination_date = m.get('determination_publication_date') or ''
        notification_date = m.get('effective_notification_datetime') or ''

        codes = m.get('anzsic_codes') or m.get('anszic_codes') or []
        for code_obj in codes:
            code = code_obj.get('code', '')

            if code:  # Only add if code exists
                merger_summary = {
                    "merger_id": merger_id,
                    "merger_name": merger_name,
                    "is_waiver": is_waiver,
                    "status": status,
                    "phase": phase,
                    # Internal field for sorting only (not displayed)
                    "_latest_date": max(determination_date, notification_date),
                }
                # Use code as key (name can vary). Last write wins on dupes.
                industry_mergers_map[code][merger_id] = merger_summary
                industry_full_map[code][merger_id] = m

    for code, merger_map in industry_mergers_map.items():
        industry_mergers = list(merger_map.values())

        # Sort by most recent date (determination or notification)
        industry_mergers.sort(key=lambda x: x.get('_latest_date', ''), reverse=True)

        # Remove internal sorting field before output
        for merger in industry_mergers:
            merger.pop('_latest_date', None)

        output_data = {
            "code": code,
            "mergers": industry_mergers,
            "count": len(industry_mergers),
            **_industry_stats(list(industry_full_map[code].values())),
        }

        safe_code = code.replace('/', '-').replace('\\', '-')
        out_path = industries_dir / f"{safe_code}.json"

        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2)

    return len(industry_mergers_map)
