"""``python -m scripts.eval.theory_of_harm <command>``: see README.md.

    run     score one or more models against the gold set
    review  walk the gold set and confirm or correct its labels
    sync    add passages that appeared since the gold set was built
    stats   what the gold set holds
"""

import argparse
import hashlib
import json
import shutil
import sys
import textwrap
import time
from datetime import datetime, timezone
from pathlib import Path

from scripts.paths import REPO_ROOT

from . import gold as gold_mod
from .metrics import is_probabilistic, predicted_set, score, threshold_sweep
from .providers import Prediction, make_provider, user_prompt, verify_evidence
from .taxonomy import CATEGORIES, CATEGORY_LABELS, guidelines_text

OUT_DIR = REPO_ROOT / 'data' / 'output' / 'eval' / 'theory_of_harm'
CACHE_DIR = OUT_DIR / 'cache'
RUNS_DIR = OUT_DIR / 'runs'

SHORT = {
    'horizontal_unilateral_effects': 'horiz',
    'coordinated_effects': 'coord',
    'vertical_foreclosure': 'vert',
    'conglomerate_bundling': 'congl',
    'potential_nascent_competition': 'potential',
    'buyer_power': 'buyer',
    'entry_barriers': 'entry',
}


# ── run ─────────────────────────────────────────────────────────────────────

def _cache_path(provider, entry: dict) -> Path:
    key = hashlib.sha256((provider.identity() + '\n' + user_prompt(entry)).encode()).hexdigest()
    slug = ''.join(ch if ch.isalnum() or ch in '-._' else '_' for ch in provider.name)[:80]
    return CACHE_DIR / slug / f'{key}.json'


def _predict(provider, entries: list[dict], workers: int, use_cache: bool) -> list[Prediction]:
    preds: list = [None] * len(entries)
    missing = []
    for i, e in enumerate(entries):
        path = _cache_path(provider, e)
        if use_cache and provider.cacheable and path.exists():
            preds[i] = Prediction.from_dict(json.loads(path.read_text()))
        else:
            missing.append(i)
    if missing:
        print(f'  {provider.name}: {len(missing)} to classify, {len(entries) - len(missing)} cached',
              file=sys.stderr)
        fresh = provider.predict_batch([entries[i] for i in missing], workers)
        for i, pred in zip(missing, fresh):
            preds[i] = pred
            # Errors aren't cached, so a re-run retries them.
            if provider.cacheable and pred.error is None:
                path = _cache_path(provider, entries[i])
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(pred.to_dict(), ensure_ascii=False))
    return preds


def _evaluate(name: str, entries: list[dict], preds: list[Prediction], threshold: float,
              evidence_gate: bool) -> dict:
    by_id = {}
    scores_by_id = {}
    evidence_checked = evidence_ok = 0
    for e, p in zip(entries, preds):
        scores = dict(p.scores) if not p.error else {}
        if evidence_gate:
            scores = {c: s for c, s in scores.items()
                      if verify_evidence(p.evidence.get(c, ''), e['text'])}
        else:
            for c in predicted_set(scores, threshold):
                if c in p.evidence:
                    evidence_checked += 1
                    evidence_ok += verify_evidence(p.evidence[c], e['text'])
        scores_by_id[e['id']] = scores
        by_id[e['id']] = predicted_set(scores, threshold)

    unambiguous = [e for e in entries if not e.get('ambiguous')]
    result = {
        'name': name,
        'all': score(entries, by_id),
        'unambiguous': score(unambiguous, by_id),
        'predicted': {k: sorted(v) for k, v in by_id.items()},
        'errors': sum(1 for p in preds if p.error),
        'invalid_labels': sum(len(p.invalid) for p in preds),
        'evidence_verified': (evidence_ok / evidence_checked) if evidence_checked else None,
        'input_tokens': sum(p.usage.get('input_tokens', 0) for p in preds),
        'output_tokens': sum(p.usage.get('output_tokens', 0) for p in preds),
        'seconds_per_passage': sum(p.seconds for p in preds) / len(preds) if preds else 0,
    }
    if is_probabilistic(scores_by_id):
        result['sweep'] = threshold_sweep(entries, scores_by_id)
    return result


def _pct(x) -> str:
    return '—' if x is None else f'{x * 100:.0f}%'


