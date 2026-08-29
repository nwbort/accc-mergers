"""Decide which register matter pages the scraper should fetch.

The ACCC register listing is paginated at 50 rows per page over a sort that
is not stable across requests: scrape.sh fetches each page as its own HTTP
request, and rows that tie on the sort key can move between those requests.
The result is that one crawl serves the same matter on two adjacent pages
and silently drops another. Observed live on a 12-page crawl: 554 rows
served, 550 distinct, 4 matters missing from the listing entirely even
though their pages were still online.

A matter that falls out of the listing is never re-fetched, so its saved
HTML in data/raw/matters/ — and every field extract_mergers.py derives from
it — stays frozen at whatever the last successful crawl happened to see.
That is invisible in the output: the record simply keeps reporting a stale
status forever.

To close the gap, the listing links are unioned with the URL paths of
matters already recorded in mergers.json that are still active under the
cutoff rules. A matter the listing drops is then recovered from what we
already know about it, and only genuinely new matters depend on the listing.

Comparisons are made on a normalised key rather than the raw path, because
the same matter is reachable under two spellings of the register segment
(``mergers-and-acquisitions-registers`` and the newer
``acquisitions-and-mergers-registers``, which 301s between them). The ACCC
is mid-migration and serves a mix of both, so raw-string matching would
both re-fetch matters that are past cutoff and queue duplicates of matters
already covered by the listing.
"""

import json
import os
import sys
from urllib.parse import unquote, urlparse

from scripts.cutoff import CUTOFF_WEEKS, should_skip_merger


def normalize_target(path: str) -> str:
    """Return a comparison key identifying the matter a path points at.

    Keys off the final path segment (the matter slug) with percent-escapes
    decoded and case folded, so the two register-segment spellings and any
    difference in escape casing collapse to the same value.
    """
    if not path:
        return ''
    segment = urlparse(path).path.rstrip('/').rsplit('/', 1)[-1]
    return unquote(segment).casefold()


def select_targets(listing_paths, mergers, cutoff_weeks: int = CUTOFF_WEEKS,
                   scrape_all: bool = False):
    """Choose the matter paths to fetch.

    Args:
        listing_paths: Relative paths scraped from the register listing pages.
        mergers: Records already in mergers.json.
        cutoff_weeks: Weeks after determination at which a matter goes cold.
        scrape_all: Ignore cutoff dates — fetch every matter we know of.

    Returns:
        (paths, stats) where paths preserves listing order (listing links
        first, then recovered ones) and stats reports what happened.
    """
    # Merger IDs keyed by target so the run summary can name what was skipped
    # or recovered, rather than only counting it.
    ids_by_key = {}
    skip_keys = set()
    known_paths = []
    for merger in mergers:
        url = merger.get('url', '')
        if not url:
            continue
        path = urlparse(url).path
        if not path:
            continue
        key = normalize_target(path)
        merger_id = merger.get('merger_id')
        if merger_id:
            ids_by_key[key] = merger_id
        if not scrape_all and should_skip_merger(merger, cutoff_weeks=cutoff_weeks):
            skip_keys.add(key)
        else:
            known_paths.append(path)

    paths = []
    seen = set()
    # Keys seen anywhere in the listing, cutoff or not, so a repeated row is
    # counted as a duplicate even when the matter is too cold to fetch.
    listing_seen = set()
    stats = {
        'listing': 0,
        'duplicates': 0,
        'skipped': 0,
        'skipped_mergers': [],
        'recovered': 0,
        'recovered_paths': [],
        'recovered_mergers': [],
    }

    for path in listing_paths:
        path = path.strip()
        if not path:
            continue
        stats['listing'] += 1
        key = normalize_target(path)
        # Count duplicates before the cutoff check. Most listing rows are past
        # cutoff, so checking after it hid nearly every duplicate the listing
        # served — the summary would report a stable crawl while the same cold
        # matter was served twice and another was silently dropped, which is
        # exactly the instability this counter exists to surface.
        if key in listing_seen:
            stats['duplicates'] += 1
            continue
        listing_seen.add(key)
        if key in skip_keys:
            stats['skipped'] += 1
            stats['skipped_mergers'].append(
                {'merger_id': ids_by_key.get(key), 'path': path}
            )
            continue
        seen.add(key)
        paths.append(path)

    # Recover matters the listing dropped. Without this a matter that ties on
    # the listing's sort key can vanish for an unbounded number of runs.
    for path in known_paths:
        key = normalize_target(path)
        if key in seen:
            continue
        seen.add(key)
        paths.append(path)
        stats['recovered'] += 1
        stats['recovered_paths'].append(path)
        stats['recovered_mergers'].append(
            {'merger_id': ids_by_key.get(key), 'path': path}
        )

    stats['targets'] = len(paths)

    return paths, stats


def load_mergers(mergers_json_path: str):
    """Read mergers.json, treating a missing or unreadable file as empty."""
    if not os.path.exists(mergers_json_path):
        return []
    try:
        with open(mergers_json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (json.JSONDecodeError, IOError):
        return []
    return data if isinstance(data, list) else []


def main():
    """Read listing paths on stdin, write the paths to fetch on stdout.

    Usage:
        pup ... | python3 scrape_targets.py [--all] [mergers.json]

    Progress detail goes to stderr so stdout stays a clean path list.
    """
    import argparse

    parser = argparse.ArgumentParser(
        description='Select register matter paths for the scraper to fetch.'
    )
    parser.add_argument(
        'mergers_json',
        nargs='?',
        default='data/processed/mergers.json',
        help='Path to mergers.json (default: data/processed/mergers.json)'
    )
    parser.add_argument(
        '--all',
        action='store_true',
        help='Ignore cutoff dates and fetch every known matter'
    )
    parser.add_argument(
        '--cutoff-weeks',
        type=int,
        default=CUTOFF_WEEKS,
        help=f'Weeks after determination to cut off (default: {CUTOFF_WEEKS})'
    )
    parser.add_argument(
        '--stats-json',
        help='Write the selection stats to this path as JSON (for run summaries)'
    )
    args = parser.parse_args()

    listing_paths = [line.strip() for line in sys.stdin if line.strip()]
    mergers = load_mergers(args.mergers_json)
    paths, stats = select_targets(
        listing_paths,
        mergers,
        cutoff_weeks=args.cutoff_weeks,
        scrape_all=args.all,
    )

    if args.stats_json:
        with open(args.stats_json, 'w', encoding='utf-8') as f:
            json.dump(stats, f, indent=2)

    if stats['duplicates']:
        print(f"    Listing served {stats['duplicates']} duplicate link(s)", file=sys.stderr)
    if stats['skipped']:
        print(f"    Skipping {stats['skipped']} merger(s) past cutoff", file=sys.stderr)
    if stats['recovered']:
        print(f"    Recovered {stats['recovered']} merger(s) missing from the listing:", file=sys.stderr)
        for path in stats['recovered_paths']:
            print(f"    - {path}", file=sys.stderr)

    for path in paths:
        print(path)


if __name__ == '__main__':
    main()
