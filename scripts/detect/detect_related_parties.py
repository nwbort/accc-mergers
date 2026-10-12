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
  * ``name_variant`` — names that are identical apart from punctuation, spacing
    or case (e.g. ``Francisco Partners Management, L.P`` and ``... LP``). As
    reliable as a name match, so it runs by default too.
  * ``fuzzy`` — very similar normalised names that also share a distinctive
    token; weakest signal, gated by ``--fuzzy-threshold``. The fuzzy pass skips
    pairs that differ only by a sibling-distinguishing token (a number, roman
    numeral, compass point, ``-co`` role, or state code) so it stops
    recommending distinct vehicles from one deal (``BidCo``/``MidCo``,
    ``No. 1``/``No. 2``, ``WA1``/``WA2``).

A cluster is only reported when it contains at least two *distinct* identities
and none of its members already belong to a recorded group. Each candidate gets
a confidence score from its strongest signal.

High-confidence candidates
--------------------------
A narrower test than the signal, ``is_high_confidence``, picks out candidates
safe to record without a human reviewing the PR first. The pipeline merges a
batch made up entirely of these and opens a verification issue instead (see
``--meta-json`` / ``--issue-markdown``). The signal alone is not enough: a
``name`` match strips suffixes like "Australia" and "Corporation", so it links
``SONY AUSTRALIA LIMITED`` to ``Sony Corporation``, and a shared identifier is
regularly a copy-pasted ABN on two unrelated vehicles in one deal.

Usage
-----
  python -m scripts.detect.detect_related_parties [--summary]
  python -m scripts.detect.detect_related_parties --apply-suggestions --pr-markdown pr_body.md

Exit code is 1 if new candidate groups are found (useful in CI), 0 otherwise.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path

from scripts.constants.site import REPO as _REPO, mergers_fyi_url
from scripts.merger_filters import load_mergers
from scripts.detect.party_matching import (
    build_group_lookups,
    load_parties_doc,
    match_party,
    normalise_identifier,
    normalise_name,
    save_parties_doc,
)
from scripts.slug import slugify
from scripts.paths import REPO_ROOT

DEFAULT_MERGERS = REPO_ROOT / "data" / "processed" / "mergers.json"
DEFAULT_PARTIES = REPO_ROOT / "data" / "processed" / "related_parties.json"

DEFAULT_FUZZY_THRESHOLD = 0.88

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
SIGNAL_NAME_VARIANT = "name_variant"
SIGNAL_FUZZY = "fuzzy"
_SIGNAL_SCORES = {
    SIGNAL_IDENTIFIER: 0.95,
    SIGNAL_NAME: 0.90,
    SIGNAL_NAME_VARIANT: 0.90,
    SIGNAL_FUZZY: 0.80,
}
_SIGNAL_RANK = {
    SIGNAL_IDENTIFIER: 4, SIGNAL_NAME: 3, SIGNAL_NAME_VARIANT: 2, SIGNAL_FUZZY: 1,
}

# Tokens that mark a genuinely *distinct* sibling entity rather than a name
# variant: numbered / lettered SPVs, roman numerals, compass points, the
# structural "-co" roles that differ between vehicles in one deal, and
# state/country codes. The fuzzy pass refuses to link a pair whose names differ
# only by tokens like these.
_ROMAN_NUMERALS = {
    "i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x", "xi", "xii",
}
_DIRECTIONS = {
    "north", "south", "east", "west",
    "northern", "southern", "eastern", "western", "central",
}
_NUMBER_WORDS = {
    "first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth",
    "ninth", "tenth", "one", "two", "three", "four", "five", "six", "seven",
    "eight", "nine", "ten",
}
_SPV_ROLES = {
    "bidco", "midco", "topco", "holdco", "opco", "propco", "finco", "newco",
    "aggco", "gp", "lp", "op", "prop", "mm", "sub", "blocker", "mid",
}
_GEO_CODES = {
    "vic", "nsw", "qld", "wa", "sa", "nt", "act", "tas",
    "aus", "au", "uk", "us", "usa", "nz", "eu", "apac",
}
_STATE_NUMBER = re.compile(r"[a-z]{0,4}\d+")


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


