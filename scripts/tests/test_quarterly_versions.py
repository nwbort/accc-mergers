"""Tests for the quarterly report's version numbers (static_data/quarterly_versions.py)."""

import copy
import json

from scripts.generate.static_data import quarterly_versions as qv


def _payload(**q3_overrides):
    q2 = {'quarter': '2026-Q2', 'url_key': '26Q2', 'label': 'Q2 2026', 'notifications': {'filed': 95}}
    q3 = {'quarter': '2026-Q3', 'url_key': '26Q3', 'label': 'Q3 2026', 'notifications': {'filed': 113}}
    q3.update(q3_overrides)
    return {'quarters': [q2, q3]}


def test_first_sighting_is_v1_dated_today():
    payload = _payload()
    store = qv.stamp_versions(payload, {}, '2026-11-02')
    assert [(q['version'], q['version_date']) for q in payload['quarters']] == [
        (1, '2026-11-02'), (1, '2026-11-02'),
    ]
    assert list(store) == ['26Q2', '26Q3']
    assert store['26Q3'][0]['digest'] == qv.block_digest(payload['quarters'][1])


def test_unchanged_quarter_keeps_its_version_and_date():
    store = qv.stamp_versions(_payload(), {}, '2026-11-02')
    payload = _payload()
    again = qv.stamp_versions(payload, store, '2026-12-01')
    assert again == store
    assert payload['quarters'][1]['version_date'] == '2026-11-02'


def test_a_changed_quarter_moves_to_the_next_version():
    store = qv.stamp_versions(_payload(), {}, '2026-11-02')
    payload = _payload(notifications={'filed': 114})
    store = qv.stamp_versions(payload, store, '2026-11-20')
    q2, q3 = payload['quarters']
    assert (q2['version'], q2['version_date']) == (1, '2026-11-02')
    assert (q3['version'], q3['version_date']) == (2, '2026-11-20')
    assert [v['version'] for v in store['26Q3']] == [1, 2]


def test_returning_to_earlier_content_is_still_a_new_version():
    store = qv.stamp_versions(_payload(), {}, '2026-11-02')
    store = qv.stamp_versions(_payload(notifications={'filed': 114}), store, '2026-11-03')
    payload = _payload()
    qv.stamp_versions(payload, store, '2026-11-04')
    assert payload['quarters'][1]['version'] == 3


def test_digest_ignores_the_version_fields_themselves():
    payload = _payload()
    qv.stamp_versions(payload, {}, '2026-11-02')
    stamped = copy.deepcopy(payload['quarters'][1])
    assert qv.block_digest(stamped) == qv.block_digest(_payload()['quarters'][1])


def test_store_is_not_mutated():
    store = qv.stamp_versions(_payload(), {}, '2026-11-02')
    before = copy.deepcopy(store)
    qv.stamp_versions(_payload(notifications={'filed': 1}), store, '2026-11-03')
    assert store == before


def test_load_and_save_round_trip(tmp_path, monkeypatch):
    path = tmp_path / 'quarterly_versions.json'
    monkeypatch.setattr(qv, 'VERSIONS_STORE_PATH', path)
    assert qv.load_store() == {}
    payload = qv.apply_versions(_payload(), today='2026-11-02')
    assert payload['quarters'][1]['version'] == 1
    on_disk = json.loads(path.read_text())
    assert '_comment' in on_disk
    assert qv.load_store() == {k: v for k, v in on_disk.items() if k != '_comment'}
    qv.apply_versions(_payload(notifications={'filed': 2}), today='2026-11-05')
    assert qv.load_store()['26Q3'][-1] == {
        'version': 2, 'date': '2026-11-05', 'digest': qv.block_digest(_payload(notifications={'filed': 2})['quarters'][1]),
    }


def test_numbering_continues_from_a_backfilled_history():
    """Versions backfilled from the PDF's git history carry no digest; the
    next change still numbers on from the last of them."""
    backfilled = {'26Q3': [
        {'version': 1, 'date': '2026-10-23', 'digest': None, 'commit': 'f07ccbbd2'},
        {'version': 2, 'date': '2026-10-26', 'digest': None, 'commit': '574985341'},
    ]}
    payload = _payload()
    store = qv.stamp_versions(payload, backfilled, '2026-11-02')
    assert (payload['quarters'][1]['version'], payload['quarters'][1]['version_date']) == (3, '2026-11-02')
    assert store['26Q3'][:2] == backfilled['26Q3']
