"""Tests for generate_static_data.py"""
import pytest
from datetime import datetime, timedelta
from scripts.generate_static_data import (
    is_christmas_new_year_period,
    calculate_calendar_days,
    extract_phase_from_event,
    is_waiver_merger,
    enrich_merger
)


class TestIsChristmasNewYearPeriod:
    """Test suite for is_christmas_new_year_period function."""

    def test_christmas_period(self):
        """Test dates in Christmas period (23-31 Dec)."""
        assert is_christmas_new_year_period(datetime(2025, 12, 23)) is True
        assert is_christmas_new_year_period(datetime(2025, 12, 25)) is True
        assert is_christmas_new_year_period(datetime(2025, 12, 31)) is True

    def test_new_year_period(self):
        """Test dates in New Year period (1-10 Jan)."""
        assert is_christmas_new_year_period(datetime(2026, 1, 1)) is True
        assert is_christmas_new_year_period(datetime(2026, 1, 5)) is True
        assert is_christmas_new_year_period(datetime(2026, 1, 10)) is True

    def test_outside_period(self):
        """Test dates outside the Christmas/New Year period."""
        assert is_christmas_new_year_period(datetime(2025, 12, 22)) is False
        assert is_christmas_new_year_period(datetime(2026, 1, 11)) is False
        assert is_christmas_new_year_period(datetime(2025, 6, 15)) is False

    def test_boundary_dates(self):
        """Test boundary dates of the period."""
        # Dec 22 - not in period
        assert is_christmas_new_year_period(datetime(2025, 12, 22)) is False
        # Dec 23 - first day of period
        assert is_christmas_new_year_period(datetime(2025, 12, 23)) is True
        # Jan 10 - last day of period
        assert is_christmas_new_year_period(datetime(2026, 1, 10)) is True
        # Jan 11 - not in period
        assert is_christmas_new_year_period(datetime(2026, 1, 11)) is False


class TestCalculateCalendarDays:
    """Test suite for calculate_calendar_days function."""

    def test_calculate_single_day(self):
        """Test calculation for same-day dates."""
        start = "2025-01-01T00:00:00Z"
        end = "2025-01-01T23:59:59Z"
        result = calculate_calendar_days(start, end)
        assert result == 0

    def test_calculate_one_week(self):
        """Test calculation for one week."""
        start = "2025-01-01T00:00:00Z"
        end = "2025-01-08T00:00:00Z"
        result = calculate_calendar_days(start, end)
        assert result == 7

    def test_calculate_one_month(self):
        """Test calculation for approximately one month."""
        start = "2025-01-01T00:00:00Z"
        end = "2025-02-01T00:00:00Z"
        result = calculate_calendar_days(start, end)
        assert result == 31

    def test_empty_dates(self):
        """Test that empty dates return None."""
        assert calculate_calendar_days("", "2025-01-01T00:00:00Z") is None
        assert calculate_calendar_days("2025-01-01T00:00:00Z", "") is None
        assert calculate_calendar_days(None, None) is None

    def test_invalid_dates(self):
        """Test that invalid dates return None."""
        assert calculate_calendar_days("invalid", "2025-01-01T00:00:00Z") is None
        assert calculate_calendar_days("2025-01-01T00:00:00Z", "invalid") is None


class TestExtractPhaseFromEvent:
    """Test suite for extract_phase_from_event function."""

    def test_extract_phase_1(self):
        """Test extraction of Phase 1 from event title."""
        assert extract_phase_from_event("Phase 1 determination published") == "Phase 1"
        assert extract_phase_from_event("Phase 1 - initial assessment") == "Phase 1"

    def test_extract_phase_2(self):
        """Test extraction of Phase 2 from event title."""
        assert extract_phase_from_event("Phase 2 determination published") == "Phase 2"
        assert extract_phase_from_event("Subject to Phase 2 review") == "Phase 2"

    def test_extract_public_benefits(self):
        """Test extraction of Public Benefits phase."""
        assert extract_phase_from_event("Public Benefits assessment") == "Public Benefits"
        assert extract_phase_from_event("Assessment of public benefits") == "Public Benefits"

    def test_extract_waiver(self):
        """Test extraction of Waiver phase."""
        assert extract_phase_from_event("Waiver application") == "Waiver"
        assert extract_phase_from_event("waiver decision published") == "Waiver"

    def test_extract_notification(self):
        """Test that notification events with 'notified' keyword are Phase 1."""
        assert extract_phase_from_event("Merger notified to ACCC") == "Phase 1"
        # "Notification received" doesn't contain "notified" so returns None
        assert extract_phase_from_event("Notification received") is None

    def test_no_phase_extracted(self):
        """Test that None is returned when no phase can be extracted."""
        assert extract_phase_from_event("Some other event") is None
        assert extract_phase_from_event("") is None
        assert extract_phase_from_event(None) is None


