"""Paginated timeline events + metadata file.

Writes:
  <output_dir>/timeline-page-{N}.json
  <output_dir>/timeline-meta.json
"""

import json
from pathlib import Path

from ..enrichment import extract_phase_from_event


def generate(mergers: list, output_dir: Path, page_size: int = 100) -> int:
    """Generate paginated timeline files. Returns number of pages written."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    events = []
    for m in mergers:
        merger_id = m['merger_id']
        merger_name = m['merger_name']
        merger_is_waiver = m.get('is_waiver', False)

        for event in m.get('events', []):
            title = event.get('title', '')
            events.append({
                "date": event.get('date'),
                "title": title,
                "display_title": event.get('display_title'),
                "url": event.get('url'),
                "url_gh": event.get('url_gh'),
                "status": event.get('status'),
                "merger_id": merger_id,
                "merger_name": merger_name,
                "phase": event.get('phase') or extract_phase_from_event(title),
                "is_waiver": merger_is_waiver,
            })

    # Sort by date ascending (oldest first, newest last).
    # New events always append to the last page, so only the last page file
    # changes per scrape run rather than cascading through all pages.
    events.sort(key=lambda x: x.get('date', ''))

    total_events = len(events)
    total_pages = (total_events + page_size - 1) // page_size

    for page_num in range(1, total_pages + 1):
        start_idx = (page_num - 1) * page_size
        end_idx = min(start_idx + page_size, total_events)
        page_data = {
            "events": events[start_idx:end_idx],
            "page": page_num,
            "page_size": page_size,
        }

        out_path = output_dir / f"timeline-page-{page_num}.json"
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(page_data, f, indent=2)

    meta_data = {
        "total": total_events,
        "page_size": page_size,
        "total_pages": total_pages,
    }
    meta_path = output_dir / "timeline-meta.json"
    with open(meta_path, 'w', encoding='utf-8') as f:
        json.dump(meta_data, f, indent=2)

    return total_pages
