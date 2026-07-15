"""Tests for the waiver-refile tracker output (refiled-notifications.json)."""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from static_data.outputs import refiled


def _waiver(merger_id='WA-0001', notification_id='MN-0001'):
    return {
        'merger_id': merger_id,
        'merger_name': 'Some deal',
        'status': 'Assessment completed',
        'accc_determination': 'Not approved',
        'effective_notification_datetime': '2025-01-06T09:00:00Z',
        'determination_publication_date': '2025-01-20T09:00:00Z',
        'related_merger': {
            'merger_id': notification_id,
            'relationship': 'refiled_as',
            'merger_name': 'Some deal',
        },
    }


def _current_notification(merger_id='MN-0001', waiver_id='WA-0001'):
    return {
        'merger_id': merger_id,
        'merger_name': 'Some deal',
        'status': 'Under assessment',
        'effective_notification_datetime': '2025-02-01T09:00:00Z',
        'related_merger': {
            'merger_id': waiver_id,
            'relationship': 'refiled_from',
            'merger_name': 'Some deal',
        },
    }


def _completed_notification(merger_id='MN-0002', waiver_id='WA-0002', determination='Approved'):
    return {
        'merger_id': merger_id,
        'merger_name': 'Another deal',
        'status': 'Assessment completed',
        'accc_determination': determination,
        'determination_publication_date': '2025-04-01T09:00:00Z',
        'effective_notification_datetime': '2025-03-01T09:00:00Z',
        'related_merger': {
            'merger_id': waiver_id,
            'relationship': 'refiled_from',
            'merger_name': 'Another deal',
        },
    }


class TestReturnsValidShape:
    def test_empty_input(self):
        payload = refiled.generate([])
        json.dumps(payload)
        assert payload == {
            'current': [],
            'completed': [],
            'count': {'current': 0, 'completed': 0},
            'clearance_rate': {'cleared': 0, 'not_cleared': 0, 'total': 0, 'rate': None},
            'phase_duration': None,
            'straight_phase_duration': None,
        }

    def test_shape(self):
        mergers = [_waiver(), _current_notification()]
        payload = refiled.generate(mergers)
        json.dumps(payload)
        entry = payload['current'][0]
        assert set(entry.keys()) == {
            'waiver_id', 'waiver_name', 'waiver_filed_date', 'waiver_declined_date',
            'notification_id', 'notification_name', 'notification_filed_date',
            'notification_status', 'notification_determination', 'notification_determination_date',
        }


class TestCurrentVsCompleted:
    def test_pair_without_notification_determination_is_current(self):
        mergers = [_waiver(), _current_notification()]
        payload = refiled.generate(mergers)
        assert payload['count'] == {'current': 1, 'completed': 0}
        entry = payload['current'][0]
        assert entry['waiver_id'] == 'WA-0001'
        assert entry['notification_id'] == 'MN-0001'
        assert entry['notification_determination'] is None

    def test_pair_with_notification_determination_is_completed(self):
        mergers = [
            _waiver(merger_id='WA-0002', notification_id='MN-0002'),
            _completed_notification(),
        ]
        payload = refiled.generate(mergers)
        assert payload['count'] == {'current': 0, 'completed': 1}
        entry = payload['completed'][0]
        assert entry['notification_determination'] == 'Approved'
        assert entry['notification_determination_date'] == '2025-04-01T09:00:00Z'

    def test_mergers_without_related_merger_are_ignored(self):
        mergers = [{'merger_id': 'MN-9999', 'merger_name': 'Unrelated'}]
        payload = refiled.generate(mergers)
        assert payload['count'] == {'current': 0, 'completed': 0}

    def test_suspended_refiled_pairs_are_excluded(self):
        # Only waiver_refiled ("refiled_as"/"refiled_from") pairs belong on
        # this page; suspended-then-refiled matters are a different concept.
        waiver = _waiver()
        waiver['related_merger']['relationship'] = 'suspended_refiled_as'
        mergers = [waiver, _current_notification()]
        payload = refiled.generate(mergers)
        assert payload['count'] == {'current': 0, 'completed': 0}

    def test_dangling_relationship_without_matching_merger_is_ignored(self):
        mergers = [_waiver(notification_id='MN-9999')]
        payload = refiled.generate(mergers)
        assert payload['count'] == {'current': 0, 'completed': 0}


