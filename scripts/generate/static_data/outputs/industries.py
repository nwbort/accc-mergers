"""Industries index + per-division node files.

``generate_index`` returns the ``industries.json`` payload.
``generate_detail_files`` writes one file per ANZSIC *division* into
``<output_dir>/industries/{division}.json``, each holding every node in that
division's subtree — see :mod:`scripts.industry_division` for why the division
is the seam and how the frontend picks the file to fetch.
"""

import json
from collections import defaultdict
from pathlib import Path

from scripts.constants import merger_status
from scripts.industry_division import (
    ORPHAN_FILE_STEM,
    division_file_stem,
)

from .. import anzsic
from ..durations import phase_1_duration_stats, waiver_duration_stats
from ..prune import prune_stale_files


def classify_phase(m: dict) -> str:
    """Bucket a merger into Phase 2 / Phase 1 / Waiver.

    Mirrors the Phase/Waiver split used on the Mergers page: waivers first,
    then anything currently in Phase 2, with everything else treated as
    Phase 1. Returns one of ``merger_status.WAIVER``/``PHASE_2``/``PHASE_1``.
    """
    if m.get('is_waiver'):
        return merger_status.WAIVER
    stage = m.get('stage') or ''
    if merger_status.PHASE_2 in stage:
        return merger_status.PHASE_2
    return merger_status.PHASE_1


def is_active(m: dict) -> bool:
    """Whether the review is still open (under assessment / suspended)."""
    return m.get('status') in (
        merger_status.UNDER_ASSESSMENT,
        merger_status.ASSESSMENT_SUSPENDED,
    )


def _industry_stats(unique_mergers: list) -> dict:
    """Compute the per-industry stat counts shown on the detail page."""
    phase_2 = sum(1 for m in unique_mergers if classify_phase(m) == merger_status.PHASE_2)
    waivers = sum(1 for m in unique_mergers if classify_phase(m) == merger_status.WAIVER)
    phase_1 = len(unique_mergers) - phase_2 - waivers
    active = sum(1 for m in unique_mergers if is_active(m))
    return {
        "phase_1_count": phase_1,
        "phase_2_count": phase_2,
        "waiver_count": waivers,
        "active_count": active,
    }


def generate_index(mergers: list) -> dict:
    """Return the industries.json payload (codes + merger counts)."""
    # Group unique mergers by (code, name). Dedupe by merger_id so a merger
    # tagged with the same code twice isn't counted more than once.
    industry_mergers = defaultdict(set)  # key -> {merger_id}
    all_merger_ids = set()

    for m in mergers:
        merger_id = m['merger_id']
        codes = m.get('anzsic_codes') or []
        for code in codes:
            key = (code.get('code', ''), code.get('name', ''))
            industry_mergers[key].add(merger_id)
            all_merger_ids.add(merger_id)

    industries = [
        {
            "code": code,
            "name": name,
            "merger_count": len(merger_ids),
        }
        for (code, name), merger_ids in industry_mergers.items()
    ]

    # Sort by merger count descending
    industries.sort(key=lambda x: -x['merger_count'])

    return {
        "industries": industries,
        # Number of distinct mergers tagged to at least one industry. Used as
        # the denominator for each industry's "share" so it reflects the share
        # of all mergers (shares may sum to >100% since mergers span industries).
        "total_mergers": len(all_merger_ids),
        "total_industries": len(industries),
    }


def _sort_mergers(records: list) -> list:
    """Order an industry's mergers for display.

    Open reviews (under assessment / suspended) come first, most recently
    notified first. Concluded reviews follow, most recent decision first.
    ``records`` is a list of ``(summary, full_merger)`` tuples.
    """
    active = [r for r in records if is_active(r[1])]
    decided = [r for r in records if not is_active(r[1])]
    active.sort(key=lambda r: r[1].get('effective_notification_datetime') or '', reverse=True)
    decided.sort(key=lambda r: r[1].get('determination_publication_date') or '', reverse=True)
    return [summary for summary, _ in active + decided]


def _node_payload(
    name: str | None,
    level: str | None,
    parent_code: str | None,
    child_codes: list[str],
    records: list,
) -> dict:
    """One node's entry in its division file.

    ``records`` is the list of ``(summary, full_merger)`` tuples rolled up onto
    this node. Only the merger *ids* are stored here, in display order — the
    summaries themselves live once in the division's ``mergers`` map, because a
    merger tagged at a class rolls up onto its group, subdivision and division
    too and would otherwise be written out four times.

    Ancestors and each child's merger count are deliberately absent: both are
    derivable from ``parent``/``children`` and the other nodes in the same file,
    and the reader (``frontend/src/utils/industryNode.js``) rebuilds them.
    """
    full_mergers = [full for _, full in records]
    payload = {
        "name": name,
        "level": level,
        "parent": parent_code,
        "children": list(child_codes),
        "mergers": [summary["merger_id"] for summary in _sort_mergers(records)],
        "count": len(records),
        **_industry_stats(full_mergers),
    }
    # Durations are absent for most nodes (no completed reviews of that kind),
    # and an explicit null per node across 825 nodes is pure noise.
    phase_duration = phase_1_duration_stats(full_mergers)
    if phase_duration is not None:
        payload["phase_duration"] = phase_duration
    waiver_duration = waiver_duration_stats(full_mergers)
    if waiver_duration is not None:
        payload["waiver_duration"] = waiver_duration
    return payload


