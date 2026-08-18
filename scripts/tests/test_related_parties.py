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

import pytest

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


def test_normalise_identifier_treats_na_placeholder_as_missing():
    # "N/A" is recorded for parties with no known ABN; it must not normalise
    # to a shared identifier ("NA") that falsely links unrelated parties.
    assert pm.normalise_identifier("N/A") == ""
    assert pm.normalise_identifier("n/a") == ""


def test_identical_placeholder_identifier_does_not_collide_unrelated_parties():
    mergers = [
        _merger("MN-1", targets=[{"name": "Metrotech Vertriebs GmbH", "identifier": "N/A"}]),
        _merger("MN-2", targets=[{"name": "L Catterton Management Limited", "identifier": "N/A"}]),
    ]
    assert drp.find_candidates(mergers, []) == []


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


def test_dedupe_members_drops_normalised_duplicates_keeping_first_display_form():
    members = [
        {"name": "COLES GROUP LIMITED", "identifier": "11 004 089 936"},
        {"name": "Coles Group Limited", "identifier": "11004089936"},  # same, different casing/spacing
        {"name": "COLES SUPERMARKETS AUSTRALIA PTY LTD", "identifier": ""},
    ]
    out = pm.dedupe_members(members)
    assert out == [
        {"name": "COLES GROUP LIMITED", "identifier": "11 004 089 936"},
        {"name": "COLES SUPERMARKETS AUSTRALIA PTY LTD", "identifier": ""},
    ]


def test_merge_groups_combines_members_and_dedupes():
    groups = [
        {
            "id": "coles",
            "canonical_name": "Coles Group",
            "members": [{"name": "COLES GROUP LIMITED", "identifier": "11 004 089 936"}],
        },
        {
            "id": "coles-2",
            "canonical_name": "Coles Supermarkets",
            "members": [
                {"name": "COLES SUPERMARKETS AUSTRALIA PTY LTD", "identifier": "45 004 189 708"},
                {"name": "COLES GROUP LIMITED", "identifier": "11 004 089 936"},  # duplicate
            ],
        },
        {
            "id": "woolworths",
            "canonical_name": "Woolworths Group",
            "members": [{"name": "WOOLWORTHS GROUP LIMITED", "identifier": "88 000 014 675"}],
        },
    ]
    merged = pm.merge_groups(groups, ["coles", "coles-2"])
    ids = [g["id"] for g in merged]
    assert ids == ["coles", "woolworths"]  # first-listed id kept, other dropped, rest untouched
    kept = next(g for g in merged if g["id"] == "coles")
    assert kept["canonical_name"] == "Coles Group"  # default: kept group's own name
    assert kept["members"] == [
        {"name": "COLES GROUP LIMITED", "identifier": "11 004 089 936"},
        {"name": "COLES SUPERMARKETS AUSTRALIA PTY LTD", "identifier": "45 004 189 708"},
    ]
    # Original list is untouched.
    assert len(groups) == 3


def test_merge_groups_keeps_first_requested_id_regardless_of_storage_order():
    # "coles-2" is stored *before* "coles", but the caller asked to merge
    # ["coles", "coles-2"] - the kept id must follow the caller's order, not
    # whatever order the groups happen to be stored in.
    groups = [
        {"id": "coles-2", "canonical_name": "Coles Supermarkets", "members": [{"name": "B", "identifier": ""}]},
        {"id": "coles", "canonical_name": "Coles Group", "members": [{"name": "A", "identifier": ""}]},
    ]
    merged = pm.merge_groups(groups, ["coles", "coles-2"])
    assert [g["id"] for g in merged] == ["coles"]
    assert merged[0]["canonical_name"] == "Coles Group"


def test_merge_groups_accepts_custom_canonical_name():
    groups = [
        {"id": "a", "canonical_name": "A", "members": [{"name": "A Pty Ltd", "identifier": "1"}]},
        {"id": "b", "canonical_name": "B", "members": [{"name": "B Pty Ltd", "identifier": "2"}]},
    ]
    merged = pm.merge_groups(groups, ["a", "b"], canonical_name="A and B Combined")
    assert len(merged) == 1
    assert merged[0]["canonical_name"] == "A and B Combined"


