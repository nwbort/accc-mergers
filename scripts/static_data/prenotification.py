"""Estimate how long a notification sat in pre-notification before it was filed.

Parties work with the ACCC on a draft notification before filing it, and that
pre-notification stage never appears on the register: the first public date a
merger has is the day it was formally notified. The merger ID leaks it anyway.

Method
------
An ACCC merger ID is ``<kind>-<group><seq>`` — ``MN-01016`` is kind ``MN``,
group ``01``, sequence ``16``. There are 20 groups (``01``, ``05``, ``10`` …
``95``), a case is assigned to one on some basis we can't see, and each group
carries its own counter. Two facts make the counter useful:

* **The counter is shared between merger notifications and waiver
  applications.** No sequence number is ever used by both an ``MN-`` and a
  ``WA-`` ID in the same group, so waivers and notifications interleave on one
  timeline.
* **The number is issued when the case is opened, not when it is filed.** A
  notification's ID is therefore stamped at the *start* of pre-notification.

So within a group, ``seq(A) < seq(B)`` implies A's ID was issued before B's,
and since B cannot have been notified before its own ID existed:

    issued(A) <= issued(B) <= notified(B)

If A was nonetheless notified *after* B, the gap is pre-notification A must
have spent, giving a hard lower bound:

    pre_notification(A) >= notified(A) - min{ notified(B) : seq(B) > seq(A) }

Waivers pin this down much harder. A waiver application has no pre-notification
stage — it is lodged when it is opened — so a waiver's notification date dates
the counter directly. The nearest waiver *above* a notification's sequence
number bounds when its ID was issued from above (the lower bound on
pre-notification), and the nearest waiver *below* bounds it from below (the
upper bound), bracketing the period from both sides.

Why we trust the ordering
-------------------------
The bounds only hold if sequence numbers really are issued in time order, and
waivers test that independently: since they are filed on issue, waiver-vs-waiver
pairs should almost never appear out of order, and on the current data they
invert 0.9% of the time (and waiver-then-notification pairs 0.1%). Inversions
concentrate in pairs whose *earlier* ID is a notification — 21% for
notification-then-waiver — which is the pre-notification period showing through
rather than noise in the counter.

Unlike :mod:`static_data.phase1_estimate`, these estimates are **not** frozen.
A bound is only as tight as the cases sitting above and below it in the
counter, so it genuinely improves as later IDs surface; recomputing every run
is the point.
"""

import re
from datetime import date, timedelta

from date_utils import parse_iso_datetime

# A waiver is treated as filed the day its ID was issued, which is what lets it
# date the counter. That is very nearly true — 95% of waivers have no provable
# lag at all — but not exactly, so the upper bound carries slack covering
# roughly the 90th percentile of the lag that *is* provable (p90 28d, max 34d
# across the waivers that show one). Slack only ever widens the upper bound;
# the lower bound doesn't depend on it.
WAIVER_LODGEMENT_SLACK_DAYS = 28

# Bump when the method changes so stored values are recognisable.
METHOD_VERSION = 1

# MN-01016 -> kind "MN", group "01", sequence 16.
_ID_PATTERN = re.compile(r"^(?P<kind>[A-Z]{2})-(?P<group>\d{2})(?P<seq>\d{3})$")


def parse_merger_id(merger_id: str) -> tuple[str, str, int] | None:
    """Split a merger ID into ``(kind, group, sequence)``.

    Returns ``None`` for anything that isn't a well-formed ID, so a stray or
    hand-entered value can't silently land in the wrong group's counter.
    """
    match = _ID_PATTERN.match((merger_id or "").strip())
    if not match:
        return None
    return match["kind"], match["group"], int(match["seq"])


def filing_date(merger: dict) -> date | None:
    """The day the matter was actually lodged — the end of pre-notification.

    Prefers the original notification date over the effective one: where the
    two differ the ACCC has moved the effective date after the fact, which
    changes the review clock but not when the parties filed.
    """
    raw = merger.get("original_notification_datetime") or merger.get(
        "effective_notification_datetime"
    )
    parsed = parse_iso_datetime(raw)
    return parsed.date() if parsed else None


def _counter_positions(mergers: list) -> list[dict]:
    """Every merger that has both a place on a group counter and a filing date."""
    positions = []
    for merger in mergers:
        parsed = parse_merger_id(merger.get("merger_id", ""))
        filed = filing_date(merger)
        if not parsed or not filed:
            continue
        kind, group, seq = parsed
        positions.append(
            {
                "merger_id": merger["merger_id"],
                "kind": kind,
                "group": group,
                "seq": seq,
                "filed": filed,
                "merger": merger,
            }
        )
    return positions


