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
from datetime import datetime, timedelta, timezone
from markdownify import markdownify as md
from parse_determination import parse_determination_pdf
from parse_phase2_notice import parse_phase2_notice_pdf
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
from normalization import normalize_determination, normalize_dashes
from constants.site import REPO, mergers_fyi_url
from cutoff import get_skipped_merger_ids, is_waiver_merger
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
    hostname = parsed.hostname
    return (parsed.scheme in ('http', 'https')
            and hostname is not None
            and (hostname == 'accc.gov.au' or hostname.endswith('.accc.gov.au')))


def _is_determination_attachment(event_title: str | None, filename: str) -> bool:
    """Whether an attachment is a determination PDF worth parsing for a
    commission-division sentence and table content.

    The event title doesn't always say "determination" — some are titled
    with just the merger name (e.g. "Carlyle - BASF Coatings") even though
    the attached PDF plainly is one — so this also falls back to the
    attachment's own filename, which reliably does (e.g. "Foo -
    Determination - 1 Jan 2026.pdf").
    """
    if not filename.lower().endswith('.pdf'):
        return False
    if event_title and 'determination' in event_title.lower():
        return True
    return 'determination' in filename.lower()


def download_attachment(merger_id, attachment_url, event_title=None, cached_determination_data=None):
    """
    Downloads an attachment if it doesn't already exist locally.
    If it's a determination PDF, also parses it to extract commission division and table content.

    Phase 2 Notice PDFs are downloaded here too but parsed later, in the
    enrich phase (see ``extract_phase2_notice_data``) — unlike determinations,
    parsing one can require the Tesseract OCR fallback (see
    parse_phase2_notice.py), so it's kept out of this always-runs download
    path to avoid making that a hard dependency of every scrape.

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

        # Check if this is a determination PDF and parse it.
        is_determination = _is_determination_attachment(event_title, filename)

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

# Known notification dates for mergers whose ACCC page never publishes one.
# Loaded from data/known_notification_dates.json, which fix_missing_notification_dates.py
# keeps up to date via an automated PR (see .github/workflows/fix-missing-notification-dates.yml).
KNOWN_NOTIFICATION_DATES_PATH = 'data/known_notification_dates.json'


def _load_known_notification_dates():
    try:
        with open(KNOWN_NOTIFICATION_DATES_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return {
            merger_id: entry['date']
            for merger_id, entry in data.items()
            if isinstance(entry, dict) and entry.get('date')
        }
    except FileNotFoundError:
        return {}
    except Exception as e:
        print(f"Warning: could not load {KNOWN_NOTIFICATION_DATES_PATH}: {e}", file=sys.stderr)
        return {}


KNOWN_NOTIFICATION_DATES = _load_known_notification_dates()


def _parse_freeze_spec(value):
    """Interpret a frozen_events_mergers.json entry's freeze setting.

    Returns:
        True       -> freeze every event for the merger (existing behaviour).
        set[str]   -> freeze only the events whose ``title`` is in the set; all
                      other events are still merged/updated from the scraped page.
        None       -> not frozen (the entry only carries field overrides / a comment).
    """
    if not isinstance(value, dict):
        # A bare/empty value (e.g. ``{}`` shorthand) freezes all events.
        return True
    if not value:
        return True
    freeze = value.get('freeze_events')
    if isinstance(freeze, list):
        # Selective freeze: a list of event titles to preserve.
        titles = {t for t in freeze if isinstance(t, str) and t}
        return titles or None
    if freeze:
        return True
    return None


def _freeze_spec_for(frozen_events_mergers, merger_id):
    """Return the freeze spec for ``merger_id`` (True, a set of titles, or None).

    Accepts either the dict returned by :func:`_load_frozen_events_mergers`
    (merger_id -> spec) or a plain collection of merger IDs, in which case
    membership means "freeze all events" (legacy behaviour used by tests).
    """
    if not frozen_events_mergers:
        return None
    if isinstance(frozen_events_mergers, dict):
        return frozen_events_mergers.get(merger_id)
    return True if merger_id in frozen_events_mergers else None


def _load_frozen_events_mergers():
    """Load frozen-events and field-override data from frozen_events_mergers.json.

    Returns:
        tuple: (frozen_specs, field_overrides)
            frozen_specs: dict mapping merger IDs to a freeze spec. The spec is
                ``True`` to freeze every event, or a set of event titles to freeze
                only those specific events while still updating the rest from the
                scraped page. An entry with an empty dict, ``freeze_events: true``,
                or a bare value freezes all events; ``freeze_events: ["title", ...]``
                freezes only the listed events.
            field_overrides: dict mapping merger IDs to dicts of field values that should
                replace whatever the scraper finds.  Any key other than ``freeze_events``
                (and keys starting with ``_``) is treated as a field override.
    """
    try:
        with open(FROZEN_EVENTS_MERGERS_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        frozen_specs = {}
        field_overrides = {}
        for k, v in data.items():
            if k.startswith('_'):
                continue
            spec = _parse_freeze_spec(v)
            if spec is not None:
                frozen_specs[k] = spec
            if isinstance(v, dict):
                overrides = {fk: fv for fk, fv in v.items()
                             if fk != 'freeze_events' and not fk.startswith('_')}
                if overrides:
                    field_overrides[k] = overrides
        return frozen_specs, field_overrides
    except FileNotFoundError:
        return {}, {}
    except Exception as e:
        print(f"Warning: could not load {FROZEN_EVENTS_MERGERS_PATH}: {e}", file=sys.stderr)
        return {}, {}


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

    # Use known hardcoded date if the page is missing the notification date
    if not data.get('effective_notification_datetime') and merger_id in KNOWN_NOTIFICATION_DATES:
        data['effective_notification_datetime'] = KNOWN_NOTIFICATION_DATES[merger_id]

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
        if raw_determination and raw_determination != data['accc_determination']:
            data['accc_determination_raw'] = raw_determination

    # Use known hardcoded date if the page is missing the determination date
    if data.get('accc_determination') and not data.get('determination_publication_date'):
        if merger_id in KNOWN_DETERMINATION_DATES:
            data['determination_publication_date'] = KNOWN_DETERMINATION_DATES[merger_id]

    modified_meta = soup.find('meta', attrs={'name': 'dcterms.modified'})
    if modified_meta and modified_meta.has_attr('content'):
        data['page_modified_datetime'] = modified_meta['content']

    return data


# --- Consultation section: two ACCC page formats ----------------------------
#
# Old format: a free-text blurb (field_acccgov_consultation_text) stating the
# response deadline in prose, followed by a table of consultation documents
# using the same markup as the "Decisions and key events" table — so
# _scrape_events picked the questionnaire up as an ordinary attachment row.
#
# New format (rolled out page by page from Aug 2026; MN-40039 was among the
# first pages to be published with it): a structured consultation paragraph
# carrying its own header, description, status, open/closing dates and a
# questionnaire file reference. The document table is gone, so the questionnaire
# has to be read out of this section instead, and the deadline now comes from
# the "Closing date" field rather than from prose.
#
# Both formats must keep working while the rollout completes.

_CONSULTATION_HEADING = 'consultation'


def _has_class(tag, class_name):
    return tag.name == 'div' and class_name in (tag.get('class') or [])


def _class_matcher(class_name):
    return lambda tag: _has_class(tag, class_name)


def _consultation_section(soup):
    """Return the div wrapping the page's "Consultation" section, if present."""
    for heading in soup.find_all('h3', class_='border-bottom'):
        if heading.get_text(strip=True).lower() == _CONSULTATION_HEADING:
            return heading.parent
    return None


