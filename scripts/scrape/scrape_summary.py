"""Render a Markdown summary of what a scrape run fetched.

The pipeline appends this to the GitHub Actions step summary so a run can be
spot checked against the ACCC register emails: it names every merger ID the
scraper fetched, flags which of those pages actually changed on disk, and —
just as usefully when a change goes missing — names the matters the run
never fetched because they are past the cutoff.

Inputs are the report files ``scrape.sh`` writes when ``SCRAPE_REPORT_DIR``
is set:

* ``targets.json``  — selection stats from ``scrape_targets.py``
* ``fetched.tsv``   — one ``status<TAB>merger_id<TAB>path`` row per fetch

Usage:
    python3 -m scripts.scrape.scrape_summary --report-dir /tmp/scrape-report \
        [--changed-paths changed.txt] >> "$GITHUB_STEP_SUMMARY"
"""

import argparse
import json
import os

# Long lists are collapsed behind a <details> block rather than dumped into
# the summary; anything at or under this many entries is shown inline.
INLINE_LIMIT = 25


def load_stats(report_dir: str) -> dict:
    """Read targets.json, treating a missing or unreadable file as empty."""
    path = os.path.join(report_dir, 'targets.json')
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def load_fetched(report_dir: str):
    """Read fetched.tsv into (ok, failed) lists of ``{merger_id, path}``."""
    path = os.path.join(report_dir, 'fetched.tsv')
    ok, failed = [], []
    try:
        with open(path, 'r', encoding='utf-8') as f:
            rows = f.read().splitlines()
    except OSError:
        return ok, failed

    for row in rows:
        if not row.strip():
            continue
        parts = row.split('\t')
        if len(parts) != 3:
            continue
        status, merger_id, link = parts
        entry = {'merger_id': merger_id, 'path': link}
        (ok if status == 'ok' else failed).append(entry)
    return ok, failed


def load_changed_ids(changed_paths_file: str) -> set:
    """Return merger IDs whose saved matter page changed in this run.

    Takes a file of git-reported paths, one per line, and keys off the matter
    page filename — data/raw/matters/MN-100123.html is merger MN-100123.
    """
    if not changed_paths_file:
        return set()
    try:
        with open(changed_paths_file, 'r', encoding='utf-8') as f:
            lines = f.read().splitlines()
    except OSError:
        return set()

    changed = set()
    for line in lines:
        line = line.strip().strip('"')
        if not line.endswith('.html'):
            continue
        if 'data/raw/matters/' not in line:
            continue
        changed.add(os.path.basename(line)[:-len('.html')])
    return changed


def _ids(entries) -> list:
    """Sorted, de-duplicated merger IDs from a list of report entries."""
    return sorted({e['merger_id'] for e in entries if e.get('merger_id')})


def _code_list(ids) -> str:
    return ', '.join(f'`{i}`' for i in ids)


def _block(title: str, ids, empty: str = '') -> list:
    """Render a labelled ID list, collapsing it when it is a long one."""
    if not ids:
        return [empty, ''] if empty else []
    if len(ids) <= INLINE_LIMIT:
        return [f'**{title} ({len(ids)}):** {_code_list(ids)}', '']
    return [
        '<details>',
        f'<summary>{title} ({len(ids)})</summary>',
        '',
        _code_list(ids),
        '',
        '</details>',
        '',
    ]


def render(stats: dict, fetched, failed, changed_ids) -> str:
    """Build the Markdown summary for one scrape run."""
    lines = ['### Scrape', '']

    if not stats and not fetched and not failed:
        lines += ['No scrape report was produced for this run.', '']
        return '\n'.join(lines)

    fetched_ids = _ids(fetched)
    skipped_ids = _ids(stats.get('skipped_mergers', []))
    recovered_ids = _ids(stats.get('recovered_mergers', []))
    # Only count pages we fetched this run: a page can also show as changed
    # because an earlier run left it dirty.
    changed_fetched = [i for i in fetched_ids if i in changed_ids]

    lines += [
        '| | |',
        '| --- | ---: |',
        f"| Links in register listing | {stats.get('listing', 0)} |",
        f"| Duplicate links dropped | {stats.get('duplicates', 0)} |",
        f"| Skipped (past cutoff) | {stats.get('skipped', 0)} |",
        f"| Recovered (missing from listing) | {stats.get('recovered', 0)} |",
        f'| Pages fetched | {len(fetched)} |',
        f'| Pages changed | {len(changed_fetched)} |',
        f'| Fetch failures | {len(failed)} |',
        '',
    ]

    lines += _block('Changed this run', changed_fetched,
                    empty='No matter pages changed in this run.')
    lines += _block('Merger IDs scraped', fetched_ids,
                    empty='No matter pages were fetched.')
    if recovered_ids:
        lines += _block('Recovered from outside the listing', recovered_ids)
    if skipped_ids:
        lines += _block('Skipped — past cutoff, not scraped', skipped_ids)
    if failed:
        lines += _block('Fetch failures',
                        [e['path'] for e in failed])

    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(
        description='Render a Markdown summary of a scrape run.'
    )
    parser.add_argument(
        '--report-dir',
        required=True,
        help='Directory scrape.sh wrote its run report into (SCRAPE_REPORT_DIR)'
    )
    parser.add_argument(
        '--changed-paths',
        help='File of git-reported changed paths, one per line'
    )
    args = parser.parse_args()

    stats = load_stats(args.report_dir)
    fetched, failed = load_fetched(args.report_dir)
    changed_ids = load_changed_ids(args.changed_paths)

    print(render(stats, fetched, failed, changed_ids))


if __name__ == '__main__':
    main()
