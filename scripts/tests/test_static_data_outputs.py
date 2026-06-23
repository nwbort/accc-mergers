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
from static_data import anzsic
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

    def test_recent_determinations_includes_ceased_assessments(self):
        mergers = _raw_fixture()
        mergers.append({
            'merger_id': 'MN-0006',
            'merger_name': 'Lambda ceased',
            'status': merger_status.ASSESSMENT_CEASED,
            'accc_determination': None,
            'stage': 'Phase 1 - preliminary assessment',
            'effective_notification_datetime': '2026-01-10T09:00:00Z',
            'determination_publication_date': None,
            'end_of_determination_period': '2026-03-01T12:00:00Z',
            'page_modified_datetime': '2026-02-15T12:30:00Z',
            'anzsic_codes': [],
            'acquirers': ['Lambda'],
            'targets': ['Mu'],
            'other_parties': [],
            'url': 'https://example.com/MN-0006',
            'events': [
                {'title': 'Merger notified to ACCC', 'date': '2026-01-10T09:00:00Z'},
                {'title': 'Consideration of Notification ceased', 'date': '2026-02-15T12:00:00Z'},
            ],
        })
        enriched = [enrich_merger(m) for m in mergers]
        payload = stats.generate(enriched)
        ceased = [
            d for d in payload['recent_determinations']
            if d.get('determination_type') == 'ceased'
        ]
        assert any(d['merger_id'] == 'MN-0006' for d in ceased)
        entry = next(d for d in ceased if d['merger_id'] == 'MN-0006')
        assert entry['determination'] == merger_status.ASSESSMENT_CEASED
        assert entry['determination_date'] == '2026-02-15T12:00:00Z'

    def test_recent_determinations_includes_phase_2_referrals(self):
        mergers = _raw_fixture()
        mergers.append({
            'merger_id': 'MN-0005',
            'merger_name': 'Iota proceeds to phase 2',
            'status': merger_status.UNDER_ASSESSMENT,
            'accc_determination': None,
            'stage': 'Phase 2 - detailed assessment',
            'effective_notification_datetime': '2026-03-03T09:00:00Z',
            'determination_publication_date': None,
            'end_of_determination_period': '2026-08-01T12:00:00Z',
            'page_modified_datetime': '2026-04-16T12:30:00Z',
            'anzsic_codes': [],
            'acquirers': ['Iota'],
            'targets': ['Kappa'],
            'other_parties': [],
            'url': 'https://example.com/MN-0005',
            'events': [
                {'title': 'Merger notified to ACCC', 'date': '2026-03-03T09:00:00Z', 'url': 'e6'},
                {'title': 'Decision to Proceed to a Phase 2 review', 'date': '2026-04-16T12:00:00Z', 'url': 'e7'},
            ],
        })
        enriched = [enrich_merger(m) for m in mergers]
        payload = stats.generate(enriched)
        phase_transitions = [
            d for d in payload['recent_determinations']
            if d.get('determination_type') == 'phase_transition'
        ]
        assert any(d['merger_id'] == 'MN-0005' for d in phase_transitions)
        phase_2 = next(d for d in phase_transitions if d['merger_id'] == 'MN-0005')
        assert phase_2['determination'] == merger_status.REFERRED_TO_PHASE_2
        assert phase_2['determination_date'] == '2026-04-16T12:00:00Z'


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

    def test_total_mergers_counts_unique_mergers(self):
        # MN-0001, MN-0002 (Mining) + WA-0003 (Transport); MN-0004 has no codes.
        # A merger tagged to multiple industries must only count once.
        payload = industries.generate_index(_enriched_fixture())
        assert payload['total_mergers'] == 3
        assert payload['total_industries'] == 2


