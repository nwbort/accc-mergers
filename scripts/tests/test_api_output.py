"""The key-gated API's merger list (scripts/generate/static_data/outputs/api.py).

The pre-notification summary rule is hand-copied from the site's
``getPreNotificationEstimate`` (frontend/src/utils/preNotification.js);
``fixtures/pre-notification-summary-cases.json`` binds the two, and the JS side
asserts against it in ``frontend/src/utils/__tests__/preNotification.test.js``.
"""

import json
from pathlib import Path

import pytest

from scripts.generate.static_data.outputs import api, list as list_out

REPO_ROOT = Path(__file__).resolve().parents[2]
CASES = json.loads(
    (REPO_ROOT / "fixtures" / "pre-notification-summary-cases.json").read_text(encoding="utf-8")
)["cases"]


@pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
def test_summary_matches_fixture(case):
    assert api.pre_notification_summary(case["merger"]) == case["expected"]


def test_thresholds_match_the_frontend():
    source = (REPO_ROOT / "frontend" / "src" / "utils" / "preNotification.js").read_text()
    assert f"HIGH_CONFIDENCE_WINDOW_DAYS = {api.HIGH_CONFIDENCE_WINDOW_DAYS};" in source
    assert f"MEDIUM_CONFIDENCE_WINDOW_DAYS = {api.MEDIUM_CONFIDENCE_WINDOW_DAYS};" in source


def _merger(**extra):
    return {
        "merger_id": "MN-1",
        "merger_name": "A / B",
        "effective_notification_datetime": "2026-10-01T12:00:00Z",
        "pre_notification": {
            "estimated_days": 17, "min_days": 10, "max_days": 20,
            "id_issued_estimated": "2026-09-14", "basis": "bracketed",
            "min_days_witness": "WA-1", "max_days_witness": "WA-2", "method_version": 1,
        },
        "phase_1_estimate": {"expected_business_days": 17},
        "events": [{"date": "2026-10-01T12:00:00Z", "title": "Notified"}],
        **extra,
    }


def test_entry_is_the_list_entry_plus_the_summary():
    m = _merger()
    entry = api._entry(m)
    expected = list_out._lightweight(m)
    expected["pre_notification"] = {"kind": "around", "start_date": "2026-09-14", "confidence": "high"}
    assert entry == expected


def test_entry_never_carries_the_raw_workings():
    text = json.dumps(api._entry(_merger()))
    for leaked in ("witness", "min_days", "max_days", "method_version", "phase_1_estimate", "events"):
        assert leaked not in text


def test_entry_keys_are_pinned():
    """The list entry can't grow or shrink the v1 API without this set changing too."""
    m = _merger(
        appeal={"status": "current"},
        under_judicial_review=True,
        materially_incomplete=True,
    )
    keys = set(api._entry(m))
    assert keys <= api.API_ENTRY_KEYS, f"new list field(s) would reach the API: {keys - api.API_ENTRY_KEYS}"
    always = api.API_ENTRY_KEYS - {"appeal", "under_judicial_review", "materially_incomplete", "reached_phase_2"}
    assert always <= set(api._entry(_merger())), "a v1 field has disappeared from the list entry"


def test_generate_writes_one_merger_per_line(tmp_path):
    mergers = [
        _merger(merger_id="MN-2", effective_notification_datetime="2026-10-02T12:00:00Z"),
        _merger(merger_id="MN-1"),
    ]
    assert api.generate(mergers, tmp_path) == 2
    path = tmp_path / "api" / "v1" / "mergers.json"
    text = path.read_text(encoding="utf-8")
    payload = json.loads(text)
    assert payload["version"] == "v1"
    assert payload["licence"].startswith("CC BY 4.0")
    assert [m["merger_id"] for m in payload["mergers"]] == ["MN-1", "MN-2"]
    assert len(text.splitlines()) == 4  # header line, two mergers, closing line
