"""Which matters named in an ACCC register email has the listing not served?

An email-triggered run exists to pick up the matter the email is about, but
the register listing paginates over an unstable sort (see scrape_targets.py):
one crawl serves some rows twice and silently drops others. A matter already
in mergers.json survives that, because scrape_targets.py recovers it from its
stored URL. A brand-new matter has no stored URL, so if the crawl drops it the
run fetches nothing new and reports success (runs 2825 and 2826 missed WA-75070
and WA-30046 this way, each the very matter its email announced).

Each listing card carries the matter's case number beside its link, so the
listing pages say which matters a crawl actually served. This module reads
them and reports the emailed IDs that are neither already known nor served,
which scrape.sh answers by crawling the listing again: the sort reshuffles on
every request, so a dropped row usually turns up on the next pass.

The matter IDs come from an inbound email (regex-extracted by the
accc-register-watcher Worker), so they are treated as untrusted: anything that
isn't shaped like a case number is dropped before it is used.
"""

import argparse
import re
import sys

from bs4 import BeautifulSoup

from scripts.scrape.scrape_targets import load_mergers

CASE_NUMBER = re.compile(r'^(?:MN|WA)-\d{4,6}$')


def parse_expected_ids(raw: str) -> list[str]:
    """Split an email's matter IDs into unique, well-formed case numbers.

    Accepts any mix of commas and whitespace as separators and keeps first-seen
    order. Anything not shaped like ``MN-12345`` or ``WA-12345`` is dropped.
    """
    ids = []
    for token in re.split(r'[\s,]+', raw or ''):
        token = token.strip().upper()
        if CASE_NUMBER.match(token) and token not in ids:
            ids.append(token)
    return ids


def listing_case_numbers(html: str) -> dict[str, str]:
    """Map each case number on a register listing page to its matter path."""
    soup = BeautifulSoup(html, 'lxml')
    found = {}
    for card in soup.select('.accc-collapsed-card'):
        link = card.select_one('.accc-collapsed-card__header a[href]')
        number = card.select_one(
            '.field--name-field-acccgov-mcmsmergermatterno .field__item'
        )
        if not link or not number:
            continue
        case_number = number.get_text(strip=True).upper()
        href = link['href']
        if CASE_NUMBER.match(case_number) and not href.startswith('#'):
            found.setdefault(case_number, href)
    return found


def missing_ids(expected: list[str], listing_pages: list[str],
                known_ids: set[str]) -> list[str]:
    """Expected IDs that are neither already known nor on any listing page."""
    served = set()
    for html in listing_pages:
        served.update(listing_case_numbers(html))
    return [i for i in expected if i not in known_ids and i not in served]


def main() -> None:
    """Print the emailed IDs still missing, one per line, for scrape.sh."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--ids', required=True,
                        help='Matter IDs from the email (comma/space separated)')
    parser.add_argument('--mergers-json', default='data/processed/mergers.json')
    parser.add_argument('pages', nargs='*', help='Saved register listing pages')
    args = parser.parse_args()

    expected = parse_expected_ids(args.ids)
    known = {m.get('merger_id') for m in load_mergers(args.mergers_json)}
    pages = []
    for path in args.pages:
        try:
            with open(path, encoding='utf-8', errors='replace') as f:
                pages.append(f.read())
        except OSError as exc:
            print(f'    Warning: could not read {path}: {exc}', file=sys.stderr)

    for merger_id in missing_ids(expected, pages, known):
        print(merger_id)


if __name__ == '__main__':
    main()
