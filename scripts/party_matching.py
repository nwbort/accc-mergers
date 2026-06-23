"""Shared helpers for matching merger parties to canonical "related party" groups.

A *party* (an acquirer, target or other party recorded against a merger) is
sometimes the same real-world entity captured under more than one name or ABN —
e.g. ``COLES GROUP LIMITED`` and ``COLES SUPERMARKETS AUSTRALIA PTY LTD`` are
both Coles. ``data/processed/related_parties.json`` records these as canonical
*groups*; this module is the single source of truth for

  (a) how party names / identifiers are normalised for comparison, and
  (b) how a party record is matched back to a group,

so that the daily detector (``detect_related_parties.py``) and the static-data
pipeline (``static_data.enrichment``) always agree on what counts as a match.
"""

from __future__ import annotations

import re

# Company-form suffixes and boilerplate words that carry no identifying signal.
# Kept deliberately in sync with the equivalent list in detect_related_mergers.py.
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


def normalise_identifier(identifier: str) -> str:
    """Strip whitespace/punctuation from an ABN/ACN-style identifier."""
    if not identifier:
        return ""
    return re.sub(r"[^0-9A-Za-z]", "", identifier).upper()


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
