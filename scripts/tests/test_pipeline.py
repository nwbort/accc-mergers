"""Tests for core pipeline logic: determination parsing, questionnaire parsing,
static data generation, cutoff logic, and extraction helpers."""

import sys
import os
import json
import unittest.mock
from datetime import datetime, timedelta

# Add scripts directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Mock heavy transitive imports before importing modules that need them
sys.modules['pdfplumber'] = unittest.mock.MagicMock()
sys.modules['markdownify'] = unittest.mock.MagicMock()
sys.modules['requests'] = unittest.mock.MagicMock()

from parse_determination import (
    extract_commission_division,
    parse_text_as_table,
    _parse_section_blocks,
)
from parse_questionnaire import extract_deadline, extract_questions, extract_questions_from_text, _extract_subpoints, _extract_bullets, _has_questionnaire_header
from cutoff import is_waiver_merger, get_cutoff_date, should_skip_merger
from extract_mergers import (
    is_safe_url,
    get_serve_filename,
    detect_inferred_phase_2,
    detect_missing_notification_dates,
    _infer_determination_date_from_events,
    _extract_anzsic_codes,
    _merge_events,
    find_pending_phase2_notice_events,
    extract_phase2_notice_data,
)
import extract_mergers
from bs4 import BeautifulSoup


# ---------------------------------------------------------------------------
# _merge_events: attachment preservation when ACCC drops a document link
# ---------------------------------------------------------------------------

class TestMergeEventsAttachmentDropped:
    """When the ACCC removes an event's document link but keeps the event as a
    plain (URL-less) timeline row, the previously captured attachment must be
    preserved on a single event rather than spawning a recurring duplicate.

    This is the MN-30003 "subject to Phase 2 review" case: a dedup PR that just
    deletes the URL-less copy is undone by the next scrape because the row keeps
    reappearing. Re-binding it to the existing event fixes the loop at source.
    """

    TITLE = "ACCC decided notification is subject to Phase 2 review"

    def _existing(self):
        return {
            "events": [
                {
                    "date": "2026-04-01T12:00:00Z",
                    "title": self.TITLE,
                    "display_title": self.TITLE,
                    "url": "https://accc.gov.au/.../phase-2-notice.pdf",
                    "url_gh": "/mergers/MN-30003/phase-2-notice.pdf",
                    "status": "live",
                },
            ],
        }

    def test_urlless_row_rebinds_to_attachment_event(self):
        # The page now shows the event only as a plain timeline row (no link).
        scraped = [{"date": "2026-04-01T12:00:00Z", "title": self.TITLE}]
        merged = _merge_events(scraped, self._existing(), "MN-30003", set())

        assert len(merged) == 1, "no duplicate should be created"
        ev = merged[0]
        assert ev["url_gh"] == "/mergers/MN-30003/phase-2-notice.pdf"
        assert ev["url"] == "https://accc.gov.au/.../phase-2-notice.pdf"
        assert ev["status"] == "live", "event is still on the page, not removed"

    def test_one_day_date_shift_still_rebinds(self):
        scraped = [{"date": "2026-04-02T12:00:00Z", "title": self.TITLE}]
        merged = _merge_events(scraped, self._existing(), "MN-30003", set())
        assert len(merged) == 1
        assert merged[0]["url_gh"] == "/mergers/MN-30003/phase-2-notice.pdf"
        assert merged[0]["status"] == "live"

    def test_event_truly_gone_is_marked_removed(self):
        # No matching timeline row: the event really disappeared from the page.
        scraped = [{"date": "2026-05-01T12:00:00Z", "title": "Some other event"}]
        merged = _merge_events(scraped, self._existing(), "MN-30003", set())
        statuses = {e["title"]: e.get("status") for e in merged}
        assert statuses[self.TITLE] == "removed"

    def test_different_title_row_not_consumed(self):
        # A genuinely different URL-less event must remain a separate event and
        # the attachment event is marked removed (its link is gone, no rebind).
        scraped = [{"date": "2026-04-01T12:00:00Z", "title": "Merger notified to ACCC"}]
        merged = _merge_events(scraped, self._existing(), "MN-30003", set())
        titles = sorted(e["title"] for e in merged)
        assert titles == sorted([self.TITLE, "Merger notified to ACCC"])


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
# parse_determination: _parse_section_blocks (Statement of reasons structure)
# ---------------------------------------------------------------------------

