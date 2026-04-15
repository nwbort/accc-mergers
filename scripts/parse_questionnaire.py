#!/usr/bin/env python3
"""
Parse questionnaire PDFs to extract consultation closing date and questions.

Uses pdfplumber's character-level font metadata to detect bold section
headers structurally, rather than relying on regex patterns.
"""

import pdfplumber
import re
import json
from typing import Optional, Dict, List
from pathlib import Path
from date_utils import parse_text_to_iso


def extract_deadline(text: str) -> Optional[str]:
    """
    Extract the consultation closing date from the questionnaire.

    Looks for patterns like:
    - "Deadline to respond: 25 August 2025"
    - "Deadline to respond: 3 November 2025"
    - "Deadline to respond: 5.00pm (AEDT) on 20 October 2025"

    Args:
        text: Full text of the questionnaire PDF

    Returns:
        The deadline date as a string, or None if not found
    """
    # Look for "Deadline to respond:" followed by optional time/timezone, then a date
    # Pattern handles both formats:
    # 1. "Deadline to respond: 25 August 2025"
    # 2. "Deadline to respond: 5.00pm (AEDT) on 20 October 2025"
    pattern = r'Deadline to respond:\s*(?:[\d:.apm]+\s*\([A-Z]+\)\s+on\s+)?(\d{1,2}\s+[A-Za-z]+\s+\d{4})'
    match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)

    if match:
        # Clean up the deadline by removing extra whitespace and newlines
        deadline = match.group(1).strip()
        deadline = re.sub(r'\s+', ' ', deadline)  # Replace multiple spaces/newlines with single space
        return deadline

    return None


def _is_bold_line(chars: list) -> bool:
    """
    Determine if a line is bold by examining character font names.

    A line is considered bold if the majority of its non-space alphabetic
    characters use a bold font (fontname contains "Bold").
    """
    if not chars:
        return False

    alpha_chars = [c for c in chars if c.get('text', '').strip()]
    if not alpha_chars:
        return False

    bold_count = sum(
        1 for c in alpha_chars
        if 'bold' in c.get('fontname', '').lower()
    )

    return bold_count > len(alpha_chars) / 2


def extract_lines_with_formatting(pdf_path: str) -> List[Dict]:
    """
    Extract text lines from a PDF with formatting metadata.

    Returns a list of dicts, each with:
    - text: the line's text content
    - is_bold: whether the line is predominantly bold

    Also returns the full plain text for deadline extraction.
    """
    lines = []
    full_text = ""

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                full_text += page_text + "\n"

            text_lines = page.extract_text_lines(return_chars=True)
            for tl in text_lines:
                text = tl.get('text', '').strip()
                if text:
                    lines.append({
                        'text': text,
                        'is_bold': _is_bold_line(tl.get('chars', [])),
                    })

    return lines, full_text


