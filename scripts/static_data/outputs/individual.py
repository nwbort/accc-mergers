"""Write one JSON file per merger into ``<output_dir>/mergers/{merger_id}.json``."""

import json
from pathlib import Path

from ..enrichment import strip_event_status
from ..prune import prune_stale_files

# ``mergers/`` also holds the paginated list written by :mod:`.list`; those
# files belong to that generator and are never pruned from here.
LIST_FILES = ("list-page-*.json", "list-meta.json")


def generate(mergers: list, output_dir: Path) -> int:
    """Write individual merger detail JSON files. Returns count written.

    Detail files for mergers that are no longer in the data set (deduped away,
    or dropped from the register) are pruned.
    """
    mergers_dir = Path(output_dir) / "mergers"
    mergers_dir.mkdir(parents=True, exist_ok=True)

    written: set[str] = set()
    for merger in mergers:
        merger_id = merger.get('merger_id', '')
        if merger_id:
            out_path = mergers_dir / f"{merger_id}.json"
            with open(out_path, 'w', encoding='utf-8') as f:
                json.dump(strip_event_status(merger), f, indent=2)
            written.add(out_path.name)

    prune_stale_files(mergers_dir, written, exclude=LIST_FILES, label="mergers")

    return len(written)
