"""Party pages: ``parties.json`` index + per-party merger files.

Every party that appears in any merger gets a page — not just parties that
belong to a declared canonical group in ``related_parties.json``. Parties
matching a canonical group share that group's page (as before); every other
party gets a synthesized "group of one" page, keyed by normalised identifier
(preferred) or normalised name so repeat appearances of the same unlisted
entity under the same name/ABN still share one page. This is what lets every
``canonical``-chip *and* every plain party link on a merger detail page
resolve to a page — see issue #596.

:func:`build_party_pages` does the clustering and, as a side effect, attaches
a ``party_page`` field (``{"id", "name"}``) to every acquirer/target/other
party dict in place, mirroring how :func:`static_data.enrichment.
link_related_parties` attaches ``canonical`` — but for every party, not just
ones matched to a declared group.

``generate_index`` returns the ``parties.json`` payload.
``generate_detail_files`` writes one file per party group into
``<output_dir>/parties/{id}.json``.
"""

import json
from collections import Counter
from pathlib import Path

from constants import merger_status
from party_matching import build_group_lookups, match_party, normalise_identifier, normalise_name
from slug import slugify

from ..durations import collect_phase_1_durations, collect_waiver_durations, median_or_none
from ..prune import prune_stale_files
from .industries import classify_phase, is_active

PARTY_ROLE_FIELDS = ("acquirers", "targets", "other_parties")
ROLE_LABELS = {"acquirers": "acquirer", "targets": "target", "other_parties": "other"}


def _title_case_name(name: str) -> str:
    """Turn an ALL-CAPS register name into a friendlier display name."""
    cleaned = " ".join((name or "").split())
    if cleaned and cleaned == cleaned.upper():
        return cleaned.title()
    return cleaned


def _synth_key(party: dict) -> str:
    """Identity a party clusters on when it belongs to no declared group.

    Its normalised ABN when it has one, else its normalised name, so repeat
    appearances of the same unlisted entity share a page. Empty when the party
    has neither and cannot be clustered at all.
    """
    return normalise_identifier(party.get('identifier', '')) or normalise_name(party.get('name') or '')


def _best_name(name_counts: Counter, fallback: str) -> str:
    """The name a cluster is displayed under: most common, then shortest."""
    if not name_counts:
        return fallback
    return min(name_counts.items(), key=lambda item: (-item[1], len(item[0]), item[0]))[0]


def _base_slug(canonical_name: str) -> str:
    """The page id a cluster takes, before any collision suffix."""
    return slugify(canonical_name) or 'party'


