"""Tests for the quarterly report output (quarterly.json)."""

import sys
import unittest.mock
from datetime import date

# Mock heavy transitive imports before importing modules that need them
sys.modules.setdefault('pdfplumber', unittest.mock.MagicMock())
sys.modules.setdefault('markdownify', unittest.mock.MagicMock())
sys.modules.setdefault('requests', unittest.mock.MagicMock())

from scripts.generate.static_data.outputs import quarterly


def _notification(merger_id, filed, phase_1=None, phase_1_date=None, **extra):
    merger = {
        'merger_id': merger_id,
        'merger_name': f'{merger_id} deal',
        'is_waiver': False,
        'status': 'Under assessment' if not phase_1 else 'Assessment completed',
        'stage': 'Phase 1 - initial assessment',
        'effective_notification_datetime': f'{filed}T12:00:00Z',
        'phase_1_determination': phase_1,
        'phase_1_determination_date': f'{phase_1_date}T12:00:00Z' if phase_1_date else None,
        'acquirers': [{'name': 'Acquirer Pty Ltd', 'identifier_type': 'ABN', 'identifier': '1'}],
        'targets': [{'name': 'Target Pty Ltd', 'identifier_type': 'ACN', 'identifier': '2'}],
        'anzsic_codes': [],
        'events': [],
    }
    merger.update(extra)
    return merger


def _waiver(merger_id, filed, decided, determination='Approved', **extra):
    merger = {
        'merger_id': merger_id,
        'merger_name': f'{merger_id} waiver',
        'is_waiver': True,
        'status': 'Assessment completed',
        'stage': 'Waiver application',
        'effective_notification_datetime': f'{filed}T12:00:00Z',
        'determination_publication_date': f'{decided}T12:00:00Z',
        'accc_determination': determination,
        'acquirers': [],
        'targets': [],
        'anzsic_codes': [],
        'events': [],
    }
    merger.update(extra)
    return merger


AS_AT = date(2026, 10, 22)


def _quarter(payload, key):
    return next(q for q in payload['quarters'] if q['quarter'] == key)


class TestQuarterRange:
    def test_runs_from_the_mandatory_regime_to_the_current_quarter(self):
        payload = quarterly.generate([], as_at=AS_AT)
        assert [q['quarter'] for q in payload['quarters']] == [
            '2026-Q1', '2026-Q2', '2026-Q3', '2026-Q4',
        ]

    def test_only_the_current_quarter_is_incomplete(self):
        payload = quarterly.generate([], as_at=AS_AT)
        assert [q['complete'] for q in payload['quarters']] == [True, True, True, False]
        q3 = _quarter(payload, '2026-Q3')
        assert (q3['start'], q3['end'], q3['label']) == ('2026-07-01', '2026-09-30', 'Q3 2026')

    def test_quarter_ending_yesterday_is_complete(self):
        payload = quarterly.generate([], as_at=date(2026, 10, 1))
        assert _quarter(payload, '2026-Q3')['complete'] is True

    def test_bucket_labels_match_bucket_counts(self):
        payload = quarterly.generate([_waiver('WA-1', '2026-07-01', '2026-07-03')], as_at=AS_AT)
        q3 = _quarter(payload, '2026-Q3')
        assert len(payload['duration_buckets']) == len(q3['waivers']['timing']['buckets'])
        assert payload['duration_buckets'][0] == '0–4'
        assert payload['duration_buckets'][-1] == '50+'