class TestParseSectionBlocks:
    def test_numbered_paragraph(self):
        text = (
            "2.1. When making a determination in Phase 1, the ACCC undertakes a\n"
            "competition assessment.\n"
        )
        blocks = _parse_section_blocks(text, {})
        assert len(blocks) == 1
        assert blocks[0]['type'] == 'paragraph'
        assert blocks[0]['number'] == '2.1'
        assert 'competition assessment' in blocks[0]['text']

    def test_heading_then_paragraph(self):
        text = (
            "Industry background\n"
            "Mining equipment\n"
            "2.4. Mining equipment refers to various categories.\n"
        )
        heading_info = {
            'Industry background': {'size': 14.0, 'bold': True, 'italic': False},
            'Mining equipment': {'size': 11.0, 'bold': True, 'italic': False},
        }
        blocks = _parse_section_blocks(text, heading_info)
        assert blocks[0] == {'type': 'heading', 'text': 'Industry background'}
        assert blocks[1] == {'type': 'heading', 'text': 'Mining equipment'}
        assert blocks[2]['type'] == 'paragraph'
        assert blocks[2]['number'] == '2.4'

    def test_multiline_heading_merged(self):
        text = (
            "Reduced competition arising from accessing and using competitively\n"
            "significant information about rival OEMs\n"
            "2.19. The ACCC considers...\n"
        )
        heading_info = {
            'Reduced competition arising from accessing and using competitively': {
                'size': 14.0, 'bold': True, 'italic': False,
            },
            'significant information about rival OEMs': {
                'size': 14.0, 'bold': True, 'italic': False,
            },
        }
        blocks = _parse_section_blocks(text, heading_info)
        assert blocks[0]['type'] == 'heading'
        assert 'competitively significant information' in blocks[0]['text']
        # The heading-level fields are stripped from the public output.
        assert '_size' not in blocks[0]
        assert blocks[1]['type'] == 'paragraph'

    def test_different_size_headings_not_merged(self):
        text = (
            "Industry background\n"
            "Mining equipment\n"
        )
        heading_info = {
            'Industry background': {'size': 14.0, 'bold': True, 'italic': False},
            'Mining equipment': {'size': 11.0, 'bold': True, 'italic': False},
        }
        blocks = _parse_section_blocks(text, heading_info)
        assert len(blocks) == 2
        assert blocks[0]['text'] == 'Industry background'
        assert blocks[1]['text'] == 'Mining equipment'

    def test_bullet_list(self):
        text = (
            "2.20. The information types include:\n"
            "• Maintenance strategy\n"
            "• Equipment hire rates\n"
            "• The actual usage and downtime.\n"
        )
        blocks = _parse_section_blocks(text, {})
        assert blocks[0]['type'] == 'paragraph'
        assert blocks[1]['type'] == 'bullet_list'
        assert blocks[1]['items'] == [
            'Maintenance strategy',
            'Equipment hire rates',
            'The actual usage and downtime.',
        ]

    def test_lettered_list_parens(self):
        text = (
            "2.4. Examples of mining equipment include:\n"
            "(a) Large haul trucks\n"
            "(b) Loading equipment\n"
            "(c) Drilling equipment\n"
        )
        blocks = _parse_section_blocks(text, {})
        assert blocks[1]['type'] == 'lettered_list'
        assert [it['letter'] for it in blocks[1]['items']] == ['a', 'b', 'c']
        assert blocks[1]['items'][0]['text'] == 'Large haul trucks'

    def test_lettered_list_period_after_colon(self):
        text = (
            "2.14. The ACCC has considered, by:\n"
            "a. Providing one ability.\n"
            "b. Undermining another ability.\n"
        )
        blocks = _parse_section_blocks(text, {})
        # Paragraph ending with a colon followed by "a." starts a lettered list.
        assert blocks[1]['type'] == 'lettered_list'
        assert blocks[1]['items'][0]['letter'] == 'a'
        assert blocks[1]['items'][1]['letter'] == 'b'

    def test_continuation_lines_joined(self):
        text = (
            "2.1. When making a determination in Phase 1, the ACCC undertakes\n"
            "a competition assessment in accordance with the Act.\n"
        )
        blocks = _parse_section_blocks(text, {})
        assert len(blocks) == 1
        assert 'undertakes a competition assessment' in blocks[0]['text']

    def test_bullet_continuation(self):
        text = (
            "2.20. The types of information include:\n"
            "• The life cycle and maintenance strategy for equipment, including\n"
            "estimates of the costs of maintenance\n"
            "• Parts pricing\n"
        )
        blocks = _parse_section_blocks(text, {})
        bullets = blocks[1]
        assert bullets['type'] == 'bullet_list'
        assert 'estimates of the costs of maintenance' in bullets['items'][0]
        assert bullets['items'][1] == 'Parts pricing'


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

    def test_deadline_with_day_name_and_comma(self):
        text = "Deadline to respond: Wednesday, 6 May 2026"
        result = extract_deadline(text)
        assert result == "6 May 2026"

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

    def test_questions_for_as_sole_heading(self):
        """'Questions for X' is used as the main heading when no plain 'Questions' exists."""
        lines = _lines(
            ("Questions for the parties", True),
            "1. Describe your business.",
        )
        result = extract_questions(lines)
        assert len(result) == 1
        assert result[0]['number'] == 1
        assert result[0]['section'] == 'Questions for the parties'

    def test_questions_for_all_stakeholders_pattern(self):
        """MN-10007 style: two 'Questions for X' sections, no plain 'Questions' heading."""
        lines = _lines(
            ("Questions for all stakeholders", True),
            "1. Describe your business.",
            "2. Outline any concerns.",
            "3. Provide any additional information.",
            ("Questions for stakeholders at the Port of Newcastle", True),
            "Although MAM does not have a direct ownership interest,",
            "the ACCC is considering the extent to which MAM could control.",
            "4. Identify alternative suppliers of stevedoring services.",
            "5. Identify alternative suppliers of grain export terminal services.",
        )
        result = extract_questions(lines)
        assert len(result) == 5
        assert result[0]['section'] == 'Questions for all stakeholders'
        assert result[1]['section'] == 'Questions for all stakeholders'
        assert result[2]['section'] == 'Questions for all stakeholders'
        assert result[3]['section'] == 'Questions for stakeholders at the Port of Newcastle'
        assert result[4]['section'] == 'Questions for stakeholders at the Port of Newcastle'
        assert result[3]['number'] == 4
        assert result[4]['number'] == 5

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


class TestHasQuestionnaireHeader:
    """Tests for content-based questionnaire detection (_has_questionnaire_header)."""

    def _patch_pdfplumber(self, first_page_text):
        """Patch pdfplumber via the function's own __globals__ so the test is
        immune to other test files replacing sys.modules['parse_questionnaire']."""
        page = unittest.mock.MagicMock()
        page.extract_text.return_value = first_page_text
        pdf_obj = unittest.mock.MagicMock()
        pdf_obj.pages = [page]
        mock_pdfplumber = unittest.mock.MagicMock()
        mock_pdfplumber.open.return_value.__enter__.return_value = pdf_obj
        return unittest.mock.patch.dict(
            _has_questionnaire_header.__globals__, {'pdfplumber': mock_pdfplumber}
        )

    def test_detects_questionnaire_header(self):
        with self._patch_pdfplumber("Questionnaire: Acme – Target\nMN-99999"):
            assert _has_questionnaire_header(unittest.mock.MagicMock()) is True

    def test_rejects_determination(self):
        with self._patch_pdfplumber("Determination\nSome content here."):
            assert _has_questionnaire_header(unittest.mock.MagicMock()) is False

    def test_rejects_empty_page(self):
        with self._patch_pdfplumber(""):
            assert _has_questionnaire_header(unittest.mock.MagicMock()) is False

    def test_returns_false_on_exception(self):
        broken = unittest.mock.MagicMock()
        broken.open.side_effect = Exception("bad pdf")
        with unittest.mock.patch.dict(
            _has_questionnaire_header.__globals__, {'pdfplumber': broken}
        ):
            assert _has_questionnaire_header(unittest.mock.MagicMock()) is False


