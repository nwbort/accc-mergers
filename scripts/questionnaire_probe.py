"""Guess where a questionnaire the ACCC page doesn't list would live.

The ACCC names a questionnaire after the matter, so a notification whose page
omits it can often be found by trying the filenames recent matters used:

    {name} - Questionnaire.docx
    Questionnaire - {name}.docx
    {name} - third-party questionnaire.docx
    {name} - Third-party questionnaire - Phase 1 consultation - 28 September 2026.docx

each optionally with the ``_0``/``_1`` suffix Drupal adds when a name is
re-uploaded. Roughly two thirds of recent files contain the register's matter
name verbatim; the rest (``MPMS-Grow - Questionnaire_0.docx``) can't be guessed.

The ACCC answers a missing file with a clean 404 and a real one with a 200, so a
``HEAD`` is enough. A hit only ever *reports* the URL: it doesn't touch the
timeline, because a guessed link is a lead for a person, not a fact about the page.
"""

from __future__ import annotations

import re
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from itertools import product
from urllib.parse import quote

import requests

from scripts.normalization import normalize_dashes

BASE_URL = 'https://www.accc.gov.au/system/files/moderated_files/'
DOC_CONTENT_TYPES = ('officedocument', 'msword', 'pdf')
# Every questionnaire published since mid-September 2026 is a Word document.
EXTENSIONS = ('docx',)
SUFFIXES = ('', '_0', '_1')
# The dated "Phase 1 consultation" title carries the day the ACCC published,
# which has run from the notified date to three days after it.
CONSULTATION_DAY_OFFSETS = range(0, 6)

# {n} is the matter name, {d} a 'D Month YYYY' date. Only shapes seen on
# questionnaires published since mid-September 2026 are tried; older shapes
# (' - Questionnaires', PDFs, 'Third Party Questionnaire') have not recurred.
STEM_TEMPLATES = (
    '{n} - Questionnaire',
    'Questionnaire - {n}',
    '{n} - third-party questionnaire',
    '{n} - Third party questionnaire',
    '{id} - {n} - questionnaire',
)
DATED_STEM_TEMPLATES = (
    '{n} - Third-party questionnaire - Phase 1 consultation - {d}',
)
REQUEST_TIMEOUT = 15
MAX_WORKERS = 8


def _name_variants(name: str) -> list[str]:
    """The register's name as written, with plain dashes, and without a trailing
    parenthetical (the ACCC drops "(Tasmania)" from some filenames)."""
    name = ' '.join((name or '').split())
    plain = normalize_dashes(name)
    variants = [name, plain]
    variants += [re.sub(r'\s*\([^)]*\)\s*$', '', v) for v in (name, plain)]
    return list(dict.fromkeys(v for v in variants if v))


def _consultation_dates(notified: str) -> list[str]:
    """'D Month YYYY' strings for the days a consultation is likely published."""
    try:
        start = datetime.strptime(notified[:10], '%Y-%m-%d')
    except ValueError:
        return []
    days = (start + timedelta(days=o) for o in CONSULTATION_DAY_OFFSETS)
    return [f'{d.day} {d:%B %Y}' for d in days]


def candidate_urls(merger: dict) -> list[str]:
    """Every URL worth trying for this matter, most likely first, no repeats."""
    names = _name_variants(merger.get('merger_name', ''))
    if not names:
        return []
    merger_id = merger.get('merger_id', '')
    notified = merger.get('effective_notification_datetime') or ''

    stems: list[str] = []
    dated: list[str] = []
    for name in names:
        stems += [t.format(n=name, id=merger_id) for t in STEM_TEMPLATES]
        if name not in names[:2]:  # dated files use the name as the ACCC wrote it
            continue
        for date in _consultation_dates(notified):
            dated += [t.format(n=name, d=date) for t in DATED_STEM_TEMPLATES]

    urls = [
        f'{BASE_URL}{quote(stem + suffix)}.{ext}'
        for stem, suffix, ext in product(stems + dated, SUFFIXES, EXTENSIONS)
    ]
    return list(dict.fromkeys(urls))


def _is_document(url: str, session: requests.Session) -> bool:
    """True when the URL serves a document. Network errors read as 'not found'."""
    try:
        response = session.head(url, timeout=REQUEST_TIMEOUT, allow_redirects=False)
    except Exception:  # best effort: a probe must never fail the pipeline
        return False
    content_type = response.headers.get('content-type', '').lower()
    return response.status_code == 200 and any(t in content_type for t in DOC_CONTENT_TYPES)


def probe_questionnaire(merger: dict, session: requests.Session | None = None) -> str | None:
    """Return the first candidate URL that serves a document, else None."""
    urls = candidate_urls(merger)
    if not urls:
        return None
    session = session or requests.Session()
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        # map() keeps candidate order, so the likeliest hit wins a tie.
        for url, found in zip(urls, pool.map(lambda u: _is_document(u, session), urls)):
            if found:
                print(
                    f"Probed a questionnaire for {merger.get('merger_id')}: {url}",
                    file=sys.stderr,
                )
                return url
    return None
