#!/usr/bin/env python3
"""
Improved PDF parser that handles:
1. Line wrapping vs paragraph breaks
2. Table cells spanning multiple pages
"""

import pdfplumber
import re
import json
from typing import Optional, Dict, List
from pathlib import Path


def join_wrapped_lines(text: str) -> str:
    """
    Join lines that appear to be wrapped due to page width constraints.

    This attempts to distinguish between:
    - Line breaks due to text wrapping (should be joined)
    - True paragraph breaks (should be preserved)

    Heuristics used:
    - If a line doesn't end with sentence-ending punctuation (.!?:) and the next
      line doesn't start with a bullet/number, join them
    - Preserve double newlines (paragraph breaks)
    - Preserve lines ending with colons (likely list introductions)

    Args:
        text: Text with newlines from PDF extraction

    Returns:
        Text with wrapped lines joined but paragraphs preserved
    """
    lines = text.split('\n')
    result = []
    i = 0

    while i < len(lines):
        line = lines[i].strip()

        # Skip empty lines but preserve paragraph breaks
        if not line:
            # Check if this is a paragraph break (preceded and followed by content)
            if result and i + 1 < len(lines) and lines[i + 1].strip():
                result.append('')  # Preserve the paragraph break
            i += 1
            continue

        # Check if this line should be joined with the next
        should_join = False
        if i + 1 < len(lines):
            next_line = lines[i + 1].strip()

            if next_line:
                # Don't join if current line ends with sentence/list ending
                if not line.endswith(('.', '!', '?', ':')):
                    # Don't join if next line starts with bullet or number
                    if not re.match(r'^[•\-\*\d]', next_line):
                        should_join = True
                # Special case: hyphenated word at end of line
                elif line.endswith('-') and not line.endswith('--'):
                    should_join = True

        if should_join:
            # Join with next line
            next_line = lines[i + 1].strip()
            if line.endswith('-') and not line.endswith('--'):
                # Remove hyphen for hyphenated words
                line = line[:-1] + next_line
            else:
                line = line + ' ' + next_line
            i += 2
        else:
            result.append(line)
            i += 1

    return '\n'.join(result)


def extract_commission_division(text: str) -> Optional[str]:
    """
    Extract the commission division information from the last sentence of the determination.
    """
    pattern = r'Determination made by.+?(?:of the Act|under section \d+\(\d+\)(?:\s+of the Act)?)'
    matches = re.findall(pattern, text, re.IGNORECASE | re.DOTALL)

    if matches:
        result = matches[-1].strip()
        result = re.sub(r'\s+', ' ', result)
        if result.endswith('.'):
            result = result[:-1]
        return result.strip()

    return None


def merge_multipage_table_data(all_page_tables: List[List[List[Dict[str, str]]]]) -> List[Dict[str, str]]:
    """
    Merge table data from multiple pages, handling cells that span pages.

    Args:
        all_page_tables: List of [page_num, tables] where tables is list of extracted tables

    Returns:
        Merged list of table items
    """
    table_data = []

    for page_num, tables in all_page_tables:
        for table in tables:
            if not table:
                continue

            for row in table:
                if not row or len(row) < 2:
                    continue

                item = (row[0] if row[0] else "").strip()
                details = (row[1] if row[1] else "").strip()

                if not item or not details:
                    # Might be a continuation row
                    if table_data and details:
                        # Append to previous row's details
                        table_data[-1]['details'] += ' ' + details
                    continue

                # Check if this is a continuation of the previous row
                if table_data and (item[0].islower() if item else False):
                    table_data[-1]['details'] += ' ' + item + ' ' + details
                else:
                    # Check if previous row looks incomplete (common sign of page break)
                    # An incomplete row might not end with punctuation
                    if table_data and not table_data[-1]['details'].rstrip().endswith(('.', ':', ')')):
                        # This might be a continuation - check if item looks like a continuation
                        # (starts with lowercase, is a short phrase, etc.)
                        if item and (item[0].islower() or len(item.split()) <= 3):
                            # Likely a continuation
                            table_data[-1]['details'] += ' ' + item
                            if details:
                                table_data[-1]['details'] += ' ' + details
                            continue

                    table_data.append({
                        'item': item,
                        'details': details
                    })

    return table_data


def extract_table_content(pdf_path: str, join_wrapped: bool = True) -> List[Dict[str, str]]:
    """
    Extract the 2-column table content from the determination PDF.

    Args:
        pdf_path: Path to the determination PDF file
        join_wrapped: If True, attempt to join wrapped lines in cell text

    Returns:
        List of dictionaries with 'item' and 'details' keys
    """
    all_page_tables = []

    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, 1):
            tables = page.extract_tables()
            if tables:
                all_page_tables.append((page_num, tables))

    if not all_page_tables:
        # Fallback to text parsing
        with pdfplumber.open(pdf_path) as pdf:
            full_text = ""
            for page in pdf.pages:
                full_text += page.extract_text() + "\n"
            return parse_text_as_table(full_text, join_wrapped)

    # Merge tables from all pages
    table_data = merge_multipage_table_data(all_page_tables)

    # Post-process to join wrapped lines if requested
    if join_wrapped:
        for item in table_data:
            item['details'] = join_wrapped_lines(item['details'])

    return table_data


def parse_text_as_table(text: str, join_wrapped: bool = True) -> List[Dict[str, str]]:
    """
    Fallback method to parse text as a table when table extraction fails.
    """
    table_data = []

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

        is_item = False
        for item in common_items:
            if line.startswith(item):
                if current_item:
                    details_text = ' '.join(current_details).strip()
                    if join_wrapped:
                        details_text = join_wrapped_lines(details_text)
                    table_data.append({
                        'item': current_item,
                        'details': details_text
                    })

                current_item = item
                current_details = [line[len(item):].strip()]
                is_item = True
                break

        if not is_item and current_item:
            current_details.append(line)

    if current_item:
        details_text = ' '.join(current_details).strip()
        if join_wrapped:
            details_text = join_wrapped_lines(details_text)
        table_data.append({
            'item': current_item,
            'details': details_text
        })

    return table_data


def parse_determination_pdf(pdf_path: str, join_wrapped_lines: bool = True) -> Dict[str, any]:
    """
    Parse a determination PDF to extract all relevant information.

    Args:
        pdf_path: Path to the determination PDF file
        join_wrapped_lines: If True, attempt to join text lines that are wrapped

    Returns:
        Dictionary containing:
        - commission_division: The commission division sentence
        - table_content: List of item/details dictionaries
        - table_content_json: JSON string of the table content
    """
    result = {
        'commission_division': None,
        'table_content': [],
        'table_content_json': None
    }

    if not Path(pdf_path).exists():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    # Extract full text for commission division
    full_text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            full_text += page.extract_text() + "\n"

    result['commission_division'] = extract_commission_division(full_text)

    # Extract table content with improvements
    result['table_content'] = extract_table_content(pdf_path, join_wrapped_lines)

    if result['table_content']:
        result['table_content_json'] = json.dumps(result['table_content'], indent=2)

    return result


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python parse_determination_improved.py <path_to_pdf> [--no-join-wrapped]")
        sys.exit(1)

    pdf_path = sys.argv[1]
    join_wrapped = '--no-join-wrapped' not in sys.argv

    try:
        result = parse_determination_pdf(pdf_path, join_wrapped)

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
