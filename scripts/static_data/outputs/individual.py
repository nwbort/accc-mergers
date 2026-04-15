"""Write one JSON file per merger into ``<output_dir>/mergers/{merger_id}.json``."""

import json
from pathlib import Path


def generate(mergers: list, output_dir: Path) -> int:
    """Write individual merger detail JSON files. Returns count written."""
    mergers_dir = Path(output_dir) / "mergers"
    mergers_dir.mkdir(parents=True, exist_ok=True)

    count = 0
    for merger in mergers:
        merger_id = merger.get('merger_id', '')
        if merger_id:
            out_path = mergers_dir / f"{merger_id}.json"
            with open(out_path, 'w', encoding='utf-8') as f:
                json.dump(merger, f, indent=2)
            count += 1
    return count
