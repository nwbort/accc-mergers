"""Tests for parse_phase2_notice: extraction of "Matters the ACCC intends to
investigate in Phase 2" boxes from Phase 2 Notice PDFs."""

import sys
import os
import unittest.mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

sys.modules.setdefault('pdfplumber', unittest.mock.MagicMock())

from parse_phase2_notice import _extract_matters_boxes, _classify_line


def _line(text, size=11.0):
    return {'text': text, 'size': size}


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
