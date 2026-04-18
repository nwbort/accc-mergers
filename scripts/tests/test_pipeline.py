"""Tests for core pipeline logic: determination parsing, questionnaire parsing,
static data generation, cutoff logic, and extraction helpers."""

import sys
import os
import unittest.mock
from datetime import datetime, timedelta

# Add scripts directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Mock heavy transitive imports before importing modules that need them
sys.modules['pdfplumber'] = unittest.mock.MagicMock()
sys.modules['markdownify'] = unittest.mock.MagicMock()
sys.modules['requests'] = unittest.mock.MagicMock()

from parse_determination import extract_commission_division, parse_text_as_table
from parse_notice_of_competition_concerns import split_sections, extract_issue_date
from parse_questionnaire import extract_deadline, extract_questions, extract_questions_from_text
from cutoff import is_waiver_merger, get_cutoff_date, should_skip_merger
from extract_mergers import is_safe_url, get_serve_filename


# ---------------------------------------------------------------------------
# parse_determination: extract_commission_division
# ---------------------------------------------------------------------------

class TestExtractCommissionDivision:
    def test_standard_division_sentence(self):
        text = (
            "Some preamble text.\n"
            "Determination made by a division of the Commission constituted by "
            "a direction issued pursuant to section 19 of the Act"
        )
        result = extract_commission_division(text)
        assert result is not None
        assert result.startswith("Determination made by")
        assert "section 19 of the Act" in result

    def test_commissioner_delegation(self):
        text = (
            "Blah blah.\n"
            "Determination made by Commissioner Williams pursuant to a delegation "
            "under section 25(1) of the Act"
        )
        result = extract_commission_division(text)
        assert result is not None
        assert "Commissioner Williams" in result
        assert "section 25(1)" in result

    def test_multiline_match(self):
        text = (
            "Determination made by a division\n"
            "of the Commission constituted by a direction issued\n"
            "pursuant to section 19 of the Act"
        )
        result = extract_commission_division(text)
        assert result is not None
        # Should collapse whitespace
        assert "\n" not in result

    def test_trailing_period_removed(self):
        text = "Determination made by someone pursuant to section 19 of the Act."
        result = extract_commission_division(text)
        assert result is not None
        assert not result.endswith(".")

    def test_no_match(self):
        text = "This document has no commission division information."
        assert extract_commission_division(text) is None

    def test_empty_text(self):
        assert extract_commission_division("") is None

    def test_multiple_matches_returns_last(self):
        text = (
            "Determination made by Commissioner A under section 25(1) of the Act\n"
            "Some intervening text.\n"
            "Determination made by Commissioner B under section 25(1) of the Act"
        )
        result = extract_commission_division(text)
        assert "Commissioner B" in result


# ---------------------------------------------------------------------------
# parse_determination: parse_text_as_table
# ---------------------------------------------------------------------------

class TestParseTextAsTable:
    def test_single_item(self):
        text = "Notified acquisition\nAcquisition of Company B by Company A"
        result = parse_text_as_table(text)
        assert len(result) == 1
        assert result[0]['item'] == "Notified acquisition"
        assert "Acquisition of Company B" in result[0]['details']

    def test_multiple_items(self):
        text = (
            "Notified acquisition\nAcquisition of B by A\n"
            "Determination\nApproved\n"
            "Date of determination\n15 January 2025"
        )
        result = parse_text_as_table(text)
        assert len(result) == 3
        assert result[0]['item'] == "Notified acquisition"
        assert result[1]['item'] == "Determination"
        assert result[2]['item'] == "Date of determination"

    def test_multiline_details(self):
        text = (
            "Nature of business activities\n"
            "Company A operates in mining.\n"
            "Company B operates in logistics.\n"
            "Market definition\nNational market"
        )
        result = parse_text_as_table(text)
        assert len(result) == 2
        assert "mining" in result[0]['details']
        assert "logistics" in result[0]['details']

    def test_empty_text(self):
        assert parse_text_as_table("") == []

    def test_no_known_items(self):
        text = "Random text\nMore random text"
        assert parse_text_as_table(text) == []

    def test_item_with_inline_detail(self):
        text = "Determination Approved"
        result = parse_text_as_table(text)
        assert len(result) == 1
        assert result[0]['item'] == "Determination"
        assert result[0]['details'] == "Approved"

    def test_skips_blank_lines(self):
        text = (
            "Notified acquisition\n"
            "\n"
            "\n"
            "Acquisition of B by A\n"
            "Determination\nApproved"
        )
        result = parse_text_as_table(text)
        assert len(result) == 2


# ---------------------------------------------------------------------------
# parse_notice_of_competition_concerns: split_sections
# ---------------------------------------------------------------------------

