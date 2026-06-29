"""Industries index + per-industry merger files.

``generate_index`` returns the ``industries.json`` payload.
``generate_detail_files`` writes one file per industry code into
``<output_dir>/industries/{code}.json``.
"""

import json
from collections import defaultdict
from pathlib import Path

from constants import merger_status

from .. import anzsic
from ..durations import collect_phase_1_durations


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


def _avg(values: list):
    return sum(values) / len(values) if values else None


def _median(values: list):
    return sorted(values)[len(values) // 2] if values else None


def _phase_duration(unique_mergers: list) -> dict | None:
    """Phase 1 duration stats for an industry, mirroring the dashboard stats.

    Measures notification → Phase 1 end for completed notification (non-waiver)
    mergers, with matters referred to Phase 2 measured to the referral date so
    the Phase 2 clock never inflates the figures. Returns ``None`` when the
    industry has no completed Phase 1 reviews.
    """
    durations, business_durations = collect_phase_1_durations(unique_mergers)

    if not durations and not business_durations:
        return None

    return {
        "average_days": _avg(durations),
        "median_days": _median(durations),
        "average_business_days": _avg(business_durations),
        "median_business_days": _median(business_durations),
        "completed_count": len(business_durations),
    }


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
        codes = m.get('anzsic_codes') or m.get('anszic_codes') or []
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


def _node_ref(node: anzsic.Node, merger_count: int | None = None) -> dict:
    """A compact reference to a hierarchy node (for parent/child/breadcrumb links)."""
    ref = {"code": node.code, "name": node.name, "level": node.level}
    if merger_count is not None:
        ref["merger_count"] = merger_count
    return ref


def _write_detail_file(industries_dir: Path, code: str, payload: dict) -> None:
    safe_code = code.replace('/', '-').replace('\\', '-')
    out_path = industries_dir / f"{safe_code}.json"
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(payload, f, indent=2)


def generate_detail_files(mergers: list, output_dir: Path) -> int:
    """Write one JSON file per ANZSIC node. Returns the number of files written.

    A file is generated for every node in the ANZSIC tree — divisions,
    subdivisions, groups and classes — so each level is independently
    addressable at ``/industries/{code}``. Each file carries the hierarchy
    metadata (name, level, breadcrumb ancestors, parent, children) needed to
    render the page and navigate up/down the tree.

    Mergers aggregate up the tree: a parent node lists every merger tagged to
    any node in its subtree (plus any tagged directly to the parent code),
    deduped by merger_id. The ACCC occasionally tags a merger at several levels
    at once, so deduping keeps it appearing once per page.
    """
    industries_dir = Path(output_dir) / "industries"
    industries_dir.mkdir(parents=True, exist_ok=True)

    # Records aggregated onto each hierarchy node. A merger tagged at a class
    # rolls up to its group/subdivision/division too. code -> {merger_id: (summary, full)}
    node_records: dict[str, dict] = defaultdict(dict)
    # Tagged codes that aren't part of the ANZSIC tree get a standalone flat
    # file so existing links never 404 (none at time of writing, but defensive).
    orphan_records: dict[str, dict] = defaultdict(dict)

    for m in mergers:
        merger_id = m.get('merger_id')
        summary = {
            "merger_id": merger_id,
            "merger_name": m.get('merger_name'),
            "is_waiver": m.get('is_waiver', False),
            "status": m.get('status'),
            "phase": classify_phase(m),
            # Dates that drive industry-level "follow" notifications: a merger
            # being filed in the industry and its determination being published.
            # Kept on the lightweight summary so the frontend can detect new
            # filings/determinations without fetching each merger's detail file.
            "notification_date": m.get('effective_notification_datetime')
            or m.get('original_notification_datetime'),
            "determination_date": m.get('determination_publication_date'),
        }

        codes = m.get('anzsic_codes') or m.get('anszic_codes') or []
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

    def merger_count(code: str) -> int:
        return len(node_records.get(code, {}))

    hierarchy = anzsic.hierarchy()
    for code, node in hierarchy.items():
        record_list = list(node_records.get(code, {}).values())
        full_mergers = [full for _, full in record_list]

        children = [
            _node_ref(hierarchy[child_code], merger_count(child_code))
            for child_code in node.child_codes
        ]
        parent = anzsic.get(node.parent_code) if node.parent_code else None

        payload = {
            "code": code,
            "name": node.name,
            "level": node.level,
            "ancestors": [_node_ref(a) for a in anzsic.ancestors(code)],
            "parent": _node_ref(parent) if parent else None,
            "children": children,
            "mergers": _sort_mergers(record_list),
            "count": len(record_list),
            **_industry_stats(full_mergers),
            "phase_duration": _phase_duration(full_mergers),
        }
        _write_detail_file(industries_dir, code, payload)

    # Standalone files for any tagged codes outside the ANZSIC tree.
    for code, records in orphan_records.items():
        record_list = list(records.values())
        full_mergers = [full for _, full in record_list]
        payload = {
            "code": code,
            "name": None,
            "level": None,
            "ancestors": [],
            "parent": None,
            "children": [],
            "mergers": _sort_mergers(record_list),
            "count": len(record_list),
            **_industry_stats(full_mergers),
            "phase_duration": _phase_duration(full_mergers),
        }
        _write_detail_file(industries_dir, code, payload)

    return len(hierarchy) + len(orphan_records)