class TestIndustriesDetailFiles:
    # The fixture tags MN-0001/MN-0002 to ANZSIC class 0600 (Coal Mining, a real
    # node) and WA-0003 to 5400 (not a real ANZSIC code — an "orphan").

    def test_writes_a_file_for_every_node_plus_orphans(self, tmp_path):
        n = industries.generate_detail_files(_enriched_fixture(), tmp_path)
        # One file per ANZSIC node, plus a standalone file for the orphan code.
        assert n == len(anzsic.hierarchy()) + 1
        written = {p.stem for p in (tmp_path / 'industries').glob('*.json')}
        assert len(written) == n
        # Tagged class, its ancestors, an untouched node, and the orphan all exist.
        for code in ('0600', '060', '06', 'B', '0801', '5400'):
            assert (tmp_path / 'industries' / f'{code}.json').exists()

    def test_class_file_contents(self, tmp_path):
        industries.generate_detail_files(_enriched_fixture(), tmp_path)
        with open(tmp_path / 'industries' / '0600.json') as f:
            data = json.load(f)
        assert data['code'] == '0600'
        # Name and level come from the official ANZSIC tree, not the merger tag.
        assert data['name'] == 'Coal Mining'
        assert data['level'] == 'class'
        assert data['parent'] == {'code': '060', 'name': 'Coal Mining', 'level': 'group'}
        # Breadcrumb runs division → subdivision → group.
        assert [a['code'] for a in data['ancestors']] == ['B', '06', '060']
        assert data['children'] == []  # classes are leaves
        assert data['count'] == 2
        # _latest_date should have been stripped
        assert all('_latest_date' not in m for m in data['mergers'])
        # Per-merger phase + aggregate stat breakdown are present
        assert all(m['phase'] in ('Phase 1', 'Phase 2', 'Waiver') for m in data['mergers'])
        assert data['phase_1_count'] == 2
        assert data['phase_2_count'] == 0
        assert data['waiver_count'] == 0
        assert data['active_count'] == 1

    def test_mergers_roll_up_to_ancestors(self, tmp_path):
        industries.generate_detail_files(_enriched_fixture(), tmp_path)
        # The group/subdivision/division above 0600 aggregate its mergers,
        # deduped by merger_id, and expose 0600 as a child with its count.
        for code in ('060', '06', 'B'):
            with open(tmp_path / 'industries' / f'{code}.json') as f:
                node = json.load(f)
            ids = {m['merger_id'] for m in node['mergers']}
            assert ids == {'MN-0001', 'MN-0002'}
            assert node['count'] == 2
        with open(tmp_path / 'industries' / '060.json') as f:
            group = json.load(f)
        child = next(c for c in group['children'] if c['code'] == '0600')
        assert child['merger_count'] == 2
        assert group['level'] == 'group'

    def test_orphan_code_file(self, tmp_path):
        industries.generate_detail_files(_enriched_fixture(), tmp_path)
        with open(tmp_path / 'industries' / '5400.json') as f:
            data = json.load(f)
        assert data['code'] == '5400'
        assert data['name'] is None
        assert data['level'] is None
        assert data['parent'] is None
        assert data['ancestors'] == []
        assert data['count'] == 1

    def test_includes_phase_duration(self, tmp_path):
        industries.generate_detail_files(_enriched_fixture(), tmp_path)
        with open(tmp_path / 'industries' / '0600.json') as f:
            mining = json.load(f)
        # MN-0001 completed (notified 2025-01-06 → determined 2025-02-05).
        assert mining['phase_duration'] is not None
        assert mining['phase_duration']['average_days'] == 30
        assert mining['phase_duration']['completed_count'] == 1
        # The orphan code is a single waiver — no Phase 1 duration.
        with open(tmp_path / 'industries' / '5400.json') as f:
            transport = json.load(f)
        assert transport['phase_duration'] is None


# ---------------------------------------------------------------------------
# Phase 1 duration (shared across stats / industries / analysis)
# ---------------------------------------------------------------------------

def _referred_then_completed_phase_2_raw():
    """A matter referred to Phase 2 whose Phase 2 has since concluded.

    Its published determination is the *Phase 2* outcome months after
    notification; Phase 1 ended at the referral on 2026-01-20.
    """
    return {
        'merger_id': 'MN-7000',
        'merger_name': 'Referred then approved at Phase 2',
        'status': 'Assessment completed',
        'accc_determination': 'Approved',
        'stage': 'Phase 2 - detailed assessment',
        'effective_notification_datetime': '2025-10-10T12:00:00Z',
        'determination_publication_date': '2026-06-02T12:00:00Z',
        'page_modified_datetime': '2026-06-02T12:30:00Z',
        'anzsic_codes': [{'code': '0600', 'name': 'Mining'}],
        'acquirers': ['Nu'],
        'targets': ['Xi'],
        'other_parties': [],
        'url': 'https://example.com/MN-7000',
        'events': [
            {'title': 'Merger notified to ACCC', 'date': '2025-10-10T12:00:00Z'},
            {'title': 'Decision to Proceed to a Phase 2 review', 'date': '2026-01-20T12:00:00Z'},
            {'title': 'Phase 2 - Determination', 'date': '2026-06-02T12:00:00Z'},
        ],
    }


