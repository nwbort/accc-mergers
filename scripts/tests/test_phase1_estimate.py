"""Tests for scripts/generate/static_data/phase1_estimate.py.

Cover the ANZSIC level resolution, the hierarchical-backoff pooling, the
global fallback, waiver/undated exclusion, and the freeze semantics (an
existing store entry is never recomputed).
"""

import sys
import unittest.mock

sys.modules.setdefault('pdfplumber', unittest.mock.MagicMock())
sys.modules.setdefault('markdownify', unittest.mock.MagicMock())
sys.modules.setdefault('requests', unittest.mock.MagicMock())

from scripts.generate.static_data import anzsic
from scripts.generate.static_data.enrichment import enrich_merger
from scripts.generate.static_data.phase1_estimate import (
    MIN_SUPPORT,
    attach_phase_1_estimates,
    build_completed_pool,
    compute_estimate,
    resolve_level_codes,
)


def _real_class_code():
    """Pick a real class code from the loaded ANZSIC tree (with its ancestors)."""
    for code, node in anzsic.hierarchy().items():
        if node.level == 'class' and len(anzsic.ancestors(code)) == 3:
            return code
    raise AssertionError("no class node found")


CLASS_CODE = _real_class_code()
GROUP_CODE = anzsic.get(CLASS_CODE).parent_code
SUBDIV_CODE = anzsic.get(GROUP_CODE).parent_code
DIV_CODE = anzsic.get(SUBDIV_CODE).parent_code


def _completed(merger_id, code, notif, det):
    """A determined phase-1 notification merger tagged with a single code."""
    return enrich_merger({
        'merger_id': merger_id,
        'merger_name': merger_id,
        'status': 'Determined',
        'accc_determination': 'Approved',
        'stage': 'Phase 1 - preliminary assessment',
        'effective_notification_datetime': notif,
        'determination_publication_date': det,
        'anzsic_codes': [{'code': code, 'name': code}],
        'acquirers': [], 'targets': [], 'other_parties': [],
        'url': f'https://example.com/{merger_id}',
        'events': [],
    })


# ---------------------------------------------------------------------------
# resolve_level_codes
# ---------------------------------------------------------------------------

class TestResolveLevelCodes:
    def test_class_tag_populates_every_level(self):
        resolved = resolve_level_codes([CLASS_CODE])
        assert resolved['class'] == {CLASS_CODE}
        assert resolved['group'] == {GROUP_CODE}
        assert resolved['subdivision'] == {SUBDIV_CODE}
        assert resolved['division'] == {DIV_CODE}

    def test_coarse_tag_does_not_drill_down(self):
        # A subdivision tag has no class/group beneath it.
        resolved = resolve_level_codes([SUBDIV_CODE])
        assert resolved['class'] == set()
        assert resolved['group'] == set()
        assert resolved['subdivision'] == {SUBDIV_CODE}
        assert resolved['division'] == {DIV_CODE}

    def test_unknown_code_ignored(self):
        assert resolve_level_codes(['ZZZZ']) == {
            'class': set(), 'group': set(), 'subdivision': set(), 'division': set()
        }


# ---------------------------------------------------------------------------
# compute_estimate — backoff, fallback, exclusions
# ---------------------------------------------------------------------------

