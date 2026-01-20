import os
import json
import sys
from concurrent.futures import ProcessPoolExecutor
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, unquote
import requests
import re
from datetime import datetime
from markdownify import markdownify as md
from parse_determination import parse_determination_pdf
from parse_questionnaire import process_all_questionnaires

BASE_URL = "https://www.accc.gov.au"
MATTERS_DIR = "./data/raw/matters"


def is_safe_filename(filename):
    """
    Validate filename to prevent path traversal attacks.
    Only allows alphanumeric characters, spaces, dots, hyphens, and underscores.
    Rejects filenames with path traversal sequences or suspicious patterns.
    """
    if not filename or not isinstance(filename, str):
        return False

    # Reject empty or whitespace-only filenames
    if not filename.strip():
        return False

    # Reject path traversal sequences
    if '..' in filename or '/' in filename or '\\' in filename:
        return False

    # Allow hyphens, en-dashes, em-dashes, apostrophes, and accented Latin chars
    if not re.match(r'^[a-zA-Z0-9\u00C0-\u00FF][\w\u00C0-\u00FF\u002D\u2013\u2014\u0027\u2019. (),]*\.[a-zA-Z0-9]+$', filename):
        return False

    # Filename should not exceed reasonable length
    if len(filename) > 255:
        return False

    return True


def parse_date_from_text(text: str) -> str:
    """
    Extract and parse a date from text like '21 November 2025' and return ISO format.
    Returns None if no date is found.
    """
    if not text:
        return None

    # Pattern to match dates like "21 November 2025" or "21 Nov 2025"
    date_pattern = r'(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{4})'
    match = re.search(date_pattern, text, re.IGNORECASE)

    if match:
        day = match.group(1)
        month = match.group(2)
        year = match.group(3)

        # Parse the date
        try:
            date_str = f"{day} {month} {year}"
            parsed_date = datetime.strptime(date_str, "%d %B %Y")
            # Return in ISO format with timezone (assuming Australian time, midday)
            return parsed_date.strftime("%Y-%m-%dT12:00:00Z")
        except ValueError:
            # Try abbreviated month format
            try:
                parsed_date = datetime.strptime(date_str, "%d %b %Y")
                return parsed_date.strftime("%Y-%m-%dT12:00:00Z")
            except ValueError:
                return None

    return None


def normalize_determination(determination: str) -> str:
    """Normalize determination strings to cleaner values."""
    if not determination:
        return determination

    # Remove 'ACCC Determination' prefix (with or without space)
    determination = determination.replace('ACCC Determination', '').strip()

    # Normalize common patterns
    if 'Approved' in determination or 'approved' in determination:
        return 'Approved'
    elif 'Declined' in determination or 'declined' in determination:
        return 'Declined'
    elif 'Not opposed' in determination or 'not opposed' in determination:
        return 'Not opposed'

    return determination


