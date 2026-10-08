"""Tests for scripts/generate/generate_rss_feed.py's entry ids."""

from scripts.generate.generate_rss_feed import collect_feed_entries


def _appeal_event(date, number):
    return {
        'date': date,
        'title': 'Notice of Address for Service',
        'display_title': 'Tribunal appeal – Notice of Address for Service',
        'appeal_base_title': 'Tribunal appeal – Notice of Address for Service',
        'is_appeal': True,
        'tribunal_number': number,
    }


def test_same_document_in_two_matters_on_one_day_gets_two_ids():
    merger = {
        'merger_id': 'MN-65005',
        'merger_name': 'IAG – RAC Insurance',
        'events': [
            _appeal_event('2026-10-05T12:00:00Z', 'ACT 3 of 2026'),
            _appeal_event('2026-10-05T12:00:00Z', 'ACT 4 of 2026'),
        ],
    }
    ids = [e['id'] for e in collect_feed_entries([merger])]
    assert len(set(ids)) == 2
    # The first keeps the id it would have had alone.
    assert 'https://mergers.fyi/mergers/MN-65005#2026-10-05T12:00:00Z-Tribunal appeal – Notice of Address for Service' in ids
    assert any(i.endswith('-ACT 4 of 2026') for i in ids)