class TestComputeEstimate:
    def test_uses_finest_level_with_enough_support(self):
        # MIN_SUPPORT completed peers all sharing the same class → class basis.
        peers = [
            _completed(f'MN-P{i}', CLASS_CODE, '2025-01-06T09:00:00Z', '2025-02-05T12:00:00Z')
            for i in range(MIN_SUPPORT)
        ]
        target = _completed('MN-T', CLASS_CODE, '2025-03-03T09:00:00Z', '2025-04-01T12:00:00Z')
        pool = build_completed_pool(peers)
        est = compute_estimate(target, pool, '2025-03-03')
        assert est['basis'] == 'industry'
        assert est['anzsic_level'] == 'class'
        assert est['anzsic_codes'] == [CLASS_CODE]
        assert est['sample_size'] == MIN_SUPPORT
        assert isinstance(est['expected_business_days'], int)

    def test_backs_off_to_coarser_level_when_class_thin(self):
        # Peers share the division but sit in different classes, so no single
        # finer level reaches MIN_SUPPORT — but the division pool does.
        class_codes = [c for c, n in anzsic.hierarchy().items()
                       if n.level == 'class' and DIV_CODE in {a.code for a in anzsic.ancestors(c)}]
        assert len(class_codes) >= 2
        peers = [
            _completed(f'MN-P{i}', class_codes[i % len(class_codes)],
                       '2025-01-06T09:00:00Z', '2025-02-05T12:00:00Z')
            for i in range(MIN_SUPPORT)
        ]
        target = _completed('MN-T', class_codes[0], '2025-03-03T09:00:00Z', '2025-04-01T12:00:00Z')
        pool = build_completed_pool(peers)
        est = compute_estimate(target, pool, '2025-03-03')
        assert est['basis'] == 'industry'
        # The class pool was too thin, so it backed off to a coarser level
        # (whichever of group/subdivision/division first reaches MIN_SUPPORT).
        assert est['anzsic_level'] in ('group', 'subdivision', 'division')
        assert est['sample_size'] >= MIN_SUPPORT

    def test_falls_back_to_global_without_industry_support(self):
        # A handful of peers in an unrelated division → target with no overlap
        # falls back to the whole-of-market median.
        peers = [
            _completed(f'MN-P{i}', CLASS_CODE, '2025-01-06T09:00:00Z', '2025-02-05T12:00:00Z')
            for i in range(3)
        ]
        # target tagged with a different division's class
        other_class = next(
            c for c, n in anzsic.hierarchy().items()
            if n.level == 'class' and DIV_CODE not in {a.code for a in anzsic.ancestors(c)}
        )
        target = _completed('MN-T', other_class, '2025-03-03T09:00:00Z', '2025-04-01T12:00:00Z')
        pool = build_completed_pool(peers)
        est = compute_estimate(target, pool, '2025-03-03')
        assert est['basis'] == 'global'
        assert est['anzsic_level'] is None
        assert est['sample_size'] == 3

    def test_excludes_self_from_pool(self):
        target = _completed('MN-T', CLASS_CODE, '2025-03-03T09:00:00Z', '2025-04-01T12:00:00Z')
        pool = build_completed_pool([target])  # only itself
        # No other completed history → no estimate.
        assert compute_estimate(target, pool, '2025-03-03') is None

    def test_waiver_gets_no_estimate(self):
        waiver = enrich_merger({
            'merger_id': 'WA-1', 'merger_name': 'w', 'status': 'Determined',
            'accc_determination': 'Waiver granted', 'stage': 'Waiver',
            'effective_notification_datetime': '2025-02-01T09:00:00Z',
            'determination_publication_date': '2025-02-10T12:00:00Z',
            'anzsic_codes': [{'code': CLASS_CODE, 'name': 'x'}],
            'acquirers': [], 'targets': [], 'other_parties': [],
            'url': 'https://example.com/WA-1', 'events': [],
        })
        peers = [
            _completed(f'MN-P{i}', CLASS_CODE, '2025-01-06T09:00:00Z', '2025-02-05T12:00:00Z')
            for i in range(MIN_SUPPORT)
        ]
        pool = build_completed_pool(peers)
        assert compute_estimate(waiver, pool, '2025-03-03') is None

    def test_undated_merger_gets_no_estimate(self):
        target = _completed('MN-T', CLASS_CODE, None, None)
        peers = [
            _completed(f'MN-P{i}', CLASS_CODE, '2025-01-06T09:00:00Z', '2025-02-05T12:00:00Z')
            for i in range(MIN_SUPPORT)
        ]
        pool = build_completed_pool(peers)
        assert compute_estimate(target, pool, '2025-03-03') is None


# ---------------------------------------------------------------------------
# attach_phase_1_estimates — freeze semantics
# ---------------------------------------------------------------------------

class TestAttachAndFreeze:
    def test_attaches_and_freezes_new_entries(self):
        mergers = [
            _completed(f'MN-P{i}', CLASS_CODE, '2025-01-06T09:00:00Z', '2025-02-05T12:00:00Z')
            for i in range(MIN_SUPPORT)
        ]
        live = _completed('MN-LIVE', CLASS_CODE, '2025-06-02T09:00:00Z', None)
        live['status'] = 'Under assessment'
        live['accc_determination'] = None
        mergers.append(live)

        store = {}
        new, attached = attach_phase_1_estimates(mergers, store=store, estimated_at='2025-06-02')
        assert new == attached  # every attached one was newly frozen
        assert 'MN-LIVE' in store
        assert mergers[-1]['phase_1_estimate']['expected_business_days'] > 0

    def test_existing_entry_is_not_recomputed(self):
        mergers = [
            _completed(f'MN-P{i}', CLASS_CODE, '2025-01-06T09:00:00Z', '2025-02-05T12:00:00Z')
            for i in range(MIN_SUPPORT)
        ]
        frozen = {
            'expected_business_days': 999, 'range_business_days': [999, 999],
            'basis': 'industry', 'anzsic_level': 'class', 'anzsic_codes': [CLASS_CODE],
            'sample_size': 1, 'estimated_at': '2020-01-01', 'method_version': 1,
        }
        store = {'MN-P0': dict(frozen)}
        new, attached = attach_phase_1_estimates(mergers, store=store, estimated_at='2025-06-02')
        # MN-P0 kept its frozen (absurd) value; only the rest were computed.
        assert mergers[0]['phase_1_estimate'] == frozen
        assert new == attached - 1
