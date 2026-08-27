#!/usr/bin/env python3
"""Print a batch of mergers for manual related-party review.

This is the entry point for the recurring "link the next N mergers' related
parties" workflow: pick a rank range (newest-first, matching the order the
register is normally worked through), and for every merger in that range,
print each acquirer/target/other party alongside whether it already resolves
to a canonical group in ``data/processed/related_parties.json`` (via
``party_matching.match_party``), plus the full ``merger_description`` — the
usual source of the "X, a subsidiary of Y" / "together, Z" evidence used to
decide new groupings.

It deliberately does not decide or apply anything: read the output, form
candidate groupings (checking company filings/press releases where the
description doesn't spell out a relationship), get them approved, then apply
approved changes with ``party_matching.add_members_to_group`` /
``party_matching.create_group`` and ``party_matching.save_parties_doc`` (see
``scripts/tools/related_parties.py`` for the interactive equivalent, or write
a short one-off script importing those same functions).

Usage
-----
    # Mergers ranked 31st-40th by notification date, newest first (i.e. the
    # next batch after having covered the most recent 30):
    python -m scripts.detect.related_parties_batch --start 31 --count 10

    # Re-check specific mergers by id, e.g. after editing related_parties.json:
    python -m scripts.detect.related_parties_batch --ids MN-50032,MN-60031

    # Machine-readable form, for feeding into another script:
    python -m scripts.detect.related_parties_batch --start 31 --count 10 --json batch.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from scripts.merger_filters import DEFAULT_MERGERS_JSON, load_mergers, sort_by_notification_date
from scripts.detect.party_matching import DEFAULT_PARTIES_JSON, build_group_lookups, load_parties_doc, match_party

PARTY_ROLES = ("acquirers", "targets", "other_parties")


# ---------------------------------------------------------------------------
# Batch selection
# ---------------------------------------------------------------------------

def select_batch_by_rank(mergers: list[dict], start: int, count: int) -> list[dict]:
    """Return the ``count`` mergers ranked ``start``..``start+count-1``
    (1-based, newest-first by notification date).

    Raises ``ValueError`` if ``start`` or ``count`` isn't positive.
    """
    if start < 1:
        raise ValueError("--start is 1-based; must be >= 1")
    if count < 1:
        raise ValueError("--count must be >= 1")
    ordered = sort_by_notification_date(mergers)
    return ordered[start - 1: start - 1 + count]


def select_batch_by_ids(mergers: list[dict], ids: list[str]) -> list[dict]:
    """Return the mergers matching ``ids``, in the order ``ids`` were given.

    Raises ``KeyError`` listing any id not found in ``mergers``.
    """
    by_id = {m.get("merger_id"): m for m in mergers if m.get("merger_id")}
    missing = [mid for mid in ids if mid not in by_id]
    if missing:
        raise KeyError(f"Merger id(s) not found: {', '.join(missing)}")
    return [by_id[mid] for mid in ids]


# ---------------------------------------------------------------------------
# Party annotation
# ---------------------------------------------------------------------------

def annotate_parties(merger: dict, by_identifier: dict, by_name: dict) -> list[dict]:
    """Return every acquirer/target/other party on ``merger`` annotated with
    the canonical group it already matches, if any.

    Each entry is ``{"role", "name", "identifier", "group"}`` where ``group``
    is the matching group dict (with ``id`` / ``canonical_name``) or ``None``.
    """
    annotated = []
    for role in PARTY_ROLES:
        for party in merger.get(role) or []:
            group = match_party(party, by_identifier, by_name)
            annotated.append({
                "role": role,
                "name": party.get("name", ""),
                "identifier": party.get("identifier", ""),
                "group": {"id": group["id"], "canonical_name": group["canonical_name"]} if group else None,
            })
    return annotated


def build_batch(
    mergers: list[dict], groups: list[dict], start_rank: int, selected: list[dict]
) -> list[dict]:
    """Assemble the review batch: each selected merger with its rank and
    annotated parties, ready to print or serialise as JSON."""
    by_identifier, by_name = build_group_lookups(groups)
    batch = []
    for offset, merger in enumerate(selected):
        batch.append({
            "rank": start_rank + offset,
            "merger_id": merger.get("merger_id", ""),
            "merger_name": merger.get("merger_name", ""),
            "notification_date": merger.get("effective_notification_datetime")
            or merger.get("original_notification_datetime") or "",
            "stage": merger.get("stage", ""),
            "parties": annotate_parties(merger, by_identifier, by_name),
            "merger_description": merger.get("merger_description", ""),
        })
    return batch


# ---------------------------------------------------------------------------
# Text rendering
# ---------------------------------------------------------------------------

def format_batch_text(batch: list[dict]) -> str:
    lines: list[str] = []
    for entry in batch:
        lines.append(f"=== #{entry['rank']} {entry['merger_id']} - {entry['merger_name']} ===")
        lines.append(f"date: {entry['notification_date']}  stage: {entry['stage']}")
        lines.append("--- parties ---")
        for p in entry["parties"]:
            if p["group"]:
                tag = f"MATCHED -> {p['group']['canonical_name']} ({p['group']['id']})"
            else:
                tag = "UNMATCHED"
            lines.append(f"  [{p['role']}] {p['name']!r} id={p['identifier']!r}  {tag}")
        lines.append("--- description ---")
        lines.append(entry["merger_description"])
        lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--mergers", type=Path, default=DEFAULT_MERGERS_JSON)
    parser.add_argument("--parties", type=Path, default=DEFAULT_PARTIES_JSON)
    parser.add_argument(
        "--start", type=int, default=None,
        help="1-based rank (newest-first by notification date) of the first merger in the batch",
    )
    parser.add_argument(
        "--count", type=int, default=10,
        help="Number of mergers to include when using --start (default 10)",
    )
    parser.add_argument(
        "--ids", type=str, default=None,
        help="Comma-separated merger_ids to review instead of a --start/--count rank range",
    )
    parser.add_argument(
        "--json", type=Path, default=None,
        help="Write the batch as JSON to this path (also prints the human-readable form unless --quiet)",
    )
    parser.add_argument(
        "--quiet", action="store_true",
        help="Suppress the human-readable text output (only useful with --json)",
    )
    args = parser.parse_args()

    if not args.ids and args.start is None:
        parser.error("pass either --start (with optional --count) or --ids")
    if args.ids and args.start is not None:
        parser.error("--start and --ids are mutually exclusive")

    if not args.mergers.exists():
        print(f"ERROR: mergers file not found: {args.mergers}", file=sys.stderr)
        return 2

    mergers = load_mergers(args.mergers)
    doc = load_parties_doc(args.parties)

    try:
        if args.ids:
            ids = [i.strip() for i in args.ids.split(",") if i.strip()]
            selected = select_batch_by_ids(mergers, ids)
            start_rank = 0  # ids are unranked; rank column is meaningless here
        else:
            selected = select_batch_by_rank(mergers, args.start, args.count)
            start_rank = args.start
    except (ValueError, KeyError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    batch = build_batch(mergers, doc["groups"], start_rank, selected)

    if not args.quiet:
        print(format_batch_text(batch))

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        with args.json.open("w") as fh:
            json.dump(batch, fh, indent=2, ensure_ascii=False)
            fh.write("\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
