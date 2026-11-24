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


class TestPinnedStaticLastmods:
    """The hand-edited pages whose sitemap date the pre-commit hook maintains."""

    def test_every_pinned_page_is_a_static_page_with_real_sources(self):
        from scripts.generate.generate_sitemap import STATIC_PAGES
        from scripts.generate.sitemap_lastmod import load_pinned
        from scripts.paths import REPO_ROOT

        static_paths = {page["path"] for page in STATIC_PAGES}
        for path, page in load_pinned().items():
            assert path in static_paths
            assert page["sources"]
            for source in page["sources"]:
                assert (REPO_ROOT / source).exists(), source

    def test_touched_pages_matches_on_source_files(self):
        from scripts.generate.sitemap_lastmod import touched_pages

        pinned = {
            "/privacy": {"sources": ["a.jsx"], "lastmod": "2026-01-01"},
            "/copyright": {"sources": ["b.jsx", "c.json"], "lastmod": "2026-01-01"},
        }
        assert touched_pages(pinned, {"c.json", "unrelated.py"}) == ["/copyright"]
        assert touched_pages(pinned, {"unrelated.py"}) == []

    def test_patch_sitemap_rewrites_only_the_named_page(self):
        from scripts.generate.generate_sitemap import url_entry
        from scripts.generate.sitemap_lastmod import patch_sitemap

        xml = "\n".join([
            url_entry("https://mergers.fyi/", "2026-01-01", "daily", "1.0"),
            url_entry("https://mergers.fyi/privacy", "2026-01-01", "monthly", "0.8"),
        ])
        patched = patch_sitemap(xml, {"/privacy": "2026-10-21"})
        assert patched.count("2026-10-21") == 1
        assert "<loc>https://mergers.fyi/privacy</loc>\n    <lastmod>2026-10-21" in patched


class TestQuarterlyReports:
    QUARTERS = [
        {"url_key": "26Q2", "end": "2026-06-30"},
        {"url_key": "26Q3", "end": "2026-09-30"},
    ]

    def test_each_quarter_page_is_listed_and_the_latest_ranks_highest(self):
        from scripts.generate.generate_sitemap import quarterly_entries
        q2, q3 = quarterly_entries(self.QUARTERS)
        assert "<loc>https://mergers.fyi/quarterly/26Q2</loc>" in q2
        assert "<lastmod>2026-07-01</lastmod>" in q2 and "<priority>0.5</priority>" in q2
        assert "<loc>https://mergers.fyi/quarterly/26Q3</loc>" in q3
        assert "<lastmod>2026-10-01</lastmod>" in q3 and "<priority>0.8</priority>" in q3

    def test_the_bare_quarterly_url_is_not_listed(self):
        # It canonicalises to the latest quarter's page, so it isn't advertised.
        from scripts.generate.generate_sitemap import STATIC_PAGES, generate_sitemap
        assert "/quarterly" not in {page["path"] for page in STATIC_PAGES}
        xml = generate_sitemap([], [], [], self.QUARTERS)
        assert "<loc>https://mergers.fyi/quarterly</loc>" not in xml
        assert xml.count("/quarterly/") == 2

    def test_missing_quarterly_json_lists_no_quarters(self, tmp_path):
        from scripts.generate.generate_sitemap import load_quarters
        assert load_quarters(tmp_path / "absent.json") == []


class TestDataDrivenLastmod:
    """Hub pages are dated by the data, so unchanged data is an unchanged sitemap."""

    MERGERS = [
        {"merger_id": "MN-1", "merger_name": "A", "page_modified_datetime": "2026-11-03T09:00:00+11:00"},
        # Later as a string, earlier as an instant: compared by instant.
        {"merger_id": "MN-2", "merger_name": "B", "page_modified_datetime": "2026-11-03T08:00:00+00:00"},
        {"merger_id": "MN-3", "merger_name": "C", "page_modified_datetime": "2026-10-01T09:00:00+10:00"},
        {"merger_id": "MN-4", "merger_name": "D"},
    ]

    def test_data_lastmod_is_the_newest_timestamp(self):
        from scripts.generate.generate_sitemap import data_lastmod
        assert data_lastmod(self.MERGERS) == "2026-11-03"
        assert data_lastmod(self.MERGERS[2:]) == "2026-10-01"

    def test_data_lastmod_falls_back_to_today_without_timestamps(self):
        from scripts.generate import generate_sitemap as gs
        assert gs.data_lastmod([{"merger_id": "MN-4"}]) == gs.TODAY
        assert gs.data_lastmod([{"page_modified_datetime": "garbage"}]) == gs.TODAY

    def test_static_pages_and_untimed_mergers_use_the_data_date(self, monkeypatch):
        from scripts.generate import generate_sitemap as gs
        monkeypatch.setattr(gs, "pinned_lastmods", lambda: {})
        xml = gs.generate_sitemap(self.MERGERS, [], [])
        assert "<lastmod>2026-11-03</lastmod>" in xml
        home = xml.split("<loc>https://mergers.fyi/</loc>")[1].split("</url>")[0]
        assert "<lastmod>2026-11-03</lastmod>" in home
        untimed = xml.split("/mergers/MN-4")[1].split("</url>")[0]
        assert "<lastmod>2026-11-03</lastmod>" in untimed

    def test_identical_output_on_different_days(self, monkeypatch):
        from scripts.generate import generate_sitemap as gs
        monkeypatch.setattr(gs, "pinned_lastmods", lambda: {})
        monkeypatch.setattr(gs, "TODAY", "2026-11-24")
        first = gs.generate_sitemap(self.MERGERS, [], [])
        monkeypatch.setattr(gs, "TODAY", "2026-11-25")
        assert gs.generate_sitemap(self.MERGERS, [], []) == first
