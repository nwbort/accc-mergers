"""Tests for parse_phase2_notice: extraction of "Matters the ACCC intends to
investigate in Phase 2" boxes from Phase 2 Notice PDFs."""

import sys
import os
import unittest.mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

sys.modules.setdefault('pdfplumber', unittest.mock.MagicMock())

from parse_phase2_notice import (
    _extract_matters_boxes,
    _classify_line,
    _classify_ocr_line,
    _feed_ocr_lines,
    _feed_vector_lines,
    _MattersBoxBuilder,
)


def _line(text, size=11.0):
    return {'text': text, 'size': size}


def _ocr_line(text, gap=100, left=300):
    return {'text': text, 'gap': gap, 'left': left}


class TestClassifyLine:
    def test_matters_heading_exact(self):
        assert _classify_line(_line('Matters the ACCC intends to investigate in Phase 2')) == 'matters_heading'

    def test_matters_heading_with_box_prefix(self):
        assert _classify_line(_line('Box 1: Matters the ACCC intends to investigate in Phase 2')) == 'matters_heading'

    def test_bullet(self):
        assert _classify_line(_line('• Some concern about the market.')) == 'bullet'

    def test_alternate_bullet_glyph(self):
        assert _classify_line(_line(' A Wingdings-rendered bullet.')) == 'bullet'

    def test_numbered_paragraph(self):
        assert _classify_line(_line('3.11.The ACCC is satisfied that...')) == 'numbered_para'

    def test_large_font_is_heading(self):
        assert _classify_line(_line('Relevant areas of competition', size=14.0)) == 'heading'

    def test_body_text_is_continuation(self):
        assert _classify_line(_line('some wrapped body text')) == 'continuation'