def _group_find(group, matcher):
    """First tag in ``group`` (a flat list of sibling tags) matching ``matcher``,
    searching each sibling itself and then its descendants."""
    for node in group:
        if matcher(node):
            return node
        found = node.find(matcher)
        if found:
            return found
    return None


def _group_field_time(group, field_name):
    """ISO datetime from a ``field--name-<field_name>`` field holding a <time>."""
    field = _group_find(group, _class_matcher(f'field--name-{field_name}'))
    time_tag = field.find('time') if field else None
    if time_tag and time_tag.has_attr('datetime'):
        return time_tag['datetime']
    return None


def _group_inline_field(group, label):
    """Value of a label/value pair rendered without a ``field--name-*`` class.

    The new consultation markup renders "Status" as a bare
    ``<div class="field field--label-inline">`` holding a ``field__label`` and a
    ``field__item``, so it can only be located by its label text.
    """
    def is_labelled_field(tag):
        if not _has_class(tag, 'field'):
            return False
        label_tag = tag.find('div', class_='field__label')
        return bool(label_tag) and label_tag.get_text(strip=True).lower() == label.lower()

    field = _group_find(group, is_labelled_field)
    if field is None:
        return None
    item = field.find('div', class_='field__item')
    return item.get_text(strip=True) if item else None


