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
    def test_runs_from_the_mandatory_regime_to_the_last_complete_quarter(self):
        payload = quarterly.generate([], as_at=AS_AT)
        assert [q['quarter'] for q in payload['quarters']] == ['2026-Q1', '2026-Q2', '2026-Q3']

    def test_the_quarter_in_progress_is_left_out(self):
        assert [q['quarter'] for q in quarterly.generate([], as_at=date(2026, 9, 30))['quarters']] == [
            '2026-Q1', '2026-Q2',
        ]
        # The first day of a quarter publishes the one that just ended.
        assert quarterly.generate([], as_at=date(2026, 10, 1))['quarters'][-1]['quarter'] == '2026-Q3'
        # Across a year boundary.
        assert quarterly.generate([], as_at=date(2027, 2, 1))['quarters'][-1]['quarter'] == '2026-Q4'

    def test_nothing_before_the_first_quarter_ends(self):
        assert quarterly.generate([], as_at=date(2026, 3, 31))['quarters'] == []

    def test_quarter_bounds_and_label(self):
        q3 = _quarter(quarterly.generate([], as_at=AS_AT), '2026-Q3')
        assert (q3['start'], q3['end'], q3['label']) == ('2026-07-01', '2026-09-30', 'Q3 2026')
        assert 'complete' not in q3

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
        # A phase 2 outcome is listed as the outcome itself, with no separate detail.
        assert q3 == [{
            'merger_id': 'MN-1', 'merger_name': 'MN-1 deal', 'kind': 'phase_2_outcome',
            'date': '2026-08-20', 'label': 'Approved with conditions',
        }]
        q4 = _quarter(quarterly.generate([m], as_at=date(2027, 1, 5)), '2026-Q4')['milestones']
        assert [(e['label'], e['detail']) for e in q4] == [('Tribunal review sought', 'Rival')]

    def test_a_refusal_at_phase_1_does_not_repeat_itself(self):
        m = _notification('MN-1', '2026-07-01', 'Not approved', '2026-08-01')
        [milestone] = _quarter(quarterly.generate([m], as_at=AS_AT), '2026-Q3')['milestones']
        assert milestone['label'] == 'Not approved at phase 1'
        assert 'detail' not in milestone

    def test_a_phase_1_cessation_is_its_own_milestone(self):
        m = _notification('MN-1', '2026-07-01', status='Assessment ceased', ceased_date='2026-07-20T12:00:00Z')
        q3 = _quarter(quarterly.generate([m], as_at=AS_AT), '2026-Q3')
        assert [e['kind'] for e in q3['milestones']] == ['ceased']
        assert q3['notifications']['ceased'] == 1
        assert q3['notifications']['phase_1_decided'] == 0


class TestIndustries:
    def test_each_matter_counts_once_per_division(self):
        mergers = [
            _notification('MN-1', '2026-07-01', anzsic_codes=[{'code': '6322'}, {'code': '632'}]),
            _notification('MN-2', '2026-07-01', anzsic_codes=[{'code': '6322'}, {'code': '1211'}]),
        ]
        industries = _quarter(quarterly.generate(mergers, as_at=AS_AT), '2026-Q3')['industries']
        assert industries[0] == {'code': 'K', 'name': industries[0]['name'], 'count': 2}
        assert {i['code']: i['count'] for i in industries} == {'K': 2, 'C': 1}


def _summary(key, label, *, filed=100, decided=150, p1_median=17, w_median=12,
             referred=2, milestones=()):
    return {
        'quarter': key, 'label': label,
        'notifications': {
            'filed': filed, 'phase_1_decided': 90, 'referred_to_phase_2': referred,
            'clearance_rate': 88 / 90, 'timing': {'median': p1_median},
        },
        'waivers': {'decided': decided, 'clearance_rate': 0.96, 'timing': {'median': w_median}},
        'milestones': list(milestones),
    }


Q2 = _summary('2026-Q2', 'Q2 2026')
Q3 = _summary('2026-Q3', 'Q3 2026', filed=113, decided=183, p1_median=18, w_median=17, milestones=[
    {'kind': 'phase_2_outcome', 'label': 'Not approved'},
    {'kind': 'phase_2_outcome', 'label': 'Not approved'},
    {'kind': 'phase_2_outcome', 'label': 'Assessment ceased'},
    {'kind': 'tribunal_application', 'detail': 'Coles'},
])


