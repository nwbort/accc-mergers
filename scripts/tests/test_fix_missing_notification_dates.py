"""Tests for fix_missing_notification_dates.py — the daily detector that
suggests freezing today's date as the default notification date for mergers
whose ACCC page never publishes one."""

import json
import os
import sys

# Add scripts directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import fix_missing_notification_dates as fmnd

TODAY = "2026-07-02T12:00:00Z"


def _merger(merger_id, name="Some Merger", url="https://accc.gov.au/x", notified=None):
    m = {"merger_id": merger_id, "merger_name": name, "url": url}
    if notified:
        m["effective_notification_datetime"] = notified
    return m


def test_finds_merger_with_no_notification_date():
    mergers = [_merger("MN-50030", "Symal Group - Shamrock")]
    candidates = fmnd.find_candidates(mergers, {}, TODAY)
    assert len(candidates) == 1
    assert candidates[0]["merger_id"] == "MN-50030"
    assert candidates[0]["date"] == TODAY


def test_ignores_merger_with_notification_date():
    mergers = [_merger("MN-00001", notified="2026-03-05T12:00:00Z")]
    assert fmnd.find_candidates(mergers, {}, TODAY) == []


def test_ignores_merger_already_in_known_dates():
    mergers = [_merger("MN-50030")]
    known_dates = {"MN-50030": {"date": "2026-07-01T12:00:00Z", "note": "already fixed"}}
    assert fmnd.find_candidates(mergers, known_dates, TODAY) == []


def test_apply_suggestions_adds_entry(tmp_path):
    known_dates = tmp_path / "known_notification_dates.json"
    candidates = [{
        "merger_id": "MN-50030",
        "merger_name": "Symal Group - Shamrock",
        "url": "https://accc.gov.au/x",
        "date": TODAY,
    }]
    added = fmnd.apply_suggestions(known_dates, candidates)
    assert added == 1
    data = json.loads(known_dates.read_text())
    assert data["MN-50030"]["date"] == TODAY
    assert "Symal Group - Shamrock" in data["MN-50030"]["note"]


def test_apply_suggestions_preserves_existing_entries(tmp_path):
    known_dates = tmp_path / "known_notification_dates.json"
    known_dates.write_text(json.dumps({
        "MN-OLD": {"date": "2026-01-01T12:00:00Z", "note": "already recorded"},
    }))
    candidates = [{
        "merger_id": "MN-50030",
        "merger_name": "Symal Group - Shamrock",
        "url": "https://accc.gov.au/x",
        "date": TODAY,
    }]
    fmnd.apply_suggestions(known_dates, candidates)
    data = json.loads(known_dates.read_text())
    assert data["MN-OLD"]["date"] == "2026-01-01T12:00:00Z"
    assert data["MN-50030"]["date"] == TODAY


def test_build_pr_body_mentions_each_candidate_and_default_date():
    candidates = [{
        "merger_id": "MN-50030",
        "merger_name": "Symal Group - Shamrock",
        "url": "https://accc.gov.au/x",
        "date": TODAY,
    }]
    body = fmnd.build_pr_body(candidates, "2026-07-02")
    assert "MN-50030" in body
    assert "Symal Group - Shamrock" in body
    assert TODAY in body
    assert "2026-07-02" in body