class TestExtractMattersBoxes:
    def test_single_box_under_heading(self):
        lines = [
            _line('3. Basis for Phase 2 Notice', size=18.0),
            _line('3.1.During Phase 1, the ACCC may decide...'),
            _line('Relevant areas of competition', size=14.0),
            _line('3.5.The ACCC considers the relevant areas...'),
            _line('Matters the ACCC intends to investigate in Phase 2'),
            _line('• The extent to which markets are discrete.'),
            _line('• Whether geographic markets are narrower than national.'),
            _line('Competition effects in the supply of widgets', size=14.0),
            _line('3.9.The ACCC is satisfied that...'),
        ]
        boxes = _extract_matters_boxes(lines)
        assert len(boxes) == 1
        assert boxes[0]['heading'] == 'Relevant areas of competition'
        assert boxes[0]['items'] == [
            'The extent to which markets are discrete.',
            'Whether geographic markets are narrower than national.',
        ]

    def test_multiple_boxes_under_different_headings(self):
        lines = [
            _line('Relevant areas of competition', size=14.0),
            _line('Matters the ACCC intends to investigate in Phase 2'),
            _line('• First matter.'),
            _line('Competition effects in certain domains', size=14.0),
            _line('3.9.The ACCC is satisfied that...'),
            _line('Matters the ACCC intends to investigate in Phase 2'),
            _line('• Second matter.'),
            _line('• Third matter.'),
        ]
        boxes = _extract_matters_boxes(lines)
        assert len(boxes) == 2
        assert boxes[0]['heading'] == 'Relevant areas of competition'
        assert boxes[0]['items'] == ['First matter.']
        assert boxes[1]['heading'] == 'Competition effects in certain domains'
        assert boxes[1]['items'] == ['Second matter.', 'Third matter.']

    def test_wrapped_bullet_text_is_joined(self):
        lines = [
            _line('Matters the ACCC intends to investigate in Phase 2'),
            _line('• The extent to which alternative suppliers would'),
            _line('meaningfully constrain the merged entity post-Acquisition.'),
        ]
        boxes = _extract_matters_boxes(lines)
        assert boxes[0]['items'] == [
            'The extent to which alternative suppliers would meaningfully constrain the merged entity post-Acquisition.'
        ]

    def test_multiline_heading_merged(self):
        lines = [
            _line('Competition effects in the supply of calibration services to', size=14.0),
            _line('customers requiring multiple testing domains', size=14.0),
            _line('Matters the ACCC intends to investigate in Phase 2'),
            _line('• Some matter.'),
        ]
        boxes = _extract_matters_boxes(lines)
        assert boxes[0]['heading'] == (
            'Competition effects in the supply of calibration services to '
            'customers requiring multiple testing domains'
        )

    def test_box_with_no_preceding_heading(self):
        lines = [
            _line('3.4.The ACCC invites submissions...'),
            _line('Matters the ACCC intends to investigate in Phase 2'),
            _line('• A general matter.'),
        ]
        boxes = _extract_matters_boxes(lines)
        assert boxes[0]['heading'] is None
        assert boxes[0]['items'] == ['A general matter.']

    def test_stray_inline_sub_label_before_first_bullet_is_dropped_not_lost(self):
        # A sub-label ahead of the box's very first bullet has no item to
        # attach to, so it's dropped cleanly rather than closing the box.
        lines = [
            _line('Competitive effects in motor insurance', size=14.0),
            _line('Matters the ACCC intends to investigate in Phase 2'),
            _line('Horizontal effects'),
            _line('• A horizontal matter.'),
        ]
        boxes = _extract_matters_boxes(lines)
        assert len(boxes) == 1
        assert boxes[0]['items'] == ['A horizontal matter.']

    def test_stray_inline_sub_label_between_bullets_is_appended_not_lost(self):
        # A sub-label between two bullet groups (e.g. "Horizontal effects" /
        # "Vertical effects" splitting one box into sub-themes) has no
        # heading-level formatting to distinguish it from a wrapped
        # continuation line, so it's folded onto the preceding item rather
        # than being lost or incorrectly closing the box.
        lines = [
            _line('Matters the ACCC intends to investigate in Phase 2'),
            _line('• A horizontal matter.'),
            _line('Vertical effects'),
            _line('• A vertical matter.'),
        ]
        boxes = _extract_matters_boxes(lines)
        assert len(boxes) == 1
        assert boxes[0]['items'] == [
            'A horizontal matter. Vertical effects',
            'A vertical matter.',
        ]

    def test_no_matters_boxes_returns_empty_list(self):
        lines = [
            _line('1. Decision', size=18.0),
            _line('1.1.On 1 January 2026, a notification was lodged...'),
        ]
        assert _extract_matters_boxes(lines) == []

    def test_box_at_end_of_document_is_flushed(self):
        lines = [
            _line('Matters the ACCC intends to investigate in Phase 2'),
            _line('• Only matter, no trailing heading.'),
        ]
        boxes = _extract_matters_boxes(lines)
        assert boxes[0]['items'] == ['Only matter, no trailing heading.']


class TestClassifyOcrLine:
    """Tests for the OCR fallback used on redacted, image-only pages, where
    there's no font-size/bold info and bullet glyphs are often dropped or
    mangled by OCR - so classification instead relies on the vertical gap
    before a line and its left-indent position."""

    def test_matters_heading_exact(self):
        ctype, _ = _classify_ocr_line(_ocr_line('Matters the ACCC intends to investigate in Phase 2'), in_box=False)
        assert ctype == 'matters_heading'

    def test_numbered_paragraph(self):
        ctype, _ = _classify_ocr_line(_ocr_line('3.11.The ACCC is satisfied that...'), in_box=False)
        assert ctype == 'numbered_para'

    def test_bullet_glyph_mangled_to_letter_e(self):
        ctype, item = _classify_ocr_line(_ocr_line('e The extent to which markets are discrete.'), in_box=False)
        assert ctype == 'bullet'
        assert item == 'The extent to which markets are discrete.'

    def test_heading_shaped_line_outside_box(self):
        ctype, _ = _classify_ocr_line(
            _ocr_line('Relevant areas of competition', gap=135, left=302), in_box=False
        )
        assert ctype == 'heading'

    def test_wrapped_paragraph_continuation_is_not_a_heading(self):
        # A wrapped (non-final) line of a redaction-truncated paragraph: no
        # trailing punctuation and a big gap (since the redacted sentence
        # before it was dropped), but indented to the continuation margin
        # rather than the heading/numbered-para margin.
        ctype, _ = _classify_ocr_line(
            _ocr_line('Information before the ACCC indicates that a radius of up to', gap=163, left=446),
            in_box=False,
        )
        assert ctype == 'continuation'

    def test_small_gap_is_continuation(self):
        ctype, _ = _classify_ocr_line(_ocr_line('natural barriers in specific local areas.', gap=42, left=406), in_box=False)
        assert ctype == 'continuation'

    def test_new_block_in_box_without_bullet_glyph_is_a_new_item(self):
        ctype, item = _classify_ocr_line(
            _ocr_line('The significance of competition between Ampol and EG sites.', gap=79, left=402),
            in_box=True,
        )
        assert ctype == 'bullet'
        assert item == 'The significance of competition between Ampol and EG sites.'

    def test_heading_shaped_line_ends_a_box(self):
        # A heading appearing while a box is still open (no explicit
        # terminator paragraph in between) must still be recognised as a
        # heading, not swallowed as another bullet item.
        ctype, _ = _classify_ocr_line(
            _ocr_line('Competitive effects in the retail supply of fuel in local markets', gap=161, left=302),
            in_box=True,
        )
        assert ctype == 'heading'


