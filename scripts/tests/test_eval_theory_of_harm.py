"""The theory-of-harm eval harness (scripts/eval/theory_of_harm/).

No network: the HTTP providers are exercised only through ``parse_response``,
and the command provider through a throwaway Python script.
"""

import json
import sys

import pytest

from scripts.eval.theory_of_harm import cli, gold, metrics
from scripts.eval.theory_of_harm.passages import Passage, passage_id
from scripts.eval.theory_of_harm.providers import (
    RESPONSE_SCHEMA,
    SYSTEM_PROMPT,
    CommandProvider,
    KeywordProvider,
    make_provider,
    parse_response,
    verify_evidence,
)
from scripts.eval.theory_of_harm.taxonomy import CATEGORIES, DEFINITIONS
from scripts.generate.static_data.outputs.theories_of_harm import CATEGORY_LABELS

H = 'horizontal_unilateral_effects'
E = 'entry_barriers'


# ── the committed gold set ─────────────────────────────────────────────────

def test_gold_set_is_valid():
    entries = gold.load()
    assert entries, 'gold.jsonl is empty'
    assert gold.validate(entries) == []


def test_gold_set_is_sorted_one_line_per_passage():
    """save() writes it this way; a hand edit that breaks it makes noisy diffs."""
    ids = [e['id'] for e in gold.load()]
    assert ids == sorted(ids)


def test_every_production_category_has_a_definition():
    # A category added to the production classifier must be defined here
    # before the gold set (and the prompt) can use it.
    assert set(DEFINITIONS) == set(CATEGORY_LABELS)
    assert CATEGORIES == list(CATEGORY_LABELS)
    for key in CATEGORIES:
        assert key in SYSTEM_PROMPT


def test_response_schema_enumerates_the_categories():
    item = RESPONSE_SCHEMA['properties']['categories']['items']
    assert item['properties']['category']['enum'] == CATEGORIES


# ── passages ────────────────────────────────────────────────────────────────

def test_passage_id_depends_on_heading_and_text_only():
    a = passage_id('MN-1', 'nocc', 'Heading', 'Some text.')
    assert a == passage_id('MN-1', 'nocc', 'Heading', 'Some text.')
    assert a != passage_id('MN-1', 'nocc', 'Other heading', 'Some text.')
    assert a.startswith('MN-1/nocc/')


def test_validate_catches_bad_entries():
    base = Passage('x', 'MN-1', None, 'nocc', None, None, None, None, 'text').to_dict()
    entries = [
        {**base, 'id': 'a', 'labels': ['not_a_category'], 'status': 'draft'},
        {**base, 'id': 'b', 'labels': [H, H], 'status': 'reviewed'},
        {**base, 'id': 'c', 'labels': [], 'status': 'unlabelled'},
        {**base, 'id': 'd', 'labels': None, 'status': 'draft'},
        {**base, 'id': 'a', 'labels': [], 'status': 'done'},
    ]
    problems = '\n'.join(gold.validate(entries))
    assert 'unknown category' in problems
    assert 'repeated label' in problems
    assert 'unlabelled but has labels' in problems
    assert 'labels must be a list' in problems
    assert 'duplicate id' in problems
    assert 'unknown status' in problems


# ── metrics ─────────────────────────────────────────────────────────────────

def _g(pid, labels, ambiguous=False):
    return {'id': pid, 'labels': labels, 'ambiguous': ambiguous, 'text': pid}


def test_score_counts_per_category_and_pools():
    gold_set = [_g('1', [H]), _g('2', [H, E]), _g('3', []), _g('4', [])]
    predicted = {'1': {H}, '2': {H}, '3': {E}, '4': set()}
    m = metrics.score(gold_set, predicted)
    assert (m['per_category'][H]['tp'], m['per_category'][H]['fp'], m['per_category'][H]['fn']) == (2, 0, 0)
    assert (m['per_category'][E]['tp'], m['per_category'][E]['fp'], m['per_category'][E]['fn']) == (0, 1, 1)
    assert m['micro']['precision'] == pytest.approx(2 / 3)
    assert m['micro']['recall'] == pytest.approx(2 / 3)
    assert m['exact_match'] == 0.5          # passages 1 and 4
    assert m['empty_precision'] == 0.5      # 4 held back, 3 didn't
    # Macro averages only categories that appear: H (1.0) and E (0.0).
    assert m['macro_f1'] == pytest.approx(0.5)


