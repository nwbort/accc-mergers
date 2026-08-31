"""Pins scripts/shard.py's party bucketing to the shared golden fixture.

The shard algorithm is hand-copied into two places — this module
(``scripts/shard.py``, which writes ``parties/shard-{nn}.json``) and the SPA
copy in ``frontend/src/utils/shard.js`` (which decides which bucket to fetch,
and which ``frontend/prerender.js`` walks at build time). If they diverge the
SPA asks for the wrong bucket and every party page 404s.

``fixtures/shard-cases.json`` is the single source of truth binding the two.
The JS side asserts against it in
``frontend/src/utils/__tests__/shard.test.js``; this file does the same for the
Python copy. Change the algorithm or ``SHARD_COUNT`` -> update both and
regenerate the fixture.
"""

import json
from pathlib import Path

import pytest

from scripts.shard import (
    SHARD_COUNT,
    all_shard_names,
    fnv1a_32,
    party_shard,
    party_shard_name,
    shard_name,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE = json.loads(
    (REPO_ROOT / "fixtures" / "shard-cases.json").read_text(encoding="utf-8")
)
CASES = FIXTURE["cases"]


def test_fixture_is_non_empty():
    assert isinstance(CASES, list)
    assert CASES, "fixtures/shard-cases.json has no cases"


def test_fixture_shard_count_matches():
    """A fixture generated under a different SHARD_COUNT would pass every case
    by luck and still describe a different layout."""
    assert FIXTURE["shard_count"] == SHARD_COUNT


@pytest.mark.parametrize("case", CASES, ids=[c["id"][:20] or "<empty>" for c in CASES])
def test_party_shard_matches_golden_fixture(case):
    assert party_shard(case["id"]) == case["shard"]
    assert party_shard_name(case["id"]) == case["file"]


def test_known_fnv1a_vectors():
    """Published FNV-1a 32-bit vectors, so a subtle arithmetic bug shows up
    here rather than as a silently different (but self-consistent) mapping."""
    assert fnv1a_32("") == 0x811C9DC5
    assert fnv1a_32("a") == 0xE40C292C
    assert fnv1a_32("foobar") == 0xBF9CF968


def test_hashes_utf8_bytes_not_code_points():
    """The JS side hashes TextEncoder output, i.e. UTF-8 bytes. Python must fold
    the same two bytes for "e-acute" rather than the single code point 0xE9 —
    the difference is invisible on ASCII ids and wrong on every other one."""
    expected = 0x811C9DC5
    for byte in (0xC3, 0xA9):  # "é" encoded as UTF-8
        expected ^= byte
        expected = (expected * 0x01000193) & 0xFFFFFFFF
    assert fnv1a_32("é") == expected


def test_shard_is_in_range_and_stable():
    for party_id in ("coles", "", "a/b", "x" * 500, "日本たばこ産業"):
        first = party_shard(party_id)
        assert 0 <= first < SHARD_COUNT
        assert party_shard(party_id) == first


def test_handles_empty_and_none():
    assert party_shard("") == party_shard(None)
    assert party_shard_name(None).startswith("shard-")


def test_shard_name_is_two_hex_digits():
    assert shard_name(0) == "shard-00.json"
    assert shard_name(255) == "shard-ff.json"


def test_all_shard_names_is_the_complete_set():
    names = all_shard_names()
    assert len(names) == SHARD_COUNT
    assert len(set(names)) == SHARD_COUNT
    assert names[0] == "shard-00.json"


def test_distribution_is_even_enough():
    """A hash that clumped would put a big share of parties in one bucket and
    make that one fetch large. Not a strict bound — just a smoke alarm."""
    ids = [f"party-{i}" for i in range(5000)]
    counts = [0] * SHARD_COUNT
    for party_id in ids:
        counts[party_shard(party_id)] += 1
    expected = len(ids) / SHARD_COUNT
    assert all(counts), "some bucket got nothing"
    assert max(counts) < expected * 2.5