def _write_division_file(industries_dir: Path, stem: str, payload: dict) -> str:
    """Write one division file; returns the file name written."""
    out_path = industries_dir / f"{stem}.json"
    with open(out_path, 'w', encoding='utf-8') as f:
        # Compact: these are machine-read payloads and the largest division
        # (Manufacturing, 214 nodes) is about half the size without the indent.
        json.dump(payload, f, separators=(',', ':'))
    return out_path.name


def generate_detail_files(mergers: list, output_dir: Path) -> int:
    """Write one JSON file per ANZSIC division. Returns the files written.

    Every node in the ANZSIC tree — divisions, subdivisions, groups and classes
    — gets an entry, so each level stays independently addressable at
    ``/industries/{code}``; they are simply packed one file per division rather
    than one file per node. See :mod:`scripts.industry_division` for why.

    Each file is ``{"division", "nodes", "mergers"}``: ``nodes`` maps a code to
    its hierarchy metadata, stat counts, durations and an ordered list of merger
    *ids*, and ``mergers`` maps each of those ids to its summary exactly once.

    Mergers aggregate up the tree: a parent node lists every merger tagged to
    any node in its subtree (plus any tagged directly to the parent code),
    deduped by merger_id. The ACCC occasionally tags a merger at several levels
    at once, so deduping keeps it appearing once per page.

    Tagged codes outside the ANZSIC tree get an entry too, filed by the same
    rule as real nodes so the frontend finds them where it looks: under their
    derivable division if they have one, otherwise in ``_orphans.json``. That
    file is written even when empty, so the fallback the frontend reaches for
    always exists rather than 404ing into the SPA's index.html.
    """
    industries_dir = Path(output_dir) / "industries"
    industries_dir.mkdir(parents=True, exist_ok=True)

    # Records aggregated onto each hierarchy node. A merger tagged at a class
    # rolls up to its group/subdivision/division too. code -> {merger_id: (summary, full)}
    node_records: dict[str, dict] = defaultdict(dict)
    # Tagged codes that aren't part of the ANZSIC tree (none at time of writing,
    # but the ACCC has mistyped one before and the page must not 404).
    orphan_records: dict[str, dict] = defaultdict(dict)

    for m in mergers:
        merger_id = m.get('merger_id')
        summary = {
            "merger_id": merger_id,
            "merger_name": m.get('merger_name'),
            "is_waiver": m.get('is_waiver', False),
            "status": m.get('status'),
            # ACCC outcome (Approved / Not opposed / Declined / …) when the
            # review has concluded, so the list can show the result — not just
            # whether the review is open or closed. Absent while still open.
            "determination": m.get('accc_determination'),
            "has_conditions": m.get('has_conditions', False),
            "phase": classify_phase(m),
            # Dates that drive industry-level "follow" notifications: a merger
            # being filed in the industry and its determination being published.
            # Kept on the lightweight summary so the frontend can detect new
            # filings/determinations without fetching each merger's detail file.
            "notification_date": m.get('effective_notification_datetime')
            or m.get('original_notification_datetime'),
            "determination_date": m.get('determination_publication_date'),
        }

        codes = m.get('anzsic_codes') or []
        for code_obj in codes:
            code = code_obj.get('code', '')
            if not code:
                continue
            node = anzsic.get(code)
            if node is None:
                orphan_records[code][merger_id] = (summary, m)
                continue
            # Roll the merger up onto this node and all its ancestors.
            node_records[code][merger_id] = (summary, m)
            for ancestor in anzsic.ancestors(code):
                node_records[ancestor.code][merger_id] = (summary, m)

    # One bucket per division file, plus the orphan bucket. Divisions with no
    # activity anywhere in their subtree still get a file: every node in the
    # tree is a real page, and an empty one says so rather than 404ing.
    buckets: dict[str, dict[str, dict]] = defaultdict(dict)

    hierarchy = anzsic.hierarchy()
    for code, node in hierarchy.items():
        records = list(node_records.get(code, {}).values())
        buckets[division_file_stem(code)][code] = _node_payload(
            node.name, node.level, node.parent_code, node.child_codes, records
        )

    # Orphans are placed by the same rule as everything else, because the
    # frontend has only that rule to go on. A code like "5400" looks like a
    # class and has a derivable division (J) without being a real ANZSIC node,
    # so it belongs in J.json — parking it in the orphan file would put it
    # somewhere the SPA would never look. Only a code with no derivable
    # division at all falls through to _orphans.json.
    for code, records in orphan_records.items():
        buckets[division_file_stem(code)][code] = _node_payload(
            None, None, None, [], list(records.values())
        )

    written: set[str] = set()
    for stem in sorted(set(buckets) | {ORPHAN_FILE_STEM}):
        nodes = buckets.get(stem, {})
        # Each summary once per file, keyed by id. A merger tagged in two
        # divisions is in both files; that is 19 copies at worst, against the
        # four per division a node-per-file layout paid.
        summaries: dict[str, dict] = {}
        for code in nodes:
            source = orphan_records.get(code) or node_records.get(code, {})
            for summary, _ in source.values():
                summaries.setdefault(summary["merger_id"], summary)
        payload = {
            "division": None if stem == ORPHAN_FILE_STEM else stem,
            "nodes": nodes,
            "mergers": summaries,
        }
        written.add(_write_division_file(industries_dir, stem, payload))

    # Retires the ~825 per-node files this layout replaced, and any division
    # file for a letter the ANZSIC tree stops using.
    prune_stale_files(industries_dir, written)

    return len(written)
