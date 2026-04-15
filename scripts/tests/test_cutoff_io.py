"""Tests for cutoff.py helpers that read mergers.json from disk:
get_active_merger_ids, get_skipped_merger_ids, get_skipped_url_paths.

The "skip old merger" predicate (should_skip_merger) and its underlying
helpers are already exercised in test_pipeline.py — these tests focus on
the file-IO wrappers around that predicate.
"""

import json
import os
import sys
import unittest.mock
from datetime import datetime, timedelta

# Add scripts directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Mock heavy transitive imports (cutoff itself has none, but keeping parity
# with test_pipeline.py in case the import graph grows).
sys.modules.setdefault('pdfplumber', unittest.mock.MagicMock())
sys.modules.setdefault('markdownify', unittest.mock.MagicMock())
sys.modules.setdefault('requests', unittest.mock.MagicMock())

from cutoff import (
    get_active_merger_ids,
    get_skipped_merger_ids,
    get_skipped_url_paths,
)


def _write_mergers(path, mergers):
    path.write_text(json.dumps(mergers))


def _make_mergers(reference: datetime):
    """Build a set of mergers with a mix of active / skipped states."""
    long_ago = (reference - timedelta(weeks=10)).strftime('%Y-%m-%dT12:00:00Z')
    recent = (reference - timedelta(days=2)).strftime('%Y-%m-%dT12:00:00Z')
    return [
        # Approved long ago → should be skipped
        {
            'merger_id': 'MN-SKIP-1',
            'accc_determination': 'Approved',
            'determination_publication_date': long_ago,
            'stage': 'Phase 1',
            'url': 'https://www.accc.gov.au/public-registers/skip1',
        },
        # Approved recently → still active (within cutoff window)
        {
            'merger_id': 'MN-ACTIVE-1',
            'accc_determination': 'Approved',
            'determination_publication_date': recent,
            'stage': 'Phase 1',
            'url': 'https://www.accc.gov.au/public-registers/active1',
        },
        # Not opposed → active forever
        {
            'merger_id': 'MN-ACTIVE-2',
            'accc_determination': 'Not opposed',
            'determination_publication_date': long_ago,
            'stage': 'Phase 1',
            'url': 'https://www.accc.gov.au/public-registers/active2',
        },
        # Waiver long ago → skipped (waivers cut off regardless of outcome)
        {
            'merger_id': 'WA-SKIP-1',
            'accc_determination': 'Not approved',
            'determination_publication_date': long_ago,
            'stage': 'Waiver',
            'url': 'https://www.accc.gov.au/public-registers/waiver-skip',
        },
        # No determination → active
        {
            'merger_id': 'MN-UNDECIDED',
            'accc_determination': '',
            'determination_publication_date': None,
            'stage': 'Phase 1',
            'url': 'https://www.accc.gov.au/public-registers/pending',
        },
    ]


class TestGetActiveMergerIds:
    def test_returns_set_of_active_ids(self, tmp_path):
        # The predicate uses datetime.now() internally, so pin "now" by
        # picking a reference well after the long-ago timestamps but only
        # days after the recent ones.
        reference = datetime(2026, 6, 1)
        path = tmp_path / 'mergers.json'
        _write_mergers(path, _make_mergers(reference))

        # We cannot easily inject reference_date through this API, so patch
        # datetime.now in the cutoff module.
        with unittest.mock.patch('cutoff.datetime') as mock_dt:
            mock_dt.now.return_value = reference
            mock_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)
            result = get_active_merger_ids(str(path))

        assert isinstance(result, set)
        assert 'MN-ACTIVE-1' in result
        assert 'MN-ACTIVE-2' in result
        assert 'MN-UNDECIDED' in result
        assert 'MN-SKIP-1' not in result
        assert 'WA-SKIP-1' not in result

    def test_missing_file_returns_empty_set(self, tmp_path):
        result = get_active_merger_ids(str(tmp_path / 'does-not-exist.json'))
        assert result == set()

    def test_invalid_json_returns_empty_set(self, tmp_path):
        path = tmp_path / 'bad.json'
        path.write_text('not: valid json{')
        assert get_active_merger_ids(str(path)) == set()

    def test_empty_list_returns_empty_set(self, tmp_path):
        path = tmp_path / 'empty.json'
        path.write_text('[]')
        assert get_active_merger_ids(str(path)) == set()

    def test_skips_mergers_without_id(self, tmp_path):
        path = tmp_path / 'mergers.json'
        path.write_text(json.dumps([{'stage': 'Phase 1'}]))
        assert get_active_merger_ids(str(path)) == set()