def _squash_name(name: str) -> str:
    """Reduce a name to just its lower-cased alphanumerics.

    Two names with the same squash are identical apart from punctuation,
    spacing and case — ``Francisco Partners Management, L.P`` and ``... LP``
    both squash to ``franciscopartnersmanagementlp`` — so they are one entity
    written two ways, not merely similar. Sibling vehicles that differ by any
    real token (``... No. 1`` / ``... No. 2``) never collide here.
    """
    return re.sub(r"[^a-z0-9]", "", (name or "").lower())


def _is_distinguishing_token(tok: str) -> bool:
    """True if ``tok`` only tells two sibling vehicles apart (a number, roman
    numeral, compass point, ``-co`` role or state/country code)."""
    if tok in _ROMAN_NUMERALS or tok in _DIRECTIONS or tok in _NUMBER_WORDS:
        return True
    if tok in _SPV_ROLES or tok in _GEO_CODES:
        return True
    # A bare ordinal ("2") or a short-prefixed number ("wa1", "ak2", "no3").
    return bool(_STATE_NUMBER.fullmatch(tok))


def _differs_only_by_sibling_token(norm_a: str, norm_b: str) -> bool:
    """True if two normalised names differ *only* by distinguishing tokens.

    ``Swan Bidco`` vs ``Swan Midco``, ``... No. 1`` vs ``... No. 3`` and
    ``Smile Partners (WA1)`` vs ``... (WA2)`` are separate vehicles in one
    structure, not one entity under two names. The fuzzy pass uses this to stop
    recommending such siblings.
    """
    sym = set(norm_a.split()) ^ set(norm_b.split())
    return bool(sym) and all(_is_distinguishing_token(t) for t in sym)


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
        key = frozenset((i, j))
        prev = link_signals.get(key)
        # A pair can qualify under several rules (identical names also squash
        # equal); keep the strongest so the group is scored on its best signal.
        if prev is None or _SIGNAL_RANK[signal] > _SIGNAL_RANK[prev]:
            link_signals[key] = signal

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

    # Punctuation/spacing/case-only name variants (e.g. "L.P" vs "LP"). These
    # are as trustworthy as an exact-name match — a differing token would break
    # the squash — so they run by default rather than only under --fuzzy.
    by_squash: dict[str, list[int]] = defaultdict(list)
    for idx, rec in enumerate(records):
        squashed = _squash_name(rec.name)
        if squashed:
            by_squash[squashed].append(idx)
    for bucket in by_squash.values():
        for j in bucket[1:]:
            link(bucket[0], j, SIGNAL_NAME_VARIANT)

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
            if _differs_only_by_sibling_token(records[i].norm_name, records[j].norm_name):
                continue  # distinct sibling vehicle, not one entity twice
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
    """Pick the canonical record: the one appearing in the most mergers,
    tie-broken by the shortest name (usually the cleanest form) and then
    alphabetically for stability."""
    return min(records, key=lambda r: (-len(r.merger_ids), len(r.name), r.name))


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


def _has_digit(identifier: str) -> bool:
    return any(ch.isdigit() for ch in identifier)


