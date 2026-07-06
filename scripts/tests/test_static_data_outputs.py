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
    theories_of_harm,
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


class TestStatsMedianMatchesAnalysis:
    """stats.py and analysis.py must agree on 'median Phase 1 duration'.

    Regression test for the two modules previously disagreeing on
    even-length duration lists: stats.py took the upper-middle element
    while analysis.py used statistics.median (average of the two middle
    values).
    """

    def test_even_length_duration_list_medians_agree(self):
        mergers = [
            {
                'merger_id': f'MN-800{i}',
                'merger_name': f'Merger {i}',
                'status': 'Determined',
                'accc_determination': 'Approved',
                'stage': 'Phase 1 - preliminary assessment',
                'effective_notification_datetime': notified,
                'determination_publication_date': determined,
                'end_of_determination_period': determined,
                'page_modified_datetime': determined,
                'anzsic_codes': [],
                'acquirers': [f'Acquirer {i}'],
                'targets': [f'Target {i}'],
                'other_parties': [],
                'url': f'https://example.com/MN-800{i}',
                'events': [
                    {'title': 'Merger notified to ACCC', 'date': notified},
                    {'title': 'Phase 1 - Determination', 'date': determined},
                ],
            }
            for i, (notified, determined) in enumerate([
                ('2025-01-06T09:00:00Z', '2025-01-15T12:00:00Z'),
                ('2025-02-03T09:00:00Z', '2025-02-19T12:00:00Z'),
                ('2025-03-03T09:00:00Z', '2025-03-25T12:00:00Z'),
                ('2025-04-07T09:00:00Z', '2025-05-06T12:00:00Z'),
            ])
        ]
        enriched = [enrich_merger(m) for m in mergers]

        stats_payload = stats.generate(enriched)
        analysis_payload = analysis.generate(enriched)

        assert stats_payload['phase_duration']['median_business_days'] == (
            analysis_payload['phase1_duration']['stats']['median']
        )
        assert stats_payload['phase_duration']['median_days'] == (
            analysis_payload['phase1_duration']['calendar_stats']['median']
        )


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

    def test_summary_carries_follow_notification_dates(self, tmp_path):
        # The per-merger summary exposes the filing + determination dates that
        # drive industry-follow notifications on the frontend.
        industries.generate_detail_files(_enriched_fixture(), tmp_path)
        with open(tmp_path / 'industries' / '0600.json') as f:
            data = json.load(f)
        by_id = {m['merger_id']: m for m in data['mergers']}
        # Determined notification: both dates present.
        assert by_id['MN-0001']['notification_date'] == '2025-01-06T09:00:00Z'
        assert by_id['MN-0001']['determination_date'] == '2025-02-05T12:00:00Z'
        # In-progress notification: filed but no determination yet.
        assert by_id['MN-0002']['notification_date'] == '2025-03-15T09:00:00Z'
        assert by_id['MN-0002']['determination_date'] is None

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
        assert set(payload.keys()) == {
            'phase1_duration', 'waiver_duration', 'monthly_volume', 'industry_phase1_duration',
            'by_commission_division',
            'deadline_utilisation', 'notification_restarts', 'restart_rate',
            'outcomes_by_division', 'referrals_by_quarter',
        }
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

    def test_industry_phase1_duration_rolls_up_to_division(self):
        payload = analysis.generate(_enriched_fixture())
        divisions = payload['industry_phase1_duration']
        # MN-0001 (code 0600, Coal Mining) has a completed Phase 1 and rolls up
        # to division B (Mining). MN-0002 shares the code but is in progress,
        # so it doesn't add a second completed review. WA-0003's code (5400)
        # is an orphan outside the ANZSIC tree, so Transport contributes nothing.
        assert [d['code'] for d in divisions] == ['B']
        mining = divisions[0]
        assert mining['name'] == 'Mining'
        assert mining['count'] == 1


