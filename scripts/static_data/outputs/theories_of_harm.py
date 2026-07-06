"""Theory-of-harm taxonomy — ``theories_of_harm.json``.

Keyword-based classifier over the two places the ACCC's substantive
competition concerns show up in already-parsed data:

- ``phase2_notice_matters_to_investigate`` on Phase 2 Notice events (a list
  of ``{heading, items}`` boxes per merger, see ``parse_phase2_notice.py``).
- NOCC (Notice of Competition Concerns) section text, ``data/processed/nocc_data.json``.

Phase 2 matters are a small, enumerable set, so precision matters more than
recall here: an item that doesn't clearly match a category goes to
``unclassified`` rather than being force-fitted. NOCC text is bulkier prose
(introductions, party backgrounds, next steps) that was never meant to be
exhaustively classified, so only text that actually matches a category is
surfaced — there's no NOCC-side "unclassified" bucket.

To add or tune a category, edit ``CATEGORY_KEYWORDS`` (and ``CATEGORY_LABELS``
for its display name). Keywords are matched as case-insensitive substrings,
so prefer specific multi-word phrases over single common words to avoid
false positives (e.g. "barriers to entry" rather than bare "barrier", which
also shows up in unrelated geographic/demand-side-substitution discussion).
"""

CATEGORY_LABELS = {
    'horizontal_unilateral_effects': 'Horizontal unilateral effects',
    'coordinated_effects': 'Coordinated effects',
    'vertical_foreclosure': 'Vertical foreclosure',
    'conglomerate_bundling': 'Conglomerate / bundling',
    'potential_nascent_competition': 'Potential / nascent competition',
    'buyer_power': 'Buyer power',
    'entry_barriers': 'Entry barriers',
}

CATEGORY_KEYWORDS = {
    'horizontal_unilateral_effects': [
        'unilateral effect',
        'compete closely',
        'competing closely',
        'closeness of competition',
        'close competitor',
        'removal of a competitor',
        'removal of an effective competitor',
        'removal of a key provider',
        'removal of a direct competitor',
        'meaningfully constrain',
        'loss of competition between',
    ],
    'coordinated_effects': [
        'coordinated effect',
        'coordination between',
        'price cycle',
        'facilitate coordination',
        'tacit coordination',
        'collusive',
    ],
    'vertical_foreclosure': [
        'foreclose',
        'foreclosure',
        'frustrate competing',
        'restrict rival',
        'restricting rival',
        'input foreclosure',
        'customer foreclosure',
        "raise rivals’ costs",
        'raise rivals costs',
        'deny access',
        'refuse to supply',
    ],
    'conglomerate_bundling': [
        'bundl',
        'one-stop shop',
        'tying',
        'single supplier',
        'cross-sell',
        'full suite of',
    ],
    'potential_nascent_competition': [
        'nascent',
        'potential competition',
        'potential competitor',
        'future competitiveness',
        'future competitor',
        'emerging competitor',
        "would-be competitor",
        'future competition',
    ],
    'buyer_power': [
        'buyer power',
        'buying power',
        'countervailing power',
        'monopsony',
        'bargaining power',
    ],
    'entry_barriers': [
        'barrier to entry',
        'barriers to entry',
        'entry barrier',
        'new entry',
        'new entrant',
        'timely entry',
        'entry and expansion',
        'expansion by rivals',
    ],
}


def _classify(text: str) -> list:
    """Return ``[(category, matched_phrase), ...]`` for every category whose
    keyword list has a hit in ``text`` (zero, one, or several)."""
    low = text.lower()
    matches = []
    for category, phrases in CATEGORY_KEYWORDS.items():
        for phrase in phrases:
            if phrase in low:
                matches.append((category, phrase))
                break
    return matches


def _iter_phase2_matters(mergers: list):
    """Yield ``(merger_id, merger_name, heading, item)`` for every bullet
    item in every Phase 2 Notice "matters to investigate" box."""
    for m in mergers:
        for event in m.get('events', []):
            boxes = event.get('phase2_notice_matters_to_investigate')
            if not boxes:
                continue
            for box in boxes:
                heading = box.get('heading')
                for item in box.get('items', []):
                    yield m.get('merger_id'), m.get('merger_name'), heading, item


def _iter_nocc_text(nocc_data: dict):
    """Yield ``(merger_id, section_heading, text)`` for every paragraph,
    heading, and bullet-list item across a merger's NOCC sections."""
    for merger_id, data in (nocc_data or {}).items():
        for section in data.get('sections', []):
            heading = section.get('title')
            for block in section.get('blocks', []):
                texts = [block['text']] if block.get('text') else (block.get('items') or [])
                for text in texts:
                    if text:
                        yield merger_id, heading, text


def generate(mergers: list, nocc_data: dict = None) -> dict:
    """Return the theories_of_harm.json payload."""
    merger_names = {m.get('merger_id'): m.get('merger_name') for m in mergers}

    categories = {
        key: {'label': CATEGORY_LABELS[key], 'count': 0, 'matters': []}
        for key in CATEGORY_KEYWORDS
    }
    unclassified = []

    for merger_id, merger_name, heading, item in _iter_phase2_matters(mergers):
        matches = _classify(item)
        if not matches:
            unclassified.append({
                'merger_id': merger_id,
                'merger_name': merger_name,
                'heading': heading,
                'excerpt': item,
            })
            continue
        for category, phrase in matches:
            categories[category]['matters'].append({
                'merger_id': merger_id,
                'merger_name': merger_name,
                'source': 'phase2_notice',
                'heading': heading,
                'excerpt': item,
                'matched_phrase': phrase,
            })

    for merger_id, heading, text in _iter_nocc_text(nocc_data):
        for category, phrase in _classify(text):
            categories[category]['matters'].append({
                'merger_id': merger_id,
                'merger_name': merger_names.get(merger_id),
                'source': 'nocc',
                'heading': heading,
                'excerpt': text,
                'matched_phrase': phrase,
            })

    for cat in categories.values():
        cat['count'] = len(cat['matters'])

    return {
        'categories': categories,
        'unclassified': {
            'count': len(unclassified),
            'matters': unclassified,
        },
    }
