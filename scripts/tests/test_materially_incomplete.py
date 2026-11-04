"""The materially incomplete (s 51ABZ) flag: enrichment and the merger list."""

from scripts.atproto.post_bluesky import milestones
from scripts.generate.static_data.enrichment import enrich_merger
from scripts.generate.static_data.outputs.list import _lightweight

S51ABZ = (
    'In accordance with s 51ABZ of the CCA the ACCC decided that the '
    'notification lodged on 26 October 2026 should be taken not to have an '
    'effective notification date because it is materially incomplete.'
)


def _merger(**overrides) -> dict:
    m = {
        'merger_id': 'MN-55046',
        'merger_name': 'USCO – ITM',
        'status': 'Under assessment',
        'stage': 'Phase 1 - initial assessment',
        'accc_determination': None,
        'original_notification_datetime': '2026-10-26T12:00:00Z',
        'effective_notification_datetime': None,
        'determination_publication_date': None,
        'end_of_determination_period': '2026-12-07T12:00:00Z',
        'events': [
            {'date': '2026-10-26T12:00:00Z', 'title': 'Merger notified to ACCC'},
            {'date': '2026-11-04T12:00:00Z', 'title': S51ABZ},
        ],
    }
    m.update(overrides)
    return m


def test_flags_a_notification_held_materially_incomplete():
    m = enrich_merger(_merger())
    assert m['materially_incomplete'] is True
    assert m['materially_incomplete_date'] == '2026-11-04T12:00:00Z'
    assert _lightweight(m)['materially_incomplete'] is True


def test_is_a_milestone_only_while_it_lasts():
    held = enrich_merger(_merger())
    [milestone] = milestones(held)
    assert milestone.key == 'MN-55046:incomplete:2026-11-04'
    assert milestone.headline == 'Notification materially incomplete'
    # Resolved (or resolved before the milestone existed, like MN-30003):
    # nothing to announce but the notification itself.
    later = enrich_merger(_merger(effective_notification_datetime='2026-11-11T12:00:00Z'))
    assert [m.key.split(':')[1] for m in milestones(later)] == ['notified']


def test_clears_once_an_effective_date_is_set():
    # MN-30003: the parties supplied the missing information a week later.
    m = enrich_merger(_merger(effective_notification_datetime='2026-11-11T12:00:00Z'))
    assert 'materially_incomplete' not in m
    assert 'materially_incomplete' not in _lightweight(m)


def test_ignores_matters_without_the_notice():
    m = enrich_merger(_merger(events=[]))
    assert 'materially_incomplete' not in m


def test_a_suspended_assessment_is_told_by_its_status_instead():
    m = enrich_merger(_merger(status='Assessment suspended'))
    assert 'materially_incomplete' not in m
