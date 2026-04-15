"""Tests for scripts/static_data/filters.py."""

import os
import sys
import unittest.mock

# Add scripts directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Mock heavy transitive imports before importing modules that need them
sys.modules.setdefault('pdfplumber', unittest.mock.MagicMock())
sys.modules.setdefault('markdownify', unittest.mock.MagicMock())
sys.modules.setdefault('requests', unittest.mock.MagicMock())

from constants import merger_status
from static_data.filters import (
    exclude_for_public_output,
    filter_notifications,
    filter_suspended,
    filter_waivers,
    is_suspended,
    is_waiver,
)


def _fixture():
    """4 mergers: 1 waiver, 1 suspended, 1 live notification, 1 determined notification."""
    return [
        {'merger_id': 'MN-001', 'is_waiver': False, 'status': 'Determined'},
        {'merger_id': 'MN-002', 'is_waiver': False, 'status': merger_status.ASSESSMENT_SUSPENDED},
        {'merger_id': 'WA-003', 'is_waiver': True, 'status': 'Determined'},
        {'merger_id': 'MN-004', 'is_waiver': False, 'status': 'Under assessment'},
    ]


class TestPredicates:
    def test_is_waiver_true(self):
        assert is_waiver({'is_waiver': True}) is True

    def test_is_waiver_false(self):
        assert is_waiver({'is_waiver': False}) is False

    def test_is_waiver_missing_key(self):
        assert is_waiver({}) is False

    def test_is_suspended_true(self):
        assert is_suspended({'status': merger_status.ASSESSMENT_SUSPENDED}) is True

    def test_is_suspended_false(self):
        assert is_suspended({'status': 'Determined'}) is False

    def test_is_suspended_missing_key(self):
        assert is_suspended({}) is False


class TestFilterWaivers:
    def test_returns_only_waivers(self):
        result = filter_waivers(_fixture())
        assert len(result) == 1
        assert result[0]['merger_id'] == 'WA-003'

    def test_empty_input(self):
        assert filter_waivers([]) == []

    def test_no_waivers(self):
        mergers = [{'merger_id': 'MN-001', 'is_waiver': False}]
        assert filter_waivers(mergers) == []


class TestFilterNotifications:
    def test_returns_only_non_waivers(self):
        result = filter_notifications(_fixture())
        ids = sorted(m['merger_id'] for m in result)
        assert ids == ['MN-001', 'MN-002', 'MN-004']

    def test_empty_input(self):
        assert filter_notifications([]) == []


class TestFilterSuspended:
    def test_returns_only_suspended(self):
        result = filter_suspended(_fixture())
        assert len(result) == 1
        assert result[0]['merger_id'] == 'MN-002'

    def test_empty_input(self):
        assert filter_suspended([]) == []

    def test_no_suspended(self):
        mergers = [{'merger_id': 'MN-001', 'status': 'Determined'}]
        assert filter_suspended(mergers) == []


class TestExcludeForPublicOutput:
    def test_excludes_waivers_and_suspended(self):
        result = exclude_for_public_output(_fixture())
        ids = sorted(m['merger_id'] for m in result)
        # WA-003 (waiver) and MN-002 (suspended) excluded; the other 2 remain
        assert ids == ['MN-001', 'MN-004']

    def test_empty_input(self):
        assert exclude_for_public_output([]) == []

    def test_waiver_also_suspended_excluded_once(self):
        mergers = [{
            'merger_id': 'WA-999',
            'is_waiver': True,
            'status': merger_status.ASSESSMENT_SUSPENDED,
        }]
        assert exclude_for_public_output(mergers) == []

    def test_preserves_order(self):
        mergers = [
            {'merger_id': 'MN-A', 'is_waiver': False, 'status': 'Determined'},
            {'merger_id': 'WA-B', 'is_waiver': True, 'status': 'Determined'},
            {'merger_id': 'MN-C', 'is_waiver': False, 'status': 'Under assessment'},
        ]
        result = exclude_for_public_output(mergers)
        assert [m['merger_id'] for m in result] == ['MN-A', 'MN-C']


class TestDisjointPartition:
    """filter_waivers + filter_notifications should partition enriched mergers."""

    def test_partition(self):
        mergers = _fixture()
        waivers = filter_waivers(mergers)
        notifications = filter_notifications(mergers)
        assert len(waivers) + len(notifications) == len(mergers)
        waiver_ids = {m['merger_id'] for m in waivers}
        notif_ids = {m['merger_id'] for m in notifications}
        assert waiver_ids.isdisjoint(notif_ids)