class TestNotificationRestarts:
    """Spec 14: original_notification_datetime vs effective_notification_datetime."""

    def _restarted_notification_raw(self):
        return {
            'merger_id': 'MN-9001',
            'merger_name': 'Restarted notification',
            'status': 'Under assessment',
            'accc_determination': None,
            'stage': 'Phase 1 - preliminary assessment',
            'original_notification_datetime': '2026-02-06T12:00:00Z',
            'effective_notification_datetime': '2026-02-20T12:00:00Z',
            'determination_publication_date': None,
            'page_modified_datetime': '2026-02-20T12:30:00Z',
            'anzsic_codes': [],
            'acquirers': ['Omicron'],
            'targets': ['Pi'],
            'other_parties': [],
            'url': 'https://example.com/MN-9001',
            'events': [
                {'title': 'Merger notified to ACCC', 'date': '2026-02-20T12:00:00Z'},
            ],
        }

    def _restarted_waiver_raw(self):
        # Same original/effective mismatch, but a waiver — must not count as
        # a notification restart, since waivers have no Phase 1 clock.
        return {
            'merger_id': 'WA-9002',
            'merger_name': 'Restarted waiver (excluded)',
            'status': 'Determined',
            'accc_determination': 'Waiver granted',
            'stage': 'Waiver',
            'original_notification_datetime': '2026-03-01T12:00:00Z',
            'effective_notification_datetime': '2026-03-10T12:00:00Z',
            'determination_publication_date': '2026-03-20T12:00:00Z',
            'page_modified_datetime': '2026-03-20T12:30:00Z',
            'anzsic_codes': [],
            'acquirers': ['Rho'],
            'targets': ['Sigma'],
            'other_parties': [],
            'url': 'https://example.com/WA-9002',
            'events': [
                {'title': 'Waiver application received', 'date': '2026-03-10T12:00:00Z'},
            ],
        }

    def test_finds_restarted_notification(self):
        enriched = [enrich_merger(self._restarted_notification_raw())]
        restarts = analysis.notification_restarts(enriched)
        assert len(restarts) == 1
        entry = restarts[0]
        assert entry['merger_id'] == 'MN-9001'
        assert entry['original_date'] == '2026-02-06'
        assert entry['effective_date'] == '2026-02-20'
        assert entry['delta_calendar_days'] == 14

    def test_excludes_waivers(self):
        enriched = [enrich_merger(self._restarted_waiver_raw())]
        assert analysis.notification_restarts(enriched) == []

    def test_excludes_unchanged_dates(self):
        # The base fixture's mergers all have matching original/effective dates.
        assert analysis.notification_restarts(_enriched_fixture()) == []

    def test_sorted_by_delta_descending(self):
        small_delta = self._restarted_notification_raw()
        small_delta['merger_id'] = 'MN-9003'
        small_delta['effective_notification_datetime'] = '2026-02-08T12:00:00Z'
        enriched = [
            enrich_merger(small_delta),
            enrich_merger(self._restarted_notification_raw()),
        ]
        restarts = analysis.notification_restarts(enriched)
        assert [r['merger_id'] for r in restarts] == ['MN-9001', 'MN-9003']
        assert restarts[0]['delta_calendar_days'] > restarts[1]['delta_calendar_days']

    def test_restart_rate_in_generate_payload(self):
        mergers = _raw_fixture() + [self._restarted_notification_raw(), self._restarted_waiver_raw()]
        enriched = [enrich_merger(m) for m in mergers]
        payload = analysis.generate(enriched)
        assert len(payload['notification_restarts']) == 1
        notification_count = sum(1 for m in enriched if not m.get('is_waiver'))
        assert payload['restart_rate'] == round(1 / notification_count, 4)


# ---------------------------------------------------------------------------
# deadline_utilisation
# ---------------------------------------------------------------------------

def _deadline_merger(merger_id, det_date, deadline=None, determination='Approved'):
    """A notification merger notified 2025-06-02T09:00:00Z (a Monday).

    ``det_date`` and ``deadline`` are ISO datetimes for the Phase 1
    determination and ``end_of_determination_period`` respectively.
    """
    return {
        'merger_id': merger_id,
        'merger_name': f'{merger_id} merger',
        'status': 'Determined' if determination != merger_status.REFERRED_TO_PHASE_2 else 'Assessment completed',
        'accc_determination': determination if determination != merger_status.REFERRED_TO_PHASE_2 else None,
        'stage': 'Phase 1 - preliminary assessment',
        'effective_notification_datetime': '2025-06-02T09:00:00Z',
        'determination_publication_date': det_date if determination != merger_status.REFERRED_TO_PHASE_2 else None,
        'end_of_determination_period': deadline,
        'page_modified_datetime': det_date,
        'anzsic_codes': [],
        'acquirers': ['Acquirer'],
        'targets': ['Target'],
        'other_parties': [],
        'url': f'https://example.com/{merger_id}',
        'events': (
            [{'title': 'Decision to Proceed to a Phase 2 review', 'date': det_date}]
            if determination == merger_status.REFERRED_TO_PHASE_2 else []
        ),
    }


def _deadline_utilisation_fixture():
    """Notification 2025-06-02T09:00:00Z; a standard 30-BD window (deadline
    2025-07-15). Determinations land at used_bd 30, 28, 26, 24 (slack 0, 2, 4,
    6 respectively), plus an extended matter (45-BD window, used_bd 40) and a
    Phase 2 referral (excluded entirely).
    """
    deadline = '2025-07-15T12:00:00Z'
    return [
        _deadline_merger('MN-1000', '2025-07-15T12:00:00Z', deadline),  # slack 0
        _deadline_merger('MN-1001', '2025-07-11T12:00:00Z', deadline),  # slack 2
        _deadline_merger('MN-1002', '2025-07-09T12:00:00Z', deadline),  # slack 4
        _deadline_merger('MN-1003', '2025-07-07T12:00:00Z', deadline),  # slack 6
        _deadline_merger('MN-1004', '2025-07-29T12:00:00Z', '2025-08-05T12:00:00Z'),  # extended
        _deadline_merger('MN-1005', '2025-08-01T12:00:00Z', determination=merger_status.REFERRED_TO_PHASE_2),
    ]


