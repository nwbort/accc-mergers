"""Tests for the Federal Court judicial review overlay.

Covers loading judicial_reviews.json and linking review records onto
enriched mergers (the ``judicial_review`` field). Unlike tribunal appeals,
there is no documents list, no event-timeline folding, and no lifecycle
status to track — this overlay only carries enough to render a link-out
card to the court's own case page.
"""

import json
import os
import sys
import unittest.mock
from pathlib import Path

# Add scripts directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Mock heavy transitive imports before importing modules that need them
sys.modules.setdefault('pdfplumber', unittest.mock.MagicMock())
sys.modules.setdefault('markdownify', unittest.mock.MagicMock())
sys.modules.setdefault('requests', unittest.mock.MagicMock())

from static_data import loaders
from static_data.enrichment import enrich_merger, link_judicial_reviews


def _phase2_not_approved(merger_id='MN-0001'):
    return {
        'merger_id': merger_id,
        'merger_name': f'{merger_id} deal',
        'status': 'Assessment completed',
        'stage': 'Phase 2 - detailed assessment',
        'accc_determination': 'Not approved',
        'determination_publication_date': '2026-07-01T12:00:00Z',
        'end_of_determination_period': '2026-07-02T12:00:00Z',
        'effective_notification_datetime': '2025-11-27T12:00:00Z',
        'events': [
            {'title': 'Merger notified to ACCC', 'date': '2025-11-27T12:00:00Z'},
            {'title': 'ACCC decided notification is subject to Phase 2 review', 'date': '2026-01-29T12:00:00Z'},
        ],
    }


def _judicial_review(merger_id='MN-0001'):
    return {
        merger_id: {
            'applicant': 'Coles',
            'filed_date': '2026-07-15',
            'case_number': 'NSD1310/2026',
            'case_url': 'https://www.comcourts.gov.au/file/Federal/P/nsd1310/2026/actions',
        }
    }


class TestLinkJudicialReviews:
    def test_sets_record(self):
        mergers = [enrich_merger(_phase2_not_approved())]
        linked = link_judicial_reviews(mergers, _judicial_review())
        assert linked == 1
        m = mergers[0]
        assert m['judicial_review']['applicant'] == 'Coles'
        assert m['judicial_review']['filed_date'] == '2026-07-15'
        assert m['judicial_review']['case_number'] == 'NSD1310/2026'
        assert m['judicial_review']['case_url'] == 'https://www.comcourts.gov.au/file/Federal/P/nsd1310/2026/actions'

    def test_no_entry_means_no_record(self):
        mergers = [enrich_merger(_phase2_not_approved())]
        linked = link_judicial_reviews(mergers, _judicial_review('MN-9999'))
        assert linked == 0
        assert 'judicial_review' not in mergers[0]

    def test_empty_dict_is_noop(self):
        mergers = [enrich_merger(_phase2_not_approved())]
        assert link_judicial_reviews(mergers, {}) == 0


class TestLoader:
    def test_strips_metadata_keys(self, tmp_path, monkeypatch):
        path = tmp_path / 'judicial_reviews.json'
        path.write_text(json.dumps({'_comment': 'x', 'MN-0001': _judicial_review()['MN-0001']}))
        monkeypatch.setattr(loaders, 'JUDICIAL_REVIEWS_JSON', path)
        data = loaders.load_judicial_reviews()
        assert set(data.keys()) == {'MN-0001'}

    def test_missing_file_returns_empty(self, tmp_path, monkeypatch):
        monkeypatch.setattr(loaders, 'JUDICIAL_REVIEWS_JSON', tmp_path / 'nope.json')
        assert loaders.load_judicial_reviews() == {}


class TestRealDataFile:
    def test_committed_file_is_valid(self):
        """The checked-in overlay parses and every entry has the required fields."""
        repo_root = Path(__file__).resolve().parent.parent.parent
        path = repo_root / 'data' / 'processed' / 'judicial_reviews.json'
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        for merger_id, review in data.items():
            if merger_id.startswith('_'):
                continue
            assert review.get('applicant')
            assert review.get('filed_date')
            assert review.get('case_number')
            assert review.get('case_url', '').startswith('https://www.comcourts.gov.au/')
