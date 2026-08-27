"""Individual questionnaire JSON files for lazy loading by the frontend.

Writes one ``<output_dir>/questionnaires/{merger_id}.json`` per merger that has
questionnaire data with at least one question.
"""

import json
import re
from pathlib import Path

from ..prune import prune_stale_files


def _norm_filename(name: str) -> str:
    """Strip re-download suffixes (_0, _1 …) before the extension.

    Mirrors the frontend's ``normalizeFilename`` so that a version whose file
    the scraper suffixed (e.g. "…Remedy Offer (10 July)_0.pdf") still matches
    an active event that points at a different suffix ("…_2.pdf").
    """
    return re.sub(r'_\d+(\.[^.]+)$', r'\1', name or '')


def _active_versions(versions: list, active_files: set) -> list:
    """Restrict parsed versions to those backing an active questionnaire event.

    Each active event is claimed by an exact filename match when one exists;
    otherwise it is matched by normalised filename. This drops superseded
    downloads that are no longer on the register while still keeping a version
    whose file the scraper re-suffixed relative to its event (e.g. MN-90008's
    Remedy "…_0" file, whose active event points at "…_2").
    """
    exact_claimed = {
        e for e in active_files if any(v.get('file_name') == e for v in versions)
    }

    def is_active(v: dict) -> bool:
        fn = v.get('file_name')
        if fn in active_files:
            return True
        return any(
            _norm_filename(e) == _norm_filename(fn)
            for e in active_files
            if e not in exact_claimed
        )

    return [v for v in versions if is_active(v)]


def _questionnaire_record(q_data: dict) -> dict:
    return {
        'deadline': q_data.get('deadline'),
        'deadline_iso': q_data.get('deadline_iso'),
        'file_name': q_data.get('file_name'),
        'questions': q_data.get('questions', []),
        'questions_count': q_data.get('questions_count', 0),
    }


def _is_questionnaire_event(event: dict) -> bool:
    """Whether a timeline event points at a questionnaire document.

    ``is_questionnaire_event`` is set by the scraper for questionnaires read out
    of the ACCC's structured consultation section, whose title is the
    consultation header and does not always say "questionnaire" (e.g. MN-45024's
    "OEConnection-Epyx - Phase 1 consultation"). Older events predate the flag,
    so the title check remains the fallback.
    """
    return bool(event.get('is_questionnaire_event')) or 'questionnaire' in event.get('title', '').lower()


def _active_questionnaire_filenames(merger: dict) -> set:
    """Return the set of questionnaire file names that have an active event."""
    return {
        Path(e['url_gh']).name
        for e in merger.get('events', [])
        if e.get('url_gh') and _is_questionnaire_event(e)
    }


def generate(questionnaire_data: dict, output_dir: Path, mergers: list | None = None) -> int:
    """Write individual questionnaire files. Returns count written.

    Files for matters whose questionnaires are no longer parsed (or no longer
    have any questions) are pruned.
    """
    active_by_merger = {}
    if mergers:
        for merger in mergers:
            merger_id = merger.get('merger_id')
            if merger_id:
                active_by_merger[merger_id] = _active_questionnaire_filenames(merger)

    questionnaires_dir = Path(output_dir) / "questionnaires"
    questionnaires_dir.mkdir(parents=True, exist_ok=True)

    count = 0
    written: set[str] = set()
    for merger_id, q_data in questionnaire_data.items():
        # All distinct versions parsed for this matter (the primary entry is
        # also the first element of all_questionnaires when it exists).
        versions = q_data.get('all_questionnaires') or [q_data]
        versions = [v for v in versions if v.get('questions')]
        if not versions:
            continue

        # Restrict to versions that still correspond to an active questionnaire
        # event, so superseded/stale downloads that are no longer on the ACCC
        # register are not displayed. Only fall back to the full set when nothing
        # matches, so a divergence between event and file names never drops the
        # questionnaire entirely.
        active_files = active_by_merger.get(merger_id)
        if active_files:
            matched = _active_versions(versions, active_files)
            if matched:
                versions = matched

        # Primary = latest by deadline (missing deadline sorts oldest).
        versions.sort(key=lambda v: v.get('deadline_iso') or '0000-00-00', reverse=True)

        output = _questionnaire_record(versions[0])
        if len(versions) > 1:
            output['all_questionnaires'] = [_questionnaire_record(v) for v in versions]

        out_path = questionnaires_dir / f"{merger_id}.json"
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2)
        written.add(out_path.name)
        count += 1

    prune_stale_files(questionnaires_dir, written)

    return count
