"""Tests for parse_questionnaire.py"""
import pytest
from scripts.parse_questionnaire import (
    extract_deadline,
    parse_deadline_date,
    extract_questions
)


class TestExtractDeadline:
    """Test suite for extract_deadline function."""

    def test_extract_simple_deadline(self):
        """Test extraction of simple deadline format."""
        text = "Deadline to respond: 25 August 2025"
        result = extract_deadline(text)
        assert result == "25 August 2025"

    def test_extract_deadline_with_time(self):
        """Test extraction of deadline with time and timezone."""
        text = "Deadline to respond: 5.00pm (AEDT) on 20 October 2025"
        result = extract_deadline(text)
        assert result == "20 October 2025"

    def test_extract_from_longer_text(self):
        """Test extraction from longer text."""
        text = """
        Please submit your responses by the deadline.
        Deadline to respond: 3 November 2025
        All responses must be in writing.
        """
        result = extract_deadline(text)
        assert result == "3 November 2025"

    def test_clean_whitespace(self):
        """Test that whitespace is cleaned up."""
        text = "Deadline to respond:  25  August  2025"
        result = extract_deadline(text)
        assert "  " not in result
        assert result == "25 August 2025"

    def test_return_none_when_not_found(self):
        """Test that None is returned when pattern not found."""
        text = "This text has no deadline information."
        result = extract_deadline(text)
        assert result is None


class TestParseDeadlineDate:
    """Test suite for parse_deadline_date function."""

    def test_parse_valid_date(self):
        """Test parsing of valid date string."""
        result = parse_deadline_date("25 August 2025")
        assert result == "2025-08-25"

    def test_parse_single_digit_day(self):
        """Test parsing date with single-digit day."""
        result = parse_deadline_date("3 November 2025")
        assert result == "2025-11-03"

    def test_parse_different_months(self):
        """Test parsing various months."""
        test_cases = [
            ("1 January 2025", "2025-01-01"),
            ("15 June 2025", "2025-06-15"),
            ("31 December 2025", "2025-12-31"),
        ]
        for date_str, expected in test_cases:
            result = parse_deadline_date(date_str)
            assert result == expected

    def test_return_none_for_empty(self):
        """Test that None is returned for empty string."""
        assert parse_deadline_date("") is None
        assert parse_deadline_date(None) is None

    def test_return_none_for_invalid_format(self):
        """Test that None is returned for invalid format."""
        assert parse_deadline_date("2025-08-25") is None  # Wrong format
        assert parse_deadline_date("August 25, 2025") is None  # Wrong format


class TestExtractQuestions:
    """Test suite for extract_questions function."""

    def test_extract_simple_questions(self):
        """Test extraction of simple numbered questions."""
        text = """
        Questions

        1. What is your company name?
        2. What is your annual revenue?
        3. How many employees do you have?
        """
        result = extract_questions(text)

        assert len(result) == 3
        assert result[0]['number'] == 1
        assert 'company name' in result[0]['text'].lower()
        assert result[1]['number'] == 2
        assert 'revenue' in result[1]['text'].lower()
        assert result[2]['number'] == 3
        assert 'employees' in result[2]['text'].lower()

    def test_extract_multiline_questions(self):
        """Test extraction of questions that span multiple lines."""
        text = """
        Questions

        1. Please describe your company's business activities
        and the markets in which you operate.

        2. What is your market share?
        """
        result = extract_questions(text)

        assert len(result) == 2
        assert result[0]['number'] == 1
        assert 'business activities' in result[0]['text']
        assert 'markets' in result[0]['text']

    def test_extract_inline_questions(self):
        """Test extraction when questions appear inline without newlines."""
        text = """
        Questions

        1. Question one text here 2. Question two text here 3. Question three text
        """
        result = extract_questions(text)

        # Should detect inline question numbers
        assert len(result) >= 2

    def test_stop_at_confidentiality_section(self):
        """Test that extraction stops at 'Confidentiality' keyword."""
        text = """
        Questions

        1. What is your company name?
        2. What is your annual revenue?

        Confidentiality
        All responses will be kept confidential.
        """
        result = extract_questions(text)

        # Should only have 2 questions, not include Confidentiality section
        assert len(result) == 2
        assert all('Confidentiality' not in q['text'] for q in result)

    def test_clean_trailing_content(self):
        """Test that trailing section headings and page numbers are removed."""
        text = """
        Questions

        1. What is your company name? Questions for customers of Company A
        2. What is your revenue? 5
        """
        result = extract_questions(text)

        # Should clean trailing content
        assert len(result) == 2
        assert 'Questions for customers' not in result[0]['text']
        # Page number should be removed
        assert not result[1]['text'].endswith('5')

    def test_no_questions_section(self):
        """Test that empty list is returned when no Questions section found."""
        text = "This is some text without a Questions section."
        result = extract_questions(text)
        assert result == []

    def test_empty_text(self):
        """Test that empty text returns empty list."""
        result = extract_questions("")
        assert result == []

    def test_questions_with_sub_parts(self):
        """Test handling of questions with multiple parts."""
        text = """
        Questions

        1. Please provide the following information:
        a) Your company name
        b) Your contact details

        2. What is your annual revenue?
        """
        result = extract_questions(text)

        assert len(result) >= 2
        # First question should include sub-parts
        assert 'company name' in result[0]['text'].lower()
