"""Tests for generate_weekly_digest.

Focuses on the inclusion criteria used to build digest buckets —
especially the late-arrival catch-up that surfaces determinations
dated on a Friday but not actually published on the ACCC's
acquisitions register until the following Monday.
"""

import os
import sys
import unittest.mock
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# Add scripts directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Mock heavy transitive imports before importing modules that need them
sys.modules.setdefault('pdfplumber', unittest.mock.MagicMock())
sys.modules.setdefault('markdownify', unittest.mock.MagicMock())
sys.modules.setdefault('requests', unittest.mock.MagicMock())

import generate_weekly_digest as gwd
from constants import merger_status


SYDNEY = ZoneInfo('Australia/Sydney')


def _period(monday_iso: str):
    """Build a (Mon 00:00, Sun 23:59:59.999999) range from a Monday date."""
    monday = datetime.fromisoformat(monday_iso).replace(tzinfo=SYDNEY)
    sunday = monday + timedelta(days=6, hours=23, minutes=59, seconds=59, microseconds=999999)
    return monday, sunday


class TestAppearedInPeriod:
    """appeared_in_period is the core of the late-arrival logic."""

    def test_primary_date_inside_period_returns_true(self):
        # Current-period digest: Mon 14 Apr - Sun 20 Apr 2025
        start, end = _period('2025-04-14')
        assert gwd.appeared_in_period(
            '2025-04-16T12:00:00Z',
            None,
            start, end,
        ) is True

    def test_primary_date_before_period_without_page_modified_returns_false(self):
        start, end = _period('2025-04-14')
        assert gwd.appeared_in_period(
            '2025-04-11T12:00:00Z',
            None,
            start, end,
        ) is False

    def test_friday_decision_appearing_monday_is_caught(self):
        """Core bug: determination dated Fri 11 Apr, page modified Mon 14 Apr afternoon."""
        start, end = _period('2025-04-14')
        # page_modified_datetime format from ACCC: includes offset
        assert gwd.appeared_in_period(
            '2025-04-11T12:00:00Z',
            '2025-04-14T15:30:00+10:00',
            start, end,
        ) is True

    def test_primary_date_too_old_is_not_caught_even_if_page_modified_this_week(self):
        """ACCC editing an old page (typo fix, adding a document) must not re-surface
        the merger in every later digest."""
        start, end = _period('2025-04-14')
        # Determination two weeks ago — would already have appeared in an earlier digest.
        assert gwd.appeared_in_period(
            '2025-03-28T12:00:00Z',
            '2025-04-15T10:00:00+10:00',
            start, end,
        ) is False

    def test_primary_date_in_prior_week_but_page_modified_also_in_prior_week_returns_false(self):
        """If the page was already visible during the prior week, the prior week's
        digest caught it; don't re-include now."""
        start, end = _period('2025-04-14')
        assert gwd.appeared_in_period(
            '2025-04-11T12:00:00Z',
            '2025-04-11T13:00:00+10:00',
            start, end,
        ) is False

    def test_missing_primary_date_returns_false(self):
        start, end = _period('2025-04-14')
        assert gwd.appeared_in_period(None, '2025-04-14T15:30:00+10:00', start, end) is False

    def test_page_modified_far_in_future_still_requires_primary_in_prior_week(self):
        start, end = _period('2025-04-14')
        # Primary two months ago — should not be caught.
        assert gwd.appeared_in_period(
            '2025-02-14T12:00:00Z',
            '2025-04-15T10:00:00+10:00',
            start, end,
        ) is False


