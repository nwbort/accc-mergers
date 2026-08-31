"""Paginated lightweight merger list + metadata file.

Writes:
  <output_dir>/mergers/list-page-{N}.json
  <output_dir>/mergers/list-meta.json
"""

import json
from pathlib import Path

from ..loaders import FORWARD_REFILE_RELATIONSHIPS
from ..prune import prune_stale_files


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
        "stage": m.get('stage'),
        "acquirers": _party_names(m.get('acquirers')),
        "targets": _party_names(m.get('targets')),
        "other_parties": _party_names(m.get('other_parties')),
        "anzsic_codes": m.get('anzsic_codes') or [],
    }
    appeal = _appeal_summary(m)
    if appeal:
        entry["appeal"] = appeal
    return entry


def generate(mergers: list, output_dir: Path, page_size: int = 50) -> int:
    """Generate paginated merger list files. Returns number of pages written.

    Page files beyond the current last page are pruned, so a list that shrinks
    (e.g. after a dedup) doesn't keep serving a trailing page of stale entries.
    """
    mergers_dir = Path(output_dir) / "mergers"
    mergers_dir.mkdir(parents=True, exist_ok=True)

    lightweight_mergers = [_lightweight(m) for m in mergers]

    # Sort by notification date ascending (oldest first, newest last).
    # New mergers always append to the last page, so only the last page file
    # changes per scrape run rather than cascading through all pages.
    lightweight_mergers.sort(key=lambda x: x.get('effective_notification_datetime') or '')

    total_mergers = len(lightweight_mergers)
    total_pages = (total_mergers + page_size - 1) // page_size

    for page_num in range(1, total_pages + 1):
        start_idx = (page_num - 1) * page_size
        end_idx = min(start_idx + page_size, total_mergers)
        page_data = {
            "mergers": lightweight_mergers[start_idx:end_idx],
            "page": page_num,
            "page_size": page_size,
        }

        out_path = mergers_dir / f"list-page-{page_num}.json"
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(page_data, f, indent=2)

    meta_data = {
        "total": total_mergers,
        "page_size": page_size,
        "total_pages": total_pages,
    }
    meta_path = mergers_dir / "list-meta.json"
    with open(meta_path, 'w', encoding='utf-8') as f:
        json.dump(meta_data, f, indent=2)

    # Only the paginated list is ours to prune — the per-merger detail files in
    # this same directory belong to :mod:`.individual`.
    prune_stale_files(
        mergers_dir,
        {f"list-page-{n}.json" for n in range(1, total_pages + 1)},
        pattern="list-page-*.json",
        label="mergers",
    )

    return total_pages
