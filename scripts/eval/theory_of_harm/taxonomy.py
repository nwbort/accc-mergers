"""What each theory-of-harm category means, for people and models alike.

The category *keys* and *labels* are the production ones in
``scripts/generate/static_data/outputs/theories_of_harm.py``. They are imported
from there, so the gold set can't drift from what the site publishes. If a key
is added or renamed there, the gold-set test fails until it has a definition
here.

The definitions below do two jobs:

- they are the labelling guidelines a person follows when reviewing
  ``gold.jsonl`` (``python -m scripts.eval.theory_of_harm review`` prints them), and
- they are pasted verbatim into the prompt every model provider receives.

Keeping one copy means a model is judged against the rules the labels were
written to, not a paraphrase of them. Editing a definition changes the prompt,
and so the cache key, so the next run re-asks every model.
"""

from scripts.generate.static_data.outputs.theories_of_harm import CATEGORY_LABELS

# Ordered as the production taxonomy orders them.
CATEGORIES: list[str] = list(CATEGORY_LABELS)

DEFINITIONS: dict[str, str] = {
    'horizontal_unilateral_effects': (
        'Loss of rivalry between the merging parties that would let the merged '
        'firm, on its own, raise prices or worsen its offer. Includes: overlap '
        'between the parties, closeness of competition, removal of a competitor, '
        'market shares and concentration, how strongly remaining rivals would '
        'constrain the merged firm, market power, pricing-pressure measures '
        '(GUPPI, IPR), how strong a competitor the target is, and whether it would '
        'remain one without the acquisition (the counterfactual, including '
        'failing-firm arguments).'
    ),
    'coordinated_effects': (
        'Whether the acquisition makes tacit or explicit coordination among the '
        'remaining firms more likely, more complete or more sustainable. A '
        'description of market features such as petrol price cycles counts only '
        'when it is used as part of a coordination analysis.'
    ),
    'vertical_foreclosure': (
        'The merged firm\'s ability or incentive to foreclose rivals from an '
        'input or a route to customers, or to raise their costs, through a '
        'vertical relationship: exclusivity, priority access, refusing supply, '
        'and the capacity or access conditions that make that possible.'
    ),
    'conglomerate_bundling': (
        'Portfolio or range effects across products or services: bundling, '
        'tying, one-stop-shop offers, customers who need one supplier for a '
        'broad range, and whether rivals could match that range (for example '
        'by teaming up). A product called "unbundled" does not count.'
    ),
    'potential_nascent_competition': (
        'Loss of competition that does not exist yet but would likely emerge '
        'without the acquisition: a party that would enter or expand to compete '
        'more strongly, or the acquisition of a nascent rival. Whether the '
        'target keeps competing as it does today is horizontal, not this.'
    ),
    'buyer_power': (
        'Two things, as the production taxonomy groups them: (a) customers\' '
        'countervailing power as a constraint on the merged firm, including '
        'credible threats to bypass it, self-supply or sponsor new entry; and '
        '(b) the merged firm\'s own buying (monopsony) power over its suppliers.'
    ),
    'entry_barriers': (
        'Whether entry or expansion by rivals would be likely, timely and '
        'sufficient to constrain the merged firm, and the barriers that affect '
        'it: sunk costs, regulation and accreditation, relationships, customer '
        'stickiness, scale, recent examples of entry. Sponsored entry by '
        'customers is buyer power, not this.'
    ),
}

GENERAL_RULES: list[str] = [
    'Label the passage on its own. Use the heading and section only to understand it, '
    'never as the reason for a label.',
    'A passage can have several categories, or none.',
    'A category applies when the passage raises, investigates or assesses that mechanism '
    'as part of the competition analysis. That holds whether the ACCC finds a concern '
    'or dismisses one.',
    'No category: market definition (product or geographic dimensions, substitutability), '
    'background facts about the parties or the industry, procedure and timing, headings, '
    'lead-in sentences ("The ACCC considered:"), and bare conclusions that the acquisition '
    'would or would not substantially lessen competition without naming how.',
    'A passage that only refers back ("The ACCC will consider this issue further") '
    'gets no category.',
    'Prefer no category to a guess.',
]


def guidelines_text() -> str:
    """The definitions and rules as plain text, for the review CLI and the prompt."""
    lines = ['Categories:']
    for key in CATEGORIES:
        lines.append(f'- {key} ({CATEGORY_LABELS[key]}): {DEFINITIONS[key]}')
    lines.append('')
    lines.append('Rules:')
    lines.extend(f'- {rule}' for rule in GENERAL_RULES)
    return '\n'.join(lines)