class TestNOCCSplitSections:
    def test_splits_on_top_level_headings(self):
        text = (
            "1. Introduction\n"
            "1.1. Lorem ipsum.\n"
            "2. Background\n"
            "2.1. Dolor sit amet.\n"
            "3. Next steps\n"
            "3.1. Consequuntur."
        )
        result = split_sections(text)
        assert [s['item'] for s in result] == [
            "1. Introduction",
            "2. Background",
            "3. Next steps",
        ]
        assert "Lorem ipsum" in result[0]['details']
        assert "Dolor sit amet" in result[1]['details']
        assert "Consequuntur" in result[2]['details']

    def test_ignores_numbered_paragraphs(self):
        # 1.1. and 2.15. style paragraph numbers must not be treated as section headings.
        text = (
            "1. Introduction\n"
            "1.1. First paragraph.\n"
            "1.2. Second paragraph.\n"
            "2. Background\n"
            "2.15. A later paragraph."
        )
        result = split_sections(text)
        assert len(result) == 2
        assert result[0]['item'] == "1. Introduction"
        assert "1.1." in result[0]['details']
        assert "1.2." in result[0]['details']

    def test_sub_headings_remain_in_details(self):
        text = (
            "1. Introduction\n"
            "1.1. Some intro.\n"
            "2. Background\n"
            "The Acquisition\n"
            "2.1. Details about the acquisition.\n"
            "The acquirer\n"
            "2.2. Details about the acquirer."
        )
        result = split_sections(text)
        assert len(result) == 2
        assert "The Acquisition" in result[1]['details']
        assert "The acquirer" in result[1]['details']

    def test_requires_sequential_numbering(self):
        # A lone "7." heading with no "1." context should not be treated as a section.
        text = (
            "7. Something that looks like a heading\n"
            "but is actually a stray line."
        )
        assert split_sections(text) == []

    def test_empty_input(self):
        assert split_sections("") == []


# ---------------------------------------------------------------------------
# parse_notice_of_competition_concerns: extract_issue_date
# ---------------------------------------------------------------------------

class TestNOCCExtractIssueDate:
    def test_standard_sentence(self):
        text = (
            "1.3. On 5 March 2026, the ACCC issued a Notice of Competition "
            "Concerns (NOCC) to Coles Supermarkets."
        )
        assert extract_issue_date(text) == "5 March 2026"

    def test_sentence_without_comma(self):
        text = "On 27 February 2026 the ACCC issued a Notice of Competition Concerns to Ampol."
        assert extract_issue_date(text) == "27 February 2026"

    def test_no_match_returns_none(self):
        assert extract_issue_date("No issuing sentence here.") is None

    def test_empty_input(self):
        assert extract_issue_date("") is None


# ---------------------------------------------------------------------------
# parse_questionnaire: extract_deadline
# ---------------------------------------------------------------------------

class TestExtractDeadline:
    def test_simple_deadline(self):
        text = "Please respond by the date below.\nDeadline to respond: 25 August 2025\nThank you."
        result = extract_deadline(text)
        assert result == "25 August 2025"

    def test_deadline_with_time_and_timezone(self):
        text = "Deadline to respond: 5.00pm (AEDT) on 20 October 2025"
        result = extract_deadline(text)
        assert result == "20 October 2025"

    def test_single_digit_day(self):
        text = "Deadline to respond: 3 November 2025"
        result = extract_deadline(text)
        assert result == "3 November 2025"

    def test_no_deadline(self):
        text = "This questionnaire has no deadline mentioned."
        assert extract_deadline(text) is None

    def test_empty_text(self):
        assert extract_deadline("") is None

    def test_deadline_with_newline_in_date(self):
        text = "Deadline to respond: 25\nAugust 2025"
        # The regex uses DOTALL so \s+ matches newlines
        result = extract_deadline(text)
        assert result is not None
        assert "August 2025" in result


# ---------------------------------------------------------------------------
# parse_questionnaire: extract_questions
# ---------------------------------------------------------------------------

def _lines(*specs):
    """Helper to build annotated lines for extract_questions tests.

    Each spec is either a string (plain line) or a tuple (text, is_bold).
    """
    result = []
    for s in specs:
        if isinstance(s, tuple):
            result.append({'text': s[0], 'is_bold': s[1]})
        else:
            result.append({'text': s, 'is_bold': False})
    return result


