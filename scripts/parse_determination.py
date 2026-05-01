#!/usr/bin/env python3
"""
Parse determination PDFs to extract commission division information and table content.
"""

import pdfplumber
import re
import json
from typing import Optional, Dict, List, Tuple
from pathlib import Path


def extract_commission_division(text: str) -> Optional[str]:
    """
    Extract the commission division information from the last sentence of the determination.

    Examples:
    - "Determination made by a division of the Commission constituted by a direction issued pursuant to section 19 of the Act"
    - "Determination made by Commissioner Williams pursuant to a delegation under section 25(1) of the Act"

    Args:
        text: Full text of the determination PDF

    Returns:
        The commission division sentence, or None if not found
    """
    # Look for sentences that start with "Determination made by"
    # This should typically be at the end of the document
    # The sentence may span multiple lines, so use DOTALL and look for "of the Act" as the ending
    pattern = r'Determination made by.+?(?:of the Act|under section \d+\(\d+\)(?:\s+of the Act)?)'
    matches = re.findall(pattern, text, re.IGNORECASE | re.DOTALL)

    if matches:
        # Return the last match (should be at the end of the document)
        # Clean up the match by removing extra whitespace and newlines
        result = matches[-1].strip()
        # Replace multiple spaces/newlines with single space
        result = re.sub(r'\s+', ' ', result)
        # Remove trailing period if present
        if result.endswith('.'):
            result = result[:-1]
        return result.strip()

    return None


def extract_table_content(pdf_path: str) -> List[Dict[str, str]]:
    """
    Extract the 2-column table content from the determination PDF.

    The table typically has:
    - Column 1: Item name (e.g., "Notified acquisition", "Determination", "Parties to the Acquisition")
    - Column 2: Details about that item

    Args:
        pdf_path: Path to the determination PDF file

    Returns:
        List of dictionaries with 'item' and 'details' keys
    """
    table_data = []

    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, 1):
            # Extract tables from the page
            tables = page.extract_tables()

            for table in tables:
                if not table:
                    continue

                # Process each row in the table
                for row in table:
                    if not row or len(row) < 2:
                        continue

                    # Get the first two columns
                    item = row[0] if row[0] else ""
                    details = row[1] if row[1] else ""

                    # Clean up the text
                    item = item.strip()
                    details = details.strip()

                    # Skip completely empty rows
                    if not item and not details:
                        continue

                    # Check if this is a continuation of the previous row.
                    # Handles: empty item, lowercase/whitespace start, or bullet "•"
                    # (bullet markers appear when a spanning row has sub-points in the
                    # item column, e.g. the "Explanation for determination" continuation rows)
                    if table_data and (not item or item == '•' or (item and item[0].islower()) or (item and item.startswith(' '))):
                        # Append to the previous row's details
                        continuation_text = (item.strip() + ' ' + details.strip()) if item else details.strip()
                        table_data[-1]['details'] += '\n' + continuation_text
                        continue

                    # Skip rows without details (header rows)
                    if not details:
                        continue

                    table_data.append({
                        'item': item,
                        'details': details
                    })

        # If no tables were extracted, try to extract text and parse it manually
        if not table_data:
            full_text = ""
            for page in pdf.pages:
                full_text += page.extract_text() + "\n"

            table_data = parse_text_as_table(full_text)

    return table_data


def parse_text_as_table(text: str) -> List[Dict[str, str]]:
    """
    Fallback method to parse text as a table when table extraction fails.

    Looks for common patterns in determination documents where items
    are followed by their details.

    Args:
        text: Full text of the determination PDF

    Returns:
        List of dictionaries with 'item' and 'details' keys
    """
    table_data = []

    # Common item names in determination documents
    common_items = [
        "Notified acquisition",
        "Determination",
        "Parties to the Acquisition",
        "Date of determination",
        "Date of notification",
        "Nature of business activities",
        "Market definition",
        "Statement of issues",
        "Conditions",
        "Public benefits",
        "Statutory time period"
    ]

    lines = text.split('\n')
    current_item = None
    current_details = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Check if this line is a known item
        is_item = False
        for item in common_items:
            if line.startswith(item):
                # If we have a current item, save it
                if current_item:
                    table_data.append({
                        'item': current_item,
                        'details': ' '.join(current_details).strip()
                    })

                # Start a new item
                current_item = item
                # The rest of the line after the item name is the start of details
                current_details = [line[len(item):].strip()]
                is_item = True
                break

        # If not an item, add to current details
        if not is_item and current_item:
            current_details.append(line)

    # Don't forget the last item
    if current_item:
        table_data.append({
            'item': current_item,
            'details': ' '.join(current_details).strip()
        })

    return table_data


