"""Tests for utility functions: date parsing, filename sanitization, normalization."""

import sys
import os
import unittest.mock
from datetime import datetime

# Add scripts directory to path so we can import modules directly
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from date_utils import parse_iso_datetime, parse_text_to_iso
from normalization import normalize_determination

# extract_mergers has heavy transitive imports (pdfplumber, etc.)
# Mock them so we can import just the filename functions
sys.modules['parse_determination'] = unittest.mock.MagicMock()
sys.modules['parse_questionnaire'] = unittest.mock.MagicMock()
sys.modules['pdfplumber'] = unittest.mock.MagicMock()

from extract_mergers import is_safe_filename, sanitize_filename


# ---------------------------------------------------------------------------
# date_utils: parse_iso_datetime
# ---------------------------------------------------------------------------

class TestParseIsoDatetime:
    def test_iso_with_z_suffix(self):
        result = parse_iso_datetime("2025-11-21T12:00:00Z")
        assert result is not None
        assert result.year == 2025
        assert result.month == 11
        assert result.day == 21
        assert result.hour == 12

    def test_iso_with_offset(self):
        result = parse_iso_datetime("2025-11-21T12:00:00+00:00")
        assert result is not None
        assert result.year == 2025

    def test_simple_date(self):
        result = parse_iso_datetime("2025-11-21")
        assert result is not None
        assert result.year == 2025
        assert result.month == 11
        assert result.day == 21

    def test_none_input(self):
        assert parse_iso_datetime(None) is None

    def test_empty_string(self):
        assert parse_iso_datetime("") is None

    def test_invalid_string(self):
        assert parse_iso_datetime("not a date") is None

    def test_iso_without_timezone(self):
        result = parse_iso_datetime("2025-11-21T14:30:00")
        assert result is not None
        assert result.hour == 14
        assert result.minute == 30


# ---------------------------------------------------------------------------
# date_utils: parse_text_to_iso
# ---------------------------------------------------------------------------

class TestParseTextToIso:
    def test_full_month_name(self):
        assert parse_text_to_iso("Deadline: 25 August 2025") == "2025-08-25"

    def test_abbreviated_month(self):
        assert parse_text_to_iso("Due by 3 Nov 2025") == "2025-11-03"

    def test_with_time(self):
        result = parse_text_to_iso("Due on 21 November 2025", include_time=True)
        assert result == "2025-11-21T12:00:00Z"

    def test_no_date_in_text(self):
        assert parse_text_to_iso("No date here") is None

    def test_none_input(self):
        assert parse_text_to_iso(None) is None

    def test_empty_string(self):
        assert parse_text_to_iso("") is None

    def test_embedded_in_sentence(self):
        result = parse_text_to_iso("Responses should be provided by 21 November 2025 to the ACCC")
        assert result == "2025-11-21"

    def test_single_digit_day(self):
        assert parse_text_to_iso("Due 5 January 2026") == "2026-01-05"


# ---------------------------------------------------------------------------
# extract_mergers: is_safe_filename
# ---------------------------------------------------------------------------

class TestIsSafeFilename:
    def test_simple_filename(self):
        assert is_safe_filename("document.pdf") is True

    def test_filename_with_spaces(self):
        assert is_safe_filename("my document.pdf") is True

    def test_path_traversal_dotdot(self):
        assert is_safe_filename("../etc/passwd") is False

    def test_path_traversal_slash(self):
        assert is_safe_filename("path/to/file.pdf") is False

    def test_backslash(self):
        assert is_safe_filename("path\\to\\file.pdf") is False

    def test_none_input(self):
        assert is_safe_filename(None) is False

    def test_empty_string(self):
        assert is_safe_filename("") is False

    def test_whitespace_only(self):
        assert is_safe_filename("   ") is False

    def test_consecutive_spaces(self):
        assert is_safe_filename("file  name.pdf") is False

    def test_too_long(self):
        assert is_safe_filename("a" * 252 + ".pdf") is False  # 256 chars total, exceeds 255 limit

    def test_filename_with_hyphen(self):
        assert is_safe_filename("my-document.pdf") is True

    def test_filename_with_parentheses(self):
        assert is_safe_filename("document (1).pdf") is True


# ---------------------------------------------------------------------------
# extract_mergers: sanitize_filename
# ---------------------------------------------------------------------------

class TestSanitizeFilename:
    def test_colon_replacement(self):
        result = sanitize_filename("Company: Document.pdf")
        assert result is not None
        assert ":" not in result
        assert result.endswith(".pdf")

    def test_ampersand_replacement(self):
        result = sanitize_filename("Toyota & Ford.pdf")
        assert result is not None
        assert "&" not in result
        assert "and" in result

    def test_percent_replacement(self):
        result = sanitize_filename("50% acquisition.pdf")
        assert result is not None
        assert "%" not in result
        assert "pct" in result

    def test_already_safe(self):
        assert sanitize_filename("safe-file.pdf") == "safe-file.pdf"

    def test_none_input(self):
        assert sanitize_filename(None) is None

    def test_empty_string(self):
        assert sanitize_filename("") is None

    def test_path_traversal_rejected(self):
        assert sanitize_filename("../etc/passwd") is None

    def test_double_spaces_cleaned(self):
        result = sanitize_filename("Company:  Document.pdf")
        assert result is not None
        assert "  " not in result

    def test_long_filename_truncated(self):
        long_name = "a" * 260 + ".pdf"
        result = sanitize_filename(long_name)
        if result:
            assert len(result) <= 255


# ---------------------------------------------------------------------------
# normalization: normalize_determination
# ---------------------------------------------------------------------------

class TestNormalizeDetermination:
    def test_approved(self):
        assert normalize_determination("ACCC Determination Approved") == "Approved"

    def test_not_approved_before_approved(self):
        assert normalize_determination("Not approved") == "Not approved"

    def test_not_opposed(self):
        assert normalize_determination("not opposed") == "Not opposed"

    def test_declined(self):
        assert normalize_determination("Declined") == "Declined"

    def test_none_input(self):
        assert normalize_determination(None) is None

    def test_empty_string(self):
        assert normalize_determination("") is None

    def test_prefix_removal(self):
        assert normalize_determination("ACCC Determination Declined") == "Declined"

    def test_unknown_determination_passthrough(self):
        assert normalize_determination("Some other value") == "Some other value"

    def test_case_sensitivity(self):
        assert normalize_determination("approved") == "Approved"
        assert normalize_determination("not approved") == "Not approved"