class TestExtractQuestions:
    def test_simple_numbered_questions(self):
        lines = _lines(
            "Background", "Some background info.",
            ("Questions", True),
            "1. What is the nature of your business?",
            "2. How will this merger affect competition?",
            "3. Are there any barriers to entry?",
        )
        result = extract_questions(lines)
        assert len(result) == 3
        assert result[0]['number'] == 1
        assert "nature of your business" in result[0]['text']
        assert result[2]['number'] == 3

    def test_multiline_question(self):
        lines = _lines(
            ("Questions", True),
            "1. Please describe in detail",
            "the nature of your business",
            "and your market position.",
            "2. Next question.",
        )
        result = extract_questions(lines)
        assert len(result) == 2
        assert "nature of your business" in result[0]['text']
        assert "market position" in result[0]['text']

    def test_no_questions_section(self):
        lines = _lines("This document has no questions heading.")
        assert extract_questions(lines) == []

    def test_stops_at_confidentiality(self):
        lines = _lines(
            ("Questions", True),
            "1. First question?",
            "2. Second question?",
            "Confidentiality",
            "3. This should not be captured.",
        )
        result = extract_questions(lines)
        assert len(result) == 2

    def test_empty_lines(self):
        assert extract_questions([]) == []

    def test_question_with_trailing_page_number(self):
        lines = _lines(
            ("Questions", True),
            "1. What is the relevant market? 5",
            "2. Next question.",
        )
        result = extract_questions(lines)
        assert len(result) == 2
        # Trailing page number should be stripped
        assert not result[0]['text'].endswith("5")

    def test_no_section_field_when_no_sections(self):
        lines = _lines(
            ("Questions", True),
            "1. First question?",
            "2. Second question?",
        )
        result = extract_questions(lines)
        assert len(result) == 2
        assert 'section' not in result[0]
        assert 'section' not in result[1]

    def test_bold_lines_become_section_headers(self):
        lines = _lines(
            ("Questions", True),
            ("General questions", True),
            "1. Describe your business.",
            "2. Outline any concerns.",
            ("Questions for mining customers", True),
            "3. Describe your fleet.",
            "4. Identify alternative suppliers.",
        )
        result = extract_questions(lines)
        assert len(result) == 4
        assert result[0]['section'] == 'General questions'
        assert result[1]['section'] == 'General questions'
        assert result[2]['section'] == 'Questions for mining customers'
        assert result[3]['section'] == 'Questions for mining customers'

    def test_bold_header_mid_question(self):
        """Bold section header between questions saves current question first."""
        lines = _lines(
            ("Questions", True),
            "1. Describe your business.",
            "2. Provide additional info relevant",
            "to the ACCC assessment.",
            ("Independent Repairers", True),
            "3. Identify barriers to entry.",
        )
        result = extract_questions(lines)
        assert len(result) == 3
        assert "to the ACCC assessment" in result[1]['text']
        assert "Independent" not in result[1]['text']
        assert result[0]['section'] is None
        assert result[1]['section'] is None
        assert result[2]['section'] == 'Independent Repairers'

    def test_multiple_bold_sections(self):
        """Any bold non-numbered text works as a section header."""
        lines = _lines(
            ("Questions", True),
            ("General questions", True),
            "1. General Q1.",
            "2. General Q2.",
            ("Questions for OEMs", True),
            "3. OEM Q1.",
            ("Other issues", True),
            "4. Other Q1.",
        )
        result = extract_questions(lines)
        assert len(result) == 4
        assert result[0]['section'] == 'General questions'
        assert result[1]['section'] == 'General questions'
        assert result[2]['section'] == 'Questions for OEMs'
        assert result[3]['section'] == 'Other issues'

    def test_non_bold_non_numbered_line_is_continuation(self):
        """A non-bold, non-numbered line should be treated as continuation text."""
        lines = _lines(
            ("Questions", True),
            "1. First question starts here",
            "and continues on next line.",
            "2. Second question.",
        )
        result = extract_questions(lines)
        assert len(result) == 2
        assert "starts here and continues" in result[0]['text']

    def test_multiline_bold_section_header(self):
        """Consecutive bold lines should be concatenated into one section name."""
        lines = _lines(
            ("Questions", True),
            ("Questions for customers of Event Stream Processing Software and", True),
            ("Integration Software", True),
            "1. Describe your usage.",
            "2. What features matter?",
        )
        result = extract_questions(lines)
        assert len(result) == 2
        assert result[0]['section'] == 'Questions for customers of Event Stream Processing Software and Integration Software'
        assert result[1]['section'] == result[0]['section']

    def test_questions_for_not_treated_as_heading(self):
        """'Questions for ...' is a sub-section, not the main heading."""
        lines = _lines(
            ("Questions for the parties", True),
            "1. Should not match.",
        )
        # "Questions for ..." should NOT match as the main heading
        result = extract_questions(lines)
        assert len(result) == 0

    def test_heading_with_subtitle(self):
        """Heading like 'Questions – please answer all questions...'"""
        lines = _lines(
            ("Questions – please answer all questions", True),
            ("General questions", True),
            "1. Describe your business.",
            ("Questions for suppliers of ITOM software", True),
            "2. Describe your position.",
        )
        result = extract_questions(lines)
        assert len(result) == 2
        assert result[0]['section'] == 'General questions'
        assert result[1]['section'] == 'Questions for suppliers of ITOM software'

    def test_non_bold_heading(self):
        """Some PDFs have the Questions heading as non-bold (e.g. MN-25004)."""
        lines = _lines(
            "Questions – please answer all questions that are relevant to your business",
            ("General questions", True),
            "1. Describe your business.",
            "2. Outline any concerns.",
            ("Questions for suppliers of ITOM software", True),
            "3. Describe your position.",
        )
        result = extract_questions(lines)
        assert len(result) == 3
        assert result[0]['section'] == 'General questions'
        assert result[0]['number'] == 1
        assert result[2]['section'] == 'Questions for suppliers of ITOM software'