class TestDeadlineUtilisationGenerate:
    def test_histogram_buckets_used_bd_excludes_extended_and_referred(self):
        enriched = [enrich_merger(m) for m in _deadline_utilisation_fixture()]
        payload = analysis.deadline_utilisation(enriched)
        assert payload['histogram'] == {'24': 1, '26': 1, '28': 1, '30': 1}

    def test_last_5_bd_counts_keyed_by_slack_remaining(self):
        enriched = [enrich_merger(m) for m in _deadline_utilisation_fixture()]
        payload = analysis.deadline_utilisation(enriched)
        # slack 0, 2 and 4 fall in the last-5-BD window; slack 6 does not.
        assert payload['last_5_bd_counts'] == {'0': 1, '2': 1, '4': 1}

    def test_extended_matter_counted_separately(self):
        enriched = [enrich_merger(m) for m in _deadline_utilisation_fixture()]
        payload = analysis.deadline_utilisation(enriched)
        assert payload['extended_count'] == 1

    def test_referral_excluded_entirely(self):
        enriched = [enrich_merger(m) for m in _deadline_utilisation_fixture()]
        payload = analysis.deadline_utilisation(enriched)
        assert payload['stats']['count'] == 4
        assert payload['extended_count'] == 1  # not 2 — the referral isn't counted here either

    def test_stats_mean_median_and_final_3_pct(self):
        enriched = [enrich_merger(m) for m in _deadline_utilisation_fixture()]
        payload = analysis.deadline_utilisation(enriched)
        stats = payload['stats']
        assert stats['mean_used_bd'] == 27.0
        assert stats['median_used_bd'] == 27
        # 2 of the 4 standard matters (slack 0 and 2) landed in the final 3 BDs.
        assert stats['pct_decided_final_3_bd'] == 50.0

    def test_empty_input_returns_zeroed_shape(self):
        payload = analysis.deadline_utilisation([])
        assert payload == {
            'histogram': {},
            'last_5_bd_counts': {},
            'stats': {},
            'extended_count': 0,
        }


# ---------------------------------------------------------------------------
# outcomes_by_division / referrals_by_quarter (spec 15)
# ---------------------------------------------------------------------------

def _outcomes_fixture_raw():
    """Notifications spanning every Phase 1 outcome, plus a referral, for spec 15.

    - MN-9101: approved, division B (Mining) via code 0600, notified Q1 2025.
    - MN-9102: not approved, division B via code 0600, notified Q1 2025.
    - MN-9103: referred to Phase 2, division B via code 0600, notified Q2 2025.
    - MN-9104: in progress (no determination yet), division B via code 0600,
      notified Q2 2025.
    - MN-9105: approved, tagged with two codes (0600 and 0801) that both roll
      up to division B — must be deduped, not double-counted.
    - WA-9106: a waiver (excluded from notification-based aggregates entirely).
    """
    return [
        {
            'merger_id': 'MN-9101',
            'merger_name': 'Outcome approved',
            'status': 'Determined',
            'accc_determination': 'Approved',
            'stage': 'Phase 1 - preliminary assessment',
            'effective_notification_datetime': '2025-01-10T09:00:00Z',
            'determination_publication_date': '2025-02-10T12:00:00Z',
            'page_modified_datetime': '2025-02-10T12:30:00Z',
            'anzsic_codes': [{'code': '0600', 'name': 'Coal Mining'}],
            'acquirers': ['A'], 'targets': ['B'], 'other_parties': [],
            'url': 'https://example.com/MN-9101',
            'events': [
                {'title': 'Merger notified to ACCC', 'date': '2025-01-10T09:00:00Z'},
                {'title': 'Phase 1 - Determination', 'date': '2025-02-10T12:00:00Z'},
            ],
        },
        {
            'merger_id': 'MN-9102',
            'merger_name': 'Outcome not approved',
            'status': 'Determined',
            'accc_determination': 'Not approved',
            'stage': 'Phase 1 - preliminary assessment',
            'effective_notification_datetime': '2025-01-20T09:00:00Z',
            'determination_publication_date': '2025-02-20T12:00:00Z',
            'page_modified_datetime': '2025-02-20T12:30:00Z',
            'anzsic_codes': [{'code': '0600', 'name': 'Coal Mining'}],
            'acquirers': ['C'], 'targets': ['D'], 'other_parties': [],
            'url': 'https://example.com/MN-9102',
            'events': [
                {'title': 'Merger notified to ACCC', 'date': '2025-01-20T09:00:00Z'},
                {'title': 'Phase 1 - Determination', 'date': '2025-02-20T12:00:00Z'},
            ],
        },
        {
            'merger_id': 'MN-9103',
            'merger_name': 'Outcome referred',
            'status': 'Under assessment',
            'accc_determination': None,
            'stage': 'Phase 2 - detailed assessment',
            'effective_notification_datetime': '2025-04-05T09:00:00Z',
            'determination_publication_date': None,
            'page_modified_datetime': '2025-06-01T12:30:00Z',
            'anzsic_codes': [{'code': '0600', 'name': 'Coal Mining'}],
            'acquirers': ['E'], 'targets': ['F'], 'other_parties': [],
            'url': 'https://example.com/MN-9103',
            'events': [
                {'title': 'Merger notified to ACCC', 'date': '2025-04-05T09:00:00Z'},
                {'title': 'Decision to Proceed to a Phase 2 review', 'date': '2025-06-01T12:00:00Z'},
            ],
        },
        {
            'merger_id': 'MN-9104',
            'merger_name': 'Outcome in progress',
            'status': 'Under assessment',
            'accc_determination': None,
            'stage': 'Phase 1 - preliminary assessment',
            'effective_notification_datetime': '2025-05-15T09:00:00Z',
            'determination_publication_date': None,
            'page_modified_datetime': '2025-05-15T09:30:00Z',
            'anzsic_codes': [{'code': '0600', 'name': 'Coal Mining'}],
            'acquirers': ['G'], 'targets': ['H'], 'other_parties': [],
            'url': 'https://example.com/MN-9104',
            'events': [
                {'title': 'Merger notified to ACCC', 'date': '2025-05-15T09:00:00Z'},
            ],
        },
        {
            'merger_id': 'MN-9105',
            'merger_name': 'Outcome approved, dual-tagged same division',
            'status': 'Determined',
            'accc_determination': 'Approved',
            'stage': 'Phase 1 - preliminary assessment',
            'effective_notification_datetime': '2025-01-25T09:00:00Z',
            'determination_publication_date': '2025-02-25T12:00:00Z',
            'page_modified_datetime': '2025-02-25T12:30:00Z',
            'anzsic_codes': [
                {'code': '0600', 'name': 'Coal Mining'},
                {'code': '0801', 'name': 'Iron Ore Mining'},
            ],
            'acquirers': ['I'], 'targets': ['J'], 'other_parties': [],
            'url': 'https://example.com/MN-9105',
            'events': [
                {'title': 'Merger notified to ACCC', 'date': '2025-01-25T09:00:00Z'},
                {'title': 'Phase 1 - Determination', 'date': '2025-02-25T12:00:00Z'},
            ],
        },
        {
            'merger_id': 'WA-9106',
            'merger_name': 'Excluded waiver',
            'status': 'Determined',
            'accc_determination': 'Waiver granted',
            'stage': 'Waiver',
            'effective_notification_datetime': '2025-01-01T09:00:00Z',
            'determination_publication_date': '2025-01-15T12:00:00Z',
            'page_modified_datetime': '2025-01-15T12:30:00Z',
            'anzsic_codes': [{'code': '0600', 'name': 'Coal Mining'}],
            'acquirers': ['K'], 'targets': ['L'], 'other_parties': [],
            'url': 'https://example.com/WA-9106',
            'events': [
                {'title': 'Waiver application received', 'date': '2025-01-01T09:00:00Z'},
            ],
        },
    ]