def _extract_consultations(soup):
    """Parse a new-format consultation section into a list of consultations.

    Each entry has ``title``, ``status``, ``open_date``, ``close_date`` and
    ``document_url`` (the questionnaire attachment, absolute).

    Returns ``[]`` for old-format pages, and for pages with no consultation at
    all — the ACCC now drops the whole section once a consultation closes,
    where it previously left behind a "the period ... has concluded" blurb.

    The section's children are flat: a consultation's fields are siblings of its
    ``<h4>`` header rather than being wrapped per consultation, so they are
    grouped by splitting the children at each header.
    """
    section = _consultation_section(soup)
    if section is None:
        return []

    groups = []
    current = None
    for child in section.children:
        if getattr(child, 'name', None) is None or child.name == 'h3':
            continue
        if child.name == 'h4':
            current = [child]
            groups.append(current)
        elif current is not None:
            current.append(child)

    consultations = []
    for group in groups:
        header = _group_find(group, _class_matcher('field--name-field-accc-header'))
        description = _group_find(
            group, _class_matcher('field--name-field-acccgov-description'))
        questionnaire = _group_find(
            group, _class_matcher('paragraph--type--acccgov-questionnaire'))
        link = questionnaire.find('a', href=True) if questionnaire else None

        consultations.append({
            'title': header.get_text(strip=True) if header else None,
            'description': description.get_text(strip=True) if description else None,
            'status': _group_inline_field(group, 'Status'),
            'open_date': _group_field_time(group, 'field-acccgov-consult-open-date'),
            'close_date': _group_field_time(group, 'field-acccgov-consult-close-date'),
            'document_url': urljoin(BASE_URL, link['href']) if link else None,
        })

    return consultations


