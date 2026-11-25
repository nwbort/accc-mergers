"""The gold set: ``gold.jsonl``, one labelled passage per line.

Each line is a passage (see ``passages.Passage``) plus:

- ``labels``: the categories that apply, ``[]`` for none, or ``null`` while unlabelled.
- ``status``: ``unlabelled`` | ``draft`` | ``reviewed``. ``draft`` labels were
  proposed without a person checking them (the initial set was drafted by a
  model, so treat it as unverified). ``review`` turns them into ``reviewed``.
- ``ambiguous``: a careful reader could reasonably label it otherwise. The eval
  reports with and without these.
- ``notes``: why, when that isn't obvious.

The file holds its passages' text, so the eval never needs the pipeline's data
files. It is JSONL, sorted by id, so a review diffs one line per passage.
"""

import json
from pathlib import Path
from typing import Optional

from .taxonomy import CATEGORIES

GOLD_PATH = Path(__file__).with_name('gold.jsonl')

STATUSES = ('unlabelled', 'draft', 'reviewed')


def load(path: Path = GOLD_PATH) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]


def save(entries: list[dict], path: Path = GOLD_PATH) -> None:
    entries = sorted(entries, key=lambda e: e['id'])
    path.write_text(
        ''.join(json.dumps(e, ensure_ascii=False) + '\n' for e in entries),
        encoding='utf-8',
    )


def validate(entries: list[dict]) -> list[str]:
    """Every problem with the gold set, as human-readable strings."""
    problems = []
    seen = set()
    for e in entries:
        pid = e.get('id', '<no id>')
        if pid in seen:
            problems.append(f'{pid}: duplicate id')
        seen.add(pid)
        if not e.get('text'):
            problems.append(f'{pid}: no text')
        status = e.get('status')
        if status not in STATUSES:
            problems.append(f'{pid}: unknown status {status!r}')
        labels = e.get('labels')
        if status == 'unlabelled':
            if labels is not None:
                problems.append(f'{pid}: unlabelled but has labels')
            continue
        if not isinstance(labels, list):
            problems.append(f'{pid}: labels must be a list once labelled')
            continue
        for label in labels:
            if label not in CATEGORIES:
                problems.append(f'{pid}: unknown category {label!r}')
        if len(set(labels)) != len(labels):
            problems.append(f'{pid}: repeated label')
    return problems


def select(
    entries: list[dict],
    *,
    reviewed_only: bool = False,
    exclude_ambiguous: bool = False,
    source: Optional[str] = None,
) -> list[dict]:
    """The labelled entries an eval run scores against."""
    out = []
    for e in entries:
        if e['status'] == 'unlabelled':
            continue
        if reviewed_only and e['status'] != 'reviewed':
            continue
        if exclude_ambiguous and e.get('ambiguous'):
            continue
        if source and e['source'] != source:
            continue
        out.append(e)
    return out
