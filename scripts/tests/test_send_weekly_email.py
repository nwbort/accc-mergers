"""Tests for the weekly digest email.

Focused on how a conditional clearance is presented. The ACCC register
publishes one as a plain "Approved" and carries the conditions separately in
``has_conditions``, so without explicit handling a conditional clearance reads
as an unconditional one in both the lede and the tables.
"""

import json
import re
import sys
import unittest.mock

# Mock heavy transitive imports before importing modules that need them
sys.modules.setdefault('pdfplumber', unittest.mock.MagicMock())
sys.modules.setdefault('markdownify', unittest.mock.MagicMock())
sys.modules.setdefault('requests', unittest.mock.MagicMock())

from scripts import send_weekly_email as swe


def _cleared(merger_id, name, has_conditions=False, **overrides):
    merger = {
        'merger_id': merger_id,
        'merger_name': name,
        'accc_determination': 'Approved',
        'phase_1_determination': 'Approved',
        'determination_publication_date': '2026-03-04T00:00:00Z',
        'has_conditions': has_conditions,
    }
    merger.update(overrides)
    return merger


def _digest(cleared=None, new_deals=None):
    return {
        'period_start': '2026-03-02T00:00:00+11:00',
        'period_end': '2026-03-08T23:59:59+11:00',
        'new_deals_notified': new_deals or [],
        'deals_cleared': cleared or [],
        'deals_referred_to_phase_2': [],
        'deals_declined': [],
        'deals_assessment_ceased': [],
        'deals_appealed_to_tribunal': [],
        'ongoing_phase_1': [],
        'ongoing_phase_2': [],
        'ongoing_tribunal_appeals': [],
    }


def _text(html):
    return re.sub(r'<[^>]+>', '', html)


class TestConditionsNote:
    def test_no_note_when_nothing_was_conditional(self):
        assert swe.conditions_note(0) == ''

    def test_note_reads_as_a_bracketed_rider(self):
        assert swe.conditions_note(2) == ' (2 with conditions)'


class TestWithConditions:
    def test_true_when_flagged(self):
        assert swe.with_conditions(_cleared('MN-1', 'A', has_conditions=True)) is True

    def test_false_when_not_flagged(self):
        assert swe.with_conditions(_cleared('MN-1', 'A')) is False

    def test_false_for_an_archived_digest_that_predates_the_field(self):
        merger = _cleared('MN-1', 'A')
        del merger['has_conditions']
        assert swe.with_conditions(merger) is False


class TestLede:
    def _lede(self, digest):
        return _text(swe.build_lede(swe._counts(digest)))

    def test_conditional_clearances_are_bracketed_after_the_count(self):
        digest = _digest(
            cleared=[
                _cleared('MN-1', 'One', has_conditions=True),
                _cleared('MN-2', 'Two', has_conditions=True),
                _cleared('MN-3', 'Three'),
            ],
            new_deals=[{'merger_id': 'MN-9', 'merger_name': 'Nine'}],
        )
        assert 'cleared 3 (2 with conditions).' in self._lede(digest)

    def test_no_bracket_when_every_clearance_was_unconditional(self):
        digest = _digest(
            cleared=[_cleared('MN-1', 'One')],
            new_deals=[{'merger_id': 'MN-9', 'merger_name': 'Nine'}],
        )
        lede = self._lede(digest)
        assert 'cleared 1.' in lede
        assert 'with conditions' not in lede

    def test_bracket_also_appears_in_the_no_new_deals_sentence(self):
        digest = _digest(cleared=[_cleared('MN-1', 'One', has_conditions=True)])
        assert 'cleared 1 deal (1 with conditions) this week' in self._lede(digest)


class TestLedeOnFoot:
    def _lede(self, p1=0, p2=0, pb=0):
        digest = _digest()
        digest['ongoing_phase_1'] = [{'merger_id': f'P1-{i}'} for i in range(p1)]
        digest['ongoing_phase_2'] = [{'merger_id': f'P2-{i}'} for i in range(p2)]
        digest['ongoing_public_benefit'] = [{'merger_id': f'PB-{i}'} for i in range(pb)]
        return _text(swe.build_lede(swe._counts(digest)))

    def test_public_benefit_matters_count_as_on_foot(self):
        assert ('38 assessments remain on foot – 35 in phase 1, 2 in phase 2 '
                'and 1 in the public benefit phase.') in self._lede(35, 2, 1)

    def test_two_phases_without_public_benefit_read_as_before(self):
        assert '37 assessments remain on foot – 35 in phase 1 and 2 in phase 2.' in self._lede(35, 2)

    def test_a_lone_public_benefit_matter(self):
        assert '1 assessment remains on foot, all in the public benefit phase.' in self._lede(pb=1)

    def test_digest_that_predates_the_public_benefit_list(self):
        digest = _digest()
        digest['ongoing_phase_1'] = [{'merger_id': 'P1'}]
        assert 'all in phase 1' in _text(swe.build_lede(swe._counts(digest)))


