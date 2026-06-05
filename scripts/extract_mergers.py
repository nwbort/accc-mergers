import os
import json
import sys
import argparse
from concurrent.futures import ProcessPoolExecutor
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, unquote
import unicodedata
import requests
import re
from datetime import datetime
from markdownify import markdownify as md
from parse_determination import parse_determination_pdf
from parse_nocc import (
    process_all_noccs,
    _build_caches_from_existing as _build_nocc_caches,
    _DEFAULT_CACHE_PATH as _NOCC_CACHE_PATH,
)
from parse_questionnaire import (
    process_all_questionnaires,
    _build_caches_from_existing as _build_q_caches,
    _DEFAULT_CACHE_PATH as _Q_CACHE_PATH,
    _NEG_CACHE_KEY as _Q_NEG_CACHE_KEY,
)
from normalization import normalize_determination
from cutoff import should_skip_merger, get_skipped_merger_ids, is_waiver_merger
from date_utils import parse_text_to_iso, parse_iso_datetime
from static_data.enrichment import is_phase_2_referral_event
from constants import merger_status

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

    # Reject consecutive spaces (should be normalized by sanitize_filename)
    if '  ' in filename:
        return False

    # Allow hyphens, en-dashes, em-dashes, apostrophes, and accented Latin chars
    if not re.match(r'^[a-zA-Z0-9\u00C0-\u00FF][\w\u00C0-\u00FF\u002D\u2013\u2014\u0027\u2019. (),]*\.[a-zA-Z0-9]+$', filename):
        return False

    # Filename should not exceed reasonable length
    if len(filename) > 255:
        return False

    return True


def sanitize_filename(filename):
    """
    Sanitize a filename by replacing problematic characters with safe alternatives.
    Preserves the file extension and returns a filename that passes is_safe_filename().

    Characters replaced:
    - Colons (:) -> hyphen (-) - problematic on Windows
    - Ampersands (&) -> 'and' - not allowed in safe filename regex

    Returns None if the filename cannot be sanitized (e.g., path traversal attempts).
    """
    if not filename or not isinstance(filename, str):
        return None

    # Normalize Unicode to prevent bypass via homoglyphs or decomposed characters
    filename = unicodedata.normalize('NFKC', filename)

    # Reject empty or whitespace-only filenames
    if not filename.strip():
        return None

    # Reject path traversal sequences - these can't be sanitized safely
    if '..' in filename or '/' in filename or '\\' in filename:
        return None

    # Replace colons with hyphens (common in document titles like "Company: Document")
    sanitized = filename.replace(':', ' -')

    # Replace ampersands with 'and' (common in company names like "Toyota & Ford")
    sanitized = sanitized.replace('&', 'and')

    # Replace percent signs with 'pct' (common in titles like "50% acquisition")
    sanitized = sanitized.replace('%', 'pct')

    # Clean up any double spaces that might result
    while '  ' in sanitized:
        sanitized = sanitized.replace('  ', ' ')

    sanitized = sanitized.strip()

    # Filename should not exceed reasonable length
    if len(sanitized) > 255:
        # Truncate but preserve extension
        name, ext = os.path.splitext(sanitized)
        max_name_len = 255 - len(ext)
        sanitized = name[:max_name_len] + ext

    # Verify the sanitized filename is safe
    if not is_safe_filename(sanitized):
        return None

    return sanitized


def is_safe_url(url):
    """Validate that a URL points to an allowed domain to prevent SSRF attacks."""
    parsed = urlparse(url)
    return (parsed.scheme in ('http', 'https')
            and parsed.netloc.endswith('accc.gov.au'))


def download_attachment(merger_id, attachment_url, event_title=None, cached_determination_data=None):
    """
    Downloads an attachment if it doesn't already exist locally.
    If it's a determination PDF, also parses it to extract commission division and table content.

    Args:
        merger_id: The merger ID
        attachment_url: URL to download
        event_title: Title of the event (used to detect determination PDFs)
        cached_determination_data: Previously-parsed determination data for this
            attachment. When provided, parse_determination_pdf() is skipped and
            this value is returned as-is for determination PDFs.

    Returns:
        Dictionary with parsed determination data if applicable, None otherwise
    """
    if not merger_id or not attachment_url:
        return None

    if not is_safe_url(attachment_url):
        print(f"Warning: Rejecting URL with disallowed domain: {attachment_url}", file=sys.stderr)
        return None

    determination_data = None

    try:
        # Create a directory for the merger's attachments
        attachment_dir = os.path.join(MATTERS_DIR, merger_id)
        os.makedirs(attachment_dir, exist_ok=True)

        # Get filename from URL and construct local path
        # Security: Decode URL first, then extract basename, then sanitize
        parsed_url = urlparse(attachment_url)
        decoded_path = unquote(parsed_url.path)
        original_filename = os.path.basename(decoded_path).strip()  # Strip accidental leading/trailing whitespace

        # Security: Sanitize filename to prevent path traversal and handle problematic characters
        if is_safe_filename(original_filename):
            filename = original_filename
        else:
            filename = sanitize_filename(original_filename)
            if filename is None:
                print(f"Warning: Unsafe filename could not be sanitized: {original_filename}", file=sys.stderr)
                return None

        local_filepath = os.path.join(attachment_dir, filename)

        # Check if the file already exists before downloading
        if not os.path.exists(local_filepath):
            # Download the file
            response = requests.get(attachment_url, stream=True, timeout=30)
            response.raise_for_status()  # Raise an exception for bad status codes

            # Save the file
            with open(local_filepath, 'wb') as f_out:
                for chunk in response.iter_content(chunk_size=8192):
                    f_out.write(chunk)

        # Check if this is a determination PDF and parse it
        is_determination = (
            event_title and
            'determination' in event_title.lower() and
            filename.lower().endswith('.pdf')
        )

        if is_determination and os.path.exists(local_filepath):
            if cached_determination_data is not None:
                determination_data = cached_determination_data
            else:
                try:
                    determination_data = parse_determination_pdf(local_filepath)
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