class TestIsWaiverMerger:
    """Test suite for is_waiver_merger function."""

    def test_waiver_by_id(self):
        """Test detection by merger_id prefix."""
        merger = {"merger_id": "WA-00123", "stage": ""}
        assert is_waiver_merger(merger) is True

    def test_waiver_by_stage(self):
        """Test detection by Waiver in stage."""
        merger = {"merger_id": "MN-00123", "stage": "Waiver application"}
        assert is_waiver_merger(merger) is True

    def test_not_waiver(self):
        """Test that regular mergers are not detected as waivers."""
        merger = {"merger_id": "MN-00123", "stage": "Phase 1"}
        assert is_waiver_merger(merger) is False


class TestEnrichMerger:
    """Test suite for enrich_merger function."""

    def test_adds_is_waiver_flag(self):
        """Test that is_waiver flag is added."""
        merger = {"merger_id": "WA-00123"}
        enriched = enrich_merger(merger)
        assert enriched["is_waiver"] is True

        merger = {"merger_id": "MN-00123"}
        enriched = enrich_merger(merger)
        assert enriched["is_waiver"] is False

    def test_normalizes_determination(self):
        """Test that determination is normalized."""
        merger = {
            "merger_id": "MN-00123",
            "accc_determination": "ACCC Determination Approved"
        }
        enriched = enrich_merger(merger)
        assert enriched["accc_determination"] == "Approved"

    def test_adds_phase_determinations(self):
        """Test that phase-specific determinations are extracted."""
        merger = {
            "merger_id": "MN-00123",
            "stage": "Phase 1 - initial assessment",
            "accc_determination": "Approved",
            "determination_publication_date": "2025-01-15T12:00:00Z",
            "events": []
        }
        enriched = enrich_merger(merger)

        assert enriched["phase_1_determination"] == "Approved"
        assert enriched["phase_1_determination_date"] == "2025-01-15T12:00:00Z"
        assert enriched["phase_2_determination"] is None

    def test_detects_phase_2_referral(self):
        """Test detection of Phase 2 referral from events."""
        merger = {
            "merger_id": "MN-00123",
            "events": [
                {
                    "title": "Merger subject to Phase 2 review",
                    "date": "2025-01-10T12:00:00Z"
                }
            ]
        }
        enriched = enrich_merger(merger)

        assert enriched["phase_1_determination"] == "Referred to phase 2"
        assert enriched["phase_1_determination_date"] == "2025-01-10T12:00:00Z"

    def test_ensures_anzsic_codes_exist(self):
        """Test that anzsic_codes list exists even if missing."""
        merger = {"merger_id": "MN-00123"}
        enriched = enrich_merger(merger)
        assert "anzsic_codes" in enriched
        assert enriched["anzsic_codes"] == []

    def test_adds_phase_to_events(self):
        """Test that phase is added to events without it."""
        merger = {
            "merger_id": "MN-00123",
            "events": [
                {"title": "Phase 1 determination published"},
                {"title": "Some other event"}
            ]
        }
        enriched = enrich_merger(merger)

        assert enriched["events"][0]["phase"] == "Phase 1"
        # Second event has no detectable phase
        assert enriched["events"][1]["phase"] is None

    def test_preserves_existing_phase_in_events(self):
        """Test that existing phase in events is preserved."""
        merger = {
            "merger_id": "MN-00123",
            "events": [
                {"title": "Test event", "phase": "Phase 2"}
            ]
        }
        enriched = enrich_merger(merger)

        assert enriched["events"][0]["phase"] == "Phase 2"

    def test_adds_commentary_when_provided(self):
        """Test that commentary is added when available."""
        merger = {"merger_id": "MN-00123"}
        commentary = {
            "MN-00123": {
                "commentary": "Test commentary",
                "tags": ["competition", "market-power"]
            }
        }
        enriched = enrich_merger(merger, commentary)

        assert "commentary" in enriched
        assert enriched["commentary"]["commentary"] == "Test commentary"
        assert "competition" in enriched["commentary"]["tags"]

    def test_no_commentary_when_not_provided(self):
        """Test that no commentary is added when not available."""
        merger = {"merger_id": "MN-00123"}
        enriched = enrich_merger(merger, {})

        assert "commentary" not in enriched