def _report(results: list[dict], entries: list[dict], args, show_errors: int) -> str:
    drafts = sum(1 for e in entries if e['status'] == 'draft')
    ambiguous = sum(1 for e in entries if e.get('ambiguous'))
    lines = [f'# Theory-of-harm eval — {datetime.now().strftime("%Y-%m-%d %H:%M")}', '']
    lines.append(f'{len(entries)} gold passages ({ambiguous} marked ambiguous), threshold {args.threshold}.')
    if drafts:
        lines.append('')
        lines.append(f'**{drafts} of them carry draft labels nobody has reviewed yet.** They were '
                     'drafted by a model, so these numbers partly measure agreement with that '
                     'model. Run `review` to confirm them, then `run --reviewed-only`.')

    for subset, title in (('all', 'All passages'), ('unambiguous', 'Excluding ambiguous passages')):
        lines += ['', f'## {title}', '',
                  '| model | micro P | micro R | micro F1 | macro F1 | exact | empty ok | errors |',
                  '|---|---|---|---|---|---|---|---|']
        for r in results:
            m = r[subset]
            lines.append(
                f"| {r['name']} | {_pct(m['micro']['precision'])} | {_pct(m['micro']['recall'])} "
                f"| **{_pct(m['micro']['f1'])}** | {_pct(m['macro_f1'])} | {_pct(m['exact_match'])} "
                f"| {_pct(m['empty_precision'])} | {r['errors']} |")

    lines += ['', '## F1 by category (all passages)', '',
              '| model | ' + ' | '.join(f"{SHORT[c]} ({r0})" for c, r0 in
                                         ((c, results[0]['all']['per_category'][c]['support'])
                                          for c in CATEGORIES)) + ' |',
              '|---|' + '---|' * len(CATEGORIES)]
    for r in results:
        pc = r['all']['per_category']
        lines.append(f"| {r['name']} | " + ' | '.join(
            f"{_pct(pc[c]['f1'])} ({pc[c]['tp']}/{pc[c]['fp']}/{pc[c]['fn']})" for c in CATEGORIES) + ' |')
    lines.append('')
    lines.append('Cells are F1 (true positives / false positives / misses); headers show how '
                 'many gold passages carry each category.')

    lines += ['', '## Cost and checks', '',
              '| model | input tokens | output tokens | s/passage | evidence verified | invalid labels |',
              '|---|---|---|---|---|---|']
    for r in results:
        lines.append(f"| {r['name']} | {r['input_tokens']:,} | {r['output_tokens']:,} "
                     f"| {r['seconds_per_passage']:.2f} | {_pct(r['evidence_verified'])} "
                     f"| {r['invalid_labels']} |")
    lines.append('')
    lines.append('"Evidence verified" is the share of predicted labels whose quote really appears '
                 'in the passage. A model scored again with the unverified labels dropped appears '
                 'as "+ evidence gate".')

    for r in results:
        if 'sweep' in r:
            lines += ['', f"## Threshold sweep — {r['name']}", '', '| threshold | P | R | F1 |', '|---|---|---|---|']
            for row in r['sweep']:
                lines.append(f"| {row['threshold']} | {_pct(row['precision'])} | {_pct(row['recall'])} | {_pct(row['f1'])} |")

    if show_errors:
        for r in results:
            wrong = [e for e in entries if set(e['labels']) != set(r['predicted'][e['id']])]
            lines += ['', f"## Disagreements — {r['name']} ({len(wrong)})", '']
            for e in wrong[:show_errors]:
                gold_l = ', '.join(SHORT[c] for c in e['labels']) or 'none'
                pred_l = ', '.join(SHORT[c] for c in r['predicted'][e['id']]) or 'none'
                text = textwrap.shorten(e['text'], 220, placeholder='…')
                flag = ' (ambiguous)' if e.get('ambiguous') else ''
                lines.append(f"- `{e['id']}`{flag} gold **{gold_l}**, model **{pred_l}**: {text}")
            if len(wrong) > show_errors:
                lines.append(f'- … and {len(wrong) - show_errors} more (all in the run JSON)')
    return '\n'.join(lines) + '\n'


