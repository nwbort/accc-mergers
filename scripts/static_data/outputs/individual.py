"""Write one JSON file per merger into ``<output_dir>/mergers/{merger_id}.json``."""

import json
from pathlib import Path


def _strip_event_status(merger: dict) -> dict:
    """Return a copy of ``merger`` with event-level 'status' dropped.

    The 'live'/'removed' status is backend-only: it drives dedup in
    data/processed/mergers.json but the frontend never reads it. Emitting it
    here would churn this file every time a document link drops off the ACCC
    register, so it is stripped from the deployed UI copy. The input merger is
    left unmutated because the same object feeds other outputs.
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
                json.dump(_strip_event_status(merger), f, indent=2)
            count += 1
    return count
