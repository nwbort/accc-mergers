#!/usr/bin/env python3
"""
Detect likely "related mergers" — an earlier application that was later
re-filed as a separate matter.

Background
----------
`data/processed/related_mergers.json` records pairs of merger IDs where one
matter was effectively re-filed as another. Two patterns are covered:

  * ``waiver_refiled`` — a `WA-*` waiver application was declined, then
    re-filed as an `MN-*` notification; and
  * ``suspended_refiled`` — a matter whose assessment was suspended is
    re-filed later (often, but not necessarily, under a fresh `MN-*` ID).

This script looks through the processed merger data for likely new pairs and
reports any that aren't already recorded.

Matching heuristic
------------------
Each pass pairs a "source" merger with a later "target" merger that share at
least one acquirer or target identifier (ABN/etc.), or have very similar
acquirer- and target-name strings, and where the target was filed after the
source (soft check — missing dates don't disqualify a pair).

  * Waiver pass — source is a `WA-*` with `accc_determination == "Not
    approved"`; target is any `MN-*`.
  * Suspended pass — source is any merger with
    `status == "Assessment suspended"`; target is any other merger.

Each candidate gets a confidence score; only pairs above `--threshold`
(default 0.70) are reported. Existing pairs listed in `related_mergers.json`
are filtered out.

Usage
-----
  python scripts/detect_related_mergers.py [--threshold 0.70] [--summary]
  python scripts/detect_related_mergers.py --apply-suggestions --pr-markdown pr_body.md

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

from constants import merger_status

SCRIPT_DIR = Path(__file__).parent
REPO_ROOT = SCRIPT_DIR.parent
DEFAULT_MERGERS = REPO_ROOT / "data" / "processed" / "mergers.json"
DEFAULT_RELATED = REPO_ROOT / "data" / "processed" / "related_mergers.json"

DEFAULT_THRESHOLD = 0.70
NAME_SIMILARITY_THRESHOLD = 0.75

# Pair types recorded in related_mergers.json (see its `_README`).
WAIVER_REFILED = "waiver_refiled"
SUSPENDED_REFILED = "suspended_refiled"

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
    """Return the set of (source, target) pairs already recorded.

    Each pair has the ``{"from", "to", "type"}`` shape (see
    ``related_mergers.json``).
    """
    if not path.exists():
        return set()
    with path.open() as fh:
        data = json.load(fh)
    pairs: set[tuple[str, str]] = set()
    for p in data.get("pairs", []):
        source = p.get("from")
        target = p.get("to")
        if source and target:
            pairs.add((source, target))
    return pairs


def _build_candidate(
    source: dict, target: dict, pair_type: str, score: float, diag: dict
) -> dict:
    """Assemble a candidate dict shared by both detection passes."""
    return {
        "type": pair_type,
        "source": source.get("merger_id"),
        "target": target.get("merger_id"),
        "source_name": source.get("merger_name", ""),
        "target_name": target.get("merger_name", ""),
        "source_filed": source.get("effective_notification_datetime"),
        "target_filed": target.get("effective_notification_datetime"),
        "source_determination": source.get("accc_determination"),
        "source_status": source.get("status"),
        "target_status": target.get("status"),
        "score": round(score, 3),
        "signals": diag,
    }


def find_waiver_candidates(
    mergers: list[dict],
    known_pairs: set[tuple[str, str]],
    threshold: float,
) -> list[dict]:
    """Declined waiver (WA, "Not approved") → later notification (MN)."""
    known_sources = {s for s, _ in known_pairs}
    known_targets = {t for _, t in known_pairs}

    waivers = [
        m
        for m in mergers
        if m.get("merger_id", "").startswith("WA")
        and m.get("accc_determination") == "Not approved"
        and m.get("merger_id") not in known_sources
    ]
    notifications = [
        m
        for m in mergers
        if m.get("merger_id", "").startswith("MN")
        and m.get("merger_id") not in known_targets
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
                candidates.append(
                    _build_candidate(wa, mn, WAIVER_REFILED, score, diag)
                )
    return candidates


def find_suspended_candidates(
    mergers: list[dict],
    known_pairs: set[tuple[str, str]],
    threshold: float,
) -> list[dict]:
    """Suspended merger (any ID) → a later, separately-filed merger.

    Mirrors the waiver pass but keys off ``status == "Assessment suspended"``
    rather than the WA/"Not approved" combination, and is deliberately
    prefix-agnostic on both sides — a suspended matter may be refiled under a
    fresh ``MN`` (or any other) identifier.
    """
    known_sources = {s for s, _ in known_pairs}
    known_targets = {t for _, t in known_pairs}

    suspended = [
        m
        for m in mergers
        if m.get("status") == merger_status.ASSESSMENT_SUSPENDED
        and m.get("merger_id")
        and m.get("merger_id") not in known_sources
    ]
    others = [m for m in mergers if m.get("merger_id")]

    candidates: list[dict] = []
    for src in suspended:
        src_id = src.get("merger_id")
        src_date = parse_date(src.get("effective_notification_datetime"))
        for tgt in others:
            tgt_id = tgt.get("merger_id")
            # Never link a merger to itself, and skip already-recorded refiles.
            if tgt_id == src_id or tgt_id in known_targets:
                continue
            tgt_date = parse_date(tgt.get("effective_notification_datetime"))
            # Soft ordering check: a refile should be filed after the suspension.
            if src_date and tgt_date and tgt_date < src_date:
                continue
            score, diag = score_pair(src, tgt)
            if score >= threshold:
                candidates.append(
                    _build_candidate(src, tgt, SUSPENDED_REFILED, score, diag)
                )
    return candidates


def find_candidates(
    mergers: list[dict],
    known_pairs: set[tuple[str, str]],
    threshold: float,
) -> list[dict]:
    """Return candidate pair dicts from every detection pass, best-scored first."""
    candidates = find_waiver_candidates(mergers, known_pairs, threshold)
    candidates += find_suspended_candidates(mergers, known_pairs, threshold)

    # If one merger matches several partners, keep only the best per side.
    # Secondary keys keep the output stable across runs.
    candidates.sort(key=lambda c: (-c["score"], c["source"], c["target"]))
    seen_sources: set[str] = set()
    seen_targets: set[str] = set()
    deduped: list[dict] = []
    for c in candidates:
        if c["source"] in seen_sources or c["target"] in seen_targets:
            continue
        seen_sources.add(c["source"])
        seen_targets.add(c["target"])
        deduped.append(c)
    return deduped


# ---------------------------------------------------------------------------
# Reporting helpers
# ---------------------------------------------------------------------------

def mergers_fyi_url(merger_id: str) -> str:
    return f"{_MERGERS_FYI_BASE}/{merger_id}"


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
    """Canonical, parseable identifier for a candidate pair."""
    return f"{candidate['source']}/{candidate['target']}"


def _relationship_blurb(candidate: dict) -> str:
    """One-line description of the relationship pattern for the PR body."""
    if candidate["type"] == SUSPENDED_REFILED:
        return (
            "A matter whose assessment was **suspended** and which appears to "
            "have been **re-filed** as a separate matter."
        )
    return (
        "A matter initially filed as a **waiver** application, declined, then "
        "re-filed as a formal **notification**."
    )


# ---------------------------------------------------------------------------
# Applying suggestions to related_mergers.json
# ---------------------------------------------------------------------------

def _pair_from_candidate(candidate: dict) -> dict:
    """Render a candidate as a pair entry for related_mergers.json."""
    return {
        "from": candidate["source"],
        "to": candidate["target"],
        "type": candidate["type"],
    }


def write_related_mergers(path: Path, data: dict) -> None:
    """Write related_mergers.json, preserving the compact one-line-per-pair style."""
    pairs = data.get("pairs", [])
    lines = ["{"]
    if "_README" in data:
        lines.append(f"  {json.dumps('_README')}: {json.dumps(data['_README'])},")
    lines.append('  "pairs": [')
    for i, p in enumerate(pairs):
        trailing = "," if i < len(pairs) - 1 else ""
        lines.append(
            f'    {{ "from": "{p["from"]}", "to": "{p["to"]}", '
            f'"type": "{p.get("type", WAIVER_REFILED)}" }}{trailing}'
        )
    lines.append("  ]")
    lines.append("}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n")


def apply_suggestions(related_path: Path, candidates: list[dict]) -> int:
    """Append candidate pairs to related_mergers.json in-place. Returns count added."""
    if related_path.exists():
        with related_path.open() as fh:
            data = json.load(fh)
    else:
        data = {"pairs": []}
    data.setdefault("pairs", [])
    data["pairs"].extend(_pair_from_candidate(c) for c in candidates)
    write_related_mergers(related_path, data)
    return len(candidates)


# ---------------------------------------------------------------------------
# PR body construction
# ---------------------------------------------------------------------------

def build_pr_body(candidates: list[dict], date: str) -> str:
    """Build a markdown PR body recommending the candidate pairs."""
    related_blob = f"https://github.com/{_REPO}/blob/main/{_RELATED_PATH}"
    lines = [
        f"The daily detector found **{len(candidates)}** candidate related-merger "
        f"pair(s) on **{date}** that aren't yet recorded in "
        f"[`{_RELATED_PATH}`]({related_blob}).",
        "",
        "Each pair below is one matter that appears to have been re-filed as "
        "another. The change in this PR adds them to `related_mergers.json`; once "
        "merged, each merger detail page links to its related matter.",
        "",
        "Review each pair, **edit or remove any that are wrong**, then merge.",
        "",
        "---",
        "",
    ]
    for c in candidates:
        src, tgt = c["source"], c["target"]
        if c["type"] == SUSPENDED_REFILED:
            source_label = "Suspended matter"
            source_detail = f"status: {c['source_status'] or 'unknown'}"
            target_label = "Re-filed as"
            target_detail = f"status: {c['target_status'] or 'unknown'}"
        else:
            source_label = "Waiver"
            source_detail = f"determination: {c['source_determination'] or 'unknown'}"
            target_label = "Notification"
            target_detail = f"status: {c['target_status'] or 'unknown'}"

        lines.append(f"### `{src}` ↔ `{tgt}`  ·  `type: {c['type']}`")
        lines.append("")
        lines.append(
            f"_{_relationship_blurb(c)} (confidence {c['score']:.2f})._"
        )
        lines.append("")
        lines.append(
            f"- **{source_label}:** [{src} — {c['source_name']}]({mergers_fyi_url(src)}) "
            f"· filed {c['source_filed'] or 'unknown'} · {source_detail}"
        )
        lines.append(
            f"- **{target_label}:** [{tgt} — {c['target_name']}]({mergers_fyi_url(tgt)}) "
            f"· filed {c['target_filed'] or 'unknown'} · {target_detail}"
        )
        lines.append("")
        lines.append(f"**Signals:** {_format_signals(c['signals'])}")
        lines.append("")
    lines.extend([
        "---",
        "",
        f"*Generated automatically by the [Detect Related Mergers]"
        f"(https://github.com/{_REPO}/actions/workflows/detect-related-mergers.yml) workflow.*",
    ])
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def print_summary(candidates: list[dict], threshold: float) -> None:
    if not candidates:
        print("No new related-merger candidates found.")
        return
    print(f"Found {len(candidates)} candidate pair(s) above threshold {threshold}:")
    print()
    for c in candidates:
        print(f"  {c['source']} ↔ {c['target']}  (score {c['score']:.2f}, {c['type']})")
        print(f"    source : {c['source_name']}")
        print(f"    target : {c['target_name']}")
        print(f"    signals: {_format_signals(c['signals'])}")
        print()


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
        "--summary",
        action="store_true",
        help="Print a human-readable summary to stdout",
    )
    parser.add_argument(
        "--apply-suggestions",
        action="store_true",
        dest="apply_suggestions",
        help="Append candidate pairs to the related_mergers.json file in-place",
    )
    parser.add_argument(
        "--pr-markdown",
        type=Path,
        default=None,
        dest="pr_markdown",
        help="Write a PR body (markdown) recommending the candidates to this path",
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

    if args.summary or not (args.apply_suggestions or args.pr_markdown):
        print_summary(candidates, args.threshold)

    if args.pr_markdown and candidates:
        from datetime import timezone
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        args.pr_markdown.parent.mkdir(parents=True, exist_ok=True)
        with args.pr_markdown.open("w") as fh:
            fh.write(build_pr_body(candidates, today))

    if args.apply_suggestions and candidates:
        added = apply_suggestions(args.related, candidates)
        print(f"Added {added} candidate pair(s) to {args.related}", file=sys.stderr)

    return 1 if candidates else 0


if __name__ == "__main__":
    sys.exit(main())
