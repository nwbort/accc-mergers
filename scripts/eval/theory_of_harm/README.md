# Theory-of-harm eval

A hand-run harness that scores classifiers for `theories_of_harm.json` against a
labelled gold set. The production classifier is the keyword matcher in
`scripts/generate/static_data/outputs/theories_of_harm.py`. This lets any model
(a cheap LLM, a decision model, a local model) be compared with it on the same
passages, before anything replaces it. Nothing here runs in CI or the pipeline,
apart from its tests.

```bash
# Baseline: the production keyword classifier. Free, offline.
python -m scripts.eval.theory_of_harm run

# Compare models, each with --model (-m). The keyword baseline is only included if named.
python -m scripts.eval.theory_of_harm run -m keyword -m anthropic:claude-haiku-5-5 -m openrouter:qwen/qwen3-30b-a3b

# A cheap smoke test of a new provider first
python -m scripts.eval.theory_of_harm run -m groq:llama-3.3-70b-versatile --limit 10
```

The report prints to the terminal and is saved, with every prediction, under
`data/output/eval/theory_of_harm/runs/` (gitignored). Answers are cached under
`data/output/eval/theory_of_harm/cache/`, keyed by the model, its options, the
exact prompt and the passage. A re-run costs nothing, and changing a
definition in `taxonomy.py` re-asks every model automatically. Errored calls
aren't cached, so a re-run retries them.

## Choosing a provider

A model is `provider:model`, with options after commas
(`anthropic:claude-haiku-5-5,effort=medium`, `openai:o4-mini,temperature=none`).

