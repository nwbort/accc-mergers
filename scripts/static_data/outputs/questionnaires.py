"""Individual questionnaire JSON files for lazy loading by the frontend.

Writes one ``<output_dir>/questionnaires/{merger_id}.json`` per merger that has
questionnaire data with at least one question.
"""

import json
from pathlib import Path


def _questionnaire_record(q_data: dict) -> dict:
    return {
        'deadline': q_data.get('deadline'),
        'deadline_iso': q_data.get('deadline_iso'),
        'file_name': q_data.get('file_name'),
        'questions': q_data.get('questions', []),
        'questions_count': q_data.get('questions_count', 0),
    }


def _active_questionnaire_filenames(merger: dict) -> set:
    """Return the set of questionnaire file names that have an active event."""
    return {
        Path(e['url_gh']).name
        for e in merger.get('events', [])
        if e.get('url_gh') and 'questionnaire' in e.get('title', '').lower()
    }


def generate(questionnaire_data: dict, output_dir: Path, mergers: list | None = None) -> int:
    """Write individual questionnaire files. Returns count written."""
    active_by_merger = {}
    if mergers:
        for merger in mergers:
            merger_id = merger.get('merger_id')
            if merger_id:
                active_by_merger[merger_id] = _active_questionnaire_filenames(merger)

    questionnaires_dir = Path(output_dir) / "questionnaires"
    questionnaires_dir.mkdir(parents=True, exist_ok=True)

    count = 0
    for merger_id, q_data in questionnaire_data.items():
        if q_data.get('questions'):
            output = _questionnaire_record(q_data)

            # When the matter has multiple distinct questionnaires, include them
            # all (sorted latest-first) so consumers can access older versions.
            # Filter to only questionnaires that have a corresponding active event
            # so manually-removed duplicate events don't reappear on next pipeline run.
            all_qs = q_data.get('all_questionnaires', [])
            active_files = active_by_merger.get(merger_id)
            if active_files is not None:
                all_qs = [aq for aq in all_qs if aq.get('file_name') in active_files]
            if len(all_qs) > 1:
                output['all_questionnaires'] = [
                    _questionnaire_record(aq)
                    for aq in all_qs
                    if aq.get('questions')
                ]

            out_path = questionnaires_dir / f"{merger_id}.json"
            with open(out_path, 'w', encoding='utf-8') as f:
                json.dump(output, f, indent=2)
            count += 1

    return count
