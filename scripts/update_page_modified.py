#!/usr/bin/env python3
"""
Simple script to extract dcterms.modified from HTML files and update mergers.json.
This adds the page_modified_datetime field without requiring all dependencies.
"""

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
MERGERS_JSON = REPO_ROOT / "data" / "processed" / "mergers.json"
HTML_DIR = REPO_ROOT / "data" / "raw" / "matters"

def extract_dcterms_modified(html_path):
    """Extract dcterms.modified from HTML file."""
    try:
        with open(html_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Search for <meta name="dcterms.modified" content="..." />
        match = re.search(r'<meta\s+name="dcterms\.modified"\s+content="([^"]+)"\s*/>', content)
        if match:
            return match.group(1)
    except Exception as e:
        print(f"Error reading {html_path}: {e}")
    return None

def main():
    """Update mergers.json with page_modified_datetime field."""
    print("Loading mergers.json...")
    with open(MERGERS_JSON, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Handle both formats
    if isinstance(data, list):
        mergers = data
    elif isinstance(data, dict) and 'mergers' in data:
        mergers = data['mergers']
    else:
        raise ValueError("Unexpected mergers.json format")

    print(f"Processing {len(mergers)} mergers...")
    updated_count = 0

    for merger in mergers:
        merger_id = merger.get('merger_id')
        if not merger_id:
            continue

        html_path = HTML_DIR / f"{merger_id}.html"
        if not html_path.exists():
            continue

        modified_time = extract_dcterms_modified(html_path)
        if modified_time:
            merger['page_modified_datetime'] = modified_time
            updated_count += 1

    print(f"Updated {updated_count} mergers with page_modified_datetime")

    # Save back to file
    print("Saving updated mergers.json...")
    with open(MERGERS_JSON, 'w', encoding='utf-8') as f:
        json.dump(mergers, f, indent=2)

    print("Done!")

if __name__ == "__main__":
    main()
