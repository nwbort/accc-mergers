"""Tests for related-merger detection and linking.

Covers two layers:
  * ``static_data.loaders.build_relationship_map`` — turns recorded pairs into
    the per-merger relationship lookup the frontend consumes, from the
    ``{from, to, type}`` pair shape.
  * ``detect_related_mergers`` — the daily candidate detector, including the
    new "suspended assessment, re-filed later" pass.
"""

import json
import os
import sys
import unittest.mock

# Add scripts directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Mock heavy transitive imports before importing modules that need them
sys.modules.setdefault('pdfplumber', unittest.mock.MagicMock())
sys.modules.setdefault('markdownify', unittest.mock.MagicMock())
sys.modules.setdefault('requests', unittest.mock.MagicMock())

import detect_related_mergers as drm
from constants import merger_status
from static_data.loaders import build_relationship_map


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
# detector: issue rendering
# ---------------------------------------------------------------------------

def test_json_line_waiver_uses_typed_shape():
    c = {"type": drm.WAIVER_REFILED, "source": "WA-100", "target": "MN-200"}
    line = drm.json_line_for(c)
    assert '"from": "WA-100"' in line
    assert '"to": "MN-200"' in line
    assert '"type": "waiver_refiled"' in line


def test_json_line_suspended_uses_typed_shape():
    c = {"type": drm.SUSPENDED_REFILED, "source": "MN-300", "target": "MN-400"}
    line = drm.json_line_for(c)
    assert '"from": "MN-300"' in line
    assert '"to": "MN-400"' in line
    assert '"type": "suspended_refiled"' in line


def test_issue_body_describes_suspension_for_suspended_pair():
    cands = drm.find_candidates(_mergers(), known_pairs=set(), threshold=0.70)
    suspended = next(c for c in cands if c["type"] == drm.SUSPENDED_REFILED)
    body = drm.build_issue_body(suspended)
    assert "suspended" in body.lower()
    assert drm.pair_id(suspended) == "MN-300/MN-400"
