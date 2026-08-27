"""Tests for serial-acquirer ("creeping acquisitions") detection."""

import json
import sys
import unittest.mock

# Mock heavy transitive imports before importing modules that need them
sys.modules.setdefault('pdfplumber', unittest.mock.MagicMock())
sys.modules.setdefault('markdownify', unittest.mock.MagicMock())
sys.modules.setdefault('requests', unittest.mock.MagicMock())

from scripts.generate.static_data.enrichment import enrich_merger, link_related_parties
from scripts.generate.static_data.outputs import serial_acquirers

# Real ANZSIC codes used across tests: 0600 (Coal Mining, class) rolls up to
# group 060 (also named Coal Mining); 1211 (Soft Drink Manufacturing, class)
# rolls up to group 121 (Beverage Manufacturing) — a wholly separate industry.
COAL_CLASS = {'code': '0600', 'name': 'Coal Mining'}
COAL_GROUP = {'code': '060', 'name': 'Coal Mining'}
BEVERAGE_CLASS = {'code': '1211', 'name': 'Soft Drink, Cordial and Syrup Manufacturing'}


def _notification(merger_id, acquirer_name, date, anzsic_codes=(COAL_CLASS,), is_waiver=False):
    return {
        'merger_id': merger_id,
        'merger_name': f'{acquirer_name} deal {merger_id}',
        'is_waiver': is_waiver,
        'effective_notification_datetime': date,
        'anzsic_codes': list(anzsic_codes),
        'acquirers': [{'name': acquirer_name, 'identifier': ''}],
        'targets': [{'name': 'Target Co', 'identifier': ''}],
        'other_parties': [],
    }


class TestReturnsValidShape:
    def test_empty_input(self):
        payload = serial_acquirers.generate([])
        json.dumps(payload)
        assert payload == {'acquirers': [], 'count': 0}

    def test_shape(self):
        mergers = [
            _notification('MN-0001', 'Acme Pty Ltd', '2025-01-06T09:00:00Z'),
            _notification('MN-0002', 'Acme Pty Ltd', '2025-04-06T09:00:00Z'),
        ]
        payload = serial_acquirers.generate(mergers)
        json.dumps(payload)
        assert payload['count'] == 1
        record = payload['acquirers'][0]
        assert set(record.keys()) == {
            'acquirer_name', 'canonical_id', 'anzsic_code', 'anzsic_name',
            'merger_ids', 'dates', 'count',
        }


class TestWindowDetection:
    def test_six_months_apart_is_detected(self):
        mergers = [
            _notification('MN-0001', 'Acme Pty Ltd', '2025-01-06T09:00:00Z'),
            _notification('MN-0002', 'Acme Pty Ltd', '2025-07-06T09:00:00Z'),
        ]
        payload = serial_acquirers.generate(mergers)
        assert payload['count'] == 1
        record = payload['acquirers'][0]
        assert record['count'] == 2
        assert set(record['merger_ids']) == {'MN-0001', 'MN-0002'}
        assert record['anzsic_code'] == '060'

    def test_eighteen_months_apart_is_not_detected(self):
        mergers = [
            _notification('MN-0001', 'Acme Pty Ltd', '2025-01-06T09:00:00Z'),
            _notification('MN-0002', 'Acme Pty Ltd', '2026-07-06T09:00:00Z'),
        ]
        payload = serial_acquirers.generate(mergers)
        assert payload['count'] == 0

    def test_third_filing_bridges_the_gap(self):
        # MN-0001 and MN-0003 are 18 months apart (would not qualify alone),
        # but MN-0002 sits 9 months after MN-0001 and 9 months before
        # MN-0003, so all three are part of the same creeping pattern.
        mergers = [
            _notification('MN-0001', 'Acme Pty Ltd', '2025-01-06T09:00:00Z'),
            _notification('MN-0002', 'Acme Pty Ltd', '2025-10-06T09:00:00Z'),
            _notification('MN-0003', 'Acme Pty Ltd', '2026-07-06T09:00:00Z'),
        ]
        payload = serial_acquirers.generate(mergers)
        assert payload['count'] == 1
        record = payload['acquirers'][0]
        assert record['count'] == 3
        assert set(record['merger_ids']) == {'MN-0001', 'MN-0002', 'MN-0003'}

    def test_single_notification_is_not_detected(self):
        mergers = [_notification('MN-0001', 'Acme Pty Ltd', '2025-01-06T09:00:00Z')]
        payload = serial_acquirers.generate(mergers)
        assert payload['count'] == 0