def cmd_run(args) -> int:
    entries = gold_mod.load()
    problems = gold_mod.validate(entries)
    if problems:
        print('gold.jsonl is invalid:\n  ' + '\n  '.join(problems[:20]), file=sys.stderr)
        return 1
    entries = gold_mod.select(entries, reviewed_only=args.reviewed_only,
                              exclude_ambiguous=args.exclude_ambiguous, source=args.source)
    if args.merger:
        entries = [e for e in entries if e['merger_id'] in args.merger]
    if args.limit:
        entries = entries[:args.limit]
    if not entries:
        print('No gold passages match.', file=sys.stderr)
        return 1

    results = []
    for spec in args.model:
        provider = make_provider(spec)
        start = time.monotonic()
        preds = _predict(provider, entries, args.workers, not args.no_cache)
        print(f'  {provider.name}: done in {time.monotonic() - start:.1f}s', file=sys.stderr)
        results.append(_evaluate(provider.name, entries, preds, args.threshold, evidence_gate=False))
        if any(p.evidence for p in preds) and spec != 'keyword':
            results.append(_evaluate(f'{provider.name} + evidence gate', entries, preds,
                                     args.threshold, evidence_gate=True))

    report = _report(results, entries, args, args.show_errors)
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    (RUNS_DIR / f'{stamp}.md').write_text(report)
    (RUNS_DIR / f'{stamp}.json').write_text(json.dumps(
        {'args': {k: v for k, v in vars(args).items() if k != 'func'}, 'gold_ids': [e['id'] for e in entries], 'results': results}, indent=1))
    print(report)
    print(f'Written to {RUNS_DIR / stamp}.md / .json', file=sys.stderr)
    return 0


# ── review ──────────────────────────────────────────────────────────────────

REVIEW_HELP = """\
  Enter   accept the labels shown          0      no category
  1-7     set labels, e.g. "1 7" or "17"   a      toggle ambiguous
  n       add or replace the note          s      skip for now
  ?       show the guidelines              q      save and quit"""


def _show(e: dict, blind: bool, pos: str) -> None:
    width = min(shutil.get_terminal_size((100, 20)).columns, 110)
    print('\n' + '─' * width)
    print(f"{pos}  {e['id']}  [{e['status']}]{'  AMBIGUOUS' if e.get('ambiguous') else ''}")
    print(f"{e.get('merger_name') or e['merger_id']} · "
          f"{'Phase 2 notice' if e['source'] == 'phase2_notice' else 'NOCC'}"
          + (f" · {e['section']}" if e.get('section') else '')
          + (f" › {e['heading']}" if e.get('heading') else ''))
    print()
    print(textwrap.fill(e['text'], width=width))
    print()
    for i, c in enumerate(CATEGORIES, 1):
        mark = '■' if not blind and c in (e.get('labels') or []) else ' '
        print(f'  {mark} {i} {CATEGORY_LABELS[c]}')
    if e.get('notes'):
        print(f"\n  note: {e['notes']}")


def cmd_review(args) -> int:
    entries = gold_mod.load()
    wanted = ('unlabelled', 'draft', 'reviewed') if args.all else ('unlabelled', 'draft')
    queue = [e for e in entries if e['status'] in wanted
             and (not args.merger or e['merger_id'] in args.merger)
             and (not args.source or e['source'] == args.source)]
    if not queue:
        print('Nothing to review.')
        return 0
    print(f'{len(queue)} to review. Blind mode hides the draft labels.' if args.blind
          else f'{len(queue)} to review.')
    print(REVIEW_HELP)
    done = 0
    for n, e in enumerate(queue, 1):
        _show(e, args.blind, f'{n}/{len(queue)}')
        while True:
            try:
                answer = input('> ').strip().lower()
            except EOFError:
                answer = 'q'
            if answer == '?':
                print(guidelines_text())
                continue
            if answer == 'a':
                e['ambiguous'] = not e.get('ambiguous')
                print(f"  ambiguous: {e['ambiguous']}")
                continue
            if answer == 'n':
                e['notes'] = input('  note: ').strip() or None
                continue
            if answer in ('q', 's'):
                break
            if answer == '':
                if args.blind or e.get('labels') is None:
                    print('  Type the label numbers, or 0 for none.')
                    continue
            elif answer == '0':
                e['labels'] = []
            elif all(ch.isdigit() or ch in ' ,' for ch in answer):
                picks = sorted({int(ch) for ch in answer if ch.isdigit()})
                if any(p < 1 or p > len(CATEGORIES) for p in picks):
                    print(f'  1-{len(CATEGORIES)} only.')
                    continue
                e['labels'] = [CATEGORIES[p - 1] for p in picks]
            else:
                print(REVIEW_HELP)
                continue
            e['status'] = 'reviewed'
            done += 1
            gold_mod.save(entries)
            break
        if answer == 'q':
            break
    gold_mod.save(entries)
    print(f'\n{done} reviewed and saved.')
    return 0


