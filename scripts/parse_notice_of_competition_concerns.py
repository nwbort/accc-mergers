#!/usr/bin/env python3
"""
Parse Notice of Competition Concerns (NOCC) summary PDFs to extract
the section-by-section content and the date the NOCC was issued.

NOCC summary PDFs are structured prose documents (not table-based like
determinations). They have a distinctive typography:

- 30pt+: cover page / TOC heading
- 18pt:  top-level section headings (e.g. "1. Introduction")
- 14pt:  sub-headings within a section (e.g. "The Acquisition")
- 11pt:  body text
- 9pt:   repeated page header / footer
- 7-8pt: footnote text and superscript markers

We exploit these consistent sizes to strip page headers, footnotes and
the cover/TOC pages, leaving clean body text that is split into sections
on the top-level numbered headings.
"""

import pdfplumber
import re
from typing import Optional, Dict, List
from pathlib import Path


BODY_MIN_FONT_SIZE = 10  # anything below this is header/footer/footnote
COVER_OR_TOC_FONT_SIZE = 24  # cover and TOC pages have text >= this size


def _extract_body_text(pdf_path: str) -> str:
    """Extract clean body text from an NOCC PDF.

    Skips cover and table-of-contents pages (detected by very large font
    sizes used only on those pages), and strips per-page headers,
    footnotes and page numbers (detected by small font sizes).
    """
    page_texts: List[str] = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            # Skip the cover page and any table-of-contents page, both of
            # which contain text noticeably larger than body headings.
            if any(
                c.get('size', 0) >= COVER_OR_TOC_FONT_SIZE for c in page.chars
            ):
                continue

            def keep(obj):
                if obj['object_type'] == 'char':
                    return obj.get('size', 0) >= BODY_MIN_FONT_SIZE
                return True

            text = page.filter(keep).extract_text()
            if text:
                page_texts.append(text)

    return '\n'.join(page_texts)


def split_sections(text: str) -> List[Dict[str, str]]:
    """Split NOCC body text into top-level sections.

    Each section starts with a line like "1. Introduction" — a leading
    integer, a period, whitespace, then a title starting with a capital
    letter. Body paragraphs are numbered "N.N." (no space after the
    first dot) so they do not match.
    """
    heading_re = re.compile(
        r'^(\d+)\.\s+([A-Z][^\n]*?)\s*$',
        re.MULTILINE,
    )
    matches = list(heading_re.finditer(text))

    # Require sequential numbering starting from 1 to avoid treating a
    # stray numbered line in the body as a section heading.
    sections: List[Dict[str, str]] = []
    expected = 1
    for i, m in enumerate(matches):
        number = int(m.group(1))
        if number != expected:
            continue
        expected = number + 1

        title = m.group(2).strip()
        start = m.end()
        # The next valid section heading (if any) bounds this section.
        end = len(text)
        for later in matches[i + 1:]:
            if int(later.group(1)) == expected:
                end = later.start()
                break

        body = text[start:end].strip()
        if body:
            sections.append({
                'item': f"{number}. {title}",
                'details': body,
            })

    return sections


def extract_issue_date(text: str) -> Optional[str]:
    """Extract the NOCC issue date from the Introduction section.

    Looks for a sentence of the form:
        "On <day> <month> <year>, the ACCC issued a Notice of
        Competition Concerns"
    and returns the "<day> <month> <year>" portion.
    """
    pattern = re.compile(
        r'On\s+(\d{1,2}\s+[A-Z][a-z]+\s+\d{4}),?\s+the ACCC issued a Notice of Competition Concerns',
        re.IGNORECASE,
    )
    m = pattern.search(text)
    if m:
        return m.group(1).strip()
    return None


def parse_notice_of_competition_concerns_pdf(pdf_path: str) -> Dict[str, any]:
    """Parse an NOCC summary PDF.

    Returns a dict with:
    - sections: list of {item, details} for each top-level section
    - issue_date: the NOCC issue date as it appears in the text, or None
    """
    result = {
        'sections': [],
        'issue_date': None,
    }

    if not Path(pdf_path).exists():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    body_text = _extract_body_text(pdf_path)
    result['sections'] = split_sections(body_text)
    result['issue_date'] = extract_issue_date(body_text)

    return result


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python parse_notice_of_competition_concerns.py <path_to_pdf>")
        sys.exit(1)

    pdf_path = sys.argv[1]

    try:
        result = parse_notice_of_competition_concerns_pdf(pdf_path)

        print("=" * 80)
        print("ISSUE DATE:")
        print("=" * 80)
        print(result['issue_date'] or "Not found")
        print()

        print("=" * 80)
        print("SECTIONS:")
        print("=" * 80)
        for section in result['sections']:
            print(f"\n{section['item']}")
            print("-" * 40)
            print(section['details'])

        print("\n" + "=" * 80)
        print(f"Extracted {len(result['sections'])} sections")

    except Exception as e:
        print(f"Error parsing PDF: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
