#!/usr/bin/env python3
"""
Generate 'similar mergers' suggestions for each merger.

For each merger, finds up to 3 other mergers that share parties or industries.
Party overlap is the primary signal; industry overlap is secondary.

Scoring
-------
  * Exact identifier match (ABN/ACN) on any party:   returns 1.0 immediately
  * Best name similarity across all party pairs:      up to 0.90
  * Significant shared words in party names:          up to 0.60 (0.25 per word)
  * Shared ANZSIC code (Jaccard × 0.25):             up to 0.25

  Party score = max(name_similarity × 0.9, word_overlap_score)
  Total       = party_score + industry_score
  Threshold   = 0.30; top MAX_RESULTS kept per merger

Output
------
  data/processed/similar_mergers.json
  Format: { "_note": "...", "_generated": "...", "similar": { "MN-XXXXX": ["MN-YYYYY", ...] } }

Usage
-----
  python scripts/generate_similar_mergers.py           # incremental (skip already-computed)
  python scripts/generate_similar_mergers.py --all     # full recompute
  python scripts/generate_similar_mergers.py --merger-id MN-01016
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
REPO_ROOT = SCRIPT_DIR.parent
DEFAULT_MERGERS = REPO_ROOT / "data" / "processed" / "mergers.json"
DEFAULT_RELATED = REPO_ROOT / "data" / "processed" / "related_mergers.json"
DEFAULT_OUTPUT = REPO_ROOT / "data" / "processed" / "similar_mergers.json"

MAX_RESULTS = 3
SCORE_THRESHOLD = 0.30

# ---------------------------------------------------------------------------
# Normalisation helpers (mirrors detect_related_mergers.py)
# ---------------------------------------------------------------------------

_COMPANY_SUFFIXES = re.compile(
    r"\b(pty|ltd|limited|inc|llc|l\.l\.c\.|gmbh|b\.v\.|bv|nv|plc|co|corp|"
    r"corporation|holdings|group|international|australia|the trustee for|trustee for)\b",
    re.IGNORECASE,
)

# Generic business words that shouldn't drive party similarity
_WORD_STOP = frozenset({
    'energy', 'services', 'solutions', 'management', 'capital', 'resources',
    'enterprises', 'investments', 'properties', 'technologies', 'healthcare',
    'media', 'finance', 'financial', 'digital', 'retail', 'network', 'trust',
    'fund', 'asset', 'assets', 'super', 'super', 'pension',
})


def _normalise_name(name: str) -> str:
    if not name:
        return ""
    out = name.lower()
    out = _COMPANY_SUFFIXES.sub(" ", out)
    out = re.sub(r"[^\w\s]", " ", out)
    out = re.sub(r"\s+", " ", out).strip()
    return out


def _normalise_identifier(identifier: str) -> str:
    if not identifier:
        return ""
    return re.sub(r"\s+", "", identifier).upper()


def _significant_words(names: list[str]) -> set[str]:
    """Return significant words (≥4 chars, not generic) from normalised party names."""
    words: set[str] = set()
    for name in names:
        for word in name.split():
            if len(word) >= 4 and word not in _WORD_STOP:
                words.add(word)
    return words


def _all_parties(merger: dict) -> list[dict]:
    return (
        merger.get("acquirers", [])
        + merger.get("targets", [])
        + merger.get("other_parties", [])
    )


# ---------------------------------------------------------------------------
# Similarity scoring
# ---------------------------------------------------------------------------

def score_similarity(a: dict, b: dict) -> float:
    """Score how similar two mergers are. Rough range: 0.0 – 1.25."""
    a_parties = _all_parties(a)
    b_parties = _all_parties(b)

    # Exact identifier match → definite similarity (short-circuit)
    a_ids = {_normalise_identifier(p.get("identifier", "")) for p in a_parties if p.get("identifier")}
    b_ids = {_normalise_identifier(p.get("identifier", "")) for p in b_parties if p.get("identifier")}
    if a_ids & b_ids:
        return 1.0

    # Normalised party names
    a_names = [_normalise_name(p.get("name", "")) for p in a_parties if p.get("name")]
    b_names = [_normalise_name(p.get("name", "")) for p in b_parties if p.get("name")]

    # Best sequence-based name similarity (any-to-any pair)
    best_name_sim = 0.0
    for an in a_names:
        for bn in b_names:
            if an and bn:
                s = SequenceMatcher(None, an, bn).ratio()
                if s > best_name_sim:
                    best_name_sim = s

    # Significant-word overlap — catches "Coles X" vs "Coles Y" type matches
    a_words = _significant_words(a_names)
    b_words = _significant_words(b_names)
    shared = a_words & b_words
    word_score = min(len(shared) * 0.25, 0.60)

    party_score = max(best_name_sim * 0.9, word_score)

    # ANZSIC industry overlap (Jaccard × 0.25)
    a_codes = {c.get("code") for c in a.get("anzsic_codes", []) if c.get("code")}
    b_codes = {c.get("code") for c in b.get("anzsic_codes", []) if c.get("code")}
    if a_codes and b_codes:
        industry_score = len(a_codes & b_codes) / len(a_codes | b_codes) * 0.25
    else:
        industry_score = 0.0

    return party_score + industry_score


def find_similar(
    target: dict,
    all_mergers: list[dict],
    exclude_ids: set[str],
    max_results: int = MAX_RESULTS,
    threshold: float = SCORE_THRESHOLD,
) -> list[str]:
    """Return up to max_results merger_ids most similar to target."""
    target_id = target.get("merger_id", "")
    scored: list[tuple[float, str]] = []

    for candidate in all_mergers:
        cid = candidate.get("merger_id", "")
        if not cid or cid == target_id or cid in exclude_ids:
            continue
        score = score_similarity(target, candidate)
        if score >= threshold:
            scored.append((score, cid))

    scored.sort(key=lambda x: (-x[0], x[1]))
    return [mid for _, mid in scored[:max_results]]


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------

def _load_mergers(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    return raw if isinstance(raw, list) else raw.get("mergers", [])


def _load_existing(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f).get("similar", {})
    except (json.JSONDecodeError, IOError):
        return {}


def _load_related_partner_map(path: Path) -> dict[str, str]:
    """Return {merger_id: direct_partner_id} for all related-merger pairs.

    Both directions are mapped so each merger knows its own direct partner.
    """
    if not path.exists():
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        result: dict[str, str] = {}
        for pair in data.get("pairs", []):
            source = pair.get("from", "")
            target = pair.get("to", "")
            if source and target:
                result[source] = target
                result[target] = source
        return result
    except (json.JSONDecodeError, IOError):
        return {}


def _save_output(path: Path, similar: dict) -> None:
    payload = {
        "_note": (
            "Auto-generated by scripts/generate_similar_mergers.py. "
            "Up to 3 similar mergers per merger_id. "
            "Run with --all to fully refresh."
        ),
        "_generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "similar": similar,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--mergers", type=Path, default=DEFAULT_MERGERS)
    parser.add_argument("--related", type=Path, default=DEFAULT_RELATED,
                        help="related_mergers.json path (related-merger pairs to exclude)")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--all", action="store_true",
                        help="Recompute similar mergers for all mergers (full refresh)")
    parser.add_argument("--merger-id", metavar="ID",
                        help="Only compute similar mergers for this specific merger ID")
    parser.add_argument("--threshold", type=float, default=SCORE_THRESHOLD,
                        help=f"Minimum similarity score to include (default: {SCORE_THRESHOLD})")
    parser.add_argument("--max", type=int, default=MAX_RESULTS, dest="max_results",
                        help=f"Maximum results per merger (default: {MAX_RESULTS})")
    args = parser.parse_args()

    if not args.mergers.exists():
        print(f"ERROR: mergers file not found: {args.mergers}", file=sys.stderr)
        return 2

    all_mergers = _load_mergers(args.mergers)
    merger_index = {m.get("merger_id"): m for m in all_mergers if m.get("merger_id")}

    # Related-merger pairs are already surfaced via related_merger; exclude each
    # merger's direct partner so we don't double-surface that link.
    related_partners = _load_related_partner_map(args.related)

    existing = _load_existing(args.output)

    if args.merger_id:
        if args.merger_id not in merger_index:
            print(f"ERROR: merger {args.merger_id!r} not found", file=sys.stderr)
            return 2
        targets = [merger_index[args.merger_id]]
    elif args.all:
        targets = all_mergers
        existing = {}
    else:
        # Incremental: only process mergers not yet in the output file
        targets = [m for m in all_mergers if m.get("merger_id") not in existing]
        if not targets:
            print("No new mergers to process. Use --all to refresh all.")
            return 0

    print(f"Computing similar mergers for {len(targets)} merger(s)...")
    similar = dict(existing)

    for target in targets:
        tid = target.get("merger_id", "")
        if not tid:
            continue
        # Exclude the merger's direct related-merger partner — that relationship
        # is already surfaced via the related_merger link above the page fold.
        exclude: set[str] = set()
        if tid in related_partners:
            exclude.add(related_partners[tid])

        results = find_similar(
            target, all_mergers,
            exclude_ids=exclude,
            max_results=args.max_results,
            threshold=args.threshold,
        )
        similar[tid] = results
        if results:
            print(f"  {tid}: {results}")
        else:
            print(f"  {tid}: (none)")

    _save_output(args.output, similar)
    print(f"\n✓ Saved {len(similar)} entries to {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