| provider | how it connects | credentials |
|---|---|---|
| `keyword` | the production classifier | none |
| `anthropic` | the official `anthropic` SDK, answer constrained to a JSON schema. Options: `effort` (default `low`), `max_tokens` | `pip install anthropic`; `ANTHROPIC_API_KEY` or an `ant auth login` profile |
| `openai`, `openrouter`, `groq`, `together`, `deepseek`, `mistral`, `gemini` | their OpenAI-compatible `/chat/completions` endpoint. Options: `temperature` (default 0, `none` to omit), `max_tokens`, `json_mode` | `OPENAI_API_KEY`, `OPENROUTER_API_KEY`, … (the provider's name, upper-cased, + `_API_KEY`; `GEMINI_API_KEY` for Gemini) |
| `ollama` | a local Ollama server on `localhost:11434` | none |
| `custom` | any other OpenAI-compatible server (vLLM, LM Studio, a gateway) | `EVAL_OPENAI_BASE_URL`, optionally `EVAL_OPENAI_API_KEY` |
| `command:<cmd>` | runs your program once over every passage, JSON Lines in and out | whatever it needs |

Adding a preset for another OpenAI-compatible host is one line in
`OPENAI_COMPATIBLE` in `providers.py`. A provider with its own API is a small
`Provider` subclass.

### Decision models and anything else: `command:`

Decision models (Jev-style, or an open one such as Strands Decider) take a
state, a question and options, and return a probability per option. They
don't write JSON answers, so they plug in through `command:`. Your program
reads one JSON object per line on stdin:

```json
{"id": "...", "merger_name": "...", "source": "nocc", "section": "...", "heading": "...",
 "text": "...", "categories": ["horizontal_unilateral_effects", ...],
 "definitions": {"horizontal_unilateral_effects": "...", ...}, "guidelines": "..."}
```

and writes one per line on stdout, in any order:

```json
{"id": "...", "scores": {"entry_barriers": 0.83, "horizontal_unilateral_effects": 0.12}}
```

Scores may be probabilities. A category left out scores 0, and `evidence` and
`error` are optional. A decision model is single-choice, so for this
multi-label task ask it one yes/no question per category ("Does this passage
raise <definition>?") and report P(yes) as that category's score. When the
scores aren't all 0 or 1, the report adds a threshold sweep, so you can pick
the cut-off. Set `EVAL_COMMAND_VERSION` when the model behind the command
changes, or its cached answers will be reused.

```bash
python -m scripts.eval.theory_of_harm run -m keyword -m "command:python my_decider.py"
```

## Reading the report

- **micro P / R / F1** pool every passage-and-category decision. Micro F1 is
  the headline number.
- **macro F1** averages the per-category F1s, so missing the rare categories
  counts.
- **exact** is the share of passages whose whole label set is right.
- **empty ok** is the share of no-category passages (headings, background,
  procedure) where the model also said nothing. It measures over-labelling.
- **evidence verified**: LLMs must quote the passage for each label. This is
  the share of quotes that really appear in it, checked in code. The model is
  scored a second time as "+ evidence gate", with unverified labels dropped,
  which is how a production version would run.
- Each table is shown twice: once over all passages, once without the ones
  marked ambiguous. A model that gains a lot when ambiguous passages are
  excluded is mostly disagreeing on judgment calls.

**Treat the numbers with care:**

- The gold set covers only **9 matters**. IAG–RACI alone supplies about a
  third of it, and passages from the same document are correlated.
- Four categories are rare: coordinated effects 5, vertical 7, conglomerate 3,
  potential competition 2. Their per-category F1 is closer to an anecdote than
  a measurement.
- Lean on micro F1 and the disagreement list, not on small differences.

## The gold set

`gold.jsonl`, one passage per line, sorted by id. Each line holds the passage
text and context, plus `labels`, `status`, `ambiguous` and `notes` (see
`gold.py`). It carries its own text, so the eval doesn't depend on the
pipeline's data files. An id is the merger, the source and a hash of the
heading and text, so a passage keeps its id across re-scrapes as long as its
wording doesn't change.

**What's in it (341 passages):**

- all 89 Phase 2 notice items;
- all 212 NOCC passages in the assessment sections ("Summary of preliminary
  competition concerns/assessment", "The future with and without", "Areas no
  longer under active investigation");
- the 10 other NOCC passages the keyword classifier fires on, which is where
  its false positives are;
- 30 sampled background and market-definition passages, as negatives.

That's every passage that matters for precision and recall, and a fraction of
the 432 background passages that are almost all "none".

**The labels are drafts.** They were proposed by a model (Claude, while
building this harness), applying the definitions in `taxonomy.py`, and nobody
has checked them yet. Until they are reviewed:

- the eval partly measures agreement with that model;
- LLM-family models are likely flattered, since they share its
  interpretations.

Each report says how many draft labels it used.

### Reviewing

```bash
python -m scripts.eval.theory_of_harm review            # drafts and unlabelled, one at a time
python -m scripts.eval.theory_of_harm review --blind    # hide the draft labels while you choose
python -m scripts.eval.theory_of_harm review --merger MN-65005
python -m scripts.eval.theory_of_harm run --reviewed-only
```

Each answer is saved immediately, so you can quit (`q`) and resume. `?` shows
the guidelines. `--blind` avoids anchoring on the draft, and is worth it for at
least a sample, to see how often you would have disagreed.

The guidelines live in `taxonomy.py`, and they are also what every model is
told. Change a definition there and both the reviewers and the prompt follow.
Two calls in them are worth knowing:

- **Counterfactual reasoning about the target is horizontal.** "Would RACI
  remain a strong competitor without the acquisition" is the strength of the
  competitor being removed. Potential competition is kept for competition that
  doesn't exist yet.
- **`buyer_power` covers two different things**, as the production taxonomy
  does: customers' countervailing power (a constraint on the merged firm) and
  the merged firm's own buying power (a harm). Splitting it would make both
  measurable. The split would start in production's `CATEGORY_LABELS`, and the
  gold set's test fails until it's defined here.

### Keeping it current

```bash
python -m scripts.eval.theory_of_harm sync     # add new Phase 2 items / NOCC passages as unlabelled
python -m scripts.eval.theory_of_harm stats
```

`sync` adds every new passage matching the selection rule above
(`passages.is_gold_candidate`), so new matters flow into the review queue. It
reports gold passages that no longer appear in the data, but keeps them, since
they still score fine.