def test_merge_groups_requires_two_distinct_ids():
    groups = [{"id": "a", "canonical_name": "A", "members": []}]
    with pytest.raises(ValueError):
        pm.merge_groups(groups, ["a"])


def test_merge_groups_raises_on_unknown_id():
    groups = [{"id": "a", "canonical_name": "A", "members": []}]
    with pytest.raises(KeyError):
        pm.merge_groups(groups, ["a", "missing"])


# ---------------------------------------------------------------------------
# party_matching: group mutation helpers (unique_group_id, add_members_to_group,
# create_group) — shared by the batch-review workflow and the hand-editing UI.
# ---------------------------------------------------------------------------

def test_unique_group_id_slugifies_and_avoids_collisions():
    assert pm.unique_group_id("Coles Group", set()) == "coles-group"
    assert pm.unique_group_id("Coles Group", {"coles-group"}) == "coles-group-2"
    assert pm.unique_group_id("Coles Group", {"coles-group", "coles-group-2"}) == "coles-group-3"


def test_unique_group_id_falls_back_when_name_has_no_usable_characters():
    assert pm.unique_group_id("***", set()) == "party"


def test_add_members_to_group_dedupes_and_mutates_in_place():
    groups = [{
        "id": "coles",
        "canonical_name": "Coles Group",
        "members": [{"name": "COLES GROUP LIMITED", "identifier": "11 004 089 936"}],
    }]
    result = pm.add_members_to_group(groups, "coles", [
        {"name": "COLES SUPERMARKETS AUSTRALIA PTY LTD", "identifier": "45 004 189 708"},
        {"name": "Coles Group Limited", "identifier": "11004089936"},  # duplicate of existing member
    ])
    assert result is groups[0]  # mutated in place, not a copy
    assert groups[0]["members"] == [
        {"name": "COLES GROUP LIMITED", "identifier": "11 004 089 936"},
        {"name": "COLES SUPERMARKETS AUSTRALIA PTY LTD", "identifier": "45 004 189 708"},
    ]


def test_add_members_to_group_raises_on_unknown_id():
    with pytest.raises(KeyError):
        pm.add_members_to_group([], "missing", [{"name": "A", "identifier": ""}])


def test_create_group_appends_a_new_group_with_a_unique_id():
    groups = [{"id": "coles", "canonical_name": "Coles Group", "members": []}]
    new_group = pm.create_group(
        groups, "Woolworths Group", [{"name": "WOOLWORTHS GROUP LIMITED", "identifier": "88 000 014 675"}]
    )
    assert new_group is groups[-1]  # appended
    assert new_group["id"] == "woolworths-group"
    assert new_group["canonical_name"] == "Woolworths Group"
    assert len(groups) == 2


def test_create_group_dedupes_members():
    groups = []
    new_group = pm.create_group(groups, "Acme", [
        {"name": "ACME PTY LTD", "identifier": "11 111 111 111"},
        {"name": "Acme Pty Ltd", "identifier": "11111111111"},  # duplicate
    ])
    assert len(new_group["members"]) == 1


def test_create_group_raises_when_no_members_survive_dedup():
    with pytest.raises(ValueError):
        pm.create_group([], "Empty", [{"name": "", "identifier": ""}])


def test_create_group_avoids_id_collision_with_existing_groups():
    groups = [{"id": "acme", "canonical_name": "Acme (old)", "members": []}]
    new_group = pm.create_group(groups, "Acme", [{"name": "Acme Pty Ltd", "identifier": "1"}])
    assert new_group["id"] == "acme-2"


def test_create_group_accepts_explicit_group_id():
    groups = []
    new_group = pm.create_group(
        groups, "Acme", [{"name": "Acme Pty Ltd", "identifier": "1"}], group_id="custom-id"
    )
    assert new_group["id"] == "custom-id"


# ---------------------------------------------------------------------------
# party_matching: load_parties_doc / save_parties_doc
# ---------------------------------------------------------------------------

