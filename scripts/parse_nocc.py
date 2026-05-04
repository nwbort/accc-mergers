#!/usr/bin/env python3
"""
Parse Notice of Competition Concerns (NOCC) summary PDFs to extract structured
content.

NOCC summaries are published during Phase 2 review (around business day 25 of
Phase 2). The published version is a ~10-15 page document with a cover page,
optional table of contents, and numbered top-level sections (e.g.
"1. Introduction", "2. Background", ...) each containing numbered paragraphs
("1.1.", "1.2.", ...), bold sub-headings, bullet lists and lettered lists.

The structure mirrors Phase 1 detailed-determination "Statement of reasons"
content, so we reuse the line/heading helpers from ``parse_determination``.
The shape of the output, however, is NOCC-specific: a list of top-level
sections, each with its own ordered block stream.
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Optional

import pdfplumber

from parse_determination import _group_chars_into_lines
from date_utils import parse_text_to_iso

# Lines with font size below this threshold (footnote anchors/bodies, page
# numbers and the running page header) are discarded before parsing.
_BODY_MIN_FONT_SIZE = 10.0

# Top-level numbered headings (e.g. "1. Introduction") render at this size in
# the published NOCCs we have seen; sub-section headings ("The Acquisition")
# render around 14pt. The threshold sits between the two.
_TOP_LEVEL_HEADING_MIN_SIZE = 15.0
_SUB_HEADING_MIN_SIZE = 12.5

_TOC_DOT_LEADER_RE = re.compile(r'\.{4,}')
_TOP_LEVEL_HEADING_RE = re.compile(r'^(\d+)\.\s*(.+?)\s*$')


def _is_top_level_heading(line: Dict) -> bool:
    return (
        line['size'] >= _TOP_LEVEL_HEADING_MIN_SIZE
        and bool(_TOP_LEVEL_HEADING_RE.match(line['text']))
    )


def _is_sub_heading(line: Dict) -> bool:
    text = line['text']
    size = line['size']
    if _is_top_level_heading(line):
        return False
    # Numbered paragraphs and list markers are body content even if they pick
    # up bold styling.
    if re.match(r'^\d+\.\d+', text):
        return False
    if re.match(r'^[•▪]\s', text):
        return False
    if re.match(r'^\([a-z]\)\s', text):
        return False
    # Any line noticeably larger than body text (≈11pt) is a heading. This
    # covers regular-weight 14pt sub-sub-headings such as "Grocery retailing
    # in Australia" that the published NOCCs render unbolded.
    if size >= 13.5 and len(text) <= 200:
        return True
    # Body-sized but bold or italic: standard sub-heading style. Limit length
    # so we don't promote a stray bold inline phrase to a heading.
    if line['bold'] and _SUB_HEADING_MIN_SIZE <= size < 13.5 and len(text) <= 120:
        return True
    if (
        line['italic']
        and not line['bold']
        and 10 <= size < 13.5
        and len(text) <= 60
        and not text.endswith('.')
        and not text.endswith(',')
    ):
        return True
    return False


def _extract_cover_metadata(page) -> Dict[str, Optional[str]]:
    """Pull title, matter id and publication date from the cover page.

    The cover layout is consistent across the NOCCs we have:
        <Title>                                   18pt bold
        <MN-XXXXX>                                14pt
        Notice of                                 ~40pt bold
        Competition Concerns –                    ~40pt bold
        Summary                                   ~40pt bold
        <DD Month YYYY>                           14pt
    """
    title: Optional[str] = None
    matter_id: Optional[str] = None
    date_text: Optional[str] = None
    document_type: Optional[str] = None

    big_title_parts: List[str] = []

    for line in _group_chars_into_lines(page):
        text = line['text'].strip()
        if not text:
            continue
        size = line['size']

        m = re.match(r'^(MN-\d+)$', text)
        if m and matter_id is None:
            matter_id = m.group(1)
            continue

        if size >= 30:
            big_title_parts.append(text)
            continue

        # Title is the largest line that isn't the giant document-type banner;
        # take the first such line we see.
        if title is None and 16 <= size < 30:
            title = text
            continue

        if 12 <= size < 16 and re.match(
            r'^\d{1,2}\s+[A-Za-z]+\s+\d{4}$', text
        ):
            date_text = text
            continue

    if big_title_parts:
        joined = ' '.join(big_title_parts)
        # Normalise the dash and trailing whitespace; collapse to a canonical
        # short form for downstream callers.
        joined = re.sub(r'\s+', ' ', joined).strip()
        document_type = joined

    return {
        'title': title,
        'matter_id': matter_id,
        'date': date_text,
        'document_type': document_type,
    }


def _collect_body_lines(pdf) -> List[Dict]:
    """Return formatted lines from the body pages, skipping page chrome.

    Filters applied:
      - Font size below ``_BODY_MIN_FONT_SIZE`` (page header, page number,
        footnote anchor superscripts, footnote bodies).
      - Lines that consist solely of a TOC dot leader plus page number.
      - The TOC page itself, identified by a ``Contents`` heading.
    """
    lines: List[Dict] = []
    for page_idx, page in enumerate(pdf.pages):
        if page_idx == 0:
            # Cover page — handled separately for metadata.
            continue

        page_lines = _group_chars_into_lines(page)
        # Detect TOC page: starts with a large "Contents" heading.
        if any(
            line['text'].strip().lower() == 'contents' and line['size'] >= 18
            for line in page_lines
        ):
            continue

        for line in page_lines:
            if line['size'] < _BODY_MIN_FONT_SIZE:
                continue
            text = line['text']
            # Skip stray TOC entries if they ever survive past the page filter
            # (defensive — leading digit + dot-leader + trailing page number).
            if _TOC_DOT_LEADER_RE.search(text):
                continue
            lines.append(line)

    return lines


def _parse_blocks(lines: List[Dict]) -> List[Dict]:
    """Turn formatted lines into a flat block stream.

    Block types:
      - ``heading``  with ``text`` and ``level`` (1 = top-level numbered
        section, 2 = sub-heading)
      - ``paragraph`` with ``text`` and optional ``number`` (e.g. "2.4")
      - ``bullet_list`` with ``items`` (list of strings)
      - ``lettered_list`` with ``items`` (list of {'letter', 'text'})
    """
    blocks: List[Dict] = []
    current: Optional[Dict] = None

    def flush():
        nonlocal current
        if current is not None:
            blocks.append(current)
            current = None

    def append_continuation(text: str) -> None:
        nonlocal current
        if current is None:
            current = {'type': 'paragraph', 'text': text}
            return
        if current['type'] == 'paragraph':
            current['text'] = (current['text'] + ' ' + text).strip()
        elif current['type'] == 'bullet_list':
            if current['items']:
                current['items'][-1] = (current['items'][-1] + ' ' + text).strip()
            else:
                current['items'].append(text)
        elif current['type'] == 'lettered_list':
            if current['items']:
                current['items'][-1]['text'] = (
                    current['items'][-1]['text'] + ' ' + text
                ).strip()

    for line in lines:
        text = line['text'].strip()
        if not text:
            continue

        if _is_top_level_heading(line):
            flush()
            blocks.append({'type': 'heading', 'level': 1, 'text': text})
            continue

        if _is_sub_heading(line):
            flush()
            # Merge with the previous sub-heading only if it shares the same
            # visual style — handles a single sub-heading wrapping across two
            # PDF lines, while keeping a sub-heading and a sub-sub-heading
            # (different bold/italic) distinct.
            prev = blocks[-1] if blocks else None
            if (
                prev
                and prev['type'] == 'heading'
                and prev.get('level') == 2
                and prev.get('_bold') == line['bold']
                and prev.get('_italic') == line['italic']
            ):
                prev['text'] = (prev['text'] + ' ' + text).strip()
            else:
                blocks.append({
                    'type': 'heading',
                    'level': 2,
                    'text': text,
                    '_bold': line['bold'],
                    '_italic': line['italic'],
                })
            continue

        # Numbered paragraph: "2.4. text" or "2.4text" (no space) or "2.4 text".
        para_match = re.match(r'^(\d+)\.(\d+)\.?\s*(.+)$', text)
        if para_match:
            flush()
            current = {
                'type': 'paragraph',
                'number': f"{para_match.group(1)}.{para_match.group(2)}",
                'text': para_match.group(3).strip(),
            }
            continue

        # Bullet item — accepts the standard ACCC bullet markers as well as
        # the en-dash / minus-sign characters used for nested sub-bullets.
        # A marker on a line by itself is allowed (the next line will supply
        # the item text via the continuation path).
        bullet_match = re.match(r'^([•▪−–])\s*(.*)$', text)
        if bullet_match:
            if current is None or current.get('type') != 'bullet_list':
                flush()
                current = {'type': 'bullet_list', 'items': []}
            current['items'].append(bullet_match.group(2).strip())
            continue

        # Lettered list "(a) text".
        letter_match = re.match(r'^\(([a-z])\)\s*(.+)$', text)
        if letter_match:
            if current is None or current.get('type') != 'lettered_list':
                flush()
                current = {'type': 'lettered_list', 'items': []}
            current['items'].append({
                'letter': letter_match.group(1),
                'text': letter_match.group(2).strip(),
            })
            continue

        # Continuation of the previous block.
        append_continuation(text)

    flush()
    return blocks


def _group_blocks_into_sections(blocks: List[Dict]) -> List[Dict]:
    """Group the flat block stream by top-level numbered sections."""
    sections: List[Dict] = []
    preamble: List[Dict] = []
    current: Optional[Dict] = None

    for block in blocks:
        if block['type'] == 'heading' and block.get('level') == 1:
            if current is not None:
                sections.append(current)
            m = _TOP_LEVEL_HEADING_RE.match(block['text'])
            number = m.group(1) if m else None
            heading_text = m.group(2).strip() if m else block['text']
            current = {
                'number': number,
                'title': heading_text,
                'blocks': [],
            }
            continue

        if current is None:
            preamble.append(block)
        else:
            # Strip the synthetic heading-level markers from sub-headings on
            # the way out so consumers see a stable schema.
            if block['type'] == 'heading':
                block = {'type': 'heading', 'text': block['text']}
            current['blocks'].append(block)

    if current is not None:
        sections.append(current)

    if preamble:
        # Anything before the first numbered section is unusual but should not
        # be silently dropped. Keep it as a synthetic leading section.
        cleaned_preamble = []
        for block in preamble:
            if block['type'] == 'heading':
                block = {'type': 'heading', 'text': block['text']}
            cleaned_preamble.append(block)
        sections.insert(0, {
            'number': None,
            'title': None,
            'blocks': cleaned_preamble,
        })

    return sections


def parse_nocc_pdf(pdf_path: str) -> Dict[str, object]:
    """Parse a NOCC summary PDF.

    Returns a dictionary with the cover-page metadata and a structured list
    of sections.
    """
    pdf_file = Path(pdf_path)
    if not pdf_file.exists():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    with pdfplumber.open(pdf_path) as pdf:
        if not pdf.pages:
            raise ValueError(f"PDF has no pages: {pdf_path}")

        metadata = _extract_cover_metadata(pdf.pages[0])
        body_lines = _collect_body_lines(pdf)

    blocks = _parse_blocks(body_lines)
    sections = _group_blocks_into_sections(blocks)

    date_iso = parse_text_to_iso(metadata['date'], include_time=False) if metadata.get('date') else None

    return {
        'title': metadata.get('title'),
        'matter_id': metadata.get('matter_id'),
        'document_type': metadata.get('document_type'),
        'date': metadata.get('date'),
        'date_iso': date_iso,
        'sections': sections,
    }


def _is_nocc_filename(name: str) -> bool:
    lower = name.lower()
    if not lower.endswith('.pdf'):
        return False
    # Match either the full phrase or the common abbreviation.
    return 'notice of competition concerns' in lower or 'nocc' in lower


def process_all_noccs(matters_dir: str = "data/raw/matters") -> Dict[str, Dict]:
    """Process all NOCC PDFs in the matters directory.

    Mirrors the questionnaire pipeline: when a matter has multiple NOCC PDFs,
    the latest by publication date wins, with duplicates (same normalised
    filename and date) collapsed.
    """
    matters_path = Path(matters_dir)
    if not matters_path.exists():
        raise FileNotFoundError(f"Matters directory not found: {matters_dir}")

    candidates = [pdf for pdf in matters_path.glob("*/*.pdf") if _is_nocc_filename(pdf.name)]

    pdfs_by_matter: Dict[str, List[Path]] = {}
    for pdf_path in candidates:
        matter_id = pdf_path.parent.name
        pdfs_by_matter.setdefault(matter_id, []).append(pdf_path)

    def _norm(name: str) -> str:
        return re.sub(r'_\d+(\.[^.]+)$', r'\1', name)

    results: Dict[str, Dict] = {}
    for matter_id, pdf_paths in pdfs_by_matter.items():
        parsed: List[Dict] = []
        last_error: Optional[Dict] = None

        for pdf_path in sorted(pdf_paths):
            try:
                data = parse_nocc_pdf(str(pdf_path))
                data['file_path'] = str(pdf_path.relative_to(matters_path.parent))
                data['file_name'] = pdf_path.name
                parsed.append(data)
            except Exception as e:
                print(f"Error processing {pdf_path}: {e}")
                last_error = {
                    'error': str(e),
                    'file_path': str(pdf_path.relative_to(matters_path.parent)),
                }

        if not parsed:
            if last_error:
                results[matter_id] = last_error
            continue

        seen: set = set()
        unique: List[Dict] = []
        for p in parsed:
            key = (_norm(p['file_name']), p.get('date_iso') or '')
            if key not in seen:
                seen.add(key)
                unique.append(p)

        unique.sort(
            key=lambda p: p.get('date_iso') or '0000-00-00',
            reverse=True,
        )

        primary = unique[0].copy()
        if len(unique) > 1:
            primary['all_noccs'] = unique
        results[matter_id] = primary

    return results


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == '--debug-lines':
        pdf_path = sys.argv[2]
        with pdfplumber.open(pdf_path) as pdf:
            for i, page in enumerate(pdf.pages):
                print(f"--- Page {i + 1} ---")
                for line in _group_chars_into_lines(page):
                    flag = ''
                    if _is_top_level_heading(line):
                        flag = ' [H1]'
                    elif _is_sub_heading(line):
                        flag = ' [H2]'
                    print(
                        f"  size={line['size']:5.2f} bold={int(line['bold'])} "
                        f"italic={int(line['italic'])}{flag}: {line['text']!r}"
                    )
        sys.exit(0)

    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
        try:
            result = parse_nocc_pdf(pdf_path)
        except Exception as e:
            print(f"Error parsing PDF: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)

        print("=" * 80)
        print(f"Title:          {result['title']}")
        print(f"Matter ID:      {result['matter_id']}")
        print(f"Document type:  {result['document_type']}")
        print(f"Date:           {result['date']}  ({result['date_iso']})")
        print(f"Sections:       {len(result['sections'])}")
        print("=" * 80)
        for sec in result['sections']:
            heading = (
                f"{sec['number']}. {sec['title']}" if sec['number'] else sec['title'] or '<preamble>'
            )
            print(f"\n## {heading}")
            for block in sec['blocks']:
                t = block['type']
                if t == 'heading':
                    print(f"  ### {block['text']}")
                elif t == 'paragraph':
                    num = block.get('number')
                    prefix = f"{num}. " if num else ""
                    print(f"  {prefix}{block['text']}")
                elif t == 'bullet_list':
                    for item in block['items']:
                        print(f"    • {item}")
                elif t == 'lettered_list':
                    for item in block['items']:
                        print(f"    ({item['letter']}) {item['text']}")
        sys.exit(0)

    # Process every NOCC under data/raw/matters and write the JSON manifest.
    print("Processing all NOCC PDFs in matters directory...")
    print()

    try:
        results = process_all_noccs()
        for matter_id, data in sorted(results.items()):
            print("=" * 80)
            print(f"Matter: {matter_id}")
            print("=" * 80)
            if 'error' in data:
                print(f"ERROR: {data['error']}")
            else:
                print(f"File:     {data.get('file_name')}")
                print(f"Title:    {data.get('title')}")
                print(f"Date:     {data.get('date')}  ({data.get('date_iso')})")
                print(f"Sections: {len(data.get('sections', []))}")

        output_file = "data/processed/nocc_data.json"
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2, sort_keys=True)

        print()
        print("=" * 80)
        print(f"Results saved to {output_file}")
        print(f"Processed {len(results)} NOCC summaries")
    except Exception as e:
        print(f"Error processing NOCCs: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
