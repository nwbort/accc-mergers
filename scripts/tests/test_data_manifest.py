"""Tests for scripts/generate/data_manifest.py."""

import hashlib
import json

import pytest

from scripts.generate.data_manifest import (
    FORMAT,
    build_manifest,
    file_hash,
    main,
    write_manifest,
)


def _data_dir(tmp_path, files, phase2_current=(), industries=None):
    mergers = tmp_path / "mergers"
    mergers.mkdir()
    for name, body in files.items():
        (mergers / name).write_bytes(body)
    (tmp_path / "industries").mkdir()
    for name, body in (industries or {}).items():
        (tmp_path / "industries" / name).write_bytes(body)
    (tmp_path / "phase2.json").write_text(
        json.dumps({"current": [{"merger_id": m} for m in phase2_current], "completed": []})
    )
    return tmp_path


def test_file_hash_is_pinned():
    # The Android app recomputes this from its cached copy (data/Manifest.kt in
    # nwbort/accc-mergers-app, which pins the same value): change both or neither.
    body = '{"merger_id":"MN-01016","merger_name":"Asahi – Warehouse"}'.encode()
    assert file_hash(body) == "5161c4b975b1"
    assert file_hash(body) == hashlib.sha256(body).hexdigest()[:12]


def test_hashes_every_detail_file_and_nothing_else(tmp_path):
    data = _data_dir(tmp_path, {
        "MN-01016.json": b'{"a":1}',
        "WA-01087.json": b'{"b":2}',
        "list.json": b'{"mergers":[]}',
    })
    manifest = build_manifest(data)
    assert manifest["format"] == FORMAT
    assert manifest["mergers"] == {
        "MN-01016": file_hash(b'{"a":1}'),
        "WA-01087": file_hash(b'{"b":2}'),
    }


def test_hash_follows_the_bytes(tmp_path):
    data = _data_dir(tmp_path, {"MN-01016.json": b'{"a":1}'})
    before = build_manifest(data)["mergers"]["MN-01016"]
    (data / "mergers" / "MN-01016.json").write_bytes(b'{"a":2}')
    assert build_manifest(data)["mergers"]["MN-01016"] != before


def test_hashes_every_industry_division_file(tmp_path):
    data = _data_dir(
        tmp_path, {"MN-01016.json": b"{}"},
        industries={"G.json": b'{"division":"G"}', "_orphans.json": b"{}"},
    )
    assert build_manifest(data)["industries"] == {
        "G": file_hash(b'{"division":"G"}'),
        "_orphans": file_hash(b"{}"),
    }


def test_phase2_current_ids(tmp_path):
    data = _data_dir(tmp_path, {"MN-01072.json": b"{}"}, phase2_current=["MN-01072", "MN-65005"])
    assert build_manifest(data)["phase2_current"] == ["MN-01072", "MN-65005"]


def test_writes_compact_json(tmp_path, capsys):
    data = _data_dir(tmp_path, {"MN-01016.json": b"{}"})
    main([str(data)])
    text = (data / "manifest.json").read_text()
    assert "\n" not in text and ": " not in text
    assert json.loads(text)["mergers"] == {"MN-01016": file_hash(b"{}")}
    assert "Wrote" in capsys.readouterr().out


def test_refuses_to_write_an_empty_manifest(tmp_path):
    data = _data_dir(tmp_path, {})
    with pytest.raises(SystemExit):
        write_manifest(data)
    assert not (data / "manifest.json").exists()