class TestFindings:
    def test_compares_volume_and_timing_with_the_previous_quarter(self):
        assert quarterly.findings(Q3, Q2) == [
            '113 notifications filed, up 13% on Q2 2026, and 183 waiver applications decided, up 22% on Q2 2026.',
            'Phase 1 reviews concluded in a median 18 business days, 1 day slower than Q2 2026; '
            'waivers in 17, 5 days slower than Q2 2026.',
            '96% of waivers were granted and 98% of phase 1 reviews ended in approval.',
            '2 matters referred to phase 2; 3 phase 2 reviews concluded (2 not approved, 1 assessment ceased).',
        ]

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


class TestPreNotification:
    def _filed(self, merger_id, filed, days, **extra):
        return _notification(
            merger_id, filed,
            pre_notification={'estimated_days': days},
            original_notification_datetime=f'{filed}T12:00:00Z',
            **extra,
        )

    def test_keyed_by_filing_date_in_business_days(self):
        # Filed Wed 15 Jul; 14 calendar days earlier is Wed 1 Jul — 10 business days.
        mergers = [self._filed('MN-1', '2026-07-15', 14), self._filed('MN-2', '2026-04-15', 0)]
        payload = quarterly.generate(mergers, as_at=AS_AT)
        q3 = _quarter(payload, '2026-Q3')['pre_notification']
        assert (q3['count'], q3['median'], q3['average']) == (1, 10, 10)
        assert q3['buckets'] == [0, 1, 0, 0, 0, 0]
        q2 = _quarter(payload, '2026-Q2')['pre_notification']
        assert (q2['count'], q2['median'], q2['buckets'][0]) == (1, 0, 1)

    def test_matters_without_an_estimate_are_left_out(self):
        mergers = [_notification('MN-1', '2026-07-15')]
        pre = _quarter(quarterly.generate(mergers, as_at=AS_AT), '2026-Q3')['pre_notification']
        assert pre['count'] == 0 and pre['median'] is None

    def test_bucket_labels(self):
        payload = quarterly.generate([], as_at=AS_AT)
        assert payload['pre_notification_buckets'] == ['0', '1–10', '11–20', '21–40', '41–60', '61+']

    def test_finding_compares_with_the_previous_quarter(self):
        q2 = dict(Q2, pre_notification={'median': 14.5})
        q3 = dict(Q3, pre_notification={'median': 16})
        assert ('Notifications filed had spent an estimated median 16 business days in '
                'pre-notification, 1.5 days longer than Q2 2026.') in quarterly.findings(q3, q2)

    def test_no_finding_without_an_estimate(self):
        assert not any('pre-notification' in f for f in quarterly.findings(Q3, Q2))