class TestExtractSubpoints:
    def test_inline_comma_separated(self):
        text = (
            "Describe whether your organisation purchases guidewires as a bundled package. "
            "Please address whether guidewires are bundled with any of the following products "
            "that you procure: a. catheters, b. stent retrievers, c. neurovascular coils, "
            "d. flow diverters, and e. liquid embolic agents."
        )
        _, result = _extract_subpoints(text)
        assert len(result) == 5
        assert result[0] == {'letter': 'a', 'text': 'catheters'}
        assert result[1] == {'letter': 'b', 'text': 'stent retrievers'}
        assert result[2] == {'letter': 'c', 'text': 'neurovascular coils'}
        assert result[3] == {'letter': 'd', 'text': 'flow diverters'}
        assert result[4] == {'letter': 'e', 'text': 'liquid embolic agents'}

    def test_stem_is_text_up_to_colon(self):
        text = "Please address the following products that you procure: a. X, and b. Y."
        stem, _ = _extract_subpoints(text)
        assert stem == "Please address the following products that you procure:"

    def test_no_colon_returns_empty(self):
        assert _extract_subpoints("What is your business? a. retail b. wholesale") == (None, [])

    def test_no_subpoints_returns_empty(self):
        assert _extract_subpoints("What is the nature of your business?") == (None, [])

    def test_single_item_returns_empty(self):
        assert _extract_subpoints("Please address: a. only one thing.") == (None, [])

    def test_space_separated_subpoints(self):
        """Sub-points joined from separate PDF lines (no commas)."""
        text = "Please address each of the following: a. item one b. item two c. item three"
        _, result = _extract_subpoints(text)
        assert len(result) == 3
        assert result[0] == {'letter': 'a', 'text': 'item one'}
        assert result[1] == {'letter': 'b', 'text': 'item two'}
        assert result[2] == {'letter': 'c', 'text': 'item three'}

    def test_non_sequential_letters_returns_empty(self):
        text = "Consider: a. first thing, c. third thing skipping b."
        assert _extract_subpoints(text) == (None, [])

    def test_two_items(self):
        text = "Choose between: a. option alpha, and b. option beta."
        _, result = _extract_subpoints(text)
        assert len(result) == 2
        assert result[0] == {'letter': 'a', 'text': 'option alpha'}
        assert result[1] == {'letter': 'b', 'text': 'option beta'}


class TestExtractQuestionsWithSubpoints:
    def test_question_with_lettered_subpoints(self):
        lines = _lines(
            ("Questions", True),
            "1. Please address the following: a. item one, b. item two, and c. item three.",
            "2. Unrelated question.",
        )
        result = extract_questions(lines)
        assert len(result) == 2
        assert 'subpoints' in result[0]
        assert len(result[0]['subpoints']) == 3
        assert result[0]['subpoints'][0] == {'letter': 'a', 'text': 'item one'}
        assert result[0]['subpoints'][2] == {'letter': 'c', 'text': 'item three'}
        assert 'subpoints' not in result[1]

    def test_question_without_subpoints_has_no_field(self):
        lines = _lines(
            ("Questions", True),
            "1. Describe your business.",
        )
        result = extract_questions(lines)
        assert len(result) == 1
        assert 'subpoints' not in result[0]

    def test_multiline_subpoints(self):
        """Sub-points spread across multiple PDF lines are joined then parsed."""
        lines = _lines(
            ("Questions", True),
            "1. Describe bundling across any of the following:",
            "a. catheters, b. stent retrievers,",
            "c. neurovascular coils.",
            "2. Next question.",
        )
        result = extract_questions(lines)
        assert len(result) == 2
        assert 'subpoints' in result[0]
        assert len(result[0]['subpoints']) == 3
        assert result[0]['subpoints'][1]['letter'] == 'b'


class TestExtractBullets:
    BULLET = ''

    def test_basic(self):
        text = f'Explain whether you compete. If so: {self.BULLET} identify which products, and {self.BULLET} respond to questions 19 and 20.'
        _, result = _extract_bullets(text)
        assert result == ['identify which products', 'respond to questions 19 and 20']

    def test_no_colon_returns_empty(self):
        text = f'Some question {self.BULLET} item one {self.BULLET} item two'
        assert _extract_bullets(text) == (None, [])

    def test_stem_is_text_up_to_colon(self):
        text = f'Explain whether you compete. If so: {self.BULLET} item one {self.BULLET} item two.'
        stem, _ = _extract_bullets(text)
        assert stem == 'Explain whether you compete. If so:'

    def test_no_bullet_returns_empty(self):
        assert _extract_bullets('What is your business?') == (None, [])

    def test_strips_trailing_and(self):
        text = f'Describe, including: {self.BULLET} item one, and {self.BULLET} item two.'
        _, result = _extract_bullets(text)
        assert result == ['item one', 'item two']

    def test_no_space_after_bullet(self):
        text = f'Description, including: {self.BULLET}item one, and {self.BULLET}item two.'
        _, result = _extract_bullets(text)
        assert result == ['item one', 'item two']


class TestExtractQuestionsWithBullets:
    BULLET = ''

    def test_question_with_bullets(self):
        lines = _lines(
            ("Questions", True),
            f"1. Describe your experience, including: {self.BULLET} item one, and {self.BULLET} item two.",
            "2. Unrelated question.",
        )
        result = extract_questions(lines)
        assert len(result) == 2
        assert 'bullets' in result[0]
        assert result[0]['bullets'] == ['item one', 'item two']
        assert result[0]['text'] == 'Describe your experience, including:'
        assert 'bullets' not in result[1]

    def test_bullets_take_priority_over_subpoints(self):
        """If both patterns somehow appear, bullets win."""
        lines = _lines(
            ("Questions", True),
            f"1. Address these: {self.BULLET} item one {self.BULLET} item two with a. detail b. more.",
        )
        result = extract_questions(lines)
        assert 'bullets' in result[0]
        assert 'subpoints' not in result[0]


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
# extract_mergers: _infer_determination_date_from_events
# ---------------------------------------------------------------------------