class TestAnzsicRollup:
    def test_class_and_group_tag_pair_up(self):
        # Same acquirer, one filing tagged at the class level and the other
        # at the parent group level — both roll up to group 060 and pair.
        mergers = [
            _notification('MN-0001', 'Acme Pty Ltd', '2025-01-06T09:00:00Z', anzsic_codes=(COAL_CLASS,)),
            _notification('MN-0002', 'Acme Pty Ltd', '2025-06-06T09:00:00Z', anzsic_codes=(COAL_GROUP,)),
        ]
        payload = serial_acquirers.generate(mergers)
        assert payload['count'] == 1
        assert payload['acquirers'][0]['anzsic_code'] == '060'

    def test_different_industries_do_not_pair(self):
        mergers = [
            _notification('MN-0001', 'Acme Pty Ltd', '2025-01-06T09:00:00Z', anzsic_codes=(COAL_CLASS,)),
            _notification('MN-0002', 'Acme Pty Ltd', '2025-06-06T09:00:00Z', anzsic_codes=(BEVERAGE_CLASS,)),
        ]
        payload = serial_acquirers.generate(mergers)
        assert payload['count'] == 0

    def test_unknown_anzsic_code_is_skipped(self):
        mergers = [
            _notification('MN-0001', 'Acme Pty Ltd', '2025-01-06T09:00:00Z', anzsic_codes=({'code': '9999', 'name': 'Not real'},)),
            _notification('MN-0002', 'Acme Pty Ltd', '2025-06-06T09:00:00Z', anzsic_codes=({'code': '9999', 'name': 'Not real'},)),
        ]
        payload = serial_acquirers.generate(mergers)
        assert payload['count'] == 0


class TestAcquirerMatching:
    def test_different_acquirers_do_not_pair(self):
        mergers = [
            _notification('MN-0001', 'Acme Pty Ltd', '2025-01-06T09:00:00Z'),
            _notification('MN-0002', 'Zenith Pty Ltd', '2025-06-06T09:00:00Z'),
        ]
        payload = serial_acquirers.generate(mergers)
        assert payload['count'] == 0

    def test_fallback_name_normalisation_matches_company_suffix_variants(self):
        mergers = [
            _notification('MN-0001', 'Acme Holdings Pty Ltd', '2025-01-06T09:00:00Z'),
            _notification('MN-0002', 'ACME HOLDINGS LIMITED', '2025-06-06T09:00:00Z'),
        ]
        payload = serial_acquirers.generate(mergers)
        assert payload['count'] == 1
        assert payload['acquirers'][0]['canonical_id'] is None

    def test_canonical_group_link_takes_precedence_over_name(self):
        # Two differently-named entities matched to the same canonical group
        # via related_parties.json should still pair.
        groups = [{
            'id': 'acme-group',
            'canonical_name': 'Acme Group',
            'members': [
                {'name': 'Acme Trading Pty Ltd', 'identifier': ''},
                {'name': 'Acme Subco Pty Ltd', 'identifier': ''},
            ],
        }]
        mergers = [
            enrich_merger(_notification('MN-0001', 'Acme Trading Pty Ltd', '2025-01-06T09:00:00Z')),
            enrich_merger(_notification('MN-0002', 'Acme Subco Pty Ltd', '2025-06-06T09:00:00Z')),
        ]
        link_related_parties(mergers, groups)
        payload = serial_acquirers.generate(mergers)
        assert payload['count'] == 1
        record = payload['acquirers'][0]
        assert record['canonical_id'] == 'acme-group'
        assert record['acquirer_name'] == 'Acme Group'

    def test_unnamed_acquirer_is_skipped(self):
        mergers = [
            _notification('MN-0001', '', '2025-01-06T09:00:00Z'),
            _notification('MN-0002', '', '2025-06-06T09:00:00Z'),
        ]
        payload = serial_acquirers.generate(mergers)
        assert payload['count'] == 0


class TestFiltersAndSorting:
    def test_waivers_are_excluded(self):
        mergers = [
            _notification('MN-0001', 'Acme Pty Ltd', '2025-01-06T09:00:00Z'),
            _notification('WA-0002', 'Acme Pty Ltd', '2025-06-06T09:00:00Z', is_waiver=True),
        ]
        payload = serial_acquirers.generate(mergers)
        assert payload['count'] == 0

    def test_sorted_by_count_desc_then_most_recent_date(self):
        mergers = [
            # Acme: 2 notifications, most recent 2025-06-06
            _notification('MN-0001', 'Acme Pty Ltd', '2025-01-06T09:00:00Z'),
            _notification('MN-0002', 'Acme Pty Ltd', '2025-06-06T09:00:00Z'),
            # Zenith: 3 notifications (higher count), most recent 2025-05-01
            _notification('MN-0003', 'Zenith Pty Ltd', '2025-01-01T09:00:00Z', anzsic_codes=(BEVERAGE_CLASS,)),
            _notification('MN-0004', 'Zenith Pty Ltd', '2025-03-01T09:00:00Z', anzsic_codes=(BEVERAGE_CLASS,)),
            _notification('MN-0005', 'Zenith Pty Ltd', '2025-05-01T09:00:00Z', anzsic_codes=(BEVERAGE_CLASS,)),
        ]
        payload = serial_acquirers.generate(mergers)
        assert payload['count'] == 2
        assert [r['acquirer_name'] for r in payload['acquirers']] == ['Zenith Pty Ltd', 'Acme Pty Ltd']