def _extract_consultation_date(soup, existing_merger_data):
    """Extract consultation response due date, preserving existing data as fallback."""
    # New format: the closing date is a structured field. Take the latest when a
    # page carries more than one consultation, falling back to the deadline
    # stated in the consultation's own prose if the field is ever left empty.
    consultations = _extract_consultations(soup)
    close_dates = [c['close_date'] for c in consultations if c['close_date']]
    if not close_dates:
        close_dates = [
            iso for iso in (
                parse_text_to_iso(c['description'], include_time=True)
                for c in consultations if c['description']
            )
            if iso
        ]
    consultation_due_date = max(close_dates) if close_dates else None

    # Old format: the deadline is stated in prose in the consultation blurb.
    if not consultation_due_date:
        consultation_tag = soup.find('div', class_='field--name-field-acccgov-consultation-text')
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
    # The ACCC renamed this field from 'field-acquisition-anzsic-code' to
    # 'field-acccgov-anzsic-code'; accept either so we can parse old and new pages.
    container = soup.find(
        'div',
        class_=lambda c: c and (
            'field--name-field-acquisition-anzsic-code' in c
            or 'field--name-field-acccgov-anzsic-code' in c
        ),
    )
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
    (matched by attachment URL) to avoid re-parsing PDFs on every run. A
    Phase 2 Notice result computed by a previous ``extract_phase2_notice_data``
    (enrich-phase) run is carried forward the same way, but without
    triggering a re-parse here — that parse can require the OCR fallback
    (see parse_phase2_notice.py), so it's kept out of this always-runs path.
    """
    cached_determination_by_url = {}
    cached_phase2_notice_by_url = {}
    if existing_merger_data:
        for existing_event in existing_merger_data.get('events', []):
            url = existing_event.get('url')
            if not url:
                continue
            # 'determination_commission_division' is always written when a
            # determination PDF parse has previously succeeded, so use its
            # presence as the signal that we have cached data to reuse.
            if 'determination_commission_division' in existing_event:
                cached_determination_by_url[url] = {
                    'commission_division': existing_event.get('determination_commission_division'),
                    'table_content': existing_event.get('determination_table_content'),
                    'statement_of_reasons': existing_event.get('determination_statement_of_reasons'),
                }
            # 'phase2_notice_matters_to_investigate' is always written (even
            # as an empty list) once extract_phase2_notice_data has parsed
            # this event, so use its presence as the cache signal.
            if 'phase2_notice_matters_to_investigate' in existing_event:
                cached_phase2_notice_by_url[url] = {
                    'matters_to_investigate': existing_event['phase2_notice_matters_to_investigate'],
                    'commission_division': existing_event.get('phase2_notice_commission_division'),
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
                _attach_document(
                    event, merger_id, urljoin(BASE_URL, link_tag['href']),
                    cached_determination_by_url, cached_phase2_notice_by_url,
                )

            scraped_events.append(event)

    scraped_events.extend(_scrape_consultation_events(
        soup, merger_id, scraped_events,
        cached_determination_by_url, cached_phase2_notice_by_url,
    ))

    return scraped_events


def _attach_document(event, merger_id, url, cached_determination_by_url,
                     cached_phase2_notice_by_url):
    """Download ``url`` and record it (and anything parsed from it) on ``event``."""
    event['url'] = url

    determination_data = download_attachment(
        merger_id, url, event.get('title'),
        cached_determination_data=cached_determination_by_url.get(url),
    )
    if determination_data:
        event['determination_commission_division'] = determination_data.get('commission_division')
        event['determination_table_content'] = determination_data.get('table_content')
        statement = determination_data.get('statement_of_reasons')
        if statement:
            event['determination_statement_of_reasons'] = statement

    if url in cached_phase2_notice_by_url:
        cached_notice = cached_phase2_notice_by_url[url]
        event['phase2_notice_matters_to_investigate'] = cached_notice['matters_to_investigate']
        event['phase2_notice_commission_division'] = cached_notice['commission_division']

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


def _scrape_consultation_events(soup, merger_id, table_events,
                                cached_determination_by_url,
                                cached_phase2_notice_by_url):
    """Build timeline events for questionnaires held in the new consultation section.

    On old-format pages the questionnaire was a row in the consultation document
    table, which _scrape_events already picks up; on new-format pages that table
    is gone and the questionnaire hangs off the structured consultation instead
    (see _extract_consultations). Turning it back into an ordinary attachment
    event keeps the download, the DOCX→PDF conversion, questionnaire parsing and
    the frontend timeline working exactly as before.

    ``is_questionnaire_event`` marks these events as questionnaires structurally:
    the consultation header the ACCC now uses as the title does not always say
    "questionnaire" (e.g. MN-45024's "OEConnection-Epyx - Phase 1 consultation"),
    which the title-based checks downstream rely on.
    """
    already_scraped = {
        _normalize_attachment_name(e.get('url')) for e in table_events if e.get('url')
    }
    already_scraped.discard(None)

    events = []
    for consultation in _extract_consultations(soup):
        url = consultation['document_url']
        if not url:
            continue
        # A page carrying both formats at once (should not happen, but the
        # rollout is page by page) must not yield the document twice.
        if _normalize_attachment_name(url) in already_scraped:
            continue

        title = consultation['title'] or 'Questionnaire'
        event = {
            'date': consultation['open_date'] or '',
            'title': title,
            'display_title': title,
            'is_questionnaire_event': True,
        }
        _attach_document(
            event, merger_id, url,
            cached_determination_by_url, cached_phase2_notice_by_url,
        )
        events.append(event)

    return events


def _merge_events(scraped_events, existing_merger_data, merger_id, frozen_events_mergers):
    """Merge scraped events with existing events, handling frozen mergers and display_title preservation.

    ``frozen_events_mergers`` controls which existing events are protected from
    the scraped page. The spec for a merger is either ``True`` (freeze every
    event) or a set of event titles (freeze only those events, still updating the
    rest). See :func:`_load_frozen_events_mergers`.
    """
    spec = _freeze_spec_for(frozen_events_mergers, merger_id)

    if existing_merger_data and 'events' in existing_merger_data and spec is True:
        # Events are frozen: preserve existing events exactly as-is, only add genuinely new ones
        existing_urls = {e['url'] for e in existing_merger_data['events'] if 'url' in e}
        new_events = [e for e in scraped_events if e.get('url') not in existing_urls and 'url' in e]
        return existing_merger_data['events'] + new_events

    if not (existing_merger_data and 'events' in existing_merger_data):
        return scraped_events

    existing_events = existing_merger_data['events']

    # Selective freeze: keep the listed events exactly as-is. Drop the scraped
    # copies up front so they can neither overwrite (in the loop below) nor be
    # re-appended (in the trailing loops) as duplicates.
    frozen_titles = spec if isinstance(spec, (set, frozenset)) else frozenset()
    if frozen_titles:
        scraped_events = [e for e in scraped_events
                          if e.get('title') not in frozen_titles]

    existing_urls = {e['url'] for e in existing_events if 'url' in e}

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
        if existing_event.get('title') in frozen_titles:
            # Frozen event: keep the existing version verbatim (its scraped
            # counterpart was already dropped above).
            merged_events.append(existing_event)
            if 'url' in existing_event:
                existing_urls_processed.add(existing_event['url'])
            continue
        if 'url' in existing_event:
            url = existing_event['url']
            if url in scraped_by_url:
                updated_event = scraped_by_url[url].copy()
                if 'display_title' in existing_event:
                    updated_event['display_title'] = existing_event['display_title']
                merged_events.append(updated_event)
                existing_urls_processed.add(url)
            else:
                # The document link is gone from the scraped page. The ACCC
                # sometimes re-uploads the same document under a new URL (the
                # CMS appends a fresh _N suffix to the filename, e.g.
                # "...March 2026_9.pdf" -> "...March 2026_5.pdf"). Without this
                # match the existing event would be flagged 'removed' AND the
                # new URL appended as a separate event, duplicating the whole
                # timeline entry (e.g. MN-01068's Phase 2 documents). Re-bind
                # the existing event to the re-uploaded document instead.
                reuploaded = next(
                    (e for e in scraped_by_url.values()
                     if e['url'] not in existing_urls
                     and e['url'] not in existing_urls_processed
                     and _matches_existing_event(e, existing_event)),
                    None,
                )
                if reuploaded is not None:
                    updated_event = reuploaded.copy()
                    if 'display_title' in existing_event:
                        updated_event['display_title'] = existing_event['display_title']
                    if existing_event.get('is_determination_event'):
                        updated_event['is_determination_event'] = existing_event['is_determination_event']
                    merged_events.append(updated_event)
                    existing_urls_processed.add(updated_event['url'])
                    continue

                # The ACCC also sometimes drops an event's attachment but keeps
                # the event itself as a plain (URL-less) timeline row. Without
                # this match the existing event would be flagged 'removed' AND
                # the URL-less row appended as a separate event, producing a
                # duplicate that reappears on every scrape (e.g. MN-30003's
                # "subject to Phase 2 review"). Re-bind that timeline row to the
                # existing event so we keep the attachment we previously
                # captured.
                replacement_row = next(
                    (e for e in scraped_without_url
                     if _normalize_event_title(e.get('title')) == _normalize_event_title(existing_event.get('title'))
                     and _dates_within_one_day(
                         e.get('date', ''), existing_event.get('date', ''))),
                    None,
                )
                if replacement_row is not None:
                    existing_event['status'] = 'live'
                    merged_events.append(existing_event)
                    scraped_without_url.remove(replacement_row)
                else:
                    existing_event['status'] = 'removed'
                    merged_events.append(existing_event)
        else:
            matching_scraped = next(
                (e for e in scraped_without_url
                 if _normalize_event_title(e['title']) == _normalize_event_title(existing_event['title'])),
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

    return _drop_superseded_removed_events(merged_events)


def _drop_superseded_removed_events(events):
    """Drop 'removed' document events that a live event has superseded.

    Data written before re-uploaded documents were re-bound to their existing
    event (see _merge_events) can contain both a 'removed' copy of an event and
    a 'live' copy under the document's new URL. The document was never actually
    removed, so drop the stale copy, moving any flags it carried onto the live
    event.
    """
    live_url_events = [e for e in events if e.get('status') == 'live' and 'url' in e]
    kept_events = []
    for event in events:
        if event.get('status') == 'removed' and 'url' in event:
            successor = next(
                (live for live in live_url_events if _matches_existing_event(live, event)),
                None,
            )
            if successor is not None:
                if event.get('is_determination_event') and not successor.get('is_determination_event'):
                    successor['is_determination_event'] = event['is_determination_event']
                if (event.get('display_title', event['title']) != event['title']
                        and successor.get('display_title', successor['title']) == successor['title']):
                    successor['display_title'] = event['display_title']
                continue
        kept_events.append(event)
    return kept_events


def _normalize_event_title(title):
    """Whitespace-, dash-, and case-insensitive form of an event title, for
    matching the same timeline entry across scrapes (the ACCC occasionally
    re-cases titles, e.g. "Summary of Reasons" vs "Summary of reasons", or
    swaps the dash character used, e.g. an en dash '–' becoming a hyphen
    '-')."""
    return ' '.join(normalize_dashes(title or '').split()).casefold()


def _mentions_reasons(event):
    """True if an event looks like a "Summary of reasons"/"Statement of
    reasons" document rather than the determination instrument itself."""
    return 'reasons' in f"{event.get('title', '')} {event.get('url', '')}".lower()


def _same_event_identity(event_a, event_b):
    """Return True if two events describe the same timeline entry: the same
    normalized title on the same date (with the usual ±1 day tolerance)."""
    return (
        _normalize_event_title(event_a.get('title')) == _normalize_event_title(event_b.get('title'))
        and _dates_within_one_day(event_a.get('date', ''), event_b.get('date', ''))
    )


def _normalize_attachment_name(url):
    """Comparable form of an attachment's filename, or None when there isn't one.

    Strips the CMS re-upload suffix (_0, _1 …) and every non-alphanumeric
    character, so the same document still matches after the ACCC re-uploads it
    under a different directory and tweaks the spacing or punctuation of its
    name (e.g. "L'Oréal Gucci Beauty Licence -Questionnaire.docx" versus
    "L'Oréal Gucci Beauty Licence - Questionnaire_4.docx"). The extension is
    kept, so a DOCX never matches its converted PDF.
    """
    if not url:
        return None
    name = unquote(os.path.basename(urlparse(url).path)).strip()
    if not name:
        return None
    name = re.sub(r'_\d+(\.[^.]+)$', r'\1', name)
    normalized = re.sub(r'[^0-9a-z]+', '', name.casefold())
    return normalized or None


def _same_consultation_document(scraped_event, existing_event):
    """True when a consultation-section questionnaire event is the page's new
    home for an existing event's document.

    The Aug 2026 template change moved questionnaires out of the consultation
    document table and into the structured consultation section, re-uploading
    the file under /system/files/moderated_files/ and sometimes re-titling or
    re-dating the entry (e.g. MN-45024's "Questionnaire - OEConnection - Epyx"
    became "OEConnection-Epyx - Phase 1 consultation", and MN-05046's open date
    moved two days). Neither the title nor the date survives, so these events
    are matched on the attachment's own name instead. Scoped to consultation
    events so ordinary timeline documents keep their stricter title+date rule.
    """
    if not scraped_event.get('is_questionnaire_event'):
        return False
    name = _normalize_attachment_name(scraped_event.get('url'))
    return name is not None and name == _normalize_attachment_name(existing_event.get('url'))


def _matches_existing_event(scraped_event, existing_event):
    """True when a scraped event is a re-publication of an existing event."""
    return (_same_event_identity(scraped_event, existing_event)
            or _same_consultation_document(scraped_event, existing_event))


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


def _determination_pdf_precedes_registration(event_date, det_date, max_days_before=4):
    """Return True if event_date falls within max_days_before days before det_date.

    The ACCC sometimes records a determination_publication_date on the register
    page that is later than the actual decision date on the PDF event (e.g.
    MN-30008: decision made 11 Jun, registered on the page 15 Jun).  This helper
    identifies those PDF events so they can be promoted as the canonical
    determination event rather than creating a URL-less synthetic event.
    """
    dt_event = parse_iso_datetime(event_date)
    dt_det = parse_iso_datetime(det_date)
    if dt_event is None or dt_det is None:
        return False
    diff = (dt_det.date() - dt_event.date()).days  # positive when event is before det
    return 0 < diff <= max_days_before


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


def _calculate_missing_end_of_determination_period(merger_data, merger_id):
    """Calculate end_of_determination_period as effective_notification_datetime + 30 business days.

    Fallback for when the ACCC register page hasn't yet populated the field.
    Skipped for WA- (waiver) mergers which follow different rules.
    """
    if merger_data.get('end_of_determination_period'):
        return
    if (merger_id or '').startswith('WA-'):
        return
    start_dt = parse_iso_datetime(merger_data.get('effective_notification_datetime'))
    if start_dt:
        from static_data.business_days import add_business_days
        # BD 1 of the review period is the day after notification (day 0), but
        # add_business_days counts its start date as day 1 - so shift the start
        # forward one day before adding 30 business days.
        end_dt = add_business_days(start_dt + timedelta(days=1), 30)
        merger_data['end_of_determination_period'] = end_dt.strftime('%Y-%m-%dT%H:%M:%SZ')


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
    # The ACCC publishes the determination instrument alongside "Summary of
    # reasons"/"Statement of reasons" documents on the same date; attach the
    # determination outcome to the instrument itself, not its reasons.
    candidate_events = [
        e for e in events
        if _dates_within_one_day(e.get('date'), det_date)
        and ('determination' in e.get('title', '').lower()
             or 'determination' in e.get('url', '').lower())
        and e.get('url')
    ]
    existing_det_event = min(candidate_events, key=_mentions_reasons, default=None)

    # Fallback: the ACCC sometimes records a determination_publication_date that
    # is later than the actual decision date on the PDF event (e.g. MN-30008:
    # decision 11 Jun, registered on the page 15 Jun).  If no event was found
    # within ±1 day, look for a determination PDF event up to 4 days earlier.
    if not existing_det_event:
        prior_pdf_events = sorted(
            (e for e in events
             if ('determination' in e.get('title', '').lower()
                 or 'determination' in e.get('url', '').lower())
             and e.get('url')
             and _determination_pdf_precedes_registration(e.get('date'), det_date)),
            key=lambda e: (e.get('date', ''), not _mentions_reasons(e)),
            reverse=True,
        )
        if prior_pdf_events:
            existing_det_event = prior_pdf_events[0]

    if existing_det_event:
        existing_det_event['display_title'] = determination_title
        existing_det_event['is_determination_event'] = True
        # Earlier data may carry the flag on a different event (e.g. a reasons
        # document that used to be picked); clear it so exactly one event is
        # the determination event.
        for e in events:
            if e is not existing_det_event and e.get('is_determination_event'):
                del e['is_determination_event']
                if e.get('display_title') == determination_title:
                    e['display_title'] = e['title']
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
        _calculate_missing_end_of_determination_period(merger_data, merger_id)
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
    """Detect catchable events with empty dates, set a date, and freeze those events.

    Catchable event types: questionnaire, remedy offer (see _CATCHABLE_EVENT_KEYWORDS).

    For each merger not already frozen that has a catchable event with no date:
      1. Tries to extract the date from the event title; falls back to today at noon UTC.
      2. Adds a selective freeze to frozen_events_mergers.json listing only those
         specific events (``freeze_events: [title, ...]``) so future scrapes preserve
         the auto-set date(s) while every other event still updates from the page.
      3. Writes issue content to MISSING_EVENT_DATES_PATH for the pipeline to create
         GitHub issues asking the user to confirm the auto-set date is correct.

    Returns a set of newly frozen merger IDs (empty set if nothing was fixed).
    """
    today = datetime.now(timezone.utc)
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
        # Freeze only the specific events whose dates we auto-set, not the whole
        # list, so later events (e.g. a Phase 2 determination) still flow through
        # from the scraped page. Dedupe titles while preserving order.
        frozen_titles = list(dict.fromkeys(
            fe['event_title'] for fe in item['fixed_events']
        ))
        frozen_data[mid] = {
            "_comment": (
                f"Event date(s) missing from ACCC page ({event_summaries}); "
                "freezing these specific events to preserve the automatically set "
                "date(s) while other events still update from the page."
            ),
            "freeze_events": frozen_titles,
        }

    with open(FROZEN_EVENTS_MERGERS_PATH, 'w', encoding='utf-8') as f:
        json.dump(frozen_data, f, indent=2)

    # Build GitHub issue content
    issues = []
    for item in newly_frozen:
        mid = item['merger_id']
        name = item['merger_name']
        url = item['merger_url']
        fixed_events = item['fixed_events']
        fyi_url = mergers_fyi_url(mid)
        frozen_json_url = f"https://github.com/{REPO}/blob/main/data/frozen_events_mergers.json"

        event_rows = ''.join(
            f"| {fe['event_title']} | {fe['date_display']} | "
            f"{'from title' if fe['extracted_from_title'] else 'today (fallback)'} |\n"
            for fe in fixed_events
        )
        body = (
            f"One or more events for **{name}** had no date on the ACCC page.\n\n"
            f"The pipeline automatically set the date(s) and froze "
            f"those specific event(s) to prevent future scrapes from clearing them "
            f"(other events for this merger still update from the ACCC page).\n\n"
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
            f"[View on mergers.fyi]({fyi_url})"
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
        fyi_url = mergers_fyi_url(merger_id)
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
            f"[View on mergers.fyi]({fyi_url})"
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


def find_pending_phase2_notice_events(all_mergers_data):
    """Return ``(merger_id, event, local_path)`` for each Phase 2 Notice event
    that hasn't been parsed yet and whose PDF has already been downloaded.

    An event counts as already parsed once it carries
    ``phase2_notice_matters_to_investigate`` (written even as an empty list
    on a successful-but-empty parse), so a matter like Ampol-EG Australia
    is never re-parsed once it has a result.
    """
    pending = []
    for merger in all_mergers_data:
        merger_id = merger.get('merger_id')
        for event in merger.get('events', []):
            if 'phase2_notice_matters_to_investigate' in event:
                continue
            if not is_phase_2_referral_event(event.get('title', '')):
                continue
            url_gh = event.get('url_gh')
            if not url_gh or not url_gh.lower().endswith('.pdf'):
                continue
            local_path = os.path.join(MATTERS_DIR, merger_id, os.path.basename(url_gh))
            if os.path.exists(local_path):
                pending.append((merger_id, event, local_path))
    return pending


def extract_phase2_notice_data(all_mergers_data):
    """Parse pending Phase 2 Notice PDFs and attach their "matters the ACCC
    intends to investigate" boxes, and their decision-attribution sentence,
    to the corresponding event in place.

    The decision-attribution sentence is stored as
    ``phase2_notice_commission_division`` — deliberately not
    ``determination_commission_division`` — since a matter that reaches a
    final determination gets its *own* (possibly different) attribution
    from that later determination PDF, which should take precedence; this
    field only matters as a fallback for matters whose assessment is ceased
    (or otherwise never reaches a determination) after being referred to
    Phase 2.

    Run in the enrich phase (after DOCX conversion) rather than inline
    during download: some notices redact individual paragraphs by
    flattening the whole page to a picture, which needs the Tesseract OCR
    fallback in parse_phase2_notice.py, and we don't want that as a hard
    dependency of the always-runs HTML-parse/download phase.

    Returns the number of events parsed.
    """
    pending = find_pending_phase2_notice_events(all_mergers_data)
    if not pending:
        return 0

    print(f"Parsing {len(pending)} pending Phase 2 Notice PDF(s)...", file=sys.stderr)

    parsed_count = 0
    for merger_id, event, local_path in pending:
        try:
            data = parse_phase2_notice_pdf(local_path)
            event['phase2_notice_matters_to_investigate'] = data.get('matters_to_investigate', [])
            event['phase2_notice_commission_division'] = data.get('commission_division')
            parsed_count += 1
        except Exception as e:
            print(f"Error parsing Phase 2 Notice PDF for {merger_id}: {e}", file=sys.stderr)

    return parsed_count


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

        # 8b2. Parse pending Phase 2 Notice PDFs into their events.
        extract_phase2_notice_data(all_mergers_data)

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