def download_attachment(merger_id, attachment_url, event_title=None):
    """
    Downloads an attachment if it doesn't already exist locally.
    If it's a determination PDF, also parses it to extract commission division and table content.

    Args:
        merger_id: The merger ID
        attachment_url: URL to download
        event_title: Title of the event (used to detect determination PDFs)

    Returns:
        Dictionary with parsed determination data if applicable, None otherwise
    """
    if not merger_id or not attachment_url:
        return None

    determination_data = None

    try:
        # Create a directory for the merger's attachments
        attachment_dir = os.path.join(MATTERS_DIR, merger_id)
        os.makedirs(attachment_dir, exist_ok=True)

        # Get filename from URL and construct local path
        # Security: Decode URL first, then extract basename, then validate
        parsed_url = urlparse(attachment_url)
        decoded_path = unquote(parsed_url.path)
        filename = os.path.basename(decoded_path)

        # Security: Validate filename to prevent path traversal
        if not is_safe_filename(filename):
            print(f"Warning: Unsafe filename detected and rejected: {filename}", file=sys.stderr)
            return None

        local_filepath = os.path.join(attachment_dir, filename)

        # Check if the file already exists before downloading
        if not os.path.exists(local_filepath):
            print(f"Downloading new attachment for {merger_id}: {filename}", file=sys.stderr)

            # Download the file
            response = requests.get(attachment_url, stream=True)
            response.raise_for_status()  # Raise an exception for bad status codes

            # Save the file
            with open(local_filepath, 'wb') as f_out:
                for chunk in response.iter_content(chunk_size=8192):
                    f_out.write(chunk)
            print(f"Saved to {local_filepath}", file=sys.stderr)

        # Check if this is a determination PDF and parse it
        is_determination = (
            event_title and
            'determination' in event_title.lower() and
            filename.lower().endswith('.pdf')
        )

        if is_determination and os.path.exists(local_filepath):
            print(f"Parsing determination PDF: {filename}", file=sys.stderr)
            try:
                determination_data = parse_determination_pdf(local_filepath)
                print(f"Successfully parsed determination PDF: {filename}", file=sys.stderr)
            except Exception as e:
                print(f"Error parsing determination PDF {filename}: {e}", file=sys.stderr)
                determination_data = None

    except requests.exceptions.RequestException as e:
        print(f"Error downloading {attachment_url}: {e}", file=sys.stderr)
    except IOError as e:
        print(f"Error saving file {local_filepath}: {e}", file=sys.stderr)

    return determination_data


def get_serve_filename(original_filename: str) -> str:
    """
    Determine the filename to serve to users.
    For DOCX files, returns the PDF filename (conversion handled by separate workflow).
    For other files, returns the original filename.
    """
    if original_filename.lower().endswith('.docx'):
        # Return PDF filename - conversion workflow will create it
        return os.path.splitext(original_filename)[0] + '.pdf'
    return original_filename