def test_load_parties_doc_returns_empty_groups_when_file_missing(tmp_path):
    doc = pm.load_parties_doc(tmp_path / "nope.json")
    assert doc == {"groups": []}


def test_load_parties_doc_preserves_extra_top_level_keys(tmp_path):
    path = tmp_path / "related_parties.json"
    path.write_text(json.dumps({"_README": "some notes", "groups": [{"id": "a", "canonical_name": "A", "members": []}]}))
    doc = pm.load_parties_doc(path)
    assert doc["_README"] == "some notes"
    assert doc["groups"][0]["id"] == "a"


def test_save_parties_doc_round_trips_and_creates_parent_dirs(tmp_path):
    path = tmp_path / "nested" / "related_parties.json"
    doc = {"groups": [{"id": "a", "canonical_name": "A", "members": []}]}
    pm.save_parties_doc(doc, path)
    assert pm.load_parties_doc(path) == doc


def test_save_parties_doc_writes_non_ascii_characters_literally(tmp_path):
    # ensure_ascii=False: accented characters already in the file must
    # round-trip as literal UTF-8, not be rewritten as \uXXXX escapes on
    # every save (which would turn an unrelated edit into a huge diff).
    path = tmp_path / "related_parties.json"
    doc = {"groups": [{
        "id": "loreal",
        "canonical_name": "L'Oréal",
        "members": [{"name": "Société Anonyme des Eaux Minérales d'Évian S.A.", "identifier": ""}],
    }]}
    pm.save_parties_doc(doc, path)
    text = path.read_text(encoding="utf-8")
    assert "Évian" in text
    assert "\\u00c9" not in text.lower()
    assert json.loads(text) == doc


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


def test_sibling_spvs_not_grouped_even_with_fuzzy():
    # "Bidco"/"Midco" are separate vehicles in one deal, not one entity under
    # two names. They differ only by a distinguishing "-co" role token, so even
    # the fuzzy pass must refuse to link them.
    mergers = [
        _merger("MN-1", acquirers=[{"name": "Swan Bidco Pty Ltd", "identifier": "99 634 920 773"}]),
        _merger("MN-2", acquirers=[{"name": "Swan Midco Pty Ltd", "identifier": "55 682 241 621"}]),
    ]
    assert drp.find_candidates(mergers, []) == []
    assert drp.find_candidates(mergers, [], fuzzy_threshold=0.6, enable_fuzzy=True) == []


def test_numbered_and_state_sibling_spvs_are_not_fuzzy_linked():
    # Numbered / state-suffixed siblings must not be recommended even under fuzzy.
    mergers = [
        _merger("MN-1", acquirers=[{"name": "Count Holdings No. 1 Pty Ltd", "identifier": "70 696 338 995"}]),
        _merger("MN-2", acquirers=[{"name": "Count Holdings No. 3 Pty Ltd", "identifier": "37 696 339 161"}]),
        _merger("MN-3", targets=[{"name": "Smile Partners (WA1) Pty Ltd", "identifier": "27 662 001 925"}]),
        _merger("MN-4", targets=[{"name": "Smile Partners (WA2) Pty Ltd", "identifier": "98 674 927 943"}]),
    ]
    assert drp.find_candidates(mergers, [], fuzzy_threshold=0.6, enable_fuzzy=True) == []


def test_fuzzy_still_links_genuinely_similar_non_sibling_names():
    # A real typo that isn't just a distinguishing token (shared "acme" and
    # "solutions" tokens, one mis-spelt word) should still come through fuzzy.
    mergers = [
        _merger("MN-1", acquirers=[{"name": "Acme Global Solutions Pty Ltd", "identifier": "60 129 983 688"}]),
        _merger("MN-2", acquirers=[{"name": "Acme Globel Solutions Pty Ltd", "identifier": "68 120 964 650"}]),
    ]
    fuzzy = drp.find_candidates(mergers, [], fuzzy_threshold=0.8, enable_fuzzy=True)
    assert len(fuzzy) == 1
    assert fuzzy[0]["signal"] == "fuzzy"