FROZEN_EVENTS_MERGERS_PATH = 'data/frozen_events_mergers.json'

# Known determination dates for mergers where the ACCC page is unlikely to be corrected
KNOWN_DETERMINATION_DATES = {
    'MN-15002': '2026-02-19T12:00:00Z',  # Google - Wiz: approved 19 Feb 2026, date never added to page
}


def _load_frozen_events_mergers():
    """Load frozen-events and field-override data from frozen_events_mergers.json.

    Returns:
        tuple: (frozen_ids, field_overrides)
            frozen_ids: set of merger IDs whose events should not be updated from scraping.
                An entry with an empty dict or ``freeze_events: true`` freezes events.
            field_overrides: dict mapping merger IDs to dicts of field values that should
                replace whatever the scraper finds.  Any key other than ``freeze_events``
                (and keys starting with ``_``) is treated as a field override.
    """
    try:
        with open(FROZEN_EVENTS_MERGERS_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        frozen_ids = set()
        field_overrides = {}
        for k, v in data.items():
            if k.startswith('_'):
                continue
            if not isinstance(v, dict) or not v or v.get('freeze_events'):
                frozen_ids.add(k)
            if isinstance(v, dict):
                overrides = {fk: fv for fk, fv in v.items()
                             if fk != 'freeze_events' and not fk.startswith('_')}
                if overrides:
                    field_overrides[k] = overrides
        return frozen_ids, field_overrides
    except FileNotFoundError:
        return set(), {}
    except Exception as e:
        print(f"Warning: could not load {FROZEN_EVENTS_MERGERS_PATH}: {e}", file=sys.stderr)
        return set(), {}


def _extract_basic_info(soup):
    """Extract URL, name, status, and merger ID from the parsed HTML."""
    data = {}

    canonical_link = soup.find('link', rel='canonical')
    if canonical_link and canonical_link.has_attr('href'):
        data['url'] = canonical_link['href']

    data['merger_name'] = soup.find('h1', class_='page-title').get_text(strip=True) if soup.find('h1', class_='page-title') else None

    status_tag = soup.select_one('.field--name-field-acccgov-merger-status .field__item')
    data['status'] = status_tag.get_text(strip=True) if status_tag else None

    id_tag = soup.select_one('.field--name-dynamic-token-fieldnode-acccgov-merger-id .field__item')
    data['merger_id'] = id_tag.get_text(strip=True) if id_tag else None

    return data


def _extract_dates_and_status(soup, merger_id, existing_merger_data):
    """Extract dates, stage, determination info, and page modification time."""
    data = {}

    date_tag = soup.find('div', class_='field--name-field-acccgov-pub-reg-date')
    if date_tag and date_tag.find('time'):
        data['effective_notification_datetime'] = date_tag.find('time')['datetime']

    # Preserve original_notification_datetime from existing data if already set,
    # otherwise initialise it from the current effective_notification_datetime.
    if existing_merger_data and existing_merger_data.get('original_notification_datetime'):
        data['original_notification_datetime'] = existing_merger_data['original_notification_datetime']
    else:
        data['original_notification_datetime'] = data.get('effective_notification_datetime')

    stage_tag = soup.find('div', class_='field--name-field-acquisition-stage')
    data['stage'] = stage_tag.get_text(strip=True, separator=' ',).replace('Stage ', '') if stage_tag else None

    end_date_tag = soup.find('div', class_='field--name-field-acccgov-end-determination')
    if end_date_tag and end_date_tag.find('time'):
        data['end_of_determination_period'] = end_date_tag.find('time')['datetime']
    elif existing_merger_data and 'end_of_determination_period' in existing_merger_data:
        # Preserve from existing data (often removed from HTML after assessment completes)
        data['end_of_determination_period'] = existing_merger_data['end_of_determination_period']

    determination_date_tag = soup.find('div', class_='field--name-field-acccgov-pub-reg-end-date')
    if determination_date_tag and determination_date_tag.find('time'):
        data['determination_publication_date'] = determination_date_tag.find('time')['datetime']

    determination_tag = soup.find('div', class_='field--name-field-acccgov-acquisition-deter')
    if determination_tag:
        raw_determination = determination_tag.get_text(strip=True)
        data['accc_determination'] = normalize_determination(raw_determination)

    # Use known hardcoded date if the page is missing the determination date
    if data.get('accc_determination') and not data.get('determination_publication_date'):
        if merger_id in KNOWN_DETERMINATION_DATES:
            data['determination_publication_date'] = KNOWN_DETERMINATION_DATES[merger_id]

    modified_meta = soup.find('meta', attrs={'name': 'dcterms.modified'})
    if modified_meta and modified_meta.has_attr('content'):
        data['page_modified_datetime'] = modified_meta['content']

    return data


def _extract_consultation_date(soup, existing_merger_data):
    """Extract consultation response due date, preserving existing data as fallback."""
    consultation_tag = soup.find('div', class_='field--name-field-acccgov-consultation-text')
    consultation_due_date = None
    if consultation_tag:
        consultation_text = consultation_tag.get_text(strip=True)
        consultation_due_date = parse_text_to_iso(consultation_text, include_time=True)

    if consultation_due_date:
        return {'consultation_response_due_date': consultation_due_date}
    elif existing_merger_data and 'consultation_response_due_date' in existing_merger_data:
        # Preserve from existing data (often removed after consultation period ends)
        return {'consultation_response_due_date': existing_merger_data['consultation_response_due_date']}

    return {}


def _extract_parties(soup):
    """Extract acquirers, targets, and other parties."""
    def get_parties(field_name):
        parties = []
        container = soup.find('div', class_=field_name)
        if not container:
            return parties

        for item in container.find_all('div', class_='paragraph--type--acccgov-trader'):
            name = item.find('span', class_='field_acccgov_name').get_text(strip=True)
            acn_span = item.find_all('span')[-1]
            acn_text = acn_span.get_text(strip=True).replace('-', '').strip()
            party_type, number = (('ACN', acn_text.replace('ACN', '').strip()) if 'ACN' in acn_text else
                                ('ABN', acn_text.replace('ABN', '').strip()) if 'ABN' in acn_text else
                                (None, acn_text))
            parties.append({'name': name, 'identifier_type': party_type, 'identifier': number})
        return parties

    return {
        'acquirers': get_parties('field--name-field-acccgov-applicants'),
        'targets': get_parties('field--name-field-acccgov-pub-reg-targets'),
        'other_parties': get_parties('field--name-field-acccgov-other-parties'),
    }


def _extract_anzsic_codes(soup):
    """Extract ANZSIC industry classification codes."""
    codes = []
    container = soup.find('div', class_='field--name-field-acquisition-anzsic-code')
    if container:
        for code_div in container.find_all('div', class_='field__item'):
            text = code_div.get_text(strip=True)
            for code_entry in text.split(';'):
                code_entry = code_entry.strip()
                if code_entry:
                    parts = code_entry.split(maxsplit=1)
                    if len(parts) >= 2:
                        codes.append({'code': parts[0], 'name': parts[1]})
    return codes


def _extract_description(soup):
    """Extract merger description, converting HTML to Markdown."""
    description_tag = soup.find('div', class_='field--name-field-accc-body')
    if not description_tag:
        return None

    full_text_div = description_tag.find('div', class_='full-text')
    if full_text_div:
        description_html = str(full_text_div)
        description_md = md(description_html, heading_style="ATX", strip=['a'])
        return description_md.strip()

    field_item = description_tag.find('div', class_='field__item')
    if field_item:
        description_html = str(field_item)
        description_md = md(description_html, heading_style="ATX", strip=['a'])
        return description_md.replace('### Description', '').strip()

    return description_tag.get_text('\n', strip=True).replace('Description', '').strip()


def _scrape_events(soup, merger_id, existing_merger_data=None):
    """Scrape timeline events from the HTML, downloading attachments as needed.

    Reuses previously-parsed determination data from ``existing_merger_data``
    (matched by attachment URL) to avoid re-parsing PDFs on every run.
    """
    cached_determination_by_url = {}
    if existing_merger_data:
        for existing_event in existing_merger_data.get('events', []):
            url = existing_event.get('url')
            # 'determination_commission_division' is always written when a
            # determination PDF parse has previously succeeded, so use its
            # presence as the signal that we have cached data to reuse.
            if url and 'determination_commission_division' in existing_event:
                cached_determination_by_url[url] = {
                    'commission_division': existing_event.get('determination_commission_division'),
                    'table_content': existing_event.get('determination_table_content'),
                    'statement_of_reasons': existing_event.get('determination_statement_of_reasons'),
                }

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
                'display_title': title,
            }

            link_tag = link_cell.find('a') if link_cell else None
            if link_tag and link_tag.has_attr('href'):
                url = urljoin(BASE_URL, link_tag['href'])
                event['url'] = url

                determination_data = download_attachment(
                    merger_id, url, title,
                    cached_determination_data=cached_determination_by_url.get(url),
                )
                if determination_data:
                    event['determination_commission_division'] = determination_data.get('commission_division')
                    event['determination_table_content'] = determination_data.get('table_content')
                    statement = determination_data.get('statement_of_reasons')
                    if statement:
                        event['determination_statement_of_reasons'] = statement

                parsed_url = urlparse(url)
                original_filename = unquote(os.path.basename(parsed_url.path)).strip()
                if is_safe_filename(original_filename):
                    safe_filename = original_filename
                else:
                    safe_filename = sanitize_filename(original_filename)

                if safe_filename:
                    serve_filename = get_serve_filename(safe_filename)
                    event['url_gh'] = f"/mergers/{merger_id}/{serve_filename}"
                event['status'] = 'live'

            scraped_events.append(event)

    return scraped_events