def parse_merger_file(filepath, existing_merger_data=None):
    """
    Parses a single HTML file, extracts structured data for a merger,
    and downloads any new attachments found. This function is designed to be
    run in a separate process.

    Args:
        filepath (str): The path to the HTML file.
        existing_merger_data (dict or None): Existing data for the merger.

    Returns:
        dict or None: A dictionary containing the structured data for the merger,
                      or None if parsing fails.
    """
    try:
        print(f"Processing file: {filepath}...", file=sys.stderr)
        with open(filepath, 'r', encoding='utf-8') as f:
            html_content = f.read()

        soup = BeautifulSoup(html_content, 'html.parser')
        merger_data = {}

        # --- URL ---
        canonical_link = soup.find('link', rel='canonical')
        if canonical_link and canonical_link.has_attr('href'):
            merger_data['url'] = canonical_link['href']

        # --- Basic Information ---
        merger_data['merger_name'] = soup.find('h1', class_='page-title').get_text(strip=True) if soup.find('h1', class_='page-title') else None
        
        status_tag = soup.select_one('.field--name-field-acccgov-merger-status .field__item')
        merger_data['status'] = status_tag.get_text(strip=True) if status_tag else None

        id_tag = soup.select_one('.field--name-dynamic-token-fieldnode-acccgov-merger-id .field__item')
        merger_id = id_tag.get_text(strip=True) if id_tag else None
        merger_data['merger_id'] = merger_id
        
        # --- Dates and Status ---
        date_tag = soup.find('div', class_='field--name-field-acccgov-pub-reg-date')
        if date_tag and date_tag.find('time'):
            merger_data['effective_notification_datetime'] = date_tag.find('time')['datetime']

        stage_tag = soup.find('div', class_='field--name-field-acquisition-stage')
        merger_data['stage'] = stage_tag.get_text(strip=True, separator=' ',).replace('Stage ', '') if stage_tag else None

        end_date_tag = soup.find('div', class_='field--name-field-acccgov-end-determination')
        if end_date_tag and end_date_tag.find('time'):
            merger_data['end_of_determination_period'] = end_date_tag.find('time')['datetime']
        elif existing_merger_data and 'end_of_determination_period' in existing_merger_data:
            # Preserve end_of_determination_period from existing data if not in HTML
            # (it's often removed from the HTML after assessment is completed)
            merger_data['end_of_determination_period'] = existing_merger_data['end_of_determination_period']
        
        determination_date_tag = soup.find('div', class_='field--name-field-acccgov-pub-reg-end-date')
        if determination_date_tag and determination_date_tag.find('time'):
            merger_data['determination_publication_date'] = determination_date_tag.find('time')['datetime']
            
        determination_tag = soup.find('div', class_='field--name-field-acccgov-acquisition-deter')
        if determination_tag:
            raw_determination = determination_tag.get_text(strip=True)
            merger_data['accc_determination'] = normalize_determination(raw_determination)

        # --- Consultation Response Due Date ---
        consultation_tag = soup.find('div', class_='field--name-field-acccgov-consultation-text')
        consultation_due_date = None
        if consultation_tag:
            consultation_text = consultation_tag.get_text(strip=True)
            # Look for patterns like "provided by 21 November 2025"
            consultation_due_date = parse_date_from_text(consultation_text)

        if consultation_due_date:
            merger_data['consultation_response_due_date'] = consultation_due_date
        elif existing_merger_data and 'consultation_response_due_date' in existing_merger_data:
            # Preserve consultation_response_due_date from existing data if not in HTML
            # or if consultation text doesn't contain a parseable date
            # (it's often removed or changed after consultation period ends)
            merger_data['consultation_response_due_date'] = existing_merger_data['consultation_response_due_date']

        # --- Parties (Acquirers and Targets) ---
        def get_parties(field_name):
            parties = []
            container = soup.find('div', class_=field_name)
            if not container: return parties
            
            for item in container.find_all('div', class_='paragraph--type--acccgov-trader'):
                name = item.find('span', class_='field_acccgov_name').get_text(strip=True)
                acn_span = item.find_all('span')[-1]
                acn_text = acn_span.get_text(strip=True).replace('-', '').strip()
                party_type, number = (('ACN', acn_text.replace('ACN', '').strip()) if 'ACN' in acn_text else
                                    ('ABN', acn_text.replace('ABN', '').strip()) if 'ABN' in acn_text else
                                    (None, acn_text))
                parties.append({'name': name, 'identifier_type': party_type, 'identifier': number})
            return parties

        merger_data['acquirers'] = get_parties('field--name-field-acccgov-applicants')
        merger_data['targets'] = get_parties('field--name-field-acccgov-pub-reg-targets')
        merger_data['other_parties'] = get_parties('field--name-field-acccgov-other-parties')

        # --- ANZSIC Codes ---
        merger_data['anszic_codes'] = []
        anszic_container = soup.find('div', class_='field--name-field-acquisition-anzsic-code')
        if anszic_container:
            for code in anszic_container.find_all('div', class_='field__item'):
                text = code.get_text(strip=True)
                # Split by semicolon first to handle multiple codes in one field__item
                for code_entry in text.split(';'):
                    code_entry = code_entry.strip()
                    if code_entry:
                        parts = code_entry.split(maxsplit=1)
                        if len(parts) >= 2:
                            code_num = parts[0]
                            code_name = parts[1]
                            merger_data['anszic_codes'].append({'code': code_num, 'name': code_name})

        # --- Description ---
        description_tag = soup.find('div', class_='field--name-field-accc-body')
        if description_tag:
            full_text_div = description_tag.find('div', class_='full-text')
            if full_text_div:
                # Convert HTML to Markdown to preserve formatting (bullets, bold, etc.)
                description_html = str(full_text_div)
                description_md = md(description_html, heading_style="ATX", strip=['a'])
                merger_data['merger_description'] = description_md.strip()
            else:
                # Fallback to old method if full-text div not found
                field_item = description_tag.find('div', class_='field__item')
                if field_item:
                    description_html = str(field_item)
                    description_md = md(description_html, heading_style="ATX", strip=['a'])
                    # Remove the 'Description' heading if present
                    description_md = description_md.replace('### Description', '').strip()
                    merger_data['merger_description'] = description_md
                else:
                    merger_data['merger_description'] = description_tag.get_text('\n', strip=True).replace('Description','').strip()

        # --- Events ---
        merger_data['events'] = []
        scraped_events = []
        attachment_tables = soup.find_all('div', class_='table-responsive')
        for table in attachment_tables:
            for row in table.find_all('tr'):
                date_cell = row.find('td', class_='acccgov-timeline__date')
                link_cell = row.find('td', class_='acccgov-timeline__file-link')
                title_cell = next((c for c in row.find_all('td') if c not in [date_cell, link_cell]), None)

                if not (date_cell and title_cell):
                    continue

                title = title_cell.get_text(strip=True)
                event = {
                    'date': date_cell.find('time')['datetime'] if date_cell.find('time') else date_cell.get_text(strip=True),
                    'title': title,
                    'display_title': title  # Default to title, can be manually overridden
                }

                link_tag = link_cell.find('a') if link_cell else None
                if link_tag and link_tag.has_attr('href'):
                    url = urljoin(BASE_URL, link_tag['href'])
                    event['url'] = url

                    # Download attachment and parse if it's a determination PDF
                    determination_data = download_attachment(merger_id, url, title)

                    # If determination data was parsed, add it to the event
                    if determination_data:
                        event['determination_commission_division'] = determination_data.get('commission_division')
                        event['determination_table_content'] = determination_data.get('table_content')

                    # Get original filename and determine serve filename
                    # For DOCX files, url_gh points to PDF (created by separate workflow)
                    parsed_url = urlparse(url)
                    original_filename = unquote(os.path.basename(parsed_url.path))
                    serve_filename = get_serve_filename(original_filename)
                    
                    event['url_gh'] = f"/matters/{merger_id}/{serve_filename}"
                    event['status'] = 'live'

                scraped_events.append(event)

        # Merge scraped events with existing events
        if existing_merger_data and 'events' in existing_merger_data:
            existing_events = existing_merger_data['events']

            # Create a mapping of scraped events by URL (for events with URLs)
            # Use URL as the primary key for matching to avoid title-based duplicates
            scraped_by_url = {}
            scraped_without_url = []

            for event in scraped_events:
                if 'url' in event:
                    scraped_by_url[event['url']] = event
                else:
                    scraped_without_url.append(event)

            # Process existing events
            merged_events = []
            existing_urls_processed = set()

            for existing_event in existing_events:
                if 'url' in existing_event:
                    url = existing_event['url']
                    if url in scraped_by_url:
                        # Event still exists, update it but preserve display_title
                        updated_event = scraped_by_url[url].copy()
                        if 'display_title' in existing_event:
                            updated_event['display_title'] = existing_event['display_title']
                        merged_events.append(updated_event)
                        existing_urls_processed.add(url)
                    else:
                        # Event no longer in scrape, mark as removed
                        existing_event['status'] = 'removed'
                        merged_events.append(existing_event)
                else:
                    # Event without URL (like "Merger notified to ACCC")
                    # Match by title for these
                    matching_scraped = next(
                        (e for e in scraped_without_url if e['title'] == existing_event['title']),
                        None
                    )
                    if matching_scraped:
                        # Preserve display_title if it exists
                        if 'display_title' in existing_event:
                            matching_scraped['display_title'] = existing_event['display_title']
                        elif 'display_title' not in matching_scraped:
                            matching_scraped['display_title'] = matching_scraped['title']
                        merged_events.append(matching_scraped)
                        scraped_without_url.remove(matching_scraped)
                    else:
                        # Add display_title if missing
                        if 'display_title' not in existing_event:
                            existing_event['display_title'] = existing_event['title']
                        merged_events.append(existing_event)

            # Add any new scraped events that weren't in existing
            for url, event in scraped_by_url.items():
                if url not in existing_urls_processed:
                    merged_events.append(event)

            # Add any remaining scraped events without URLs
            for event in scraped_without_url:
                if 'display_title' not in event:
                    event['display_title'] = event['title']
                merged_events.append(event)

            merger_data['events'] = merged_events
        else:
            merger_data['events'] = scraped_events

        # Add notification date as an event
        if merger_data.get('effective_notification_datetime'):
            notification_title = 'Merger notified to ACCC'
            notification_event = {
                'date': merger_data['effective_notification_datetime'],
                'title': notification_title,
                'display_title': notification_title,
            }
            # Add to events if not already there
            if not any(e['title'] == notification_event['title'] for e in merger_data['events']):
                merger_data['events'].append(notification_event)

        # Add determination publication as an event
        if merger_data.get('determination_publication_date'):
            determination = merger_data.get('accc_determination', 'Decision made')
            phase = merger_data.get('stage', 'Phase 1')
            determination_title = f"{phase} determination: {determination}"
            determination_event = {
                'date': merger_data['determination_publication_date'],
                'title': determination_title,
                'display_title': determination_title,
            }

            # Remove old format determination events to avoid duplicates
            merger_data['events'] = [
                e for e in merger_data['events']
                if not (e['title'].startswith('Determination published:') and
                       e['date'] == merger_data['determination_publication_date'])
            ]

            # Add new determination event if not already there
            if not any(e['title'] == determination_title for e in merger_data['events']):
                merger_data['events'].append(determination_event)

        return merger_data
    
    except Exception as e:
        print(f"Error processing {filepath}: {e}", file=sys.stderr)
        return None


