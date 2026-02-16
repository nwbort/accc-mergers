"""Tests for generate_weekly_digest.py"""
import pytest
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from scripts.generate_weekly_digest import (
    parse_datetime,
    get_last_week_range,
    is_in_week_range,
    create_merger_summary
)


class TestParseDateTime:
    """Test suite for parse_datetime function."""

    def test_parse_iso_with_z(self):
        """Test parsing ISO datetime with Z timezone."""
        result = parse_datetime("2025-01-15T12:00:00Z")
        assert result is not None
        assert result.year == 2025
        assert result.month == 1
        assert result.day == 15

    def test_parse_iso_with_offset(self):
        """Test parsing ISO datetime with timezone offset."""
        result = parse_datetime("2025-01-15T12:00:00+10:00")
        assert result is not None
        assert result.year == 2025

    def test_parse_empty_string(self):
        """Test that empty string returns None."""
        assert parse_datetime("") is None
        assert parse_datetime(None) is None

    def test_parse_invalid_format(self):
        """Test that invalid format returns None."""
        assert parse_datetime("not-a-date") is None
        assert parse_datetime("2025-13-45") is None


class TestGetLastWeekRange:
    """Test suite for get_last_week_range function."""

    def test_returns_monday_to_sunday(self):
        """Test that the function returns a Monday-Sunday range."""
        start, end = get_last_week_range()

        # Start should be a Monday (weekday 0)
        assert start.weekday() == 0

        # End should be a Sunday (weekday 6)
        assert end.weekday() == 6

        # Start should be at 00:00:00
        assert start.hour == 0
        assert start.minute == 0
        assert start.second == 0
        assert start.microsecond == 0

        # End should be at 23:59:59.999999
        assert end.hour == 23
        assert end.minute == 59
        assert end.second == 59

    def test_range_is_7_days(self):
        """Test that the range spans exactly 7 days."""
        start, end = get_last_week_range()

        # The difference should be 6 days plus almost 24 hours (Monday 00:00 to Sunday 23:59:59)
        delta = end - start
        assert delta.days == 6
        assert delta.seconds == 86399  # 23:59:59

    def test_uses_sydney_timezone(self):
        """Test that dates are in Sydney timezone."""
        start, end = get_last_week_range()

        sydney_tz = ZoneInfo('Australia/Sydney')
        assert start.tzinfo == sydney_tz
        assert end.tzinfo == sydney_tz