def _merge_events(scraped_events, existing_merger_data, merger_id, frozen_events_mergers):
    """Merge scraped events with existing events, handling frozen mergers and display_title preservation."""
    frozen = frozen_events_mergers or set()

    if existing_merger_data and 'events' in existing_merger_data and merger_id in frozen:
        # Events are frozen: preserve existing events exactly as-is, only add genuinely new ones
        existing_urls = {e['url'] for e in existing_merger_data['events'] if 'url' in e}
        new_events = [e for e in scraped_events if e.get('url') not in existing_urls and 'url' in e]
        return existing_merger_data['events'] + new_events

    if not (existing_merger_data and 'events' in existing_merger_data):
        return scraped_events

    existing_events = existing_merger_data['events']

    scraped_by_url = {}
    scraped_without_url = []
    for event in scraped_events:
        if 'url' in event:
            scraped_by_url[event['url']] = event
        else:
            scraped_without_url.append(event)

    merged_events = []
    existing_urls_processed = set()

    for existing_event in existing_events:
        if 'url' in existing_event:
            url = existing_event['url']
            if url in scraped_by_url:
                updated_event = scraped_by_url[url].copy()
                if 'display_title' in existing_event:
                    updated_event['display_title'] = existing_event['display_title']
                merged_events.append(updated_event)
                existing_urls_processed.add(url)
            else:
                existing_event['status'] = 'removed'
                merged_events.append(existing_event)
        else:
            matching_scraped = next(
                (e for e in scraped_without_url if e['title'] == existing_event['title']),
                None
            )
            if matching_scraped:
                if 'display_title' in existing_event:
                    matching_scraped['display_title'] = existing_event['display_title']
                elif 'display_title' not in matching_scraped:
                    matching_scraped['display_title'] = matching_scraped['title']
                if existing_event.get('is_determination_event'):
                    matching_scraped['is_determination_event'] = existing_event['is_determination_event']
                merged_events.append(matching_scraped)
                scraped_without_url.remove(matching_scraped)
            else:
                if 'display_title' not in existing_event:
                    existing_event['display_title'] = existing_event['title']
                merged_events.append(existing_event)

    for url, event in scraped_by_url.items():
        if url not in existing_urls_processed:
            merged_events.append(event)

    for event in scraped_without_url:
        if 'display_title' not in event:
            event['display_title'] = event['title']
        merged_events.append(event)

    return merged_events