# ── sync / stats ────────────────────────────────────────────────────────────

def cmd_sync(args) -> int:
    from .passages import is_gold_candidate, load_all

    entries = gold_mod.load()
    have = {e['id'] for e in entries}
    current = load_all()
    current_ids = {p.id for p in current}
    added = 0
    for p in current:
        if p.id not in have and is_gold_candidate(p):
            entries.append({**p.to_dict(), 'labels': None, 'status': 'unlabelled',
                            'ambiguous': False, 'notes': None})
            added += 1
    stale = [e['id'] for e in entries if e['id'] not in current_ids]
    if added and not args.dry_run:
        gold_mod.save(entries)
    print(f'{added} new passage(s) {"would be " if args.dry_run else ""}added as unlabelled.')
    if stale:
        print(f'{len(stale)} gold passage(s) no longer appear in the data (the document was '
              're-parsed or withdrawn). They still score fine, since the gold set keeps its own text:')
        for pid in stale[:20]:
            print(f'  {pid}')
    return 0


def cmd_stats(args) -> int:
    entries = gold_mod.load()
    problems = gold_mod.validate(entries)
    by = lambda key: {v: sum(1 for e in entries if e.get(key) == v)
                      for v in sorted({e.get(key) for e in entries}, key=str)}
    print(f'{len(entries)} passages')
    print('  status:   ', by('status'))
    print('  source:   ', by('source'))
    print('  ambiguous:', sum(1 for e in entries if e.get('ambiguous')))
    labelled = [e for e in entries if e['labels'] is not None]
    print(f"  no category: {sum(1 for e in labelled if not e['labels'])}")
    for c in CATEGORIES:
        print(f"  {c}: {sum(1 for e in labelled if c in e['labels'])}")
    if problems:
        print('\nProblems:\n  ' + '\n  '.join(problems))
        return 1
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog='python -m scripts.eval.theory_of_harm',
                                     description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)

    run = sub.add_parser('run', help='score models against the gold set')
    run.add_argument('--model', '-m', action='append', default=None,
                     help='provider spec, repeatable (default: keyword). See providers.py')
    run.add_argument('--reviewed-only', action='store_true', help='skip draft labels')
    run.add_argument('--exclude-ambiguous', action='store_true')
    run.add_argument('--source', choices=['phase2_notice', 'nocc'])
    run.add_argument('--merger', action='append', help='only this merger id, repeatable')
    run.add_argument('--limit', type=int, help='first N passages only (a cheap smoke test)')
    run.add_argument('--threshold', type=float, default=0.5)
    run.add_argument('--workers', type=int, default=4, help='concurrent requests')
    run.add_argument('--no-cache', action='store_true', help='ask again even if cached')
    run.add_argument('--show-errors', type=int, default=15, help='disagreements listed per model')
    run.set_defaults(func=cmd_run)

    review = sub.add_parser('review', help='confirm or correct gold labels')
    review.add_argument('--all', action='store_true', help='include already-reviewed passages')
    review.add_argument('--blind', action='store_true', help='hide draft labels while labelling')
    review.add_argument('--merger', action='append')
    review.add_argument('--source', choices=['phase2_notice', 'nocc'])
    review.set_defaults(func=cmd_review)

    sync = sub.add_parser('sync', help='add new passages from the data as unlabelled')
    sync.add_argument('--dry-run', action='store_true')
    sync.set_defaults(func=cmd_sync)

    stats = sub.add_parser('stats', help='summarise the gold set')
    stats.set_defaults(func=cmd_stats)

    args = parser.parse_args(argv)
    if getattr(args, 'model', 1) is None:
        args.model = ['keyword']
    return args.func(args)
