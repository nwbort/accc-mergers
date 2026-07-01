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

Some published notices redact individual paragraphs by flattening the whole
page to an image (rather than blacking out just the redacted text), so those
pages carry no extractable text layer even though most of the page — often
including a "Matters..." box — is still visible to the eye. Such pages are
OCR'd as a fallback: real character/font info isn't available from OCR, so
box and heading boundaries there are inferred from bullet-glyph remnants and
the vertical gap between lines instead (see ``_classify_ocr_line``).
"""

import re
import sys
from typing import Dict, List, Optional, Tuple

import pdfplumber

from parse_determination import _group_chars_into_lines

_MATTERS_HEADING_NORM = 'matters the accc intends to investigate in phase 2'

# U+F0B7 / U+F0A7 are Wingdings-style bullets some older Word-exported
# notices use in place of a real bullet glyph.
_BULLET_CHARS = ('•', '▪', '◦', chr(0xF0B7), chr(0xF0A7))

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


class _MattersBoxBuilder:
    """Incrementally groups classified lines into "Matters..." boxes.

    Shared between the vector-text and OCR line sources (see
    ``_feed_vector_lines`` / ``_feed_ocr_lines`` below) so heading/box state
    carries correctly across a page-type boundary — e.g. a box whose bullets
    start on a normal page and continue onto a redacted, OCR'd one.
    """

    def __init__(self):
        self.results: List[Dict[str, object]] = []
        self.current_heading: Optional[str] = None
        self._heading_open = False
        self.in_box = False
        self._items: List[str] = []
        self._item_buffer: Optional[str] = None
        self._box_heading: Optional[str] = None

    def _flush_box(self):
        if self._item_buffer is not None:
            self._items.append(self._item_buffer.strip())
        cleaned = [it for it in self._items if it]
        if cleaned:
            self.results.append({'heading': self._box_heading, 'items': cleaned})
        self.in_box = False
        self._items = []
        self._item_buffer = None
        self._box_heading = None

    def feed(self, ctype: str, text: str, item_text: Optional[str] = None):
        if ctype == 'matters_heading':
            if self.in_box:
                self._flush_box()
            self.in_box = True
            self._box_heading = self.current_heading
            self._items = []
            self._item_buffer = None
            self._heading_open = False
            return

        if self.in_box:
            if ctype == 'bullet':
                if self._item_buffer is not None:
                    self._items.append(self._item_buffer.strip())
                self._item_buffer = (item_text if item_text is not None else text).strip()
                return
            if ctype == 'continuation':
                if self._item_buffer is not None:
                    self._item_buffer += ' ' + text
                # else: a stray inline sub-label before the first bullet -
                # drop it rather than closing the box.
                return
            self._flush_box()
            # Fall through so this line is still considered for heading
            # tracking below.

        if ctype == 'heading':
            if self._heading_open:
                self.current_heading += ' ' + text
            else:
                self.current_heading = text
            self._heading_open = True
        else:
            self._heading_open = False

    def finish(self) -> List[Dict[str, object]]:
        if self.in_box:
            self._flush_box()
        return self.results


# ---------------------------------------------------------------------------
# Vector-text pages (the normal case: a real, selectable text layer)
# ---------------------------------------------------------------------------

def _collect_page_lines(page) -> List[Dict]:
    """Return formatted lines from a body page with header/footer/footnote
    chrome filtered out."""
    lines: List[Dict] = []
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


def _feed_vector_lines(builder: _MattersBoxBuilder, lines: List[Dict]):
    for line in lines:
        ctype = _classify_line(line)
        item_text = line['text'][1:].strip() if ctype == 'bullet' else None
        builder.feed(ctype, line['text'], item_text)


def _extract_matters_boxes(lines: List[Dict]) -> List[Dict[str, object]]:
    """Run the vector-text pipeline over a flat line list and return its boxes."""
    builder = _MattersBoxBuilder()
    _feed_vector_lines(builder, lines)
    return builder.finish()


# ---------------------------------------------------------------------------
# Image-only pages (redacted pages flattened to a picture with no text layer)
# ---------------------------------------------------------------------------

# Common OCR mangles of a bullet glyph, rendered as a stray letter (the real
# bullet dot is usually too small for OCR to recognise). Requires a capital
# letter straight after so real words/footnote markers aren't matched.
_OCR_BULLET_PREFIX_RE = re.compile(r'^[el«]\s+([A-Z].*)$')

# A bare 1-2 digit footnote anchor fused onto the footnote body text (the
# superscript can't be represented separately by OCR). Footnotes always
# trail at the bottom of a page in these notices, so once one is seen the
# rest of that page's lines are dropped rather than risking them being
# folded into whatever bullet item was open.
_OCR_FOOTNOTE_RE = re.compile(r'^\d{1,2}\s+[A-Z]')

# Resolution used to render image-only pages before OCR.
_OCR_RESOLUTION = 300

# Vertical pixel gap (at _OCR_RESOLUTION) above which a line is judged to
# start a new heading/bullet rather than continue the previous one. OCR
# gives no font-size/bold info, so this substitutes for it. Calibrated
# against sampled notices: wrapped continuation lines run ~40-60px, new
# paragraphs/bullets ~70-190px.
_OCR_NEW_BLOCK_GAP = 68


def _page_needs_ocr(page) -> bool:
    return len(page.chars) == 0 and len(page.images) > 0


def phase2_notice_needs_ocr(pdf_path: str) -> bool:
    """Return True if any body page of the PDF has no extractable text layer
    and would need the OCR fallback to parse fully.

    Lets callers (e.g. a CI step) decide whether to install Tesseract before
    parsing, instead of requiring it unconditionally for every run.
    """
    with pdfplumber.open(pdf_path) as pdf:
        return any(_page_needs_ocr(page) for page in pdf.pages[1:])


def _ocr_page_lines(page) -> List[Dict]:
    """OCR an image-only page and return line dicts with a ``gap`` (vertical
    pixel distance from the previous line, or None for the page's first
    line) in place of font info.
    """
    import pytesseract
    from pytesseract import Output

    image = page.to_image(resolution=_OCR_RESOLUTION).original
    data = pytesseract.image_to_data(image, output_type=Output.DICT)

    grouped: Dict[Tuple[int, int, int], Dict] = {}
    for i in range(len(data['text'])):
        text = data['text'][i].strip()
        if not text:
            continue
        key = (data['block_num'][i], data['par_num'][i], data['line_num'][i])
        bucket = grouped.setdefault(key, {'words': [], 'top': data['top'][i], 'lefts': []})
        bucket['words'].append(text)
        bucket['lefts'].append(data['left'][i])

    ordered = sorted(grouped.values(), key=lambda b: b['top'])
    lines: List[Dict] = []
    prev_top: Optional[int] = None
    for bucket in ordered:
        text = re.sub(r'\s+', ' ', ' '.join(bucket['words'])).strip()
        if not text:
            continue
        gap = None if prev_top is None else bucket['top'] - prev_top
        lines.append({'text': text, 'gap': gap, 'left': min(bucket['lefts'])})
        prev_top = bucket['top']
    return lines


# Section headings and numbered-paragraph first lines both start at this
# left offset (or less) in the notices sampled; bullets and wrapped
# continuation lines always start further right. Used to tell a genuine
# heading apart from a wrapped, redaction-truncated paragraph line that
# also happens to lack trailing punctuation.
_OCR_HEADING_LEFT_MAX = 320


def _classify_ocr_line(line: Dict, in_box: bool) -> Tuple[str, Optional[str]]:
    text = line['text']
    norm = text.lower().rstrip(':')
    if _MATTERS_HEADING_NORM in norm:
        return 'matters_heading', None
    if _NUMBERED_PARA_RE.match(text):
        return 'numbered_para', None

    m = _OCR_BULLET_PREFIX_RE.match(text)
    if m:
        return 'bullet', m.group(1).strip()

    gap = line.get('gap')
    left = line.get('left')
    is_new_block = gap is None or gap > _OCR_NEW_BLOCK_GAP
    looks_like_heading = (
        is_new_block
        and left is not None and left <= _OCR_HEADING_LEFT_MAX
        and len(text) <= 100
        and not text.rstrip().endswith(('.', ':', ';', ','))
    )

    if looks_like_heading:
        return 'heading', None
    if in_box and is_new_block:
        return 'bullet', text
    return 'continuation', None


def _feed_ocr_lines(builder: _MattersBoxBuilder, lines: List[Dict]):
    for line in lines:
        text = line['text']
        if _PAGE_HEADER_RE.match(text) or _DECISION_FOOTER_RE.match(text) or _PAGE_NUMBER_RE.match(text):
            continue
        if _OCR_FOOTNOTE_RE.match(text) and not _NUMBERED_PARA_RE.match(text):
            break  # footnotes trail the page; stop rather than misfeed them
        ctype, item_text = _classify_ocr_line(line, builder.in_box)
        builder.feed(ctype, text, item_text)


def parse_phase2_notice_pdf(pdf_path: str) -> Dict[str, object]:
    """Parse a Phase 2 Notice PDF and return its "matters to investigate" boxes.

    Returns ``{'matters_to_investigate': [{'heading': str | None, 'items':
    [str, ...]}, ...]}``. Pages with no text layer (see module docstring) are
    OCR'd as a best-effort fallback; if that still yields nothing the list is
    simply shorter, not an error.
    """
    with pdfplumber.open(pdf_path) as pdf:
        if not pdf.pages:
            raise ValueError(f"PDF has no pages: {pdf_path}")

        builder = _MattersBoxBuilder()
        for page_idx, page in enumerate(pdf.pages):
            if page_idx == 0:
                continue  # cover page
            if _page_needs_ocr(page):
                try:
                    _feed_ocr_lines(builder, _ocr_page_lines(page))
                except Exception as e:
                    # e.g. Tesseract isn't installed. Skip just this page
                    # rather than losing boxes already collected from
                    # earlier, normal-text pages.
                    print(f"Warning: OCR failed for page {page_idx} of {pdf_path}: {e}", file=sys.stderr)
            else:
                _feed_vector_lines(builder, _collect_page_lines(page))

    return {'matters_to_investigate': builder.finish()}