def test_detects_punctuation_only_name_variant_by_default():
    # Same name written two ways (comma / no full stop): one entity, and the
    # name_variant signal catches it without needing --fuzzy.
    mergers = [
        _merger("MN-1", acquirers=[{"name": "Francisco Partners Management, L.P", "identifier": ""}]),
        _merger("MN-2", acquirers=[{"name": "Francisco Partners Management, LP", "identifier": ""}]),
    ]
    candidates = drp.find_candidates(mergers, [])
    assert len(candidates) == 1
    assert candidates[0]["signal"] == "name_variant"
    assert candidates[0]["score"] == 0.90


def test_exact_name_signal_wins_over_name_variant():
    # Identical names also squash-equal, but the stronger "name" signal should
    # label the group, not "name_variant".
    mergers = [
        _merger("MN-1", targets=[{"name": "Eli Lilly and Company", "identifier": "IRS 350470950"}]),
        _merger("MN-2", targets=[{"name": "Eli Lilly and Company", "identifier": "350470950 (IRS)"}]),
    ]
    candidates = drp.find_candidates(mergers, [])
    assert len(candidates) == 1
    assert candidates[0]["signal"] == "name"


def test_single_identity_across_many_mergers_is_not_a_candidate():
    same = {"name": "Solo Pty Ltd", "identifier": "11 111 111 111"}
    mergers = [_merger(f"MN-{i}", acquirers=[dict(same)]) for i in range(3)]
    assert drp.find_candidates(mergers, []) == []


def test_canonical_name_prefers_most_mergers_then_shortest_and_is_title_cased():
    mergers = [
        _merger("MN-1", acquirers=[{"name": "ACME GLOBAL PTY LTD", "identifier": "12 345 678 901"}]),
        _merger("MN-2", acquirers=[{"name": "ACME GLOBAL PTY LTD", "identifier": "12 345 678 901"}]),
        _merger("MN-3", acquirers=[{"name": "ACME PTY LTD", "identifier": "12 345 678 901"}]),
    ]
    c = drp.find_candidates(mergers, [])[0]
    # The most common member wins (2 mergers > 1), title-cased for display.
    assert c["canonical_name"] == "Acme Global Pty Ltd"


def test_canonical_name_tie_breaks_on_shortest():
    mergers = [
        _merger("MN-1", acquirers=[{"name": "ACME GLOBAL PTY LTD", "identifier": "12 345 678 901"}]),
        _merger("MN-2", acquirers=[{"name": "ACME PTY LTD", "identifier": "12 345 678 901"}]),
    ]
    c = drp.find_candidates(mergers, [])[0]
    # Equal merger counts -> the shorter name wins.
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


def test_find_group_merge_candidates_flags_groups_sharing_an_identifier():
    groups = [
        {
            "id": "old-name",
            "canonical_name": "Old Name",
            "members": [{"name": "Old Name Pty Ltd", "identifier": "12 345 678 901"}],
        },
        {
            "id": "new-name",
            "canonical_name": "New Name",
            "members": [{"name": "New Name Pty Ltd", "identifier": "12 345 678 901"}],
        },
    ]
    candidates = drp.find_group_merge_candidates(groups, enable_fuzzy=False)
    assert len(candidates) == 1
    c = candidates[0]
    assert c["group_ids"] == ["new-name", "old-name"]
    assert c["signal"] == "identifier"
    assert {g["canonical_name"] for g in c["groups"]} == {"Old Name", "New Name"}


def test_find_group_merge_candidates_ignores_clusters_within_one_group():
    groups = [{
        "id": "coles",
        "canonical_name": "Coles Group",
        "members": [
            {"name": "COLES GROUP LIMITED", "identifier": "11 004 089 936"},
            {"name": "Coles Group Limited", "identifier": "11 004 089 936"},
        ],
    }]
    assert drp.find_group_merge_candidates(groups, enable_fuzzy=False) == []


def test_find_group_merge_candidates_no_groups_is_noop():
    assert drp.find_group_merge_candidates([], enable_fuzzy=False) == []


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
