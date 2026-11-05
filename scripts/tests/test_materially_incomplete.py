"""The materially incomplete (s 51ABZ) flag and the recommencement that ends it."""

from scripts.atproto.post_bluesky import milestones, pending
from scripts.generate.og_cards import current_card
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
    # Resolved: the hold is over, and what is left is the notification and
    # its recommencement (``pending`` decides whether the latter is news).
    later = enrich_merger(_merger(effective_notification_datetime='2026-11-11T12:00:00Z'))
    assert [m.key.split(':')[1] for m in milestones(later)] == ['notified', 'recommenced']


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


S51ABY = (
    'USCO provided additional information in response to the ACCC’s decision '
    'under s 51ABY of the CCA. The effective notification date is 5 November 2026.'
)


def _recommenced(**overrides) -> dict:
    m = _merger(
        effective_notification_datetime='2026-11-05T12:00:00Z',
        events=[*_merger()['events'], {'date': '2026-11-05T12:00:00Z', 'title': S51ABY}],
    )
    m.update(overrides)
    return enrich_merger(m)


def test_records_when_the_assessment_recommenced():
    m = _recommenced()
    assert m['assessment_recommenced_date'] == '2026-11-05T12:00:00Z'
    assert 'materially_incomplete' not in m
    kinds = [x.key for x in milestones(m)]
    assert 'MN-55046:recommenced:2026-11-05' in kinds
    [milestone] = [x for x in milestones(m) if x.key.split(':')[1] == 'recommenced']
    assert milestone.headline == 'Assessment recommenced'


def test_no_recommencement_without_a_hold_or_while_held():
    assert 'assessment_recommenced_date' not in enrich_merger(_merger())
    plain = enrich_merger(_merger(events=[], effective_notification_datetime='2026-10-26T12:00:00Z'))
    assert 'assessment_recommenced_date' not in plain
    # An effective date older than the notice is the one the hold set aside.
    stale = enrich_merger(_merger(effective_notification_datetime='2026-10-26T12:00:00Z'))
    assert 'assessment_recommenced_date' not in stale


def _due(state: dict) -> list[str]:
    return [x.key.split(':', 1)[1] for x in pending([_recommenced()], {'posted': state})]


def test_posts_a_recommencement_after_an_earlier_notified_post():
    # MN-55046: announced on lodgement, then held, then recommenced.
    assert _due({
        'MN-55046:notified:2026-10-26': {'seeded': True},
        'MN-55046:incomplete:2026-11-04': {'seeded': True},
    }) == ['recommenced:2026-11-05']


def test_a_matter_held_before_it_was_announced_is_just_notified():
    # Never announced: the notified post is the news, and once it has gone
    # out under the recommencement's own date there is nothing more to say.
    assert _due({'MN-55046:incomplete:2026-11-04': {'seeded': True}}) == ['notified:2026-11-05']
    assert _due({
        'MN-55046:incomplete:2026-11-04': {'seeded': True},
        'MN-55046:notified:2026-11-05': {'seeded': True},
    }) == []


def test_a_recommenced_matter_shows_its_card():
    assert current_card(_recommenced()) == 'assessment-recommenced.png'
