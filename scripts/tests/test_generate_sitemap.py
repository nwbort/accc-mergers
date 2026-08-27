"""Covers the sitemap's party and industry inclusion rules.

The sitemap deliberately advertises fewer pages than the site builds: single-
merger shelf companies and empty ANZSIC nodes are prerendered and served, but
kept out of the sitemap so crawl budget goes to the merger pages. See the
module docstring in ``scripts/generate/generate_sitemap.py`` for the full policy.

These tests pin the two filters, because getting either wrong is silent — the
sitemap still validates, it just advertises the wrong set of URLs.
"""


from scripts.generate.generate_sitemap import (  # noqa: E402
    group_merger_count,
    industry_codes_with_mergers,
    sitemap_party_groups,
)


def party_group(group_id, mergers_by_role):
    return {
        "id": group_id,
        "canonical_name": group_id.title(),
        "mergers_by_role": mergers_by_role,
    }


def roles(acquirer=(), target=(), other=()):
    return {
        "acquirer": {m: {"merger_id": m} for m in acquirer},
        "target": {m: {"merger_id": m} for m in target},
        "other": {m: {"merger_id": m} for m in other},
    }


class TestGroupMergerCount:
    def test_counts_across_every_role(self):
        group = party_group("acme", roles(acquirer=["MN-1"], target=["MN-2"], other=["MN-3"]))
        assert group_merger_count(group) == 3

    def test_counts_a_merger_once_when_the_party_holds_two_roles(self):
        group = party_group("acme", roles(acquirer=["MN-1"], other=["MN-1"]))
        assert group_merger_count(group) == 1

    def test_zero_for_a_group_with_no_mergers(self):
        assert group_merger_count(party_group("acme", roles())) == 0


class TestSitemapPartyGroups:
    def test_keeps_a_hand_declared_group_even_with_one_merger(self):
        groups = [party_group("coles", roles(acquirer=["MN-1"]))]
        related = [{"id": "coles", "canonical_name": "Coles Group"}]
        assert [g["id"] for g in sitemap_party_groups(groups, related)] == ["coles"]

    def test_drops_a_synthesised_group_with_one_merger(self):
        groups = [party_group("spv-pty-ltd", roles(acquirer=["MN-1"]))]
        assert sitemap_party_groups(groups, []) == []

    def test_keeps_a_synthesised_group_with_two_mergers(self):
        # Repeat acquirers that simply have not been grouped by hand yet —
        # exactly the candidates detect_related_parties.py surfaces.
        groups = [party_group("repeat-buyer", roles(acquirer=["MN-1", "MN-2"]))]
        assert [g["id"] for g in sitemap_party_groups(groups, [])] == ["repeat-buyer"]

    def test_a_party_on_one_merger_under_two_roles_is_not_promoted(self):
        groups = [party_group("spv", roles(acquirer=["MN-1"], other=["MN-1"]))]
        assert sitemap_party_groups(groups, []) == []

    def test_ignores_declared_groups_with_no_id(self):
        groups = [party_group("spv", roles(acquirer=["MN-1"]))]
        assert sitemap_party_groups(groups, [{"canonical_name": "No id"}]) == []


class TestIndustryCodesWithMergers:
    def test_includes_the_tagged_code_and_all_its_ancestors(self):
        # 6240 is an ANZSIC class under subdivision 62, group 624, division K.
        codes = industry_codes_with_mergers([{"anzsic_codes": [{"code": "6240"}]}])
        assert "6240" in codes
        assert {"K", "62", "624"} <= codes

    def test_excludes_nodes_with_no_activity(self):
        codes = industry_codes_with_mergers([{"anzsic_codes": [{"code": "6240"}]}])
        assert "9002" not in codes

    def test_does_not_depend_on_page_modified_datetime(self):
        # industry_lastmods() keys on that timestamp; this filter must not, or
        # an industry with mergers but no timestamps would vanish from the
        # sitemap.
        codes = industry_codes_with_mergers([
            {"anzsic_codes": [{"code": "6240"}], "page_modified_datetime": ""},
        ])
        assert "6240" in codes

    def test_tolerates_mergers_with_no_or_malformed_codes(self):
        assert industry_codes_with_mergers([{}]) == set()
        assert industry_codes_with_mergers([{"anzsic_codes": None}]) == set()
        assert industry_codes_with_mergers([{"anzsic_codes": [{"code": ""}]}]) == set()