class TestPhase1DurationExcludesPhase2Clock:
    """A Phase-2-referred matter must be measured to the referral date, never
    to the later Phase 2 determination, which would inflate Phase 1 durations.
    """

    def test_collect_uses_referral_date_not_phase_2_determination(self):
        from static_data.business_days import (
            calculate_business_days,
            calculate_calendar_days,
        )
        from static_data.durations import collect_phase_1_durations

        enriched = enrich_merger(_referred_then_completed_phase_2_raw())
        cal, bus = collect_phase_1_durations([enriched])

        # Phase 1 ran notification → referral (2025-10-10 → 2026-01-20), not
        # notification → Phase 2 determination (→ 2026-06-02).
        assert bus == [calculate_business_days('2025-10-10T12:00:00Z', '2026-01-20T12:00:00Z')]
        assert cal == [calculate_calendar_days('2025-10-10T12:00:00Z', '2026-01-20T12:00:00Z')]

    def test_stats_phase_duration_not_inflated(self):
        enriched = enrich_merger(_referred_then_completed_phase_2_raw())
        payload = stats.generate([enriched])
        # The full notification → Phase 2 span is ~165 business days; Phase 1
        # alone is well under the 30-business-day statutory window plus the
        # Christmas shutdown — comfortably below 80.
        assert payload['phase_duration']['average_business_days'] < 80

    def test_industries_phase_duration_counts_referred_matter(self, tmp_path):
        industries.generate_detail_files([enrich_merger(_referred_then_completed_phase_2_raw())], tmp_path)
        with open(tmp_path / 'industries' / '0600.json') as f:
            mining = json.load(f)
        # The referred matter has a concluded Phase 1, so it is counted...
        assert mining['phase_duration']['completed_count'] == 1
        # ...but at its Phase 1 length, not the Phase 2 span.
        assert mining['phase_duration']['average_business_days'] < 80

    def test_untouched_node_has_empty_payload(self, tmp_path):
        industries.generate_detail_files(_enriched_fixture(), tmp_path)
        # 0801 (Iron Ore Mining) has no mergers but still gets a browsable page.
        with open(tmp_path / 'industries' / '0801.json') as f:
            data = json.load(f)
        assert data['count'] == 0
        assert data['mergers'] == []
        assert data['name'] == 'Iron Ore Mining'

    def test_active_mergers_sort_first(self, tmp_path):
        industries.generate_detail_files(_enriched_fixture(), tmp_path)
        with open(tmp_path / 'industries' / '0600.json') as f:
            data = json.load(f)
        # MN-0002 is under assessment, so it leads MN-0001 (completed).
        assert [m['merger_id'] for m in data['mergers']] == ['MN-0002', 'MN-0001']


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

    def test_excludes_early_determination_missing_pub_date(self):
        # A Phase 2 merger where accc_determination is set but
        # determination_publication_date is None (early determination, date not
        # yet scraped) must not produce a "determination due" event.
        from datetime import datetime, timedelta, timezone
        future = (datetime.now(timezone.utc) + timedelta(days=30)).strftime('%Y-%m-%dT12:00:00Z')
        merger = {
            'merger_id': 'MN-9999',
            'merger_name': 'Early Phase 2 determination',
            'status': 'Assessment completed',
            'accc_determination': 'Approved',
            'stage': 'Phase 2 - detailed assessment',
            'effective_notification_datetime': '2025-01-01T12:00:00Z',
            'determination_publication_date': None,
            'end_of_determination_period': future,
            'page_modified_datetime': '2026-01-01T12:00:00Z',
            'anzsic_codes': [],
            'acquirers': [],
            'targets': [],
            'other_parties': [],
            'url': 'https://example.com/MN-9999',
            'events': [{'title': 'Phase 2 determination', 'date': '2026-01-01T12:00:00Z'}],
        }
        enriched = [enrich_merger(merger)]
        payload = upcoming_events.generate(enriched, days_ahead=60)
        assert not any(e['merger_id'] == 'MN-9999' for e in payload['events']), (
            "Merger with accc_determination set should be excluded even if "
            "determination_publication_date is missing"
        )


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

    def test_filters_all_questionnaires_to_active_events(self, tmp_path):
        q_data = {
            'MN-0001': {
                'deadline': '26 Jun 2026',
                'deadline_iso': '2026-06-26',
                'file_name': 'Q_0.pdf',
                'questions': [{'number': 1, 'text': 'Q?'}],
                'questions_count': 1,
                'all_questionnaires': [
                    {
                        'deadline': '26 Jun 2026',
                        'deadline_iso': '2026-06-26',
                        'file_name': 'Q_0.pdf',
                        'questions': [{'number': 1, 'text': 'Q?'}],
                        'questions_count': 1,
                    },
                    {
                        'deadline': '25 Jun 2026',
                        'deadline_iso': '2026-06-25',
                        'file_name': 'Q.pdf',
                        'questions': [{'number': 1, 'text': 'Q?'}],
                        'questions_count': 1,
                    },
                ],
            },
        }
        mergers = [
            {
                'merger_id': 'MN-0001',
                'events': [
                    {
                        'title': 'Questionnaire',
                        'url_gh': '/mergers/MN-0001/Q_0.pdf',
                    },
                ],
            }
        ]
        questionnaires.generate(q_data, tmp_path, mergers=mergers)
        with open(tmp_path / 'questionnaires' / 'MN-0001.json') as f:
            data = json.load(f)
        assert 'all_questionnaires' not in data, "Removed event's questionnaire should be filtered out"
