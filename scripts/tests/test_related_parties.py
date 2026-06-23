"""Tests for related-party detection, matching and linking.

Covers three layers:
  * ``party_matching`` — normalisation and the group lookup/match logic shared by
    the detector and the static-data pipeline.
  * ``static_data.enrichment.link_related_parties`` — attaching the ``canonical``
    link to each party that belongs to a recorded group.
  * ``detect_related_parties`` — the daily candidate detector.
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

import detect_related_parties as drp
import party_matching as pm
from static_data.enrichment import link_related_parties


# ---------------------------------------------------------------------------
# party_matching
# ---------------------------------------------------------------------------

def test_normalise_name_strips_company_suffixes():
    assert pm.normalise_name("COLES GROUP LIMITED") == "coles"
    assert pm.normalise_name("Coles Supermarkets Australia Pty Ltd") == "coles supermarkets"


def test_normalise_identifier_strips_spaces_and_punctuation():
    assert pm.normalise_identifier("45 004 189 708") == "45004189708"
    assert pm.normalise_identifier("CBN  764228300") == "CBN764228300"
    assert pm.normalise_identifier("") == ""


def test_build_group_lookups_indexes_by_name_and_identifier():
    groups = [{
        "id": "coles",
        "canonical_name": "Coles Group",
        "members": [
            {"name": "COLES GROUP LIMITED", "identifier": "11 004 089 936"},
            {"name": "COLES SUPERMARKETS AUSTRALIA PTY LTD", "identifier": ""},
        ],
    }]
    by_id, by_name = pm.build_group_lookups(groups)
    assert by_id["11004089936"]["id"] == "coles"
    assert by_name["coles"]["id"] == "coles"
    assert by_name["coles supermarkets"]["id"] == "coles"


def test_match_party_prefers_identifier_then_name():
    groups = [{
        "id": "coles",
        "canonical_name": "Coles Group",
        "members": [{"name": "COLES GROUP LIMITED", "identifier": "11 004 089 936"}],
    }]
    by_id, by_name = pm.build_group_lookups(groups)
    # Matches on ABN even when the name differs
    assert pm.match_party(
        {"name": "Coles (renamed) Pty Ltd", "identifier": "11 004 089 936"}, by_id, by_name
    )["id"] == "coles"
    # Matches on normalised name when no identifier given
    assert pm.match_party(
        {"name": "COLES GROUP LIMITED", "identifier": ""}, by_id, by_name
    )["id"] == "coles"
    # No match
    assert pm.match_party({"name": "Woolworths", "identifier": ""}, by_id, by_name) is None


# ---------------------------------------------------------------------------
# enrichment.link_related_parties
# ---------------------------------------------------------------------------

def test_link_related_parties_attaches_canonical():
    mergers = [
        {
            "merger_id": "MN-1",
            "acquirers": [{"name": "COLES GROUP LIMITED", "identifier": "11 004 089 936"}],
            "targets": [{"name": "Someone Else Pty Ltd", "identifier": "99 999 999 999"}],
        },
        {
            "merger_id": "MN-2",
            "acquirers": [{"name": "Coles Supermarkets Australia Pty Ltd", "identifier": ""}],
            "targets": [],
        },
    ]
    groups = [{
        "id": "coles",
        "canonical_name": "Coles Group",
        "members": [
            {"name": "COLES GROUP LIMITED", "identifier": "11 004 089 936"},
            {"name": "COLES SUPERMARKETS AUSTRALIA PTY LTD", "identifier": ""},
        ],
    }]
    linked = link_related_parties(mergers, groups)
    assert linked == 2
    assert mergers[0]["acquirers"][0]["canonical"] == {"id": "coles", "name": "Coles Group"}
    assert "canonical" not in mergers[0]["targets"][0]
    assert mergers[1]["acquirers"][0]["canonical"]["id"] == "coles"


def test_link_related_parties_no_groups_is_noop():
    mergers = [{"merger_id": "MN-1", "acquirers": [{"name": "A", "identifier": "1"}]}]
    assert link_related_parties(mergers, []) == 0
    assert "canonical" not in mergers[0]["acquirers"][0]


# ---------------------------------------------------------------------------
# detect_related_parties
# ---------------------------------------------------------------------------

def _merger(mid, acquirers=None, targets=None, other=None):
    return {
        "merger_id": mid,
        "acquirers": acquirers or [],
        "targets": targets or [],
        "other_parties": other or [],
    }


def test_detects_identifier_collision():
    # Same ABN, two different names -> one entity recorded under two names.
    mergers = [
        _merger("MN-1", acquirers=[{"name": "Old Name Pty Ltd", "identifier": "12 345 678 901"}]),
        _merger("MN-2", acquirers=[{"name": "New Name Pty Ltd", "identifier": "12 345 678 901"}]),
    ]
    candidates = drp.find_candidates(mergers, [])
    assert len(candidates) == 1
    c = candidates[0]
    assert c["signal"] == "identifier"
    assert c["score"] == 0.95
    assert {m["name"] for m in c["members"]} == {"Old Name Pty Ltd", "New Name Pty Ltd"}


def test_detects_name_collision_with_differing_identifier_formats():
    # Same name, the same registration number recorded two different ways: one
    # entity, distinct on-record identities worth linking.
    mergers = [
        _merger("MN-1", targets=[{"name": "Eli Lilly and Company", "identifier": "IRS Number 350470950"}]),
        _merger("MN-2", targets=[{"name": "Eli Lilly and Company", "identifier": "350470950 (IRS)"}]),
    ]
    candidates = drp.find_candidates(mergers, [])
    assert len(candidates) == 1
    assert candidates[0]["signal"] == "name"


def test_identical_name_differing_only_by_missing_identifier_is_skipped():
    # Same display name, one record just missing its ABN: searching the name
    # already finds both, so there's nothing to link.
    mergers = [
        _merger("MN-1", targets=[{"name": "Eli Lilly and Company", "identifier": "350470950"}]),
        _merger("MN-2", targets=[{"name": "Eli Lilly and Company", "identifier": ""}]),
    ]
    assert drp.find_candidates(mergers, []) == []


def test_existing_group_members_are_excluded():
    mergers = [
        _merger("MN-1", acquirers=[{"name": "Old Name Pty Ltd", "identifier": "12 345 678 901"}]),
        _merger("MN-2", acquirers=[{"name": "New Name Pty Ltd", "identifier": "12 345 678 901"}]),
    ]
    groups = [{
        "id": "existing",
        "canonical_name": "Existing",
        "members": [{"name": "Old Name Pty Ltd", "identifier": "12 345 678 901"}],
    }]
    assert drp.find_candidates(mergers, groups) == []


def test_sibling_spvs_not_grouped_without_fuzzy():
    # Distinct names + distinct ABNs: only the (off-by-default) fuzzy pass could
    # link these, and it shouldn't run by default.
    mergers = [
        _merger("MN-1", acquirers=[{"name": "Swan Bidco Pty Ltd", "identifier": "99 634 920 773"}]),
        _merger("MN-2", acquirers=[{"name": "Swan Midco Pty Ltd", "identifier": "55 682 241 621"}]),
    ]
    assert drp.find_candidates(mergers, []) == []
    fuzzy = drp.find_candidates(mergers, [], fuzzy_threshold=0.6, enable_fuzzy=True)
    assert len(fuzzy) == 1


def test_single_identity_across_many_mergers_is_not_a_candidate():
    same = {"name": "Solo Pty Ltd", "identifier": "11 111 111 111"}
    mergers = [_merger(f"MN-{i}", acquirers=[dict(same)]) for i in range(3)]
    assert drp.find_candidates(mergers, []) == []


def test_canonical_name_defaults_to_shortest_and_is_title_cased():
    mergers = [
        _merger("MN-1", acquirers=[{"name": "ACME GLOBAL PTY LTD", "identifier": "12 345 678 901"}]),
        _merger("MN-2", acquirers=[{"name": "ACME GLOBAL PTY LTD", "identifier": "12 345 678 901"}]),
        _merger("MN-3", acquirers=[{"name": "ACME PTY LTD", "identifier": "12 345 678 901"}]),
    ]
    c = drp.find_candidates(mergers, [])[0]
    # The shortest member name wins even though it is the less common one,
    # and it is title-cased for display.
    assert c["canonical_name"] == "Acme Pty Ltd"


def test_apply_suggestions_appends_groups(tmp_path):
    parties = tmp_path / "related_parties.json"
    parties.write_text(json.dumps({"groups": []}))
    candidates = [{
        "id": "old-name-pty-ltd",
        "canonical_name": "Old Name Pty Ltd",
        "members": [
            {"name": "Old Name Pty Ltd", "identifier": "12 345 678 901", "merger_count": 1, "merger_ids": ["MN-1"]},
            {"name": "New Name Pty Ltd", "identifier": "12 345 678 901", "merger_count": 1, "merger_ids": ["MN-2"]},
        ],
    }]
    added = drp.apply_suggestions(parties, candidates)
    assert added == 1
    data = json.loads(parties.read_text())
    assert data["groups"][0]["id"] == "old-name-pty-ltd"
    # merger_count / merger_ids are stripped from the stored members
    assert data["groups"][0]["members"][0] == {"name": "Old Name Pty Ltd", "identifier": "12 345 678 901"}


def test_generated_ids_are_unique():
    mergers = [
        _merger("MN-1", acquirers=[{"name": "Acme Pty Ltd", "identifier": "11 111 111 111"}]),
        _merger("MN-2", acquirers=[{"name": "Acme Holdings Pty Ltd", "identifier": "11 111 111 111"}]),
        _merger("MN-3", targets=[{"name": "Acme Pty Ltd", "identifier": "22 222 222 222"}]),
        _merger("MN-4", targets=[{"name": "Acme (2) Pty Ltd", "identifier": "22 222 222 222"}]),
    ]
    candidates = drp.find_candidates(mergers, [])
    ids = [c["id"] for c in candidates]
    assert len(ids) == len(set(ids))