def _dates_within_one_day(date1, date2):
    """Return True if two ISO date strings are on the same date or one day apart.

    The ACCC website sometimes shows a determination publication date that is
    one day later than the date recorded in the events table (e.g. the page
    field says 10 April but the timeline row says 9 April).  Allowing a ±1 day
    tolerance prevents a duplicate synthetic event from being created when the
    PDF event already exists under a slightly different date.
    """
    dt1 = parse_iso_datetime(date1)
    dt2 = parse_iso_datetime(date2)
    if dt1 is None or dt2 is None:
        return date1 == date2
    return abs((dt1.date() - dt2.date()).days) <= 1


def _infer_determination_date_from_events(merger_data):
    """Set determination_publication_date from linked determination events when absent.

    The ACCC sometimes publishes the determination outcome and document links
    before populating the structured date field on the page.  When accc_determination
    is set but the HTML date field was absent, use the latest linked determination
    event's date as the publication date.

    Using the latest (not earliest) date is important for Phase 1 → Phase 2 mergers:
    both phases can have linked determination documents in the events list, and the
    Phase 2 determination is always dated after the Phase 1 referral document.
    Taking the earliest would wrongly pick the Phase 1 date in that scenario.
    """
    if not merger_data.get('accc_determination') or merger_data.get('determination_publication_date'):
        return
    det_events = [
        e for e in merger_data.get('events', [])
        if 'determination' in e.get('title', '').lower() and e.get('url')
    ]
    if det_events:
        merger_data['determination_publication_date'] = max(
            det_events, key=lambda e: e.get('date', '')
        )['date']