def is_high_confidence(candidate: dict) -> bool:
    """True if a candidate is one entity beyond reasonable doubt.

    Either:

    * every member's name is identical apart from punctuation, spacing and
      case, and the members carry no two *different* identifiers
      (``Eurazeo S.E.`` / ``Eurazeo SE``); or
    * every member carries the same identifier, and every other member's name
      merely extends the shortest one (``AUSTRALIANSUPER PTY LTD`` /
      ``AUSTRALIANSUPER PTY LTD atf AustralianSuper``, ``... (Administrators
      Appointed)``, ``... trading as ...``).

    Deliberately excluded: a shared identifier on names that diverge
    (``Hermes Bidco`` / ``Hermes TopCo``), which is as often a copied ABN as a
    renamed entity, and a ``name`` match that only holds once suffixes like
    "Australia" are stripped.
    """
    members = candidate.get("members") or []
    if len(members) < 2:
        return False
    squashed = [_squash_name(m.get("name", "")) for m in members]
    if not all(squashed):
        return False
    ids = [normalise_identifier(m.get("identifier", "")) for m in members]
    distinct_ids = {i for i in ids if i}

    if len(set(squashed)) == 1:
        return len(distinct_ids) <= 1

    if not all(ids) or len(distinct_ids) != 1:
        return False
    if not _has_digit(next(iter(distinct_ids))):
        return False  # "NASDAQTECH"-style junk in the identifier field
    shortest = min(squashed, key=len)
    return all(s.startswith(shortest) for s in squashed)


def find_group_merge_candidates(
    groups: list[dict],
    fuzzy_threshold: float = DEFAULT_FUZZY_THRESHOLD,
    enable_fuzzy: bool = True,
) -> list[dict]:
    """Find existing canonical groups that look like the same real-world
    entity and should be merged into one.

    Where ``find_candidates`` clusters *ungrouped* parties, this clusters
    every member across *all* recorded groups using the same matching rules
    and reports clusters that span more than one group id — i.e. the same
    identifier/name/fuzzy match shows up under two different canonical
    groups, most often because they were recorded separately before either
    was noticed to be the same entity.
    """
    records: list[PartyRecord] = []
    owners: list[str] = []
    for g in groups:
        gid = g.get("id", "")
        for m in g.get("members", []):
            name = (m.get("name") or "").strip()
            identifier = (m.get("identifier") or "").strip()
            if not normalise_name(name) and not normalise_identifier(identifier):
                continue
            records.append(PartyRecord(name, identifier))
            owners.append(gid)

    components, link_signals = _cluster(records, fuzzy_threshold, enable_fuzzy)
    by_id = {g.get("id"): g for g in groups}

    candidates: list[dict] = []
    for members in components:
        group_ids = sorted({owners[i] for i in members})
        if len(group_ids) < 2:
            continue  # cluster is entirely within one group already
        signal = _component_signal(members, link_signals)
        candidates.append({
            "group_ids": group_ids,
            "groups": [
                {"id": gid, "canonical_name": by_id[gid].get("canonical_name", "")}
                for gid in group_ids
            ],
            "signal": signal,
            "score": _SIGNAL_SCORES[signal],
        })

    candidates.sort(key=lambda c: (-c["score"], c["group_ids"]))
    return candidates


def _member_key(member: dict) -> tuple[str, str]:
    """The ``PartyRecord.key`` a stored ``{name, identifier}`` member stands for."""
    return (
        normalise_name(member.get("name") or ""),
        normalise_identifier(member.get("identifier") or ""),
    )


def find_candidates(
    mergers: list[dict],
    groups: list[dict],
    fuzzy_threshold: float = DEFAULT_FUZZY_THRESHOLD,
    enable_fuzzy: bool = False,
    rejected: list[dict] | None = None,
) -> list[dict]:
    """Return candidate group dicts not already captured in ``related_parties.json``.

    ``rejected`` is the file's ``rejected`` list: groups a person has said are
    *not* one entity. A cluster made up only of one rejected entry's members is
    not suggested again; one that has picked up a new member is.
    """
    rejected_keys = [
        {_member_key(m) for m in r.get("members", [])} for r in rejected or []
    ]
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
        keys = {r.key for r in recs}
        if any(keys <= rk for rk in rejected_keys):
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
    """Append candidate groups to related_parties.json in-place. Returns count added.

    Writes through ``save_parties_doc`` so accented/non-Latin characters already
    in the file round-trip as literal UTF-8; dumping the document here with the
    default ``ensure_ascii=True`` re-escaped every one of them on each run.
    """
    doc = load_parties_doc(parties_path)
    doc["groups"].extend(_group_from_candidate(c) for c in candidates)
    save_parties_doc(doc, parties_path)
    return len(candidates)