def extract_questions(lines: List[Dict]) -> List[Dict[str, str]]:
    """
    Extract the numbered questions from annotated lines.

    Uses font metadata (bold detection) to identify section headers
    instead of regex pattern matching. A bold, non-numbered line within
    the questions block is treated as a section header.

    Args:
        lines: List of dicts with 'text' and 'is_bold' keys,
               as returned by extract_lines_with_formatting().

    Returns:
        List of dictionaries with 'number', 'text', and optionally 'section' keys
    """
    questions = []

    # Find the "Questions" heading line
    start_idx = None
    for i, line in enumerate(lines):
        if re.match(r'^Questions\b', line['text']) and line['is_bold']:
            start_idx = i + 1
            break

    if start_idx is None:
        return questions

    current_question_num = None
    current_question_text = []
    current_section = None
    has_sections = False
    prev_was_section_header = False

    def save_current_question():
        """Helper to save the current question to the list."""
        nonlocal current_question_num, current_question_text
        if current_question_num is not None:
            full_text = ' '.join(current_question_text).strip()
            full_text = re.sub(r'\s+', ' ', full_text)
            # Remove trailing page numbers (single digit at the end)
            full_text = re.sub(r'\s+\d$', '', full_text)
            questions.append({
                'number': current_question_num,
                'text': full_text,
                'section': current_section,
            })

    for line in lines[start_idx:]:
        text = line['text']
        is_bold = line['is_bold']

        # Stop if we hit certain keywords that indicate end of questions section
        if re.match(r'^(Confidentiality|Note:|Please note)', text, re.IGNORECASE):
            break

        # Bold non-numbered line = section header
        if is_bold and not re.match(r'^\d+\.', text):
            if current_question_num is not None:
                save_current_question()
                current_question_num = None
                current_question_text = []
            # Consecutive bold lines = multi-line section header, concatenate
            if prev_was_section_header and current_section:
                current_section = current_section + ' ' + text
            else:
                current_section = text
            has_sections = True
            prev_was_section_header = True
            continue

        prev_was_section_header = False

        # Check if this line starts a new question (e.g., "1.", "2.", "3.")
        question_start_match = re.match(r'^(\d+)\.\s*(.*)$', text)

        if question_start_match:
            # Save the previous question if exists
            save_current_question()

            # Start a new question
            current_question_num = int(question_start_match.group(1))
            remaining_text = question_start_match.group(2)

            # Check if there are inline questions in the remaining text
            inline_questions = re.split(r'\s+(?=\d+\.\s*[A-Z])', remaining_text)

            if len(inline_questions) > 1:
                current_question_text = [inline_questions[0]]
                save_current_question()
                current_question_num = None
                current_question_text = []

                for inline_q in inline_questions[1:]:
                    inline_match = re.match(r'^(\d+)\.\s*(.*)$', inline_q)
                    if inline_match:
                        current_question_num = int(inline_match.group(1))
                        current_question_text = [inline_match.group(2)]
                        save_current_question()
                        current_question_num = None
                        current_question_text = []
            else:
                current_question_text = [remaining_text] if remaining_text else []
        elif current_question_num is not None:
            # Continuation of current question
            inline_split = re.split(r'\s+(?=\d+\.\s*[A-Z])', text)

            if len(inline_split) > 1:
                current_question_text.append(inline_split[0])
                save_current_question()
                current_question_num = None
                current_question_text = []

                for inline_q in inline_split[1:]:
                    inline_match = re.match(r'^(\d+)\.\s*(.*)$', inline_q)
                    if inline_match:
                        current_question_num = int(inline_match.group(1))
                        current_question_text = [inline_match.group(2)]
                        save_current_question()
                        current_question_num = None
                        current_question_text = []
            else:
                current_question_text.append(text)

    # Don't forget the last question
    save_current_question()

    # If no sections were found, strip the section field to keep output clean
    if not has_sections:
        for q in questions:
            del q['section']

    return questions


def extract_questions_from_text(text: str) -> List[Dict[str, str]]:
    """
    Fallback: extract questions from plain text without formatting metadata.

    Used when character-level data is unavailable (e.g., in tests).
    Falls back to regex-based section detection for known patterns.

    Args:
        text: Full text of the questionnaire PDF

    Returns:
        List of dictionaries with 'number', 'text', and optionally 'section' keys
    """
    # Build annotated lines from plain text using regex heuristics
    questions_match = re.search(r'^Questions\b', text, re.MULTILINE)
    if not questions_match:
        return []

    annotated_lines = []
    for raw_line in text.split('\n'):
        stripped = raw_line.strip()
        if not stripped:
            continue
        # Heuristic: detect section headers by known patterns
        is_header = bool(
            re.match(r'^Questions(\s+for\s+|\s*$)', stripped, re.IGNORECASE)
            or re.match(r'^General\s+questions', stripped, re.IGNORECASE)
            or re.match(r'^Other\s+issues', stripped, re.IGNORECASE)
        )
        annotated_lines.append({'text': stripped, 'is_bold': is_header})

    return extract_questions(annotated_lines)