def _add_synthetic_events(merger_data):
    """Add notification and determination synthetic events if not already present."""
    events = merger_data['events']

    # Notification event
    if merger_data.get('effective_notification_datetime'):
        notification_title = 'Merger notified to ACCC'
        if not any(e['title'] == notification_title for e in events):
            events.append({
                'date': merger_data['effective_notification_datetime'],
                'title': notification_title,
                'display_title': notification_title,
            })

    # Determination event
    if not merger_data.get('determination_publication_date'):
        return

    determination = merger_data.get('accc_determination', 'Decision made')
    phase = merger_data.get('stage', 'Phase 1')
    determination_title = f"{phase} determination: {determination}"
    det_date = merger_data['determination_publication_date']

    # Remove old format determination events to avoid duplicates
    merger_data['events'] = [
        e for e in events
        if not (e['title'].startswith('Determination published:') and e['date'] == det_date)
    ]
    events = merger_data['events']

    # Look for an existing determination document event on the same date (or
    # ±1 day to handle cases where the ACCC publication date field and the
    # events table date differ by one day, e.g. MN-01090).
    # Also check the URL in case the event title is just the parties' names
    # while the attached PDF filename contains "determination".
    existing_det_event = next(
        (e for e in events
         if _dates_within_one_day(e.get('date'), det_date)
         and ('determination' in e.get('title', '').lower()
              or 'determination' in e.get('url', '').lower())
         and e.get('url')),
        None
    )

    if existing_det_event:
        existing_det_event['display_title'] = determination_title
        existing_det_event['is_determination_event'] = True
        if 'phase' not in existing_det_event:
            if 'waiver' in phase.lower():
                existing_det_event['phase'] = 'Waiver'
            else:
                existing_det_event['phase'] = phase.split(' - ')[0] if ' - ' in phase else phase
        # Remove any redundant plain-text status row with the same title that
        # the ACCC sometimes publishes alongside the document row.
        merger_data['events'] = [
            e for e in merger_data['events']
            if not (e['title'] == determination_title and not e.get('url'))
        ]
    else:
        if not any(e['title'] == determination_title for e in events):
            events.append({
                'date': det_date,
                'title': determination_title,
                'display_title': determination_title,
                'is_determination_event': True,
            })


