"""Tests for the compact similar_mergers cards attached to each merger.

The cards are rendered by the "You might be interested in" tile in
MergerDetail.jsx and nothing else reads them, so they carry only the fields
that tile shows: the id/name for the link, up to two acquirer and target
names, and a single outcome label.
"""

import sys
import unittest.mock

# Mock heavy transitive imports before importing modules that need them
sys.modules.setdefault('pdfplumber', unittest.mock.MagicMock())
sys.modules.setdefault('markdownify', unittest.mock.MagicMock())
sys.modules.setdefault('requests', unittest.mock.MagicMock())

from scripts.generate.static_data.enrichment import link_similar_mergers


def _party(name):
    return {
        'name': name,
        'identifier_type': 'ABN',
        'identifier': '12 345 678 901',
        'party_page': {'id': name.lower().replace(' ', '-'), 'name': name},
    }


def _merger(merger_id, **overrides):
    merger = {
        'merger_id': merger_id,
        'merger_name': f'{merger_id} deal',
        'status': 'Assessment completed',
        'accc_determination': 'Approved',
        'acquirers': [_party('Buyer One'), _party('Buyer Two'), _party('Buyer Three')],
        'targets': [_party('Target One')],
        'anzsic_codes': [{'code': '1234', 'description': 'Something'}],
        'events': [{'title': 'Merger notified to ACCC', 'date': '2026-01-05T00:00:00Z'}],
    }
    merger.update(overrides)
    return merger


def test_card_carries_only_the_fields_the_tile_renders():
    mergers = [_merger('MN-0001'), _merger('MN-0002')]

    assert link_similar_mergers(mergers, {'MN-0001': ['MN-0002']}) == 1

    card = mergers[0]['similar_mergers'][0]
    assert set(card) == {'merger_id', 'merger_name', 'acquirers', 'targets', 'accc_determination'}
    assert card['merger_id'] == 'MN-0002'
    assert card['merger_name'] == 'MN-0002 deal'
    assert card['accc_determination'] == 'Approved'


def test_parties_are_bare_names_capped_at_two():
    mergers = [_merger('MN-0001'), _merger('MN-0002')]
    link_similar_mergers(mergers, {'MN-0001': ['MN-0002']})

    card = mergers[0]['similar_mergers'][0]
    assert card['acquirers'] == ['Buyer One', 'Buyer Two']
    assert card['targets'] == ['Target One']


def test_status_only_carried_when_undecided():
    undecided = _merger('MN-0002', accc_determination=None, status='Phase 1 review')
    mergers = [_merger('MN-0001'), undecided]
    link_similar_mergers(mergers, {'MN-0001': ['MN-0002']})

    card = mergers[0]['similar_mergers'][0]
    assert card['status'] == 'Phase 1 review'
    assert 'accc_determination' not in card


def test_empty_party_lists_are_omitted():
    partyless = _merger('MN-0002', acquirers=[], targets=[])
    mergers = [_merger('MN-0001'), partyless]
    link_similar_mergers(mergers, {'MN-0001': ['MN-0002']})

    card = mergers[0]['similar_mergers'][0]
    assert 'acquirers' not in card
    assert 'targets' not in card


def test_related_merger_partner_is_never_surfaced():
    mergers = [
        _merger('MN-0001', related_merger={'merger_id': 'MN-0002'}),
        _merger('MN-0002'),
        _merger('MN-0003'),
    ]

    link_similar_mergers(mergers, {'MN-0001': ['MN-0002', 'MN-0003']})

    ids = [c['merger_id'] for c in mergers[0]['similar_mergers']]
    assert ids == ['MN-0003']
