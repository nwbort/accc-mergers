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

                    # Skip empty rows or header rows
                    if not item or not details:
                        continue

                    # Check if this is a continuation of the previous row
                    # (item is empty or starts with lowercase/whitespace)
                    if table_data and (not item or item[0].islower() or item.startswith(' ')):
                        # Append to the previous row's details
                        table_data[-1]['details'] += ' ' + item + ' ' + details
                    else:
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
    """
    result = {
        'commission_division': None,
        'table_content': [],
        'table_content_json': None
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
