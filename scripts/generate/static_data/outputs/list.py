"""Lightweight merger list: every merger, in one file.

Writes:
  <output_dir>/mergers/list.json
"""

import json
from pathlib import Path

from scripts.constants import merger_status

from ..enrichment import reached_phase_2
from ..loaders import FORWARD_REFILE_RELATIONSHIPS
from ..prune import prune_stale_files

LIST_FILE = "list.json"
# Everything in mergers/ this generator owns, including the retired
# list-page-{N}.json / list-meta.json files it now prunes. Matter files are
# named MN-/WA-..., so nothing of individual.py's matches.
LIST_FILES_GLOB = "list*.json"


def _party_names(parties: list | None) -> list:
    """Reduce parties to the names the list pages actually use.

    The merger cards never render parties — the party lists exist only to feed
    utils/searchIndex.js, which reads each party's ``name`` and its canonical
    group ``name``. The identifier, identifier type and party_page link that
    ride along on the full party dicts are pure weight here, and the list is
    downloaded in full by both /mergers and the command palette.

    A party given as a bare name string is carried through as one, so an odd
    record can't take the whole list generator down.
    """
    entries = []
    for party in parties or []:
        if isinstance(party, str):
            entries.append({"name": party})
            continue
        entry = {"name": party.get("name")}
        canonical = party.get("canonical") or {}
        if canonical.get("name"):
            entry["canonical"] = {"name": canonical["name"]}
        entries.append(entry)
    return entries


def _latest_event_date(m: dict) -> str | None:
    """Most recent event date, driving the list's "Last updated" sort.

    Reuses the events already scraped for the timeline rather than tracking a
    separate modification timestamp: any change to a matter's ACCC register
    page (a new document, an extension, a determination) adds or updates an
    event, so this is a genuine "when did this matter last change" signal at
    zero extra scraping cost.
    """
    dates = [e.get('date') for e in (m.get('events') or []) if e.get('date')]
    return max(dates) if dates else None


def _appeal_summary(m: dict) -> dict | None:
    """Slim appeal fields needed to render the status badge on a list card.

    Only the lifecycle status and the concluded result are carried — enough for
    the appeal-aware StatusBadge — not the full documents list. Returns ``None``
    when the merger has no tribunal appeal.
    """
    appeal = m.get('appeal')
    if not appeal:
        return None
    return {
        'status': appeal.get('status'),
        'outcome': appeal.get('outcome'),
        'effective_determination': appeal.get('effective_determination'),
    }


def _lightweight(m: dict) -> dict:
    entry = {
        "merger_id": m.get('merger_id'),
        "merger_name": m.get('merger_name'),
        "status": m.get('status'),
        "accc_determination": m.get('accc_determination'),
        "has_conditions": m.get('has_conditions', False),
        "is_waiver": m.get('is_waiver', False),
        "under_appeal": m.get('under_appeal', False),
        # True for a matter (waiver or notification) later re-filed as a
        # separate matter — e.g. a ceased assessment re-notified under a new
        # merger ID. Mirrors phase2.py's is_refiled (the earlier/superseded
        # matter), not stats.py's (which flags the new, re-filing matter).
        "is_refiled": (m.get('related_merger') or {}).get('relationship') in FORWARD_REFILE_RELATIONSHIPS,
        "effective_notification_datetime": m.get('effective_notification_datetime'),
        "determination_publication_date": m.get('determination_publication_date'),
        "end_of_determination_period": m.get('end_of_determination_period'),
        "latest_event_date": _latest_event_date(m),
        # The register page's real modified timestamp (to the second). Event
        # dates are all stored at a nominal midday, so this is the only thing
        # that orders matters updated on the same day; it is the list's
        # "Last updated" tie-break, never its primary key (the ACCC rewriting
        # an old page would otherwise float it to the top).
        "page_modified_datetime": m.get('page_modified_datetime'),
        "stage": m.get('stage'),
        "acquirers": _party_names(m.get('acquirers')),
        "targets": _party_names(m.get('targets')),
        "other_parties": _party_names(m.get('other_parties')),
        "anzsic_codes": m.get('anzsic_codes') or [],
    }
    appeal = _appeal_summary(m)
    if appeal:
        entry["appeal"] = appeal
    # A matter that has moved on from Phase 2 to the public benefit phase no
    # longer says "Phase 2" in its stage, but the list's Phase 2 filter should
    # still find it. Carried only where the stage doesn't already say so, so
    # the ordinary entry is no larger.
    if reached_phase_2(m) and merger_status.stage_phase(m.get('stage')) != merger_status.PHASE_2:
        entry["reached_phase_2"] = True
    return entry


def generate(mergers: list, output_dir: Path) -> int:
    """Write the lightweight merger list as one file. Returns the merger count.

    The list used to be split into 50-merger ``list-page-{N}.json`` files plus
    a ``list-meta.json``, but every consumer (the /mergers page, the command
    palette) needs the whole list to search, filter and sort it, so the pages
    only cost round trips. The whole list is ~120 KB gzipped. Those legacy
    files are pruned here.

    One merger per line: compact on the wire, but a pipeline commit still
    diffs as the handful of matters that changed rather than one giant line.
    Ordered by notification date ascending so the line order is stable.
    """
    mergers_dir = Path(output_dir) / "mergers"
    mergers_dir.mkdir(parents=True, exist_ok=True)

    lightweight_mergers = [_lightweight(m) for m in mergers]
    lightweight_mergers.sort(key=lambda x: x.get('effective_notification_datetime') or '')

    lines = ",\n".join(
        json.dumps(m, ensure_ascii=False, separators=(',', ':')) for m in lightweight_mergers
    )
    out_path = mergers_dir / LIST_FILE
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('{"mergers":[\n' + lines + '\n]}\n')

    # Only the list is ours to prune — the per-merger detail files in this
    # same directory belong to :mod:`.individual`.
    prune_stale_files(mergers_dir, {LIST_FILE}, pattern=LIST_FILES_GLOB, label="mergers")

    return len(lightweight_mergers)