class TestExtractQuestionsFromText:
    """Tests for the plain-text fallback used when font data is unavailable."""

    def test_simple_questions(self):
        text = (
            "Questions\n"
            "1. What is your business?\n"
            "2. Any concerns?\n"
        )
        result = extract_questions_from_text(text)
        assert len(result) == 2

    def test_known_section_patterns_detected(self):
        text = (
            "Questions\n"
            "General questions\n"
            "1. Q1.\n"
            "Questions for mining customers\n"
            "2. Q2.\n"
            "Other issues\n"
            "3. Q3.\n"
        )
        result = extract_questions_from_text(text)
        assert len(result) == 3
        assert result[0]['section'] == 'General questions'
        assert result[1]['section'] == 'Questions for mining customers'
        assert result[2]['section'] == 'Other issues'

    def test_no_questions_heading(self):
        assert extract_questions_from_text("No heading here.") == []


# ---------------------------------------------------------------------------
# cutoff: is_waiver_merger
# ---------------------------------------------------------------------------

class TestIsWaiverMerger:
    def test_waiver_by_id(self):
        assert is_waiver_merger({'merger_id': 'WA-00123', 'stage': ''}) is True

    def test_waiver_by_stage(self):
        assert is_waiver_merger({'merger_id': 'MN-01016', 'stage': 'Waiver - assessment'}) is True

    def test_not_waiver(self):
        assert is_waiver_merger({'merger_id': 'MN-01016', 'stage': 'Phase 1'}) is False

    def test_empty_merger(self):
        assert is_waiver_merger({}) is False


# ---------------------------------------------------------------------------
# cutoff: get_cutoff_date
# ---------------------------------------------------------------------------

class TestGetCutoffDate:
    def test_approved_notification_has_cutoff(self):
        merger = {
            'merger_id': 'MN-01016',
            'accc_determination': 'Approved',
            'determination_publication_date': '2025-01-15T12:00:00Z',
            'stage': 'Phase 1'
        }
        result = get_cutoff_date(merger)
        assert result is not None

    def test_not_approved_no_cutoff(self):
        merger = {
            'merger_id': 'MN-01016',
            'accc_determination': 'Not opposed',
            'determination_publication_date': '2025-01-15T12:00:00Z',
            'stage': 'Phase 1'
        }
        result = get_cutoff_date(merger)
        assert result is None

    def test_waiver_always_has_cutoff_after_determination(self):
        merger = {
            'merger_id': 'WA-00123',
            'accc_determination': 'Not approved',
            'determination_publication_date': '2025-01-15T12:00:00Z',
            'stage': 'Waiver'
        }
        result = get_cutoff_date(merger)
        assert result is not None

    def test_no_determination_date_no_cutoff(self):
        merger = {
            'merger_id': 'MN-01016',
            'accc_determination': 'Approved',
            'determination_publication_date': None,
            'stage': 'Phase 1'
        }
        result = get_cutoff_date(merger)
        assert result is None


# ---------------------------------------------------------------------------
# cutoff: should_skip_merger
# ---------------------------------------------------------------------------

class TestShouldSkipMerger:
    def test_approved_past_cutoff(self):
        merger = {
            'merger_id': 'MN-01016',
            'accc_determination': 'Approved',
            'determination_publication_date': '2024-01-01T12:00:00Z',
            'stage': 'Phase 1'
        }
        # Reference date well after cutoff
        ref = datetime(2025, 1, 1)
        assert should_skip_merger(merger, reference_date=ref) is True

    def test_approved_within_cutoff(self):
        merger = {
            'merger_id': 'MN-01016',
            'accc_determination': 'Approved',
            'determination_publication_date': '2025-01-10T12:00:00Z',
            'stage': 'Phase 1'
        }
        # Reference date within 3 weeks of determination
        ref = datetime(2025, 1, 15)
        assert should_skip_merger(merger, reference_date=ref) is False

    def test_undetermined_never_skipped(self):
        merger = {
            'merger_id': 'MN-01016',
            'stage': 'Phase 1'
        }
        assert should_skip_merger(merger) is False


# ---------------------------------------------------------------------------
# extract_mergers: is_safe_url
# ---------------------------------------------------------------------------

class TestIsSafeUrl:
    def test_valid_accc_url(self):
        assert is_safe_url("https://www.accc.gov.au/some-page") is True

    def test_http_accc_url(self):
        assert is_safe_url("http://www.accc.gov.au/some-page") is True

    def test_subdomain_accc(self):
        assert is_safe_url("https://register.accc.gov.au/some-page") is True

    def test_non_accc_domain(self):
        assert is_safe_url("https://example.com/some-page") is False

    def test_ftp_scheme(self):
        assert is_safe_url("ftp://www.accc.gov.au/file") is False

    def test_empty_url(self):
        assert is_safe_url("") is False

    def test_none_url(self):
        assert is_safe_url(None) is False

    def test_javascript_scheme(self):
        assert is_safe_url("javascript:alert(1)") is False