def build_party_pages(mergers: list, party_groups: list) -> list:
    """Cluster every party appearance into a page group.

    Attaches ``party_page`` (``{"id", "name"}``) to every party dict in place.
    Returns a list of group records, sorted by id for deterministic output::

        {"id": ..., "canonical_name": ...,
         "members": [{"name", "identifier", "identifier_type"}, ...],
         "mergers_by_role": {"acquirer": {merger_id: merger}, "target": {...}, "other": {...}}}
    """
    by_identifier, by_name = build_group_lookups(party_groups)
    used_ids = {g.get('id') for g in party_groups if g.get('id')}

    # key -> accumulator. Canonical parties key on the declared group's id, so
    # every party matching that group naturally coalesces into one entry.
    # Ungrouped parties key on their own normalised identifier/name.
    acc: dict[tuple[str, str], dict] = {}

    for merger in mergers:
        for field in PARTY_ROLE_FIELDS:
            for party in merger.get(field) or []:
                name = party.get('name') or ''
                group = match_party(party, by_identifier, by_name)
                if group:
                    key = ('canonical', group['id'])
                else:
                    synth_key = _synth_key(party)
                    if not synth_key:
                        continue
                    key = ('synth', synth_key)

                entry = acc.setdefault(key, {
                    'canonical_group': group,
                    'name_counts': Counter(),
                    'members': set(),
                    'appearances': [],
                })
                if name:
                    entry['name_counts'][name] += 1
                entry['members'].add((name, party.get('identifier') or '', party.get('identifier_type') or ''))
                entry['appearances'].append((merger, field, party))

    groups = []
    for key in sorted(acc.keys()):
        entry = acc[key]
        if key[0] == 'canonical':
            group_id = entry['canonical_group']['id']
            canonical_name = entry['canonical_group'].get('canonical_name') or ''
        else:
            canonical_name = _title_case_name(_best_name(entry['name_counts'], key[1]))
            base_slug = _base_slug(canonical_name)
            group_id = base_slug
            n = 2
            while group_id in used_ids:
                group_id = f"{base_slug}-{n}"
                n += 1
            used_ids.add(group_id)

        members = sorted(
            {(name, identifier, id_type) for name, identifier, id_type in entry['members'] if name}
        )

        # A party can be listed under more than one role on the same merger
        # (e.g. named as both an applicant and an "other party" in the ACCC's
        # own register). Only show it once per merger on its party page,
        # preferring acquirer/target over other — PARTY_ROLE_FIELDS order
        # ("acquirers", "targets", "other_parties") gives us that priority
        # since appearances for a given merger are processed in that order.
        mergers_by_role: dict[str, dict] = {'acquirer': {}, 'target': {}, 'other': {}}
        assigned_role_by_merger: dict = {}
        for merger, field, party in entry['appearances']:
            party['party_page'] = {'id': group_id, 'name': canonical_name}
            role = ROLE_LABELS[field]
            merger_id = merger.get('merger_id')
            if merger_id in assigned_role_by_merger:
                continue
            assigned_role_by_merger[merger_id] = role
            mergers_by_role[role][merger_id] = merger

        groups.append({
            'id': group_id,
            'canonical_name': canonical_name,
            'members': [
                {'name': name, 'identifier': identifier or None, 'identifier_type': id_type or None}
                for name, identifier, id_type in members
            ],
            'mergers_by_role': mergers_by_role,
        })

    groups.sort(key=lambda g: g['id'])
    return groups


def build_party_aliases(mergers: list, party_groups: list, pages: list) -> dict:
    """Map a grouped party's would-be page id → the id of the page it now shares.

    A party that matches a declared group in ``related_parties.json`` has no
    page of its own: it is folded into the group's page. Before it was declared
    a member it had one, at the id its own name produces — the id this returns
    the mapping for. Those retired ids are what the redirect rules point at the
    surviving group page (see :mod:`.redirects`), so old links and bookmarks
    keep working instead of hitting "Party not found".

    Returns ``{retired_id: canonical_id}``, sorted by key. Ids that are a live
    page in their own right are never aliased — a live page always wins.
    """
    by_identifier, by_name = build_group_lookups(party_groups)

    # synth key -> {'names': Counter, 'group_id': str}. Only parties that
    # matched a declared group can have had a page retired.
    clusters: dict[str, dict] = {}
    for merger in mergers:
        for field in PARTY_ROLE_FIELDS:
            for party in merger.get(field) or []:
                group = match_party(party, by_identifier, by_name)
                if not group or not group.get('id'):
                    continue
                key = _synth_key(party)
                if not key:
                    continue
                cluster = clusters.setdefault(key, {'names': Counter(), 'group_id': group['id']})
                name = party.get('name') or ''
                if name:
                    cluster['names'][name] += 1

    live_ids = {p['id'] for p in pages}

    aliases = {}
    for key, cluster in clusters.items():
        retired_id = _base_slug(_title_case_name(_best_name(cluster['names'], key)))
        if retired_id in live_ids or retired_id == cluster['group_id']:
            continue
        aliases[retired_id] = cluster['group_id']

    return dict(sorted(aliases.items()))


def generate_index(groups: list) -> dict:
    """Return the parties.json payload (ids, names, merger counts)."""
    parties = []
    for g in groups:
        merger_ids: set = set()
        for role_mergers in g['mergers_by_role'].values():
            merger_ids.update(role_mergers.keys())
        parties.append({
            'id': g['id'],
            'name': g['canonical_name'],
            'merger_count': len(merger_ids),
        })

    parties.sort(key=lambda p: (-p['merger_count'], p['id']))

    return {
        'parties': parties,
        'total_parties': len(parties),
    }


