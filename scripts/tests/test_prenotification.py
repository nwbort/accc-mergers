"""Tests for scripts/static_data/prenotification.py.

Cover ID parsing, the filing-date choice, the lower bound from any later ID,
the waiver-anchored upper bound and interpolation, and the rules about which
mergers get an estimate at all.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from static_data.prenotification import (
    METHOD_VERSION,
    WAIVER_LODGEMENT_SLACK_DAYS,
    attach_prenotification_estimates,
    filing_date,
    parse_merger_id,
)


def _merger(merger_id, notified, original=None):
    """A merger record carrying only what the estimator reads."""
    return {
        'merger_id': merger_id,
        'effective_notification_datetime': f'{notified}T12:00:00Z',
        'original_notification_datetime': (
            f'{original}T12:00:00Z' if original else f'{notified}T12:00:00Z'
        ),
    }


def _estimates(mergers, slack=0):
    attach_prenotification_estimates(mergers, slack=slack)
    return {m['merger_id']: m.get('pre_notification') for m in mergers}


# ---------------------------------------------------------------------------
# parse_merger_id
# ---------------------------------------------------------------------------

class TestParseMergerId:
    def test_splits_kind_group_and_sequence(self):
        assert parse_merger_id('MN-01016') == ('MN', '01', 16)
        assert parse_merger_id('WA-95004') == ('WA', '95', 4)

    def test_leading_zeros_do_not_change_the_group(self):
        # '01' and '10' are different counters, not the same one reordered.
        assert parse_merger_id('MN-01005')[1] == '01'
        assert parse_merger_id('MN-10005')[1] == '10'

    def test_rejects_malformed_ids(self):
        for bad in ('', None, 'MN-1016', 'MN01016', 'M-01016', 'MN-0101A', 'MN-010160'):
            assert parse_merger_id(bad) is None


# ---------------------------------------------------------------------------
# filing_date
# ---------------------------------------------------------------------------

class TestFilingDate:
    def test_prefers_the_original_notification_date(self):
        merger = _merger('MN-01010', '2026-03-01', original='2026-02-01')
        assert filing_date(merger).isoformat() == '2026-02-01'

    def test_falls_back_to_the_effective_date(self):
        merger = {
            'merger_id': 'MN-01010',
            'effective_notification_datetime': '2026-03-01T12:00:00Z',
        }
        assert filing_date(merger).isoformat() == '2026-03-01'

    def test_undated_merger_has_no_filing_date(self):
        assert filing_date({'merger_id': 'MN-01010'}) is None


# ---------------------------------------------------------------------------
# Lower bound: a later ID that was notified earlier
# ---------------------------------------------------------------------------

class TestLowerBound:
    def test_later_id_notified_earlier_bounds_the_period(self):
        mergers = [
            _merger('MN-01010', '2026-04-01'),
            _merger('WA-01011', '2026-03-01'),
        ]
        estimate = _estimates(mergers)['MN-01010']
        assert estimate['min_days'] == 31
        assert estimate['min_days_witness'] == 'WA-01011'
        assert estimate['id_issued_before'] == '2026-03-01'

    def test_takes_the_tightest_witness_not_the_nearest_sequence(self):
        mergers = [
            _merger('MN-01010', '2026-04-01'),
            _merger('WA-01011', '2026-03-20'),
            _merger('WA-01020', '2026-03-01'),  # further up, but filed earliest
        ]
        assert _estimates(mergers)['MN-01010']['min_days_witness'] == 'WA-01020'

    def test_ids_in_other_groups_are_not_witnesses(self):
        # Each group runs its own counter, so sequence order says nothing across groups.
        mergers = [
            _merger('MN-01010', '2026-04-01'),
            _merger('WA-05011', '2026-03-01'),
        ]
        assert _estimates(mergers)['MN-01010'] is None

    def test_notified_in_sequence_order_proves_nothing(self):
        mergers = [
            _merger('MN-01010', '2026-03-01'),
            _merger('WA-01011', '2026-04-01'),
        ]
        assert _estimates(mergers)['MN-01010']['min_days'] == 0


# ---------------------------------------------------------------------------
# Upper bound and interpolation, anchored on waivers
# ---------------------------------------------------------------------------

class TestWaiverAnchors:
    def test_earlier_waiver_caps_the_period(self):
        mergers = [
            _merger('WA-01005', '2026-01-01'),
            _merger('MN-01010', '2026-04-01'),
            _merger('WA-01011', '2026-03-01'),
        ]
        estimate = _estimates(mergers)['MN-01010']
        assert estimate['max_days'] == 90
        assert estimate['max_days_witness'] == 'WA-01005'
        assert estimate['basis'] == 'bracketed'
        assert estimate['min_days'] <= estimate['estimated_days'] <= estimate['max_days']

    def test_an_earlier_notification_cannot_cap_the_period(self):
        # A notification's own ID predates its filing by an unknown amount, so
        # it says nothing about when a later ID was issued.
        mergers = [
            _merger('MN-01005', '2026-01-01'),
            _merger('MN-01010', '2026-04-01'),
            _merger('WA-01011', '2026-03-01'),
        ]
        estimate = _estimates(mergers)['MN-01010']
        assert estimate['max_days'] is None
        assert estimate['basis'] == 'lower-bound-only'

    def test_slack_widens_only_the_upper_bound(self):
        mergers = [
            _merger('WA-01005', '2026-01-01'),
            _merger('MN-01010', '2026-04-01'),
            _merger('WA-01011', '2026-03-01'),
        ]
        tight = _estimates([dict(m) for m in mergers], slack=0)['MN-01010']
        loose = _estimates([dict(m) for m in mergers], slack=10)['MN-01010']
        assert loose['max_days'] == tight['max_days'] + 10
        assert loose['min_days'] == tight['min_days']

    def test_interpolation_tracks_the_sequence_number(self):
        # Two waivers 100 days and 100 sequence numbers apart date the counter;
        # a notification a quarter of the way up sits a quarter of the way along.
        mergers = [
            _merger('WA-01000', '2026-01-01'),
            _merger('WA-01100', '2026-04-11'),
            _merger('MN-01025', '2026-05-01'),
        ]
        estimate = _estimates(mergers)['MN-01025']
        assert estimate['id_issued_before'] == '2026-04-11'
        # 25% of the way from 1 Jan to 11 Apr is 26 Jan; 1 May is 95 days later.
        assert estimate['estimated_days'] == 95

    def test_estimate_is_clamped_into_the_proven_bounds(self):
        # Interpolating between the waivers either side of MN-01050 would date
        # its ID in April, but a waiver further up the counter was already filed
        # on 1 March, so the ID cannot have been issued after that. The proven
        # bound wins over the interpolation.
        mergers = [
            _merger('WA-01000', '2026-01-01'),
            _merger('WA-01060', '2026-06-01'),  # nearest above by sequence
            _merger('WA-01090', '2026-03-01'),  # further up, but filed earliest
            _merger('MN-01050', '2026-05-01'),
        ]
        estimate = _estimates(mergers)['MN-01050']
        assert estimate['id_issued_before'] == '2026-03-01'
        assert estimate['estimated_days'] == estimate['min_days'] == 61


# ---------------------------------------------------------------------------
# What gets an estimate
# ---------------------------------------------------------------------------

class TestAttachment:
    def test_waivers_are_anchors_and_get_no_estimate(self):
        mergers = [
            _merger('WA-01005', '2026-01-01'),
            _merger('WA-01010', '2026-04-01'),
            _merger('WA-01011', '2026-03-01'),
        ]
        assert attach_prenotification_estimates(mergers) == 0
        assert all('pre_notification' not in m for m in mergers)

    def test_top_of_the_counter_gets_no_estimate(self):
        mergers = [_merger('MN-01010', '2026-04-01')]
        assert _estimates(mergers)['MN-01010'] is None

    def test_undated_and_malformed_records_are_skipped(self):
        mergers = [
            {'merger_id': 'MN-01010'},
            {'merger_id': 'not-an-id', 'effective_notification_datetime': '2026-04-01T12:00:00Z'},
            _merger('WA-01011', '2026-03-01'),
        ]
        assert attach_prenotification_estimates(mergers) == 0

    def test_estimate_carries_the_method_version(self):
        mergers = [_merger('MN-01010', '2026-04-01'), _merger('WA-01011', '2026-03-01')]
        assert _estimates(mergers)['MN-01010']['method_version'] == METHOD_VERSION

    def test_default_slack_is_used_when_unspecified(self):
        mergers = [
            _merger('WA-01005', '2026-01-01'),
            _merger('MN-01010', '2026-04-01'),
            _merger('WA-01011', '2026-03-01'),
        ]
        attach_prenotification_estimates(mergers)
        assert mergers[1]['pre_notification']['max_days'] == 90 + WAIVER_LODGEMENT_SLACK_DAYS
