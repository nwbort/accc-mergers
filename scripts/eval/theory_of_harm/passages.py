"""The passages the theory-of-harm classifier sees, with stable ids.

Production (``outputs/theories_of_harm.py``) classifies two kinds of text:

- each item in a Phase 2 notice's "matters to investigate" boxes, and
- each paragraph, heading and bullet in a NOCC summary.

This module yields the same text, plus the context a model needs to read it:
the merger, the box heading or NOCC section, and the nearest NOCC sub-heading.

An id is ``{merger_id}/{source}/{hash}``, the hash taken over the heading and
the text. Re-scraping a document leaves the ids of unchanged passages alone,
which is what lets the gold set outlive a re-parse. The ACCC repeats sentences
word for word under different headings (IAG–RACI's motor and home sections),
so the heading is part of the hash.
"""

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from typing import Iterator, Optional

from scripts.generate.static_data.outputs.theories_of_harm import _classify
from scripts.paths import REPO_ROOT

MERGERS_JSON = REPO_ROOT / 'data' / 'processed' / 'mergers.json'
NOCC_JSON = REPO_ROOT / 'data' / 'processed' / 'nocc_data.json'

# NOCC sections that hold the competition assessment itself. Everything else
# (introduction, background, market definition, remedies, next steps) is
# mostly negatives, so the gold set takes only their keyword hits.
ASSESSMENT_SECTION = re.compile(
    r'competition (concerns|assessment)|future with|no longer under', re.I,
)


@dataclass
class Passage:
    id: str
    merger_id: str
    merger_name: Optional[str]
    source: str                 # 'phase2_notice' | 'nocc'
    section: Optional[str]      # NOCC section title; None for Phase 2 items
    heading: Optional[str]      # Phase 2 box heading, or the NOCC sub-heading above
    block_type: Optional[str]   # NOCC block type: paragraph | bullet_list | heading
    number: Optional[str]       # NOCC paragraph number, e.g. "4.12"
    text: str

    def to_dict(self) -> dict:
        return asdict(self)


def passage_id(merger_id: str, source: str, context: Optional[str], text: str) -> str:
    digest = hashlib.sha1(f'{context or ""}\n{text}'.encode('utf-8')).hexdigest()[:10]
    return f'{merger_id}/{source}/{digest}'


def iter_phase2(mergers: list) -> Iterator[Passage]:
    for m in mergers:
        for event in m.get('events', []):
            for box in event.get('phase2_notice_matters_to_investigate') or []:
                heading = box.get('heading')
                for item in box.get('items', []):
                    if item:
                        yield Passage(
                            id=passage_id(m['merger_id'], 'phase2_notice', heading, item),
                            merger_id=m['merger_id'],
                            merger_name=m.get('merger_name'),
                            source='phase2_notice',
                            section=None,
                            heading=heading,
                            block_type=None,
                            number=None,
                            text=item,
                        )


def iter_nocc(nocc_data: dict, merger_names: dict) -> Iterator[Passage]:
    for merger_id, data in (nocc_data or {}).items():
        for section in data.get('sections', []):
            title = section.get('title')
            subheading = None
            for block in section.get('blocks', []):
                texts = [block['text']] if block.get('text') else (block.get('items') or [])
                for text in texts:
                    if not text:
                        continue
                    # A heading block is its own passage (production classifies
                    # it too) as well as the context for what follows it.
                    heading = None if block.get('type') == 'heading' else subheading
                    context = '\n'.join(filter(None, [title, heading]))
                    yield Passage(
                        id=passage_id(merger_id, 'nocc', context, text),
                        merger_id=merger_id,
                        merger_name=merger_names.get(merger_id),
                        source='nocc',
                        section=title,
                        heading=heading,
                        block_type=block.get('type'),
                        number=block.get('number') or None,
                        text=text,
                    )
                if block.get('type') == 'heading' and block.get('text'):
                    subheading = block['text']


def load_all() -> list[Passage]:
    """Every passage production classifies, Phase 2 items first."""
    mergers = json.loads(MERGERS_JSON.read_text())
    nocc = json.loads(NOCC_JSON.read_text()) if NOCC_JSON.exists() else {}
    names = {m['merger_id']: m.get('merger_name') for m in mergers}
    passages = list(iter_phase2(mergers)) + list(iter_nocc(nocc, names))
    # The same sentence under the same heading twice in one document (a
    # repeated process step in a background list): number the repeats.
    seen: dict[str, int] = {}
    for p in passages:
        n = seen.get(p.id, 0) + 1
        seen[p.id] = n
        if n > 1:
            p.id = f'{p.id}-{n}'
    return passages


def is_gold_candidate(p: Passage) -> bool:
    """Whether ``sync`` should offer this passage for labelling.

    Every Phase 2 item; every NOCC passage in an assessment section; and any
    other NOCC passage the keyword classifier fires on, since those are where
    its false positives live. The rest of the NOCC text is background, so the
    gold set holds only a fixed sample of it as negatives.
    """
    if p.source == 'phase2_notice':
        return True
    if p.section and ASSESSMENT_SECTION.search(p.section):
        return True
    return bool(_classify(p.text))
