"""Pins scripts/slug.py's slugify to the shared golden fixture.

The slug algorithm is hand-copied into three places — this module
(``scripts/slug.py``, used to build the sitemap), the SPA copy in
``frontend/src/utils/slug.js`` (rendered links, canonical tags
and the build-time prerender), and the inline copy in
``functions/mergers/[matter]/[[path]].js`` (the OG handler). If they diverge,
the sitemap, canonical tags and rendered URLs disagree and search engines pick
the wrong canonical page.

``fixtures/slug-cases.json`` is the single source of truth binding all
three. The JS side asserts against it in
``frontend/src/utils/__tests__/slug.test.js``; this file does the
same for the Python copy. Change the algorithm -> update all three and
regenerate the fixture.
"""

import json
import os
import sys
from pathlib import Path

import pytest

# Import scripts/slug.py the same way the other tests here reach scripts modules.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from slug import merger_path, slugify  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE = json.loads(
    (REPO_ROOT / "fixtures" / "slug-cases.json").read_text(encoding="utf-8")
)
CASES = FIXTURE["cases"]


def test_fixture_is_non_empty():
    assert isinstance(CASES, list)
    assert CASES, "fixtures/slug-cases.json has no cases"


@pytest.mark.parametrize("case", CASES, ids=[c["slug"] or "<empty>" for c in CASES])
def test_slugify_matches_golden_fixture(case):
    assert slugify(case["name"]) == case["slug"]


def test_slugify_handles_empty_and_none():
    assert slugify("") == ""
    assert slugify(None) == ""


def test_merger_path_appends_slug_or_falls_back():
    assert (
        merger_path("WA-35022", "Hexagon - Waygate Technologies")
        == "/mergers/WA-35022/hexagon-waygate-technologies"
    )
    # No derivable slug -> bare-id form.
    assert merger_path("MN-10007", "!!!") == "/mergers/MN-10007"