def get_merger_id_from_file(filepath):
    """Extracts the merger ID from the HTML file without full parsing."""
    with open(filepath, 'r', encoding='utf-8') as f:
        html_content = f.read()
    soup = BeautifulSoup(html_content, 'html.parser')
    id_tag = soup.select_one('.field--name-dynamic-token-fieldnode-acccgov-merger-id .field__item')
    if id_tag:
        return id_tag.get_text(strip=True)
    return None


def enrich_with_questionnaire_data(mergers_data):
    """
    Enrich merger data with consultation deadlines from questionnaire PDFs.
    Only updates consultation_response_due_date if it's missing from the merger data.
    Also writes questionnaire_data.json as a standalone reference file.

    Args:
        mergers_data: List of merger dictionaries

    Returns:
        Updated list of merger dictionaries
    """
    print("Extracting questionnaire data...", file=sys.stderr)

    try:
        # Process all questionnaires in the matters directory
        questionnaire_data = process_all_questionnaires(MATTERS_DIR)

        if not questionnaire_data:
            print("No questionnaire data found.", file=sys.stderr)
            return mergers_data

        print(f"Found {len(questionnaire_data)} questionnaires", file=sys.stderr)

        # Write questionnaire data to JSON file for reference
        with open('data/processed/questionnaire_data.json', 'w', encoding='utf-8') as f:
            json.dump(questionnaire_data, f, indent=2, sort_keys=True)
        print("Wrote data/processed/questionnaire_data.json", file=sys.stderr)

        # Create a mapping of merger_id to merger data for quick lookups
        mergers_by_id = {m['merger_id']: m for m in mergers_data if 'merger_id' in m}

        # Update mergers with questionnaire data where consultation date is missing
        updates_made = 0
        for matter_id, q_data in questionnaire_data.items():
            if matter_id in mergers_by_id:
                merger = mergers_by_id[matter_id]

                # Only update if consultation_response_due_date is missing and we have a deadline
                if (not merger.get('consultation_response_due_date') and
                    q_data.get('deadline_iso')):

                    # Convert ISO date (YYYY-MM-DD) to datetime format with time
                    iso_date = q_data['deadline_iso']
                    consultation_datetime = f"{iso_date}T12:00:00Z"
                    merger['consultation_response_due_date'] = consultation_datetime

                    print(f"Updated {matter_id} with consultation date: {consultation_datetime}",
                          file=sys.stderr)
                    updates_made += 1

        if updates_made > 0:
            print(f"Updated {updates_made} merger(s) with questionnaire consultation dates",
                  file=sys.stderr)
        else:
            print("No consultation dates needed updating", file=sys.stderr)

    except Exception as e:
        print(f"Error enriching with questionnaire data: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)

    return mergers_data

def run_parse_merger_file(task):
    """Helper function to unpack arguments for parse_merger_file."""
    return parse_merger_file(*task)

def main():
    """
    Main function to find all merger HTML files, parse them in parallel,
    and print the consolidated data as JSON to stdout.
    """
    if not os.path.isdir(MATTERS_DIR):
        print(f"Error: Directory '{MATTERS_DIR}' not found.", file=sys.stderr)
        sys.exit(1)

    # 1. Load existing data if mergers.json exists
    existing_mergers = {}
    mergers_json_path = 'data/processed/mergers.json'
    if os.path.exists(mergers_json_path) and os.path.getsize(mergers_json_path) > 0:
        try:
            with open(mergers_json_path, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
                for merger in existing_data:
                    if 'merger_id' in merger:
                        existing_mergers[merger['merger_id']] = merger
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON from {mergers_json_path}:", file=sys.stderr)
            print(f"  - Error: {e.msg}", file=sys.stderr)
            print(f"  - At line {e.lineno}, column {e.colno}", file=sys.stderr)
            
            # Go back and read the problematic line to show the user
            with open(mergers_json_path, 'r', encoding='utf-8') as f_debug:
                for i, line in enumerate(f_debug, 1):
                    if i == e.lineno:
                        print(f"Problematic line ({i}): {line.strip()}", file=sys.stderr)
                        print(f"{' ' * (e.colno + 21)}--->^", file=sys.stderr)
                        break
            sys.exit(1) # Exit if the existing data can't be parsed
    elif os.path.exists(mergers_json_path):
         print("Warning: mergers.json exists but is empty. Starting fresh.", file=sys.stderr)


    # 2. Get a list of all HTML file paths to process
    filepaths = [
        os.path.join(MATTERS_DIR, filename)
        for filename in os.listdir(MATTERS_DIR)
        if filename.endswith(".html")
    ]

    all_mergers_data = []
    # 3. Use a ProcessPoolExecutor to run parsing in parallel
    with ProcessPoolExecutor() as executor:
        # Create a list of arguments for parse_merger_file
        tasks = []
        for fp in filepaths:
            merger_id = get_merger_id_from_file(fp)
            if merger_id:
                tasks.append((fp, existing_mergers.get(merger_id)))
            else:
                print(f"Warning: Could not extract merger_id from {fp}", file=sys.stderr)

        # The map function applies parse_merger_file to each task tuple
        results = executor.map(run_parse_merger_file, tasks)
        
        # 4. Collect valid results, filtering out any None values from failed parses
        all_mergers_data = [data for data in results if data is not None]

    # 5. Enrich with questionnaire data (consultation deadlines)
    all_mergers_data = enrich_with_questionnaire_data(all_mergers_data)

    # 6. Sort the data by merger_id to ensure a consistent output
    all_mergers_data.sort(key=lambda x: x.get('merger_id', ''))

    # 7. Write the final JSON output to mergers.json
    with open('data/processed/mergers.json', 'w', encoding='utf-8') as f:
        json.dump(all_mergers_data, f, indent=2)

if __name__ == "__main__":
    main()
