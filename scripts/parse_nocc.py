#!/usr/bin/env python3
"""
Parse Notice of Competition Concerns (NOCC) summary PDFs to extract structured
section content and key dates.

NOCC summaries are published on the ACCC's public merger register with titles
like "Summary of Notice of Competition Concerns". They follow a consistent
outline:

    1. Introduction
    2. Background
    3. Relevant areas of competition (or "Overlap and relevant areas of competition")
    4. Summary of preliminary competition assessment
    5. Next steps

Paragraphs inside each section are numbered like "1.1.", "2.3.", etc., and each
section may contain unnumbered sub-headings.
"""

import re
import json
from typing import Optional, Dict, List
from pathlib import Path

import pdfplumber


# Top-level section heading: a line that starts with "<n>. " followed by words.
# We reject "<n>.<n>." style paragraph numbers via a negative lookahead.
TOP_LEVEL_HEADING_RE = re.compile(
    r'^(?P<number>\d+)\.\s+(?P<title>[A-Z][^\n]{1,100})$'
)

# Paragraph number like "1.1.", "2.11.", possibly followed by a space.
PARAGRAPH_NUMBER_RE = re.compile(r'^\d+\.\d+\.?(\s|$)')

# Page footer: a line that is just a page number.
PAGE_FOOTER_RE = re.compile(r'^\d{1,3}$')


def _strip_running_headers(text: str) -> str:
    """Remove repeating running headers that pdfplumber often pulls into the text.

    NOCC PDFs typically have a running header like
        "Notice of Competition Concerns – Summary | <name> (<id>)"
    repeated on every page. These headers are not useful for our extraction and
    confuse section detection when they start with capital letters.
    """
    lines = text.split('\n')
    # Count frequency of each line; anything appearing 3+ times and starting
    # with "Notice of Competition Concerns" is treated as a running header.
    from collections import Counter
    counts = Counter(l.strip() for l in lines if l.strip())

    def is_running_header(line: str) -> bool:
        stripped = line.strip()
        if not stripped:
            return False
        if counts[stripped] >= 3 and stripped.lower().startswith('notice of competition concerns'):
            return True
        return False

    return '\n'.join(l for l in lines if not is_running_header(l))


def _clean_content(lines: List[str]) -> str:
    """Join section content lines into a single cleaned string.

    - Drops lines that are just a page number (page footers).
    - Collapses consecutive blank lines.
    - Strips trailing whitespace on each line.
    """
    cleaned = []
    prev_blank = False
    for line in lines:
        stripped = line.rstrip()
        if not stripped.strip():
            if not prev_blank and cleaned:
                cleaned.append('')
            prev_blank = True
            continue
        if PAGE_FOOTER_RE.match(stripped.strip()):
            # Drop bare page numbers.
            continue
        cleaned.append(stripped)
        prev_blank = False
    # Trim trailing blank line
    while cleaned and not cleaned[-1].strip():
        cleaned.pop()
    return '\n'.join(cleaned)


def extract_sections(text: str) -> List[Dict[str, str]]:
    """Split NOCC text into top-level numbered sections.

    Returns a list of dicts with keys:
        number:  The section number as a string, e.g. "1"
        title:   The section title, e.g. "Introduction"
        content: The body text of the section (may be empty)
    """
    if not text:
        return []

    cleaned = _strip_running_headers(text)

    sections: List[Dict[str, str]] = []
    current: Optional[Dict[str, object]] = None
    expected_next = 1

    for raw_line in cleaned.split('\n'):
        line = raw_line.rstrip()
        match = TOP_LEVEL_HEADING_RE.match(line.strip())
        # Guard against paragraph numbers matching (e.g. "1.1. On 5 March...").
        is_paragraph_number = PARAGRAPH_NUMBER_RE.match(line.strip()) is not None

        if match and not is_paragraph_number:
            number = int(match.group('number'))
            title = match.group('title').strip()
            # Only accept sections in increasing order starting from 1, so we
            # don't get fooled by numbered list items that happen to look like
            # section headings.
            if number == expected_next:
                if current is not None:
                    current['content'] = _clean_content(current['content'])  # type: ignore[arg-type]
                    sections.append(current)  # type: ignore[arg-type]
                current = {'number': str(number), 'title': title, 'content': []}
                expected_next = number + 1
                continue

        if current is not None:
            current['content'].append(line)  # type: ignore[union-attr]

    if current is not None:
        current['content'] = _clean_content(current['content'])  # type: ignore[arg-type]
        sections.append(current)  # type: ignore[arg-type]

    return sections