class TestClearanceRate:
    def test_no_completed_pairs(self):
        payload = refiled.generate([_waiver(), _current_notification()])
        assert payload['clearance_rate'] == {'cleared': 0, 'not_cleared': 0, 'total': 0, 'rate': None}

    def test_mixed_outcomes(self):
        mergers = [
            _waiver(merger_id='WA-0001', notification_id='MN-0001'),
            _completed_notification(merger_id='MN-0001', waiver_id='WA-0001', determination='Approved'),
            _waiver(merger_id='WA-0002', notification_id='MN-0002'),
            _completed_notification(merger_id='MN-0002', waiver_id='WA-0002', determination='Not opposed'),
            _waiver(merger_id='WA-0003', notification_id='MN-0003'),
            _completed_notification(merger_id='MN-0003', waiver_id='WA-0003', determination='Declined'),
        ]
        payload = refiled.generate(mergers)
        assert payload['clearance_rate'] == {'cleared': 2, 'not_cleared': 1, 'total': 3, 'rate': round(2 / 3, 3)}


class TestPhaseDuration:
    def test_refiled_and_straight_durations_are_kept_separate(self):
        refiled_notification = _completed_notification(merger_id='MN-0002', waiver_id='WA-0002')
        refiled_notification['phase_1_determination_date'] = '2025-04-15T09:00:00Z'
        straight_notification = {
            'merger_id': 'MN-9000',
            'merger_name': 'Straight notification',
            'status': 'Assessment completed',
            'accc_determination': 'Approved',
            'effective_notification_datetime': '2025-01-01T09:00:00Z',
            'phase_1_determination_date': '2025-01-20T09:00:00Z',
            'determination_publication_date': '2025-01-20T09:00:00Z',
        }
        mergers = [
            _waiver(merger_id='WA-0002', notification_id='MN-0002'),
            refiled_notification,
            straight_notification,
        ]
        payload = refiled.generate(mergers)
        assert payload['phase_duration']['completed_count'] == 1
        assert payload['straight_phase_duration']['completed_count'] == 1

    def test_no_completed_reviews_returns_none(self):
        payload = refiled.generate([_waiver(), _current_notification()])
        assert payload['phase_duration'] is None
        assert payload['straight_phase_duration'] is None


class TestSorting:
    def test_current_sorted_by_notification_filed_date_desc(self):
        older = _waiver(merger_id='WA-0001', notification_id='MN-0001')
        older_notif = _current_notification(merger_id='MN-0001', waiver_id='WA-0001')
        older_notif['effective_notification_datetime'] = '2025-01-01T09:00:00Z'

        newer = _waiver(merger_id='WA-0002', notification_id='MN-0002')
        newer_notif = _current_notification(merger_id='MN-0002', waiver_id='WA-0002')
        newer_notif['effective_notification_datetime'] = '2025-06-01T09:00:00Z'

        mergers = [older, older_notif, newer, newer_notif]
        payload = refiled.generate(mergers)
        assert [e['notification_id'] for e in payload['current']] == ['MN-0002', 'MN-0001']

    def test_completed_sorted_by_determination_date_desc(self):
        early = _completed_notification(merger_id='MN-0001', waiver_id='WA-0001')
        early['determination_publication_date'] = '2025-01-01T09:00:00Z'
        early_waiver = _waiver(merger_id='WA-0001', notification_id='MN-0001')

        late = _completed_notification(merger_id='MN-0002', waiver_id='WA-0002')
        late['determination_publication_date'] = '2025-09-01T09:00:00Z'
        late_waiver = _waiver(merger_id='WA-0002', notification_id='MN-0002')

        mergers = [early_waiver, early, late_waiver, late]
        payload = refiled.generate(mergers)
        assert [e['notification_id'] for e in payload['completed']] == ['MN-0002', 'MN-0001']
