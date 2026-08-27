"""Serial-acquirer ("creeping acquisitions") detection — ``serial-acquirers.json``.

Flags canonical acquirer groups with two or more notifications in the same
ANZSIC class/group within any rolling 12-month window — the pattern the new
merger regime's cumulative-turnover thresholds target.
"""

from datetime import datetime

from scripts.date_utils import parse_iso_datetime
from scripts.detect.party_matching import normalise_name

from .. import anzsic
from ..filters import filter_notifications

# A notification pair counts as "creeping" when it falls within 12 months.
WINDOW_DAYS = 365
MIN_NOTIFICATIONS = 2


def _group_level_tag(code: str) -> tuple[str, str] | None:
    """Roll an ANZSIC code up to its ``(group_code, group_name)``, or ``None``.

    Class-level tags roll up to their parent group; group-level tags are used
    as-is. Coarser (subdivision/division) or unrecognised codes have no single
    group to resolve to and are skipped — they're too broad for this analysis.
    """
    node = anzsic.get(code)
    if node is None:
        return None
    if node.level == "class":
        parent = anzsic.get(node.parent_code) if node.parent_code else None
        return (parent.code, parent.name) if parent else None
    if node.level == "group":
        return (node.code, node.name)
    return None


def _acquirer_key(party: dict) -> tuple[str, str | None, str] | None:
    """Return ``(group_key, canonical_id, display_name)`` for a party, or ``None``.

    Prefers the canonical group linked by
    :func:`static_data.enrichment.link_related_parties`; falls back to the
    normalised acquirer name (reusing :func:`party_matching.normalise_name`)
    when no canonical group exists.
    """
    canonical = party.get("canonical")
    if canonical and canonical.get("id"):
        return (f"canonical:{canonical['id']}", canonical["id"], canonical.get("name") or party.get("name", ""))
    name = party.get("name") or ""
    normalised = normalise_name(name)
    if not normalised:
        return None
    return (f"name:{normalised}", None, name)


def _has_window_pair(dates: list[datetime]) -> bool:
    """Return True if two (sorted) dates fall within ``WINDOW_DAYS`` of each other.

    Checking only consecutive pairs is sufficient: in a sorted list the
    smallest gap between any two elements is always between neighbours, so if
    every neighbouring gap exceeds the window, no pair can be within it.
    """
    return any(
        (later - earlier).days <= WINDOW_DAYS
        for earlier, later in zip(dates, dates[1:])
    )


def generate(mergers: list) -> dict:
    """Return the serial-acquirers.json payload for pre-enriched mergers."""
    buckets: dict[tuple[str, str], dict] = {}

    for merger in filter_notifications(mergers):
        merger_id = merger.get("merger_id")
        date_str = merger.get("effective_notification_datetime")
        parsed_date = parse_iso_datetime(date_str)
        if not merger_id or parsed_date is None:
            continue

        anzsic_tags = {}
        for code_entry in merger.get("anzsic_codes") or []:
            tag = _group_level_tag(code_entry.get("code", ""))
            if tag:
                anzsic_tags[tag[0]] = tag[1]
        if not anzsic_tags:
            continue

        acquirer_keys = {}
        for party in merger.get("acquirers") or []:
            key = _acquirer_key(party)
            if key:
                acquirer_keys[key[0]] = key

        for group_key, canonical_id, display_name in acquirer_keys.values():
            for anzsic_code, anzsic_name in anzsic_tags.items():
                bucket = buckets.setdefault(
                    (group_key, anzsic_code),
                    {
                        "acquirer_name": display_name,
                        "canonical_id": canonical_id,
                        "anzsic_code": anzsic_code,
                        "anzsic_name": anzsic_name,
                        "entries": {},
                    },
                )
                bucket["entries"][merger_id] = (parsed_date, date_str)

    records = []
    for bucket in buckets.values():
        entries = sorted(bucket["entries"].items(), key=lambda kv: kv[1][0])
        if len(entries) < MIN_NOTIFICATIONS:
            continue
        if not _has_window_pair([parsed for _, (parsed, _) in entries]):
            continue
        records.append({
            "acquirer_name": bucket["acquirer_name"],
            "canonical_id": bucket["canonical_id"],
            "anzsic_code": bucket["anzsic_code"],
            "anzsic_name": bucket["anzsic_name"],
            "merger_ids": [merger_id for merger_id, _ in entries],
            "dates": [date_str for _, (_, date_str) in entries],
            "count": len(entries),
        })

    records.sort(key=lambda r: (r["count"], max(r["dates"])), reverse=True)

    return {"acquirers": records, "count": len(records)}