def test_missing_prediction_counts_as_empty():
    m = metrics.score([_g('1', [H])], {})
    assert m['micro']['recall'] == 0.0


def test_threshold_sweep_and_probability_detection():
    gold_set = [_g('1', [H]), _g('2', [])]
    scores = {'1': {H: 0.6}, '2': {H: 0.3}}
    assert metrics.is_probabilistic(scores)
    assert not metrics.is_probabilistic({'1': {H: 1.0}})
    by_t = {row['threshold']: row for row in metrics.threshold_sweep(gold_set, scores)}
    assert by_t[0.5]['precision'] == 1.0 and by_t[0.5]['recall'] == 1.0
    assert by_t[0.2]['precision'] == 0.5


# ── parsing and evidence ────────────────────────────────────────────────────

def test_parse_response_accepts_fenced_json_and_drops_unknown_keys():
    text = ('Here you go:\n```json\n{"categories": ['
            '{"category": "entry_barriers", "evidence": "barriers to entry"},'
            '{"category": "market_definition", "evidence": "x"}]}\n```')
    pred = parse_response(text, 'There are barriers to entry.')
    assert pred.scores == {E: 1.0}
    assert pred.evidence == {E: 'barriers to entry'}
    assert pred.invalid == ['market_definition']
    assert pred.error is None


@pytest.mark.parametrize('text', ['no json here', '{"categories": "nope"}', '{"categories": [}'])
def test_parse_response_reports_malformed_answers(text):
    assert parse_response(text, 'x').error


def test_verify_evidence_ignores_case_whitespace_and_quote_style():
    passage = 'The ACCC’s preliminary view is that   barriers to entry are high.'
    assert verify_evidence("the ACCC's preliminary view", passage)
    assert verify_evidence('"barriers to entry are high."', passage)
    assert not verify_evidence('barriers to expansion', passage)
    assert not verify_evidence('', passage)


# ── providers ───────────────────────────────────────────────────────────────

def test_keyword_provider_is_the_production_classifier():
    pred = KeywordProvider().predict({'text': 'The likelihood of timely new entry.'})
    assert pred.scores == {E: 1.0}


def test_make_provider_rejects_unknown_and_modelless_specs():
    with pytest.raises(SystemExit):
        make_provider('nonsense:model')
    with pytest.raises(SystemExit):
        make_provider('openai')


def test_command_provider_round_trip(tmp_path):
    script = tmp_path / 'decide.py'
    script.write_text(
        'import json, sys\n'
        'for line in sys.stdin:\n'
        '    p = json.loads(line)\n'
        '    if "skip" in p["text"]:\n'
        '        continue\n'
        '    print(json.dumps({"id": p["id"], "scores": {"entry_barriers": 0.8, "bogus": 1}}))\n'
    )
    provider = CommandProvider(f'{sys.executable} {script}')
    assert provider.name == f'command:{sys.executable.rsplit("/", 1)[-1]} decide.py'
    preds = provider.predict_batch([{'id': 'a', 'source': 'nocc', 'text': 'entry'},
                                    {'id': 'b', 'source': 'nocc', 'text': 'skip me'}], workers=1)
    assert preds[0].scores == {E: 0.8} and preds[0].invalid == ['bogus']
    assert preds[1].error == 'no output for this id'


# ── the run command, end to end ─────────────────────────────────────────────

def test_run_writes_a_report(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli, 'RUNS_DIR', tmp_path / 'runs')
    monkeypatch.setattr(cli, 'CACHE_DIR', tmp_path / 'cache')
    assert cli.main(['run', '--limit', '20', '--show-errors', '2']) == 0
    report = capsys.readouterr().out
    assert '| keyword |' in report
    written = json.loads(next((tmp_path / 'runs').glob('*.json')).read_text())
    assert len(written['gold_ids']) == 20
    assert written['results'][0]['name'] == 'keyword'
