"""Retire byte-identical re-uploads of a matter's documents.

The ACCC's CMS often re-uploads a document it has already published, appending
a fresh ``_N`` suffix to the filename ("... - Questionnaire_3.docx" becomes
"... - Questionnaire_4.docx"). ``extract_mergers._merge_events`` already
re-binds the existing timeline event to the new URL, but the old file stayed
on disk, so the repo (and the deployment) kept one copy per re-upload of what
is usually the same document.

This module finishes that job in two steps:

* :func:`record_superseded` runs at each re-bind and appends the replaced
  document to the surviving event's ``previous_versions`` — URL, served path,
  title and date as they were, so the history of a document's titles is kept.
* :func:`prune_superseded` then compares each previous version's file with the
  event's current one and deletes the old file only when the two are
  **byte-identical**. A version whose bytes differ is kept on disk, since it is
  a genuinely different document; its record just says so.

``previous_versions`` is internal record-keeping: ``slim_for_site`` drops it
from the deployed detail file, publishing only the served paths of retired
copies (``retired_url_gh``) so the PDF Pages Function can redirect old links to
the surviving document.

Each version record::

    {
      "url": ACCC URL the document used to be served from,
      "url_gh": the path we used to serve it under,
      "title": the event title it carried,
      "date": the event date it carried,
      "superseded_on": "YYYY-MM-DD" (the run that re-bound it),
      "sha256": digest of the old file (once compared),
      "identical": whether it matched the current file byte for byte,
      "retired": true once its file(s) were deleted
    }

Run as a module to backfill the copies already on disk::

    python -m scripts.document_versions            # report only
    python -m scripts.document_versions --apply    # delete + record

The backfill looks for unreferenced files sharing a referenced document's name
up to the CMS suffix, and retires the byte-identical ones exactly as a re-bind
would have.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from collections.abc import Iterable
from datetime import date
from pathlib import Path
from urllib.parse import unquote, urlparse

from scripts.paths import REPO_ROOT

MATTERS_DIR = REPO_ROOT / 'data' / 'raw' / 'matters'
MERGERS_JSON = REPO_ROOT / 'data' / 'processed' / 'mergers.json'
TRIBUNAL_APPEALS_JSON = REPO_ROOT / 'data' / 'processed' / 'tribunal_appeals.json'

FIELD = 'previous_versions'

# The CMS re-upload suffix, just before the extension.
_CMS_SUFFIX_RE = re.compile(r'_\d+(\.[^.]+)$')


def document_files(record: dict) -> tuple[str | None, str | None]:
    """The (original, served) local filenames of an event's document.

    ``url_gh`` names the file we serve, which for a DOCX is its converted PDF;
    the original is the file as the ACCC published it, and is what two
    versions are compared on (two conversions of the same DOCX are never
    byte-identical). Works for an event and for a ``previous_versions`` record
    alike, since both carry ``url`` and ``url_gh``.
    """
    url_gh = record.get('url_gh')
    if not url_gh:
        return None, None
    served = os.path.basename(unquote(url_gh))
    ext = os.path.splitext(unquote(urlparse(record.get('url') or '').path))[1]
    if ext.lower() == '.docx':
        return os.path.splitext(served)[0] + ext, served
    return served, served


def record_superseded(old_event: dict, new_event: dict, today: str | None = None) -> None:
    """Record ``old_event``'s document as a previous version of ``new_event``'s.

    Called wherever ``_merge_events`` re-binds an existing event to a
    re-uploaded document. Carries the old event's own history forward, so a
    document re-uploaded several times keeps every earlier title. Nothing is
    deleted here; see :func:`prune_superseded`.
    """
    old_url = old_event.get('url')
    new_url = new_event.get('url')
    history = [dict(v) for v in new_event.get(FIELD) or []]
    seen = {v.get('url') for v in history}
    for version in old_event.get(FIELD) or []:
        if version.get('url') not in seen:
            history.append(dict(version))
            seen.add(version.get('url'))
    if old_url and old_url != new_url and old_url not in seen:
        entry = {
            'url': old_url,
            'url_gh': old_event.get('url_gh'),
            'title': old_event.get('title'),
            'date': old_event.get('date'),
            'superseded_on': today or date.today().isoformat(),
        }
        history.append({k: v for k, v in entry.items() if v is not None})
    # The ACCC can move a document back to a URL it used before.
    history = [v for v in history if v.get('url') != new_url]
    if history:
        new_event[FIELD] = history


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _referenced_files(events: Iterable[dict], extra: Iterable[str] = ()) -> set[str]:
    names = set(extra)
    for event in events:
        names.update(n for n in document_files(event) if n)
        # An event whose filename couldn't be served has no url_gh, but its
        # download may still be on disk under the URL's own name.
        url = event.get('url')
        if url:
            names.add(os.path.basename(unquote(urlparse(url).path)).strip())
    return names


def prune_superseded(merger_id: str, events: list[dict],
                     matters_dir: Path = MATTERS_DIR,
                     extra_referenced: Iterable[str] = ()) -> list[str]:
    """Delete previous versions that are byte-identical to the current document.

    For every event with ``previous_versions``, each version whose file is
    still on disk is hashed and compared with the event's current file. A
    match is deleted — with its converted PDF, for a DOCX — unless any event
    of the matter (or a name in ``extra_referenced``, e.g. a tribunal
    document) still points at it. Records are updated in place with
    ``sha256``/``identical``, and ``retired`` once deleted.

    A version is left alone when either file is missing: without both there
    is nothing to compare, and the next run will try again.

    Returns the deleted filenames.
    """
    folder = Path(matters_dir) / merger_id
    referenced = _referenced_files(events, extra_referenced)
    removed: list[str] = []
    for event in events:
        versions = event.get(FIELD)
        if not versions:
            continue
        current, _ = document_files(event)
        current_path = folder / current if current else None
        if current_path is None or not current_path.is_file():
            continue
        current_digest = None
        for version in versions:
            if version.get('retired'):
                continue
            original, served = document_files(version)
            if not original or original == current:
                continue
            old_path = folder / original
            if not old_path.is_file():
                continue
            if current_digest is None:
                current_digest = _sha256(current_path)
            digest = _sha256(old_path)
            version['sha256'] = digest
            version['identical'] = digest == current_digest
            if not version['identical'] or original in referenced:
                continue
            old_path.unlink()
            removed.append(original)
            if served and served != original and served not in referenced:
                served_path = folder / served
                if served_path.is_file():
                    served_path.unlink()
                    removed.append(served)
            version['retired'] = True
    return removed


def retired_url_gh(event: dict) -> list[str]:
    """Served paths of an event's retired copies, for the redirect."""
    return [v['url_gh'] for v in event.get(FIELD) or []
            if v.get('retired') and v.get('url_gh')]


