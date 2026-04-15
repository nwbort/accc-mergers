"""Industries index + per-industry merger files.

``generate_index`` returns the ``industries.json`` payload.
``generate_detail_files`` writes one file per industry code into
``<output_dir>/industries/{code}.json``.
"""

import json
from collections import defaultdict
from pathlib import Path


def generate_index(mergers: list) -> dict:
    """Return the industries.json payload (codes + merger counts)."""
    # Group by (code, name) to count unique mergers
    industry_mergers = defaultdict(set)

    for m in mergers:
        merger_id = m['merger_id']
        codes = m.get('anzsic_codes') or m.get('anszic_codes') or []
        for code in codes:
            key = (code.get('code', ''), code.get('name', ''))
            industry_mergers[key].add(merger_id)

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

    return {"industries": industries}


def generate_detail_files(mergers: list, output_dir: Path) -> int:
    """Write one JSON file per industry code. Returns the number of industries written."""
    industries_dir = Path(output_dir) / "industries"
    industries_dir.mkdir(parents=True, exist_ok=True)

    # Group mergers by industry
    industry_mergers_map = defaultdict(list)

    for m in mergers:
        merger_id = m.get('merger_id')
        merger_name = m.get('merger_name')
        status = m.get('status')
        is_waiver = m.get('is_waiver', False)
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
                    # Internal field for sorting only (not displayed)
                    "_latest_date": max(determination_date, notification_date),
                }
                # Use code as key (name can vary)
                industry_mergers_map[code].append(merger_summary)

    for code, industry_mergers in industry_mergers_map.items():
        # Sort by most recent date (determination or notification)
        industry_mergers.sort(key=lambda x: x.get('_latest_date', ''), reverse=True)

        # Remove internal sorting field before output
        for merger in industry_mergers:
            merger.pop('_latest_date', None)

        output_data = {
            "code": code,
            "mergers": industry_mergers,
            "count": len(industry_mergers),
        }

        safe_code = code.replace('/', '-').replace('\\', '-')
        out_path = industries_dir / f"{safe_code}.json"

        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2)

    return len(industry_mergers_map)
