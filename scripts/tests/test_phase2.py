"""Tests for the Phase 2 tracker output (phase2.json).

See docs/repo-review-specs.md #20 for the spec this implements.
"""

import json
import os
import sys
import unittest.mock

# Add scripts directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Mock heavy transitive imports before importing modules that need them
sys.modules.setdefault('pdfplumber', unittest.mock.MagicMock())
sys.modules.setdefault('markdownify', unittest.mock.MagicMock())
sys.modules.setdefault('requests', unittest.mock.MagicMock())

from static_data.enrichment import enrich_merger
from static_data.outputs import phase2


def _phase1_notification(merger_id, end_of_determination_period='2026-05-01T12:00:00Z'):
    return {
        'merger_id': merger_id,
        'merger_name': f'{merger_id} deal',
        'status': 'Under assessment',
        'stage': 'Phase 1 - preliminary assessment',
        'effective_notification_datetime': '2025-01-06T09:00:00Z',
        'end_of_determination_period': end_of_determination_period,
        'events': [
            {'title': 'Merger notified to ACCC', 'date': '2025-01-06T09:00:00Z'},
        ],
    }


def _current_phase2(merger_id, nocc_issued=True):
    events = [
        {'title': 'Merger notified to ACCC', 'date': '2025-01-06T09:00:00Z'},
        {'title': 'ACCC decided notification is subject to Phase 2 review', 'date': '2025-03-10T09:00:00Z'},
    ]
    if nocc_issued:
        events.append({'title': f'{merger_id} - Notice of competition concerns', 'date': '2025-05-01T09:00:00Z'})
    return {
        'merger_id': merger_id,
        'merger_name': f'{merger_id} deal',
        'status': 'Under assessment',
        'stage': 'Phase 2 - detailed assessment',
        'effective_notification_datetime': '2025-01-06T09:00:00Z',
        'end_of_determination_period': '2026-06-01T12:00:00Z',
        'events': events,
    }


def _completed_phase2(merger_id, determination='Approved'):
    return {
        'merger_id': merger_id,
        'merger_name': f'{merger_id} deal',
        'status': 'Determined',
        'accc_determination': determination,
        'stage': 'Phase 2 - detailed assessment',
        'effective_notification_datetime': '2025-01-06T09:00:00Z',
        'determination_publication_date': '2025-08-01T12:00:00Z',
        'end_of_determination_period': '2025-08-01T12:00:00Z',
        'events': [
            {'title': 'Merger notified to ACCC', 'date': '2025-01-06T09:00:00Z'},
            {'title': 'ACCC decided notification is subject to Phase 2 review', 'date': '2025-03-10T09:00:00Z'},
        ],
    }


def _ceased_phase2(merger_id, ceased_date='2026-06-15T12:00:00Z'):
    return {
        'merger_id': merger_id,
        'merger_name': f'{merger_id} deal',
        'status': 'Assessment ceased',
        'stage': 'Phase 2 - detailed assessment',
        'effective_notification_datetime': '2025-01-06T09:00:00Z',
        'end_of_determination_period': '2026-10-08T12:00:00Z',
        'events': [
            {'title': 'Merger notified to ACCC', 'date': '2025-01-06T09:00:00Z'},
            {'title': 'ACCC decided notification is subject to Phase 2 review', 'date': '2025-03-10T09:00:00Z'},
            {'title': 'Consideration of Notification ceased – following written request from notifying party', 'date': ceased_date},
        ],
    }


def _waiver():
    return {
        'merger_id': 'WA-0001',
        'merger_name': 'Waiver deal',
        'status': 'Determined',
        'stage': 'Waiver',
        'is_waiver': True,
        'effective_notification_datetime': '2025-01-06T09:00:00Z',
        'events': [],
    }


class TestReturnsValidShape:
    def test_empty_input(self):
        payload = phase2.generate([])
        json.dumps(payload)
        assert payload == {'current': [], 'completed': [], 'count': {'current': 0, 'completed': 0}}

    def test_shape(self):
        mergers = [enrich_merger(_current_phase2('MN-0001'))]
        payload = phase2.generate(mergers)
        json.dumps(payload)
        entry = payload['current'][0]
        assert set(entry.keys()) == {
            'merger_id', 'merger_name', 'referral_date', 'nocc_date', 'nocc_issued',
            'end_of_determination_period', 'determination', 'determination_date',
            'phase_2_inferred',
        }


