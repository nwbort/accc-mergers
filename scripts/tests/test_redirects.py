"""Tests for the retired-party-page redirects written into _redirects."""

import json
import os
import sys
import unittest.mock
from pathlib import Path

# Add scripts directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Mock heavy transitive imports
sys.modules.setdefault('pdfplumber', unittest.mock.MagicMock())
sys.modules.setdefault('markdownify', unittest.mock.MagicMock())
sys.modules.setdefault('requests', unittest.mock.MagicMock())

from static_data import loaders
from static_data.enrichment import enrich_merger
from static_data.outputs import parties, redirects


_COLES_GROUP = {
    'id': 'coles',
    'canonical_name': 'Coles Group',
    'members': [
        {'name': 'COLES GROUP LIMITED', 'identifier': '11 004 089 936'},
        {'name': 'COLES SUPERMARKETS AUSTRALIA PTY LTD', 'identifier': '45 004 189 708'},
    ],
}


def _merger(merger_id, acquirer):
    return {
        'merger_id': merger_id,
        'merger_name': f'{merger_id} matter',
        'status': 'Under assessment',
        'is_waiver': False,
        'stage': 'Phase 1',
        'effective_notification_datetime': '2025-03-01T09:00:00Z',
        'acquirers': [acquirer],
        'targets': [],
        'other_parties': [],
    }


def _fixture():
    return [
        _merger('MN-1001', {
            'name': 'COLES GROUP LIMITED',
            'identifier': '11 004 089 936',
            'identifier_type': 'ABN',
        }),
        _merger('MN-1002', {
            'name': 'COLES SUPERMARKETS AUSTRALIA PTY LTD',
            'identifier': '45 004 189 708',
            'identifier_type': 'ABN',
        }),
        _merger('MN-1003', {
            'name': 'WAREHOUSE CO PTY LTD',
            'identifier': '99 999 999 999',
            'identifier_type': 'ABN',
        }),
    ]


class TestBuildPartyAliases:
    def test_grouped_party_aliases_to_its_group(self):
        mergers = _fixture()
        pages = parties.build_party_pages(mergers, [_COLES_GROUP])
        aliases = parties.build_party_aliases(mergers, [_COLES_GROUP], pages)
        assert aliases['coles-supermarkets-australia-pty-ltd'] == 'coles'
        assert aliases['coles-group-limited'] == 'coles'

    def test_ungrouped_party_has_no_alias(self):
        # It still owns its page, so there is nothing to redirect.
        mergers = _fixture()
        pages = parties.build_party_pages(mergers, [_COLES_GROUP])
        aliases = parties.build_party_aliases(mergers, [_COLES_GROUP], pages)
        assert 'warehouse-co-pty-ltd' not in aliases

    def test_no_groups_means_no_aliases(self):
        mergers = _fixture()
        pages = parties.build_party_pages(mergers, [])
        assert parties.build_party_aliases(mergers, [], pages) == {}

    def test_a_live_page_id_is_never_aliased(self):
        # A group whose id matches what one of its members' pages would be
        # called must not redirect that id onto itself or shadow a real page.
        group = {
            'id': 'coles-group-limited',
            'canonical_name': 'Coles Group',
            'members': [{'name': 'COLES GROUP LIMITED', 'identifier': '11 004 089 936'}],
        }
        mergers = _fixture()
        pages = parties.build_party_pages(mergers, [group])
        aliases = parties.build_party_aliases(mergers, [group], pages)
        assert 'coles-group-limited' not in aliases


class TestPrunedPagesGetRedirects:
    """Pruning and redirecting are two halves of one event — a page that the
    prune removes must be a page the redirects cover."""

    def test_every_page_pruned_by_a_fold_in_gains_a_rule(self, tmp_path):
        mergers = _fixture()

        # Before: no declared groups, so every party has its own page.
        before = parties.build_party_pages(mergers, [])
        parties.generate_detail_files(before, tmp_path)
        before_ids = {p.stem for p in (tmp_path / 'parties').glob('*.json')}

        # After: Coles is declared, folding two parties into one page. Rebuild
        # from fresh mergers — build_party_pages annotates parties in place.
        mergers = _fixture()
        after = parties.build_party_pages(mergers, [_COLES_GROUP])
        parties.generate_detail_files(after, tmp_path)
        after_ids = {p.stem for p in (tmp_path / 'parties').glob('*.json')}

        pruned = before_ids - after_ids
        assert pruned  # the fold-in really did retire pages

        aliases = parties.build_party_aliases(mergers, [_COLES_GROUP], after)
        rules = redirects.build_rules(aliases, after)
        sources = {line.split()[0].split('/')[2] for line in rules}
        assert pruned <= sources


class TestBuildRules:
    PAGES = [
        {'id': 'coles', 'canonical_name': 'Coles Group'},
        {'id': 'warehouse-co-pty-ltd', 'canonical_name': 'Warehouse Co Pty Ltd'},
    ]

    def test_writes_both_url_shapes(self):
        rules = redirects.build_rules({'coles-group-limited': 'coles'}, self.PAGES)
        assert rules == [
            '/parties/coles-group-limited  /parties/coles/coles-group  301',
            '/parties/coles-group-limited/coles-group-limited  /parties/coles/coles-group  301',
        ]

    def test_skips_target_without_a_page(self):
        # Redirecting to a URL that 404s is worse than the 404 we started with.
        assert redirects.build_rules({'old-party': 'not-a-page'}, self.PAGES) == []

    def test_skips_source_that_is_a_live_page(self):
        assert redirects.build_rules({'warehouse-co-pty-ltd': 'coles'}, self.PAGES) == []

    def test_skips_self_redirect(self):
        assert redirects.build_rules({'coles': 'coles'}, self.PAGES) == []