class TestGetSkippedMergerIds:
    def test_returns_set_of_skipped_ids(self, tmp_path):
        reference = datetime(2026, 6, 1)
        path = tmp_path / 'mergers.json'
        _write_mergers(path, _make_mergers(reference))

        with unittest.mock.patch('cutoff.datetime') as mock_dt:
            mock_dt.now.return_value = reference
            mock_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)
            result = get_skipped_merger_ids(str(path))

        assert result == {'MN-SKIP-1', 'WA-SKIP-1'}

    def test_active_and_skipped_are_disjoint(self, tmp_path):
        reference = datetime(2026, 6, 1)
        path = tmp_path / 'mergers.json'
        _write_mergers(path, _make_mergers(reference))

        with unittest.mock.patch('cutoff.datetime') as mock_dt:
            mock_dt.now.return_value = reference
            mock_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)
            active = get_active_merger_ids(str(path))
            skipped = get_skipped_merger_ids(str(path))

        assert active.isdisjoint(skipped)

    def test_missing_file_returns_empty_set(self, tmp_path):
        assert get_skipped_merger_ids(str(tmp_path / 'nope.json')) == set()

    def test_custom_cutoff_weeks(self, tmp_path):
        # With a very large cutoff window, nothing should be skipped.
        reference = datetime(2026, 6, 1)
        path = tmp_path / 'mergers.json'
        _write_mergers(path, _make_mergers(reference))

        with unittest.mock.patch('cutoff.datetime') as mock_dt:
            mock_dt.now.return_value = reference
            mock_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)
            result = get_skipped_merger_ids(str(path), cutoff_weeks=520)

        assert result == set()


class TestGetSkippedUrlPaths:
    def test_returns_parsed_paths(self, tmp_path):
        reference = datetime(2026, 6, 1)
        path = tmp_path / 'mergers.json'
        _write_mergers(path, _make_mergers(reference))

        with unittest.mock.patch('cutoff.datetime') as mock_dt:
            mock_dt.now.return_value = reference
            mock_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)
            paths = get_skipped_url_paths(str(path))

        # Parsed paths only — no scheme/host.
        assert '/public-registers/skip1' in paths
        assert '/public-registers/waiver-skip' in paths
        # Active mergers should not appear.
        assert '/public-registers/active1' not in paths
        assert '/public-registers/pending' not in paths

    def test_ignores_mergers_without_url(self, tmp_path):
        reference = datetime(2026, 6, 1)
        long_ago = (reference - timedelta(weeks=10)).strftime('%Y-%m-%dT12:00:00Z')
        path = tmp_path / 'mergers.json'
        _write_mergers(path, [
            {
                'merger_id': 'MN-SKIP',
                'accc_determination': 'Approved',
                'determination_publication_date': long_ago,
                'stage': 'Phase 1',
                # No 'url' key
            },
        ])
        with unittest.mock.patch('cutoff.datetime') as mock_dt:
            mock_dt.now.return_value = reference
            mock_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)
            assert get_skipped_url_paths(str(path)) == set()

    def test_missing_file_returns_empty_set(self, tmp_path):
        assert get_skipped_url_paths(str(tmp_path / 'nope.json')) == set()

    def test_invalid_json_returns_empty_set(self, tmp_path):
        path = tmp_path / 'bad.json'
        path.write_text('{not json')
        assert get_skipped_url_paths(str(path)) == set()
