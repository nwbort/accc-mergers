"""Tests for expected_matters.py — has the listing served the emailed matters?

An email-triggered run must not silently miss a brand-new matter the register
listing's unstable sort happened to drop: the IDs reported missing here are
what makes scrape.sh crawl the listing again.
"""

from scripts.scrape.expected_matters import (
    listing_case_numbers,
    missing_ids,
    parse_expected_ids,
)

REGISTER = '/public-registers/acquisitions-and-mergers-registers/acquisitions-register'


def _card(case_number, slug):
    """One listing card, shaped as the ACCC register serves it."""
    return f'''
    <div class="views-row">
    <div class="accc-collapsed-card contextual-region h-100">
      <div class="accc-collapsed-card__header" id="heading-1">
      <a href="{REGISTER}/{slug}"><div class="field field--name-node-title"><h3>{slug}</h3></div>
      <div class="accc-collapsed-card__header-info">
        <div class="accc-collapsed-card__header-content">
          <div class="field field--acccgov-type field--label-inline"><h3 class="field__label">Type</h3>
          <div class="field__item">Waiver</div></div>
          <div class="field field--name-field-acccgov-mcmsmergermatterno field--type-string field--label-inline clearfix">
            <h3 class="field__label">Case number</h3>
            <div class="field__item">{case_number}</div>
          </div>
        </div>
      </div></a>
      </div>
    </div>
    </div>'''


def _page(*cards):
    return '<html><body>' + ''.join(cards) + '</body></html>'


class TestParseExpectedIds:
    def test_splits_on_commas_and_whitespace(self):
        assert parse_expected_ids('WA-30046, WA-75070\nMN-01016') == [
            'WA-30046', 'WA-75070', 'MN-01016']

    def test_dedupes_and_uppercases(self):
        assert parse_expected_ids('wa-30046,WA-30046') == ['WA-30046']

    def test_drops_anything_not_a_case_number(self):
        assert parse_expected_ids('WA-30046; rm -rf /, ../MN-1, XX-12345') == []
        assert parse_expected_ids('') == []
        assert parse_expected_ids(None) == []


class TestListingCaseNumbers:
    def test_maps_case_number_to_path(self):
        html = _page(_card('WA-30046', 'omers-la-trobe'), _card('MN-01016', 'a-b'))
        assert listing_case_numbers(html) == {
            'WA-30046': f'{REGISTER}/omers-la-trobe',
            'MN-01016': f'{REGISTER}/a-b',
        }

    def test_ignores_cards_without_a_case_number(self):
        html = _page(_card('', 'no-number'), _card('not-an-id', 'bad'))
        assert listing_case_numbers(html) == {}


class TestMissingIds:
    def test_new_matter_dropped_by_the_listing_is_missing(self):
        pages = [_page(_card('WA-30045', 'x'))]
        assert missing_ids(['WA-30046'], pages, known_ids=set()) == ['WA-30046']

    def test_found_on_any_crawl_is_not_missing(self):
        first = _page(_card('WA-30045', 'x'))
        recrawl = _page(_card('WA-30046', 'y'))
        assert missing_ids(['WA-30046'], [first, recrawl], known_ids=set()) == []

    def test_known_matter_is_not_missing(self):
        # scrape_targets.py recovers a known matter from its stored URL, so
        # its absence from the listing is no reason to crawl again.
        assert missing_ids(['MN-01016'], [_page()], known_ids={'MN-01016'}) == []

    def test_keeps_email_order(self):
        assert missing_ids(['WA-75070', 'WA-30046'], [_page()], set()) == [
            'WA-75070', 'WA-30046']
