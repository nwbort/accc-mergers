#!/usr/bin/env python3
"""
Parse questionnaire PDFs to extract consultation closing date and questions.
"""

import pdfplumber
import re
import json
from typing import Optional, Dict, List
from pathlib import Path
from datetime import datetime


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


def parse_deadline_date(deadline_str: str) -> Optional[str]:
    """
    Parse a deadline string into ISO format (YYYY-MM-DD).

    Args:
        deadline_str: Date string like "25 August 2025"

    Returns:
        ISO format date string or None if parsing fails
    """
    if not deadline_str:
        return None

    try:
        # Parse the date string
        date_obj = datetime.strptime(deadline_str, "%d %B %Y")
        return date_obj.strftime("%Y-%m-%d")
    except ValueError:
        return None


def extract_questions(text: str) -> List[Dict[str, str]]:
    """
    Extract the numbered questions from the questionnaire.

    Questions typically appear after a "Questions" heading and are numbered.
    Each question may span multiple lines.

    Args:
        text: Full text of the questionnaire PDF

    Returns:
        List of dictionaries with 'number' and 'text' keys
    """
    questions = []

    # Find the "Questions" section
    questions_match = re.search(r'\bQuestions\b', text, re.IGNORECASE)
    if not questions_match:
        return questions

    # Get text after the "Questions" heading
    text_after_questions = text[questions_match.end():]

    # Split into lines for processing
    lines = text_after_questions.split('\n')

    current_question_num = None
    current_question_text = []

    for line in lines:
        line = line.strip()

        # Skip empty lines
        if not line:
            continue

        # Check if this line starts a new question (e.g., "1.", "2.", "3.")
        question_start_match = re.match(r'^(\d+)\.\s+(.+)$', line)

        if question_start_match:
            # Save the previous question if exists
            if current_question_num is not None:
                questions.append({
                    'number': current_question_num,
                    'text': ' '.join(current_question_text).strip()
                })

            # Start a new question
            current_question_num = int(question_start_match.group(1))
            current_question_text = [question_start_match.group(2)]
        elif current_question_num is not None:
            # This line is a continuation of the current question
            # Stop if we hit certain keywords that indicate end of questions section
            if re.match(r'^(Confidentiality|Note:|Please note)', line, re.IGNORECASE):
                break

            current_question_text.append(line)

    # Don't forget the last question
    if current_question_num is not None:
        questions.append({
            'number': current_question_num,
            'text': ' '.join(current_question_text).strip()
        })

    return questions


def parse_questionnaire_pdf(pdf_path: str) -> Dict[str, any]:
    """
    Parse a questionnaire PDF to extract consultation deadline and questions.

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

    # Check if file exists
    pdf_file = Path(pdf_path)
    if not pdf_file.exists():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    # Extract full text
    full_text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                full_text += page_text + "\n"

    # Extract deadline
    result['deadline'] = extract_deadline(full_text)
    if result['deadline']:
        result['deadline_iso'] = parse_deadline_date(result['deadline'])

    # Extract questions
    result['questions'] = extract_questions(full_text)
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
        # Extract matter ID from the path (e.g., "MN-01016" from "matters/MN-01016/...")
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

            # Print results
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

            # Save results to JSON
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