def parse_questionnaire_pdf(pdf_path: str) -> Dict[str, any]:
    """
    Parse a questionnaire PDF to extract consultation deadline and questions.

    Uses character-level font metadata from pdfplumber to detect bold
    section headers structurally.

    Args:
        pdf_path: Path to the questionnaire PDF file

    Returns:
        Dictionary containing:
        - deadline: The consultation closing date (raw format)
        - deadline_iso: The deadline in ISO format (YYYY-MM-DD)
        - questions: List of question dictionaries with number and text
        - questions_count: Number of questions extracted
    """
    result = {
        'deadline': None,
        'deadline_iso': None,
        'questions': [],
        'questions_count': 0
    }

    pdf_file = Path(pdf_path)
    if not pdf_file.exists():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    # Extract lines with formatting metadata and full text
    annotated_lines, full_text = extract_lines_with_formatting(pdf_path)

    # Extract deadline from plain text
    result['deadline'] = extract_deadline(full_text)
    if result['deadline']:
        result['deadline_iso'] = parse_text_to_iso(result['deadline'], include_time=False)

    # Extract questions using font-aware line data
    result['questions'] = extract_questions(annotated_lines)
    result['questions_count'] = len(result['questions'])

    return result


def process_all_questionnaires(matters_dir: str = "data/raw/matters") -> Dict[str, Dict]:
    """
    Process all questionnaire PDFs in the matters directory.

    Args:
        matters_dir: Path to the matters directory

    Returns:
        Dictionary mapping matter IDs to their questionnaire data
    """
    results = {}
    matters_path = Path(matters_dir)

    if not matters_path.exists():
        raise FileNotFoundError(f"Matters directory not found: {matters_dir}")

    # Find all questionnaire PDFs (case-insensitive search for "questionnaire" in filename)
    all_pdfs = list(matters_path.glob("*/*.pdf"))
    questionnaire_pdfs = [
        pdf for pdf in all_pdfs
        if "questionnaire" in pdf.name.lower()
    ]

    for pdf_path in questionnaire_pdfs:
        matter_id = pdf_path.parent.name

        try:
            data = parse_questionnaire_pdf(str(pdf_path))
            data['file_path'] = str(pdf_path.relative_to(matters_path.parent))
            data['file_name'] = pdf_path.name
            results[matter_id] = data
        except Exception as e:
            print(f"Error processing {pdf_path}: {e}")
            results[matter_id] = {
                'error': str(e),
                'file_path': str(pdf_path.relative_to(matters_path.parent))
            }

    return results


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        # Process a single PDF file
        pdf_path = sys.argv[1]

        try:
            result = parse_questionnaire_pdf(pdf_path)

            print("=" * 80)
            print("CONSULTATION CLOSING DATE:")
            print("=" * 80)
            print(f"Deadline: {result['deadline'] or 'Not found'}")
            if result['deadline_iso']:
                print(f"ISO format: {result['deadline_iso']}")
            print()

            print("=" * 80)
            print("QUESTIONS:")
            print("=" * 80)
            for q in result['questions']:
                section = q.get('section')
                if section:
                    print(f"\n  [{section}]")
                print(f"\nQuestion {q['number']}:")
                print("-" * 40)
                print(q['text'])

            print("\n" + "=" * 80)
            print(f"Extracted {result['questions_count']} questions")

        except Exception as e:
            print(f"Error parsing PDF: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)
    else:
        # Process all questionnaires in the matters directory
        print("Processing all questionnaires in matters directory...")
        print()

        try:
            results = process_all_questionnaires()

            for matter_id, data in sorted(results.items()):
                print("=" * 80)
                print(f"Matter: {matter_id}")
                print("=" * 80)

                if 'error' in data:
                    print(f"ERROR: {data['error']}")
                else:
                    print(f"File: {data['file_name']}")
                    print(f"Deadline: {data['deadline'] or 'Not found'}")
                    if data['deadline_iso']:
                        print(f"ISO format: {data['deadline_iso']}")
                    print(f"Questions: {data['questions_count']}")

                    for q in data['questions']:
                        print(f"\n  {q['number']}. {q['text'][:100]}{'...' if len(q['text']) > 100 else ''}")

                print()

            output_file = "data/processed/questionnaire_data.json"
            with open(output_file, 'w') as f:
                json.dump(results, f, indent=2, sort_keys=True)

            print("=" * 80)
            print(f"Results saved to {output_file}")
            print(f"Processed {len(results)} questionnaires")

        except Exception as e:
            print(f"Error processing questionnaires: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)