class TestIsInWeekRange:
    """Test suite for is_in_week_range function."""

    def test_date_within_range(self):
        """Test that dates within range are detected."""
        # Create a known Monday-Sunday range
        sydney_tz = ZoneInfo('Australia/Sydney')
        monday = datetime(2025, 1, 6, 0, 0, 0, tzinfo=sydney_tz)  # Monday
        sunday = datetime(2025, 1, 12, 23, 59, 59, 999999, tzinfo=sydney_tz)  # Sunday

        # Test date in the middle of the week
        test_date = "2025-01-08T12:00:00Z"  # Wednesday
        assert is_in_week_range(test_date, monday, sunday) is True

    def test_date_on_monday_start(self):
        """Test that date on Monday start is included."""
        sydney_tz = ZoneInfo('Australia/Sydney')
        monday = datetime(2025, 1, 6, 0, 0, 0, tzinfo=sydney_tz)
        sunday = datetime(2025, 1, 12, 23, 59, 59, 999999, tzinfo=sydney_tz)

        test_date = "2025-01-06T00:00:00+11:00"  # Monday at midnight AEDT
        assert is_in_week_range(test_date, monday, sunday) is True

    def test_date_on_sunday_end(self):
        """Test that date on Sunday end is included."""
        sydney_tz = ZoneInfo('Australia/Sydney')
        monday = datetime(2025, 1, 6, 0, 0, 0, tzinfo=sydney_tz)
        sunday = datetime(2025, 1, 12, 23, 59, 59, 999999, tzinfo=sydney_tz)

        test_date = "2025-01-12T23:00:00+11:00"  # Sunday evening AEDT
        assert is_in_week_range(test_date, monday, sunday) is True

    def test_date_before_range(self):
        """Test that dates before range are not included."""
        sydney_tz = ZoneInfo('Australia/Sydney')
        monday = datetime(2025, 1, 6, 0, 0, 0, tzinfo=sydney_tz)
        sunday = datetime(2025, 1, 12, 23, 59, 59, 999999, tzinfo=sydney_tz)

        test_date = "2025-01-05T12:00:00Z"  # Previous Sunday
        assert is_in_week_range(test_date, monday, sunday) is False

    def test_date_after_range(self):
        """Test that dates after range are not included."""
        sydney_tz = ZoneInfo('Australia/Sydney')
        monday = datetime(2025, 1, 6, 0, 0, 0, tzinfo=sydney_tz)
        sunday = datetime(2025, 1, 12, 23, 59, 59, 999999, tzinfo=sydney_tz)

        test_date = "2025-01-13T12:00:00Z"  # Next Monday
        assert is_in_week_range(test_date, monday, sunday) is False

    def test_empty_date_string(self):
        """Test that empty date string returns False."""
        sydney_tz = ZoneInfo('Australia/Sydney')
        monday = datetime(2025, 1, 6, 0, 0, 0, tzinfo=sydney_tz)
        sunday = datetime(2025, 1, 12, 23, 59, 59, 999999, tzinfo=sydney_tz)

        assert is_in_week_range("", monday, sunday) is False
        assert is_in_week_range(None, monday, sunday) is False

    def test_invalid_date_string(self):
        """Test that invalid date string returns False."""
        sydney_tz = ZoneInfo('Australia/Sydney')
        monday = datetime(2025, 1, 6, 0, 0, 0, tzinfo=sydney_tz)
        sunday = datetime(2025, 1, 12, 23, 59, 59, 999999, tzinfo=sydney_tz)

        assert is_in_week_range("not-a-date", monday, sunday) is False

    def test_timezone_conversion(self):
        """Test that timezone conversion is handled correctly."""
        sydney_tz = ZoneInfo('Australia/Sydney')
        monday = datetime(2025, 1, 6, 0, 0, 0, tzinfo=sydney_tz)
        sunday = datetime(2025, 1, 12, 23, 59, 59, 999999, tzinfo=sydney_tz)

        # UTC time that converts to Sydney time within range
        test_date = "2025-01-08T02:00:00Z"  # 1pm AEDT on Wednesday
        assert is_in_week_range(test_date, monday, sunday) is True


class TestCreateMergerSummary:
    """Test suite for create_merger_summary function."""

    def test_creates_summary_with_all_fields(self):
        """Test that summary includes all expected fields."""
        merger = {
            "merger_id": "MN-00123",
            "merger_name": "Test Merger",
            "url": "https://example.com/merger",
            "acquirers": [{"name": "Acquirer Co"}],
            "targets": [{"name": "Target Co"}],
            "effective_notification_datetime": "2025-01-01T12:00:00Z",
            "determination_publication_date": "2025-02-01T12:00:00Z",
            "end_of_determination_period": "2025-01-31T23:59:59Z",
            "accc_determination": "Approved",
            "stage": "Phase 1",
            "status": "Determined",
            "is_waiver": False,
            "phase_1_determination": "Approved",
            "phase_2_determination": None,
            "merger_description": "Test description",
            "events": [{"title": "Test event"}]
        }

        summary = create_merger_summary(merger)

        assert summary["merger_id"] == "MN-00123"
        assert summary["merger_name"] == "Test Merger"
        assert summary["url"] == "https://example.com/merger"
        assert summary["acquirers"] == [{"name": "Acquirer Co"}]
        assert summary["targets"] == [{"name": "Target Co"}]
        assert summary["accc_determination"] == "Approved"
        assert summary["is_waiver"] is False
        assert "events" in summary

    def test_handles_missing_optional_fields(self):
        """Test that summary handles missing optional fields gracefully."""
        merger = {
            "merger_id": "MN-00123",
            "merger_name": "Test Merger"
        }

        summary = create_merger_summary(merger)

        assert summary["merger_id"] == "MN-00123"
        assert summary["acquirers"] == []
        assert summary["targets"] == []
        assert summary["events"] == []
