#!/usr/bin/env python3
"""
Generate an RSS feed (Atom format) of recent merger activity.

Produces an Atom XML feed of the most recent merger events (determinations,
notifications, phase transitions) for consumption by RSS readers.

Output:
  merger-tracker/frontend/public/feed.xml
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape

SCRIPT_DIR = Path(__file__).parent
REPO_ROOT = SCRIPT_DIR.parent
MERGERS_JSON = REPO_ROOT / "data" / "processed" / "mergers.json"
OUTPUT_PATH = REPO_ROOT / "merger-tracker" / "frontend" / "public" / "feed.xml"

SITE_URL = "https://mergers.fyi"
FEED_TITLE = "Australian Merger Tracker"
FEED_SUBTITLE = "Recent ACCC merger notifications, determinations, and review events"
AUTHOR_NAME = "Nick Twort"
MAX_ITEMS = 50


def load_mergers():
    """Load mergers from the processed JSON file."""
    with open(MERGERS_JSON, 'r', encoding='utf-8') as f:
        data = json.load(f)

    if isinstance(data, list):
        return data
    elif isinstance(data, dict) and 'mergers' in data:
        return data['mergers']
    else:
        raise ValueError("Unexpected mergers.json format")


def collect_feed_entries(mergers: list) -> list:
    """Collect all events from mergers and return as feed entries."""
    entries = []

    for m in mergers:
        merger_id = m.get('merger_id', '')
        merger_name = m.get('merger_name', '')
        merger_url = f"{SITE_URL}/mergers/{merger_id}"

        for event in m.get('events', []):
            date = event.get('date')
            title = event.get('display_title') or event.get('title', '')
            if not date or not title:
                continue

            entries.append({
                "title": f"{merger_name}: {title}",
                "link": merger_url,
                "id": f"{merger_url}#{date}-{title[:50]}",
                "updated": date,
                "summary": f"Merger: {merger_name} ({merger_id}). Event: {title}.",
            })

    # Sort by date descending, take the most recent
    entries.sort(key=lambda e: e['updated'], reverse=True)
    return entries[:MAX_ITEMS]


def generate_atom_xml(entries: list) -> str:
    """Generate an Atom XML feed string."""
    now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    feed_updated = entries[0]['updated'] if entries else now

    # Ensure feed_updated is a full ISO timestamp
    if len(feed_updated) == 10:
        feed_updated += 'T12:00:00Z'

    lines = [
        '<?xml version="1.0" encoding="utf-8"?>',
        '<feed xmlns="http://www.w3.org/2005/Atom">',
        f'  <title>{escape(FEED_TITLE)}</title>',
        f'  <subtitle>{escape(FEED_SUBTITLE)}</subtitle>',
        f'  <link href="{SITE_URL}/feed.xml" rel="self" type="application/atom+xml"/>',
        f'  <link href="{SITE_URL}" rel="alternate" type="text/html"/>',
        f'  <id>{SITE_URL}/</id>',
        f'  <updated>{feed_updated}</updated>',
        f'  <author><name>{escape(AUTHOR_NAME)}</name></author>',
        f'  <generator>Australian Merger Tracker</generator>',
    ]

    for entry in entries:
        entry_updated = entry['updated']
        if len(entry_updated) == 10:
            entry_updated += 'T12:00:00Z'

        lines.extend([
            '  <entry>',
            f'    <title>{escape(entry["title"])}</title>',
            f'    <link href="{escape(entry["link"])}"/>',
            f'    <id>{escape(entry["id"])}</id>',
            f'    <updated>{entry_updated}</updated>',
            f'    <summary>{escape(entry["summary"])}</summary>',
            '  </entry>',
        ])

    lines.append('</feed>')
    return '\n'.join(lines) + '\n'


def main():
    print("Loading mergers.json...")
    mergers = load_mergers()
    print(f"Loaded {len(mergers)} mergers")

    print("Collecting feed entries...")
    entries = collect_feed_entries(mergers)
    print(f"Collected {len(entries)} entries for feed")

    print("Generating Atom XML...")
    xml = generate_atom_xml(entries)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        f.write(xml)

    print(f"✓ Generated {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
