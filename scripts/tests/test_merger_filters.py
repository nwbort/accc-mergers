"""Tests for scripts/merger_filters.py — the canonical loader + predicates.

The older tests at ``test_static_data_filters.py`` still cover the
``static_data.filters`` re-export shim; these tests exercise the canonical
:mod:`merger_filters` module directly (including the loader, which did not
exist in the original ``static_data.filters``).
"""

import json
import os
import sys
import unittest.mock
from pathlib import Path

import pytest

# Add scripts directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Mock heavy transitive imports before importing modules that need them
sys.modules.setdefault('pdfplumber', unittest.mock.MagicMock())
sys.modules.setdefault('markdownify', unittest.mock.MagicMock())
sys.modules.setdefault('requests', unittest.mock.MagicMock())

from constants import merger_status
from merger_filters import (
    DEFAULT_MERGERS_JSON,
    exclude_for_public_output,
    filter_notifications,
    filter_public,
    filter_suspended,
    filter_waivers,
    is_public_visible,
    is_suspended,
    is_waiver,
    load_mergers,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _fixture():
    """Realistic mix: a live notification, a completed one, a suspended one,
    a waiver, and a waiver that also happens to be suspended."""
    return [
        {
            'merger_id': 'MN-01017',
            'merger_name': 'Acme / Widgets',
            'is_waiver': False,
            'status': merger_status.UNDER_ASSESSMENT,
            'stage': 'Phase 1 - initial assessment',
        },
        {
            'merger_id': 'MN-01018',
            'merger_name': 'Foo / Bar',
            'is_waiver': False,
            'status': merger_status.ASSESSMENT_COMPLETED,
            'accc_determination': merger_status.APPROVED,
        },
        {
            'merger_id': 'MN-01019',
            'merger_name': 'Baz / Quux',
            'is_waiver': False,
            'status': merger_status.ASSESSMENT_SUSPENDED,
        },
        {
            'merger_id': 'WA-09001',
            'merger_name': 'Waiver Co',
            'is_waiver': True,
            'status': merger_status.ASSESSMENT_COMPLETED,
            'stage': 'Waiver - assessment',
        },
        {
            'merger_id': 'WA-09002',
            'merger_name': 'Waiver + Suspended Co',
            'is_waiver': True,
            'status': merger_status.ASSESSMENT_SUSPENDED,
            'stage': 'Waiver - assessment',
        },
    ]


# ---------------------------------------------------------------------------
# is_waiver
# ---------------------------------------------------------------------------


class TestIsWaiver:
    def test_true_when_flag_true(self):
        assert is_waiver({'is_waiver': True}) is True

    def test_false_when_flag_false(self):
        assert is_waiver({'is_waiver': False}) is False

    def test_false_when_flag_missing(self):
        assert is_waiver({}) is False

    def test_truthy_non_bool_values(self):
        # The predicate normalises to a real bool.
        assert is_waiver({'is_waiver': 1}) is True
        assert is_waiver({'is_waiver': 0}) is False
        assert is_waiver({'is_waiver': None}) is False

    def test_ignores_id_prefix_directly(self):
        # The raw id prefix is *not* what the predicate consults — it looks
        # at the already-computed flag written by enrich_merger /
        # extract_mergers.py. A waiver with is_waiver=False is treated as
        # non-waiver (this is a callers-must-enrich contract).
        assert is_waiver({'merger_id': 'WA-09999', 'is_waiver': False}) is False


# ---------------------------------------------------------------------------
# is_suspended
# ---------------------------------------------------------------------------


class TestIsSuspended:
    def test_true_for_assessment_suspended(self):
        assert is_suspended({'status': merger_status.ASSESSMENT_SUSPENDED}) is True

    def test_false_for_under_assessment(self):
        assert is_suspended({'status': merger_status.UNDER_ASSESSMENT}) is False

    def test_false_for_completed(self):
        assert is_suspended({'status': merger_status.ASSESSMENT_COMPLETED}) is False

    def test_false_when_missing(self):
        assert is_suspended({}) is False

    def test_exact_string_match(self):
        # Must match the canonical constant, not a lowercased / other variant.
        assert is_suspended({'status': 'assessment suspended'}) is False


# ---------------------------------------------------------------------------
# is_public_visible
# ---------------------------------------------------------------------------


class TestIsPublicVisible:
    def test_true_for_live_notification(self):
        m = {
            'is_waiver': False,
            'status': merger_status.UNDER_ASSESSMENT,
        }
        assert is_public_visible(m) is True

    def test_true_for_completed_notification(self):
        m = {
            'is_waiver': False,
            'status': merger_status.ASSESSMENT_COMPLETED,
        }
        assert is_public_visible(m) is True

    def test_false_for_waiver(self):
        m = {
            'is_waiver': True,
            'status': merger_status.ASSESSMENT_COMPLETED,
        }
        assert is_public_visible(m) is False

    def test_false_for_suspended(self):
        m = {
            'is_waiver': False,
            'status': merger_status.ASSESSMENT_SUSPENDED,
        }
        assert is_public_visible(m) is False

    def test_false_for_waiver_and_suspended(self):
        m = {
            'is_waiver': True,
            'status': merger_status.ASSESSMENT_SUSPENDED,
        }
        assert is_public_visible(m) is False


# ---------------------------------------------------------------------------
# filter_public
# ---------------------------------------------------------------------------


class TestFilterPublic:
    def test_excludes_waivers_and_suspended(self):
        result = filter_public(_fixture())
        ids = sorted(m['merger_id'] for m in result)
        # MN-01017 (live) and MN-01018 (completed) remain.
        assert ids == ['MN-01017', 'MN-01018']

    def test_empty_input(self):
        assert filter_public([]) == []

    def test_preserves_input_order(self):
        mergers = [
            {'merger_id': 'A', 'is_waiver': False, 'status': merger_status.UNDER_ASSESSMENT},
            {'merger_id': 'W', 'is_waiver': True, 'status': merger_status.ASSESSMENT_COMPLETED},
            {'merger_id': 'B', 'is_waiver': False, 'status': merger_status.ASSESSMENT_COMPLETED},
            {'merger_id': 'S', 'is_waiver': False, 'status': merger_status.ASSESSMENT_SUSPENDED},
            {'merger_id': 'C', 'is_waiver': False, 'status': merger_status.UNDER_ASSESSMENT},
        ]
        assert [m['merger_id'] for m in filter_public(mergers)] == ['A', 'B', 'C']

    def test_accepts_any_iterable(self):
        mergers = (m for m in _fixture())  # generator
        result = filter_public(mergers)
        assert isinstance(result, list)
        assert len(result) == 2

    def test_exclude_for_public_output_alias(self):
        # Backwards-compat alias must behave identically.
        mergers = _fixture()
        assert exclude_for_public_output(mergers) == filter_public(mergers)


# ---------------------------------------------------------------------------
# filter_waivers / filter_notifications / filter_suspended
# ---------------------------------------------------------------------------


class TestFilterWaivers:
    def test_returns_only_waivers(self):
        result = filter_waivers(_fixture())
        ids = sorted(m['merger_id'] for m in result)
        assert ids == ['WA-09001', 'WA-09002']

    def test_empty_input(self):
        assert filter_waivers([]) == []


class TestFilterNotifications:
    def test_returns_only_non_waivers(self):
        result = filter_notifications(_fixture())
        ids = sorted(m['merger_id'] for m in result)
        # Includes suspended (still not a waiver).
        assert ids == ['MN-01017', 'MN-01018', 'MN-01019']

    def test_empty_input(self):
        assert filter_notifications([]) == []


class TestFilterSuspended:
    def test_returns_only_suspended(self):
        result = filter_suspended(_fixture())
        ids = sorted(m['merger_id'] for m in result)
        # Both a plain suspended notification and a suspended waiver.
        assert ids == ['MN-01019', 'WA-09002']

    def test_empty_input(self):
        assert filter_suspended([]) == []


class TestPartition:
    """filter_waivers + filter_notifications must partition the input."""

    def test_partition(self):
        mergers = _fixture()
        waivers = filter_waivers(mergers)
        notifications = filter_notifications(mergers)
        assert len(waivers) + len(notifications) == len(mergers)
        waiver_ids = {m['merger_id'] for m in waivers}
        notif_ids = {m['merger_id'] for m in notifications}
        assert waiver_ids.isdisjoint(notif_ids)


# ---------------------------------------------------------------------------
# load_mergers
# ---------------------------------------------------------------------------


class TestLoadMergers:
    def test_accepts_list_shape(self, tmp_path: Path):
        path = tmp_path / "mergers.json"
        path.write_text(json.dumps(_fixture()), encoding="utf-8")
        result = load_mergers(path)
        assert isinstance(result, list)
        assert len(result) == 5
        assert result[0]['merger_id'] == 'MN-01017'

    def test_accepts_wrapped_shape(self, tmp_path: Path):
        path = tmp_path / "mergers.json"
        path.write_text(json.dumps({'mergers': _fixture()}), encoding="utf-8")
        result = load_mergers(path)
        assert isinstance(result, list)
        assert len(result) == 5

    def test_accepts_string_path(self, tmp_path: Path):
        path = tmp_path / "mergers.json"
        path.write_text(json.dumps(_fixture()), encoding="utf-8")
        assert len(load_mergers(str(path))) == 5

    def test_rejects_unexpected_shape(self, tmp_path: Path):
        path = tmp_path / "mergers.json"
        path.write_text(json.dumps({'items': _fixture()}), encoding="utf-8")
        with pytest.raises(ValueError, match="Unexpected mergers.json format"):
            load_mergers(path)

    def test_rejects_top_level_scalar(self, tmp_path: Path):
        path = tmp_path / "mergers.json"
        path.write_text('"not a list"', encoding="utf-8")
        with pytest.raises(ValueError):
            load_mergers(path)

    def test_raises_on_missing_file(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            load_mergers(tmp_path / "nope.json")

    def test_raises_on_invalid_json(self, tmp_path: Path):
        path = tmp_path / "mergers.json"
        path.write_text("{not json", encoding="utf-8")
        with pytest.raises(json.JSONDecodeError):
            load_mergers(path)

    def test_default_path_points_at_processed_mergers_json(self):
        # The default should resolve to data/processed/mergers.json under the
        # repo root — i.e. co-located with scripts/.
        assert DEFAULT_MERGERS_JSON.name == "mergers.json"
        assert DEFAULT_MERGERS_JSON.parent.name == "processed"
        assert DEFAULT_MERGERS_JSON.parent.parent.name == "data"


# ---------------------------------------------------------------------------
# Integration: all helpers operate on the same enriched-merger contract.
# ---------------------------------------------------------------------------


class TestFilterIntegration:
    def test_filter_public_is_disjoint_from_suspended_and_waivers(self):
        mergers = _fixture()
        public = {m['merger_id'] for m in filter_public(mergers)}
        suspended = {m['merger_id'] for m in filter_suspended(mergers)}
        waivers = {m['merger_id'] for m in filter_waivers(mergers)}
        assert public.isdisjoint(suspended)
        assert public.isdisjoint(waivers)

    def test_filter_public_preserves_objects(self):
        # Filter should pass through merger dicts by reference (no copying).
        mergers = _fixture()
        result = filter_public(mergers)
        assert result[0] is mergers[0]
