"""Tests for the weekly digest email.

Focused on how a conditional clearance is presented. The ACCC register
publishes one as a plain "Approved" and carries the conditions separately in
``has_conditions``, so without explicit handling a conditional clearance reads
as an unconditional one in both the lede and the tables.
"""

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


class TestDecisionRows:
    def test_a_conditional_clearance_is_chipped_in_the_html(self):
        digest = _digest(cleared=[_cleared('MN-1', 'One', has_conditions=True)])
        assert 'WITH CONDITIONS' in swe.build_decisions(digest)

    def test_an_unconditional_clearance_is_not(self):
        digest = _digest(cleared=[_cleared('MN-1', 'One')])
        html = swe.build_decisions(digest)
        assert 'CLEARED' in html
        assert 'WITH CONDITIONS' not in html


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
