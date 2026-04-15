"""Smoke tests for scripts/static_data/outputs/*.

Each generator is fed a small enriched fixture and asserted to produce
valid, schema-correct JSON.
"""

import json
import os
import sys
import unittest.mock

# Add scripts directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Mock heavy transitive imports
sys.modules.setdefault('pdfplumber', unittest.mock.MagicMock())
sys.modules.setdefault('markdownify', unittest.mock.MagicMock())
sys.modules.setdefault('requests', unittest.mock.MagicMock())

from constants import merger_status
from static_data.enrichment import enrich_merger
from static_data.outputs import (
    analysis,
    commentary as commentary_out,
    individual,
    industries,
    list as list_out,
    questionnaires,
    stats,
    timeline,
    upcoming_events,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _raw_fixture():
    """Four mergers: determined notification, in-progress notification, waiver, suspended."""
    return [
        {
            'merger_id': 'MN-0001',
            'merger_name': 'Alpha acquires Beta',
            'status': 'Determined',
            'accc_determination': 'Approved',
            'stage': 'Phase 1 - preliminary assessment',
            'effective_notification_datetime': '2025-01-06T09:00:00Z',
            'determination_publication_date': '2025-02-05T12:00:00Z',
            'end_of_determination_period': '2025-02-20T12:00:00Z',
            'page_modified_datetime': '2025-02-05T12:30:00Z',
            'anzsic_codes': [{'code': '0600', 'name': 'Mining'}],
            'acquirers': ['Alpha Corp'],
            'targets': ['Beta Ltd'],
            'other_parties': [],
            'url': 'https://example.com/MN-0001',
            'events': [
                {'title': 'Merger notified to ACCC', 'date': '2025-01-06T09:00:00Z', 'url': 'e1'},
                {'title': 'Phase 1 - Determination', 'date': '2025-02-05T12:00:00Z', 'url': 'e2'},
            ],
        },
        {
            'merger_id': 'MN-0002',
            'merger_name': 'Gamma buys Delta',
            'status': 'Under assessment',
            'accc_determination': None,
            'stage': 'Phase 1 - preliminary assessment',
            'effective_notification_datetime': '2025-03-15T09:00:00Z',
            'determination_publication_date': None,
            'end_of_determination_period': '2026-05-01T12:00:00Z',
            'consultation_response_due_date': '2026-04-20T12:00:00Z',
            'page_modified_datetime': '2025-03-15T09:30:00Z',
            'anzsic_codes': [{'code': '0600', 'name': 'Mining'}],
            'acquirers': ['Gamma Inc'],
            'targets': ['Delta Pty'],
            'other_parties': [],
            'url': 'https://example.com/MN-0002',
            'events': [
                {'title': 'Merger notified to ACCC', 'date': '2025-03-15T09:00:00Z', 'url': 'e3'},
            ],
        },
        {
            'merger_id': 'WA-0003',
            'merger_name': 'Epsilon waiver',
            'status': 'Determined',
            'accc_determination': 'Waiver granted',
            'stage': 'Waiver',
            'effective_notification_datetime': '2025-02-01T09:00:00Z',
            'determination_publication_date': '2025-02-10T12:00:00Z',
            'page_modified_datetime': '2025-02-10T12:30:00Z',
            'anzsic_codes': [{'code': '5400', 'name': 'Transport'}],
            'acquirers': ['Epsilon Ltd'],
            'targets': ['Zeta Co'],
            'other_parties': [],
            'url': 'https://example.com/WA-0003',
            'events': [
                {'title': 'Waiver application received', 'date': '2025-02-01T09:00:00Z', 'url': 'e4'},
            ],
        },
        {
            'merger_id': 'MN-0004',
            'merger_name': 'Eta suspended',
            'status': merger_status.ASSESSMENT_SUSPENDED,
            'accc_determination': None,
            'stage': 'Phase 1 - preliminary assessment',
            'effective_notification_datetime': '2025-02-15T09:00:00Z',
            'determination_publication_date': None,
            'page_modified_datetime': '2025-02-15T09:30:00Z',
            'anzsic_codes': [],
            'acquirers': ['Eta'],
            'targets': ['Theta'],
            'other_parties': [],
            'url': 'https://example.com/MN-0004',
            'events': [
                {'title': 'Merger notified to ACCC', 'date': '2025-02-15T09:00:00Z', 'url': 'e5'},
            ],
        },
    ]


def _enriched_fixture():
    return [enrich_merger(m) for m in _raw_fixture()]


# ---------------------------------------------------------------------------
# stats
# ---------------------------------------------------------------------------

class TestStatsGenerate:
    def test_returns_valid_shape(self):
        payload = stats.generate(_enriched_fixture())
        # JSON-serialisable
        json.dumps(payload)
        # Key shape
        assert set(payload.keys()) >= {
            'total_mergers', 'total_waivers', 'by_status', 'by_determination',
            'by_waiver_determination', 'phase_duration', 'top_industries',
            'recent_mergers', 'recent_determinations',
        }

    def test_counts_split_waivers_correctly(self):
        payload = stats.generate(_enriched_fixture())
        assert payload['total_waivers'] == 1
        assert payload['total_mergers'] == 3  # 3 notifications (1 determined + 1 live + 1 suspended)

    def test_top_industries_includes_all_mergers(self):
        payload = stats.generate(_enriched_fixture())
        names = {i['name'] for i in payload['top_industries']}
        # Mining appears twice (MN-0001, MN-0002), Transport once (WA-0003)
        assert names == {'Mining', 'Transport'}
        mining = next(i for i in payload['top_industries'] if i['name'] == 'Mining')
        assert mining['count'] == 2


# ---------------------------------------------------------------------------
# industries
# ---------------------------------------------------------------------------

class TestIndustriesGenerateIndex:
    def test_returns_valid_shape(self):
        payload = industries.generate_index(_enriched_fixture())
        json.dumps(payload)
        assert 'industries' in payload
        assert all('code' in i and 'name' in i and 'merger_count' in i for i in payload['industries'])

    def test_sorts_by_count_desc(self):
        payload = industries.generate_index(_enriched_fixture())
        counts = [i['merger_count'] for i in payload['industries']]
        assert counts == sorted(counts, reverse=True)


class TestIndustriesDetailFiles:
    def test_writes_one_file_per_code(self, tmp_path):
        n = industries.generate_detail_files(_enriched_fixture(), tmp_path)
        assert n == 2
        assert (tmp_path / 'industries' / '0600.json').exists()
        assert (tmp_path / 'industries' / '5400.json').exists()

    def test_file_contents_are_valid_json(self, tmp_path):
        industries.generate_detail_files(_enriched_fixture(), tmp_path)
        with open(tmp_path / 'industries' / '0600.json') as f:
            data = json.load(f)
        assert data['code'] == '0600'
        assert data['count'] == 2
        # _latest_date should have been stripped
        assert all('_latest_date' not in m for m in data['mergers'])


# ---------------------------------------------------------------------------
# commentary
# ---------------------------------------------------------------------------

class TestCommentaryGenerate:
    def test_returns_valid_shape(self):
        commentary = {'MN-0001': {'comments': [{'text': 'Hi', 'date': '2025-02-06'}]}}
        payload = commentary_out.generate(_enriched_fixture(), commentary)
        json.dumps(payload)
        assert payload['count'] == 1
        assert payload['items'][0]['merger_id'] == 'MN-0001'

    def test_empty_commentary(self):
        payload = commentary_out.generate(_enriched_fixture(), {})
        assert payload == {'items': [], 'count': 0}


# ---------------------------------------------------------------------------
# analysis
# ---------------------------------------------------------------------------

class TestAnalysisGenerate:
    def test_returns_valid_shape(self):
        payload = analysis.generate(_enriched_fixture())
        json.dumps(payload)
        assert set(payload.keys()) == {'phase1_duration', 'waiver_duration', 'monthly_volume'}
        assert 'scatter_data' in payload['phase1_duration']
        assert 'scatter_data' in payload['waiver_duration']
        assert 'labels' in payload['monthly_volume']

    def test_phase1_scatter_only_notifications(self):
        payload = analysis.generate(_enriched_fixture())
        ids = {p['merger_id'] for p in payload['phase1_duration']['scatter_data']}
        # Only MN-0001 has notification + determination (MN-0002 has no determination,
        # MN-0004 is suspended with no determination either)
        assert ids == {'MN-0001'}

    def test_waiver_scatter_only_waivers(self):
        payload = analysis.generate(_enriched_fixture())
        ids = {p['merger_id'] for p in payload['waiver_duration']['scatter_data']}
        assert ids == {'WA-0003'}


# ---------------------------------------------------------------------------
# individual
# ---------------------------------------------------------------------------

class TestIndividualGenerate:
    def test_writes_one_file_per_merger(self, tmp_path):
        n = individual.generate(_enriched_fixture(), tmp_path)
        assert n == 4
        assert (tmp_path / 'mergers' / 'MN-0001.json').exists()
        assert (tmp_path / 'mergers' / 'WA-0003.json').exists()

    def test_content_matches_merger(self, tmp_path):
        individual.generate(_enriched_fixture(), tmp_path)
        with open(tmp_path / 'mergers' / 'MN-0001.json') as f:
            data = json.load(f)
        assert data['merger_id'] == 'MN-0001'
        assert data['is_waiver'] is False


# ---------------------------------------------------------------------------
# list (paginated)
# ---------------------------------------------------------------------------

class TestListGenerate:
    def test_writes_pages_and_meta(self, tmp_path):
        pages = list_out.generate(_enriched_fixture(), tmp_path, page_size=2)
        assert pages == 2
        assert (tmp_path / 'mergers' / 'list-page-1.json').exists()
        assert (tmp_path / 'mergers' / 'list-page-2.json').exists()
        assert (tmp_path / 'mergers' / 'list-meta.json').exists()

    def test_meta_content(self, tmp_path):
        list_out.generate(_enriched_fixture(), tmp_path, page_size=3)
        with open(tmp_path / 'mergers' / 'list-meta.json') as f:
            meta = json.load(f)
        assert meta == {'total': 4, 'page_size': 3, 'total_pages': 2}

    def test_sorted_ascending_by_notification(self, tmp_path):
        list_out.generate(_enriched_fixture(), tmp_path, page_size=50)
        with open(tmp_path / 'mergers' / 'list-page-1.json') as f:
            page = json.load(f)
        dates = [m['effective_notification_datetime'] for m in page['mergers']]
        assert dates == sorted(dates)


# ---------------------------------------------------------------------------
# timeline (paginated)
# ---------------------------------------------------------------------------

class TestTimelineGenerate:
    def test_writes_pages_and_meta(self, tmp_path):
        pages = timeline.generate(_enriched_fixture(), tmp_path, page_size=100)
        assert pages >= 1
        assert (tmp_path / 'timeline-meta.json').exists()

    def test_meta_content(self, tmp_path):
        timeline.generate(_enriched_fixture(), tmp_path, page_size=100)
        with open(tmp_path / 'timeline-meta.json') as f:
            meta = json.load(f)
        # Total events across the fixture: 2 + 1 + 1 + 1 = 5
        assert meta['total'] == 5

    def test_events_sorted_ascending(self, tmp_path):
        timeline.generate(_enriched_fixture(), tmp_path, page_size=100)
        with open(tmp_path / 'timeline-page-1.json') as f:
            page = json.load(f)
        dates = [e['date'] for e in page['events']]
        assert dates == sorted(dates)


# ---------------------------------------------------------------------------
# upcoming_events
# ---------------------------------------------------------------------------

class TestUpcomingEventsGenerate:
    def test_returns_valid_shape(self):
        payload = upcoming_events.generate(_enriched_fixture(), days_ahead=60)
        json.dumps(payload)
        assert set(payload.keys()) == {'events', 'count', 'days_ahead'}
        assert payload['days_ahead'] == 60

    def test_excludes_waivers_and_suspended(self):
        # Any event produced should not belong to waiver or suspended merger
        payload = upcoming_events.generate(_enriched_fixture(), days_ahead=60)
        excluded_ids = {'WA-0003', 'MN-0004'}
        assert not any(e['merger_id'] in excluded_ids for e in payload['events'])


# ---------------------------------------------------------------------------
# questionnaires
# ---------------------------------------------------------------------------

class TestQuestionnairesGenerate:
    def test_writes_files(self, tmp_path):
        q_data = {
            'MN-0001': {
                'deadline': '25 Aug 2025',
                'deadline_iso': '2025-08-25',
                'file_name': 'Q.pdf',
                'questions': [{'number': 1, 'text': 'Q?'}],
                'questions_count': 1,
            },
        }
        n = questionnaires.generate(q_data, tmp_path)
        assert n == 1
        assert (tmp_path / 'questionnaires' / 'MN-0001.json').exists()

    def test_skips_empty_questions(self, tmp_path):
        q_data = {
            'MN-0001': {'questions': [], 'questions_count': 0},
        }
        n = questionnaires.generate(q_data, tmp_path)
        assert n == 0