class TestDigestBucketsLateArrival:
    """End-to-end check that generate_weekly_digest places late arrivals in the
    correct bucket for the current period."""

    def _run(self, mergers, monkeypatch):
        start, end = _period('2025-04-14')

        monkeypatch.setattr(gwd, 'load_mergers', lambda: mergers)
        monkeypatch.setattr(gwd, 'filter_active', lambda ms: ms)
        monkeypatch.setattr(gwd, 'get_last_week_range', lambda: (start, end))

        return gwd.generate_weekly_digest()

    def test_late_friday_clearance_is_picked_up_in_following_week(self, monkeypatch):
        merger = {
            'merger_id': 'MN-9001',
            'merger_name': 'Friday clearance',
            'status': merger_status.ASSESSMENT_COMPLETED,
            'stage': 'Phase 1 - initial assessment',
            'effective_notification_datetime': '2025-03-01T00:00:00Z',
            'determination_publication_date': '2025-04-11T00:00:00Z',  # Friday of prior week
            'page_modified_datetime': '2025-04-14T15:00:00+10:00',  # Monday of current week
            'accc_determination': merger_status.APPROVED,
            'events': [],
        }
        digest = self._run([merger], monkeypatch)
        assert any(m['merger_id'] == 'MN-9001' for m in digest['deals_cleared'])
        assert not any(m['merger_id'] == 'MN-9001' for m in digest['deals_declined'])

    def test_late_friday_declined_is_picked_up_in_following_week(self, monkeypatch):
        merger = {
            'merger_id': 'MN-9002',
            'merger_name': 'Friday decline',
            'status': merger_status.ASSESSMENT_COMPLETED,
            'stage': 'Phase 1 - initial assessment',
            'effective_notification_datetime': '2025-03-01T00:00:00Z',
            'determination_publication_date': '2025-04-11T00:00:00Z',
            'page_modified_datetime': '2025-04-14T15:00:00+10:00',
            'accc_determination': merger_status.NOT_APPROVED,
            'events': [],
        }
        digest = self._run([merger], monkeypatch)
        assert any(m['merger_id'] == 'MN-9002' for m in digest['deals_declined'])

    def test_late_notification_is_picked_up_in_following_week(self, monkeypatch):
        merger = {
            'merger_id': 'MN-9003',
            'merger_name': 'Late notification',
            'status': merger_status.UNDER_ASSESSMENT,
            'stage': 'Phase 1 - initial assessment',
            'effective_notification_datetime': '2025-04-11T00:00:00Z',  # prior Friday
            'page_modified_datetime': '2025-04-14T15:00:00+10:00',  # this Monday
            'events': [],
        }
        digest = self._run([merger], monkeypatch)
        assert any(m['merger_id'] == 'MN-9003' for m in digest['new_deals_notified'])

    def test_typo_fix_on_old_determination_is_not_re_surfaced(self, monkeypatch):
        merger = {
            'merger_id': 'MN-9004',
            'merger_name': 'Old determination, page edited today',
            'status': merger_status.ASSESSMENT_COMPLETED,
            'stage': 'Phase 1 - initial assessment',
            'effective_notification_datetime': '2025-02-01T00:00:00Z',
            'determination_publication_date': '2025-03-20T00:00:00Z',
            'page_modified_datetime': '2025-04-15T10:00:00+10:00',  # typo fix this week
            'accc_determination': merger_status.APPROVED,
            'events': [],
        }
        digest = self._run([merger], monkeypatch)
        assert not any(m['merger_id'] == 'MN-9004' for m in digest['deals_cleared'])

    def test_same_week_determination_still_works(self, monkeypatch):
        """Regression check: the normal path (determination in the period) still fires."""
        merger = {
            'merger_id': 'MN-9005',
            'merger_name': 'Normal mid-week clearance',
            'status': merger_status.ASSESSMENT_COMPLETED,
            'stage': 'Phase 1 - initial assessment',
            'effective_notification_datetime': '2025-03-20T00:00:00Z',
            'determination_publication_date': '2025-04-16T12:00:00Z',
            'page_modified_datetime': '2025-04-16T13:00:00+10:00',
            'accc_determination': merger_status.APPROVED,
            'events': [],
        }
        digest = self._run([merger], monkeypatch)
        assert any(m['merger_id'] == 'MN-9005' for m in digest['deals_cleared'])