class TestBucketing:
    def test_filings_count_by_filing_date_and_decisions_by_decision_date(self):
        # Filed in Q2, decided in Q3: inflow belongs to Q2, the decision to Q3.
        m = _notification('MN-1', '2026-06-25', 'Approved', '2026-07-20')
        payload = quarterly.generate([m], as_at=AS_AT)
        q2, q3 = _quarter(payload, '2026-Q2'), _quarter(payload, '2026-Q3')
        assert q2['notifications']['filed'] == 1
        assert q2['notifications']['phase_1_decided'] == 0
        assert q3['notifications']['filed'] == 0
        assert q3['notifications']['phase_1_decided'] == 1

    def test_referral_counts_as_a_phase_1_decision_measured_to_the_referral(self):
        cleared = _notification('MN-1', '2026-07-01', 'Approved', '2026-07-22')
        referred = _notification(
            'MN-2', '2026-07-01', 'Referred to phase 2', '2026-08-12',
            phase_2_determination='Not approved', phase_2_determination_date='2026-12-01T12:00:00Z',
        )
        n = _quarter(quarterly.generate([cleared, referred], as_at=AS_AT), '2026-Q3')['notifications']
        assert n['phase_1_decided'] == 2
        assert n['cleared'] == 1
        assert n['referred_to_phase_2'] == 1
        assert n['clearance_rate'] == 0.5
        # 1 Jul → 12 Aug is 30 business days; the later phase 2 date never counts.
        assert n['average_referred'] == 30
        assert n['timing']['count'] == 2

    def test_waiver_outcomes_and_refiles(self):
        waivers = [
            _waiver('WA-1', '2026-07-01', '2026-07-15'),
            _waiver('WA-2', '2026-07-01', '2026-07-22', 'Not approved',
                    related_merger={'merger_id': 'MN-9', 'relationship': 'refiled_as'}),
            _waiver('WA-3', '2026-07-01', '2026-07-22', 'Not approved'),
        ]
        w = _quarter(quarterly.generate(waivers, as_at=AS_AT), '2026-Q3')['waivers']
        assert (w['decided'], w['granted'], w['refused'], w['refused_refiled']) == (3, 1, 2, 1)
        assert w['clearance_rate'] == round(1 / 3, 4)
        assert w['average_granted'] == 10
        assert w['average_refused'] == 15

    def test_empty_quarter_has_no_rates(self):
        q1 = _quarter(quarterly.generate([], as_at=AS_AT), '2026-Q1')
        assert q1['notifications']['clearance_rate'] is None
        assert q1['waivers']['timing']['median'] is None
        assert q1['waivers']['timing']['buckets'] == [0] * len(quarterly.DURATION_BUCKETS + [None])


class TestMilestones:
    def test_post_phase_1_milestones_land_in_their_own_quarters(self):
        m = _notification(
            'MN-1', '2026-03-02', 'Referred to phase 2', '2026-04-14',
            stage='Phase 2 - detailed assessment',
            phase_2_determination='Approved', phase_2_determination_date='2026-08-20T12:00:00Z',
            has_conditions=True,
            appeals=[{'filed_date': '2026-10-02', 'appellant': 'Rival'}],
        )
        payload = quarterly.generate([m], as_at=AS_AT)
        assert [e['kind'] for e in _quarter(payload, '2026-Q2')['milestones']] == ['referred']
        q3 = _quarter(payload, '2026-Q3')['milestones']
        assert q3 == [{
            'merger_id': 'MN-1', 'merger_name': 'MN-1 deal', 'kind': 'phase_2_outcome',
            'date': '2026-08-20', 'detail': 'Approved with conditions',
        }]
        q4 = _quarter(payload, '2026-Q4')['milestones']
        assert [(e['kind'], e['detail']) for e in q4] == [('tribunal_application', 'Rival')]

    def test_a_phase_1_cessation_is_its_own_milestone(self):
        m = _notification('MN-1', '2026-07-01', status='Assessment ceased', ceased_date='2026-07-20T12:00:00Z')
        q3 = _quarter(quarterly.generate([m], as_at=AS_AT), '2026-Q3')
        assert [e['kind'] for e in q3['milestones']] == ['ceased']
        assert q3['notifications']['ceased'] == 1
        assert q3['notifications']['phase_1_decided'] == 0