# ---------------------------------------------------------------------------
# extract_mergers: get_serve_filename
# ---------------------------------------------------------------------------

class TestGetServeFilename:
    def test_pdf_unchanged(self):
        assert get_serve_filename("document.pdf") == "document.pdf"

    def test_docx_becomes_pdf(self):
        result = get_serve_filename("document.docx")
        assert result == "document.pdf"

    def test_other_extension_unchanged(self):
        assert get_serve_filename("image.png") == "image.png"


# ---------------------------------------------------------------------------
# generate_static_data: is_christmas_new_year_period
# ---------------------------------------------------------------------------

# Import after mocks are set up
from static_data.business_days import (
    is_christmas_new_year_period,
    _count_weekdays_in_range,
    calculate_calendar_days,
)
from static_data.enrichment import enrich_merger, extract_phase_from_event
from static_data.loaders import load_questionnaire_data
from static_data.outputs.commentary import generate as generate_commentary_json
from static_data.outputs.industries import generate_index as generate_industries_json
from static_data.outputs.questionnaires import generate as generate_questionnaire_files


class TestIsChristmasNewYearPeriod:
    def test_christmas_eve(self):
        assert is_christmas_new_year_period(datetime(2025, 12, 24)) is True

    def test_dec_23(self):
        assert is_christmas_new_year_period(datetime(2025, 12, 23)) is True

    def test_dec_22_not_included(self):
        assert is_christmas_new_year_period(datetime(2025, 12, 22)) is False

    def test_jan_1(self):
        assert is_christmas_new_year_period(datetime(2026, 1, 1)) is True

    def test_jan_10(self):
        assert is_christmas_new_year_period(datetime(2026, 1, 10)) is True

    def test_jan_11_not_included(self):
        assert is_christmas_new_year_period(datetime(2026, 1, 11)) is False

    def test_mid_year(self):
        assert is_christmas_new_year_period(datetime(2025, 6, 15)) is False


# ---------------------------------------------------------------------------
# generate_static_data: _count_weekdays_in_range
# ---------------------------------------------------------------------------

class TestCountWeekdaysInRange:
    def test_full_week(self):
        # Mon Jan 6 to Sun Jan 12, 2025 = 5 weekdays
        start = datetime(2025, 1, 6)
        end = datetime(2025, 1, 12)
        assert _count_weekdays_in_range(start, end) == 5

    def test_single_weekday(self):
        # A Monday
        d = datetime(2025, 1, 6)
        assert _count_weekdays_in_range(d, d) == 1

    def test_single_weekend_day(self):
        # A Saturday
        d = datetime(2025, 1, 4)
        assert _count_weekdays_in_range(d, d) == 0

    def test_start_after_end(self):
        start = datetime(2025, 1, 10)
        end = datetime(2025, 1, 5)
        assert _count_weekdays_in_range(start, end) == 0

    def test_two_weeks(self):
        # Mon Jan 6 to Sun Jan 19, 2025 = 10 weekdays
        start = datetime(2025, 1, 6)
        end = datetime(2025, 1, 19)
        assert _count_weekdays_in_range(start, end) == 10

    def test_weekend_only(self):
        # Sat to Sun
        start = datetime(2025, 1, 4)
        end = datetime(2025, 1, 5)
        assert _count_weekdays_in_range(start, end) == 0


# ---------------------------------------------------------------------------
# generate_static_data: calculate_calendar_days
# ---------------------------------------------------------------------------

class TestCalculateCalendarDays:
    def test_same_day(self):
        assert calculate_calendar_days("2025-01-15", "2025-01-15") == 0

    def test_one_day(self):
        assert calculate_calendar_days("2025-01-15", "2025-01-16") == 1

    def test_one_week(self):
        assert calculate_calendar_days("2025-01-01", "2025-01-08") == 7

    def test_none_start(self):
        assert calculate_calendar_days(None, "2025-01-15") is None

    def test_none_end(self):
        assert calculate_calendar_days("2025-01-15", None) is None

    def test_empty_strings(self):
        assert calculate_calendar_days("", "") is None


# ---------------------------------------------------------------------------
# generate_static_data: extract_phase_from_event
# ---------------------------------------------------------------------------

