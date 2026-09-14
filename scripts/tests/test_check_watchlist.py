"""Tests for the personal watchlist diff (``check_watchlist``)."""

import json

import pytest

from scripts.check_watchlist import (
    changed_watched_mergers,
    format_notification,
    main,
    parse_watched_ids,
)


def test_parse_watched_ids_splits_on_comma_and_whitespace_and_dedupes():
    assert parse_watched_ids("mn-40039, MN-45024\nmn-40039") == ["MN-40039", "MN-45024"]


def test_parse_watched_ids_empty_string_is_empty_list():
    assert parse_watched_ids("   ") == []


def test_changed_watched_mergers_detects_any_field_change():
    before = [{"merger_id": "MN-40039", "status": "Under review"}]
    after = [{"merger_id": "MN-40039", "status": "Approved"}]
    changed = changed_watched_mergers(["MN-40039"], before, after)
    assert [r["merger_id"] for r in changed] == ["MN-40039"]


def test_changed_watched_mergers_ignores_unwatched_matters():
    before = [{"merger_id": "MN-40039", "status": "Under review"}]
    after = [{"merger_id": "MN-40039", "status": "Approved"}]
    assert changed_watched_mergers(["MN-99999"], before, after) == []


def test_changed_watched_mergers_no_change_reports_nothing():
    record = {"merger_id": "MN-40039", "status": "Approved"}
    assert changed_watched_mergers(["MN-40039"], [record], [record]) == []


def test_changed_watched_mergers_missing_before_counts_as_changed():
    after = [{"merger_id": "MN-40039", "status": "Under review"}]
    changed = changed_watched_mergers(["MN-40039"], [], after)
    assert [r["merger_id"] for r in changed] == ["MN-40039"]


def test_changed_watched_mergers_missing_after_is_skipped():
    before = [{"merger_id": "MN-40039", "status": "Under review"}]
    assert changed_watched_mergers(["MN-40039"], before, []) == []


def test_format_notification_falls_back_to_id_when_name_missing():
    assert format_notification({"merger_id": "MN-40039"}) == (
        "MN-40039 (MN-40039) — https://mergers.fyi/mergers/MN-40039"
    )


def test_format_notification_includes_name_and_link():
    record = {"merger_id": "MN-40039", "merger_name": "Acme / Widgets Co"}
    assert format_notification(record) == (
        "Acme / Widgets Co (MN-40039) — https://mergers.fyi/mergers/MN-40039"
    )


@pytest.fixture
def mergers_files(tmp_path):
    before_path = tmp_path / "before.json"
    after_path = tmp_path / "after.json"
    before_path.write_text(json.dumps([{"merger_id": "MN-40039", "status": "Under review"}]))
    after_path.write_text(json.dumps([{"merger_id": "MN-40039", "status": "Approved"}]))
    return before_path, after_path


def test_main_prints_nothing_without_watchlist_env(monkeypatch, capsys, mergers_files):
    before_path, after_path = mergers_files
    monkeypatch.delenv("WATCHLIST_MATTER_IDS", raising=False)
    assert main(["--before", str(before_path), "--after", str(after_path)]) == 0
    assert capsys.readouterr().out == ""


def test_main_prints_line_when_watched_matter_changed(monkeypatch, capsys, mergers_files):
    before_path, after_path = mergers_files
    monkeypatch.setenv("WATCHLIST_MATTER_IDS", "MN-40039")
    assert main(["--before", str(before_path), "--after", str(after_path)]) == 0
    out = capsys.readouterr().out
    assert "MN-40039" in out
    assert "https://mergers.fyi/mergers/MN-40039" in out


def test_main_prints_nothing_when_watched_matter_unchanged(monkeypatch, capsys, tmp_path):
    record = {"merger_id": "MN-40039", "status": "Approved"}
    path = tmp_path / "mergers.json"
    path.write_text(json.dumps([record]))
    monkeypatch.setenv("WATCHLIST_MATTER_IDS", "MN-40039")
    assert main(["--before", str(path), "--after", str(path)]) == 0
    assert capsys.readouterr().out == ""


def test_main_missing_before_file_treats_watched_matter_as_new(monkeypatch, capsys, tmp_path):
    after_path = tmp_path / "after.json"
    after_path.write_text(json.dumps([{"merger_id": "MN-40039", "status": "Under review"}]))
    monkeypatch.setenv("WATCHLIST_MATTER_IDS", "MN-40039")
    missing_before = tmp_path / "does-not-exist.json"
    assert main(["--before", str(missing_before), "--after", str(after_path)]) == 0
    assert "MN-40039" in capsys.readouterr().out
