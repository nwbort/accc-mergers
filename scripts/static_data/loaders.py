"""Loaders for source JSON files consumed by the static data pipeline."""

import json
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = SCRIPT_DIR.parent
MERGERS_JSON = REPO_ROOT / "data" / "processed" / "mergers.json"
COMMENTARY_JSON = REPO_ROOT / "data" / "processed" / "commentary.json"
QUESTIONNAIRE_JSON = REPO_ROOT / "data" / "processed" / "questionnaire_data.json"
RELATED_MERGERS_JSON = REPO_ROOT / "data" / "processed" / "related_mergers.json"


def load_mergers() -> list:
    """Load mergers list from the processed mergers.json file.

    Accepts both the raw-list format and the ``{"mergers": [...]}`` wrapper.
    """
    with open(MERGERS_JSON, 'r', encoding='utf-8') as f:
        data = json.load(f)

    if isinstance(data, list):
        return data
    if isinstance(data, dict) and 'mergers' in data:
        return data['mergers']
    raise ValueError("Unexpected mergers.json format")


def load_related_mergers() -> dict:
    """Load related merger pairs from related_mergers.json.

    Returns a dict keyed by merger_id mapping to
    ``{'merger_id': ..., 'relationship': 'refiled_as' | 'refiled_from'}``.
    """
    if not RELATED_MERGERS_JSON.exists():
        return {}

    try:
        with open(RELATED_MERGERS_JSON, 'r', encoding='utf-8') as f:
            data = json.load(f)

        result = {}
        for pair in data.get('pairs', []):
            wa = pair['waiver']
            mn = pair['notification']
            result[wa] = {'merger_id': mn, 'relationship': 'refiled_as'}
            result[mn] = {'merger_id': wa, 'relationship': 'refiled_from'}
        return result
    except (json.JSONDecodeError, IOError, KeyError) as e:
        print(f"Warning: Could not load related_mergers.json: {e}")
        return {}


def load_commentary() -> dict:
    """Load user commentary from commentary.json if it exists."""
    if not COMMENTARY_JSON.exists():
        return {}

    try:
        with open(COMMENTARY_JSON, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Filter out metadata keys (starting with _)
        return {k: v for k, v in data.items() if not k.startswith('_')}
    except (json.JSONDecodeError, IOError) as e:
        print(f"Warning: Could not load commentary.json: {e}")
        return {}


def load_questionnaire_data() -> dict:
    """Load questionnaire data from questionnaire_data.json if it exists."""
    if not QUESTIONNAIRE_JSON.exists():
        return {}

    try:
        with open(QUESTIONNAIRE_JSON, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"Warning: Could not load questionnaire_data.json: {e}")
        return {}