def _outcomes_enriched_fixture():
    return [enrich_merger(m) for m in _outcomes_fixture_raw()]


class TestOutcomesByDivision:
    def test_counts_and_referral_rate(self):
        payload = analysis.generate(_outcomes_enriched_fixture())
        divisions = payload['outcomes_by_division']
        assert [d['code'] for d in divisions] == ['B']
        mining = divisions[0]
        # MN-9101 + MN-9105 approved, MN-9102 not approved, MN-9103 referred,
        # MN-9104 in progress. WA-9106 is a waiver, excluded entirely.
        assert mining['approved'] == 2
        assert mining['not_approved'] == 1
        assert mining['referred'] == 1
        assert mining['in_progress'] == 1
        # referred / (approved + not_approved + referred) = 1 / 4
        assert mining['phase2_referral_rate'] == 0.25

    def test_dual_tagged_merger_deduped_within_division(self):
        # MN-9105 is tagged with two codes (0600, 0801) that both roll up to
        # division B — it must be counted once, not twice.
        payload = analysis.generate(_outcomes_enriched_fixture())
        mining = next(d for d in payload['outcomes_by_division'] if d['code'] == 'B')
        assert mining['approved'] + mining['not_approved'] + mining['referred'] + mining['in_progress'] == 5

    def test_reconciles_with_stats_by_determination(self):
        enriched = _outcomes_enriched_fixture()
        analysis_payload = analysis.generate(enriched)
        stats_payload = stats.generate(enriched)

        mining = next(d for d in analysis_payload['outcomes_by_division'] if d['code'] == 'B')
        by_det = stats_payload['by_determination']
        assert mining['approved'] == by_det.get(merger_status.APPROVED, 0)
        assert mining['not_approved'] == by_det.get(merger_status.NOT_APPROVED, 0)
        assert mining['referred'] == by_det.get(merger_status.REFERRED_TO_PHASE_2, 0)


class TestReferralsByQuarter:
    def test_buckets_by_notification_quarter(self):
        payload = analysis.generate(_outcomes_enriched_fixture())
        by_quarter = {q['quarter']: q for q in payload['referrals_by_quarter']}
        # MN-9101, MN-9102, MN-9105 notified in Q1 2025; MN-9103, MN-9104 in Q2.
        assert by_quarter['2025-Q1']['notifications'] == 3
        assert by_quarter['2025-Q1']['referred'] == 0
        assert by_quarter['2025-Q2']['notifications'] == 2
        # MN-9103 was referred (notified Q2, referral event also lands in Q2,
        # but bucketing follows the notification date regardless).
        assert by_quarter['2025-Q2']['referred'] == 1

    def test_sorted_ascending_by_quarter(self):
        payload = analysis.generate(_outcomes_enriched_fixture())
        quarters = [q['quarter'] for q in payload['referrals_by_quarter']]
        assert quarters == sorted(quarters)

    def test_totals_reconcile_with_stats(self):
        enriched = _outcomes_enriched_fixture()
        analysis_payload = analysis.generate(enriched)
        stats_payload = stats.generate(enriched)

        total_notifications = sum(q['notifications'] for q in analysis_payload['referrals_by_quarter'])
        total_referred = sum(q['referred'] for q in analysis_payload['referrals_by_quarter'])

        assert total_notifications == stats_payload['total_mergers']
        assert total_referred == stats_payload['by_determination'].get(merger_status.REFERRED_TO_PHASE_2, 0)


# ---------------------------------------------------------------------------
# analysis.by_commission_division
# ---------------------------------------------------------------------------

