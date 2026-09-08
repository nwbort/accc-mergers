"""Tests for scripts/generate/static_data/phase1_estimate.py.

Cover the question-count bucketing, the questionnaire pooling and its global
fallback, the forward-chaining cutoff, waiver/undated/no-history exclusion, and
the freeze semantics (an existing current-version entry is never recomputed;
a stale-version one is).
"""

import sys
import unittest.mock

sys.modules.setdefault('pdfplumber', unittest.mock.MagicMock())
sys.modules.setdefault('markdownify', unittest.mock.MagicMock())
sys.modules.setdefault('requests', unittest.mock.MagicMock())

from scripts.generate.static_data.enrichment import enrich_merger
from scripts.generate.static_data.phase1_estimate import (
    METHOD_VERSION,
    MIN_SUPPORT,
    OVERFLOW_BUCKET,
    attach_phase_1_estimates,
    build_completed_pool,
    compute_estimate,
    question_bucket,
    question_counts_from,
)


def _completed(merger_id, notif, det):
    """A determined phase-1 notification merger."""
    return enrich_merger({
        'merger_id': merger_id,
        'merger_name': merger_id,
        'status': 'Determined',
        'accc_determination': 'Approved',
        'stage': 'Phase 1 - preliminary assessment',
        'effective_notification_datetime': notif,
        'determination_publication_date': det,
        'anzsic_codes': [],
        'acquirers': [], 'targets': [], 'other_parties': [],
        'url': f'https://example.com/{merger_id}',
        'events': [],
    })


def _questionnaire(count):
    return {'questions': [{'number': i + 1, 'text': f'q{i}'} for i in range(count)]}


# Peers all notified 2025-01-06 and determined 2025-02-05; the target is filed
# well after they concluded, so every peer is eligible under forward chaining.
PEER_NOTIF, PEER_DET = '2025-01-06T09:00:00Z', '2025-02-05T12:00:00Z'
TARGET_NOTIF, TARGET_DET = '2025-06-02T09:00:00Z', '2025-07-01T12:00:00Z'


def _peers(n, first_index=0):
    return [
        _completed(f'MN-P{i}', PEER_NOTIF, PEER_DET)
        for i in range(first_index, first_index + n)
    ]


# ---------------------------------------------------------------------------
# question_bucket / question_counts_from
# ---------------------------------------------------------------------------

class TestBucketing:
    def test_boilerplate_and_overflow_edges(self):
        assert question_bucket(1) == '3 or fewer'
        assert question_bucket(3) == '3 or fewer'
        assert question_bucket(4) == '4-5'
        assert question_bucket(5) == '4-5'
        assert question_bucket(6) == '6-9'
        assert question_bucket(9) == '6-9'
        assert question_bucket(10) == OVERFLOW_BUCKET
        assert question_bucket(25) == OVERFLOW_BUCKET

    def test_unknown_count_has_no_bucket(self):
        assert question_bucket(None) is None

    def test_counts_skip_metadata_and_empty_questionnaires(self):
        counts = question_counts_from({
            '_not_questionnaire_shas': ['abc'],
            'MN-1': _questionnaire(4),
            'MN-2': {'questions': []},
            'MN-3': {'deadline': '2025-01-01'},
        })
        assert counts == {'MN-1': 4}


# ---------------------------------------------------------------------------
# compute_estimate — pooling, fallback, exclusions
# ---------------------------------------------------------------------------

