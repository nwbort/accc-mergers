"""Tests for fix_missing_notification_dates.py — the daily detector that
suggests freezing today's date as the default notification date for mergers
whose ACCC page never publishes one."""

import json

from scripts import fix_missing_notification_dates as fmnd

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


# --- Carrying a suggestion forward across runs ---------------------------
#
# The fix branch is rebuilt from main on every pipeline run, so without the
# --previous-known-dates carry-forward every still-unreviewed candidate would be
# re-dated to today on each run — the guess drifting away from the day the
# merger was actually first seen without a date.

LATER = "2026-07-09T12:00:00Z"

PREVIOUS = {
    "MN-50030": {
        "date": TODAY,
        "note": "Symal Group - Shamrock: notification date missing from ACCC page "
                "as of 2026-07-02; confirm and correct if wrong.",
    },
}


def test_carries_previous_date_instead_of_re_dating_to_today():
    mergers = [_merger("MN-50030", "Symal Group - Shamrock")]
    candidates = fmnd.find_candidates(mergers, {}, LATER, PREVIOUS)
    assert len(candidates) == 1
    assert candidates[0]["date"] == TODAY
    assert candidates[0]["carried_entry"] == PREVIOUS["MN-50030"]


def test_new_candidate_alongside_a_carried_one_still_gets_today():
    mergers = [_merger("MN-50030", "Symal Group - Shamrock"), _merger("MN-60001", "New One")]
    by_id = {c["merger_id"]: c for c in fmnd.find_candidates(mergers, {}, LATER, PREVIOUS)}
    assert by_id["MN-50030"]["date"] == TODAY
    assert by_id["MN-60001"]["date"] == LATER
    assert by_id["MN-60001"]["carried_entry"] is None


def test_carried_entry_is_written_back_verbatim(tmp_path):
    """A date (or note) a human corrected on the branch survives the next run."""
    corrected = {"date": "2026-06-28T12:00:00Z", "note": "confirmed from questionnaire"}
    known_dates = tmp_path / "known_notification_dates.json"
    candidates = fmnd.find_candidates(
        [_merger("MN-50030", "Symal Group - Shamrock")], {}, LATER, {"MN-50030": corrected}
    )
    fmnd.apply_suggestions(known_dates, candidates)
    assert json.loads(known_dates.read_text())["MN-50030"] == corrected


def test_malformed_previous_entry_falls_back_to_today():
    for junk in ({"MN-50030": {"note": "no date"}}, {"MN-50030": "not a dict"}, {"MN-50030": None}):
        candidates = fmnd.find_candidates([_merger("MN-50030")], {}, LATER, junk)
        assert candidates[0]["date"] == LATER
        assert candidates[0]["carried_entry"] is None


def test_previous_suggestions_already_merged_into_main_are_not_re_suggested():
    """Once the PR lands, the merger is in known_dates and drops out entirely —
    the previous-run copy must not resurrect it."""
    mergers = [_merger("MN-50030")]
    assert fmnd.find_candidates(mergers, {"MN-50030": PREVIOUS["MN-50030"]}, LATER, PREVIOUS) == []


def test_load_previous_suggestions_tolerates_absent_empty_and_junk(tmp_path):
    assert fmnd.load_previous_suggestions(None) == {}
    assert fmnd.load_previous_suggestions(tmp_path / "nope.json") == {}

    empty = tmp_path / "empty.json"
    empty.write_text("")
    assert fmnd.load_previous_suggestions(empty) == {}

    junk = tmp_path / "junk.json"
    junk.write_text("{not json")
    assert fmnd.load_previous_suggestions(junk) == {}

    good = tmp_path / "good.json"
    good.write_text(json.dumps(PREVIOUS))
    assert fmnd.load_previous_suggestions(good) == PREVIOUS


def test_pr_body_flags_carried_dates_and_keeps_plain_wording_without_them():
    carried = fmnd.find_candidates(
        [_merger("MN-50030", "Symal Group - Shamrock")], {}, LATER, PREVIOUS
    )
    body = fmnd.build_pr_body(carried, "2026-07-09")
    assert TODAY in body
    assert "carried over" in body

    fresh = fmnd.find_candidates([_merger("MN-60001", "New One")], {}, LATER)
    fresh_body = fmnd.build_pr_body(fresh, "2026-07-09")
    assert "carried over" not in fresh_body
