"""Tests for cutoff.py"""
import pytest
from datetime import datetime, timedelta
from scripts.cutoff import (
    parse_date,
    is_waiver_merger,
    get_cutoff_date,
    should_skip_merger,
    CUTOFF_WEEKS
)


class TestParseDate:
    """Test suite for parse_date function."""

    def test_parse_iso_datetime(self):
        """Test parsing ISO 8601 datetime with timezone."""
        result = parse_date("2025-01-15T12:00:00Z")
        # Result may be timezone-aware or naive depending on implementation
        assert result.year == 2025
        assert result.month == 1
        assert result.day == 15
        assert result.hour == 12

    def test_parse_iso_datetime_with_offset(self):
        """Test parsing ISO datetime with timezone offset."""
        result = parse_date("2025-01-15T12:00:00+10:00")
        assert result is not None
        assert result.year == 2025
        assert result.month == 1
        assert result.day == 15

    def test_parse_simple_date(self):
        """Test parsing simple date format."""
        result = parse_date("2025-01-15")
        assert result == datetime(2025, 1, 15)

    def test_parse_empty_string(self):
        """Test parsing empty string returns None."""
        assert parse_date("") is None
        assert parse_date(None) is None

    def test_parse_invalid_date(self):
        """Test parsing invalid date returns None."""
        assert parse_date("invalid-date") is None
        assert parse_date("2025-13-45") is None


class TestIsWaiverMerger:
    """Test suite for is_waiver_merger function."""

    def test_waiver_by_id_prefix(self):
        """Test detection of waiver by merger_id starting with 'WA-'."""
        merger = {"merger_id": "WA-00123", "stage": "Phase 1"}
        assert is_waiver_merger(merger) is True

    def test_waiver_by_stage_keyword(self):
        """Test detection of waiver by 'Waiver' in stage."""
        merger = {"merger_id": "MN-00123", "stage": "Waiver application"}
        assert is_waiver_merger(merger) is True

    def test_not_waiver(self):
        """Test that regular notifications are not detected as waivers."""
        merger = {"merger_id": "MN-00123", "stage": "Phase 1"}
        assert is_waiver_merger(merger) is False

    def test_empty_merger(self):
        """Test empty merger dict."""
        assert is_waiver_merger({}) is False


class TestGetCutoffDate:
    """Test suite for get_cutoff_date function."""

    def test_no_determination_date(self):
        """Test that mergers without determination date have no cutoff."""
        merger = {
            "merger_id": "MN-00123",
            "accc_determination": "Approved"
        }
        assert get_cutoff_date(merger) is None

    def test_approved_notification_has_cutoff(self):
        """Test that approved notifications have cutoff date."""
        merger = {
            "merger_id": "MN-00123",
            "accc_determination": "Approved",
            "determination_publication_date": "2025-01-01T12:00:00Z"
        }
        cutoff = get_cutoff_date(merger)
        assert cutoff is not None
        # Check that cutoff is 3 weeks after determination
        start = datetime(2025, 1, 1, 12, 0, 0)
        expected = start + timedelta(weeks=CUTOFF_WEEKS)
        # Compare year, month, day to avoid timezone issues
        assert cutoff.year == expected.year
        assert cutoff.month == expected.month
        assert cutoff.day == expected.day

    def test_not_approved_notification_no_cutoff(self):
        """Test that non-approved notifications don't have cutoff."""
        merger = {
            "merger_id": "MN-00123",
            "accc_determination": "Not approved",
            "determination_publication_date": "2025-01-01T12:00:00Z"
        }
        assert get_cutoff_date(merger) is None

    def test_waiver_always_has_cutoff_after_determination(self):
        """Test that waivers have cutoff regardless of outcome."""
        # Approved waiver
        approved_waiver = {
            "merger_id": "WA-00123",
            "accc_determination": "Approved",
            "determination_publication_date": "2025-01-01T12:00:00Z"
        }
        assert get_cutoff_date(approved_waiver) is not None

        # Not approved waiver
        declined_waiver = {
            "merger_id": "WA-00124",
            "accc_determination": "Not approved",
            "determination_publication_date": "2025-01-01T12:00:00Z"
        }
        assert get_cutoff_date(declined_waiver) is not None

    def test_custom_cutoff_weeks(self):
        """Test custom cutoff weeks parameter."""
        merger = {
            "merger_id": "MN-00123",
            "accc_determination": "Approved",
            "determination_publication_date": "2025-01-01T12:00:00Z"
        }
        cutoff = get_cutoff_date(merger, cutoff_weeks=5)
        # Check that cutoff is 5 weeks after determination
        start = datetime(2025, 1, 1, 12, 0, 0)
        expected = start + timedelta(weeks=5)
        # Compare year, month, day to avoid timezone issues
        assert cutoff.year == expected.year
        assert cutoff.month == expected.month
        assert cutoff.day == expected.day


class TestShouldSkipMerger:
    """Test suite for should_skip_merger function."""

    def test_skip_after_cutoff_date(self):
        """Test that merger is skipped after cutoff date."""
        merger = {
            "merger_id": "MN-00123",
            "accc_determination": "Approved",
            "determination_publication_date": "2024-01-01T12:00:00Z"
        }
        # Reference date well after cutoff (3+ weeks after Jan 1, 2024)
        reference_date = datetime(2024, 3, 1)
        assert should_skip_merger(merger, reference_date) is True

    def test_dont_skip_before_cutoff_date(self):
        """Test that merger is not skipped before cutoff date."""
        merger = {
            "merger_id": "MN-00123",
            "accc_determination": "Approved",
            "determination_publication_date": "2025-01-01T12:00:00Z"
        }
        # Reference date just after determination (within 3 weeks)
        reference_date = datetime(2025, 1, 10)
        assert should_skip_merger(merger, reference_date) is False

    def test_dont_skip_without_cutoff(self):
        """Test that mergers without cutoff are never skipped."""
        merger = {
            "merger_id": "MN-00123",
            "accc_determination": "Not approved",
            "determination_publication_date": "2024-01-01T12:00:00Z"
        }
        reference_date = datetime(2025, 1, 1)
        assert should_skip_merger(merger, reference_date) is False

    def test_dont_skip_ongoing_merger(self):
        """Test that mergers without determination are not skipped."""
        merger = {
            "merger_id": "MN-00123",
            "status": "Under assessment"
        }
        reference_date = datetime(2025, 1, 1)
        assert should_skip_merger(merger, reference_date) is False

    def test_default_reference_date(self):
        """Test that default reference date (now) is used when not provided."""
        merger = {
            "merger_id": "MN-00123",
            "accc_determination": "Approved",
            "determination_publication_date": "2024-01-01T12:00:00Z"
        }
        # Without reference date, should use current time
        # Old merger from 2024 should be skipped by now
        assert should_skip_merger(merger) is True

    def test_timezone_handling(self):
        """Test proper timezone handling in comparisons."""
        merger = {
            "merger_id": "MN-00123",
            "accc_determination": "Approved",
            "determination_publication_date": "2025-01-01T12:00:00+00:00"
        }
        reference_date = datetime(2025, 1, 10)  # timezone-naive
        # Should work without errors
        result = should_skip_merger(merger, reference_date)
        assert isinstance(result, bool)
