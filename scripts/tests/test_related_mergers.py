"""Tests for related-merger detection and linking.

Covers two layers:
  * ``static_data.loaders.build_relationship_map`` — turns recorded pairs into
    the per-merger relationship lookup the frontend consumes, from the
    ``{from, to, type}`` pair shape.
  * ``detect_related_mergers`` — the daily candidate detector, including the
    new "suspended assessment, re-filed later" pass.
"""

import json
import sys
import unittest.mock

# Mock heavy transitive imports before importing modules that need them
sys.modules.setdefault('pdfplumber', unittest.mock.MagicMock())
sys.modules.setdefault('markdownify', unittest.mock.MagicMock())
sys.modules.setdefault('requests', unittest.mock.MagicMock())

from scripts.detect import detect_related_mergers as drm
from scripts.constants import merger_status
from scripts.generate.static_data.loaders import build_relationship_map


# ---------------------------------------------------------------------------
# build_relationship_map
# ---------------------------------------------------------------------------

def test_waiver_pair_maps_to_waiver_relationships():
    data = {"pairs": [{"from": "WA-100", "to": "MN-200", "type": "waiver_refiled"}]}
    result = build_relationship_map(data)
    assert result["WA-100"] == {"merger_id": "MN-200", "relationship": "refiled_as"}
    assert result["MN-200"] == {"merger_id": "WA-100", "relationship": "refiled_from"}


def test_pair_without_type_defaults_to_waiver_relationships():
    data = {"pairs": [{"from": "WA-100", "to": "MN-200"}]}
    result = build_relationship_map(data)
    assert result["WA-100"]["relationship"] == "refiled_as"
    assert result["MN-200"]["relationship"] == "refiled_from"


def test_legacy_pair_shape_is_ignored():
    # The old {waiver, notification} shape is no longer supported.
    data = {"pairs": [{"waiver": "WA-100", "notification": "MN-200"}]}
    assert build_relationship_map(data) == {}


def test_suspended_pair_shape_maps_to_suspended_relationships():
    data = {"pairs": [{"from": "MN-300", "to": "MN-400", "type": "suspended_refiled"}]}
    result = build_relationship_map(data)
    assert result["MN-300"] == {
        "merger_id": "MN-400",
        "relationship": "suspended_refiled_as",
    }
    assert result["MN-400"] == {
        "merger_id": "MN-300",
        "relationship": "suspended_refiled_from",
    }


def test_incomplete_pairs_are_skipped():
    data = {"pairs": [{"from": "MN-300"}, {"to": "MN-400"}, {}]}
    assert build_relationship_map(data) == {}


def test_unknown_type_falls_back_to_waiver_labels():
    data = {"pairs": [{"from": "MN-1", "to": "MN-2", "type": "future_thing"}]}
    result = build_relationship_map(data)
    assert result["MN-1"]["relationship"] == "refiled_as"


# ---------------------------------------------------------------------------
# detector: load_related_pairs (both schema shapes)
# ---------------------------------------------------------------------------

def test_load_related_pairs_parses_typed_shape(tmp_path):
    path = tmp_path / "related_mergers.json"
    path.write_text(json.dumps({"pairs": [
        {"from": "WA-100", "to": "MN-200", "type": "waiver_refiled"},
        {"from": "MN-300", "to": "MN-400", "type": "suspended_refiled"},
        {"from": "MN-9"},  # incomplete — ignored
        {"waiver": "WA-1", "notification": "MN-2"},  # legacy shape — ignored
    ]}))
    assert drm.load_related_pairs(path) == {("WA-100", "MN-200"), ("MN-300", "MN-400")}


def test_load_related_pairs_missing_file_returns_empty(tmp_path):
    assert drm.load_related_pairs(tmp_path / "nope.json") == set()


# ---------------------------------------------------------------------------
# detector: candidate detection
# ---------------------------------------------------------------------------

def _entity(name, identifier):
    return {"name": name, "identifier": identifier}


def _mergers():
    """A declined waiver/notification pair and a suspended/refile pair."""
    return [
        {
            "merger_id": "WA-100",
            "merger_name": "Alpha / Beta waiver",
            "accc_determination": "Not approved",
            "status": merger_status.ASSESSMENT_COMPLETED,
            "effective_notification_datetime": "2025-01-01T00:00:00Z",
            "acquirers": [_entity("Alpha Pty Ltd", "ABN-1")],
            "targets": [_entity("Beta Pty Ltd", "ABN-2")],
        },
        {
            "merger_id": "MN-200",
            "merger_name": "Alpha / Beta notification",
            "accc_determination": None,
            "status": merger_status.UNDER_ASSESSMENT,
            "effective_notification_datetime": "2025-03-01T00:00:00Z",
            "acquirers": [_entity("Alpha Pty Ltd", "ABN-1")],
            "targets": [_entity("Beta Pty Ltd", "ABN-2")],
        },
        {
            "merger_id": "MN-300",
            "merger_name": "Gamma / Delta",
            "accc_determination": None,
            "status": merger_status.ASSESSMENT_SUSPENDED,
            "effective_notification_datetime": "2025-02-01T00:00:00Z",
            "acquirers": [_entity("Gamma Pty Ltd", "ABN-3")],
            "targets": [_entity("Delta Pty Ltd", "ABN-4")],
        },
        {
            "merger_id": "MN-400",
            "merger_name": "Gamma / Delta refiled",
            "accc_determination": None,
            "status": merger_status.UNDER_ASSESSMENT,
            "effective_notification_datetime": "2025-05-01T00:00:00Z",
            "acquirers": [_entity("Gamma Pty Ltd", "ABN-3")],
            "targets": [_entity("Delta Pty Ltd", "ABN-4")],
        },
    ]


