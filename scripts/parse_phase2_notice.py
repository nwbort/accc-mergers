#!/usr/bin/env python3
"""
Parse ACCC "Phase 2 Notice" PDFs — the decision-to-proceed-to-Phase-2 document
published under event titles like "<matter> - Phase 2 Notice" or "Decision to
Proceed to a Phase 2 review" — to extract the "Matters the ACCC intends to
investigate in Phase 2" boxes.

Each notice sets out the theories of harm the ACCC is testing and, for each,
a boxed bullet list of matters it intends to investigate further before
making a determination. This module extracts those boxes, grouped under the
heading of the section they appear in.

Some published notices are redacted by replacing whole pages with a
flattened image rather than blacking out text, so those pages yield no
extractable lines and any boxes they contained are silently absent from the
output. Callers should treat an empty ``matters_to_investigate`` list as
"not available" rather than "the ACCC raised nothing".
"""

import re
from typing import Dict, List, Optional

import pdfplumber

from parse_determination import _group_chars_into_lines

_MATTERS_HEADING_NORM = 'matters the accc intends to investigate in phase 2'

# '' / '' are Wingdings-style bullets some older Word-exported
# notices use in place of a real bullet glyph.
_BULLET_CHARS = ('•', '▪', '◦', '', '')

_NUMBERED_PARA_RE = re.compile(r'^\d+\.\d+\.?')
_PAGE_HEADER_RE = re.compile(r'^(Acquisition is to be subject to (a )?Phase 2 review|Phase 2 Notice)\s*\|')
_DECISION_FOOTER_RE = re.compile(
    r'^(Decision made by a division of the Commission|section \d+ of the Competition and Consumer Act)'
)
_PAGE_NUMBER_RE = re.compile(r'^\d+$')

# Footnote anchors/bodies and other page chrome render below this size; body
# text and the "Matters..." box heading are 11pt.
_BODY_MIN_FONT_SIZE = 10.0

# Section headings (e.g. "Relevant areas of competition", "3. Basis for
# Phase 2 Notice") render at this size or larger in every notice seen so far.
# "Matters the ACCC intends to investigate in Phase 2" itself renders at body
# size, so it never trips this threshold.
_HEADING_MIN_SIZE = 13.0


def _collect_lines(pdf) -> List[Dict]:
    """Return formatted lines from the body pages (cover page excluded).

    Running page headers/footers, page numbers and footnotes are filtered
    out so the block-classification pass below only sees real content.
    """
    lines: List[Dict] = []
    for page_idx, page in enumerate(pdf.pages):
        if page_idx == 0:
            continue
        for line in _group_chars_into_lines(page):
            text = re.sub(r'\s+', ' ', line['text']).strip()
            if not text:
                continue
            if line['size'] < _BODY_MIN_FONT_SIZE:
                continue
            if _PAGE_NUMBER_RE.match(text):
                continue
            if _PAGE_HEADER_RE.match(text) or _DECISION_FOOTER_RE.match(text):
                continue
            lines.append({'text': text, 'size': line['size']})
    return lines


def _classify_line(line: Dict) -> str:
    text = line['text']
    norm = text.lower().rstrip(':')
    if _MATTERS_HEADING_NORM in norm:
        return 'matters_heading'
    if text[0] in _BULLET_CHARS:
        return 'bullet'
    if _NUMBERED_PARA_RE.match(text):
        return 'numbered_para'
    if line['size'] >= _HEADING_MIN_SIZE:
        return 'heading'
    return 'continuation'


def _extract_matters_boxes(lines: List[Dict]) -> List[Dict[str, object]]:
    """Group ``lines`` (as produced by ``_collect_lines``) into the "Matters
    the ACCC intends to investigate in Phase 2" boxes, each attributed to the
    heading of the section it appears in.

    Some notices label matters boxes "Box 1"/"Box 2" instead of (or as well
    as) grouping them under a section heading, and some nest a short inline
    sub-label (e.g. "Horizontal effects") ahead of a box's first bullet.
    Those sub-labels are dropped rather than mistaken for a new heading, so
    bullets are never lost.
    """
    results: List[Dict[str, object]] = []
    current_heading: Optional[str] = None
    heading_open = False
    in_box = False
    items: List[str] = []
    item_buffer: Optional[str] = None
    box_heading: Optional[str] = None

    def flush_box():
        nonlocal items, item_buffer, in_box, box_heading
        if item_buffer is not None:
            items.append(item_buffer.strip())
        cleaned = [it for it in items if it]
        if cleaned:
            results.append({'heading': box_heading, 'items': cleaned})
        in_box = False
        items = []
        item_buffer = None
        box_heading = None

    for line in lines:
        ctype = _classify_line(line)

        if ctype == 'matters_heading':
            if in_box:
                flush_box()
            in_box = True
            box_heading = current_heading
            items = []
            item_buffer = None
            heading_open = False
            continue

        if in_box:
            if ctype == 'bullet':
                if item_buffer is not None:
                    items.append(item_buffer.strip())
                item_buffer = line['text'][1:].strip()
                continue
            if ctype == 'continuation':
                if item_buffer is not None:
                    item_buffer += ' ' + line['text']
                # else: a stray inline sub-label before the first bullet -
                # drop it rather than closing the box.
                continue
            flush_box()
            # Fall through so this line is still considered for heading
            # tracking below.

        if ctype == 'heading':
            if heading_open:
                current_heading += ' ' + line['text']
            else:
                current_heading = line['text']
            heading_open = True
        else:
            heading_open = False

    if in_box:
        flush_box()

    return results


def parse_phase2_notice_pdf(pdf_path: str) -> Dict[str, object]:
    """Parse a Phase 2 Notice PDF and return its "matters to investigate" boxes.

    Returns ``{'matters_to_investigate': [{'heading': str | None, 'items':
    [str, ...]}, ...]}``. The list is empty when none of the boxes could be
    extracted (e.g. a heavily redacted public version whose relevant pages
    are flattened to images with no text layer).
    """
    with pdfplumber.open(pdf_path) as pdf:
        if not pdf.pages:
            raise ValueError(f"PDF has no pages: {pdf_path}")
        lines = _collect_lines(pdf)

    return {'matters_to_investigate': _extract_matters_boxes(lines)}
