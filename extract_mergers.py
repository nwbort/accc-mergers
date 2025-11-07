import os
import json
import sys
from concurrent.futures import ProcessPoolExecutor
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, unquote
import requests

BASE_URL = "https://www.accc.gov.au"
MATTERS_DIR = "./matters"

def download_attachment(merger_id, attachment_url):
    """Downloads an attachment if it doesn't already exist locally."""
    if not merger_id or not attachment_url:
        return

    try:
        # Create a directory for the merger's attachments
        attachment_dir = os.path.join(MATTERS_DIR, merger_id)
        os.makedirs(attachment_dir, exist_ok=True)

        # Get filename from URL and construct local path
        parsed_url = urlparse(attachment_url)
        filename = unquote(os.path.basename(parsed_url.path))
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

    except requests.exceptions.RequestException as e:
        print(f"Error downloading {attachment_url}: {e}", file=sys.stderr)
    except IOError as e:
        print(f"Error saving file {local_filepath}: {e}", file=sys.stderr)


def parse_merger_file(filepath):
    """
    Parses a single HTML file, extracts structured data for a merger,
    and downloads any new attachments found. This function is designed to be
    run in a separate process.

    Args:
        filepath (str): The path to the HTML file.

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

        # --- Basic Information ---
        merger_data['merger_name'] = soup.find('h1', class_='page-title').get_text(strip=True) if soup.find('h1', class_='page-title') else None
        
        status_tag = soup.find('div', class_='field--name-field-acccgov-merger-status')
        merger_data['status'] = status_tag.get_text(strip=True) if status_tag else None

        id_tag = soup.find('div', class_='field--name-dynamic-token-fieldnode-acccgov-merger-id')
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
        
        determination_date_tag = soup.find('div', class_='field--name-field-acccgov-pub-reg-end-date')
        if determination_date_tag and determination_date_tag.find('time'):
            merger_data['determination_publication_date'] = determination_date_tag.find('time')['datetime']
            
        determination_tag = soup.find('div', class_='field--name-field-acccgov-acquisition-deter')
        if determination_tag:
            merger_data['accc_determination'] = determination_tag.get_text(strip=True).replace('ACCC Determination ','')

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

        # --- ANZSIC Codes ---
        merger_data['anszic_codes'] = []
        anszic_container = soup.find('div', class_='field--name-field-acquisition-anzsic-code')
        if anszic_container:
            for code in anszic_container.find_all('div', class_='field__item'):
                text = code.get_text(strip=True)
                code_num, *code_name_parts = text.split()
                merger_data['anszic_codes'].append({'code': code_num, 'name': ' '.join(code_name_parts)})

        # --- Description ---
        description_tag = soup.find('div', class_='field--name-field-accc-body')
        if description_tag:
            full_text_div = description_tag.find('div', class_='full-text')
            merger_data['merger_description'] = (full_text_div.get_text('\n', strip=True) if full_text_div 
                                                else description_tag.get_text('\n', strip=True).replace('Description','').strip())

        # --- Events ---
        merger_data['events'] = []
        attachment_tables = soup.find_all('div', class_='table-responsive')
        for table in attachment_tables:
            for row in table.find_all('tr'):
                date_cell = row.find('td', class_='acccgov-timeline__date')
                link_cell = row.find('td', class_='acccgov-timeline__file-link')
                title_cell = next((c for c in row.find_all('td') if c not in [date_cell, link_cell]), None)

                if not (date_cell and title_cell):
                    continue

                event = {
                    'date': date_cell.find('time')['datetime'] if date_cell.find('time') else date_cell.get_text(strip=True),
                    'title': title_cell.get_text(strip=True)
                }

                link_tag = link_cell.find('a') if link_cell else None
                if link_tag and link_tag.has_attr('href'):
                    url = urljoin(BASE_URL, link_tag['href'])
                    event['url'] = url
                    download_attachment(merger_id, url)

                merger_data['events'].append(event)

        return merger_data
    
    except Exception as e:
        print(f"Error processing {filepath}: {e}", file=sys.stderr)
        return None


def main():
    """
    Main function to find all merger HTML files, parse them in parallel,
    and print the consolidated data as JSON to stdout.
    """
    if not os.path.isdir(MATTERS_DIR):
        print(f"Error: Directory '{MATTERS_DIR}' not found.", file=sys.stderr)
        sys.exit(1)

    # 1. Get a list of all HTML file paths to process
    filepaths = [
        os.path.join(MATTERS_DIR, filename)
        for filename in os.listdir(MATTERS_DIR)
        if filename.endswith(".html")
    ]

    all_mergers_data = []
    # 2. Use a ProcessPoolExecutor to run parsing in parallel
    with ProcessPoolExecutor() as executor:
        # The map function applies parse_merger_file to each filepath
        # and returns an iterator of the results.
        results = executor.map(parse_merger_file, filepaths)
        
        # 3. Collect valid results, filtering out any None values from failed parses
        all_mergers_data = [data for data in results if data is not None]

    # 4. Sort the data by merger_id to ensure a consistent output
    all_mergers_data.sort(key=lambda x: x.get('merger_id', ''))

    # 5. Print the final JSON output to stdout
    print(json.dumps(all_mergers_data, indent=2))

if __name__ == "__main__":
    main()
