"""Tests for folding FOI disclosure log releases into merger timelines."""

import json

from scripts.generate.static_data.enrichment import link_foi_disclosures
from scripts.generate.static_data import loaders
from scripts.paths import REPO_ROOT


def _disclosure():
    return {
        'reference': '100473/2026-2027',
        'url': 'https://www.accc.gov.au/foi/100473',
        'published_date': '2026-10-20',
        'documents': [
            {'document': 7, 'display_title': 'Waiver application', 'file': 'Doc 7.pdf',
             'url': 'https://www.accc.gov.au/doc7.pdf'},
            {'document': 8, 'display_title': 'Part B responses', 'file': 'Doc 8.pdf',
             'url': 'https://www.accc.gov.au/doc8.pdf'},
        ],
    }


def test_documents_become_events_dated_on_publication():
    mergers = [
        {'merger_id': 'WA-80019', 'events': [{'date': '2026-06-22T12:00:00Z', 'title': 'Determination'}]},
        {'merger_id': 'WA-00001', 'events': []},
    ]
    assert link_foi_disclosures(mergers, {'WA-80019': [_disclosure()]}) == 1

    events = mergers[0]['events']
    assert len(events) == 3
    foi = events[1:]
    assert all(e['is_foi'] for e in foi)
    assert all(e['date'] == '2026-10-20T12:00:00Z' for e in foi)
    assert foi[0]['display_title'] == 'FOI release – Waiver application'
    assert foi[0]['url_gh'] == '/mergers/WA-80019/Doc 7.pdf'
    assert foi[0]['foi_reference'] == '100473/2026-2027'
    assert foi[0]['foi_document_number'] == 7
    assert mergers[0]['foi_disclosures'][0]['document_count'] == 2
    assert 'foi_disclosures' not in mergers[1]


def test_no_disclosures_is_a_no_op():
    mergers = [{'merger_id': 'WA-80019', 'events': []}]
    assert link_foi_disclosures(mergers, {}) == 0
    assert mergers[0]['events'] == []


def test_committed_overlay_files_are_mirrored():
    """Every document named in foi_disclosures.json is on disk to be served."""
    data = loaders.load_foi_disclosures()
    raw = json.loads(loaders.FOI_DISCLOSURES_JSON.read_text(encoding='utf-8'))
    assert set(data) == {k for k in raw if not k.startswith('_')}
    for merger_id, records in data.items():
        for record in records:
            assert record.get('published_date')
            for doc in record['documents']:
                assert doc.get('display_title')
                path = REPO_ROOT / 'data' / 'raw' / 'matters' / merger_id / doc['file']
                assert path.is_file(), path
