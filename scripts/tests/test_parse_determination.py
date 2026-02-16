"""Tests for parse_determination.py"""
import pytest
from scripts.parse_determination import (
    extract_commission_division,
    parse_text_as_table
)


class TestExtractCommissionDivision:
    """Test suite for extract_commission_division function."""

    def test_extract_division_sentence(self):
        """Test extraction of commission division sentence."""
        text = """
        This is the determination content.

        Determination made by a division of the Commission constituted by a
        direction issued pursuant to section 19 of the Act.
        """
        result = extract_commission_division(text)
        assert result is not None
        assert "division of the Commission" in result
        assert "section 19 of the Act" in result

    def test_extract_delegation_sentence(self):
        """Test extraction of delegation sentence."""
        text = """
        This is the determination content.

        Determination made by Commissioner Williams pursuant to a delegation
        under section 25(1) of the Act.
        """
        result = extract_commission_division(text)
        assert result is not None
        assert "Commissioner Williams" in result
        assert "delegation" in result
        assert "section 25(1)" in result

    def test_clean_multiline_sentence(self):
        """Test that multiline sentences are cleaned up."""
        text = """
        Determination made by a division
        of the Commission constituted by a
        direction issued pursuant to section 19 of the Act.
        """
        result = extract_commission_division(text)
        assert result is not None
        # Should have single spaces, not newlines
        assert "\n" not in result
        assert "  " not in result

    def test_remove_trailing_period(self):
        """Test that trailing period is removed."""
        text = "Determination made by Commissioner Williams pursuant to a delegation under section 25(1) of the Act."
        result = extract_commission_division(text)
        assert result is not None
        assert not result.endswith(".")

    def test_return_none_when_not_found(self):
        """Test that None is returned when pattern not found."""
        text = "This is some random text without the determination pattern."
        result = extract_commission_division(text)
        assert result is None

    def test_return_last_match(self):
        """Test that last match is returned when multiple exist."""
        text = """
        Determination made by Commissioner A under section 25(1) of the Act.
        Some other content here.
        Determination made by Commissioner B under section 25(1) of the Act.
        """
        result = extract_commission_division(text)
        assert result is not None
        assert "Commissioner B" in result


class TestParseTextAsTable:
    """Test suite for parse_text_as_table function."""

    def test_parse_notified_acquisition(self):
        """Test parsing of 'Notified acquisition' item."""
        text = """
        Notified acquisition
        The proposed acquisition by Company A of Company B

        Determination
        Approved
        """
        result = parse_text_as_table(text)

        # Should have at least 2 items
        assert len(result) >= 2

        # First item should be Notified acquisition
        notified = next((item for item in result if item['item'] == 'Notified acquisition'), None)
        assert notified is not None
        assert 'Company A' in notified['details']
        assert 'Company B' in notified['details']

    def test_parse_determination(self):
        """Test parsing of 'Determination' item."""
        text = """
        Determination
        Approved

        Date of determination
        1 January 2025
        """
        result = parse_text_as_table(text)

        # Should have determination item
        det = next((item for item in result if item['item'] == 'Determination'), None)
        assert det is not None
        assert 'Approved' in det['details']

    def test_parse_parties(self):
        """Test parsing of 'Parties to the Acquisition' item."""
        text = """
        Parties to the Acquisition
        Acquirer: Company A Pty Ltd
        Target: Company B Pty Ltd

        Nature of business activities
        Manufacturing and distribution
        """
        result = parse_text_as_table(text)

        parties = next((item for item in result if item['item'] == 'Parties to the Acquisition'), None)
        assert parties is not None
        assert 'Company A' in parties['details']
        assert 'Company B' in parties['details']

    def test_multiline_details(self):
        """Test that multiline details are captured."""
        text = """
        Market definition
        The relevant market is the national market for
        the supply of widgets and related services
        to commercial customers.

        Statement of issues
        No competition concerns identified.
        """
        result = parse_text_as_table(text)

        market = next((item for item in result if item['item'] == 'Market definition'), None)
        assert market is not None
        assert 'national market' in market['details']
        assert 'widgets' in market['details']

    def test_empty_text(self):
        """Test that empty text returns empty list."""
        result = parse_text_as_table("")
        assert result == []

    def test_text_without_known_items(self):
        """Test that text without known items returns empty list."""
        text = "This is some random text that doesn't match any item patterns."
        result = parse_text_as_table(text)
        assert result == []