def reject_groups(parties_path: Path, group_ids: list[str], note: str = "") -> list[str]:
    """Move groups out of ``groups`` and into ``rejected``. Returns the ids moved.

    The undo for an auto-merged batch that turned out wrong (see
    revert-auto-merge.yml). Deleting the groups alone is not enough: the next
    run would re-detect the same high-confidence cluster and merge it straight
    back, so the members are remembered in ``rejected`` and ``find_candidates``
    skips them. Unknown ids are ignored — the group may already have been
    edited away by hand.
    """
    doc = load_parties_doc(parties_path)
    wanted = set(group_ids)
    kept, moved = [], []
    for g in doc["groups"]:
        (moved if g.get("id") in wanted else kept).append(g)
    if not moved:
        return []
    doc["groups"] = kept
    rejected = doc.setdefault("rejected", [])
    for g in moved:
        entry = {
            "canonical_name": g.get("canonical_name", ""),
            "members": [
                {"name": m.get("name", ""), "identifier": m.get("identifier", "")}
                for m in g.get("members", [])
            ],
        }
        if note:
            entry["note"] = note
        rejected.append(entry)
    save_parties_doc(doc, parties_path)
    return [g.get("id") for g in moved]


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

_SIGNAL_BLURB = {
    SIGNAL_IDENTIFIER: "share an ABN but are recorded under different names",
    SIGNAL_NAME: "share a name but have a differing or missing ABN",
    SIGNAL_NAME_VARIANT: "have the same name apart from punctuation or spacing",
    SIGNAL_FUZZY: "have very similar names and a shared distinctive token",
}


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


def print_group_merge_summary(candidates: list[dict]) -> None:
    if not candidates:
        print("No candidate group merges found.")
        return
    print(f"Found {len(candidates)} group(s) that look like the same entity:")
    print()
    for c in candidates:
        names = " / ".join(f"{g['canonical_name']} ({g['id']})" for g in c["groups"])
        print(f"  {names}  (score {c['score']:.2f}, {c['signal']})")
    print()


def build_pr_body(candidates: list[dict], date: str, auto_merge: bool = False) -> str:
    """Build a markdown PR body recommending the candidate groups.

    ``auto_merge`` says every candidate is high confidence (see
    ``is_high_confidence``), so the pipeline will merge the PR itself.
    """
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
    ]
    if auto_merge:
        lines += [
            "Every group here is **high confidence** (identical names apart "
            "from punctuation, or one name extending another under the same "
            "ABN), so this PR is merged automatically. A follow-up issue "
            "tracks manual verification.",
            "",
        ]
    else:
        lines += [
            "Review each group, **edit or remove any that are wrong**, then merge.",
            "",
        ]
    lines += [
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
        f"*Generated automatically by the related-parties step of the "
        f"[merger pipeline](https://github.com/{_REPO}/actions/workflows/pipeline.yml).*",
    ])
    return "\n".join(lines)