class TestExtractPhaseFromEvent:
    def test_phase_1(self):
        assert extract_phase_from_event("Phase 1 - Determination") == "Phase 1"

    def test_phase_2(self):
        assert extract_phase_from_event("Phase 2 - Detailed Assessment") == "Phase 2"

    def test_public_benefits(self):
        assert extract_phase_from_event("Public Benefits Test") == "Public Benefits"

    def test_public_benefits_lowercase(self):
        assert extract_phase_from_event("Applying public benefits test") == "Public Benefits"

    def test_waiver(self):
        assert extract_phase_from_event("Waiver Application") == "Waiver"

    def test_waiver_lowercase(self):
        assert extract_phase_from_event("waiver granted") == "Waiver"

    def test_notified(self):
        assert extract_phase_from_event("Merger notified to ACCC") == "Phase 1"

    def test_no_phase(self):
        assert extract_phase_from_event("Some random event") is None

    def test_none_input(self):
        assert extract_phase_from_event(None) is None

    def test_empty_string(self):
        assert extract_phase_from_event("") is None


# ---------------------------------------------------------------------------
# generate_static_data: enrich_merger
# ---------------------------------------------------------------------------

class TestEnrichMerger:
    def _base_merger(self):
        return {
            'merger_id': 'MN-01016',
            'merger_name': 'Test Merger',
            'accc_determination': 'Approved',
            'determination_publication_date': '2025-03-01T12:00:00Z',
            'stage': 'Phase 1 - preliminary assessment',
            'status': 'Determined',
            'events': [],
            'effective_notification_datetime': '2025-01-15T12:00:00Z',
        }

    def test_normalizes_determination(self):
        m = self._base_merger()
        m['accc_determination'] = 'ACCC Determination Approved'
        result = enrich_merger(m)
        assert result['accc_determination'] == 'Approved'

    def test_adds_is_waiver_false(self):
        result = enrich_merger(self._base_merger())
        assert result['is_waiver'] is False

    def test_adds_is_waiver_true(self):
        m = self._base_merger()
        m['merger_id'] = 'WA-00123'
        result = enrich_merger(m)
        assert result['is_waiver'] is True

    def test_phase_1_determination_set(self):
        result = enrich_merger(self._base_merger())
        assert result['phase_1_determination'] == 'Approved'
        assert result['phase_1_determination_date'] == '2025-03-01T12:00:00Z'

    def test_phase_2_determination_set(self):
        m = self._base_merger()
        m['stage'] = 'Phase 2 - detailed assessment'
        result = enrich_merger(m)
        assert result['phase_2_determination'] == 'Approved'
        assert result['phase_1_determination'] is None

    def test_public_benefits_determination_set(self):
        m = self._base_merger()
        m['stage'] = 'Public Benefits Test'
        result = enrich_merger(m)
        assert result['public_benefits_determination'] == 'Approved'

    def test_phase_2_referral_event(self):
        m = self._base_merger()
        m['accc_determination'] = None
        m['determination_publication_date'] = None
        m['stage'] = 'Phase 2 - detailed assessment'
        m['events'] = [
            {'title': 'Merger subject to Phase 2 review', 'date': '2025-02-15T12:00:00Z'}
        ]
        result = enrich_merger(m)
        assert result['phase_1_determination'] == 'Referred to phase 2'
        assert result['phase_1_determination_date'] == '2025-02-15T12:00:00Z'

    def test_phase_2_referral_event_new_phrasing(self):
        # ACCC changed the event title from "subject to Phase 2 review" to
        # "Decision to Proceed to a Phase 2 review" in 2026 (e.g. MN-65005).
        m = self._base_merger()
        m['accc_determination'] = None
        m['determination_publication_date'] = None
        m['stage'] = 'Phase 2 - detailed assessment'
        m['events'] = [
            {'title': 'Decision to Proceed to a Phase 2 review', 'date': '2026-04-16T12:00:00Z'}
        ]
        result = enrich_merger(m)
        assert result['phase_1_determination'] == 'Referred to phase 2'
        assert result['phase_1_determination_date'] == '2026-04-16T12:00:00Z'

    def test_adds_commentary(self):
        m = self._base_merger()
        commentary = {
            'MN-01016': {
                'comments': [{'text': 'Interesting merger', 'date': '2025-03-01'}]
            }
        }
        result = enrich_merger(m, commentary)
        assert len(result['comments']) == 1
        assert result['comments'][0]['text'] == 'Interesting merger'

    def test_ensures_anzsic_codes(self):
        m = self._base_merger()
        # No anzsic_codes key
        result = enrich_merger(m)
        assert result['anzsic_codes'] == []

    def test_preserves_existing_anzsic_codes(self):
        m = self._base_merger()
        m['anzsic_codes'] = [{'code': '0600', 'name': 'Mining'}]
        result = enrich_merger(m)
        assert len(result['anzsic_codes']) == 1

    def test_does_not_mutate_original(self):
        m = self._base_merger()
        original_det = m['accc_determination']
        enrich_merger(m)
        assert m['accc_determination'] == original_det

    def test_adds_phase_to_events(self):
        m = self._base_merger()
        m['events'] = [
            {'title': 'Phase 1 - Statement of Issues', 'date': '2025-02-01'},
            {'title': 'Some other event', 'date': '2025-02-10'},
        ]
        result = enrich_merger(m)
        assert result['events'][0]['phase'] == 'Phase 1'
        assert result['events'][1]['phase'] is None


