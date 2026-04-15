"""Individual questionnaire JSON files for lazy loading by the frontend.

Writes one ``<output_dir>/questionnaires/{merger_id}.json`` per merger that has
questionnaire data with at least one question.
"""

import json
from pathlib import Path


def generate(questionnaire_data: dict, output_dir: Path) -> int:
    """Write individual questionnaire files. Returns count written."""
    questionnaires_dir = Path(output_dir) / "questionnaires"
    questionnaires_dir.mkdir(parents=True, exist_ok=True)

    count = 0
    for merger_id, q_data in questionnaire_data.items():
        if q_data.get('questions'):
            output = {
                'deadline': q_data.get('deadline'),
                'deadline_iso': q_data.get('deadline_iso'),
                'file_name': q_data.get('file_name'),
                'questions': q_data.get('questions', []),
                'questions_count': q_data.get('questions_count', 0),
            }
            out_path = questionnaires_dir / f"{merger_id}.json"
            with open(out_path, 'w', encoding='utf-8') as f:
                json.dump(output, f, indent=2)
            count += 1

    return count