class TestOverseasParty:
    def test_australian_identifier_is_never_overseas(self):
        assert not quarterly.is_overseas_party({'name': 'Acme Inc', 'identifier_type': 'ABN', 'identifier': '1'})

    def test_foreign_registry_number_is_overseas(self):
        assert quarterly.is_overseas_party({'name': 'Rominvest', 'identifier_type': None, 'identifier': 'VAT 0172'})

    def test_overseas_legal_form_without_a_number(self):
        for name in ['Salsa Bidco, Inc.', 'Equans SAS', 'Rominvest S.p.A.', 'TDR Capital LLP', 'Foo GmbH']:
            assert quarterly.is_overseas_party({'name': name, 'identifier_type': None, 'identifier': ''}), name

    def test_ambiguous_names_are_left_out(self):
        for name in [
            'Smiths Detection Group Limited',
            'Glenn Family Trust',
            'Jane Citizen',
            'K & K RYAN PTY LTD (ACN 623119960) AS TRUSTEE',
            'APL Investments (Pty) Ltd',
        ]:
            assert not quarterly.is_overseas_party({'name': name, 'identifier_type': None, 'identifier': ''}), name

    def test_share_counts_filings_and_decided_waivers(self):
        overseas = [{'name': 'Bidco Inc', 'identifier_type': None, 'identifier': ''}]
        mergers = [
            _notification('MN-1', '2026-07-01', targets=overseas),
            _notification('MN-2', '2026-07-01'),
            _waiver('WA-1', '2026-06-20', '2026-07-03', acquirers=overseas),
        ]
        q3 = _quarter(quarterly.generate(mergers, as_at=AS_AT), '2026-Q3')
        assert (q3['matters'], q3['overseas_party']) == (3, 2)


class TestIndustries:
    def test_each_matter_counts_once_per_division(self):
        mergers = [
            _notification('MN-1', '2026-07-01', anzsic_codes=[{'code': '6322'}, {'code': '632'}]),
            _notification('MN-2', '2026-07-01', anzsic_codes=[{'code': '6322'}, {'code': '1211'}]),
        ]
        industries = _quarter(quarterly.generate(mergers, as_at=AS_AT), '2026-Q3')['industries']
        assert industries[0] == {'code': 'K', 'name': industries[0]['name'], 'count': 2}
        assert {i['code']: i['count'] for i in industries} == {'K': 2, 'C': 1}


def _summary(key, label, *, complete=True, filed=100, decided=150, p1_median=17, w_median=12,
             referred=2, milestones=()):
    return {
        'quarter': key, 'label': label, 'complete': complete,
        'notifications': {
            'filed': filed, 'phase_1_decided': 90, 'referred_to_phase_2': referred,
            'clearance_rate': 88 / 90, 'timing': {'median': p1_median},
        },
        'waivers': {'decided': decided, 'clearance_rate': 0.96, 'timing': {'median': w_median}},
        'milestones': list(milestones),
    }


Q2 = _summary('2026-Q2', 'Q2 2026')
Q3 = _summary('2026-Q3', 'Q3 2026', filed=113, decided=183, p1_median=18, w_median=17, milestones=[
    {'kind': 'phase_2_outcome', 'detail': 'Not approved'},
    {'kind': 'phase_2_outcome', 'detail': 'Not approved'},
    {'kind': 'phase_2_outcome', 'detail': 'Assessment ceased'},
    {'kind': 'tribunal_application', 'detail': 'Coles'},
])
Q4 = _summary('2026-Q4', 'Q4 2026', complete=False, filed=29)


class TestFindings:
    def test_compares_volume_and_timing_with_the_previous_quarter(self):
        assert quarterly.findings(Q3, Q2) == [
            '113 notifications filed, up 13% on Q2 2026, and 183 waiver applications decided, up 22% on Q2 2026.',
            'Phase 1 reviews concluded in a median 18 business days, 1 day slower than Q2 2026; '
            'waivers in 17, 5 days slower than Q2 2026.',
            '96% of waivers were granted and 98% of phase 1 reviews ended in approval.',
            '2 matters referred to phase 2; 3 phase 2 reviews concluded (2 not approved, 1 assessment ceased).',
        ]

    def test_leaves_volume_uncompared_for_a_quarter_in_progress(self):
        assert quarterly.findings(Q4, Q3)[0] == '29 notifications filed, and 150 waiver applications decided.'

    def test_first_quarter_has_no_comparisons(self):
        assert quarterly.findings(Q2, None)[1] == (
            'Phase 1 reviews concluded in a median 17 business days; waivers in 12.'
        )

    def test_half_day_medians_keep_their_half(self):
        q = _summary('2026-Q4', 'Q4 2026', p1_median=19.5)
        assert 'median 19.5 business days, 1.5 days slower than Q3 2026' in quarterly.findings(q, Q3)[1]

    def test_every_quarter_carries_its_findings(self):
        payload = quarterly.generate([], as_at=AS_AT)
        assert all(isinstance(q['findings'], list) and q['findings'] for q in payload['quarters'])