class TestAppeals:
    def _merger(self, *appeals):
        return _notification(
            'MN-1', '2026-02-02', 'Referred to phase 2', '2026-03-10',
            appeals=list(appeals),
        )

    @staticmethod
    def _appeal(number, filed, status='current', concluded=None, outcome=None, hearing=None):
        return {
            'tribunal_number': number, 'tribunal_url': f'https://tribunal.example/{number}',
            'appellant': 'Applicant', 'status': status, 'filed_date': filed,
            'concluded_date': concluded, 'outcome': outcome, 'hearing_date': hearing,
        }

    def test_an_appeal_counts_in_every_quarter_it_was_live(self):
        appeal = self._appeal('ACT 1 of 2026', '2026-05-10', 'concluded', '2026-08-20', 'affirmed')
        payload = quarterly.generate([self._merger(appeal)], as_at=date(2027, 1, 5))
        q2, q3, q4 = (_quarter(payload, k)['appeals'] for k in ('2026-Q2', '2026-Q3', '2026-Q4'))
        assert (q2['lodged'], q2['concluded'], q2['open_at_end']) == (1, 0, 1)
        assert (q3['lodged'], q3['concluded'], q3['open_at_end']) == (0, 1, 0)
        assert q4['matters'] == []
        assert q2['matters'][0]['note'] == (
            'Lodged this quarter; open at quarter end; since concluded 20 Aug 2026: ACCC decision affirmed'
        )
        assert q3['matters'][0]['note'] == (
            'Carried in from an earlier quarter; concluded 20 Aug 2026: ACCC decision affirmed'
        )

    def test_open_appeal_notes_its_hearing(self):
        appeal = self._appeal('ACT 1 of 2026', '2026-07-15', hearing='2026-11-09')
        q3 = _quarter(quarterly.generate([self._merger(appeal)], as_at=AS_AT), '2026-Q3')['appeals']
        assert q3['matters'][0]['note'] == 'Lodged this quarter; open at quarter end; hearing listed for 9 Nov 2026'
        assert q3['matters'][0]['tribunal_url'] == 'https://tribunal.example/ACT 1 of 2026'
        assert q3['matters'][0]['merger_id'] == 'MN-1'

    def test_lodged_after_the_quarter_is_not_in_it(self):
        appeal = self._appeal('ACT 3 of 2026', '2026-10-01')
        payload = quarterly.generate([self._merger(appeal)], as_at=date(2027, 1, 5))
        assert _quarter(payload, '2026-Q3')['appeals']['matters'] == []
        assert _quarter(payload, '2026-Q4')['appeals']['lodged'] == 1

    def test_finding_names_each_application(self):
        appeals = [self._appeal('ACT 3 of 2026', '2026-10-01'), self._appeal('ACT 4 of 2026', '2026-10-05')]
        appeals[1]['appellant'] = 'Other'
        q4 = _quarter(quarterly.generate([self._merger(*appeals)], as_at=date(2027, 1, 5)), '2026-Q4')
        assert q4['findings'][-1] == (
            '2 Tribunal reviews opened: Applicant (ACT 3 of 2026), Other (ACT 4 of 2026); 2 open at quarter end.'
        )


class TestUrlKeyAndCommentary:
    def test_each_quarter_carries_its_short_url_key(self):
        payload = quarterly.generate([], as_at=AS_AT)
        assert [q['url_key'] for q in payload['quarters']] == ['26Q1', '26Q2', '26Q3']

    def test_quarter_keys_in_every_form_people_write(self):
        for key in ('26Q3', '26q3', '2026Q3', '2026-Q3', ' 26Q3 '):
            assert quarterly.normalise_quarter_key(key) == (2026, 3), key
        for key in ('Q3', '26Q5', '2026-3', 'summer'):
            assert quarterly.normalise_quarter_key(key) is None, key

    def test_commentary_attaches_to_its_quarter(self):
        commentary = {
            '26Q3': [{'commentary': '  More of the same.  ', 'author': 'Nick', 'date': '2026-10-23'}],
            '2026-Q2': 'A bare string works too.',
        }
        payload = quarterly.generate([], as_at=AS_AT, commentary=commentary)
        assert _quarter(payload, '2026-Q3')['commentary'] == [
            {'commentary': 'More of the same.', 'author': 'Nick', 'date': '2026-10-23'},
        ]
        assert _quarter(payload, '2026-Q2')['commentary'] == [{'commentary': 'A bare string works too.'}]
        assert _quarter(payload, '2026-Q1')['commentary'] == []

    def test_blank_entries_and_unknown_keys_are_skipped(self, capsys):
        commentary = {'26Q3': [{'commentary': ''}, {'author': 'x'}], 'later': ['?']}
        payload = quarterly.generate([], as_at=AS_AT, commentary=commentary)
        assert _quarter(payload, '2026-Q3')['commentary'] == []
        assert "'later' is not a quarter" in capsys.readouterr().out

    def test_commentary_for_an_unpublished_quarter_waits_for_it(self):
        commentary = {'26Q4': ['Written early.']}
        assert all(not q['commentary'] for q in quarterly.generate([], as_at=AS_AT, commentary=commentary)['quarters'])
        q4 = quarterly.generate([], as_at=date(2027, 1, 5), commentary=commentary)['quarters'][-1]
        assert q4['commentary'] == [{'commentary': 'Written early.'}]

    def test_the_committed_commentary_file_loads(self):
        from scripts.generate.static_data.loaders import load_quarterly_commentary
        loaded = load_quarterly_commentary()
        assert all(not k.startswith('_') for k in loaded)
        for key in loaded:
            assert quarterly.normalise_quarter_key(key) is not None, key