class TestInferDeterminationDateFromEvents:
    def _base(self):
        return {
            'accc_determination': 'Approved',
            'determination_publication_date': None,
            'events': [],
        }

    def test_infers_date_from_linked_determination_event(self):
        m = self._base()
        m['events'] = [
            {'title': 'Phase 2 determination', 'date': '2026-06-02T12:00:00Z', 'url': 'https://accc.gov.au/det.pdf'},
        ]
        _infer_determination_date_from_events(m)
        assert m['determination_publication_date'] == '2026-06-02T12:00:00Z'

    def test_uses_latest_date_when_multiple_events_same_day(self):
        m = self._base()
        m['events'] = [
            {'title': 'Phase 2 determination - Summary', 'date': '2026-06-02T12:00:00Z', 'url': 'https://accc.gov.au/a.pdf'},
            {'title': 'Phase 2 determination - Statement of reasons', 'date': '2026-06-02T12:00:00Z', 'url': 'https://accc.gov.au/b.pdf'},
        ]
        _infer_determination_date_from_events(m)
        assert m['determination_publication_date'] == '2026-06-02T12:00:00Z'

    def test_uses_latest_date_for_phase1_to_phase2_merger(self):
        # Phase 1 determination document precedes Phase 2 determination document;
        # we must pick the Phase 2 (latest) date, not the Phase 1 (earliest) date.
        m = self._base()
        m['events'] = [
            {'title': 'Phase 1 determination - Referred to Phase 2', 'date': '2026-01-20T12:00:00Z', 'url': 'https://accc.gov.au/p1.pdf'},
            {'title': 'Phase 2 determination', 'date': '2026-06-02T12:00:00Z', 'url': 'https://accc.gov.au/p2.pdf'},
        ]
        _infer_determination_date_from_events(m)
        assert m['determination_publication_date'] == '2026-06-02T12:00:00Z'

    def test_skips_events_without_url(self):
        m = self._base()
        m['events'] = [
            {'title': 'Phase 2 determination', 'date': '2026-06-02T12:00:00Z'},  # no url
        ]
        _infer_determination_date_from_events(m)
        assert m['determination_publication_date'] is None

    def test_no_op_when_determination_publication_date_already_set(self):
        m = self._base()
        m['determination_publication_date'] = '2026-01-01T12:00:00Z'
        m['events'] = [
            {'title': 'Phase 2 determination', 'date': '2026-06-02T12:00:00Z', 'url': 'https://accc.gov.au/det.pdf'},
        ]
        _infer_determination_date_from_events(m)
        assert m['determination_publication_date'] == '2026-01-01T12:00:00Z'

    def test_no_op_when_no_accc_determination(self):
        m = self._base()
        m['accc_determination'] = None
        m['events'] = [
            {'title': 'Phase 2 determination', 'date': '2026-06-02T12:00:00Z', 'url': 'https://accc.gov.au/det.pdf'},
        ]
        _infer_determination_date_from_events(m)
        assert m['determination_publication_date'] is None

    def test_no_op_when_no_determination_events(self):
        m = self._base()
        m['events'] = [
            {'title': 'Merger notified to ACCC', 'date': '2025-10-10T12:00:00Z', 'url': 'https://accc.gov.au/n.pdf'},
        ]
        _infer_determination_date_from_events(m)
        assert m['determination_publication_date'] is None


# ---------------------------------------------------------------------------
# generate_static_data: is_christmas_new_year_period
# ---------------------------------------------------------------------------

# Import after mocks are set up
from static_data.business_days import (
    is_christmas_new_year_period,
    _count_weekdays_in_range,
    calculate_calendar_days,
)
from static_data.enrichment import (
    enrich_merger,
    extract_phase_from_event,
    is_phase_2_referral_event,
)
from static_data.loaders import load_questionnaire_data
from static_data.outputs.commentary import generate as generate_commentary_json
from static_data.outputs.industries import generate_index as generate_industries_json
from static_data.outputs.questionnaires import generate as generate_questionnaire_files
from static_data.outputs.noccs import generate as generate_nocc_files
from parse_nocc import (
    _parse_blocks,
    _group_blocks_into_sections,
    _is_top_level_heading,
    _is_sub_heading,
    _is_nocc_filename,
)


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

    def test_phase_2_notice_event_is_referral(self):
        # A "Phase 2 Notice" event is the mechanism that moves a matter into
        # Phase 2 (e.g. MN-30002).
        assert is_phase_2_referral_event(
            'Peter Warren - Wakeling Automotive - Phase 2 Notice'
        ) is True

    def test_infers_phase_2_when_stage_lags(self):
        # ACCC issued a Phase 2 notice but the register's stage still says
        # Phase 1 — treat the merger as Phase 2 and flag the inference.
        m = self._base_merger()
        m['accc_determination'] = None
        m['determination_publication_date'] = None
        m['stage'] = 'Phase 1 - initial assessment'
        m['events'] = [
            {'title': 'Some Merger - Phase 2 Notice', 'date': '2026-06-02T12:00:00Z'}
        ]
        result = enrich_merger(m)
        assert result['phase_2_inferred'] is True
        assert result['stage'] == 'Phase 2 - detailed assessment'
        # The notice still resolves to a Phase 1 outcome of "Referred to phase 2".
        assert result['phase_1_determination'] == 'Referred to phase 2'
        assert result['phase_1_determination_date'] == '2026-06-02T12:00:00Z'

    def test_no_inference_when_stage_already_phase_2(self):
        # When the register already shows Phase 2, there is nothing to infer.
        m = self._base_merger()
        m['accc_determination'] = None
        m['determination_publication_date'] = None
        m['stage'] = 'Phase 2 - detailed assessment'
        m['events'] = [
            {'title': 'Some Merger - Phase 2 Notice', 'date': '2026-06-02T12:00:00Z'}
        ]
        result = enrich_merger(m)
        assert 'phase_2_inferred' not in result
        assert result['stage'] == 'Phase 2 - detailed assessment'

    def test_no_inference_without_phase_2_event(self):
        m = self._base_merger()
        m['stage'] = 'Phase 1 - initial assessment'
        m['events'] = [{'title': 'Merger notified to ACCC', 'date': '2026-03-05'}]
        result = enrich_merger(m)
        assert 'phase_2_inferred' not in result
        assert result['stage'] == 'Phase 1 - initial assessment'

    def test_inference_does_not_mutate_original_stage(self):
        m = self._base_merger()
        m['stage'] = 'Phase 1 - initial assessment'
        m['events'] = [{'title': 'X - Phase 2 Notice', 'date': '2026-06-02T12:00:00Z'}]
        enrich_merger(m)
        # The genuine stage on the source record must be preserved so the
        # auto-close detection can see when the register actually updates.
        assert m['stage'] == 'Phase 1 - initial assessment'

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
# extract_mergers: detect_inferred_phase_2
# ---------------------------------------------------------------------------