def _commission_division_fixture():
    """Five mergers exercising the by_commission_division normalisation: the
    same delegate spelled two ways (with/without a first name, plus
    whitespace/case noise), a corrupted over-length extraction, a
    determination with no division parsed, and a waiver decided by a delegate
    who otherwise only appears on notifications."""
    raw = [
        {
            'merger_id': 'MN-1001',
            'merger_name': 'Iota acquires Kappa',
            'status': 'Determined',
            'accc_determination': 'Approved',
            'stage': 'Phase 1 - preliminary assessment',
            'effective_notification_datetime': '2025-01-06T09:00:00Z',
            'determination_publication_date': '2025-02-05T12:00:00Z',
            'page_modified_datetime': '2025-02-05T12:30:00Z',
            'anzsic_codes': [],
            'acquirers': [], 'targets': [], 'other_parties': [],
            'url': 'https://example.com/MN-1001',
            'events': [{
                'title': 'Phase 1 - Determination',
                'date': '2025-02-05T12:00:00Z',
                'url': 'e1',
                'determination_commission_division': (
                    'Determination made by Commissioner  Philip Williams pursuant to a\n'
                    'delegation under section 25(1) of the Act'
                ),
            }],
        },
        {
            'merger_id': 'MN-1002',
            'merger_name': 'Lambda acquires Mu',
            'status': 'Determined',
            'accc_determination': 'Not opposed',
            'stage': 'Phase 1 - preliminary assessment',
            'effective_notification_datetime': '2025-02-10T09:00:00Z',
            'determination_publication_date': '2025-03-12T12:00:00Z',
            'page_modified_datetime': '2025-03-12T12:30:00Z',
            'anzsic_codes': [],
            'acquirers': [], 'targets': [], 'other_parties': [],
            'url': 'https://example.com/MN-1002',
            'events': [{
                'title': 'Phase 1 - Determination',
                'date': '2025-03-12T12:00:00Z',
                'url': 'e2',
                # Same delegate as MN-1001's, but without the first name, and
                # differing in case/whitespace too.
                'determination_commission_division': (
                    'determination made by commissioner williams pursuant to a '
                    'delegation under section 25(1) of the act'
                ),
            }],
        },
        {
            'merger_id': 'MN-1003',
            'merger_name': 'Nu acquires Xi',
            'status': 'Determined',
            'accc_determination': 'Approved',
            'stage': 'Phase 1 - preliminary assessment',
            'effective_notification_datetime': '2025-01-20T09:00:00Z',
            'determination_publication_date': '2025-02-19T12:00:00Z',
            'page_modified_datetime': '2025-02-19T12:30:00Z',
            'anzsic_codes': [],
            'acquirers': [], 'targets': [], 'other_parties': [],
            'url': 'https://example.com/MN-1003',
            'events': [{
                'title': 'Phase 1 - Determination',
                'date': '2025-02-19T12:00:00Z',
                'url': 'e3',
                # A corrupted extraction (no "of the Act" marker nearby) that
                # captured far more than the division sentence.
                'determination_commission_division': 'Determination made by the Commission ' + 'x' * 300,
            }],
        },
        {
            'merger_id': 'MN-1004',
            'merger_name': 'Omicron acquires Pi',
            'status': 'Determined',
            'accc_determination': 'Approved',
            'stage': 'Phase 1 - preliminary assessment',
            'effective_notification_datetime': '2025-03-01T09:00:00Z',
            'determination_publication_date': '2025-03-31T12:00:00Z',
            'page_modified_datetime': '2025-03-31T12:30:00Z',
            'anzsic_codes': [],
            'acquirers': [], 'targets': [], 'other_parties': [],
            'url': 'https://example.com/MN-1004',
            'events': [
                # No determination_commission_division parsed at all.
                {'title': 'Phase 1 - Determination', 'date': '2025-03-31T12:00:00Z', 'url': 'e4'},
            ],
        },
        {
            'merger_id': 'WA-1005',
            'merger_name': 'Rho waiver',
            'status': 'Determined',
            'accc_determination': 'Approved',
            'stage': 'Waiver',
            'effective_notification_datetime': '2025-04-01T09:00:00Z',
            'determination_publication_date': '2025-04-15T12:00:00Z',
            'page_modified_datetime': '2025-04-15T12:30:00Z',
            'anzsic_codes': [],
            'acquirers': [], 'targets': [], 'other_parties': [],
            'url': 'https://example.com/WA-1005',
            'events': [{
                'title': 'Waiver determination',
                'date': '2025-04-15T12:00:00Z',
                'url': 'e5',
                # Same delegate as MN-1001/MN-1002, but this merger is a
                # waiver, so it has no Phase 1 review to measure.
                'determination_commission_division': (
                    'Determination made by Commissioner Williams pursuant to a '
                    'delegation under section 25(1) of the Act'
                ),
            }],
        },
    ]
    return [enrich_merger(m) for m in raw]


