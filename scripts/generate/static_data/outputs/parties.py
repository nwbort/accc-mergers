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
``generate_detail_files`` writes the party records into a fixed set of
buckets, ``<output_dir>/parties/shard-{nn}.json``, keyed by party id.

The buckets exist for one reason: Cloudflare Pages caps a deployment at
20,000 files, and a file-per-party cost ~2,200 of that budget to hold ~2 MB
of JSON — the limit counts files, not bytes. See ``scripts/shard.py`` for
the bucketing rule and why it has to match the frontend exactly.
"""

import json
from collections import Counter
from pathlib import Path

from scripts.constants import merger_status
from scripts.detect.party_matching import build_group_lookups, match_party, normalise_identifier, normalise_name
from scripts.shard import SHARD_COUNT, party_shard, shard_name
from scripts.slug import slugify

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
                    ident = normalise_identifier(party.get('identifier', ''))
                    synth_key = ident or normalise_name(name)
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
            if entry['name_counts']:
                best_name = min(
                    entry['name_counts'].items(),
                    key=lambda item: (-item[1], len(item[0]), item[0]),
                )[0]
            else:
                best_name = key[1]
            canonical_name = _title_case_name(best_name)
            base_slug = slugify(canonical_name) or 'party'
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


def _party_payload(g: dict) -> dict:
    """The detail record for one party group — what a party page renders."""
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

    return {
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


def build_shards(groups: list) -> dict[int, dict]:
    """Group the party payloads into their buckets.

    Returns ``{shard index: {party id: payload}}``, both levels sorted by key so
    a run that changes one party rewrites that bucket byte-identically apart
    from the party itself. Empty buckets are omitted — a bucket file only exists
    once something hashes into it, and a request for a party in an empty bucket
    404s, which is the right answer for a party that does not exist.
    """
    buckets: dict[int, dict] = {}
    for g in groups:
        buckets.setdefault(party_shard(g['id']), {})[g['id']] = _party_payload(g)
    return {
        index: {pid: buckets[index][pid] for pid in sorted(buckets[index])}
        for index in sorted(buckets)
    }


def generate_detail_files(groups: list, output_dir: Path) -> int:
    """Write the party detail buckets. Returns the number of parties written.

    Party records are packed into ``parties/shard-{nn}.json`` rather than one
    file per party — see the module docstring. The bucket for a given id is
    computed, not looked up, so the SPA reaches a party page in one request;
    ``scripts/shard.py`` and ``frontend/src/utils/shard.js`` must agree on it.

    Buckets left over from a previous run are pruned, which is also what clears
    out the old per-party files on the first run after the switch. Folding a
    party into a canonical group in ``related_parties.json`` no longer leaves a
    stale file behind at all: the party simply stops being written into its
    bucket.
    """
    parties_dir = Path(output_dir) / "parties"
    parties_dir.mkdir(parents=True, exist_ok=True)

    written: set[str] = set()
    for index, bucket in build_shards(groups).items():
        payload = {
            'shard': index,
            'shard_count': SHARD_COUNT,
            'parties': bucket,
        }
        name = shard_name(index)
        with open(parties_dir / name, 'w', encoding='utf-8') as f:
            json.dump(payload, f, indent=2)
        written.add(name)

    prune_stale_files(parties_dir, written, label='parties')

    return len(groups)