class TestDetectInferredPhase2:
    def _run(self, mergers, tmp_path, monkeypatch):
        out = tmp_path / "inferred_phase_2.json"
        monkeypatch.setattr(extract_mergers, "INFERRED_PHASE_2_PATH", str(out))
        detect_inferred_phase_2(mergers)
        if not out.exists():
            return None
        with open(out) as f:
            return json.load(f)

    def test_opens_issue_when_stage_lags(self, tmp_path, monkeypatch):
        mergers = [{
            'merger_id': 'MN-30002',
            'merger_name': 'Peter Warren - Wakeling Automotive',
            'url': 'https://accc.gov.au/x',
            'stage': 'Phase 1 - initial assessment',
            'events': [{'title': 'X - Phase 2 Notice', 'date': '2026-06-02T12:00:00Z'}],
        }]
        result = self._run(mergers, tmp_path, monkeypatch)
        assert len(result['open']) == 1
        assert result['open'][0]['merger_id'] == 'MN-30002'
        assert 'MN-30002' in result['open'][0]['title']
        assert result['confirmed'] == []

    def test_confirms_close_when_stage_updates(self, tmp_path, monkeypatch):
        mergers = [{
            'merger_id': 'MN-30002',
            'merger_name': 'Peter Warren - Wakeling Automotive',
            'stage': 'Phase 2 - detailed assessment',
            'events': [{'title': 'X - Phase 2 Notice', 'date': '2026-06-02T12:00:00Z'}],
        }]
        result = self._run(mergers, tmp_path, monkeypatch)
        assert result['open'] == []
        assert result['confirmed'] == ['MN-30002']

    def test_ignores_mergers_without_phase_2_event(self, tmp_path, monkeypatch):
        mergers = [{
            'merger_id': 'MN-00001',
            'merger_name': 'Ordinary Phase 1',
            'stage': 'Phase 1 - initial assessment',
            'events': [{'title': 'Merger notified to ACCC', 'date': '2026-03-05'}],
        }]
        result = self._run(mergers, tmp_path, monkeypatch)
        # Nothing to report → file is removed / never written.
        assert result is None

    def test_removes_stale_file_when_nothing_to_report(self, tmp_path, monkeypatch):
        out = tmp_path / "inferred_phase_2.json"
        out.write_text('{"open": [{"merger_id": "MN-OLD"}], "confirmed": []}')
        monkeypatch.setattr(extract_mergers, "INFERRED_PHASE_2_PATH", str(out))
        detect_inferred_phase_2([{
            'merger_id': 'MN-00001',
            'stage': 'Phase 1 - initial assessment',
            'events': [],
        }])
        assert not out.exists()


# ---------------------------------------------------------------------------
# extract_mergers: detect_missing_notification_dates
# ---------------------------------------------------------------------------

class TestDetectMissingNotificationDates:
    def _run(self, mergers, tmp_path, monkeypatch, known_dates=None):
        out = tmp_path / "missing_notification_dates.json"
        monkeypatch.setattr(extract_mergers, "MISSING_NOTIFICATION_DATES_PATH", str(out))
        monkeypatch.setattr(extract_mergers, "KNOWN_NOTIFICATION_DATES", known_dates or {})
        detect_missing_notification_dates(mergers)
        if not out.exists():
            return None
        with open(out) as f:
            return json.load(f)

    def test_opens_issue_when_notification_date_missing(self, tmp_path, monkeypatch):
        mergers = [{
            'merger_id': 'MN-50030',
            'merger_name': 'Symal Group - Shamrock Engineering and Equipment',
            'url': 'https://accc.gov.au/x',
        }]
        result = self._run(mergers, tmp_path, monkeypatch)
        assert len(result['issues']) == 1
        assert result['issues'][0]['merger_id'] == 'MN-50030'
        assert 'MN-50030' in result['issues'][0]['title']

    def test_ignores_merger_with_notification_date(self, tmp_path, monkeypatch):
        mergers = [{
            'merger_id': 'MN-00001',
            'merger_name': 'Ordinary Phase 1',
            'effective_notification_datetime': '2026-03-05T12:00:00Z',
        }]
        result = self._run(mergers, tmp_path, monkeypatch)
        assert result is None

    def test_ignores_merger_already_in_known_dates(self, tmp_path, monkeypatch):
        mergers = [{
            'merger_id': 'MN-50030',
            'merger_name': 'Symal Group - Shamrock Engineering and Equipment',
        }]
        result = self._run(
            mergers, tmp_path, monkeypatch,
            known_dates={'MN-50030': '2026-07-01T12:00:00Z'},
        )
        assert result is None

    def test_removes_stale_file_when_nothing_to_report(self, tmp_path, monkeypatch):
        out = tmp_path / "missing_notification_dates.json"
        out.write_text('{"issues": [{"merger_id": "MN-OLD"}]}')
        monkeypatch.setattr(extract_mergers, "MISSING_NOTIFICATION_DATES_PATH", str(out))
        monkeypatch.setattr(extract_mergers, "KNOWN_NOTIFICATION_DATES", {})
        detect_missing_notification_dates([{
            'merger_id': 'MN-00001',
            'effective_notification_datetime': '2026-03-05T12:00:00Z',
        }])
        assert not out.exists()


# ---------------------------------------------------------------------------
# find_pending_phase2_notice_events / extract_phase2_notice_data
# ---------------------------------------------------------------------------

class TestFindPendingPhase2NoticeEvents:
    def test_finds_pending_event_with_downloaded_pdf(self, tmp_path, monkeypatch):
        monkeypatch.setattr(extract_mergers, 'MATTERS_DIR', str(tmp_path))
        matter_dir = tmp_path / 'MN-90009'
        matter_dir.mkdir()
        (matter_dir / 'Notice.pdf').write_bytes(b'%PDF-1.4 fake')
        mergers = [{
            'merger_id': 'MN-90009',
            'events': [{
                'title': 'Trescal - TR Calibration - Phase 2 Notice',
                'url_gh': '/mergers/MN-90009/Notice.pdf',
            }],
        }]
        pending = find_pending_phase2_notice_events(mergers)
        assert len(pending) == 1
        merger_id, event, path = pending[0]
        assert merger_id == 'MN-90009'
        assert event['title'] == 'Trescal - TR Calibration - Phase 2 Notice'
        assert path == str(matter_dir / 'Notice.pdf')

    def test_skips_already_parsed_event(self, tmp_path, monkeypatch):
        monkeypatch.setattr(extract_mergers, 'MATTERS_DIR', str(tmp_path))
        matter_dir = tmp_path / 'MN-01019'
        matter_dir.mkdir()
        (matter_dir / 'Notice.pdf').write_bytes(b'%PDF-1.4 fake')
        mergers = [{
            'merger_id': 'MN-01019',
            'events': [{
                'title': 'ACCC decided notification is subject to Phase 2 review',
                'url_gh': '/mergers/MN-01019/Notice.pdf',
                'phase2_notice_matters_to_investigate': [],
            }],
        }]
        assert find_pending_phase2_notice_events(mergers) == []

    def test_skips_non_phase2_events(self, tmp_path, monkeypatch):
        monkeypatch.setattr(extract_mergers, 'MATTERS_DIR', str(tmp_path))
        mergers = [{
            'merger_id': 'MN-00001',
            'events': [{'title': 'Merger notified to ACCC', 'url_gh': '/mergers/MN-00001/x.pdf'}],
        }]
        assert find_pending_phase2_notice_events(mergers) == []

    def test_skips_event_without_downloaded_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr(extract_mergers, 'MATTERS_DIR', str(tmp_path))
        mergers = [{
            'merger_id': 'MN-90009',
            'events': [{
                'title': 'X - Phase 2 Notice',
                'url_gh': '/mergers/MN-90009/does-not-exist.pdf',
            }],
        }]
        assert find_pending_phase2_notice_events(mergers) == []