def _group_chars_into_lines(page) -> List[Dict]:
    """Group characters on a page into lines with dominant font info.

    Returns a list of dicts with keys 'text', 'size', 'bold', 'italic'.
    """
    lines: Dict[float, Dict] = {}
    for c in page.chars:
        # Round y0 to nearest 0.5pt to keep characters on the same baseline together.
        y = round(c.get('y0', 0) * 2) / 2
        bucket = lines.setdefault(y, {'fonts': [], 'parts': []})
        bucket['fonts'].append((c.get('size', 0), c.get('fontname', '')))
        bucket['parts'].append((c.get('x0', 0), c.get('text', '')))

    out: List[Dict] = []
    # Iterate top-to-bottom (largest y first).
    for y in sorted(lines.keys(), reverse=True):
        bucket = lines[y]
        # Reconstruct the line text in left-to-right order.
        bucket['parts'].sort(key=lambda p: p[0])
        text = ''.join(p[1] for p in bucket['parts']).strip()
        if not text:
            continue
        # Pick the most common (size, font) pair on this line.
        from collections import Counter
        font_counter = Counter(bucket['fonts'])
        (size, fontname), _ = font_counter.most_common(1)[0]
        font_short = fontname.split('+')[-1] if '+' in fontname else fontname
        out.append({
            'y': y,
            'text': text,
            'size': round(size, 2),
            'bold': 'Bold' in font_short,
            'italic': 'Italic' in font_short,
        })
    return out


PAGE_HEADER_RE = re.compile(r'^Determination \| .+? \(MN-\d+\)\s*$')
PAGE_HEADER_STRIP_RE = re.compile(r'^Determination \| [^\n]*?\(MN-\d+\)\s*\n', re.MULTILINE)
PAGE_FOOTER_NUM_RE = re.compile(r'^\d+\s*$')


def _is_heading_line(line: Dict) -> bool:
    """Return True if a line's font characteristics suggest a section heading."""
    text = line['text']
    size = line['size']
    if PAGE_HEADER_RE.match(text):
        return False
    # Top-level heading: noticeably larger font.
    if size >= 12.5:
        return True
    # Looks like body content — not a heading regardless of styling.
    if re.match(r'^\d+\.\d+\.?\s', text):
        return False
    if re.match(r'^[•▪]\s', text):
        return False
    if re.match(r'^\([a-z]\)\s', text):
        return False
    # Subheading: bold, body-sized, short.
    if line['bold'] and 10 <= size < 12.5 and len(text) <= 120:
        return True
    # Italic subheading: short, no terminal punctuation. The detailed
    # determinations sometimes use an italic line as a sub-sub-heading
    # (e.g. "Asset management software"). We're conservative so as not to
    # swallow inline-italic body lines: require short text and no period.
    if (
        line['italic']
        and not line['bold']
        and 10 <= size < 12.5
        and len(text) <= 60
        and not text.endswith('.')
        and not text.endswith(',')
    ):
        return True
    return False


def _collect_heading_info(pdf) -> Dict[str, Dict]:
    """Identify heading text by font characteristics across all pages.

    Returns a mapping of heading text → {size, bold, italic} so callers can
    distinguish heading levels (and avoid merging headings of different
    sizes when one wraps onto the next line).
    """
    headings: Dict[str, Dict] = {}
    for page in pdf.pages:
        for line in _group_chars_into_lines(page):
            if _is_heading_line(line):
                headings[line['text']] = {
                    'size': line['size'],
                    'bold': line['bold'],
                    'italic': line['italic'],
                }
    return headings