def tribunal_referenced_files(path: Path = TRIBUNAL_APPEALS_JSON) -> dict[str, set[str]]:
    """Local filenames mirrored for each merger's tribunal documents.

    Those share ``data/raw/matters/{id}/`` with the ACCC's documents but live
    in ``tribunal_appeals.json`` rather than in the merger's events, so they
    are passed to :func:`prune_superseded` as extra references.
    """
    try:
        with open(path, encoding='utf-8') as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}
    out: dict[str, set[str]] = {}
    for merger_id, records in data.items():
        if merger_id.startswith('_'):
            continue
        if isinstance(records, dict):
            records = [records]
        names = out.setdefault(merger_id, set())
        for record in records or []:
            for doc in record.get('documents') or []:
                names.update(n for n in document_files(doc) if n)
                url = doc.get('url')
                if url:
                    names.add(os.path.basename(unquote(urlparse(url).path)))
    return out


def prune_all(mergers: list[dict], matters_dir: Path | str = MATTERS_DIR) -> list[str]:
    """Run :func:`prune_superseded` over every merger; returns deleted paths."""
    tribunal = tribunal_referenced_files()
    removed = []
    for merger in mergers:
        merger_id = merger.get('merger_id')
        if not merger_id:
            continue
        for name in prune_superseded(merger_id, merger.get('events') or [],
                                     matters_dir, tribunal.get(merger_id, ())):
            removed.append(f'{merger_id}/{name}')
    return removed