def test_detects_waiver_pair():
    cands = drm.find_candidates(_mergers(), known_pairs=set(), threshold=0.70)
    waiver = next(c for c in cands if c["type"] == drm.WAIVER_REFILED)
    assert (waiver["source"], waiver["target"]) == ("WA-100", "MN-200")
    assert waiver["score"] == 1.0


def test_detects_suspended_pair():
    cands = drm.find_candidates(_mergers(), known_pairs=set(), threshold=0.70)
    suspended = next(c for c in cands if c["type"] == drm.SUSPENDED_REFILED)
    assert (suspended["source"], suspended["target"]) == ("MN-300", "MN-400")
    assert suspended["score"] == 1.0


def test_suspended_pass_never_links_a_merger_to_itself():
    cands = drm.find_suspended_candidates(_mergers(), known_pairs=set(), threshold=0.70)
    assert all(c["source"] != c["target"] for c in cands)


def test_known_pairs_are_excluded():
    cands = drm.find_candidates(
        _mergers(), known_pairs={("MN-300", "MN-400")}, threshold=0.70
    )
    assert all(c["type"] != drm.SUSPENDED_REFILED for c in cands)


def test_soft_date_ordering_rejects_earlier_refile():
    mergers = _mergers()
    # Move the refile to *before* the suspension — should no longer be paired.
    for m in mergers:
        if m["merger_id"] == "MN-400":
            m["effective_notification_datetime"] = "2024-01-01T00:00:00Z"
    cands = drm.find_suspended_candidates(mergers, known_pairs=set(), threshold=0.70)
    assert cands == []


# ---------------------------------------------------------------------------
# detector: applying suggestions to related_mergers.json
# ---------------------------------------------------------------------------

def test_apply_suggestions_appends_typed_pairs(tmp_path):
    path = tmp_path / "related_mergers.json"
    path.write_text(json.dumps({
        "_README": "doc",
        "pairs": [{"from": "WA-1", "to": "MN-2", "type": "waiver_refiled"}],
    }))
    cands = drm.find_candidates(_mergers(), known_pairs=set(), threshold=0.70)
    added = drm.apply_suggestions(path, cands)
    assert added == len(cands)

    data = json.loads(path.read_text())
    # Original pair preserved, candidates appended.
    assert {"from": "WA-1", "to": "MN-2", "type": "waiver_refiled"} in data["pairs"]
    assert {"from": "WA-100", "to": "MN-200", "type": "waiver_refiled"} in data["pairs"]
    assert {"from": "MN-300", "to": "MN-400", "type": "suspended_refiled"} in data["pairs"]
    # _README is retained.
    assert data["_README"] == "doc"
    # Re-reading the written pairs round-trips through the loader.
    assert ("WA-100", "MN-200") in drm.load_related_pairs(path)


def test_apply_suggestions_creates_file_when_missing(tmp_path):
    path = tmp_path / "nested" / "related_mergers.json"
    cands = drm.find_candidates(_mergers(), known_pairs=set(), threshold=0.70)
    drm.apply_suggestions(path, cands)
    data = json.loads(path.read_text())
    assert len(data["pairs"]) == len(cands)


def test_write_related_mergers_keeps_compact_one_line_pairs(tmp_path):
    path = tmp_path / "related_mergers.json"
    drm.write_related_mergers(path, {
        "_README": "doc",
        "pairs": [{"from": "WA-1", "to": "MN-2", "type": "waiver_refiled"}],
    })
    text = path.read_text()
    assert '    { "from": "WA-1", "to": "MN-2", "type": "waiver_refiled" }' in text


# ---------------------------------------------------------------------------
# detector: PR body rendering
# ---------------------------------------------------------------------------

def test_pr_body_describes_suspension_for_suspended_pair():
    cands = drm.find_candidates(_mergers(), known_pairs=set(), threshold=0.70)
    suspended = next(c for c in cands if c["type"] == drm.SUSPENDED_REFILED)
    body = drm.build_pr_body([suspended], "2026-01-01")
    assert "suspended" in body.lower()
    assert "MN-300" in body and "MN-400" in body
    assert drm.pair_id(suspended) == "MN-300/MN-400"