def _find_date(text: str, patterns: List[str]) -> Optional[str]:
    """Return the first matched date string from any of the given regex patterns."""
    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if m:
            # Collapse whitespace in the captured date.
            return re.sub(r'\s+', ' ', m.group(1)).strip()
    return None


def extract_key_dates(text: str) -> Dict[str, Optional[str]]:
    """Extract key dates mentioned in the NOCC.

    Returns a dict with keys:
        nocc_issued_date:        When the ACCC issued the NOCC
        response_due_date:       When the notifying party must respond to the NOCC
        determination_due_date:  Statutory deadline for the determination
    """
    date_token = r'(\d{1,2}\s+[A-Z][a-z]+\s+\d{4})'

    return {
        'nocc_issued_date': _find_date(
            text,
            [
                rf'On\s+{date_token}[^.]*ACCC issued a Notice of Competition Concerns',
                rf'ACCC issued a Notice of Competition Concerns[^.]*on\s+{date_token}',
            ],
        ),
        'response_due_date': _find_date(
            text,
            [
                rf'opportunity to respond[^.]*?by\s+{date_token}',
                rf'respond[^.]*?preliminary issues[^.]*?by\s+{date_token}',
            ],
        ),
        'determination_due_date': _find_date(
            text,
            [
                rf'ACCC must issue a determination[^.]*?by\s+{date_token}',
                rf'determination[^.]*?Acquisition by\s+{date_token}',
            ],
        ),
    }


def parse_nocc_pdf(pdf_path: str) -> Dict[str, object]:
    """Parse a NOCC summary PDF.

    Args:
        pdf_path: Path to the NOCC PDF file.

    Returns:
        Dictionary with:
            sections:    List of {number, title, content} dicts
            key_dates:   Dict of nocc_issued_date, response_due_date,
                         determination_due_date (any may be None)
            sections_json: JSON string of sections (for storage)
    """
    if not Path(pdf_path).exists():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    full_text_parts: List[str] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text() or ''
            full_text_parts.append(page_text)
    full_text = '\n'.join(full_text_parts)

    sections = extract_sections(full_text)
    key_dates = extract_key_dates(full_text)

    result: Dict[str, object] = {
        'sections': sections,
        'key_dates': key_dates,
        'sections_json': None,
    }
    if sections:
        result['sections_json'] = json.dumps(sections, indent=2)
    return result


if __name__ == '__main__':
    import sys

    if len(sys.argv) < 2:
        print("Usage: python parse_nocc.py <path_to_pdf>")
        sys.exit(1)

    pdf_path = sys.argv[1]
    try:
        result = parse_nocc_pdf(pdf_path)

        print("=" * 80)
        print("KEY DATES:")
        print("=" * 80)
        for k, v in result['key_dates'].items():  # type: ignore[union-attr]
            print(f"  {k}: {v or '(not found)'}")
        print()

        print("=" * 80)
        print("SECTIONS:")
        print("=" * 80)
        for section in result['sections']:  # type: ignore[union-attr]
            print(f"\n{section['number']}. {section['title']}")
            print('-' * 40)
            content = section['content']
            # Print just first 400 chars for preview.
            preview = content[:400] + ('…' if len(content) > 400 else '')
            print(preview)

        print()
        print(f"Extracted {len(result['sections'])} sections")  # type: ignore[arg-type]
    except Exception as e:  # pragma: no cover - CLI convenience
        print(f"Error parsing PDF: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
