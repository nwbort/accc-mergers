"""Scoring a run against the gold set.

Multi-label: each passage carries a set of categories (often empty), and so does
each prediction. Counted per category, then pooled:

- **micro** precision/recall/F1 pool every (passage, category) decision, so the
  common categories dominate. It is the headline number.
- **macro** F1 averages the per-category F1s, so a model that never finds
  coordinated effects is visibly punished even though they are rare.
- **exact match** is the share of passages where the whole set is right.
- **empty precision** is the share of gold-empty passages (headings, background,
  procedure) where the model also said nothing: how well it holds back from
  over-labelling. The production classifier's main failure is the opposite.

A passage whose prediction errored counts as an empty prediction, so errors cost
recall rather than silently shrinking the denominator. They are reported too.
"""

from .taxonomy import CATEGORIES


def _prf(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return p, r, f


def predicted_set(scores: dict, threshold: float) -> set:
    return {c for c, s in (scores or {}).items() if s >= threshold}


def score(gold: list[dict], predicted: dict[str, set]) -> dict:
    """``predicted`` maps passage id -> set of categories."""
    per = {c: {'tp': 0, 'fp': 0, 'fn': 0, 'support': 0} for c in CATEGORIES}
    exact = 0
    empty_total = empty_right = 0
    for e in gold:
        truth = set(e['labels'])
        guess = predicted.get(e['id'], set())
        exact += truth == guess
        if not truth:
            empty_total += 1
            empty_right += not guess
        for c in CATEGORIES:
            if c in truth:
                per[c]['support'] += 1
            if c in truth and c in guess:
                per[c]['tp'] += 1
            elif c in guess:
                per[c]['fp'] += 1
            elif c in truth:
                per[c]['fn'] += 1

    for c, d in per.items():
        d['precision'], d['recall'], d['f1'] = _prf(d['tp'], d['fp'], d['fn'])
    tp = sum(d['tp'] for d in per.values())
    fp = sum(d['fp'] for d in per.values())
    fn = sum(d['fn'] for d in per.values())
    micro_p, micro_r, micro_f = _prf(tp, fp, fn)
    # Categories absent from both gold and predictions say nothing; leave them out.
    scored = [d['f1'] for d in per.values() if d['support'] or d['fp']]
    return {
        'n': len(gold),
        'micro': {'precision': micro_p, 'recall': micro_r, 'f1': micro_f,
                  'tp': tp, 'fp': fp, 'fn': fn},
        'macro_f1': sum(scored) / len(scored) if scored else 0.0,
        'exact_match': exact / len(gold) if gold else 0.0,
        'empty_precision': empty_right / empty_total if empty_total else 0.0,
        'per_category': per,
    }


def threshold_sweep(gold: list[dict], scores_by_id: dict[str, dict],
                    thresholds=(0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9)) -> list[dict]:
    """Micro P/R/F1 at each threshold, for providers that return probabilities."""
    rows = []
    for t in thresholds:
        predicted = {pid: predicted_set(s, t) for pid, s in scores_by_id.items()}
        m = score(gold, predicted)['micro']
        rows.append({'threshold': t, **{k: m[k] for k in ('precision', 'recall', 'f1')}})
    return rows


def is_probabilistic(scores_by_id: dict[str, dict]) -> bool:
    return any(0.0 < s < 1.0 for scores in scores_by_id.values() for s in scores.values())