# ---------------------------------------------------------------------------
# generate_static_data: generate_industries_json
# ---------------------------------------------------------------------------

class TestGenerateIndustriesJson:
    def test_groups_by_industry(self):
        mergers = [
            {'merger_id': 'MN-001', 'anzsic_codes': [{'code': '0600', 'name': 'Mining'}]},
            {'merger_id': 'MN-002', 'anzsic_codes': [{'code': '0600', 'name': 'Mining'}]},
            {'merger_id': 'MN-003', 'anzsic_codes': [{'code': '5400', 'name': 'Transport'}]},
        ]
        result = generate_industries_json(mergers)
        industries = result['industries']
        assert len(industries) == 2
        # Sorted by count descending
        assert industries[0]['name'] == 'Mining'
        assert industries[0]['merger_count'] == 2
        assert industries[1]['name'] == 'Transport'
        assert industries[1]['merger_count'] == 1

    def test_empty_mergers(self):
        result = generate_industries_json([])
        assert result == {"industries": []}

    def test_no_anzsic_codes(self):
        mergers = [{'merger_id': 'MN-001'}]
        result = generate_industries_json(mergers)
        assert result == {"industries": []}

    def test_multiple_codes_per_merger(self):
        mergers = [
            {
                'merger_id': 'MN-001',
                'anzsic_codes': [
                    {'code': '0600', 'name': 'Mining'},
                    {'code': '5400', 'name': 'Transport'}
                ]
            },
        ]
        result = generate_industries_json(mergers)
        assert len(result['industries']) == 2


# ---------------------------------------------------------------------------
# generate_static_data: generate_commentary_json
# ---------------------------------------------------------------------------

class TestGenerateCommentaryJson:
    def test_includes_mergers_with_commentary(self):
        mergers = [
            {
                'merger_id': 'MN-001',
                'merger_name': 'Merger A',
                'status': 'Determined',
                'accc_determination': 'Approved',
                'is_waiver': False,
                'effective_notification_datetime': '2025-01-01',
                'determination_publication_date': '2025-03-01',
                'stage': 'Phase 1',
                'acquirers': [],
                'targets': [],
                'anzsic_codes': [],
                'events': [],
            },
            {
                'merger_id': 'MN-002',
                'merger_name': 'Merger B',
                'status': 'Active',
                'accc_determination': None,
                'is_waiver': False,
                'effective_notification_datetime': '2025-02-01',
                'determination_publication_date': None,
                'stage': 'Phase 1',
                'acquirers': [],
                'targets': [],
                'anzsic_codes': [],
                'events': [],
            },
        ]
        commentary = {
            'MN-001': {
                'comments': [{'text': 'Good merger', 'date': '2025-03-05'}]
            }
        }
        result = generate_commentary_json(mergers, commentary)
        assert result['count'] == 1
        assert result['items'][0]['merger_id'] == 'MN-001'
        assert len(result['items'][0]['comments']) == 1

    def test_no_commentary(self):
        mergers = [{'merger_id': 'MN-001', 'merger_name': 'A', 'events': []}]
        result = generate_commentary_json(mergers, {})
        assert result['count'] == 0
        assert result['items'] == []

    def test_sorted_by_latest_comment_date(self):
        mergers = [
            {
                'merger_id': 'MN-001', 'merger_name': 'A', 'status': 'X',
                'accc_determination': None, 'is_waiver': False,
                'effective_notification_datetime': '2025-01-01',
                'determination_publication_date': None, 'stage': 'Phase 1',
                'acquirers': [], 'targets': [], 'anzsic_codes': [], 'events': [],
            },
            {
                'merger_id': 'MN-002', 'merger_name': 'B', 'status': 'X',
                'accc_determination': None, 'is_waiver': False,
                'effective_notification_datetime': '2025-02-01',
                'determination_publication_date': None, 'stage': 'Phase 1',
                'acquirers': [], 'targets': [], 'anzsic_codes': [], 'events': [],
            },
        ]
        commentary = {
            'MN-001': {'comments': [{'text': 'Old', 'date': '2025-01-01'}]},
            'MN-002': {'comments': [{'text': 'New', 'date': '2025-03-01'}]},
        }
        result = generate_commentary_json(mergers, commentary)
        assert result['items'][0]['merger_id'] == 'MN-002'
        assert result['items'][1]['merger_id'] == 'MN-001'


# ---------------------------------------------------------------------------
# generate_static_data: enrich_merger with questionnaire data
# ---------------------------------------------------------------------------