def _full_text_without_page_chrome(pdf) -> str:
    """Extract page text concatenated with page header and footer removed."""
    parts = []
    for page in pdf.pages:
        text = page.extract_text() or ''
        # Drop the running page header.
        text = PAGE_HEADER_STRIP_RE.sub('', text)
        # Drop a trailing page-number line, if any.
        lines = text.splitlines()
        while lines and PAGE_FOOTER_NUM_RE.match(lines[-1].strip()):
            lines.pop()
        parts.append('\n'.join(lines))
    return '\n'.join(parts)


def _parse_section_blocks(text: str, heading_info: Dict[str, Dict]) -> List[Dict]:
    """Convert section text into structured blocks (headings, paragraphs, lists).

    Each block has a 'type':
      - 'heading' with 'text'
      - 'paragraph' with 'text' and optional 'number' (e.g. "2.4")
      - 'bullet_list' with 'items' (list of strings)
      - 'lettered_list' with 'items' (list of {'letter', 'text'})
    """
    blocks: List[Dict] = []
    current: Optional[Dict] = None

    def flush():
        nonlocal current
        if current is not None:
            blocks.append(current)
            current = None

    for raw_line in text.split('\n'):
        line = raw_line.strip()
        if not line:
            continue

        # Skip stray page-header fragments that may slip through (e.g. when
        # extract_text emitted them on a page we didn't strip).
        if PAGE_HEADER_RE.match(line):
            continue

        # Headings (detected via font in the source PDF). Two consecutive
        # heading lines that share font size are merged so a single heading
        # that wraps across two PDF lines renders as one block, but a
        # top-level heading immediately followed by a sub-heading stays
        # separate.
        if line in heading_info:
            info = heading_info[line]
            flush()
            prev = blocks[-1] if blocks else None
            if (
                prev
                and prev['type'] == 'heading'
                and prev.get('_size') == info['size']
                and prev.get('_bold') == info['bold']
                and prev.get('_italic') == info['italic']
            ):
                prev['text'] = (prev['text'] + ' ' + line).strip()
            else:
                blocks.append({
                    'type': 'heading',
                    'text': line,
                    '_size': info['size'],
                    '_bold': info['bold'],
                    '_italic': info['italic'],
                })
            continue

        # Numbered paragraph: "2.4. text" or "2.4 text" (sometimes the period
        # is absorbed into the next character with no space).
        para_match = re.match(r'^(\d+)\.(\d+)\.?\s*(.*)$', line)
        if para_match and para_match.group(3):
            flush()
            current = {
                'type': 'paragraph',
                'number': f"{para_match.group(1)}.{para_match.group(2)}",
                'text': para_match.group(3).strip(),
            }
            continue

        # Bullet item.
        bullet_match = re.match(r'^[•▪]\s*(.*)$', line)
        if bullet_match:
            if current is None or current.get('type') != 'bullet_list':
                flush()
                current = {'type': 'bullet_list', 'items': []}
            current['items'].append(bullet_match.group(1).strip())
            continue

        # Lettered list with parenthesised marker: "(a) text".
        letter_match = re.match(r'^\(([a-z])\)\s*(.*)$', line)
        if letter_match:
            if current is None or current.get('type') != 'lettered_list':
                flush()
                current = {'type': 'lettered_list', 'items': []}
            current['items'].append({
                'letter': letter_match.group(1),
                'text': letter_match.group(2).strip(),
            })
            continue

        # Lettered list with period marker: "a. text". Match if we're already
        # in a lettered list, or if this looks like the start of one (the
        # previous paragraph ended with a colon, and the marker is "a.").
        period_letter = re.match(r'^([a-z])\.\s+(.*)$', line)
        if period_letter:
            letter = period_letter.group(1)
            item_text = period_letter.group(2).strip()
            if current and current.get('type') == 'lettered_list':
                current['items'].append({'letter': letter, 'text': item_text})
                continue
            if (
                letter == 'a'
                and current
                and current.get('type') == 'paragraph'
                and current.get('text', '').rstrip().endswith(':')
            ):
                flush()
                current = {
                    'type': 'lettered_list',
                    'items': [{'letter': letter, 'text': item_text}],
                }
                continue

        # Continuation of the previous block.
        if current is None:
            current = {'type': 'paragraph', 'text': line}
        elif current['type'] == 'paragraph':
            current['text'] = (current['text'] + ' ' + line).strip()
        elif current['type'] == 'bullet_list':
            if current['items']:
                current['items'][-1] = (current['items'][-1] + ' ' + line).strip()
            else:
                current['items'].append(line)
        elif current['type'] == 'lettered_list':
            if current['items']:
                current['items'][-1]['text'] = (current['items'][-1]['text'] + ' ' + line).strip()

    flush()
    # Strip private font-tracking fields from heading blocks before returning.
    for block in blocks:
        if block['type'] == 'heading':
            block.pop('_size', None)
            block.pop('_bold', None)
            block.pop('_italic', None)
    return blocks


