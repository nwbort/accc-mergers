"""Tests for the trimming that separates deployed payloads from the full record.

Each generated output carries only what its consumer reads. The complete
enriched record survives in ``data/output/mergers.json``, which is what the CLI
bundle (``scripts/generate/generate-cli-data.sh``) indexes, so trimming a
deployed file never costs the CLI anything.
"""

import json
import sys
import unittest.mock

# Mock heavy transitive imports before importing modules that need them
sys.modules.setdefault('pdfplumber', unittest.mock.MagicMock())
sys.modules.setdefault('markdownify', unittest.mock.MagicMock())
sys.modules.setdefault('requests', unittest.mock.MagicMock())

from scripts.generate.static_data.enrichment import slim_for_site
from scripts.generate.static_data.outputs import individual, list as list_output, timeline
from scripts.parse.determination_text import load_records


def _party(name, canonical=None):
    party = {
        'name': name,
        'identifier_type': 'ABN',
        'identifier': '12 345 678 901',
        'party_page': {'id': 'slug', 'name': name},
    }
    if canonical:
        party['canonical'] = {'id': 'canonical-slug', 'name': canonical}
    return party


def _merger(merger_id='MN-0001', **overrides):
    merger = {
        'merger_id': merger_id,
        'merger_name': f'{merger_id} deal',
        'status': 'Assessment completed',
        'accc_determination': 'Approved',
        'accc_determination_raw': 'Approved  ',
        'page_modified_datetime': '2026-08-01T00:00:00Z',
        'public_benefits_determination': None,
        'public_benefits_determination_date': None,
        'effective_notification_datetime': '2026-01-05T00:00:00Z',
        'url': 'https://www.accc.gov.au/some-matter',
        'acquirers': [_party('Buyer One', canonical='Buyer Group')],
        'targets': [_party('Target One')],
        'other_parties': [],
        'anzsic_codes': [{'code': '1234', 'name': 'Something'}],
        'events': [
            {
                'title': 'Determination',
                'display_title': 'Phase 1 determination: Approved',
                'date': '2026-03-01T00:00:00Z',
                'url': 'https://www.accc.gov.au/doc.pdf',
                'url_gh': 'https://mergers.fyi/doc.pdf',
                'determination_commission_division': 'Division 1',
                'determination_table_content': [
                    {'item': 'Parties to the\nacquisition', 'details': 'Buyer One and Target One'},
                    {'item': 'Explanation for\ndetermination', 'details': 'The ACCC concluded...'},
                ],
            },
        ],
    }
    merger.update(overrides)
    return merger


# --- deployed per-merger detail files ---------------------------------------

def test_slim_for_site_drops_fields_no_page_reads():
    slim = slim_for_site(_merger())

    for field in ('accc_determination_raw', 'page_modified_datetime',
                  'public_benefits_determination', 'public_benefits_determination_date'):
        assert field not in slim
    assert 'determination_commission_division' not in slim['events'][0]
    assert slim['accc_determination'] == 'Approved'


def test_slim_for_site_keeps_only_the_rendered_determination_rows():
    slim = slim_for_site(_merger())

    rows = slim['events'][0]['determination_table_content']
    assert [r['item'] for r in rows] == ['Explanation for\ndetermination']
    assert rows[0]['details'] == 'The ACCC concluded...'


def test_rendered_row_matching_collapses_the_pdf_layout_newlines():
    """The label arrives from the PDF with layout newlines in it.

    DeterminationExplanationSection normalises whitespace before matching, so
    a label broken across lines must still be recognised here — matching on the
    raw string would drop the one row the page renders.
    """
    merger = _merger()
    merger['events'][0]['determination_table_content'] = [
        {'item': 'Reasons   for\n  determination', 'details': 'Because.'},
    ]

    rows = slim_for_site(merger)['events'][0]['determination_table_content']
    assert [r['details'] for r in rows] == ['Because.']


def test_determination_table_content_dropped_when_nothing_is_rendered():
    merger = _merger()
    merger['events'][0]['determination_table_content'] = [
        {'item': 'Parties to the acquisition', 'details': 'Buyer One'},
    ]

    assert 'determination_table_content' not in slim_for_site(merger)['events'][0]


def test_slim_for_site_does_not_mutate_the_input():
    merger = _merger()

    slim_for_site(merger)

    assert merger['accc_determination_raw'] == 'Approved  '
    assert len(merger['events'][0]['determination_table_content']) == 2


def test_detail_files_are_written_slimmed(tmp_path):
    individual.generate([_merger()], tmp_path)

    written = json.loads((tmp_path / 'mergers' / 'MN-0001.json').read_text())
    assert 'accc_determination_raw' not in written
    assert len(written['events'][0]['determination_table_content']) == 1


# --- paginated list pages ---------------------------------------------------

def test_list_page_parties_are_names_and_canonical_names(tmp_path):
    list_output.generate([_merger()], tmp_path)

    entry = json.loads((tmp_path / 'mergers' / 'list-page-1.json').read_text())['mergers'][0]
    assert entry['acquirers'] == [{'name': 'Buyer One', 'canonical': {'name': 'Buyer Group'}}]
    assert entry['targets'] == [{'name': 'Target One'}]
    assert entry['other_parties'] == []
    # The cards never render the ACCC register link; only the detail page does.
    assert 'url' not in entry
    # ...but the industry chips and the search index still need these.
    assert entry['anzsic_codes'] == [{'code': '1234', 'name': 'Something'}]


# --- paginated timeline pages -----------------------------------------------

def test_timeline_events_carry_only_the_mirrored_document_url(tmp_path):
    timeline.generate([_merger()], tmp_path)

    event = json.loads((tmp_path / 'timeline' / 'timeline-page-1.json').read_text())['events'][0]
    assert event['url_gh'] == 'https://mergers.fyi/doc.pdf'
    assert 'url' not in event


# --- CLI bundle source ------------------------------------------------------

def test_cli_bundle_reads_the_full_records_from_mergers_json(tmp_path):
    """The CLI's source keeps everything the deployed files drop."""
    path = tmp_path / 'mergers.json'
    path.write_text(json.dumps({'mergers': [_merger('MN-0002'), _merger('MN-0001')]}))

    records = load_records(['--mergers-json', str(path)])

    assert [r['merger_id'] for r in records] == ['MN-0001', 'MN-0002']
    assert records[0]['accc_determination_raw'] == 'Approved  '
    assert len(records[0]['events'][0]['determination_table_content']) == 2


def test_load_records_still_reads_individual_files(tmp_path):
    path = tmp_path / 'MN-0001.json'
    path.write_text(json.dumps(_merger()))

    records = load_records([str(path)])

    assert [r['merger_id'] for r in records] == ['MN-0001']