def parse_merger_file(filepath, existing_merger_data=None, frozen_events_mergers=None, field_overrides=None):
    """
    Parses a single HTML file, extracts structured data for a merger,
    and downloads any new attachments found. This function is designed to be
    run in a separate process.

    Args:
        filepath (str): The path to the HTML file.
        existing_merger_data (dict or None): Existing data for the merger.
        frozen_events_mergers (set or None): Merger IDs whose events should not be updated from scraping.
        field_overrides (dict or None): Mapping of merger IDs to field-value dicts that override scraped data.

    Returns:
        dict or None: A dictionary containing the structured data for the merger,
                      or None if parsing fails.
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            html_content = f.read()

        soup = BeautifulSoup(html_content, 'lxml')

        merger_data = _extract_basic_info(soup)
        merger_id = merger_data['merger_id']

        merger_data.update(_extract_dates_and_status(soup, merger_id, existing_merger_data))
        merger_data.update(_extract_consultation_date(soup, existing_merger_data))
        merger_data.update(_extract_parties(soup))
        merger_data['anzsic_codes'] = _extract_anzsic_codes(soup)

        description = _extract_description(soup)
        if description:
            merger_data['merger_description'] = description

        scraped_events = _scrape_events(soup, merger_id, existing_merger_data)
        merger_data['events'] = _merge_events(
            scraped_events, existing_merger_data, merger_id, frozen_events_mergers
        )

        _infer_determination_date_from_events(merger_data)
        _add_synthetic_events(merger_data)

        if field_overrides and merger_id in field_overrides:
            merger_data.update(field_overrides[merger_id])

        return merger_data

    except Exception as e:
        print(f"Error processing {filepath}: {e}", file=sys.stderr)
        return None


def get_merger_id_from_file(filepath):
    """Extracts the merger ID from the HTML file using regex, avoiding a full HTML parse."""
    with open(filepath, 'r', encoding='utf-8') as f:
        html_content = f.read()
    match = re.search(
        r'field--name-dynamic-token-fieldnode-acccgov-merger-id[^>]*>.*?'
        r'class="field__item"[^>]*>.*?([A-Z]{2}-\d+)',
        html_content, re.DOTALL
    )
    return match.group(1) if match else None


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
        # Process all questionnaires in the matters directory.
        # Pre-load positive + negative caches from the last run's JSON so
        # unchanged PDFs are not re-parsed and non-questionnaire PDFs are not
        # re-opened for the content-detection fallback.
        q_cache, q_neg_cache = _build_q_caches(_Q_CACHE_PATH)
        questionnaire_data = process_all_questionnaires(
            MATTERS_DIR, cache=q_cache, neg_cache=q_neg_cache,
        )

        if not questionnaire_data:
            print("No questionnaire data found.", file=sys.stderr)
            return mergers_data

        print(f"Found {len(questionnaire_data)} questionnaires", file=sys.stderr)

        # Write questionnaire data to JSON file for reference.
        # The negative cache is serialised alongside under a reserved
        # underscore key, sorted for deterministic diffs. Downstream loaders
        # strip underscore keys before iterating.
        payload = dict(questionnaire_data)
        if q_neg_cache:
            payload[_Q_NEG_CACHE_KEY] = sorted(q_neg_cache)
        with open('data/processed/questionnaire_data.json', 'w', encoding='utf-8') as f:
            json.dump(payload, f, indent=2, sort_keys=True)
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


MISSING_EVENT_DATES_PATH = 'data/processed/missing_event_dates.json'

# Event title keywords that trigger the missing-date catch.
_CATCHABLE_EVENT_KEYWORDS = ('questionnaire', 'remedy')


def _is_catchable_event(title):
    lower = title.lower()
    return any(kw in lower for kw in _CATCHABLE_EVENT_KEYWORDS)


def auto_fix_missing_event_dates(all_mergers_data, frozen_events_mergers):
    """Detect catchable events with empty dates, set a date, and freeze the merger.

    Catchable event types: questionnaire, remedy offer (see _CATCHABLE_EVENT_KEYWORDS).

    For each merger not already frozen that has a catchable event with no date:
      1. Tries to extract the date from the event title; falls back to today at noon UTC.
      2. Adds the merger to frozen_events_mergers.json so future scrapes preserve the date.
      3. Writes issue content to MISSING_EVENT_DATES_PATH for the pipeline to create
         GitHub issues asking the user to confirm the auto-set date is correct.

    Returns a set of newly frozen merger IDs (empty set if nothing was fixed).
    """
    today = datetime.utcnow()
    today_iso = today.strftime('%Y-%m-%dT12:00:00Z')
    day = str(today.day)
    today_display = f"{day} {today.strftime('%b %Y')}"  # e.g. "6 May 2026"

    newly_frozen = []

    for merger in all_mergers_data:
        merger_id = merger.get('merger_id')
        if not merger_id or merger_id in frozen_events_mergers:
            continue

        fixed_events = []
        for event in merger.get('events', []):
            if event.get('date') not in ('', None) or not _is_catchable_event(event.get('title', '')):
                continue
            extracted_iso = parse_text_to_iso(event.get('title', ''), include_time=True)
            if extracted_iso:
                event['date'] = extracted_iso
                dt = datetime.strptime(extracted_iso, '%Y-%m-%dT%H:%M:%SZ')
                date_display = f"{dt.day} {dt.strftime('%b %Y')}"
            else:
                event['date'] = today_iso
                date_display = today_display
            fixed_events.append({
                'event_title': event.get('title', ''),
                'date_display': date_display,
                'extracted_from_title': extracted_iso is not None,
            })

        if fixed_events:
            newly_frozen.append({
                'merger_id': merger_id,
                'merger_name': merger.get('merger_name', ''),
                'fixed_events': fixed_events,
                'merger_url': merger.get('url', ''),
            })

    if not newly_frozen:
        if os.path.exists(MISSING_EVENT_DATES_PATH):
            os.remove(MISSING_EVENT_DATES_PATH)
        return set()

    # Update frozen_events_mergers.json
    try:
        with open(FROZEN_EVENTS_MERGERS_PATH, 'r', encoding='utf-8') as f:
            frozen_data = json.load(f)
    except FileNotFoundError:
        frozen_data = {
            "_comment": (
                "Override data for specific mergers. An entry with an empty dict or "
                "'freeze_events: true' preserves the existing events array rather than "
                "overwriting from the scraped page."
            )
        }

    for item in newly_frozen:
        mid = item['merger_id']
        event_summaries = ', '.join(
            f"{fe['event_title']} ({fe['date_display']})"
            for fe in item['fixed_events']
        )
        frozen_data[mid] = {
            "_comment": (
                f"Event date(s) missing from ACCC page ({event_summaries}); "
                "freezing events to preserve the automatically set date(s)."
            ),
            "freeze_events": True,
        }

    with open(FROZEN_EVENTS_MERGERS_PATH, 'w', encoding='utf-8') as f:
        json.dump(frozen_data, f, indent=2)

    # Build GitHub issue content
    _repo = "nwbort/accc-mergers"
    issues = []
    for item in newly_frozen:
        mid = item['merger_id']
        name = item['merger_name']
        url = item['merger_url']
        fixed_events = item['fixed_events']
        mergers_fyi_url = f"https://mergers.fyi/mergers/{mid}"
        frozen_json_url = f"https://github.com/{_repo}/blob/main/data/frozen_events_mergers.json"

        event_rows = ''.join(
            f"| {fe['event_title']} | {fe['date_display']} | "
            f"{'from title' if fe['extracted_from_title'] else 'today (fallback)'} |\n"
            for fe in fixed_events
        )
        body = (
            f"One or more events for **{name}** had no date on the ACCC page.\n\n"
            f"The pipeline automatically set the date(s) and froze "
            f"the merger's events to prevent future scrapes from clearing them.\n\n"
            f"### Details\n\n"
            f"| Merger | [{name}]({url}) |\n"
            f"|--------|---------------|\n"
            f"| Merger ID | `{mid}` |\n\n"
            f"### Fixed events\n\n"
            f"| Event | Date set | Source |\n"
            f"|-------|----------|--------|\n"
            f"{event_rows}\n"
            f"### Action required\n\n"
            f"Please verify the date(s) above are correct.\n\n"
            f"- If they are correct, close this issue.\n"
            f"- If any are wrong, update the date in "
            f"[`data/frozen_events_mergers.json`]({frozen_json_url}) and "
            f"`data/processed/mergers.json` with the correct value.\n\n"
            f"[View on mergers.fyi]({mergers_fyi_url})"
        )
        issues.append({
            'merger_id': mid,
            'merger_name': name,
            'title': f"Auto-fix: missing event date(s) for {name} ({mid})",
            'body': body,
        })

    with open(MISSING_EVENT_DATES_PATH, 'w', encoding='utf-8') as f:
        json.dump({'issues': issues}, f, indent=2)

    newly_frozen_ids = {item['merger_id'] for item in newly_frozen}
    print(
        f"Auto-fixed missing event date(s) for: {', '.join(sorted(newly_frozen_ids))}",
        file=sys.stderr,
    )
    return newly_frozen_ids


INFERRED_PHASE_2_PATH = 'data/processed/inferred_phase_2.json'


def detect_inferred_phase_2(all_mergers_data):
    """Detect mergers carrying a Phase 2 notice whose ACCC stage still says Phase 1.

    ``enrich_merger`` treats such mergers as Phase 2 on the site (the register
    sometimes issues a Phase 2 notice before updating the matter's stage). Because
    parties can still drop out before Phase 2 formally begins, we open a GitHub
    issue asking the owner to confirm — and auto-close it once the register's own
    stage catches up.

    Writes ``INFERRED_PHASE_2_PATH`` with two lists for the pipeline to act on:

      - ``open``:      issue content for mergers currently inferred as Phase 2
                       (notice event present, stage not yet Phase 2).
      - ``confirmed``: merger IDs whose ACCC stage now shows Phase 2 — any open
                       tracking issue for them should be closed.

    Removes the file when there is nothing to report.

    Note: this reads the *genuine* ACCC stage. The Phase 2 override lives only in
    ``enrich_merger`` (the static-data output); it is never written back to
    mergers.json, so ``merger['stage']`` here always reflects the register.
    """
    _repo = "nwbort/accc-mergers"
    to_open = []
    confirmed = []

    for merger in all_mergers_data:
        merger_id = merger.get('merger_id')
        if not merger_id:
            continue
        if not any(
            is_phase_2_referral_event(event.get('title', ''))
            for event in merger.get('events', [])
        ):
            continue

        stage = merger.get('stage') or ''
        if merger_status.PHASE_2 in stage:
            # The register has caught up — close any open tracking issue.
            confirmed.append(merger_id)
            continue

        name = merger.get('merger_name', '')
        url = merger.get('url', '')
        mergers_fyi_url = f"https://mergers.fyi/mergers/{merger_id}"
        body = (
            f"**{name}** has a Phase 2 notice on the ACCC register, but the matter's "
            f"stage still shows **Phase 1**.\n\n"
            f"The pipeline now treats this merger as **Phase 2** on mergers.fyi.\n\n"
            f"### Details\n\n"
            f"| Merger | [{name}]({url}) |\n"
            f"|--------|---------------|\n"
            f"| Merger ID | `{merger_id}` |\n"
            f"| ACCC stage | {stage or '—'} |\n\n"
            f"### Why this issue exists\n\n"
            f"Parties can still drop out before Phase 2 formally begins, so this is "
            f"an inference rather than a confirmed Phase 2.\n\n"
            f"- This issue will **close automatically** once the ACCC register updates "
            f"the stage to Phase 2.\n"
            f"- If the parties drop out and the merger never proceeds to Phase 2, close "
            f"this issue manually.\n\n"
            f"[View on mergers.fyi]({mergers_fyi_url})"
        )
        to_open.append({
            'merger_id': merger_id,
            'merger_name': name,
            'title': f"Inferred Phase 2: {name} ({merger_id})",
            'body': body,
        })

    if not to_open and not confirmed:
        if os.path.exists(INFERRED_PHASE_2_PATH):
            os.remove(INFERRED_PHASE_2_PATH)
        return

    with open(INFERRED_PHASE_2_PATH, 'w', encoding='utf-8') as f:
        json.dump({'open': to_open, 'confirmed': confirmed}, f, indent=2)

    if to_open:
        print(
            f"Inferred Phase 2 (stage not yet updated): "
            f"{', '.join(sorted(i['merger_id'] for i in to_open))}",
            file=sys.stderr,
        )
    if confirmed:
        print(
            f"ACCC stage now confirms Phase 2 (will close tracking issue): "
            f"{', '.join(sorted(confirmed))}",
            file=sys.stderr,
        )


def extract_nocc_data():
    """Parse all NOCC summary PDFs and write the standalone JSON manifest.

    Returns the parsed dict, or an empty dict on failure / when no NOCCs are
    present.
    """
    print("Extracting NOCC summary data...", file=sys.stderr)

    try:
        # Pre-load the positive cache from the last run so unchanged NOCC
        # PDFs (typically expensive — ~2s each — and rarely re-issued)
        # don't have to be re-parsed.
        nocc_cache, _ = _build_nocc_caches(_NOCC_CACHE_PATH)
        nocc_data = process_all_noccs(MATTERS_DIR, cache=nocc_cache)
    except Exception as e:
        print(f"Error extracting NOCC data: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        return {}

    if not nocc_data:
        print("No NOCC summaries found.", file=sys.stderr)
        return {}

    print(f"Found {len(nocc_data)} NOCC summary/summaries", file=sys.stderr)

    try:
        with open('data/processed/nocc_data.json', 'w', encoding='utf-8') as f:
            json.dump(nocc_data, f, indent=2, sort_keys=True)
        print("Wrote data/processed/nocc_data.json", file=sys.stderr)
    except IOError as e:
        print(f"Error writing nocc_data.json: {e}", file=sys.stderr)

    return nocc_data


def run_parse_merger_file(task):
    """Helper function to unpack arguments for parse_merger_file."""
    return parse_merger_file(*task)

def main():
    """
    Main function to find all merger HTML files, parse them in parallel,
    and print the consolidated data as JSON to stdout.
    """
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description='Extract merger data from scraped HTML files.'
    )
    parser.add_argument(
        '--all',
        action='store_true',
        help='Process all mergers, ignoring cutoff dates (by default, mergers are skipped '
             '3 weeks after an approved notification or waiver decision)'
    )
    # The pipeline splits the run in two so DOCX→PDF conversion can happen
    # between download and PDF-parse. Phase 1 sets --skip-pdf-enrich to
    # download attachments without parsing PDFs; phase 2 runs
    # scripts/enrich_pdfs.py to do the PDF parsing once DOCX files are
    # converted. Running this script without the flag keeps the original
    # end-to-end behaviour (useful for local one-shot runs).
    parser.add_argument(
        '--skip-pdf-enrich',
        action='store_true',
        help='Skip questionnaire/NOCC parsing and auto-fix; only do HTML parsing '
             'and attachment download. Used by the pipeline ahead of DOCX→PDF '
             'conversion; pair with scripts/enrich_pdfs.py for the second phase.'
    )
    args = parser.parse_args()

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


    # 2. Determine which mergers to skip based on cutoff (unless --all is passed)
    skipped_merger_ids = set()
    if not args.all:
        skipped_merger_ids = get_skipped_merger_ids(mergers_json_path)
        if skipped_merger_ids:
            print(f"Skipping {len(skipped_merger_ids)} merger(s) past cutoff date "
                  "(use --all to process all mergers)", file=sys.stderr)

    # 3. Load the frozen events merger list and any manual field overrides
    frozen_events_mergers, field_overrides = _load_frozen_events_mergers()
    if frozen_events_mergers:
        print(f"Frozen events for {len(frozen_events_mergers)} merger(s): {', '.join(sorted(frozen_events_mergers))}",
              file=sys.stderr)
    if field_overrides:
        print(f"Field overrides for {len(field_overrides)} merger(s): {', '.join(sorted(field_overrides))}",
              file=sys.stderr)

    # 4. Get a list of all HTML file paths to process
    filepaths = [
        os.path.join(MATTERS_DIR, filename)
        for filename in os.listdir(MATTERS_DIR)
        if filename.endswith(".html")
    ]

    all_mergers_data = []
    processed_merger_ids = set()

    # 5. Use a ProcessPoolExecutor to run parsing in parallel
    with ProcessPoolExecutor() as executor:
        # Create a list of arguments for parse_merger_file
        tasks = []
        for fp in filepaths:
            merger_id = get_merger_id_from_file(fp)
            if merger_id:
                # Skip mergers past cutoff unless --all is specified
                if merger_id in skipped_merger_ids:
                    continue
                tasks.append((fp, existing_mergers.get(merger_id), frozen_events_mergers, field_overrides))
                processed_merger_ids.add(merger_id)
            else:
                print(f"Warning: Could not extract merger_id from {fp}", file=sys.stderr)

        # Most tasks are now fast (cached determination data, no PDF re-parse),
        # so per-task IPC dominates with the default chunksize=1. Send tasks
        # in small batches to amortise IPC across each worker.
        worker_count = executor._max_workers or 1
        chunksize = max(1, len(tasks) // (worker_count * 4))
        results = executor.map(run_parse_merger_file, tasks, chunksize=chunksize)

        # 6. Collect valid results, filtering out any None values from failed parses
        all_mergers_data = [data for data in results if data is not None]

    # 7. Preserve skipped mergers from existing data (they remain in output unchanged)
    for merger_id in skipped_merger_ids:
        if merger_id in existing_mergers:
            all_mergers_data.append(existing_mergers[merger_id])

    if not args.skip_pdf_enrich:
        # 8. Enrich with questionnaire data (consultation deadlines)
        all_mergers_data = enrich_with_questionnaire_data(all_mergers_data)

        # 8b. Parse NOCC summary PDFs to a standalone manifest. NOCCs do not feed
        # back into per-merger fields (their date is already on the event), but
        # downstream pipelines load the manifest separately.
        extract_nocc_data()

        # 8c. Auto-fix catchable events whose date is missing on the ACCC page.
        #     Tries to extract the date from the event title; falls back to today.
        #     Freezes the merger and writes issue content for GitHub issue creation.
        auto_fix_missing_event_dates(all_mergers_data, frozen_events_mergers)

        # 8d. Detect mergers carrying a Phase 2 notice whose ACCC stage still
        #     shows Phase 1, and write tracking-issue content for the pipeline.
        detect_inferred_phase_2(all_mergers_data)

    # 9. Add is_waiver field to each merger
    for merger in all_mergers_data:
        merger['is_waiver'] = is_waiver_merger(merger)

    # 10. Sort the data by merger_id to ensure a consistent output
    all_mergers_data.sort(key=lambda x: x.get('merger_id', ''))

    # 11. Write the final JSON output to mergers.json
    with open('data/processed/mergers.json', 'w', encoding='utf-8') as f:
        json.dump(all_mergers_data, f, indent=2)

if __name__ == "__main__":
    main()
