"""Individual NOCC (Notice of Competition Concerns) summary JSON files for
lazy loading by the frontend.

Writes one ``<output_dir>/noccs/{merger_id}.json`` per merger that has a
parsed NOCC summary.
"""

import json
from pathlib import Path


def _nocc_record(data: dict) -> dict:
    return {
        'title': data.get('title'),
        'matter_id': data.get('matter_id'),
        'document_type': data.get('document_type'),
        'date': data.get('date'),
        'date_iso': data.get('date_iso'),
        'file_name': data.get('file_name'),
        'file_path': data.get('file_path'),
        'sections': data.get('sections', []),
    }


def generate(nocc_data: dict, output_dir: Path) -> int:
    """Write individual NOCC files. Returns count written."""
    noccs_dir = Path(output_dir) / "noccs"
    noccs_dir.mkdir(parents=True, exist_ok=True)

    count = 0
    for merger_id, data in nocc_data.items():
        # Skip error entries (which contain only ``error`` and ``file_path``).
        if not data.get('sections'):
            continue

        output = _nocc_record(data)

        # When a matter has multiple distinct NOCC summaries (e.g. a re-issue),
        # include them all sorted latest-first so consumers can access older
        # versions.
        all_noccs = data.get('all_noccs', [])
        if len(all_noccs) > 1:
            output['all_noccs'] = [
                _nocc_record(n) for n in all_noccs if n.get('sections')
            ]

        out_path = noccs_dir / f"{merger_id}.json"
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2)
        count += 1

    return count