class TestComputeEstimate:
    def test_pools_on_question_bucket_when_supported(self):
        peers = _peers(MIN_SUPPORT)
        target = _completed('MN-T', TARGET_NOTIF, TARGET_DET)
        counts = {m['merger_id']: 12 for m in peers}
        counts['MN-T'] = 11  # same bucket as the peers
        pool = build_completed_pool(peers, counts)
        est = compute_estimate(target, pool, '2025-06-02', counts)
        assert est['basis'] == 'questionnaire'
        assert est['question_bucket'] == OVERFLOW_BUCKET
        assert est['question_count'] == 11
        assert est['sample_size'] == MIN_SUPPORT
        assert est['method_version'] == METHOD_VERSION
        assert isinstance(est['expected_business_days'], int)

    def test_falls_back_to_global_when_bucket_thin(self):
        # Plenty of history overall, but only a couple of peers share the
        # target's bucket, so the whole-of-market median is used instead.
        peers = _peers(MIN_SUPPORT + 2)
        counts = {m['merger_id']: 3 for m in peers}
        counts['MN-P0'] = counts['MN-P1'] = 12
        target = _completed('MN-T', TARGET_NOTIF, TARGET_DET)
        counts['MN-T'] = 12
        pool = build_completed_pool(peers, counts)
        est = compute_estimate(target, pool, '2025-06-02', counts)
        assert est['basis'] == 'global'
        assert est['question_bucket'] is None
        assert est['question_count'] == 12
        assert est['sample_size'] == MIN_SUPPORT + 2

    def test_merger_without_a_questionnaire_uses_global(self):
        peers = _peers(MIN_SUPPORT)
        counts = {m['merger_id']: 3 for m in peers}
        target = _completed('MN-T', TARGET_NOTIF, TARGET_DET)
        pool = build_completed_pool(peers, counts)
        est = compute_estimate(target, pool, '2025-06-02', counts)
        assert est['basis'] == 'global'
        assert est['question_count'] is None

    def test_records_the_forward_chaining_cutoff(self):
        peers = _peers(MIN_SUPPORT)
        target = _completed('MN-T', TARGET_NOTIF, TARGET_DET)
        pool = build_completed_pool(peers, {})
        est = compute_estimate(target, pool, '2025-06-02', {})
        assert est['as_of'] == '2025-06-02'  # the notification date, not the run date

    def test_excludes_peers_that_had_not_concluded_at_filing(self):
        # Same peers, but the target is filed one day before they concluded, so
        # none of them was knowable and there is no history left to learn from.
        peers = _peers(MIN_SUPPORT)
        early = _completed('MN-T', '2025-02-04T09:00:00Z', '2025-03-10T12:00:00Z')
        pool = build_completed_pool(peers, {})
        assert compute_estimate(early, pool, '2025-02-04', {}) is None

    def test_peer_concluding_on_the_filing_date_is_not_eligible(self):
        # The cutoff is strict: a determination published the same day the
        # target was filed is not something the filing could have relied on.
        peers = _peers(MIN_SUPPORT)
        same_day = _completed('MN-T', '2025-02-05T09:00:00Z', '2025-03-10T12:00:00Z')
        pool = build_completed_pool(peers, {})
        assert compute_estimate(same_day, pool, '2025-02-05', {}) is None

    def test_excludes_self_from_pool(self):
        target = _completed('MN-T', TARGET_NOTIF, TARGET_DET)
        pool = build_completed_pool([target], {})  # only itself
        assert compute_estimate(target, pool, '2025-06-02', {}) is None

    def test_withholds_estimate_below_minimum_history(self):
        peers = _peers(MIN_SUPPORT - 1)
        target = _completed('MN-T', TARGET_NOTIF, TARGET_DET)
        pool = build_completed_pool(peers, {})
        assert compute_estimate(target, pool, '2025-06-02', {}) is None

    def test_waiver_gets_no_estimate(self):
        waiver = enrich_merger({
            'merger_id': 'WA-1', 'merger_name': 'w', 'status': 'Determined',
            'accc_determination': 'Waiver granted', 'stage': 'Waiver',
            'effective_notification_datetime': TARGET_NOTIF,
            'determination_publication_date': TARGET_DET,
            'anzsic_codes': [],
            'acquirers': [], 'targets': [], 'other_parties': [],
            'url': 'https://example.com/WA-1', 'events': [],
        })
        pool = build_completed_pool(_peers(MIN_SUPPORT), {})
        assert compute_estimate(waiver, pool, '2025-06-02', {}) is None

    def test_undated_merger_gets_no_estimate(self):
        target = _completed('MN-T', None, None)
        pool = build_completed_pool(_peers(MIN_SUPPORT), {})
        assert compute_estimate(target, pool, '2025-06-02', {}) is None

    def test_waivers_never_enter_the_training_pool(self):
        waiver = enrich_merger({
            'merger_id': 'WA-1', 'merger_name': 'w', 'status': 'Determined',
            'accc_determination': 'Waiver granted', 'stage': 'Waiver',
            'effective_notification_datetime': PEER_NOTIF,
            'determination_publication_date': PEER_DET,
            'anzsic_codes': [],
            'acquirers': [], 'targets': [], 'other_parties': [],
            'url': 'https://example.com/WA-1', 'events': [],
        })
        pool = build_completed_pool(_peers(MIN_SUPPORT) + [waiver], {})
        assert {r['merger_id'] for r in pool} == {f'MN-P{i}' for i in range(MIN_SUPPORT)}