def _strip_cms_suffix(name: str) -> str:
    return _CMS_SUFFIX_RE.sub(r'\1', name)


def backfill(mergers: list[dict], matters_dir: Path = MATTERS_DIR,
             apply: bool = False, today: str | None = None) -> dict:
    """Retire copies left behind by re-binds that predate this module.

    For each event's current document, any file in the matter's folder with
    the same name up to the CMS suffix (same extension) that nothing
    references is a leftover re-upload. Byte-identical ones are recorded on
    the event and, with ``apply``, deleted; the rest are only reported.
    Leftovers that are their own original's converted PDF are handled with
    their DOCX, never compared on their own.
    """
    tribunal = tribunal_referenced_files()
    today = today or date.today().isoformat()
    report = {'retired': [], 'different': []}
    for merger in mergers:
        merger_id = merger.get('merger_id')
        events = merger.get('events') or []
        folder = Path(matters_dir) / (merger_id or '')
        if not merger_id or not folder.is_dir():
            continue
        extra = tribunal.get(merger_id, set())
        referenced = _referenced_files(events, extra)
        for version in (v for e in events for v in e.get(FIELD) or []):
            referenced.update(n for n in document_files(version) if n)
        files = sorted(p.name for p in folder.iterdir() if p.is_file())
        claimed: set[str] = set()
        for event in events:
            current, _ = document_files(event)
            if not current or not (folder / current).is_file():
                continue
            key = _strip_cms_suffix(current)
            current_digest = None
            for name in files:
                if (name == current or name in referenced or name in claimed
                        or _strip_cms_suffix(name) != key):
                    continue
                claimed.add(name)
                if current_digest is None:
                    current_digest = _sha256(folder / current)
                digest = _sha256(folder / name)
                if digest != current_digest:
                    report['different'].append(f'{merger_id}/{name}')
                    continue
                url_gh = event['url_gh'].rsplit('/', 1)[0] + '/' + (
                    os.path.splitext(name)[0] + '.pdf'
                    if name.lower().endswith('.docx') else name)
                version = {
                    'url_gh': url_gh,
                    'title': os.path.splitext(name)[0],
                    'superseded_on': today,
                    'sha256': digest,
                    'identical': True,
                }
                report['retired'].append(f'{merger_id}/{name}')
                if apply:
                    (folder / name).unlink()
                    served = os.path.basename(url_gh)
                    if (served != name and served not in referenced
                            and (folder / served).is_file()):
                        (folder / served).unlink()
                        claimed.add(served)
                        report['retired'].append(f'{merger_id}/{served}')
                    version['retired'] = True
                    event.setdefault(FIELD, []).append(version)
                elif name.lower().endswith('.docx'):
                    claimed.add(os.path.basename(url_gh))
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--apply', action='store_true',
                        help='delete the identical copies and record them in mergers.json')
    args = parser.parse_args(argv)

    from scripts.merger_filters import load_mergers, save_mergers

    mergers = load_mergers(str(MERGERS_JSON))
    report = backfill(mergers, apply=args.apply)
    # Save before reporting: the files are already gone, so a report cut short
    # (a closed pipe) must not leave mergers.json without their records.
    if args.apply:
        save_mergers(mergers)
    verb = 'Retired' if args.apply else 'Would retire'
    print(f"{verb} {len(report['retired'])} byte-identical file(s):")
    for name in report['retired']:
        print(f'  {name}')
    print(f"Kept {len(report['different'])} leftover re-upload(s) whose bytes differ:")
    for name in report['different']:
        print(f'  {name}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