class TestByCommissionDivision:
    def test_collapses_delegate_name_variants(self):
        divisions = analysis.generate(_commission_division_fixture())['by_commission_division']
        williams = next(d for d in divisions if 'Williams' in d['division'])
        # MN-1001 ("Philip Williams"), MN-1002 ("Williams", different
        # case/whitespace) and WA-1005 ("Williams") all collapse to one
        # delegate.
        assert williams['count'] == 3
        # Display label is canonicalised to "<title> <surname>", not the raw sentence.
        assert williams['division'] == 'Commissioner Williams'
        assert williams['outcome_mix'] == {'Approved': 2, 'Not opposed': 1}

    def test_corrupted_and_missing_values_fold_into_unknown(self):
        divisions = analysis.generate(_commission_division_fixture())['by_commission_division']
        unknown = next(d for d in divisions if d['division'] == 'Unknown')
        assert unknown['count'] == 2

    def test_median_phase_1_business_days_uses_the_subset(self):
        divisions = analysis.generate(_commission_division_fixture())['by_commission_division']
        williams = next(d for d in divisions if 'Williams' in d['division'])
        # WA-1005 is a waiver and contributes no Phase 1 duration, but
        # MN-1001/MN-1002 do, so the bucket's median isn't null just because
        # one contributing merger has no Phase 1 review.
        assert williams['median_phase_1_business_days'] is not None

    def test_waiver_only_division_has_null_median(self):
        # A delegate whose only determinations in this fixture are waivers
        # has no Phase 1 duration to report — expected, not a bug, since
        # collect_phase_1_durations only measures notifications.
        raw = [{
            'merger_id': 'WA-2001',
            'merger_name': 'Sigma waiver',
            'status': 'Determined',
            'accc_determination': 'Approved',
            'stage': 'Waiver',
            'effective_notification_datetime': '2025-05-01T09:00:00Z',
            'determination_publication_date': '2025-05-15T12:00:00Z',
            'page_modified_datetime': '2025-05-15T12:30:00Z',
            'anzsic_codes': [],
            'acquirers': [], 'targets': [], 'other_parties': [],
            'url': 'https://example.com/WA-2001',
            'events': [{
                'title': 'Waiver determination',
                'date': '2025-05-15T12:00:00Z',
                'url': 'e6',
                'determination_commission_division': (
                    'Determination made by Chair Cass-Gottlieb pursuant to a '
                    'delegation under section 25(1) of the Act'
                ),
            }],
        }]
        divisions = analysis.generate([enrich_merger(m) for m in raw])['by_commission_division']
        assert divisions[0]['division'] == 'Chair Cass-Gottlieb'
        assert divisions[0]['median_phase_1_business_days'] is None

    def test_collapses_division_of_commission_wording_variants(self):
        # A determination says "Determination made by ... of the Act"; a
        # Phase 2 Notice says "Decision made by ... of the Competition and
        # Consumer Act 2010 (Cth)" for the same kind of body. Both should
        # collapse to one canonical bucket.
        raw = [
            {
                'merger_id': 'MN-3001',
                'merger_name': 'Tau acquires Upsilon',
                'status': 'Determined',
                'accc_determination': 'Approved',
                'stage': 'Phase 1 - preliminary assessment',
                'effective_notification_datetime': '2025-06-01T09:00:00Z',
                'determination_publication_date': '2025-06-30T12:00:00Z',
                'page_modified_datetime': '2025-06-30T12:30:00Z',
                'anzsic_codes': [],
                'acquirers': [], 'targets': [], 'other_parties': [],
                'url': 'https://example.com/MN-3001',
                'events': [{
                    'title': 'Phase 1 - Determination',
                    'date': '2025-06-30T12:00:00Z',
                    'url': 'e7',
                    'determination_commission_division': (
                        'Determination made by a division of the Commission '
                        'constituted by a direction issued pursuant to section 19 of the Act'
                    ),
                }],
            },
            {
                'merger_id': 'MN-3002',
                'merger_name': 'Phi acquires Chi',
                'status': 'Assessment ceased',
                'accc_determination': None,
                'stage': 'Phase 2 - detailed assessment',
                'effective_notification_datetime': '2025-06-05T09:00:00Z',
                'determination_publication_date': None,
                'page_modified_datetime': '2025-07-01T09:30:00Z',
                'anzsic_codes': [],
                'acquirers': [], 'targets': [], 'other_parties': [],
                'url': 'https://example.com/MN-3002',
                'events': [{
                    'title': 'Phi - Chi - Phase 2 Notice',
                    'date': '2025-07-01T09:00:00Z',
                    'url': 'e8',
                    'phase2_notice_matters_to_investigate': [],
                    'phase2_notice_commission_division': (
                        'Decision made by a division of the Commission constituted by a '
                        'direction issued pursuant to section 19 of the Competition and '
                        'Consumer Act 2010 (Cth)'
                    ),
                }],
            },
        ]
        divisions = analysis.generate([enrich_merger(m) for m in raw])['by_commission_division']
        assert len(divisions) == 1
        assert divisions[0]['division'] == 'A division of the Commission (s19 direction)'
        assert divisions[0]['count'] == 2

    def test_final_determination_takes_precedence_over_phase2_notice(self):
        # A matter referred to Phase 2 and later determined by a named
        # delegate shouldn't have its bucket overridden by the earlier Phase
        # 2 Notice's division event.
        raw = [{
            'merger_id': 'MN-3003',
            'merger_name': 'Psi acquires Omega',
            'status': 'Determined',
            'accc_determination': 'Approved',
            'stage': 'Phase 2 - detailed assessment',
            'effective_notification_datetime': '2025-06-05T09:00:00Z',
            'determination_publication_date': '2025-09-01T12:00:00Z',
            'page_modified_datetime': '2025-09-01T12:30:00Z',
            'anzsic_codes': [],
            'acquirers': [], 'targets': [], 'other_parties': [],
            'url': 'https://example.com/MN-3003',
            'events': [
                {
                    'title': 'Psi - Omega - Phase 2 Notice',
                    'date': '2025-07-01T09:00:00Z',
                    'url': 'e9',
                    'phase2_notice_matters_to_investigate': [],
                    'phase2_notice_commission_division': (
                        'Decision made by a division of the Commission constituted by a '
                        'direction issued pursuant to section 19 of the Competition and '
                        'Consumer Act 2010 (Cth)'
                    ),
                },
                {
                    'title': 'Phase 2 - Determination',
                    'date': '2025-09-01T12:00:00Z',
                    'url': 'e10',
                    'determination_commission_division': (
                        'Determination made by Commissioner Woodward pursuant to a '
                        'delegation under section 25(1) of the Act'
                    ),
                },
            ],
        }]
        divisions = analysis.generate([enrich_merger(m) for m in raw])['by_commission_division']
        assert divisions[0]['division'] == 'Commissioner Woodward'


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