class TestExtractPhase2NoticeData:
    def test_parses_pending_and_attaches_result(self, tmp_path, monkeypatch):
        monkeypatch.setattr(extract_mergers, 'MATTERS_DIR', str(tmp_path))
        matter_dir = tmp_path / 'MN-90009'
        matter_dir.mkdir()
        (matter_dir / 'Notice.pdf').write_bytes(b'%PDF-1.4 fake')

        boxes = [{'heading': 'Relevant areas of competition', 'items': ['A matter.']}]
        monkeypatch.setattr(
            extract_mergers, 'parse_phase2_notice_pdf',
            lambda path: {'matters_to_investigate': boxes},
        )

        event = {'title': 'X - Phase 2 Notice', 'url_gh': '/mergers/MN-90009/Notice.pdf'}
        mergers = [{'merger_id': 'MN-90009', 'events': [event]}]

        count = extract_phase2_notice_data(mergers)
        assert count == 1
        assert event['phase2_notice_matters_to_investigate'] == boxes

    def test_leaves_already_parsed_events_untouched(self, tmp_path, monkeypatch):
        # Ampol-EG Australia's regression case: once an event has a result
        # (even an empty one), it must never be re-parsed on a later run.
        monkeypatch.setattr(extract_mergers, 'MATTERS_DIR', str(tmp_path))
        calls = []
        monkeypatch.setattr(
            extract_mergers, 'parse_phase2_notice_pdf',
            lambda path: calls.append(path) or {'matters_to_investigate': []},
        )
        event = {
            'title': 'ACCC decided notification is subject to Phase 2 review',
            'url_gh': '/mergers/MN-01019/Notice.pdf',
            'phase2_notice_matters_to_investigate': [{'heading': None, 'items': ['Already parsed.']}],
        }
        mergers = [{'merger_id': 'MN-01019', 'events': [event]}]

        count = extract_phase2_notice_data(mergers)
        assert count == 0
        assert calls == []
        assert event['phase2_notice_matters_to_investigate'] == [{'heading': None, 'items': ['Already parsed.']}]

    def test_records_error_and_continues_on_parse_failure(self, tmp_path, monkeypatch):
        monkeypatch.setattr(extract_mergers, 'MATTERS_DIR', str(tmp_path))
        matter_dir = tmp_path / 'MN-90009'
        matter_dir.mkdir()
        (matter_dir / 'Notice.pdf').write_bytes(b'%PDF-1.4 fake')

        def _raise(path):
            raise ValueError('boom')
        monkeypatch.setattr(extract_mergers, 'parse_phase2_notice_pdf', _raise)

        event = {'title': 'X - Phase 2 Notice', 'url_gh': '/mergers/MN-90009/Notice.pdf'}
        mergers = [{'merger_id': 'MN-90009', 'events': [event]}]

        count = extract_phase2_notice_data(mergers)
        assert count == 0
        assert 'phase2_notice_matters_to_investigate' not in event


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
        assert result['industries'] == []
        assert result['total_industries'] == 0
        assert result['total_mergers'] == 0

    def test_no_anzsic_codes(self):
        mergers = [{'merger_id': 'MN-001'}]
        result = generate_industries_json(mergers)
        assert result['industries'] == []
        assert result['total_industries'] == 0
        assert result['total_mergers'] == 0

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


# ---------------------------------------------------------------------------
# parse_nocc: filename detection
# ---------------------------------------------------------------------------

class TestIsNoccFilename:
    def test_full_phrase(self):
        assert _is_nocc_filename(
            'Coles_Kalgoorlie - Final - Summary of Notice of Competition Concerns - March 2026.pdf'
        )

    def test_abbreviation(self):
        assert _is_nocc_filename('Ampol_EG - NOCC summary - AR version - 2 March 2026.pdf')

    def test_case_insensitive(self):
        assert _is_nocc_filename('NOTICE OF COMPETITION CONCERNS.PDF')

    def test_must_be_pdf(self):
        assert not _is_nocc_filename('Notice of Competition Concerns.docx')

    def test_unrelated_pdf_rejected(self):
        assert not _is_nocc_filename('Phase 2 Notice - Redacted.pdf')

    def test_questionnaire_rejected(self):
        assert not _is_nocc_filename('Questionnaire - Coles - 28.11.2025.pdf')


# ---------------------------------------------------------------------------
# parse_nocc: heading detection from font metadata
# ---------------------------------------------------------------------------

def _line(text, size=11.04, bold=False, italic=False):
    return {'text': text, 'size': size, 'bold': bold, 'italic': italic, 'y': 0}


class TestIsTopLevelHeading:
    def test_numbered_heading_at_h1_size(self):
        assert _is_top_level_heading(_line('1. Introduction', size=18.0, bold=True))

    def test_numbered_heading_no_space(self):
        # Real NOCCs sometimes drop the space between "1." and the title.
        assert _is_top_level_heading(_line('1.Introduction', size=18.0, bold=True))

    def test_body_sized_numbered_line_is_not_h1(self):
        assert not _is_top_level_heading(_line('1.1. Some paragraph', size=11.04))

    def test_unnumbered_heading_is_not_h1(self):
        assert not _is_top_level_heading(_line('The Acquisition', size=14.0, bold=True))