# ---------------------------------------------------------------------------
# attach_phase_1_estimates — freeze semantics + version migration
# ---------------------------------------------------------------------------

class TestAttachAndFreeze:
    def _mergers_with_live(self):
        mergers = _peers(MIN_SUPPORT)
        live = _completed('MN-LIVE', TARGET_NOTIF, None)
        live['status'] = 'Under assessment'
        live['accc_determination'] = None
        mergers.append(live)
        return mergers

    def test_attaches_and_freezes_new_entries(self):
        mergers = self._mergers_with_live()
        store = {}
        new, attached = attach_phase_1_estimates(
            mergers, {}, store=store, estimated_at='2025-06-02'
        )
        assert new == attached  # every attached one was newly frozen
        assert 'MN-LIVE' in store
        assert mergers[-1]['phase_1_estimate']['expected_business_days'] > 0

    def test_current_version_entry_is_not_recomputed(self):
        mergers = self._mergers_with_live()
        frozen = {
            'expected_business_days': 999, 'range_business_days': [999, 999],
            'basis': 'questionnaire', 'question_bucket': '4-5', 'question_count': 5,
            'sample_size': 1, 'as_of': '2020-01-01', 'estimated_at': '2020-01-01',
            'method_version': METHOD_VERSION,
        }
        store = {'MN-LIVE': dict(frozen)}
        new, attached = attach_phase_1_estimates(
            mergers, {}, store=store, estimated_at='2025-06-02'
        )
        assert mergers[-1]['phase_1_estimate'] == frozen
        assert new == attached - 1

    def test_stale_version_entry_is_recomputed(self):
        mergers = self._mergers_with_live()
        store = {'MN-LIVE': {
            'expected_business_days': 999, 'range_business_days': [999, 999],
            'basis': 'industry', 'anzsic_level': 'class', 'anzsic_codes': ['1234'],
            'sample_size': 1, 'estimated_at': '2020-01-01', 'method_version': 1,
        }}
        attach_phase_1_estimates(mergers, {}, store=store, estimated_at='2025-06-02')
        migrated = store['MN-LIVE']
        assert migrated['method_version'] == METHOD_VERSION
        assert migrated['expected_business_days'] != 999
        assert 'anzsic_level' not in migrated

    def test_superseded_entry_is_dropped_when_no_longer_estimable(self):
        # A v1 entry for a matter that v2 cannot estimate (filed before there
        # was any history) must not survive as a stale value.
        early = _completed('MN-EARLY', '2025-01-02T09:00:00Z', '2025-01-20T12:00:00Z')
        mergers = _peers(MIN_SUPPORT) + [early]
        store = {'MN-EARLY': {'expected_business_days': 999, 'method_version': 1}}
        attach_phase_1_estimates(mergers, {}, store=store, estimated_at='2025-06-02')
        assert 'MN-EARLY' not in store
        assert 'phase_1_estimate' not in mergers[-1]