class TestLedeToPublicBenefit:
    def test_a_move_to_the_public_benefit_phase_is_reported(self):
        digest = _digest()
        digest['deals_to_public_benefit'] = [{'merger_id': 'MN-1', 'merger_name': 'One'}]
        lede = _text(swe.build_lede(swe._counts(digest)))
        assert 'One deal moved to the public benefit phase.' in lede

    def test_it_joins_the_other_outcomes_in_one_sentence(self):
        digest = _digest()
        digest['deals_referred_to_phase_2'] = [{'merger_id': 'MN-1'}]
        digest['deals_to_public_benefit'] = [{'merger_id': 'MN-2'}, {'merger_id': 'MN-3'}]
        lede = _text(swe.build_lede(swe._counts(digest)))
        assert ('One deal was referred to a phase 2 review and two deals moved '
                'to the public benefit phase.') in lede

    def test_nothing_is_said_in_a_week_without_one(self):
        assert 'public benefit' not in _text(swe.build_lede(swe._counts(_digest())))

    def test_the_text_email_counts_it(self):
        digest = _digest()
        digest['deals_to_public_benefit'] = [{'merger_id': 'MN-1', 'merger_name': 'One'}]
        assert 'To public benefit    : 1' in swe.build_text_email(digest)


class TestDecisionRows:
    def test_a_conditional_clearance_is_chipped_in_the_html(self):
        digest = _digest(cleared=[_cleared('MN-1', 'One', has_conditions=True)])
        assert 'WITH CONDITIONS' in swe.build_decisions(digest)

    def test_an_unconditional_clearance_is_not(self):
        digest = _digest(cleared=[_cleared('MN-1', 'One')])
        html = swe.build_decisions(digest)
        assert 'CLEARED' in html
        assert 'WITH CONDITIONS' not in html


class TestDecisionOrder:
    """Tribunal, then public benefit, phase 2, phase 1, waiver; within each
    group declines and referrals to phase 2, then ceased, then clearances."""

    def _order(self, **buckets):
        digest = _digest()
        digest.update(buckets)
        return [e["merger"]["merger_id"] for e in swe._decision_entries(digest)]

    def test_groups_run_tribunal_to_waiver_with_adverse_outcomes_first(self):
        order = self._order(
            deals_cleared=[
                _cleared('W-OK', 'Waiver ok', is_waiver=True, phase_1_determination=None),
                _cleared('P1-OK', 'Phase 1 ok'),
                _cleared('P2-OK', 'Phase 2 ok', phase_1_determination='Referred to phase 2',
                         phase_2_determination='Approved'),
                _cleared('PB-OK', 'PB ok', phase_1_determination='Referred to phase 2',
                         phase_2_determination='Not approved',
                         public_benefits_determination='Approved'),
            ],
            deals_declined=[
                _cleared('W-NO', 'Waiver no', is_waiver=True, accc_determination='Declined',
                         phase_1_determination=None),
                _cleared('P2-NO', 'Phase 2 no', accc_determination='Not approved',
                         phase_1_determination='Referred to phase 2',
                         phase_2_determination='Not approved'),
            ],
            deals_referred_to_phase_2=[{
                'merger_id': 'P1-REF', 'merger_name': 'Referred',
                'phase_1_determination': 'Referred to phase 2',
            }],
            deals_decided_by_tribunal=[
                {'merger_id': 'T-OK', 'merger_name': 'Tribunal ok',
                 'appeal': {'outcome': 'set_aside', 'effective_determination': 'Approved'}},
                {'merger_id': 'T-NO', 'merger_name': 'Tribunal no',
                 'appeal': {'outcome': 'affirmed', 'effective_determination': 'Not approved'}},
            ],
        )
        assert order == [
            'T-NO', 'T-OK', 'PB-OK', 'P2-NO', 'P2-OK', 'P1-REF', 'P1-OK', 'W-NO', 'W-OK',
        ]

    def test_ceased_assessment_sits_between_declines_and_clearances(self):
        order = self._order(
            deals_cleared=[_cleared('P2-OK', 'Phase 2 ok', phase_2_determination='Approved')],
            deals_declined=[_cleared('P2-NO', 'Phase 2 no', accc_determination='Not approved',
                                     phase_2_determination='Not approved')],
            deals_assessment_ceased=[{
                'merger_id': 'P2-CEASED', 'merger_name': 'Ceased',
                'stage': 'Phase 2 - detailed assessment',
            }],
        )
        assert order == ['P2-NO', 'P2-CEASED', 'P2-OK']

    def test_tribunal_row_states_the_outcome(self):
        digest = _digest()
        digest['deals_decided_by_tribunal'] = [{
            'merger_id': 'T-1', 'merger_name': 'Tribunal one',
            'appeal': {'outcome': 'affirmed', 'effective_determination': 'Not approved',
                       'concluded_date': '2026-03-05'},
        }]
        html = _text(swe.build_decisions(digest))
        assert 'DECLINED' in html
        assert 'ACCC decision affirmed' in html


