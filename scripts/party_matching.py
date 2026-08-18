"""Shared helpers for matching merger parties to canonical "related party" groups.

A *party* (an acquirer, target or other party recorded against a merger) is
sometimes the same real-world entity captured under more than one name or ABN —
e.g. ``COLES GROUP LIMITED`` and ``COLES SUPERMARKETS AUSTRALIA PTY LTD`` are
both Coles. ``data/processed/related_parties.json`` records these as canonical
*groups*; this module is the single source of truth for

  (a) how party names / identifiers are normalised for comparison,
  (b) how a party record is matched back to a group, and
  (c) how groups themselves are loaded, saved and mutated (new group, add
      members, unique id generation),

so that the daily detector (``detect_related_parties.py``), the hand-editing
web UI (``scripts/tools/related_parties.py``) and any one-off review script
all agree on what counts as a match and never diverge on how the file is
written back to disk.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from slug import slugify

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
DEFAULT_PARTIES_JSON = REPO_ROOT / "data" / "processed" / "related_parties.json"

# Company-form suffixes and boilerplate words that carry no identifying signal.
# Single source of truth — detect_related_mergers.py imports normalise_name too.
_COMPANY_SUFFIXES = re.compile(
    r"\b(pty|ltd|limited|inc|llc|l\.l\.c\.|gmbh|b\.v\.|bv|nv|plc|co|corp|"
    r"corporation|holdings|group|international|australia|"
    r"the trustee for|trustee for)\b",
    re.IGNORECASE,
)


def normalise_name(name: str) -> str:
    """Lower-case a party name and strip company suffixes/punctuation for matching.

    Returns an empty string when no usable characters remain.
    """
    if not name:
        return ""
    out = name.lower()
    out = _COMPANY_SUFFIXES.sub(" ", out)
    out = re.sub(r"[^\w\s]", " ", out)
    out = re.sub(r"\s+", " ", out).strip()
    return out


_PLACEHOLDER_IDENTIFIERS = {"NA", "NONE", "UNKNOWN"}


def normalise_identifier(identifier: str) -> str:
    """Strip whitespace/punctuation from an ABN/ACN-style identifier.

    Placeholder values like "N/A" recorded for parties with no known ABN
    normalise to a non-empty string ("NA"), which would otherwise make every
    such party look like a shared-identifier match for every other one.
    """
    if not identifier:
        return ""
    cleaned = re.sub(r"[^0-9A-Za-z]", "", identifier).upper()
    if cleaned in _PLACEHOLDER_IDENTIFIERS:
        return ""
    return cleaned


def build_group_lookups(groups: list[dict]) -> tuple[dict, dict]:
    """Build ``(by_identifier, by_name)`` lookups from a list of group dicts.

    Each group has the shape::

        {"id": "coles", "canonical_name": "Coles Group",
         "members": [{"name": ..., "identifier": ...}, ...]}

    The returned dicts map a normalised identifier / name to the *group* dict it
    belongs to. The first group to claim a given key wins (groups should not
    overlap; if they do, this keeps behaviour deterministic).
    """
    by_identifier: dict[str, dict] = {}
    by_name: dict[str, dict] = {}
    for group in groups:
        for member in group.get("members", []):
            ident = normalise_identifier(member.get("identifier", ""))
            if ident:
                by_identifier.setdefault(ident, group)
            name = normalise_name(member.get("name", ""))
            if name:
                by_name.setdefault(name, group)
    return by_identifier, by_name


def match_party(party: dict, by_identifier: dict, by_name: dict) -> dict | None:
    """Return the group a party belongs to, or ``None``.

    Identifier matches take precedence over name matches because an ABN is a
    stronger signal than a (possibly mistyped) name.
    """
    ident = normalise_identifier(party.get("identifier", ""))
    if ident and ident in by_identifier:
        return by_identifier[ident]
    name = normalise_name(party.get("name", ""))
    if name and name in by_name:
        return by_name[name]
    return None


def dedupe_members(members: list[dict]) -> list[dict]:
    """Drop exact duplicate (normalised name, normalised identifier) members,
    keeping the first display form seen."""
    seen: set[tuple[str, str]] = set()
    out: list[dict] = []
    for m in members:
        name = (m.get("name") or "").strip()
        identifier = (m.get("identifier") or "").strip()
        if not name and not identifier:
            continue
        key = (normalise_name(name), normalise_identifier(identifier))
        if key in seen:
            continue
        seen.add(key)
        out.append({"name": name, "identifier": identifier})
    return out


def merge_groups(groups: list[dict], group_ids: list[str], canonical_name: str = "") -> list[dict]:
    """Merge the groups identified by ``group_ids`` into a single group.

    The merged group keeps the id of ``group_ids[0]`` (the caller's own
    ordering, not whatever order the groups happen to be stored in); the rest
    are folded into it (members combined and de-duplicated) and dropped.
    ``canonical_name``, if given, becomes the merged group's display name;
    otherwise the kept group's own name is used.

    Returns a new list — ``groups`` is not mutated. Raises ``ValueError`` if
    fewer than two distinct ids are given, or ``KeyError`` if any id is not
    found in ``groups``.
    """
    ids = list(dict.fromkeys(group_ids))
    if len(ids) < 2:
        raise ValueError("merge_groups needs at least two distinct group ids")

    by_id = {g.get("id"): g for g in groups}
    missing = [gid for gid in ids if gid not in by_id]
    if missing:
        raise KeyError(f"Group(s) not found: {', '.join(missing)}")

    keep_id = ids[0]
    keep = by_id[keep_id]
    merge_set = set(ids)
    merging = [g for g in groups if g.get("id") in merge_set]

    combined_members: list[dict] = []
    for g in merging:
        combined_members.extend(g.get("members", []))
    merged_members = dedupe_members(combined_members)
    merged_name = (canonical_name or "").strip() or keep.get("canonical_name", "")

    result = []
    for g in groups:
        gid = g.get("id")
        if gid == keep_id:
            new_g = dict(g)
            new_g["members"] = merged_members
            new_g["canonical_name"] = merged_name
            result.append(new_g)
        elif gid in merge_set:
            continue
        else:
            result.append(g)
    return result


# ---------------------------------------------------------------------------
# Loading, saving and mutating related_parties.json
# ---------------------------------------------------------------------------
#
# These are the single implementation behind both the hand-editing web UI
# (scripts/tools/related_parties.py) and any one-off review/apply script, so
# a fix made here (e.g. the ensure_ascii write below) benefits every caller.

def load_parties_doc(path: Path | str = DEFAULT_PARTIES_JSON) -> dict:
    """Load related_parties.json, preserving the whole document (incl. _README).

    Returns ``{"groups": []}`` if the file doesn't exist yet.
    """
    path = Path(path)
    if path.exists():
        with path.open() as fh:
            doc = json.load(fh)
    else:
        doc = {"groups": []}
    doc.setdefault("groups", [])
    return doc


def save_parties_doc(doc: dict, path: Path | str = DEFAULT_PARTIES_JSON) -> None:
    """Write related_parties.json back to disk.

    Uses ``ensure_ascii=False`` so accented/non-Latin characters already in
    the file (e.g. "Société", "L'Oréal") round-trip as literal UTF-8 rather
    than being rewritten as ``\\uXXXX`` escapes on every save.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as fh:
        json.dump(doc, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def unique_group_id(canonical_name: str, existing_ids: set[str]) -> str:
    """Generate a slug id for ``canonical_name`` that doesn't collide with
    ``existing_ids``, appending ``-2``, ``-3``, ... as needed."""
    base = slugify(canonical_name) or "party"
    slug = base
    n = 2
    while slug in existing_ids:
        slug = f"{base}-{n}"
        n += 1
    return slug


def add_members_to_group(groups: list[dict], group_id: str, new_members: list[dict]) -> dict:
    """Add ``new_members`` to the group with ``group_id``, de-duplicating.

    Mutates the matching group dict in place (and therefore ``groups``) and
    returns it. Raises ``KeyError`` if no group has that id.
    """
    group = next((g for g in groups if g.get("id") == group_id), None)
    if group is None:
        raise KeyError(f"Group not found: {group_id}")
    group["members"] = dedupe_members(list(group.get("members", [])) + new_members)
    return group


def create_group(
    groups: list[dict],
    canonical_name: str,
    members: list[dict],
    group_id: str | None = None,
) -> dict:
    """Build a new canonical group from ``members``, append it to ``groups``,
    and return it.

    Generates a unique slug id from ``canonical_name`` unless ``group_id`` is
    given. Raises ``ValueError`` if no members remain after de-duplication.
    """
    deduped = dedupe_members(members)
    if not deduped:
        raise ValueError("A group needs at least one member.")
    existing_ids = {g.get("id") for g in groups if g.get("id")}
    gid = group_id or unique_group_id(canonical_name, existing_ids)
    group = {"id": gid, "canonical_name": canonical_name, "members": deduped}
    groups.append(group)
    return group