class TestIsSubHeading:
    def test_bold_14pt(self):
        assert _is_sub_heading(_line('The Acquisition', size=14.04, bold=True))

    def test_regular_14pt(self):
        # Sub-sub-headings such as "Grocery retailing in Australia" render at
        # 14pt without bold and must still be detected.
        assert _is_sub_heading(_line('Grocery retailing in Australia', size=14.04))

    def test_top_level_heading_excluded(self):
        # An H1-sized numbered line is the top-level case and must not also
        # match the sub-heading rule.
        assert not _is_sub_heading(_line('1. Introduction', size=18.0, bold=True))

    def test_numbered_paragraph_excluded(self):
        assert not _is_sub_heading(_line('1.1 Some paragraph', size=14.04, bold=True))

    def test_bullet_excluded(self):
        assert not _is_sub_heading(_line('▪ a point', size=14.04, bold=True))


# ---------------------------------------------------------------------------
# parse_nocc: _parse_blocks
# ---------------------------------------------------------------------------

class TestParseNoccBlocks:
    def test_top_level_heading_then_paragraph(self):
        lines = [
            _line('1. Introduction', size=18.0, bold=True),
            _line('1.1. The ACCC received a notification.', size=11.04),
        ]
        blocks = _parse_blocks(lines)
        assert blocks[0] == {'type': 'heading', 'level': 1, 'text': '1. Introduction'}
        assert blocks[1]['type'] == 'paragraph'
        assert blocks[1]['number'] == '1.1'
        assert 'received a notification' in blocks[1]['text']

    def test_sub_heading_between_paragraphs(self):
        lines = [
            _line('2.1. First paragraph.', size=11.04),
            _line('The Acquisition', size=14.04, bold=True),
            _line('2.2. Second paragraph.', size=11.04),
        ]
        blocks = _parse_blocks(lines)
        assert blocks[0]['type'] == 'paragraph' and blocks[0]['number'] == '2.1'
        assert blocks[1] == {
            'type': 'heading', 'level': 2, 'text': 'The Acquisition',
            '_bold': True, '_italic': False,
        }
        assert blocks[2]['type'] == 'paragraph' and blocks[2]['number'] == '2.2'

    def test_no_space_after_paragraph_number(self):
        lines = [_line('2.4.Coles operates...', size=11.04)]
        blocks = _parse_blocks(lines)
        assert blocks[0]['number'] == '2.4'
        assert blocks[0]['text'] == 'Coles operates...'

    def test_continuation_lines_joined(self):
        lines = [
            _line('1.1. First half', size=11.04),
            _line('and second half.', size=11.04),
        ]
        blocks = _parse_blocks(lines)
        assert len(blocks) == 1
        assert blocks[0]['text'] == 'First half and second half.'

    def test_bullet_list(self):
        lines = [
            _line('1.1. The ACCC considers:', size=11.04),
            _line('▪ first point', size=11.04),
            _line('▪ second point', size=11.04),
        ]
        blocks = _parse_blocks(lines)
        assert blocks[1]['type'] == 'bullet_list'
        assert blocks[1]['items'] == ['first point', 'second point']

    def test_lone_bullet_marker_collects_continuation(self):
        # Some bullet markers render on their own line with the body text on
        # the following line; the parser must keep them as a single item.
        lines = [
            _line('▪', size=11.04),
            _line('the bullet body.', size=11.04),
        ]
        blocks = _parse_blocks(lines)
        assert blocks[0]['type'] == 'bullet_list'
        assert blocks[0]['items'] == ['the bullet body.']

    def test_minus_sign_sub_bullet(self):
        # Nested sub-bullets in NOCCs use the minus-sign character.
        lines = [
            _line('1.1. Headline:', size=11.04),
            _line('−', size=11.04),
            _line('first sub-point', size=11.04),
            _line('−', size=11.04),
            _line('second sub-point', size=11.04),
        ]
        blocks = _parse_blocks(lines)
        # Paragraph followed by a bullet list of two items.
        assert blocks[0]['type'] == 'paragraph'
        assert blocks[1]['type'] == 'bullet_list'
        assert blocks[1]['items'] == ['first sub-point', 'second sub-point']

    def test_lettered_list(self):
        lines = [
            _line('1.1. Examples include:', size=11.04),
            _line('(a) first example', size=11.04),
            _line('(b) second example', size=11.04),
        ]
        blocks = _parse_blocks(lines)
        assert blocks[1]['type'] == 'lettered_list'
        assert [it['letter'] for it in blocks[1]['items']] == ['a', 'b']

    def test_two_line_sub_heading_merged(self):
        lines = [
            _line('Reduced competition arising from', size=14.04, bold=True),
            _line('access to rival information', size=14.04, bold=True),
            _line('1.1. Body.', size=11.04),
        ]
        blocks = _parse_blocks(lines)
        # The two adjacent same-style sub-heading lines collapse to one.
        sub_headings = [b for b in blocks if b['type'] == 'heading' and b.get('level') == 2]
        assert len(sub_headings) == 1
        assert sub_headings[0]['text'] == (
            'Reduced competition arising from access to rival information'
        )

    def test_different_style_sub_headings_kept_separate(self):
        # A bold 14pt section heading immediately followed by an unbold 14pt
        # sub-sub-heading must stay distinct.
        lines = [
            _line('Industry background – grocery retailing', size=14.04, bold=True),
            _line('Grocery retailing in Australia', size=14.04, bold=False),
        ]
        blocks = _parse_blocks(lines)
        sub_headings = [b for b in blocks if b['type'] == 'heading']
        assert len(sub_headings) == 2
        assert sub_headings[0]['text'] == 'Industry background – grocery retailing'
        assert sub_headings[1]['text'] == 'Grocery retailing in Australia'


# ---------------------------------------------------------------------------
# parse_nocc: _group_blocks_into_sections
# ---------------------------------------------------------------------------

