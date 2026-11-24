"""The CLI data bundle and its version counter (scripts/generate/cli_bundle.py).

The tracked ``cli-manifest.json`` is what ``pipeline.yml`` publishes
``cli.sqlite`` on, so the property that matters most is that it changes exactly
when the bundle's content does.
"""

import hashlib
import json
from datetime import datetime, timezone

import pytest

from scripts.generate import cli_bundle

NOW = datetime(2026, 11, 24, 23, 0, 0, tzinfo=timezone.utc)


def _merger(merger_id, details='Line one\nline two.'):
    return {
        'merger_id': merger_id,
        'merger_name': f'{merger_id} – deal',
        'events': [{
            'title': 'Determination',
            'determination_table_content': [
                {'item': 'Explanation for\ndetermination', 'details': details},
            ],
        }],
    }


def _inputs(**overrides):
    inputs = {
        'mergers': [_merger('MN-0002'), _merger('MN-0001')],
        'questionnaires': {'MN-0002': {'questions_count': 1, 'deadline': 'x'}},
        'noccs': {},
        'stats': {'total_mergers': 2},
        'industries': [{'code': '1234', 'count': 2}],
    }
    inputs.update(overrides)
    return inputs


def _write(tmp_path, mode='update', **overrides):
    inputs = _inputs(**overrides)
    return cli_bundle.write(
        inputs['mergers'], inputs['questionnaires'], inputs['noccs'],
        inputs['stats'], inputs['industries'],
        mode=mode, out_dir=tmp_path, now=NOW,
    )


def _manifest(tmp_path):
    return json.loads((tmp_path / cli_bundle.MANIFEST_FILE).read_text())


def test_first_run_writes_bundle_and_manifests(tmp_path):
    result = _write(tmp_path)

    assert result.bumped and result.version == 1
    bundle_bytes = (tmp_path / cli_bundle.BUNDLE_FILE).read_bytes()
    manifest = _manifest(tmp_path)
    assert manifest == {
        'version': 1,
        'generated_at': '2026-11-24T23:00:00Z',
        'merger_count': 2,
        'bundle_sha256': hashlib.sha256(bundle_bytes).hexdigest(),
        'merger_manifest_sha256': hashlib.sha256(
            (tmp_path / cli_bundle.MERGER_MANIFEST_FILE).read_bytes()
        ).hexdigest(),
    }


def test_unchanged_content_leaves_the_manifest_alone(tmp_path):
    _write(tmp_path)
    before = (tmp_path / cli_bundle.MANIFEST_FILE).read_bytes()

    result = _write(tmp_path)

    assert not result.changed and not result.bumped and result.version == 1
    assert (tmp_path / cli_bundle.MANIFEST_FILE).read_bytes() == before
    # The bundle is still there to build cli.sqlite from.
    assert (tmp_path / cli_bundle.BUNDLE_FILE).exists()


def test_input_order_does_not_change_the_bundle(tmp_path):
    _write(tmp_path)
    result = _write(tmp_path, mergers=[_merger('MN-0001'), _merger('MN-0002')])
    assert not result.changed


def test_changed_content_bumps_the_version(tmp_path):
    _write(tmp_path)
    result = _write(tmp_path, stats={'total_mergers': 3})

    assert result.changed and result.bumped and result.version == 2
    assert _manifest(tmp_path)['version'] == 2


def test_force_bumps_without_a_change(tmp_path):
    _write(tmp_path)
    result = _write(tmp_path, mode='force')
    assert not result.changed and result.bumped and result.version == 2


def test_republish_never_touches_the_manifest(tmp_path):
    _write(tmp_path)
    before = (tmp_path / cli_bundle.MANIFEST_FILE).read_bytes()

    result = _write(tmp_path, mode='republish', stats={'total_mergers': 3})

    assert result.changed and not result.bumped and result.version == 1
    assert (tmp_path / cli_bundle.MANIFEST_FILE).read_bytes() == before
    # ...but the regenerated bundle is what gets published.
    bundle = json.loads((tmp_path / cli_bundle.BUNDLE_FILE).read_text())
    assert bundle['stats'] == {'total_mergers': 3}


def test_republish_needs_a_manifest(tmp_path):
    with pytest.raises(ValueError, match='republish'):
        _write(tmp_path, mode='republish')


def test_no_mergers_is_refused(tmp_path):
    with pytest.raises(ValueError, match='no merger records'):
        _write(tmp_path, mergers=[])
    assert not (tmp_path / cli_bundle.MANIFEST_FILE).exists()


def test_bundle_shape_and_cleaning():
    mergers = [_merger('MN-0002'), _merger('MN-0001')]
    bundle = cli_bundle.build_bundle(
        mergers,
        {'MN-0002': {'z': 1, 'a': {'y': 2, 'b': 3}}},
        {'MN-0009': {'title': 'NOCC'}},
        {'s': 1},
        [{'code': '1234'}],
    )

    assert list(bundle) == ['mergers', 'questionnaires', 'noccs', 'stats', 'industries']
    assert [m['merger_id'] for m in bundle['mergers']] == ['MN-0001', 'MN-0002']
    row = bundle['mergers'][0]['events'][0]['determination_table_content'][0]
    assert row == {'item': 'Explanation for determination', 'details': 'Line one line two.'}
    # Questionnaires and NOCCs are key-sorted at every depth.
    assert list(bundle['questionnaires']['MN-0002']) == ['a', 'z']
    assert list(bundle['questionnaires']['MN-0002']['a']) == ['b', 'y']
    # The caller's records are not cleaned in place.
    assert mergers[0]['events'][0]['determination_table_content'][0]['item'] == (
        'Explanation for\ndetermination'
    )


def test_serialisation_keeps_non_ascii_and_ends_in_a_newline():
    data = cli_bundle.serialise({'mergers': [{'merger_name': 'A – B'}]})
    assert 'A – B'.encode() in data
    assert data.endswith(b'}\n')


def test_merger_checksums_hash_each_record_on_its_own():
    record = _merger('MN-0001')
    expected = hashlib.sha256(json.dumps(record, indent=2).encode()).hexdigest()
    assert cli_bundle.merger_checksums([record, {'merger_name': 'no id'}]) == {
        'MN-0001': expected,
    }


def test_unknown_mode_is_refused(tmp_path):
    with pytest.raises(ValueError, match='unknown CLI bundle mode'):
        _write(tmp_path, mode='rebuild')