class TestFeedOcrLines:
    def test_box_extracted_from_ocr_lines(self):
        builder = _MattersBoxBuilder()
        _feed_ocr_lines(builder, [
            _ocr_line('Relevant areas of competition', gap=None, left=302),
            _ocr_line('3.5. The ACCC considers...', gap=119, left=302),
            _ocr_line('Matters the ACCC intends to investigate in Phase 2', gap=189, left=331),
            _ocr_line('e The appropriate geographic dimensions of competition.', gap=94, left=331),
            _ocr_line('Competitive effects in local markets', gap=161, left=302),
        ])
        boxes = builder.finish()
        assert len(boxes) == 1
        assert boxes[0]['heading'] == 'Relevant areas of competition'
        assert boxes[0]['items'] == ['The appropriate geographic dimensions of competition.']

    def test_footnote_after_open_box_is_dropped_not_appended(self):
        builder = _MattersBoxBuilder()
        _feed_ocr_lines(builder, [
            _ocr_line('Matters the ACCC intends to investigate in Phase 2', gap=189, left=331),
            _ocr_line('e The appropriate geographic dimensions of competition.', gap=94, left=331),
            _ocr_line('3 To identify major regional centres, the ACCC used the ABS.', gap=279, left=300),
            _ocr_line('and the parties internal documents.', gap=40, left=331),
        ])
        boxes = builder.finish()
        assert boxes[0]['items'] == ['The appropriate geographic dimensions of competition.']

    def test_page_header_and_footer_are_dropped(self):
        builder = _MattersBoxBuilder()
        _feed_ocr_lines(builder, [
            _ocr_line('Acquisition is to be subject to Phase 2 review | Foo (MN-00001)', gap=None, left=300),
            _ocr_line('Matters the ACCC intends to investigate in Phase 2', gap=189, left=331),
            _ocr_line('e A matter.', gap=94, left=331),
            _ocr_line('Decision made by a division of the Commission constituted by', gap=200, left=304),
        ])
        boxes = builder.finish()
        assert boxes[0]['items'] == ['A matter.']

    def test_box_continues_across_a_vector_ocr_page_boundary(self):
        # A box opened on a normal (vector-text) page whose bullets continue
        # onto a redacted, OCR'd page must stay the same box - state has to
        # carry across the page-type transition.
        builder = _MattersBoxBuilder()
        _feed_vector_lines(builder, [
            _line('Relevant areas of competition', size=14.0),
            _line('Matters the ACCC intends to investigate in Phase 2'),
            _line('• First matter, from the vector-text page.'),
        ])
        _feed_ocr_lines(builder, [
            _ocr_line('e Second matter, recovered via OCR.', gap=94, left=331),
        ])
        boxes = builder.finish()
        assert len(boxes) == 1
        assert boxes[0]['heading'] == 'Relevant areas of competition'
        assert boxes[0]['items'] == [
            'First matter, from the vector-text page.',
            'Second matter, recovered via OCR.',
        ]
