import os
import json
import sys  # Import the sys module
from bs4 import BeautifulSoup
from urllib.parse import urljoin

BASE_URL = "https://www.accc.gov.au"
MATTERS_DIR = "./matters"

def parse_merger_file(filepath):
    """
    Parses a single HTML file and extracts structured data for a merger.

    Args:
        filepath (str): The path to the HTML file.

    Returns:
        dict: A dictionary containing the structured data for the merger.
    """
    # Print progress to stderr
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
    merger_data['merger_id'] = id_tag.get_text(strip=True) if id_tag else None
    
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
        if not container:
            return parties
        
        party_items = container.find_all('div', class_='paragraph--type--acccgov-trader')
        for item in party_items:
            name = item.find('span', class_='field_acccgov_name').get_text(strip=True)
            acn_span = item.find_all('span')[-1]
            acn_text = acn_span.get_text(strip=True).replace('-', '').strip()
            
            party_type = None
            number = None
            if 'ACN' in acn_text:
                party_type = 'ACN'
                number = acn_text.replace('ACN', '').strip()
            elif 'ABN' in acn_text:
                party_type = 'ABN'
                number = acn_text.replace('ABN', '').strip()
            else:
                number = acn_text

            parties.append({
                'name': name,
                'identifier_type': party_type,
                'identifier': number
            })
        return parties

    merger_data['acquirers'] = get_parties('field--name-field-acccgov-applicants')
    merger_data['targets'] = get_parties('field--name-field-acccgov-pub-reg-targets')

    # --- ANZSIC Codes ---
    merger_data['anszic_codes'] = []
    anszic_container = soup.find('div', class_='field--name-field-acquisition-anzsic-code')
    if anszic_container:
        codes = anszic_container.find_all('div', class_='field__item')
        for code in codes:
            text = code.get_text(strip=True)
            code_num, *code_name_parts = text.split()
            merger_data['anszic_codes'].append({
                'code': code_num,
                'name': ' '.join(code_name_parts)
            })

    # --- Description ---
    description_tag = soup.find('div', class_='field--name-field-accc-body')
    if description_tag:
        full_text_div = description_tag.find('div', class_='full-text')
        if full_text_div:
            merger_data['merger_description'] = full_text_div.get_text('\n', strip=True)
        else:
             merger_data['merger_description'] = description_tag.get_text('\n', strip=True).replace('Description','').strip()

    # --- Attachments ---
    merger_data['attachments'] = []
    attachment_tables = soup.find_all('div', class_='table-responsive')
    for table in attachment_tables:
        rows = table.find_all('tr')
        for row in rows:
            date_cell = row.find('td', class_='acccgov-timeline__date')
            link_cell = row.find('td', class_='acccgov-timeline__file-link')
            title_cell = next((c for c in row.find_all('td') if c not in [date_cell, link_cell]), None)

            if date_cell and title_cell and link_cell and link_cell.find('a'):
                attachment = {
                    'date': date_cell.find('time')['datetime'] if date_cell.find('time') else date_cell.get_text(strip=True),
                    'title': title_cell.get_text(strip=True),
                    'url': urljoin(BASE_URL, link_cell.find('a')['href'])
                }
                merger_data['attachments'].append(attachment)

    return merger_data

def main():
    """
    Main function to find all merger HTML files, parse them,
    and print the consolidated data as JSON to stdout.
    """
    all_mergers_data = []
    if not os.path.isdir(MATTERS_DIR):
        print(f"Error: Directory '{MATTERS_DIR}' not found.", file=sys.stderr)
        return

    for filename in os.listdir(MATTERS_DIR):
        if filename.endswith(".html"):
            filepath = os.path.join(MATTERS_DIR, filename)
            try:
                data = parse_merger_file(filepath)
                all_mergers_data.append(data)
            except Exception as e:
                print(f"Error processing {filepath}: {e}", file=sys.stderr)

    # Print the final JSON output to stdout
    print(json.dumps(all_mergers_data, indent=2))

if __name__ == "__main__":
    main()