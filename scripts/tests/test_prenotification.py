"""Tests for scripts/generate/static_data/prenotification.py.

Cover ID parsing, the filing-date choice, the lower bound from any later ID,
the waiver-anchored upper bound and interpolation, and the rules about which
mergers get an estimate at all.
"""


from scripts.generate.static_data.prenotification import (
    METHOD_VERSION,
    WAIVER_LODGEMENT_LAG_DAYS,
    WAIVER_LODGEMENT_LAG_MAX_DAYS,
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


def _estimates(mergers, lag=0, lag_max=None):
    """Estimates with both lag settings tied together unless told otherwise, so
    a test that isn't about the two-tier behaviour gets one coherent bracket."""
    attach_prenotification_estimates(
        mergers, lag=lag, lag_max=lag if lag_max is None else lag_max
    )
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

    def test_waiver_lag_shifts_every_number_by_the_same_amount(self):
        # The lag is the zero the estimates are measured from, so raising it
        # moves the whole bracket rather than changing its width.
        mergers = [
            _merger('WA-01005', '2026-01-01'),
            _merger('MN-01010', '2026-04-01'),
            _merger('WA-01011', '2026-03-01'),
        ]
        base = _estimates([dict(m) for m in mergers], lag=0, lag_max=0)['MN-01010']
        moved = _estimates([dict(m) for m in mergers], lag=10, lag_max=10)['MN-01010']
        for field in ('min_days', 'max_days', 'estimated_days'):
            assert moved[field] == base[field] + 10

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

    def test_estimated_date_matches_the_estimated_days(self):
        # The date is the filing date less the estimate, so a consumer reading
        # either one gets the same answer.
        mergers = [
            _merger('WA-01005', '2026-01-01'),
            _merger('MN-01010', '2026-04-01'),
            _merger('WA-01011', '2026-03-01'),
        ]
        estimate = _estimates(mergers)['MN-01010']
        assert estimate['id_issued_estimated'] == '2026-02-19'
        assert estimate['estimated_days'] == 41
        assert (
            estimate['id_issued_after']
            <= estimate['id_issued_estimated']
            <= estimate['id_issued_before']
        )

    def test_estimated_date_is_given_without_a_waiver_below(self):
        # Lower-bound-only cases still get a date, even though the ceiling and
        # its date are unknown.
        mergers = [_merger('MN-01010', '2026-04-01'), _merger('WA-01011', '2026-03-01')]
        estimate = _estimates(mergers)['MN-01010']
        assert estimate['basis'] == 'lower-bound-only'
        assert estimate['id_issued_estimated'] == '2026-03-01'
        assert estimate['id_issued_after'] is None

    def test_estimate_carries_the_method_version(self):
        mergers = [_merger('MN-01010', '2026-04-01'), _merger('WA-01011', '2026-03-01')]
        assert _estimates(mergers)['MN-01010']['method_version'] == METHOD_VERSION

    def test_defaults_prove_the_floor_and_pad_the_ceiling(self):
        # The three numbers answer to different standards: the floor assumes
        # nothing about waivers, the ceiling gives every anchor the most
        # lodgement delay any waiver is known to have taken.
        mergers = [
            _merger('WA-01005', '2026-01-01'),
            _merger('MN-01010', '2026-04-01'),
            _merger('WA-01011', '2026-03-01'),
        ]
        attach_prenotification_estimates(mergers)
        estimate = mergers[1]['pre_notification']
        assert estimate['min_days'] == 31
        assert estimate['max_days'] == 90 + WAIVER_LODGEMENT_LAG_MAX_DAYS
        assert estimate['min_days'] <= estimate['estimated_days'] <= estimate['max_days']

    def test_the_ceiling_alone_moves_with_the_generous_lag(self):
        mergers = [
            _merger('WA-01005', '2026-01-01'),
            _merger('MN-01010', '2026-04-01'),
            _merger('WA-01011', '2026-03-01'),
        ]
        tight = _estimates([dict(m) for m in mergers], lag=0, lag_max=0)['MN-01010']
        padded = _estimates([dict(m) for m in mergers], lag=0, lag_max=20)['MN-01010']
        assert padded['max_days'] == tight['max_days'] + 20
        assert padded['min_days'] == tight['min_days']
        assert padded['estimated_days'] == tight['estimated_days']

    def test_min_days_is_a_hard_bound_at_the_default_lag(self):
        # At lag 0 the lower bound rests only on a later ID having been filed
        # first, which assumes nothing about how waivers behave.
        mergers = [_merger('MN-01010', '2026-04-01'), _merger('MN-01011', '2026-03-01')]
        assert _estimates(mergers, lag=WAIVER_LODGEMENT_LAG_DAYS)['MN-01010']['min_days'] == 31

    def test_upper_bound_only_central_guess_uses_the_tight_lag(self):
        # MN-01011 sits at the top of the counter (nothing above it), so its
        # only witness is the waiver below, and its ceiling is deliberately
        # padded with lag_max. The central guess must not inherit that
        # padding, or it becomes more pessimistic than a same-witness case
        # that also gets a proven floor.
        mergers = [_merger('WA-01005', '2026-01-01'), _merger('MN-01011', '2026-04-01')]
        estimate = _estimates(mergers, lag=0, lag_max=34)['MN-01011']
        assert estimate['basis'] == 'upper-bound-only'
        assert estimate['max_days'] == 90 + 34
        assert estimate['estimated_days'] == 90
        assert estimate['id_issued_estimated'] == '2026-01-01'

    def test_a_late_waiver_below_cannot_push_max_days_under_min_days(self):
        # WA-01002 has a real 100-day lodgement lag, far past anything lag_max
        # allows for. Padding its filed date alone would place its assumed
        # issue date after MN-01003's proven ceiling (from WA-01004, seq 4),
        # crossing the two bounds. WA-01002's own ceiling — it can't have been
        # issued after WA-01004 either — must clamp it back into line.
        mergers = [
            _merger('WA-01001', '2026-01-01'),
            _merger('WA-01002', '2026-04-12'),  # issued day 2, lodged 100 days late
            _merger('MN-01003', '2026-04-13'),
            _merger('WA-01004', '2026-01-05'),
        ]
        estimate = _estimates(mergers, lag=0, lag_max=7)['MN-01003']
        assert estimate['min_days'] <= estimate['estimated_days'] <= estimate['max_days']
        assert estimate['min_days'] == estimate['max_days'] == 98
        assert estimate['id_issued_before'] == estimate['id_issued_after'] == '2026-01-05'

    def test_upper_bound_only_stays_monotonic_with_a_bracketed_neighbour(self):
        # MN-01028 (lower sequence) is bracketed by the waiver below it and
        # MN-01030 above. MN-01030 (higher sequence) only has a lower
        # witness, so it falls into upper-bound-only. Since 28 was issued no
        # later than 30, 30's best-guess issue date must not land before
        # 28's — which it did before this basis stopped using lag_max.
        mergers = [
            _merger('WA-01026', '2026-07-10'),
            _merger('MN-01028', '2026-08-13'),
            _merger('MN-01030', '2026-08-05'),
        ]
        estimates = _estimates(mergers, lag=0, lag_max=34)
        assert estimates['MN-01028']['basis'] == 'bracketed'
        assert estimates['MN-01030']['basis'] == 'upper-bound-only'
        assert estimates['MN-01030']['id_issued_estimated'] >= estimates['MN-01028']['id_issued_estimated']


# ---------------------------------------------------------------------------
# The counter's own ordering, across a whole group
# ---------------------------------------------------------------------------

class TestCounterOrder:
    def test_midpoint_fallback_ignores_the_generous_lag(self):
        # No waiver sits above MN-01010, so the guess falls back to the
        # midpoint of its bounds rather than interpolating. That midpoint is a
        # central guess and must be measured at `lag`: taking it from the
        # lag_max-padded floor instead would drag it earlier the more generous
        # the ceiling is allowed to be.
        mergers = [
            _merger('WA-01005', '2026-01-01'),
            _merger('MN-01010', '2026-04-01'),
            _merger('MN-01012', '2026-03-01'),  # later ID filed first: the ceiling
        ]
        tight = _estimates([dict(m) for m in mergers], lag=0, lag_max=0)['MN-01010']
        padded = _estimates([dict(m) for m in mergers], lag=0, lag_max=34)['MN-01010']
        assert tight['basis'] == 'bracketed'
        # Halfway between 1 Jan (the waiver) and 1 Mar (the ceiling) is 30 Jan.
        assert tight['id_issued_estimated'] == '2026-01-30'
        assert padded['estimated_days'] == tight['estimated_days']
        assert padded['max_days'] == tight['max_days'] + 34

    def test_a_higher_sequence_cannot_be_issued_before_a_lower_one(self):
        # The shape MN-75041/MN-75044 had on the register: 41 is bracketed by
        # the waiver below and 44 above, while 44 tops the counter and has only
        # that same waiver to go on, so it landed on the waiver's own date —
        # earlier than 41's guess, which the counter forbids. 44 is dragged up
        # to 41, the better-witnessed of the two.
        mergers = [
            _merger('WA-75040', '2026-08-05'),
            _merger('MN-75041', '2026-08-14'),
            _merger('MN-75044', '2026-08-20'),
        ]
        estimates = _estimates(mergers, lag=0, lag_max=7)
        assert estimates['MN-75041']['basis'] == 'bracketed'
        assert estimates['MN-75044']['basis'] == 'upper-bound-only'
        assert estimates['MN-75041']['id_issued_estimated'] == '2026-08-09'
        assert estimates['MN-75044']['id_issued_estimated'] == '2026-08-09'
        assert estimates['MN-75044']['estimated_days'] == 11

    def test_reconciling_the_order_keeps_both_bounds_intact(self):
        mergers = [
            _merger('WA-75040', '2026-08-05'),
            _merger('MN-75041', '2026-08-14'),
            _merger('MN-75044', '2026-08-20'),
        ]
        estimates = _estimates(mergers, lag=0, lag_max=7)
        for merger_id in ('MN-75041', 'MN-75044'):
            estimate = estimates[merger_id]
            floor = estimate['min_days'] or 0
            assert floor <= estimate['estimated_days'] <= estimate['max_days']

    def test_each_group_is_reconciled_on_its_own_counter(self):
        # Group 01's late guess must not follow the loop into group 05: the two
        # counters run independently and say nothing about each other.
        mergers = [
            _merger('WA-01005', '2026-06-01'),
            _merger('MN-01010', '2026-09-01'),
            _merger('WA-05005', '2026-01-01'),
            _merger('MN-05010', '2026-04-01'),
        ]
        estimates = _estimates(mergers, lag=0, lag_max=7)
        assert estimates['MN-05010']['id_issued_estimated'] == '2026-01-01'
        assert estimates['MN-01010']['id_issued_estimated'] == '2026-06-01'