# ---------------------------------------------------------------------------
# theories_of_harm
# ---------------------------------------------------------------------------
#
# Fixtures below are real "matters the ACCC intends to investigate" and NOCC
# excerpts from the live dataset (Ampol/EG Australia MN-01019, Coles/Kalgoorlie
# MN-01068, Kegstar/Konvoy MN-30003, IAG/RACI MN-65005, calibration services
# MN-90009), trimmed to the sentences that exercise each category.

def _phase2_matters_fixture():
    return [
        {
            'merger_id': 'MN-90009',
            'merger_name': 'Calibration Co acquires Rival Labs',
            'events': [
                {
                    'title': 'Phase 2 Notice',
                    'phase2_notice_matters_to_investigate': [
                        {
                            'heading': 'Competition effects in the supply of calibration services in certain testing domains',
                            'items': [
                                'The extent to which alternative suppliers would meaningfully constrain the merged entity post-Acquisition in the supply of calibration services in certain testing domains, taking into account factors such as their scope of accreditation, breadth of service offering, price and turnaround times, particularly in relation to the following testing domains: electrical, radiofrequency, torque and force.',
                                'The likelihood of timely new entry and expansion to constrain the merged entity in the electrical, radiofrequency, torque and force testing domains.',
                            ],
                        },
                        {
                            'heading': 'Competition effects in the supply of calibration services to customers that require multiple calibration services across a range of testing domains',
                            'items': [
                                'The extent to which multiple suppliers could enter into arrangements that enable a single supplier from the group to offer all of their calibration services, across the range of their testing domains, to customers.',
                            ],
                        },
                    ],
                },
            ],
        },
        {
            'merger_id': 'MN-65005',
            'merger_name': 'IAG acquires RACI',
            'events': [
                {
                    'title': 'Phase 2 Notice',
                    'phase2_notice_matters_to_investigate': [
                        {
                            'heading': 'Competitive effects in the retail supply of home and contents insurance in Western Australia',
                            'items': [
                                'The extent to which IAG and RACI compete closely in Western Australia, including in relation to price, coverage and other terms of the insurance product offering, customer service, claims handling and renewals.',
                                'The competitive significance of RACI in Western Australia, and the likely future competitiveness of RACI absent the Acquisition (taking into account RACI’s position as a state-based organisation, capital adequacy requirements, and RACI’s ability to raise capital).',
                                'The extent to which IAG would be in an enhanced position to foreclose or frustrate competing insurers’ access to repairers post-Acquisition.',
                            ],
                        },
                    ],
                },
            ],
        },
        {
            'merger_id': 'MN-30003',
            'merger_name': 'MicroStar acquires Konvoy',
            'events': [
                {
                    'title': 'Phase 2 Notice',
                    'phase2_notice_matters_to_investigate': [
                        {
                            'heading': 'Competition effects in the supply of keg pooling services',
                            'items': [
                                'The extent to which customer countervailing power would provide a competitive constraint on MicroStar after the Acquisition. The likelihood of timely new entry if the Acquisition proceeds.',
                            ],
                        },
                    ],
                },
            ],
        },
        {
            'merger_id': 'MN-01019',
            'merger_name': 'Ampol acquires EG Australia',
            'events': [
                {
                    'title': 'Phase 2 Notice',
                    'phase2_notice_matters_to_investigate': [
                        {
                            'heading': 'Relevant areas of competition',
                            'items': [
                                'The factors taken into account by fuel retailers when setting prices at retail sites, including the extent to which metropolitan-wide pricing movements are considered.',
                                'The appropriate geographic dimensions of competition, including traffic routes and natural barriers in specific local areas and the extent to which consumers travel to purchase fuel.',
                            ],
                        },
                    ],
                },
            ],
        },
    ]


def _nocc_fixture():
    return {
        'MN-01019': {
            'sections': [
                {
                    'number': '5',
                    'title': 'Summary of preliminary competition concerns',
                    'blocks': [
                        {
                            'number': '5.9',
                            'type': 'paragraph',
                            'text': (
                                'In Canberra, which does not have petrol price cycles, the Acquisition '
                                'would remove a direct competitor to Ampol and lead to Ampol becoming the '
                                'largest fuel retailer in that metropolitan market. The ACCC’s preliminary '
                                'assessment is that the Acquisition would have the effect, or likely effect, '
                                'of substantially lessening competition in the retail supply of fuel in '
                                'Canberra from coordinated effects becoming more likely, more complete '
                                'and/or more sustainable across the remaining retailers. The ACCC is '
                                'continuing to consider the potential for the Acquisition to give rise to '
                                'unilateral effects in Canberra.'
                            ),
                        },
                    ],
                },
            ],
        },
        'MN-65005': {
            'sections': [
                {
                    'number': '5',
                    'title': 'Summary of preliminary competition assessment',
                    'blocks': [
                        {
                            'number': '5.35',
                            'type': 'paragraph',
                            'text': (
                                'Barriers to entry and/or expansion applicable to the supply of motor '
                                'insurance include significant capital requirements, high sunk costs, '
                                'licensing timeframes, strict regulatory obligations, brand loyalty, and '
                                'limited access to repair services networks and skilled employees.'
                            ),
                        },
                        {
                            'number': '5.48',
                            'type': 'paragraph',
                            'text': (
                                'As such, the Acquisition could result in IAG gaining monopsony power in '
                                'the acquisition of smash repair services in Western Australia and/or '
                                'certain regions in Western Australia.'
                            ),
                        },
                        {
                            'type': 'bullet_list',
                            'items': [
                                'IAG is a strong and effective competitor in Western Australia.',
                            ],
                        },
                    ],
                },
            ],
        },
    }