def _issued_before(group: list[dict], seq: int) -> tuple[date, str] | None:
    """Tightest evidence that an ID at ``seq`` was issued before some date.

    Any case further up the counter was issued later and cannot have been
    notified before its own ID existed, so the earliest filing date above
    ``seq`` is an upper bound on when this ID was issued.
    """
    above = [p for p in group if p["seq"] > seq]
    if not above:
        return None
    best = min(above, key=lambda p: (p["filed"], p["seq"]))
    return best["filed"], best["merger_id"]


def _issued_after(group: list[dict], seq: int, slack: int) -> tuple[date, str] | None:
    """Tightest evidence that an ID at ``seq`` was issued after some date.

    Only waivers can supply this: they are lodged when they are opened, so a
    waiver below ``seq`` on the counter had its ID issued — and therefore this
    one did too — no earlier than its own filing date, less slack.
    """
    below = [p for p in group if p["seq"] < seq and p["kind"] == "WA"]
    if not below:
        return None
    best = max(below, key=lambda p: (p["filed"], p["seq"]))
    return best["filed"] - timedelta(days=slack), best["merger_id"]


def _interpolate_issue_date(group: list[dict], seq: int) -> date | None:
    """Read an ID's issue date off the counter, between the waivers around it.

    The nearest waiver on each side of ``seq`` dates two points on the group's
    counter; a sequence number between them is dated by advancing linearly from
    one to the other.
    """
    below = [p for p in group if p["seq"] < seq and p["kind"] == "WA"]
    above = [p for p in group if p["seq"] > seq and p["kind"] == "WA"]
    if not below or not above:
        return None
    start, end = max(below, key=lambda p: p["seq"]), min(above, key=lambda p: p["seq"])
    steps = end["seq"] - start["seq"]
    if steps <= 0:
        return None
    fraction = (seq - start["seq"]) / steps
    return start["filed"] + (end["filed"] - start["filed"]) * fraction


def compute_estimate(
    position: dict, group: list[dict], slack: int = WAIVER_LODGEMENT_SLACK_DAYS
) -> dict | None:
    """Bound and estimate one notification's pre-notification period, in days.

    ``None`` when the counter says nothing about this case — it sits at the top
    of its group with nothing above it and no waiver below it.
    """
    filed = position["filed"]
    upper_witness = _issued_before(group, position["seq"])
    lower_witness = _issued_after(group, position["seq"], slack)
    if not upper_witness and not lower_witness:
        return None

    min_days = max_days = None
    issued_before = issued_after = None
    if upper_witness:
        issued_before = min(upper_witness[0], filed)
        min_days = (filed - issued_before).days
    if lower_witness:
        issued_after = min(lower_witness[0], filed)
        max_days = (filed - issued_after).days

    # Both sides known: read the issue date off the counter by interpolating
    # between the waivers bracketing this sequence number, then clamp it into
    # the range the bounds already proved. Falls back to the midpoint of the
    # bounds when no pair of waivers brackets the case.
    if issued_before is not None and issued_after is not None:
        interpolated = _interpolate_issue_date(group, position["seq"])
        if interpolated is None:
            interpolated = issued_after + (issued_before - issued_after) / 2
        issued = min(max(interpolated, issued_after), issued_before)
        estimated_days = (filed - issued).days
        basis = "bracketed"
    elif min_days is not None:
        estimated_days = min_days
        basis = "lower-bound-only"
    else:
        estimated_days = max_days
        basis = "upper-bound-only"

    return {
        "estimated_days": estimated_days,
        "min_days": min_days,
        "max_days": max_days,
        "id_issued_before": issued_before.isoformat() if issued_before else None,
        "id_issued_after": issued_after.isoformat() if issued_after else None,
        "min_days_witness": upper_witness[1] if upper_witness else None,
        "max_days_witness": lower_witness[1] if lower_witness else None,
        "basis": basis,
        "method_version": METHOD_VERSION,
    }


def attach_prenotification_estimates(
    enriched: list, slack: int = WAIVER_LODGEMENT_SLACK_DAYS
) -> int:
    """Attach ``pre_notification`` to each notification in-place; return the count.

    Waiver applications get no estimate of their own — they are the anchors the
    notifications are measured against, so measuring one against the others
    would only restate the assumption that they're filed on issue.
    """
    positions = _counter_positions(enriched)
    groups: dict[str, list[dict]] = {}
    for position in positions:
        groups.setdefault(position["group"], []).append(position)

    attached = 0
    for position in positions:
        if position["kind"] != "MN":
            continue
        estimate = compute_estimate(position, groups[position["group"]], slack)
        if estimate is None:
            continue
        position["merger"]["pre_notification"] = estimate
        attached += 1
    return attached
