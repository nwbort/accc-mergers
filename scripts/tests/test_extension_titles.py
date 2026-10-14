"""Pins the timeline-extension title rules to their frontend copy.

The rules for reading a register event title as a timeline extension (is it
one, how many business days, the "following ..." reason) live in
``scripts/generate/static_data/outputs/extensions.py``, which writes
``extensions.json``, and are hand-copied into
``frontend/src/utils/timelineExtensions.js``, which shades each extension on
the merger detail timeline. If they diverge, the site shades extensions the
pipeline doesn't count, or labels them differently.

``fixtures/extension-title-cases.json`` is the single source of truth binding
the two. The JS side asserts against it in
``frontend/src/utils/__tests__/timelineExtensions.test.js``; this file does the
same for the Python copy.
"""

import json
from pathlib import Path

import pytest

from scripts.generate.static_data.outputs.extensions import (
    is_extension_event,
    parse_business_days,
    reason_detail,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE = json.loads(
    (REPO_ROOT / "fixtures" / "extension-title-cases.json").read_text(encoding="utf-8")
)
CASES = FIXTURE["cases"]
EXTENSIONS = [c for c in CASES if c["is_extension"]]


def test_fixture_covers_both_outcomes():
    assert EXTENSIONS, "fixtures/extension-title-cases.json has no extension cases"
    assert len(EXTENSIONS) < len(CASES), "fixtures/extension-title-cases.json has no non-extension cases"


@pytest.mark.parametrize("case", CASES, ids=[c["title"][:50] or "<empty>" for c in CASES])
def test_is_extension_matches_golden_fixture(case):
    assert is_extension_event(case["title"]) == case["is_extension"]


@pytest.mark.parametrize("case", EXTENSIONS, ids=[c["title"][:50] for c in EXTENSIONS])
def test_business_days_and_reason_match_golden_fixture(case):
    assert parse_business_days(case["title"]) == case["business_days"]
    assert reason_detail(case["title"]) == case["reason"]