class TestTextEmail:
    def test_summary_count_and_table_row_both_say_with_conditions(self):
        digest = _digest(cleared=[
            _cleared('MN-1', 'One', has_conditions=True),
            _cleared('MN-2', 'Two'),
        ])
        text = swe.build_text_email(digest)

        assert 'Cleared              : 2 (1 with conditions)' in text
        assert 'One (with conditions)' in text
        assert 'Two (with conditions)' not in text

    def test_unconditional_week_is_left_alone(self):
        digest = _digest(cleared=[_cleared('MN-1', 'One')])
        text = swe.build_text_email(digest)

        assert 'Cleared              : 1\n' in text
        assert 'with conditions' not in text


class TestHeaderBanner:
    # 2026-03-02 is not a feedback week; 2026-02-23 is (weeks since 2024-01-01 % 8 == 0).
    def test_ordinary_week_links_to_linkedin_and_bluesky(self):
        html = swe.build_html_email(_digest())
        assert f'href="{swe.LINKEDIN_URL}"' in html
        assert f'href="{swe.BLUESKY_URL}"' in html
        text = swe.build_text_email(_digest())
        assert swe.LINKEDIN_URL in text and swe.BLUESKY_URL in text

    def test_feedback_week_keeps_the_feedback_ask_instead(self):
        digest = _digest()
        digest['period_start'] = '2026-02-23T00:00:00+11:00'
        assert swe._is_feedback_week(digest['period_start'])
        html = swe.build_html_email(digest)
        assert 'market gossip' in html
        assert swe.LINKEDIN_URL not in html

    def test_signup_banner_restores_the_forwarded_prompt(self):
        html = swe.build_html_email(_digest(), banner='signup')
        assert 'Were you forwarded this email?' in html
        assert swe.LINKEDIN_URL not in html
        text = swe.build_text_email(_digest(), banner='signup')
        assert swe.LINKEDIN_URL not in text
        assert 'Follow mergers.fyi' not in text

    def test_banner_env_var_selects_the_banner(self, monkeypatch):
        monkeypatch.setenv('BANNER', 'signup')
        assert 'Were you forwarded' in swe.build_html_email(_digest())
        monkeypatch.delenv('BANNER')
        assert swe.LINKEDIN_URL in swe.build_html_email(_digest())


class TestPromo:
    PROMO = {
        'path': '/somewhere',
        'title': 'Something new & shiny',
        'description': 'A description of it.',
        'cta': 'Go see',
    }

    def test_promo_card_links_its_page_in_both_versions(self):
        html = swe.build_html_email(_digest(), promo=self.PROMO)
        assert html.count(f'href="{swe.SITE_BASE}/somewhere"') == 2
        assert 'Something new &amp; shiny' in html
        assert 'Go see' in html
        text = swe.build_text_email(_digest(), promo=self.PROMO)
        assert 'Something new & shiny' in text
        assert f'{swe.SITE_BASE}/somewhere' in text

    def test_no_promo_renders_no_card(self):
        html = swe.build_html_email(_digest(), promo=None)
        assert '<!-- PROMO -->' in html  # the slot, empty
        assert swe.build_promo(None) == ''
        assert 'Something new' not in swe.build_text_email(_digest(), promo=None)

    def test_promo_sits_alongside_the_header_banner(self):
        html = swe.build_html_email(_digest(), promo=self.PROMO)
        assert f'href="{swe.LINKEDIN_URL}"' in html

    def test_default_promo_points_at_a_real_quarter(self):
        promo = swe.PROMO
        if promo is None:
            return
        assert promo['path'].startswith('/')
        if promo['path'].startswith('/quarterly/'):
            data = json.loads((swe.Path(__file__).resolve().parents[2] / 'frontend/public/data/quarterly.json').read_text())
            keys = {q['url_key'] for q in data['quarters']}
            assert promo['path'].removeprefix('/quarterly/') in keys
