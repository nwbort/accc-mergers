"""Tests for scrape_targets.py — the scraper's fetch-list selection.

The behaviour that matters here is recovery: the ACCC register paginates over
an unstable sort, so a crawl can serve one matter twice and drop another
entirely. A dropped matter must still be fetched from what mergers.json
already knows, or its saved HTML never refreshes again.
"""

import json
import os
import sys
import unittest.mock
from datetime import datetime, timedelta

# Add scripts directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

sys.modules.setdefault('pdfplumber', unittest.mock.MagicMock())
sys.modules.setdefault('markdownify', unittest.mock.MagicMock())
sys.modules.setdefault('requests', unittest.mock.MagicMock())

from scrape_targets import load_mergers, normalize_target, select_targets

REGISTER = '/public-registers/acquisitions-and-mergers-registers/acquisitions-register'
OLD_REGISTER = '/public-registers/mergers-and-acquisitions-registers/acquisitions-register'


def _url(slug, register=REGISTER):
    return f'https://www.accc.gov.au{register}/{slug}'


def _active(merger_id, slug, register=REGISTER):
    """A matter with no determination — always active."""
    return {'merger_id': merger_id, 'stage': 'Phase 1 - initial assessment',
            'url': _url(slug, register)}


def _completed(merger_id, slug, weeks_ago=10, register=REGISTER):
    """An approved matter old enough to be past cutoff."""
    published = (datetime.now() - timedelta(weeks=weeks_ago)).strftime('%Y-%m-%dT12:00:00Z')
    return {'merger_id': merger_id, 'stage': 'Phase 1 - initial assessment',
            'accc_determination': 'Approved', 'determination_publication_date': published,
            'url': _url(slug, register)}


class TestNormalizeTarget:
    def test_ignores_register_segment_word_order(self):
        # The ACCC serves both spellings and 301s between them.
        assert normalize_target(f'{REGISTER}/acme-widgets') == \
            normalize_target(f'{OLD_REGISTER}/acme-widgets')

    def test_decodes_percent_escapes(self):
        assert normalize_target(f'{REGISTER}/lor%C3%A9al-innovist') == \
            normalize_target(f'{REGISTER}/loréal-innovist')

    def test_ignores_escape_case(self):
        assert normalize_target(f'{REGISTER}/a-%e2%80%93-b') == \
            normalize_target(f'{REGISTER}/a-%E2%80%93-b')

    def test_accepts_absolute_urls(self):
        assert normalize_target(_url('acme-widgets')) == \
            normalize_target(f'{REGISTER}/acme-widgets')

    def test_empty_path(self):
        assert normalize_target('') == ''