class TestCurrentVsCompleted:
    def test_phase1_matter_excluded(self):
        mergers = [enrich_merger(_phase1_notification('MN-0001'))]
        payload = phase2.generate(mergers)
        assert payload['count'] == {'current': 0, 'completed': 0}

    def test_current_phase2_matter_included(self):
        mergers = [enrich_merger(_current_phase2('MN-0001'))]
        payload = phase2.generate(mergers)
        assert payload['count'] == {'current': 1, 'completed': 0}
        entry = payload['current'][0]
        assert entry['referral_date'] == '2025-03-10T09:00:00Z'
        assert entry['nocc_issued'] is True
        assert entry['nocc_date'] == '2025-05-01T09:00:00Z'
        assert entry['determination'] is None

    def test_completed_phase2_matter_included(self):
        mergers = [enrich_merger(_completed_phase2('MN-0002'))]
        payload = phase2.generate(mergers)
        assert payload['count'] == {'current': 0, 'completed': 1}
        entry = payload['completed'][0]
        assert entry['determination'] == 'Approved'
        assert entry['determination_date'] == '2025-08-01T12:00:00Z'

    def test_waivers_excluded(self):
        mergers = [enrich_merger(_waiver())]
        payload = phase2.generate(mergers)
        assert payload['count'] == {'current': 0, 'completed': 0}

    def test_ceased_phase2_matter_included_as_completed(self):
        # A ceased assessment ends the Phase 2 review without a formal
        # determination; it should surface as a completed matter rather
        # than being excluded or stuck in "current" forever.
        mergers = [enrich_merger(_ceased_phase2('MN-0003'))]
        payload = phase2.generate(mergers)
        assert payload['count'] == {'current': 0, 'completed': 1}
        entry = payload['completed'][0]
        assert entry['determination'] == 'Assessment ceased'
        assert entry['determination_date'] == '2026-06-15T12:00:00Z'


class TestNoccFallsBackToComputedDueDate:
    def test_nocc_not_yet_issued_uses_computed_due_date(self):
        mergers = [enrich_merger(_current_phase2('MN-0001', nocc_issued=False))]
        payload = phase2.generate(mergers)
        entry = payload['current'][0]
        assert entry['nocc_issued'] is False
        # competition_concerns_notice_date is computed by enrich_merger (BD 25 of Phase 2)
        assert entry['nocc_date'] is not None


class TestInferredPhase2:
    def test_inferred_matter_flagged_and_treated_as_current(self):
        merger = _phase1_notification('MN-0001')
        merger['events'].append({
            'title': 'Decision to Proceed to a Phase 2 review',
            'date': '2025-04-01T09:00:00Z',
        })
        mergers = [enrich_merger(merger)]
        payload = phase2.generate(mergers)
        assert payload['count'] == {'current': 1, 'completed': 0}
        assert payload['current'][0]['phase_2_inferred'] is True


class TestSorting:
    def test_current_sorted_by_soonest_deadline(self):
        mergers = [
            enrich_merger(_current_phase2('MN-LATE')),
            enrich_merger(_current_phase2('MN-EARLY')),
        ]
        mergers[0]['end_of_determination_period'] = '2026-12-01T12:00:00Z'
        mergers[1]['end_of_determination_period'] = '2026-01-01T12:00:00Z'
        payload = phase2.generate(mergers)
        assert [e['merger_id'] for e in payload['current']] == ['MN-EARLY', 'MN-LATE']

    def test_completed_sorted_most_recent_first(self):
        older = _completed_phase2('MN-OLD')
        older['determination_publication_date'] = '2025-01-01T12:00:00Z'
        newer = _completed_phase2('MN-NEW')
        newer['determination_publication_date'] = '2025-09-01T12:00:00Z'
        mergers = [enrich_merger(older), enrich_merger(newer)]
        payload = phase2.generate(mergers)
        assert [e['merger_id'] for e in payload['completed']] == ['MN-NEW', 'MN-OLD']