class TestTheoriesOfHarmGenerate:
    def test_returns_all_seven_categories(self):
        payload = theories_of_harm.generate(_phase2_matters_fixture(), _nocc_fixture())
        json.dumps(payload)
        assert set(payload['categories']) == {
            'horizontal_unilateral_effects', 'coordinated_effects', 'vertical_foreclosure',
            'conglomerate_bundling', 'potential_nascent_competition', 'buyer_power', 'entry_barriers',
        }

    def test_horizontal_unilateral_effects_from_real_excerpts(self):
        payload = theories_of_harm.generate(_phase2_matters_fixture(), {})
        excerpts = {m['excerpt'] for m in payload['categories']['horizontal_unilateral_effects']['matters']}
        assert any('meaningfully constrain the merged entity' in e for e in excerpts)
        assert any('compete closely in Western Australia' in e for e in excerpts)

    def test_coordinated_effects_from_real_nocc_excerpt(self):
        payload = theories_of_harm.generate([], _nocc_fixture())
        matters = payload['categories']['coordinated_effects']['matters']
        assert len(matters) == 1
        assert matters[0]['merger_id'] == 'MN-01019'
        assert matters[0]['source'] == 'nocc'
        assert 'coordinated effects' in matters[0]['excerpt'].lower()

    def test_vertical_foreclosure_from_real_excerpts(self):
        payload = theories_of_harm.generate(_phase2_matters_fixture(), {})
        matters = payload['categories']['vertical_foreclosure']['matters']
        assert any(m['merger_id'] == 'MN-65005' for m in matters)

    def test_conglomerate_bundling_from_real_excerpt(self):
        payload = theories_of_harm.generate(_phase2_matters_fixture(), {})
        matters = payload['categories']['conglomerate_bundling']['matters']
        assert len(matters) == 1
        assert matters[0]['merger_id'] == 'MN-90009'
        assert matters[0]['matched_phrase'] == 'single supplier'

    def test_potential_nascent_competition_from_real_excerpt(self):
        payload = theories_of_harm.generate(_phase2_matters_fixture(), {})
        matters = payload['categories']['potential_nascent_competition']['matters']
        assert any('future competitiveness of RACI' in m['excerpt'] for m in matters)

    def test_buyer_power_from_real_excerpts(self):
        payload = theories_of_harm.generate(_phase2_matters_fixture(), _nocc_fixture())
        matters = payload['categories']['buyer_power']['matters']
        merger_ids = {m['merger_id'] for m in matters}
        assert 'MN-30003' in merger_ids  # "customer countervailing power" (phase2 matter)
        assert 'MN-65005' in merger_ids  # "monopsony power" (NOCC)

    def test_entry_barriers_from_real_excerpts(self):
        payload = theories_of_harm.generate(_phase2_matters_fixture(), _nocc_fixture())
        matters = payload['categories']['entry_barriers']['matters']
        merger_ids = {m['merger_id'] for m in matters}
        assert 'MN-90009' in merger_ids  # "timely new entry" (phase2 matter)
        assert 'MN-65005' in merger_ids  # "Barriers to entry" (NOCC)

    def test_unmatched_matter_goes_to_unclassified(self):
        payload = theories_of_harm.generate(_phase2_matters_fixture(), {})
        excerpts = {m['excerpt'] for m in payload['unclassified']['matters']}
        assert any('metropolitan-wide pricing movements' in e for e in excerpts)

    def test_natural_barriers_is_not_misclassified_as_entry_barrier(self):
        # Guards against an overly-broad "barrier" keyword: this excerpt is
        # about geographic/demand-side market definition, not barriers to
        # entry for rival suppliers, so it must not land in entry_barriers.
        payload = theories_of_harm.generate(_phase2_matters_fixture(), {})
        entry_excerpts = {m['excerpt'] for m in payload['categories']['entry_barriers']['matters']}
        assert not any('natural barriers' in e for e in entry_excerpts)
        unclassified_excerpts = {m['excerpt'] for m in payload['unclassified']['matters']}
        assert any('natural barriers' in e for e in unclassified_excerpts)

    def test_every_matter_to_investigate_item_is_classified_or_unclassified(self):
        mergers = _phase2_matters_fixture()
        payload = theories_of_harm.generate(mergers, {})
        raw_items = [
            item
            for m in mergers
            for event in m['events']
            for box in event['phase2_notice_matters_to_investigate']
            for item in box['items']
        ]
        classified_excerpts = {
            m['excerpt']
            for cat in payload['categories'].values()
            for m in cat['matters']
        }
        unclassified_excerpts = {m['excerpt'] for m in payload['unclassified']['matters']}
        assert not (classified_excerpts & unclassified_excerpts)
        for item in raw_items:
            assert item in classified_excerpts or item in unclassified_excerpts

    def test_nocc_text_with_no_keyword_match_is_simply_omitted(self):
        # Unlike phase2 matters, NOCC prose has no enumerable "one entry per
        # matter" structure, so non-matching text isn't tracked anywhere
        # (there's no NOCC-side unclassified bucket).
        payload = theories_of_harm.generate([], _nocc_fixture())
        all_excerpts = {
            m['excerpt']
            for cat in payload['categories'].values()
            for m in cat['matters']
        }
        assert not any('strong and effective competitor' in e for e in all_excerpts)
        assert payload['unclassified']['matters'] == []
