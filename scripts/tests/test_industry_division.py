"""Pins scripts/industry_division.py's division lookup to two things.

The lookup is hand-copied into two places — this module
(``scripts/industry_division.py``, which writes ``industries/{division}.json``)
and the SPA copy in ``frontend/src/utils/industryDivision.js`` (which decides
which file to fetch, and which ``frontend/prerender.js`` walks at build time).
If they diverge the SPA asks for the wrong division file and every industry page
404s.

``fixtures/industry-division-cases.json`` is the single source of truth binding
the two. The JS side asserts against it in
``frontend/src/utils/__tests__/industryDivision.test.js``; this file does the
same for the Python copy.

It also checks the range table against the real ANZSIC tree, which the fixture
alone cannot do: a table that both implementations agreed on but that disagreed
with ``anzsic_codes.json`` would pass every golden case and still file half the
nodes under the wrong division.
"""

import json
from pathlib import Path

import pytest

from scripts.generate.static_data import anzsic
from scripts.industry_division import (
    DIVISION_SUBDIVISION_RANGES,
    ORPHAN_FILE_STEM,
    all_file_names,
    division_file_name,
    division_file_stem,
    division_for,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE = json.loads(
    (REPO_ROOT / "fixtures" / "industry-division-cases.json").read_text(encoding="utf-8")
)
CASES = FIXTURE["cases"]


def test_fixture_is_non_empty():
    assert isinstance(CASES, list)
    assert CASES, "fixtures/industry-division-cases.json has no cases"


@pytest.mark.parametrize("case", CASES, ids=[c["code"] or "<empty>" for c in CASES])
def test_division_file_matches_golden_fixture(case):
    assert division_file_name(case["code"]) == case["file"]


# ---------------------------------------------------------------------------
# The table vs the real tree
# ---------------------------------------------------------------------------

def test_every_anzsic_node_lands_under_its_real_division():
    """Walk all 825 nodes and check the range table against the actual tree.

    This is the check the golden fixture can't make: the fixture only proves the
    two implementations agree with each other.
    """
    hierarchy = anzsic.hierarchy()
    for code, node in hierarchy.items():
        expected = node.code
        walker = node
        while walker.parent_code:
            walker = hierarchy[walker.parent_code]
            expected = walker.code
        assert division_for(code) == expected, f"{code} ({node.level})"


def test_table_covers_every_division_exactly_once():
    divisions = {n.code for n in anzsic.hierarchy().values() if n.level == "division"}
    table = [d for d, _, _ in DIVISION_SUBDIVISION_RANGES]
    assert sorted(table) == sorted(divisions)
    assert len(table) == len(set(table))


def test_ranges_are_ordered_and_do_not_overlap():
    previous_high = 0
    for _, low, high in DIVISION_SUBDIVISION_RANGES:
        assert low <= high
        assert low > previous_high, "ranges must be ordered and disjoint"
        previous_high = high


# ---------------------------------------------------------------------------
# Codes outside the tree
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "code",
    [
        "",
        None,
        "T",          # a division letter ANZSIC doesn't use
        "61",         # a subdivision number in one of the standard's gaps
        "6100",
        "9999",
        "06/10",      # the ACCC has published a slashed tag before
        "abcd",
        "0",
        "12345",
    ],
)
def test_codes_outside_the_tree_fall_to_the_orphan_file(code):
    assert division_for(code) is None
    assert division_file_stem(code) == ORPHAN_FILE_STEM
    assert division_file_name(code) == f"{ORPHAN_FILE_STEM}.json"


def test_surrounding_whitespace_is_tolerated():
    """The code arrives off a URL path segment, so a stray space shouldn't
    silently route a real industry to the orphan file."""
    assert division_for(" 4520 ") == "H"


def test_all_file_names_is_the_complete_set():
    names = all_file_names()
    assert len(names) == len(set(names))
    assert len(names) == len(DIVISION_SUBDIVISION_RANGES) + 1
    assert f"{ORPHAN_FILE_STEM}.json" in names
    # Every node in the tree is covered by one of them.
    assert {division_file_name(code) for code in anzsic.hierarchy()} <= set(names)