def _sort_mergers(unique_mergers: list) -> list:
    """Order a party's mergers for display: open reviews first, most recently
    notified first, then concluded reviews, most recent decision first."""
    active = [m for m in unique_mergers if is_active(m)]
    decided = [m for m in unique_mergers if not is_active(m)]
    active.sort(key=lambda m: m.get('effective_notification_datetime') or '', reverse=True)
    decided.sort(key=lambda m: m.get('determination_publication_date') or '', reverse=True)
    return active + decided


def _merger_summary(m: dict) -> dict:
    return {
        'merger_id': m.get('merger_id'),
        'merger_name': m.get('merger_name'),
        'is_waiver': m.get('is_waiver', False),
        'status': m.get('status'),
        # ACCC outcome (Approved / Not opposed / Declined / …) when the review
        # has concluded, so the list can show the result — not just whether the
        # review is open or closed. Absent while still open.
        'determination': m.get('accc_determination'),
        'has_conditions': m.get('has_conditions', False),
        'phase': classify_phase(m),
        'notification_date': m.get('effective_notification_datetime') or m.get('original_notification_datetime'),
        'determination_date': m.get('determination_publication_date'),
    }


def _phase_duration(unique_mergers: list) -> dict | None:
    """Phase 1 duration stats for a party, mirroring the industry stats."""
    durations, business_durations = collect_phase_1_durations(unique_mergers)

    if not durations and not business_durations:
        return None

    return {
        'average_days': sum(durations) / len(durations) if durations else None,
        'median_days': median_or_none(durations),
        'average_business_days': (
            sum(business_durations) / len(business_durations) if business_durations else None
        ),
        'median_business_days': median_or_none(business_durations),
        'completed_count': len(business_durations),
    }


def _waiver_duration(unique_mergers: list) -> dict | None:
    """Waiver duration stats for a party, mirroring :func:`_phase_duration`.

    Measures notification → determination publication for completed waivers.
    """
    durations, business_durations = collect_waiver_durations(unique_mergers)

    if not durations and not business_durations:
        return None

    return {
        'average_days': sum(durations) / len(durations) if durations else None,
        'median_days': median_or_none(durations),
        'average_business_days': (
            sum(business_durations) / len(business_durations) if business_durations else None
        ),
        'median_business_days': median_or_none(business_durations),
        'completed_count': len(business_durations),
    }


def _write_detail_file(parties_dir: Path, group_id: str, payload: dict) -> str:
    """Write one party page; returns the file name written."""
    safe_id = group_id.replace('/', '-').replace('\\', '-')
    out_path = parties_dir / f"{safe_id}.json"
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(payload, f, indent=2)
    return out_path.name


def generate_detail_files(groups: list, output_dir: Path) -> int:
    """Write one JSON file per party group. Returns the number of files written.

    Party pages left over from a previous run are pruned — folding a party into
    a canonical group in ``related_parties.json`` retires its standalone page.
    """
    parties_dir = Path(output_dir) / "parties"
    parties_dir.mkdir(parents=True, exist_ok=True)

    written: set[str] = set()
    for g in groups:
        merger_map: dict = {}
        for role_mergers in g['mergers_by_role'].values():
            merger_map.update(role_mergers)
        all_mergers = list(merger_map.values())

        phase_2 = sum(1 for m in all_mergers if classify_phase(m) == merger_status.PHASE_2)
        waivers = sum(1 for m in all_mergers if classify_phase(m) == merger_status.WAIVER)
        phase_1 = len(all_mergers) - phase_2 - waivers
        active = sum(1 for m in all_mergers if is_active(m))

        mergers_payload = {
            role: [_merger_summary(m) for m in _sort_mergers(list(role_mergers.values()))]
            for role, role_mergers in g['mergers_by_role'].items()
        }

        payload = {
            'id': g['id'],
            'canonical_name': g['canonical_name'],
            'members': g['members'],
            'mergers': mergers_payload,
            'merger_count': len(merger_map),
            'phase_1_count': phase_1,
            'phase_2_count': phase_2,
            'waiver_count': waivers,
            'active_count': active,
            'phase_duration': _phase_duration(all_mergers),
            'waiver_duration': _waiver_duration(all_mergers),
        }
        written.add(_write_detail_file(parties_dir, g['id'], payload))

    prune_stale_files(parties_dir, written)

    return len(groups)