def test_pr_body_notes_auto_merge_when_requested():
    cands = drm.find_candidates(_mergers(), known_pairs=set(), threshold=0.70)
    waiver = next(c for c in cands if c["type"] == drm.WAIVER_REFILED)
    body = drm.build_pr_body([waiver], "2026-01-01", auto_merge=True)
    assert "merged automatically" in body.lower()


# ---------------------------------------------------------------------------
# detector: exact-match auto-merge gate
# ---------------------------------------------------------------------------

def _waiver_candidate(**overrides):
    base = {
        "type": drm.WAIVER_REFILED,
        "source": "WA-1",
        "target": "MN-1",
        "source_name": "Alpha / Beta waiver",
        "target_name": "Alpha / Beta notification",
        "source_filed": "2025-01-01T00:00:00Z",
        "target_filed": "2025-03-01T00:00:00Z",
        "source_determination": "Not approved",
        "source_status": "Assessment completed",
        "target_status": "Under assessment",
        "score": 0.75,
        "signals": {
            "acq_id_overlap": False,
            "tgt_id_overlap": False,
            "acq_name_sim": 1.0,
            "tgt_name_sim": 1.0,
            "merger_name_sim": 1.0,
        },
    }
    base.update(overrides)
    return base


def test_is_certain_match_requires_all_three_name_sims_exact():
    assert drm.is_certain_match(_waiver_candidate())


def test_is_certain_match_rejects_partial_merger_name_match():
    cand = _waiver_candidate()
    cand["signals"]["merger_name_sim"] = 0.9
    assert not drm.is_certain_match(cand)


def test_is_certain_match_rejects_suspended_refiled_type():
    cand = _waiver_candidate(type=drm.SUSPENDED_REFILED)
    assert not drm.is_certain_match(cand)


def test_issue_body_lists_certain_pairs():
    body = drm.build_issue_body([_waiver_candidate()], "2026-01-01")
    assert "WA-1" in body and "MN-1" in body
    assert "exact (100%) name match" in body


def _exact_match_mergers():
    """A waiver/notification pair with identical names on every side."""
    return [
        {
            "merger_id": "WA-100",
            "merger_name": "Alpha Beta deal",
            "accc_determination": "Not approved",
            "status": merger_status.ASSESSMENT_COMPLETED,
            "effective_notification_datetime": "2025-01-01T00:00:00Z",
            "acquirers": [_entity("Alpha Pty Ltd", "ABN-1")],
            "targets": [_entity("Beta Pty Ltd", "ABN-2")],
        },
        {
            "merger_id": "MN-200",
            "merger_name": "Alpha Beta deal",
            "accc_determination": None,
            "status": merger_status.UNDER_ASSESSMENT,
            "effective_notification_datetime": "2025-03-01T00:00:00Z",
            "acquirers": [_entity("Alpha Pty Ltd", "ABN-9")],
            "targets": [_entity("Beta Pty Ltd", "ABN-8")],
        },
    ]


def test_main_writes_meta_and_issue_markdown_for_all_certain_batch(tmp_path, monkeypatch):
    mergers_path = tmp_path / "mergers.json"
    mergers_path.write_text(json.dumps(_exact_match_mergers()))
    related_path = tmp_path / "related_mergers.json"
    pr_path = tmp_path / "pr_body.md"
    issue_path = tmp_path / "pr_issue_body.md"
    meta_path = tmp_path / "pr_meta.json"

    monkeypatch.setattr(sys, "argv", [
        "detect_related_mergers.py",
        "--mergers", str(mergers_path),
        "--related", str(related_path),
        "--pr-markdown", str(pr_path),
        "--issue-markdown", str(issue_path),
        "--meta-json", str(meta_path),
    ])
    exit_code = drm.main()
    assert exit_code == 1

    meta = json.loads(meta_path.read_text())
    assert meta == {"count": 1, "certain_count": 1, "all_certain": True}
    assert "merged automatically" in pr_path.read_text().lower()
    assert "WA-100" in issue_path.read_text()


def test_main_skips_issue_markdown_when_not_all_certain(tmp_path, monkeypatch):
    mergers_path = tmp_path / "mergers.json"
    mergers_path.write_text(json.dumps(_mergers()))
    related_path = tmp_path / "related_mergers.json"
    pr_path = tmp_path / "pr_body.md"
    issue_path = tmp_path / "pr_issue_body.md"
    meta_path = tmp_path / "pr_meta.json"

    monkeypatch.setattr(sys, "argv", [
        "detect_related_mergers.py",
        "--mergers", str(mergers_path),
        "--related", str(related_path),
        "--pr-markdown", str(pr_path),
        "--issue-markdown", str(issue_path),
        "--meta-json", str(meta_path),
    ])
    exit_code = drm.main()
    assert exit_code == 1

    meta = json.loads(meta_path.read_text())
    assert meta["all_certain"] is False
    assert not issue_path.exists()
