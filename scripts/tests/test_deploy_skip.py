"""Pins which pipeline commits are committed with ``[skip ci]`` (no Pages deploy)."""

from scripts.deploy_skip import is_deployable, should_skip_deploy

ANALYSIS = "frontend/public/data/analysis.json"
RECENT = "frontend/public/data/recent-events.json"
UPCOMING = "frontend/public/data/upcoming-events.json"
SITEMAP = "frontend/public/sitemap.xml"


def test_only_date_windowed_outputs_skip():
    assert should_skip_deploy([ANALYSIS])
    assert should_skip_deploy([SITEMAP])
    assert should_skip_deploy([ANALYSIS, RECENT, UPCOMING, SITEMAP])


def test_non_deployable_paths_alongside_do_not_block_the_skip():
    assert should_skip_deploy([ANALYSIS, "data/processed/phase1_estimates.json", "data/output/mergers.json"])


def test_any_other_deployable_change_deploys():
    for other in (
        "frontend/public/data/mergers/MN-01016.json",
        "frontend/public/data/mergers/list.json",
        "data/raw/matters/MN-01016/determination.pdf",
        "functions/data/api/[[path]].js",
        "wrangler.toml",
    ):
        assert not should_skip_deploy([ANALYSIS, other]), other


def test_a_commit_with_nothing_deployable_is_left_alone():
    assert not should_skip_deploy([])
    assert not should_skip_deploy(["data/processed/mergers.json", "data/raw/matters.html"])


def test_watch_paths_match_prefixes_and_exact_files():
    assert is_deployable("frontend/src/App.jsx")
    assert is_deployable("atproto/identity.json")
    assert not is_deployable("atproto/lexicons/fyi/mergers/matter.json")
    assert not is_deployable("scripts/build.sh.bak")
    assert not is_deployable("data/raw/mattersx/foo.pdf")


def test_reads_git_output_lines():
    assert should_skip_deploy([ANALYSIS + "\n", "\n"])
