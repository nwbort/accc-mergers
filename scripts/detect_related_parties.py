#!/usr/bin/env python3
"""Detect likely "related parties" — one real-world entity recorded under more
than one name or ABN across the merger register.

Background
----------
``data/processed/related_parties.json`` records canonical *groups* of party
identities that are really the same entity (e.g. ``COLES GROUP LIMITED`` and
``COLES SUPERMARKETS AUSTRALIA PTY LTD``). The static-data pipeline uses those
groups to turn each party on a merger detail page into a link that searches the
register for every merger involving the same entity.

This script looks through every acquirer / target / other party in the
processed merger data, clusters records that look like the same entity, and
reports clusters that aren't already captured in ``related_parties.json`` so they
can be reviewed and adopted.

Matching heuristic
------------------
Distinct ``(name, identifier)`` party records are unioned together when any of:

  * ``identifier`` match — same (normalised) ABN on differently-named records
    (a renamed entity); strongest signal.
  * ``name`` match — same (normalised) name with a differing or missing
    identifier (a data-entry inconsistency, often a missing ABN).
  * ``fuzzy`` — very similar normalised names that also share a distinctive
    token; weakest signal, gated by ``--fuzzy-threshold``.

A cluster is only reported when it contains at least two *distinct* identities
and none of its members already belong to a recorded group. Each candidate gets
a confidence score from its strongest signal.

Usage
-----
  python scripts/detect_related_parties.py [--summary]
  python scripts/detect_related_parties.py --apply-suggestions --pr-markdown pr_body.md

Exit code is 1 if new candidate groups are found (useful in CI), 0 otherwise.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path

from party_matching import (
    build_group_lookups,
    match_party,
    normalise_identifier,
    normalise_name,
)
from slug import slugify

SCRIPT_DIR = Path(__file__).parent
REPO_ROOT = SCRIPT_DIR.parent
DEFAULT_MERGERS = REPO_ROOT / "data" / "processed" / "mergers.json"
DEFAULT_PARTIES = REPO_ROOT / "data" / "processed" / "related_parties.json"

DEFAULT_FUZZY_THRESHOLD = 0.88

_REPO = "nwbort/accc-mergers"
_MERGERS_FYI_BASE = "https://mergers.fyi/mergers"
_PARTIES_PATH = "data/processed/related_parties.json"

# Tokens too generic to count as a "distinctive" shared token for fuzzy linking.
_GENERIC_TOKENS = {
    "the", "and", "of", "for", "services", "service", "company", "enterprises",
    "investments", "investment", "property", "properties", "developments",
    "development", "management", "partners", "capital", "industries", "industry",
}
_MIN_TOKEN_LEN = 4

# Signal labels, strongest first, with the confidence score they imply.
SIGNAL_IDENTIFIER = "identifier"
SIGNAL_NAME = "name"
SIGNAL_FUZZY = "fuzzy"
_SIGNAL_SCORES = {
    SIGNAL_IDENTIFIER: 0.95,
    SIGNAL_NAME: 0.90,
    SIGNAL_FUZZY: 0.80,
}
_SIGNAL_RANK = {SIGNAL_IDENTIFIER: 3, SIGNAL_NAME: 2, SIGNAL_FUZZY: 1}


# ---------------------------------------------------------------------------
# Party-record collection
# ---------------------------------------------------------------------------

class PartyRecord:
    """A distinct ``(display name, identifier)`` party seen across mergers."""

    __slots__ = ("name", "identifier", "norm_name", "norm_id", "merger_ids")

    def __init__(self, name: str, identifier: str):
        self.name = name
        self.identifier = identifier
        self.norm_name = normalise_name(name)
        self.norm_id = normalise_identifier(identifier)
        self.merger_ids: set[str] = set()

    @property
    def key(self) -> tuple[str, str]:
        # Key on the *normalised* identity so trivial spacing/case differences
        # collapse to one record.
        return (self.norm_name, self.norm_id)


def collect_party_records(mergers: list[dict]) -> dict[tuple[str, str], PartyRecord]:
    """Collect distinct party records keyed by ``(norm_name, norm_id)``."""
    records: dict[tuple[str, str], PartyRecord] = {}
    for merger in mergers:
        mid = merger.get("merger_id", "")
        for field in ("acquirers", "targets", "other_parties"):
            for party in merger.get(field) or []:
                name = (party.get("name") or "").strip()
                identifier = (party.get("identifier") or "").strip()
                if not normalise_name(name) and not normalise_identifier(identifier):
                    continue
                rec = PartyRecord(name, identifier)
                existing = records.get(rec.key)
                if existing is None:
                    records[rec.key] = rec
                    existing = rec
                if mid:
                    existing.merger_ids.add(mid)
    return records


# ---------------------------------------------------------------------------
# Clustering (union-find over party records)
# ---------------------------------------------------------------------------

class _UnionFind:
    def __init__(self, n: int):
        self.parent = list(range(n))

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra


def _significant_tokens(norm_name: str) -> set[str]:
    return {
        t for t in norm_name.split()
        if len(t) >= _MIN_TOKEN_LEN and t not in _GENERIC_TOKENS
    }


def _cluster(
    records: list[PartyRecord], fuzzy_threshold: float, enable_fuzzy: bool
) -> tuple[list[list[int]], dict[frozenset[int], str]]:
    """Union records by the matching rules.

    Returns ``(components, link_signals)`` where ``components`` is a list of
    index-lists and ``link_signals`` maps each unioned index pair to the signal
    that linked it (used to score the resulting group).

    The fuzzy pass is off unless ``enable_fuzzy`` is set: very-similar names
    routinely belong to *sibling* SPVs in one deal (``BidCo``/``MidCo``,
    ``OpCo I``/``OpCo II``) that are distinct entities, so it is too noisy to
    recommend automatically.
    """
    uf = _UnionFind(len(records))
    link_signals: dict[frozenset[int], str] = {}

    def link(i: int, j: int, signal: str) -> None:
        uf.union(i, j)
        link_signals[frozenset((i, j))] = signal

    # Exact identifier / name collisions (cheap, via buckets).
    by_id: dict[str, list[int]] = defaultdict(list)
    by_name: dict[str, list[int]] = defaultdict(list)
    for idx, rec in enumerate(records):
        if rec.norm_id:
            by_id[rec.norm_id].append(idx)
        if rec.norm_name:
            by_name[rec.norm_name].append(idx)

    for bucket in by_id.values():
        for j in bucket[1:]:
            link(bucket[0], j, SIGNAL_IDENTIFIER)
    for bucket in by_name.values():
        for j in bucket[1:]:
            link(bucket[0], j, SIGNAL_NAME)

    if not enable_fuzzy:
        return _components(uf, len(records)), link_signals

    # Fuzzy name matches (O(n^2) over records with a usable name — the register
    # is small, a few thousand records at most).
    named = [i for i, r in enumerate(records) if r.norm_name]
    token_sets = {i: _significant_tokens(records[i].norm_name) for i in named}
    for a_pos, i in enumerate(named):
        for j in named[a_pos + 1:]:
            if records[i].norm_name == records[j].norm_name:
                continue  # already handled as a name collision
            if not (token_sets[i] & token_sets[j]):
                continue  # require a shared distinctive token
            ratio = SequenceMatcher(None, records[i].norm_name, records[j].norm_name).ratio()
            if ratio >= fuzzy_threshold:
                link(i, j, SIGNAL_FUZZY)

    return _components(uf, len(records)), link_signals


def _components(uf: "_UnionFind", n: int) -> list[list[int]]:
    """Collect union-find components with more than one member."""
    groups: dict[int, list[int]] = defaultdict(list)
    for idx in range(n):
        groups[uf.find(idx)].append(idx)
    return [members for members in groups.values() if len(members) > 1]


# ---------------------------------------------------------------------------
# Candidate construction
# ---------------------------------------------------------------------------

def _component_signal(members: list[int], link_signals: dict[frozenset[int], str]) -> str:
    """Return the strongest signal that holds the component together."""
    member_set = set(members)
    best = SIGNAL_FUZZY
    best_rank = 0
    for pair, signal in link_signals.items():
        if pair <= member_set:
            rank = _SIGNAL_RANK[signal]
            if rank > best_rank:
                best, best_rank = signal, rank
    return best


def _is_distinct_cluster(records: list[PartyRecord]) -> bool:
    """True if the cluster spans more than one distinct name *or* identifier.

    A cluster of records that only differ by normalisation noise isn't an
    interesting "two names for one entity" finding.
    """
    names = {r.name.strip().lower() for r in records if r.name.strip()}
    ids = {r.norm_id for r in records if r.norm_id}
    return len(names) > 1 or len(ids) > 1


def _canonical_member(records: list[PartyRecord]) -> PartyRecord:
    """Pick the canonical record: shortest name (usually the cleanest form),
    tie-broken by the most mergers and then alphabetically for stability."""
    return min(records, key=lambda r: (len(r.name), -len(r.merger_ids), r.name))


def _title_case_name(name: str) -> str:
    """Turn an ALL-CAPS register name into a friendlier canonical display name."""
    cleaned = " ".join(name.split())
    if cleaned and cleaned == cleaned.upper():
        return cleaned.title()
    return cleaned


def build_candidate(
    records: list[PartyRecord], signal: str, existing_ids: set[str]
) -> dict:
    """Assemble a candidate-group dict from a cluster of party records."""
    records = sorted(records, key=lambda r: (-len(r.merger_ids), r.name))
    canonical = _canonical_member(records)
    canonical_name = _title_case_name(canonical.name)

    base_slug = slugify(canonical_name) or "party"
    slug = base_slug
    n = 2
    while slug in existing_ids:
        slug = f"{base_slug}-{n}"
        n += 1
    existing_ids.add(slug)

    members = [
        {
            "name": r.name,
            "identifier": r.identifier,
            "merger_count": len(r.merger_ids),
            "merger_ids": sorted(r.merger_ids),
        }
        for r in records
    ]
    return {
        "id": slug,
        "canonical_name": canonical_name,
        "signal": signal,
        "score": _SIGNAL_SCORES[signal],
        "merger_count": len({mid for r in records for mid in r.merger_ids}),
        "members": members,
    }


def find_candidates(
    mergers: list[dict],
    groups: list[dict],
    fuzzy_threshold: float = DEFAULT_FUZZY_THRESHOLD,
    enable_fuzzy: bool = False,
) -> list[dict]:
    """Return candidate group dicts not already captured in ``related_parties.json``."""
    by_identifier, by_name = build_group_lookups(groups)
    records_map = collect_party_records(mergers)
    records = list(records_map.values())

    components, link_signals = _cluster(records, fuzzy_threshold, enable_fuzzy)
    existing_ids = {g.get("id") for g in groups if g.get("id")}

    candidates: list[dict] = []
    for members in components:
        recs = [records[i] for i in members]
        # Skip clusters where any member already belongs to a recorded group —
        # those are either done or need manual extension, not a fresh suggestion.
        if any(
            match_party({"name": r.name, "identifier": r.identifier}, by_identifier, by_name)
            for r in recs
        ):
            continue
        if not _is_distinct_cluster(recs):
            continue
        signal = _component_signal(members, link_signals)
        candidates.append(build_candidate(recs, signal, existing_ids))

    # Stable, best-first ordering.
    candidates.sort(key=lambda c: (-c["score"], -c["merger_count"], c["canonical_name"]))
    return candidates


# ---------------------------------------------------------------------------
# Applying suggestions to related_parties.json
# ---------------------------------------------------------------------------

def _group_from_candidate(candidate: dict) -> dict:
    """Render a candidate as a group entry for related_parties.json."""
    return {
        "id": candidate["id"],
        "canonical_name": candidate["canonical_name"],
        "members": [
            {"name": m["name"], "identifier": m["identifier"]}
            for m in candidate["members"]
        ],
    }


def apply_suggestions(parties_path: Path, candidates: list[dict]) -> int:
    """Append candidate groups to related_parties.json in-place. Returns count added."""
    if parties_path.exists():
        with parties_path.open() as fh:
            data = json.load(fh)
    else:
        data = {"groups": []}
    data.setdefault("groups", [])
    data["groups"].extend(_group_from_candidate(c) for c in candidates)
    parties_path.parent.mkdir(parents=True, exist_ok=True)
    with parties_path.open("w") as fh:
        json.dump(data, fh, indent=2)
        fh.write("\n")
    return len(candidates)


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

_SIGNAL_BLURB = {
    SIGNAL_IDENTIFIER: "share an ABN but are recorded under different names",
    SIGNAL_NAME: "share a name but have a differing or missing ABN",
    SIGNAL_FUZZY: "have very similar names and a shared distinctive token",
}


def mergers_fyi_url(merger_id: str) -> str:
    return f"{_MERGERS_FYI_BASE}/{merger_id}"


def print_summary(candidates: list[dict]) -> None:
    if not candidates:
        print("No new related-party candidates found.")
        return
    print(f"Found {len(candidates)} candidate group(s):")
    print()
    for c in candidates:
        print(f"  {c['canonical_name']}  (score {c['score']:.2f}, {c['signal']}, "
              f"{c['merger_count']} merger(s))")
        for m in c["members"]:
            ident = m["identifier"] or "—"
            print(f"    • {m['name']}  [{ident}]  ×{m['merger_count']}")
        print()


def build_pr_body(candidates: list[dict], date: str) -> str:
    """Build a markdown PR body recommending the candidate groups."""
    lines = [
        f"The daily detector found **{len(candidates)}** candidate related-party "
        f"group(s) on **{date}** that aren't yet recorded in "
        f"[`{_PARTIES_PATH}`](https://github.com/{_REPO}/blob/main/{_PARTIES_PATH}).",
        "",
        "Each group below is one real-world entity that appears under more than "
        "one name or ABN across the register. The change in this PR adds them to "
        "`related_parties.json`; once merged, each matching party on a merger "
        "detail page links to the register filtered by the group's canonical name.",
        "",
        "Review each group, **edit or remove any that are wrong**, then merge.",
        "",
        "---",
        "",
    ]
    for c in candidates:
        lines.append(f"### {c['canonical_name']}  ·  `id: {c['id']}`")
        lines.append("")
        lines.append(
            f"_Linked because these records {_SIGNAL_BLURB[c['signal']]} "
            f"(confidence {c['score']:.2f})._"
        )
        lines.append("")
        lines.append("| Name | ABN / ID | Mergers |")
        lines.append("|------|----------|---------|")
        for m in c["members"]:
            ident = (m["identifier"] or "—").replace("|", "\\|")
            name = m["name"].replace("|", "\\|")
            merger_links = ", ".join(
                f"[{mid}]({mergers_fyi_url(mid)})" for mid in m["merger_ids"]
            )
            lines.append(f"| {name} | {ident} | {merger_links} |")
        lines.append("")
    lines.extend([
        "---",
        "",
        f"*Generated automatically by the [Detect Related Parties]"
        f"(https://github.com/{_REPO}/actions/workflows/detect-related-parties.yml) workflow.*",
    ])
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mergers", type=Path, default=DEFAULT_MERGERS)
    parser.add_argument("--parties", type=Path, default=DEFAULT_PARTIES)
    parser.add_argument(
        "--fuzzy",
        action="store_true",
        help="Also cluster very-similar names (noisy: catches sibling SPVs; off by default)",
    )
    parser.add_argument(
        "--fuzzy-threshold",
        type=float,
        default=DEFAULT_FUZZY_THRESHOLD,
        help=f"Min name similarity for a fuzzy link when --fuzzy is set (default {DEFAULT_FUZZY_THRESHOLD})",
    )
    parser.add_argument(
        "--summary", action="store_true", help="Print a human-readable summary"
    )
    parser.add_argument(
        "--json", type=Path, default=None,
        help="Write the candidate list as JSON to this path",
    )
    parser.add_argument(
        "--apply-suggestions", action="store_true", dest="apply_suggestions",
        help="Append candidate groups to the related_parties.json file in-place",
    )
    parser.add_argument(
        "--pr-markdown", type=Path, default=None, dest="pr_markdown",
        help="Write a PR body (markdown) recommending the candidates to this path",
    )
    args = parser.parse_args()

    if not args.mergers.exists():
        print(f"ERROR: mergers file not found: {args.mergers}", file=sys.stderr)
        return 2

    with args.mergers.open() as fh:
        raw = json.load(fh)
    mergers = raw if isinstance(raw, list) else raw.get("mergers", [])

    groups = []
    if args.parties.exists():
        with args.parties.open() as fh:
            groups = json.load(fh).get("groups", [])

    candidates = find_candidates(mergers, groups, args.fuzzy_threshold, args.fuzzy)

    if args.summary or not (args.json or args.apply_suggestions or args.pr_markdown):
        print_summary(candidates)

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        with args.json.open("w") as fh:
            json.dump({"count": len(candidates), "candidates": candidates}, fh, indent=2)

    if args.pr_markdown and candidates:
        from datetime import datetime, timezone
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        args.pr_markdown.parent.mkdir(parents=True, exist_ok=True)
        with args.pr_markdown.open("w") as fh:
            fh.write(build_pr_body(candidates, today))

    if args.apply_suggestions and candidates:
        added = apply_suggestions(args.parties, candidates)
        print(f"Added {added} candidate group(s) to {args.parties}", file=sys.stderr)

    return 1 if candidates else 0


if __name__ == "__main__":
    sys.exit(main())