def build_issue_body(candidates: list[dict], date: str) -> str:
    """Build a markdown issue body asking for a sanity check of groups that
    were merged automatically because they are high confidence."""
    parties_blob = f"https://github.com/{_REPO}/blob/main/{_PARTIES_PATH}"
    lines = [
        f"The daily detector found **{len(candidates)}** high-confidence "
        f"related-party group(s) on **{date}** and merged them into "
        f"[`{_PARTIES_PATH}`]({parties_blob}) automatically.",
        "",
        "Please double-check each group below is one real-world entity.",
        "",
        "---",
        "",
    ]
    for c in candidates:
        lines.append(f"### {c['canonical_name']}  ·  `id: {c['id']}`")
        lines.append("")
        for m in c["members"]:
            ident = m["identifier"] or "no ABN"
            merger_links = ", ".join(
                f"[{mid}]({mergers_fyi_url(mid)})" for mid in m["merger_ids"]
            )
            lines.append(f"- **{m['name']}** · {ident} · {merger_links}")
        lines.append("")
    lines.extend([
        "---",
        "",
        f"*Generated automatically by the related-parties step of the "
        f"[merger pipeline](https://github.com/{_REPO}/actions/workflows/pipeline.yml).*",
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
    parser.add_argument(
        "--issue-markdown", type=Path, default=None, dest="issue_markdown",
        help="Write a verification-issue body (markdown) to this path, if every "
        "candidate found is high confidence (see is_high_confidence)",
    )
    parser.add_argument(
        "--meta-json", type=Path, default=None, dest="meta_json",
        help="Write JSON metadata ({count, certain_count, all_certain}) so CI "
        "can decide whether to auto-merge the suggestion PR",
    )
    parser.add_argument(
        "--reject-groups", nargs="+", default=None, dest="reject_groups", metavar="ID",
        help="Move these group ids from `groups` to `rejected` in --parties, so "
        "they are never suggested again, and exit",
    )
    parser.add_argument(
        "--reject-note", default="", dest="reject_note",
        help="Note stored on each entry moved by --reject-groups",
    )
    parser.add_argument(
        "--group-merge-candidates", action="store_true", dest="group_merge_candidates",
        help="Instead of detecting new groups, find existing groups in --parties "
        "that look like the same entity and should be merged (see related_parties.py)",
    )
    args = parser.parse_args()

    if args.reject_groups:
        moved = reject_groups(args.parties, args.reject_groups, args.reject_note)
        print(f"Rejected {len(moved)} group(s): {', '.join(moved) or 'none'}")
        return 0

    if not args.mergers.exists():
        print(f"ERROR: mergers file not found: {args.mergers}", file=sys.stderr)
        return 2

    mergers = load_mergers(args.mergers)

    groups, rejected = [], []
    if args.parties.exists():
        with args.parties.open() as fh:
            doc = json.load(fh)
        groups = doc.get("groups", [])
        rejected = doc.get("rejected", [])

    if args.group_merge_candidates:
        merge_candidates = find_group_merge_candidates(groups, args.fuzzy_threshold)
        print_group_merge_summary(merge_candidates)
        if args.json:
            args.json.parent.mkdir(parents=True, exist_ok=True)
            with args.json.open("w") as fh:
                json.dump(
                    {"count": len(merge_candidates), "candidates": merge_candidates},
                    fh, indent=2,
                )
        return 1 if merge_candidates else 0

    candidates = find_candidates(
        mergers, groups, args.fuzzy_threshold, args.fuzzy, rejected=rejected
    )

    if args.summary or not (args.json or args.apply_suggestions or args.pr_markdown):
        print_summary(candidates)

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        with args.json.open("w") as fh:
            json.dump({"count": len(candidates), "candidates": candidates}, fh, indent=2)

    certain = [c for c in candidates if is_high_confidence(c)]
    all_certain = bool(candidates) and len(certain) == len(candidates)

    from datetime import datetime, timezone
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    if args.pr_markdown and candidates:
        args.pr_markdown.parent.mkdir(parents=True, exist_ok=True)
        with args.pr_markdown.open("w") as fh:
            fh.write(build_pr_body(candidates, today, auto_merge=all_certain))

    if args.issue_markdown and all_certain:
        args.issue_markdown.parent.mkdir(parents=True, exist_ok=True)
        with args.issue_markdown.open("w") as fh:
            fh.write(build_issue_body(certain, today))

    if args.meta_json:
        args.meta_json.parent.mkdir(parents=True, exist_ok=True)
        with args.meta_json.open("w") as fh:
            json.dump(
                {
                    "count": len(candidates),
                    "certain_count": len(certain),
                    "all_certain": all_certain,
                },
                fh,
                indent=2,
            )

    if args.apply_suggestions and candidates:
        added = apply_suggestions(args.parties, candidates)
        print(f"Added {added} candidate group(s) to {args.parties}", file=sys.stderr)

    return 1 if candidates else 0


if __name__ == "__main__":
    sys.exit(main())
