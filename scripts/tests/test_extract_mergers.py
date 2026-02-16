"""Tests for extract_mergers.py"""
import pytest
from scripts.extract_mergers import (
    is_safe_filename,
    sanitize_filename,
    parse_date_from_text,
    get_serve_filename
)


class TestIsSafeFilename:
    """Test suite for is_safe_filename function."""

    def test_valid_filenames(self):
        """Test that valid filenames are accepted."""
        valid_names = [
            "document.pdf",
            "Merger-Report-2025.pdf",
            "Company Name Document.docx",
            "File_with_underscores.pdf",
            "ACCC Determination 123.pdf",
            "Café-Documents.pdf",  # Accented characters
            "Company's-Report.pdf",  # Apostrophe
        ]
        for filename in valid_names:
            assert is_safe_filename(filename) is True, f"Failed for: {filename}"

    def test_reject_path_traversal(self):
        """Test that path traversal attempts are rejected."""
        dangerous_names = [
            "../etc/passwd",
            "..\\windows\\system32",
            "docs/../../../etc/passwd",
            "file..pdf",  # '..' anywhere in name
        ]
        for filename in dangerous_names:
            assert is_safe_filename(filename) is False, f"Should reject: {filename}"

    def test_reject_path_separators(self):
        """Test that filenames with path separators are rejected."""
        assert is_safe_filename("path/to/file.pdf") is False
        assert is_safe_filename("path\\to\\file.pdf") is False

    def test_reject_empty_or_whitespace(self):
        """Test that empty or whitespace-only filenames are rejected."""
        assert is_safe_filename("") is False
        assert is_safe_filename("   ") is False
        assert is_safe_filename(None) is False

    def test_reject_no_extension(self):
        """Test that filenames without extensions are rejected."""
        assert is_safe_filename("filename_without_extension") is False

    def test_reject_too_long(self):
        """Test that overly long filenames are rejected."""
        long_name = "a" * 250 + ".pdf"
        assert is_safe_filename(long_name) is False

    def test_reject_double_spaces(self):
        """Test that filenames with double spaces are rejected."""
        assert is_safe_filename("file  name.pdf") is False

    def test_reject_invalid_characters(self):
        """Test that filenames with invalid characters are rejected."""
        invalid_names = [
            "file<name>.pdf",
            "file|name.pdf",
            "file?name.pdf",
            "file*name.pdf",
        ]
        for filename in invalid_names:
            assert is_safe_filename(filename) is False

    def test_accept_special_dashes(self):
        """Test that en-dash and em-dash are accepted."""
        assert is_safe_filename("File–with–en–dash.pdf") is True  # en-dash
        assert is_safe_filename("File—with—em—dash.pdf") is True  # em-dash


class TestSanitizeFilename:
    """Test suite for sanitize_filename function."""

    def test_sanitize_colon(self):
        """Test that colons are replaced with hyphens."""
        result = sanitize_filename("Company: Document Name.pdf")
        assert result == "Company - Document Name.pdf"
        assert is_safe_filename(result) is True

    def test_sanitize_ampersand(self):
        """Test that ampersands are replaced with 'and'."""
        result = sanitize_filename("Toyota & Ford Merger.pdf")
        assert result == "Toyota and Ford Merger.pdf"
        assert is_safe_filename(result) is True

    def test_sanitize_double_spaces(self):
        """Test that double spaces are cleaned up."""
        result = sanitize_filename("File  with  double  spaces.pdf")
        assert result == "File with double spaces.pdf"
        assert is_safe_filename(result) is True

    def test_sanitize_combined_issues(self):
        """Test sanitization of multiple issues at once."""
        result = sanitize_filename("Company: Name & Details  Document.pdf")
        assert result == "Company - Name and Details Document.pdf"
        assert is_safe_filename(result) is True

    def test_reject_path_traversal(self):
        """Test that path traversal attempts cannot be sanitized."""
        assert sanitize_filename("../etc/passwd") is None
        assert sanitize_filename("..\\windows\\system32") is None

    def test_reject_empty(self):
        """Test that empty/whitespace filenames cannot be sanitized."""
        assert sanitize_filename("") is None
        assert sanitize_filename("   ") is None
        assert sanitize_filename(None) is None

    def test_truncate_long_filenames(self):
        """Test that overly long filenames are truncated while preserving extension."""
        long_name = "a" * 300 + ".pdf"
        result = sanitize_filename(long_name)
        assert result is not None
        assert len(result) <= 255
        assert result.endswith(".pdf")
        assert is_safe_filename(result) is True

    def test_preserve_safe_filenames(self):
        """Test that already-safe filenames are returned unchanged."""
        safe_name = "Valid-Filename.pdf"
        result = sanitize_filename(safe_name)
        assert result == safe_name


class TestParseDateFromText:
    """Test suite for parse_date_from_text function."""

    def test_parse_full_month_name(self):
        """Test parsing dates with full month names."""
        result = parse_date_from_text("Deadline: 21 November 2025")
        assert result == "2025-11-21T12:00:00Z"

    def test_parse_abbreviated_month(self):
        """Test parsing dates with abbreviated month names."""
        result = parse_date_from_text("Date: 21 Nov 2025")
        assert result == "2025-11-21T12:00:00Z"

    def test_parse_single_digit_day(self):
        """Test parsing dates with single-digit days."""
        result = parse_date_from_text("Date: 3 November 2025")
        assert result == "2025-11-03T12:00:00Z"

    def test_parse_from_longer_text(self):
        """Test parsing dates embedded in longer text."""
        text = "Please respond by 25 August 2025 for consideration."
        result = parse_date_from_text(text)
        assert result == "2025-08-25T12:00:00Z"

    def test_parse_empty_text(self):
        """Test that empty text returns None."""
        assert parse_date_from_text("") is None
        assert parse_date_from_text(None) is None

    def test_parse_text_without_date(self):
        """Test that text without a date returns None."""
        result = parse_date_from_text("This text has no date in it")
        assert result is None

    def test_parse_invalid_date(self):
        """Test that invalid dates return None."""
        result = parse_date_from_text("Date: 32 November 2025")
        assert result is None


class TestGetServeFilename:
    """Test suite for get_serve_filename function."""

    def test_docx_to_pdf(self):
        """Test that DOCX filenames are converted to PDF."""
        assert get_serve_filename("document.docx") == "document.pdf"
        assert get_serve_filename("Document.DOCX") == "Document.pdf"
        assert get_serve_filename("file.Docx") == "file.pdf"

    def test_preserve_other_extensions(self):
        """Test that non-DOCX files keep their original extension."""
        assert get_serve_filename("document.pdf") == "document.pdf"
        assert get_serve_filename("image.jpg") == "image.jpg"
        assert get_serve_filename("data.json") == "data.json"

    def test_preserve_path_in_docx(self):
        """Test that the path/basename is preserved for DOCX."""
        filename = "Long Document Name.docx"
        result = get_serve_filename(filename)
        assert result == "Long Document Name.pdf"