class TestGroupBlocksIntoSections:
    def test_groups_under_top_level_headings(self):
        blocks = [
            {'type': 'heading', 'level': 1, 'text': '1. Introduction'},
            {'type': 'paragraph', 'number': '1.1', 'text': 'First.'},
            {'type': 'heading', 'level': 1, 'text': '2. Background'},
            {'type': 'paragraph', 'number': '2.1', 'text': 'Second.'},
        ]
        sections = _group_blocks_into_sections(blocks)
        assert len(sections) == 2
        assert sections[0]['number'] == '1'
        assert sections[0]['title'] == 'Introduction'
        assert sections[0]['blocks'][0]['number'] == '1.1'
        assert sections[1]['number'] == '2'
        assert sections[1]['title'] == 'Background'

    def test_strips_internal_heading_level_and_style_fields(self):
        blocks = [
            {'type': 'heading', 'level': 1, 'text': '1. Introduction'},
            {
                'type': 'heading', 'level': 2, 'text': 'A sub-heading',
                '_bold': True, '_italic': False,
            },
            {'type': 'paragraph', 'number': '1.1', 'text': 'Body.'},
        ]
        sections = _group_blocks_into_sections(blocks)
        sub = sections[0]['blocks'][0]
        # Internal level and style markers are dropped from the public output.
        assert sub == {'type': 'heading', 'text': 'A sub-heading'}

    def test_preamble_kept_when_blocks_precede_first_section(self):
        blocks = [
            {'type': 'paragraph', 'text': 'Stray preamble.'},
            {'type': 'heading', 'level': 1, 'text': '1. Introduction'},
            {'type': 'paragraph', 'number': '1.1', 'text': 'Body.'},
        ]
        sections = _group_blocks_into_sections(blocks)
        assert len(sections) == 2
        assert sections[0]['number'] is None
        assert sections[0]['blocks'][0]['text'] == 'Stray preamble.'
        assert sections[1]['number'] == '1'


# ---------------------------------------------------------------------------
# enrichment: has_nocc flag
# ---------------------------------------------------------------------------

class TestEnrichMergerNocc:
    def _base_merger(self):
        return {
            'merger_id': 'MN-01068',
            'merger_name': 'Test Merger',
            'accc_determination': None,
            'determination_publication_date': None,
            'stage': 'Phase 2',
            'status': 'Under assessment',
            'events': [],
            'effective_notification_datetime': '2025-11-27T12:00:00Z',
        }

    def test_flag_set_when_sections_present(self):
        m = self._base_merger()
        nocc = {'MN-01068': {'sections': [{'number': '1', 'title': 'Introduction', 'blocks': []}]}}
        result = enrich_merger(m, nocc_data=nocc)
        assert result.get('has_nocc') is True

    def test_no_flag_when_nocc_data_missing(self):
        m = self._base_merger()
        result = enrich_merger(m, nocc_data={})
        assert 'has_nocc' not in result

    def test_no_flag_when_merger_not_in_nocc_data(self):
        m = self._base_merger()
        result = enrich_merger(m, nocc_data={'MN-99999': {'sections': [{'blocks': []}]}})
        assert 'has_nocc' not in result

    def test_no_flag_when_sections_empty(self):
        m = self._base_merger()
        result = enrich_merger(m, nocc_data={'MN-01068': {'sections': []}})
        assert 'has_nocc' not in result

    def test_nocc_data_not_embedded(self):
        m = self._base_merger()
        nocc = {'MN-01068': {'sections': [{'number': '1', 'title': 'Introduction', 'blocks': []}]}}
        result = enrich_merger(m, nocc_data=nocc)
        # Only a flag is added; the parsed content is loaded separately.
        assert 'sections' not in result
        assert 'nocc' not in result


# ---------------------------------------------------------------------------
# generate_static_data: NOCC files
# ---------------------------------------------------------------------------

class TestGenerateNoccFiles:
    def test_generates_files(self, tmp_path):
        nocc_data = {
            'MN-01068': {
                'title': 'Coles – Kalgoorlie',
                'matter_id': 'MN-01068',
                'document_type': 'Notice of Competition Concerns – Summary',
                'date': '5 March 2026',
                'date_iso': '2026-03-05',
                'file_name': 'NOCC.pdf',
                'file_path': 'matters/MN-01068/NOCC.pdf',
                'sections': [
                    {'number': '1', 'title': 'Introduction', 'blocks': [
                        {'type': 'paragraph', 'number': '1.1', 'text': 'Body.'},
                    ]},
                ],
            },
        }
        count = generate_nocc_files(nocc_data, tmp_path)
        assert count == 1
        nocc_path = tmp_path / 'noccs' / 'MN-01068.json'
        assert nocc_path.exists()

        import json
        with open(nocc_path) as f:
            data = json.load(f)
        assert data['title'] == 'Coles – Kalgoorlie'
        assert data['date_iso'] == '2026-03-05'
        assert len(data['sections']) == 1
        assert data['sections'][0]['number'] == '1'

    def test_skips_entries_without_sections(self, tmp_path):
        nocc_data = {
            'MN-01068': {'sections': [{'number': '1', 'title': 'X', 'blocks': []}]},
            'MN-01069': {'sections': []},
            'MN-01070': {'error': 'parse failed', 'file_path': 'matters/MN-01070/x.pdf'},
        }
        count = generate_nocc_files(nocc_data, tmp_path)
        assert count == 1
        assert (tmp_path / 'noccs' / 'MN-01068.json').exists()
        assert not (tmp_path / 'noccs' / 'MN-01069.json').exists()
        assert not (tmp_path / 'noccs' / 'MN-01070.json').exists()

    def test_empty_data(self, tmp_path):
        assert generate_nocc_files({}, tmp_path) == 0


# ---------------------------------------------------------------------------
# extract_mergers: _extract_anzsic_codes
# ---------------------------------------------------------------------------

class TestExtractAnzsicCodes:
    def test_legacy_field_class(self):
        html = (
            '<div class="field field--name-field-acquisition-anzsic-code '
            'field--type-string field--label-inline clearfix">'
            '<h3 class="field__label">ANZSIC code(s)</h3>'
            '<div class="field__item">5420  Software Publishing;'
            '           6240  Financial Asset Investing</div></div>'
        )
        codes = _extract_anzsic_codes(BeautifulSoup(html, 'html.parser'))
        assert codes == [
            {'code': '5420', 'name': 'Software Publishing'},
            {'code': '6240', 'name': 'Financial Asset Investing'},
        ]

    def test_current_acccgov_field_class(self):
        # The ACCC renamed the field to 'field-acccgov-anzsic-code'.
        html = (
            '<div class="field field--name-field-acccgov-anzsic-code '
            'field--type-entity-reference field--label-inline '
            'field--type-entity-reference--taxonomy_term clearfix">'
            '<h3 class="field__label">ANZSIC code(s)</h3>'
            '<div class="field__item">5420 Software Publishing;'
            '           6240 Financial Asset Investing</div></div>'
        )
        codes = _extract_anzsic_codes(BeautifulSoup(html, 'html.parser'))
        assert codes == [
            {'code': '5420', 'name': 'Software Publishing'},
            {'code': '6240', 'name': 'Financial Asset Investing'},
        ]

    def test_no_anzsic_field(self):
        html = '<div class="field field--name-field-other">nothing here</div>'
        assert _extract_anzsic_codes(BeautifulSoup(html, 'html.parser')) == []
