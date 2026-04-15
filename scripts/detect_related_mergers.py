#!/usr/bin/env python3
"""
Detect likely "related mergers" — waiver applications that were declined and
then re-filed as formal notifications.

Background
----------
`data/processed/related_mergers.json` manually maps each `WA-*` waiver ID to
the `MN-*` notification ID that followed it after the waiver was declined.
This script looks through the processed merger data for likely new pairs and
reports any that aren't already recorded.

Matching heuristic
------------------
A candidate pair is (waiver, notification) where:

  * the waiver has `merger_id` starting with `WA-` and
    `accc_determination == "Not approved"`, and
  * the notification has `merger_id` starting with `MN-`, and
  * the two share at least one acquirer or target identifier (ABN/etc.), or
    have very similar acquirer- and target-name strings, and
  * the notification was filed after the waiver (soft check — missing dates
    don't disqualify a pair).

Each candidate gets a confidence score; only pairs above `--threshold`
(default 0.70) are reported. Existing pairs listed in `related_mergers.json`
are filtered out.

Usage
-----
  python scripts/detect_related_mergers.py [--threshold 0.70] [--json PATH]

Exit code is 1 if new candidate pairs are found (useful in CI), 0 otherwise.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
REPO_ROOT = SCRIPT_DIR.parent
DEFAULT_MERGERS = REPO_ROOT / "data" / "processed" / "mergers.json"
DEFAULT_RELATED = REPO_ROOT / "data" / "processed" / "related_mergers.json"

DEFAULT_THRESHOLD = 0.70
NAME_SIMILARITY_THRESHOLD = 0.75

_REPO = "nwbort/accc-mergers"
_MERGERS_FYI_BASE = "https://mergers.fyi/mergers"
_RELATED_PATH = "data/processed/related_mergers.json"


# ---------------------------------------------------------------------------
# Normalisation helpers
# ---------------------------------------------------------------------------

_COMPANY_SUFFIXES = re.compile(
    r"\b(pty|ltd|limited|inc|llc|l\.l\.c\.|gmbh|b\.v\.|bv|nv|plc|co|corp|"
    r"corporation|holdings|group|international|australia|the trustee for|trustee for)\b",
    re.IGNORECASE,
)


def normalise_name(name: str) -> str:
    """Lower-case, strip company suffixes and punctuation for fuzzy match."""
    if not name:
        return ""
    out = name.lower()
    out = _COMPANY_SUFFIXES.sub(" ", out)
    out = re.sub(r"[^\w\s]", " ", out)
    out = re.sub(r"\s+", " ", out).strip()
    return out


def normalise_identifier(identifier: str) -> str:
    """Strip whitespace/punctuation from an ABN/ACN-style identifier."""
    if not identifier:
        return ""
    return re.sub(r"\s+", "", identifier).upper()


def extract_identifiers(entities: list[dict]) -> set[str]:
    return {
        normalise_identifier(e.get("identifier", ""))
        for e in entities
        if e.get("identifier")
    }


def extract_names(entities: list[dict]) -> list[str]:
    return [normalise_name(e.get("name", "")) for e in entities if e.get("name")]


def best_name_similarity(a_names: list[str], b_names: list[str]) -> float:
    if not a_names or not b_names:
        return 0.0
    best = 0.0
    for a in a_names:
        for b in b_names:
            if not a or not b:
                continue
            s = SequenceMatcher(None, a, b).ratio()
            if s > best:
                best = s
    return best


def parse_date(raw: str | None):
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def score_pair(waiver: dict, notification: dict) -> tuple[float, dict]:
    """
    Compute a confidence score for a WA/MN pair and return diagnostic info.

    The score is in [0.0, 1.0]:
      * Shared identifier on both acquirer and target → 1.00
      * Shared identifier on one side only            → 0.80
      * No shared identifier, but strong name overlap → up to 0.75
    """
    wa_acq_ids = extract_identifiers(waiver.get("acquirers", []))
    wa_tgt_ids = extract_identifiers(waiver.get("targets", []))
    mn_acq_ids = extract_identifiers(notification.get("acquirers", []))
    mn_tgt_ids = extract_identifiers(notification.get("targets", []))

    acq_id_overlap = bool(wa_acq_ids & mn_acq_ids)
    tgt_id_overlap = bool(wa_tgt_ids & mn_tgt_ids)

    wa_acq_names = extract_names(waiver.get("acquirers", []))
    wa_tgt_names = extract_names(waiver.get("targets", []))
    mn_acq_names = extract_names(notification.get("acquirers", []))
    mn_tgt_names = extract_names(notification.get("targets", []))

    acq_name_sim = best_name_similarity(wa_acq_names, mn_acq_names)
    tgt_name_sim = best_name_similarity(wa_tgt_names, mn_tgt_names)

    merger_name_sim = SequenceMatcher(
        None,
        normalise_name(waiver.get("merger_name", "")),
        normalise_name(notification.get("merger_name", "")),
    ).ratio()

    if acq_id_overlap and tgt_id_overlap:
        score = 1.00
    elif acq_id_overlap or tgt_id_overlap:
        # Require the non-overlapping side to at least plausibly match by name
        other_side_sim = tgt_name_sim if acq_id_overlap else acq_name_sim
        if other_side_sim >= NAME_SIMILARITY_THRESHOLD or merger_name_sim >= NAME_SIMILARITY_THRESHOLD:
            score = 0.85
        else:
            score = 0.65
    else:
        if (
            acq_name_sim >= NAME_SIMILARITY_THRESHOLD
            and tgt_name_sim >= NAME_SIMILARITY_THRESHOLD
        ):
            score = min(0.75, (acq_name_sim + tgt_name_sim) / 2)
        elif merger_name_sim >= 0.90:
            score = 0.70
        else:
            score = 0.0

    diag = {
        "acq_id_overlap": acq_id_overlap,
        "tgt_id_overlap": tgt_id_overlap,
        "acq_name_sim": round(acq_name_sim, 3),
        "tgt_name_sim": round(tgt_name_sim, 3),
        "merger_name_sim": round(merger_name_sim, 3),
    }
    return score, diag


# ---------------------------------------------------------------------------
# Detection driver
# ---------------------------------------------------------------------------

def load_related_pairs(path: Path) -> set[tuple[str, str]]:
    """Return the set of (waiver, notification) pairs already recorded."""
    if not path.exists():
        return set()
    with path.open() as fh:
        data = json.load(fh)
    return {
        (p["waiver"], p["notification"])
        for p in data.get("pairs", [])
        if p.get("waiver") and p.get("notification")
    }


def find_candidates(
    mergers: list[dict],
    known_pairs: set[tuple[str, str]],
    threshold: float,
) -> list[dict]:
    """Return a list of candidate pair dicts, sorted by score (descending)."""
    known_waivers = {w for w, _ in known_pairs}
    known_notifs = {n for _, n in known_pairs}

    waivers = [
        m
        for m in mergers
        if m.get("merger_id", "").startswith("WA")
        and m.get("accc_determination") == "Not approved"
        and m.get("merger_id") not in known_waivers
    ]
    notifications = [
        m
        for m in mergers
        if m.get("merger_id", "").startswith("MN")
        and m.get("merger_id") not in known_notifs
    ]

    candidates: list[dict] = []
    for wa in waivers:
        wa_date = parse_date(wa.get("effective_notification_datetime"))
        for mn in notifications:
            mn_date = parse_date(mn.get("effective_notification_datetime"))
            # Soft ordering check: if both dates are known, MN should be after WA
            if wa_date and mn_date and mn_date < wa_date:
                continue
            score, diag = score_pair(wa, mn)
            if score >= threshold:
                candidates.append({
                    "waiver": wa.get("merger_id"),
                    "notification": mn.get("merger_id"),
                    "waiver_name": wa.get("merger_name", ""),
                    "notification_name": mn.get("merger_name", ""),
                    "waiver_filed": wa.get("effective_notification_datetime"),
                    "notification_filed": mn.get("effective_notification_datetime"),
                    "waiver_determination": wa.get("accc_determination"),
                    "notification_status": mn.get("status"),
                    "score": round(score, 3),
                    "signals": diag,
                })

    # If a waiver matches multiple notifications, keep only the best per side.
    # Secondary keys keep the output stable across runs.
    candidates.sort(key=lambda c: (-c["score"], c["waiver"], c["notification"]))
    seen_waivers: set[str] = set()
    seen_notifs: set[str] = set()
    deduped: list[dict] = []
    for c in candidates:
        if c["waiver"] in seen_waivers or c["notification"] in seen_notifs:
            continue
        seen_waivers.add(c["waiver"])
        seen_notifs.add(c["notification"])
        deduped.append(c)
    return deduped


# ---------------------------------------------------------------------------
# Issue body construction
# ---------------------------------------------------------------------------

def mergers_fyi_url(merger_id: str) -> str:
    return f"{_MERGERS_FYI_BASE}/{merger_id}"


def edit_related_mergers_url(branch: str = "main") -> str:
    return f"https://github.com/{_REPO}/edit/{branch}/{_RELATED_PATH}"


def json_line_for(candidate: dict) -> str:
    """Render the exact line to paste into the `pairs` array of related_mergers.json."""
    return (
        f'    {{ "waiver": "{candidate["waiver"]}", '
        f'"notification": "{candidate["notification"]}" }},'
    )


def _format_signals(signals: dict) -> str:
    bits = []
    if signals["acq_id_overlap"]:
        bits.append("shared acquirer ID")
    if signals["tgt_id_overlap"]:
        bits.append("shared target ID")
    bits.append(f"acquirer name sim {signals['acq_name_sim']:.2f}")
    bits.append(f"target name sim {signals['tgt_name_sim']:.2f}")
    bits.append(f"merger name sim {signals['merger_name_sim']:.2f}")
    return "; ".join(bits)


def pair_id(candidate: dict) -> str:
    """Canonical, parseable identifier used in titles and for de-duplication."""
    return f"{candidate['waiver']}/{candidate['notification']}"


def build_issue_title(candidate: dict) -> str:
    wa = candidate["waiver"]
    mn = candidate["notification"]
    # The `WA-XXXX/MN-XXXX` substring is the marker the workflow greps for
    # to decide whether an issue already exists for this pair.
    name = candidate.get("waiver_name") or candidate.get("notification_name") or ""
    base = f"Related mergers: {wa}/{mn}"
    if name:
        base = f"{base} — {name}"
    # GitHub issue title limit is 256 chars
    if len(base) > 240:
        base = base[:237] + "..."
    return base


def build_issue_body(candidate: dict, branch: str = "main") -> str:
    wa = candidate["waiver"]
    mn = candidate["notification"]
    edit_url = edit_related_mergers_url(branch)
    related_blob = f"https://github.com/{_REPO}/blob/{branch}/{_RELATED_PATH}"

    lines = [
        f"<!-- pair-id: {pair_id(candidate)} -->",
        f"The daily detector thinks **`{wa}`** and **`{mn}`** look like a "
        f"related-merger pair that isn't yet in "
        f"[`{_RELATED_PATH}`]({related_blob}).",
        "",
        "A \"related merger\" is one that was initially filed as a **waiver** "
        "application, declined, then re-filed as a formal **notification** "
        "(see the `_README` field in the JSON).",
        "",
        "## The two mergers",
        "",
        f"- **Waiver:** [{wa} — {candidate['waiver_name']}]({mergers_fyi_url(wa)}) "
        f"· filed {candidate['waiver_filed'] or 'unknown'} · determination: "
        f"{candidate['waiver_determination'] or 'unknown'}",
        f"- **Notification:** [{mn} — {candidate['notification_name']}]({mergers_fyi_url(mn)}) "
        f"· filed {candidate['notification_filed'] or 'unknown'} · status: "
        f"{candidate['notification_status'] or 'unknown'}",
        "",
        f"**Match confidence:** {candidate['score']:.2f}  ",
        f"**Signals:** {_format_signals(candidate['signals'])}",
        "",
        "## To accept this suggestion",
        "",
        f"1. [**Open `related_mergers.json` for editing on GitHub →**]({edit_url})",
        "2. Paste the following line into the `pairs` array:",
        "",
        "```json",
        json_line_for(candidate),
        "```",
        "",
        "3. Commit on `main` (or via a PR) — the next run will then see the "
        "pair is recorded and will auto-close this issue.",
        "",
        "## If this isn't a real pair",
        "",
        "Just close the issue. The workflow treats any closed issue for this "
        "pair as a permanent \"no\" and will not re-raise it on future runs.",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mergers", type=Path, default=DEFAULT_MERGERS)
    parser.add_argument("--related", type=Path, default=DEFAULT_RELATED)
    parser.add_argument(
        "--threshold",
        type=float,
        default=DEFAULT_THRESHOLD,
        help=f"Minimum confidence score to report (default {DEFAULT_THRESHOLD})",
    )
    parser.add_argument(
        "--branch",
        default="main",
        help="Branch name used in GitHub links within issue bodies",
    )
    parser.add_argument(
        "--issue-json",
        type=Path,
        default=None,
        help="If set, write a JSON payload (candidates + per-pair title/body + "
        "recorded_pairs) to this path, for use by the workflow.",
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Print a human-readable summary to stdout",
    )
    args = parser.parse_args()

    if not args.mergers.exists():
        print(f"ERROR: mergers file not found: {args.mergers}", file=sys.stderr)
        return 2

    with args.mergers.open() as fh:
        raw = json.load(fh)
    mergers = raw if isinstance(raw, list) else raw.get("mergers", [])

    known = load_related_pairs(args.related)
    candidates = find_candidates(mergers, known, args.threshold)

    if args.summary or not args.issue_json:
        if not candidates:
            print("No new related-merger candidates found.")
        else:
            print(f"Found {len(candidates)} candidate pair(s) above threshold {args.threshold}:")
            print()
            for c in candidates:
                print(f"  {c['waiver']} ↔ {c['notification']}  (score {c['score']:.2f})")
                print(f"    waiver       : {c['waiver_name']}")
                print(f"    notification : {c['notification_name']}")
                print(f"    signals      : {_format_signals(c['signals'])}")
                print()

    if args.issue_json:
        enriched = []
        for c in candidates:
            enriched.append({
                **c,
                "pair_id": pair_id(c),
                "title": build_issue_title(c),
                "body": build_issue_body(c, args.branch),
            })
        payload = {
            "count": len(enriched),
            "candidates": enriched,
            # Pairs already recorded in related_mergers.json — used by the
            # workflow to produce nicer close messages when an open issue's
            # pair has been recorded since it was raised.
            "recorded_pairs": sorted(f"{w}/{n}" for w, n in known),
        }
        args.issue_json.parent.mkdir(parents=True, exist_ok=True)
        with args.issue_json.open("w") as fh:
            json.dump(payload, fh, indent=2)

    return 1 if candidates else 0


if __name__ == "__main__":
    sys.exit(main())
