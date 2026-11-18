"""The API's merger list: ``list.json`` plus a condensed pre-notification estimate.

Writes:
  <output_dir>/api/v1/mergers.json

Served at https://mergers.fyi/data/api/v1/mergers (no extension) by
``functions/data/api/[[path]].js``, which sits in front of the file, checks the
key against the ``api_keys`` table in D1 when ``API_REQUIRE_KEY`` asks for one,
and counts the request. See docs/api.md.

Each entry is the merger list's own entry (:func:`.list._lightweight`) plus
``pre_notification``: when the matter's pre-notification period is estimated to
have started, and how much weight that estimate carries. Only that summary is
published here, not the raw block in the detail files (its bounds, witness
matters, method version) — the API promises the reading, not the workings.

``v1`` is a promise to the API's clients: fields are added, never renamed or
removed. ``API_ENTRY_KEYS`` pins the set, and a test fails if the list's entry
grows or shrinks underneath it, so a change made for the site can't change the
API without someone deciding it should.
"""

import json
from pathlib import Path

from scripts.constants.regime import is_voluntary_period_notification

from . import list as list_out

API_DIR = Path("api") / "v1"
API_FILE = "mergers.json"

# Mirror frontend/src/utils/preNotification.js; fixtures/pre-notification-summary-cases.json
# pins the two copies together.
HIGH_CONFIDENCE_WINDOW_DAYS = 14
MEDIUM_CONFIDENCE_WINDOW_DAYS = 42

LICENCE = "CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/)"
ATTRIBUTION = "mergers.fyi (https://mergers.fyi), from the ACCC's public merger register"

# Every field a v1 entry can carry. The first group is always present; the
# second only on the matters it applies to, as in list.json.
API_ENTRY_KEYS = frozenset({
    "merger_id", "merger_name", "status", "accc_determination", "has_conditions",
    "is_waiver", "under_appeal", "is_refiled", "effective_notification_datetime",
    "determination_publication_date", "end_of_determination_period",
    "latest_event_date", "page_modified_datetime", "stage", "acquirers",
    "targets", "other_parties", "anzsic_codes", "pre_notification",
    # Only where they apply:
    "appeal", "under_judicial_review", "materially_incomplete", "reached_phase_2",
})


def _window_days(estimate: dict) -> int | None:
    """Width of the window the period could have started in, or None with one bound."""
    min_days, max_days = estimate.get("min_days"), estimate.get("max_days")
    if not isinstance(min_days, (int, float)) or not isinstance(max_days, (int, float)):
        return None
    return max(max_days - min_days, 0)


def _confidence(estimate: dict) -> str:
    """low/medium/high, from the basis and how far apart the bounds are."""
    window = _window_days(estimate)
    if estimate.get("basis") != "bracketed" or window is None:
        return "low"
    if window <= HIGH_CONFIDENCE_WINDOW_DAYS:
        return "high"
    if window <= MEDIUM_CONFIDENCE_WINDOW_DAYS:
        return "medium"
    return "low"


def pre_notification_summary(merger: dict) -> dict | None:
    """The condensed estimate the API publishes, or None when there's nothing to say.

    ``kind`` says how to read ``start_date``: ``around`` (bracketed, a point),
    ``after`` (only the earliest possible start is known), ``before`` (only the
    latest), or ``none`` (no pre-notification period detectable; no date).
    Same rule as ``getPreNotificationEstimate`` in the frontend.
    """
    estimate = merger.get("pre_notification")
    if not estimate or not estimate.get("id_issued_estimated"):
        return None
    if estimate.get("estimated_days") is None:
        return None
    if is_voluntary_period_notification(merger):
        return None

    confidence = _confidence(estimate)
    if estimate["estimated_days"] <= 0:
        return {"kind": "none", "start_date": None, "confidence": confidence}

    kind = "around"
    if estimate.get("basis") == "upper-bound-only":
        kind = "after"
    elif estimate.get("basis") == "lower-bound-only":
        kind = "before"
    return {"kind": kind, "start_date": estimate["id_issued_estimated"], "confidence": confidence}


def _entry(merger: dict) -> dict:
    entry = list_out._lightweight(merger)
    entry["pre_notification"] = pre_notification_summary(merger)
    return entry


def generate(mergers: list, output_dir: Path) -> int:
    """Write the API's merger list. Returns the merger count.

    Ordered and laid out like list.json (one merger per line, by notification
    date) so a pipeline commit diffs per matter. Deliberately no generation
    timestamp: it would make every run a diff. Clients wanting freshness have
    each entry's ``page_modified_datetime`` and the response's ETag.
    """
    out_dir = Path(output_dir) / API_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    entries = [_entry(m) for m in mergers]
    entries.sort(key=lambda e: e.get("effective_notification_datetime") or "")

    header = json.dumps(
        {"version": "v1", "licence": LICENCE, "attribution": ATTRIBUTION},
        ensure_ascii=False, separators=(",", ":"),
    )[:-1]  # reopen the object to append the list
    lines = ",\n".join(
        json.dumps(e, ensure_ascii=False, separators=(",", ":")) for e in entries
    )
    with open(out_dir / API_FILE, "w", encoding="utf-8") as f:
        f.write(header + ',"mergers":[\n' + lines + "\n]}\n")
    return len(entries)
