"""Loaders for source JSON files consumed by the static data pipeline."""

import json
from pathlib import Path

from merger_filters import load_mergers as _load_mergers

SCRIPT_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = SCRIPT_DIR.parent
MERGERS_JSON = REPO_ROOT / "data" / "processed" / "mergers.json"
COMMENTARY_JSON = REPO_ROOT / "data" / "processed" / "commentary.json"
QUESTIONNAIRE_JSON = REPO_ROOT / "data" / "processed" / "questionnaire_data.json"
NOCC_JSON = REPO_ROOT / "data" / "processed" / "nocc_data.json"
RELATED_MERGERS_JSON = REPO_ROOT / "data" / "processed" / "related_mergers.json"
RELATED_PARTIES_JSON = REPO_ROOT / "data" / "processed" / "related_parties.json"
SIMILAR_MERGERS_JSON = REPO_ROOT / "data" / "processed" / "similar_mergers.json"
TRIBUNAL_APPEALS_JSON = REPO_ROOT / "data" / "processed" / "tribunal_appeals.json"
JUDICIAL_REVIEWS_JSON = REPO_ROOT / "data" / "processed" / "judicial_reviews.json"


def load_mergers() -> list:
    """Load mergers list from the processed mergers.json file.

    Delegates to the canonical loader in :mod:`merger_filters`, which
    accepts both the raw-list format and the ``{"mergers": [...]}`` wrapper.
    """
    return _load_mergers(MERGERS_JSON)


# Relationship labels emitted for each pair type, as (source_label,
# target_label). The source is the earlier matter (waiver / suspended); the
# target is what it was re-filed as. The frontend maps these to display text.
_RELATIONSHIP_LABELS = {
    'waiver_refiled': ('refiled_as', 'refiled_from'),
    'suspended_refiled': ('suspended_refiled_as', 'suspended_refiled_from'),
}


# Relationship values where the merger is the *earlier* matter that was later
# re-filed as another (the source side of a pair) — flags the original matter,
# e.g. a ceased Phase 2 assessment that was subsequently re-filed.
FORWARD_REFILE_RELATIONSHIPS = frozenset(source for source, _ in _RELATIONSHIP_LABELS.values())

# Relationship values where the merger is the *later*, re-filed matter (the
# target side of a pair) — flags a notification as itself being a re-file.
BACKWARD_REFILE_RELATIONSHIPS = frozenset(target for _, target in _RELATIONSHIP_LABELS.values())


def build_relationship_map(data: dict) -> dict:
    """Turn related-merger ``pairs`` into a per-merger relationship lookup.

    Each pair has the shape ``{"from", "to", "type"}`` where ``from`` is the
    earlier matter and ``to`` is what it was re-filed as. Returns a dict keyed
    by merger_id mapping to ``{'merger_id': ..., 'relationship': ...}``.
    """
    result = {}
    for pair in data.get('pairs', []):
        source = pair.get('from')
        target = pair.get('to')
        if not source or not target:
            continue
        pair_type = pair.get('type', 'waiver_refiled')
        source_rel, target_rel = _RELATIONSHIP_LABELS.get(
            pair_type, _RELATIONSHIP_LABELS['waiver_refiled']
        )
        result[source] = {'merger_id': target, 'relationship': source_rel}
        result[target] = {'merger_id': source, 'relationship': target_rel}
    return result


def load_related_mergers() -> dict:
    """Load related merger pairs from related_mergers.json.

    Returns a dict keyed by merger_id mapping to
    ``{'merger_id': ..., 'relationship': ...}``. See ``build_relationship_map``
    for the supported pair shapes and relationship values.
    """
    if not RELATED_MERGERS_JSON.exists():
        return {}

    try:
        with open(RELATED_MERGERS_JSON, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return build_relationship_map(data)
    except (json.JSONDecodeError, IOError, KeyError) as e:
        print(f"Warning: Could not load related_mergers.json: {e}")
        return {}


def load_related_parties() -> list:
    """Load canonical "related party" groups from related_parties.json.

    Returns the list of group dicts (each with ``id``, ``canonical_name`` and
    ``members``). The matching logic that turns these into a per-party lookup
    lives in ``scripts/party_matching.py`` so the daily detector and this
    pipeline stay in sync. Returns an empty list if the file is missing or
    malformed.
    """
    if not RELATED_PARTIES_JSON.exists():
        return []

    try:
        with open(RELATED_PARTIES_JSON, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data.get('groups', [])
    except (json.JSONDecodeError, IOError) as e:
        print(f"Warning: Could not load related_parties.json: {e}")
        return []


def load_similar_mergers() -> dict:
    """Load similar merger suggestions from similar_mergers.json.

    Returns a dict keyed by merger_id mapping to a list of similar merger_ids,
    e.g. ``{"MN-01016": ["MN-12345", "MN-67890"]}``.
    """
    if not SIMILAR_MERGERS_JSON.exists():
        return {}

    try:
        with open(SIMILAR_MERGERS_JSON, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data.get('similar', {})
    except (json.JSONDecodeError, IOError) as e:
        print(f"Warning: Could not load similar_mergers.json: {e}")
        return {}


def load_tribunal_appeals() -> dict:
    """Load Australian Competition Tribunal appeal data from tribunal_appeals.json.

    Returns a dict keyed by merger_id mapping to the appeal record (tribunal
    number, tribunal URL, appeal type, appellant, filed date and documents).
    Metadata keys (starting with ``_``) are stripped. Returns an empty dict if
    the file is missing or malformed.
    """
    if not TRIBUNAL_APPEALS_JSON.exists():
        return {}

    try:
        with open(TRIBUNAL_APPEALS_JSON, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return {k: v for k, v in data.items() if not k.startswith('_')}
    except (json.JSONDecodeError, IOError) as e:
        print(f"Warning: Could not load tribunal_appeals.json: {e}")
        return {}


def load_judicial_reviews() -> dict:
    """Load Federal Court judicial review data from judicial_reviews.json.

    Returns a dict keyed by merger_id mapping to the judicial review record
    (applicant, filed date, case number, case URL). Metadata keys (starting
    with ``_``) are stripped. Returns an empty dict if the file is missing or
    malformed.
    """
    if not JUDICIAL_REVIEWS_JSON.exists():
        return {}

    try:
        with open(JUDICIAL_REVIEWS_JSON, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return {k: v for k, v in data.items() if not k.startswith('_')}
    except (json.JSONDecodeError, IOError) as e:
        print(f"Warning: Could not load judicial_reviews.json: {e}")
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
            data = json.load(f)
        # Strip reserved metadata keys (parser cache state etc.)
        return {k: v for k, v in data.items() if not k.startswith('_')}
    except (json.JSONDecodeError, IOError) as e:
        print(f"Warning: Could not load questionnaire_data.json: {e}")
        return {}


def load_nocc_data() -> dict:
    """Load NOCC summary data from nocc_data.json if it exists."""
    if not NOCC_JSON.exists():
        return {}

    try:
        with open(NOCC_JSON, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return {k: v for k, v in data.items() if not k.startswith('_')}
    except (json.JSONDecodeError, IOError) as e:
        print(f"Warning: Could not load nocc_data.json: {e}")
        return {}