def extract_statement_of_reasons(pdf_path: str) -> Optional[List[Dict]]:
    """Extract the structured "Statement of reasons" content from a Phase 1
    determination PDF.

    The detailed Phase 1 determinations include a section "2. Statement of
    reasons" with the ACCC's substantive reasoning. Simpler determinations
    contain all reasoning inline within the determination table and have no
    section 2 — those return ``None``.
    """
    if not Path(pdf_path).exists():
        return None

    with pdfplumber.open(pdf_path) as pdf:
        heading_info = _collect_heading_info(pdf)
        full_text = _full_text_without_page_chrome(pdf)

    # Locate the body of section 2. The header line itself is not always on a
    # line of its own when extract_text concatenates it with the next line.
    section_match = re.search(
        r'(?:^|\n)\s*2\.\s*Statement of reasons\s*\n(.+?)'
        r'(?=\n\s*3\.\s+Applications for review|'
        r'\n\s*Determination made by\b)',
        full_text,
        re.DOTALL,
    )
    if not section_match:
        return None

    body = section_match.group(1).strip()
    if not body:
        return None

    blocks = _parse_section_blocks(body, heading_info)
    return blocks or None


def parse_determination_pdf(pdf_path: str) -> Dict[str, any]:
    """
    Parse a determination PDF to extract all relevant information.

    Args:
        pdf_path: Path to the determination PDF file

    Returns:
        Dictionary containing:
        - commission_division: The commission division sentence
        - table_content: List of item/details dictionaries
        - table_content_json: JSON string of the table content
        - statement_of_reasons: List of structured blocks for Phase 1 detailed
          reasons (section 2), or ``None`` for waivers and simple Phase 1
          determinations whose reasons are inline in the table.
    """
    result = {
        'commission_division': None,
        'table_content': [],
        'table_content_json': None,
        'statement_of_reasons': None,
    }

    # Check if file exists
    if not Path(pdf_path).exists():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    # Extract full text for commission division
    full_text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            full_text += page.extract_text() + "\n"

    # Extract commission division (from last sentence)
    result['commission_division'] = extract_commission_division(full_text)

    # Extract table content
    result['table_content'] = extract_table_content(pdf_path)

    # Convert table content to JSON for storage
    if result['table_content']:
        result['table_content_json'] = json.dumps(result['table_content'], indent=2)

    # Extract structured "Statement of reasons" (only present in Phase 1
    # determinations that put their detailed reasons after the table).
    try:
        result['statement_of_reasons'] = extract_statement_of_reasons(pdf_path)
    except Exception as e:
        print(f"Warning: Failed to extract statement of reasons: {e}")
        result['statement_of_reasons'] = None

    return result


if __name__ == "__main__":
    # Test the parser with a sample PDF
    import sys

    if len(sys.argv) < 2:
        print("Usage: python parse_determination.py <path_to_pdf>")
        sys.exit(1)

    pdf_path = sys.argv[1]

    try:
        result = parse_determination_pdf(pdf_path)

        print("=" * 80)
        print("COMMISSION DIVISION:")
        print("=" * 80)
        print(result['commission_division'] or "Not found")
        print()

        print("=" * 80)
        print("TABLE CONTENT:")
        print("=" * 80)
        for item in result['table_content']:
            print(f"\n{item['item']}")
            print("-" * 40)
            print(item['details'])

        print("\n" + "=" * 80)
        print(f"Extracted {len(result['table_content'])} table items")

    except Exception as e:
        print(f"Error parsing PDF: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