class TestGenerate:
    PAGES = [{'id': 'coles', 'canonical_name': 'Coles Group'}]
    HAND_WRITTEN = '# Redirect old /matters/ document paths to /mergers/\n/matters/*  /mergers/:splat  301\n'

    def test_preserves_hand_written_rules(self, tmp_path):
        path = tmp_path / '_redirects'
        path.write_text(self.HAND_WRITTEN)
        redirects.generate({'coles-group-limited': 'coles'}, self.PAGES, path)
        text = path.read_text()
        assert '/matters/*  /mergers/:splat  301' in text
        assert '/parties/coles-group-limited  /parties/coles/coles-group  301' in text

    def test_rerunning_replaces_the_block_rather_than_appending(self, tmp_path):
        path = tmp_path / '_redirects'
        path.write_text(self.HAND_WRITTEN)
        redirects.generate({'coles-group-limited': 'coles'}, self.PAGES, path)
        first = path.read_text()
        redirects.generate({'coles-group-limited': 'coles'}, self.PAGES, path)
        assert path.read_text() == first
        assert first.count(redirects.BEGIN_MARKER) == 1

    def test_an_alias_that_goes_away_drops_out_of_the_block(self, tmp_path):
        path = tmp_path / '_redirects'
        path.write_text(self.HAND_WRITTEN)
        redirects.generate(
            {'coles-group-limited': 'coles', 'old-party': 'coles'}, self.PAGES, path
        )
        assert '/parties/old-party  ' in path.read_text()
        redirects.generate({'coles-group-limited': 'coles'}, self.PAGES, path)
        assert '/parties/old-party  ' not in path.read_text()

    def test_no_aliases_leaves_only_hand_written_rules(self, tmp_path):
        path = tmp_path / '_redirects'
        path.write_text(self.HAND_WRITTEN)
        assert redirects.generate({}, self.PAGES, path) == 0
        assert path.read_text().rstrip('\n') == self.HAND_WRITTEN.rstrip('\n')

    def test_creates_the_file_when_absent(self, tmp_path):
        path = tmp_path / '_redirects'
        n = redirects.generate({'coles-group-limited': 'coles'}, self.PAGES, path)
        assert n == 2
        assert path.exists()

    def test_returns_the_rule_count(self, tmp_path):
        path = tmp_path / '_redirects'
        n = redirects.generate(
            {'a-party': 'coles', 'b-party': 'coles'}, self.PAGES, path
        )
        assert n == 4


class TestOverlayLoader:
    def test_reads_from_to_pairs(self, tmp_path, monkeypatch):
        path = tmp_path / 'party_redirects.json'
        path.write_text(json.dumps({
            '_README': 'x',
            'redirects': [{'from': 'old-id', 'to': 'new-id', 'note': 'why'}],
        }))
        monkeypatch.setattr(loaders, 'PARTY_REDIRECTS_JSON', path)
        assert loaders.load_party_redirects() == {'old-id': 'new-id'}

    def test_skips_incomplete_entries(self, tmp_path, monkeypatch):
        path = tmp_path / 'party_redirects.json'
        path.write_text(json.dumps({'redirects': [
            {'from': 'old-id'}, {'to': 'new-id'}, {'from': 'a', 'to': 'b'},
        ]}))
        monkeypatch.setattr(loaders, 'PARTY_REDIRECTS_JSON', path)
        assert loaders.load_party_redirects() == {'a': 'b'}

    def test_missing_file_returns_empty(self, tmp_path, monkeypatch):
        monkeypatch.setattr(loaders, 'PARTY_REDIRECTS_JSON', tmp_path / 'nope.json')
        assert loaders.load_party_redirects() == {}

    def test_malformed_file_returns_empty(self, tmp_path, monkeypatch):
        path = tmp_path / 'party_redirects.json'
        path.write_text('{not json')
        monkeypatch.setattr(loaders, 'PARTY_REDIRECTS_JSON', path)
        assert loaders.load_party_redirects() == {}


class TestRealDataFile:
    """The committed overlay has to point at pages that actually exist —
    a redirect to a 404 is worse than the 404 it replaced."""

    @staticmethod
    def _entries():
        repo_root = Path(__file__).resolve().parent.parent.parent
        path = repo_root / 'data' / 'processed' / 'party_redirects.json'
        return json.loads(path.read_text())['redirects']

    def test_entries_are_well_formed(self):
        entries = self._entries()
        assert entries, 'expected at least one hand-maintained redirect'
        seen = set()
        for entry in entries:
            assert entry['from'] and entry['to']
            assert entry['from'] != entry['to']
            assert entry.get('note'), f"{entry['from']} needs a note explaining it"
            assert entry['from'] not in seen, f"duplicate entry for {entry['from']}"
            seen.add(entry['from'])

    def test_every_target_is_a_live_page_and_no_source_is(self):
        mergers = [enrich_merger(m) for m in loaders.load_mergers()]
        pages = parties.build_party_pages(mergers, loaders.load_related_parties())
        live = {p['id'] for p in pages}
        for entry in self._entries():
            assert entry['to'] in live, f"{entry['from']} redirects to missing page {entry['to']}"
            assert entry['from'] not in live, f"{entry['from']} is a live page — it must not be redirected"