class TestEnrichMergerQuestionnaire:
    def _base_merger(self):
        return {
            'merger_id': 'MN-01016',
            'merger_name': 'Test Merger',
            'accc_determination': None,
            'determination_publication_date': None,
            'stage': 'Phase 1 - preliminary assessment',
            'status': 'Under assessment',
            'events': [],
            'effective_notification_datetime': '2025-01-15T12:00:00Z',
        }

    def test_has_questionnaire_flag_set_when_data_exists(self):
        m = self._base_merger()
        q_data = {
            'MN-01016': {
                'questions': [{'number': 1, 'text': 'Q1'}],
                'questions_count': 1,
            }
        }
        result = enrich_merger(m, questionnaire_data=q_data)
        assert result.get('has_questionnaire') is True

    def test_no_flag_when_no_questionnaire_data(self):
        m = self._base_merger()
        result = enrich_merger(m, questionnaire_data={})
        assert 'has_questionnaire' not in result

    def test_no_flag_when_questionnaire_data_is_none(self):
        m = self._base_merger()
        result = enrich_merger(m, questionnaire_data=None)
        assert 'has_questionnaire' not in result

    def test_no_flag_when_merger_not_in_data(self):
        m = self._base_merger()
        q_data = {
            'MN-99999': {
                'questions': [{'number': 1, 'text': 'Q1'}],
                'questions_count': 1,
            }
        }
        result = enrich_merger(m, questionnaire_data=q_data)
        assert 'has_questionnaire' not in result

    def test_no_flag_when_questions_list_empty(self):
        m = self._base_merger()
        q_data = {
            'MN-01016': {
                'questions': [],
                'questions_count': 0,
            }
        }
        result = enrich_merger(m, questionnaire_data=q_data)
        assert 'has_questionnaire' not in result

    def test_questionnaire_data_not_embedded(self):
        """Questionnaire data should NOT be embedded in the merger — only a flag."""
        m = self._base_merger()
        q_data = {
            'MN-01016': {
                'deadline': '25 August 2025',
                'deadline_iso': '2025-08-25',
                'file_name': 'Questionnaire.pdf',
                'questions': [{'number': 1, 'text': 'Q1'}],
                'questions_count': 1,
            }
        }
        result = enrich_merger(m, questionnaire_data=q_data)
        assert result.get('has_questionnaire') is True
        assert 'questionnaire' not in result
        assert 'questions' not in result


# ---------------------------------------------------------------------------
# generate_static_data: generate_questionnaire_files
# ---------------------------------------------------------------------------

class TestGenerateQuestionnaireFiles:
    def test_generates_files(self, tmp_path):
        q_data = {
            'MN-01016': {
                'deadline': '25 August 2025',
                'deadline_iso': '2025-08-25',
                'file_name': 'Questionnaire.pdf',
                'questions': [
                    {'number': 1, 'text': 'What is the impact?'},
                    {'number': 2, 'text': 'Describe your business.'},
                ],
                'questions_count': 2,
            },
            'MN-01017': {
                'deadline': '18 August 2025',
                'deadline_iso': '2025-08-18',
                'file_name': 'Q2.pdf',
                'questions': [{'number': 1, 'text': 'Question'}],
                'questions_count': 1,
            },
        }

        count = generate_questionnaire_files(q_data, tmp_path)
        assert count == 2

        # Verify files exist
        q_dir = tmp_path / "questionnaires"
        assert (q_dir / "MN-01016.json").exists()
        assert (q_dir / "MN-01017.json").exists()

        # Verify content
        import json
        with open(q_dir / "MN-01016.json") as f:
            data = json.load(f)
        assert data['deadline'] == '25 August 2025'
        assert data['deadline_iso'] == '2025-08-25'
        assert data['questions_count'] == 2
        assert len(data['questions']) == 2
        assert data['questions'][0]['number'] == 1
        assert data['questions'][0]['text'] == 'What is the impact?'

    def test_skips_entries_without_questions(self, tmp_path):
        q_data = {
            'MN-01016': {
                'questions': [{'number': 1, 'text': 'Q1'}],
                'questions_count': 1,
            },
            'MN-01017': {
                'questions': [],
                'questions_count': 0,
            },
        }

        count = generate_questionnaire_files(q_data, tmp_path)
        assert count == 1

        q_dir = tmp_path / "questionnaires"
        assert (q_dir / "MN-01016.json").exists()
        assert not (q_dir / "MN-01017.json").exists()

    def test_empty_data(self, tmp_path):
        count = generate_questionnaire_files({}, tmp_path)
        assert count == 0

    def test_does_not_include_file_path(self, tmp_path):
        """file_path is an internal path and should not be in the output."""
        q_data = {
            'MN-01016': {
                'file_path': 'matters/MN-01016/Questionnaire.pdf',
                'file_name': 'Questionnaire.pdf',
                'questions': [{'number': 1, 'text': 'Q1'}],
                'questions_count': 1,
            },
        }

        generate_questionnaire_files(q_data, tmp_path)

        import json
        with open(tmp_path / "questionnaires" / "MN-01016.json") as f:
            data = json.load(f)
        assert 'file_path' not in data