class TestSelectTargets:
    def test_recovers_matter_missing_from_listing(self):
        mergers = [_active('MN-1', 'acme-widgets'), _active('MN-2', 'lor%C3%A9al-innovist')]
        listing = [f'{REGISTER}/acme-widgets']

        paths, stats = select_targets(listing, mergers)

        assert stats['recovered'] == 1
        assert f'{REGISTER}/lor%C3%A9al-innovist' in paths

    def test_recovery_matches_across_register_spellings(self):
        # The stored URL and the listing link disagree on word order; that must
        # not queue the same matter twice.
        mergers = [_active('MN-1', 'acme-widgets', register=OLD_REGISTER)]
        listing = [f'{REGISTER}/acme-widgets']

        paths, stats = select_targets(listing, mergers)

        assert stats['recovered'] == 0
        assert paths == [f'{REGISTER}/acme-widgets']

    def test_drops_duplicate_listing_links(self):
        listing = [f'{REGISTER}/acme-widgets', f'{OLD_REGISTER}/acme-widgets']

        paths, stats = select_targets(listing, [])

        assert paths == [f'{REGISTER}/acme-widgets']
        assert stats['duplicates'] == 1

    def test_skips_matters_past_cutoff(self):
        mergers = [_completed('MN-1', 'old-deal')]
        listing = [f'{REGISTER}/old-deal', f'{REGISTER}/new-deal']

        paths, stats = select_targets(listing, mergers)

        assert paths == [f'{REGISTER}/new-deal']
        assert stats['skipped'] == 1

    def test_past_cutoff_matters_are_not_recovered(self):
        # Recovery must not resurrect matters the cutoff deliberately retires.
        mergers = [_completed('MN-1', 'old-deal')]

        paths, stats = select_targets([], mergers)

        assert paths == []
        assert stats['recovered'] == 0

    def test_cutoff_skip_matches_across_register_spellings(self):
        mergers = [_completed('MN-1', 'old-deal', register=OLD_REGISTER)]
        listing = [f'{REGISTER}/old-deal']

        paths, stats = select_targets(listing, mergers)

        assert paths == []
        assert stats['skipped'] == 1

    def test_all_ignores_cutoff_and_recovers_everything(self):
        mergers = [_completed('MN-1', 'old-deal'), _active('MN-2', 'live-deal')]

        paths, stats = select_targets([], mergers, scrape_all=True)

        assert sorted(paths) == sorted([f'{REGISTER}/old-deal', f'{REGISTER}/live-deal'])
        assert stats['skipped'] == 0
        assert stats['recovered'] == 2

    def test_listing_order_is_preserved_with_recoveries_last(self):
        mergers = [_active('MN-3', 'dropped-deal')]
        listing = [f'{REGISTER}/first', f'{REGISTER}/second']

        paths, _ = select_targets(listing, mergers)

        assert paths == [f'{REGISTER}/first', f'{REGISTER}/second',
                         f'{REGISTER}/dropped-deal']

    def test_ignores_records_without_a_url(self):
        paths, stats = select_targets([], [{'merger_id': 'MN-1'}, {'merger_id': 'MN-2', 'url': ''}])

        assert paths == []
        assert stats['recovered'] == 0

    def test_blank_listing_lines_are_ignored(self):
        paths, stats = select_targets(['', '  ', f'{REGISTER}/acme-widgets'], [])

        assert paths == [f'{REGISTER}/acme-widgets']
        assert stats['listing'] == 1


class TestSelectTargetsStats:
    """Stats feed the run summary, which is read to spot check a scrape."""

    def test_names_the_mergers_skipped_past_cutoff(self):
        mergers = [_completed('MN-2', 'settled-deal')]

        _, stats = select_targets([f'{REGISTER}/settled-deal'], mergers)

        assert stats['skipped_mergers'] == [
            {'merger_id': 'MN-2', 'path': f'{REGISTER}/settled-deal'}
        ]

    def test_names_the_mergers_recovered_from_outside_the_listing(self):
        mergers = [_active('MN-3', 'dropped-deal')]

        _, stats = select_targets([], mergers)

        assert stats['recovered_mergers'] == [
            {'merger_id': 'MN-3', 'path': f'{REGISTER}/dropped-deal'}
        ]

    def test_counts_the_targets_returned(self):
        mergers = [_active('MN-3', 'dropped-deal')]

        paths, stats = select_targets([f'{REGISTER}/new-deal'], mergers)

        assert stats['targets'] == len(paths) == 2


class TestLoadMergers:
    def test_missing_file(self, tmp_path):
        assert load_mergers(str(tmp_path / 'nope.json')) == []

    def test_malformed_json(self, tmp_path):
        path = tmp_path / 'mergers.json'
        path.write_text('{not json')
        assert load_mergers(str(path)) == []

    def test_non_list_payload(self, tmp_path):
        path = tmp_path / 'mergers.json'
        path.write_text(json.dumps({'merger_id': 'MN-1'}))
        assert load_mergers(str(path)) == []

    def test_reads_records(self, tmp_path):
        path = tmp_path / 'mergers.json'
        path.write_text(json.dumps([_active('MN-1', 'acme-widgets')]))
        assert len(load_mergers(str(path))) == 1
