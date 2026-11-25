"""Model providers for the theory-of-harm eval, chosen with a spec string.

A spec is ``provider`` or ``provider:model``:

    keyword                                  the production keyword classifier (baseline)
    anthropic:claude-haiku-5-5               Claude via the anthropic SDK (ANTHROPIC_API_KEY)
    openai:gpt-5-mini                        any preset in OPENAI_COMPATIBLE below
    openrouter:qwen/qwen3-30b-a3b
    ollama:llama3.2                          a local model, no key
    custom:my-model                          EVAL_OPENAI_BASE_URL + EVAL_OPENAI_API_KEY
    command:python my_decision_model.py      anything else, over stdin/stdout (see CommandProvider)

Options go after the spec, comma-separated: ``anthropic:claude-haiku-5-5,effort=medium``,
``openai:o4-mini,temperature=none`` (drops the temperature a reasoning model
rejects), ``max_tokens=2000``. Each provider class documents its own.

Every provider returns a score per category in [0, 1]. Prompted LLMs return
1.0 for each category they name. A decision model, or anything else that
outputs probabilities, returns those, and the eval sweeps the threshold for it.
LLMs also return a verbatim quote per category as evidence. ``verify_evidence``
checks the quote really is in the passage, and the eval scores the model with
and without dropping the categories whose quote fails that check.

To add a provider, subclass ``Provider``, implement ``predict`` (or
``predict_batch``), and add a branch in ``make_provider``.
"""

import hashlib
import json
import os
import re
import shlex
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Optional

from scripts.generate.static_data.outputs.theories_of_harm import _classify

from .taxonomy import CATEGORIES, guidelines_text

# name -> (base URL, API key env var or None, send response_format=json_object)
OPENAI_COMPATIBLE: dict[str, tuple[Optional[str], Optional[str], bool]] = {
    'openai': ('https://api.openai.com/v1', 'OPENAI_API_KEY', True),
    'openrouter': ('https://openrouter.ai/api/v1', 'OPENROUTER_API_KEY', False),
    'groq': ('https://api.groq.com/openai/v1', 'GROQ_API_KEY', True),
    'together': ('https://api.together.xyz/v1', 'TOGETHER_API_KEY', True),
    'deepseek': ('https://api.deepseek.com/v1', 'DEEPSEEK_API_KEY', True),
    'mistral': ('https://api.mistral.ai/v1', 'MISTRAL_API_KEY', True),
    'gemini': ('https://generativelanguage.googleapis.com/v1beta/openai', 'GEMINI_API_KEY', True),
    'ollama': ('http://localhost:11434/v1', None, True),
    'custom': (None, 'EVAL_OPENAI_API_KEY', False),  # base URL from EVAL_OPENAI_BASE_URL
}

SYSTEM_PROMPT = f"""You classify passages from Australian Competition and Consumer Commission (ACCC) \
merger documents: items from Phase 2 notices ("matters to investigate") and paragraphs from \
Notices of Competition Concerns. For each passage, say which theory-of-harm categories it \
raises, investigates or assesses.

{guidelines_text()}

Answer with JSON only, in this shape:
{{"categories": [{{"category": "<category key>", "evidence": "<the shortest verbatim quote from the passage that shows it>"}}]}}
Use the category keys exactly as listed. Copy the evidence character for character from the \
passage, never from the heading. If no category applies, answer {{"categories": []}}."""


def user_prompt(passage: dict) -> str:
    lines = [f"Merger: {passage.get('merger_name') or passage['merger_id']}"]
    lines.append('Document: ' + ('Phase 2 notice' if passage['source'] == 'phase2_notice'
                                 else 'Notice of Competition Concerns summary'))
    if passage.get('section'):
        lines.append(f"Section: {passage['section']}")
    if passage.get('heading'):
        lines.append(f"Heading: {passage['heading']}")
    lines.append('')
    lines.append('Passage:')
    lines.append(passage['text'])
    return '\n'.join(lines)


@dataclass
class Prediction:
    scores: dict = field(default_factory=dict)      # category -> score in [0, 1]
    evidence: dict = field(default_factory=dict)    # category -> quoted text
    invalid: list = field(default_factory=list)     # category keys outside the taxonomy
    usage: dict = field(default_factory=dict)       # input_tokens / output_tokens
    seconds: float = 0.0
    error: Optional[str] = None
    raw: Optional[str] = None

    def to_dict(self) -> dict:
        return dict(self.__dict__)

    @classmethod
    def from_dict(cls, d: dict) -> 'Prediction':
        return cls(**d)


_QUOTES = str.maketrans({'‘': "'", '’': "'", '“': '"', '”': '"', '–': '-', '—': '-', '‑': '-'})


def _normalise(s: str) -> str:
    return re.sub(r'\s+', ' ', s.translate(_QUOTES)).strip().lower()


def verify_evidence(quote: str, text: str) -> bool:
    """Whether ``quote`` appears in ``text``, ignoring whitespace, case and quote style."""
    q = _normalise(quote or '').strip(' .…"\'')
    return bool(q) and q in _normalise(text)


def parse_response(text: str, passage_text: str) -> Prediction:
    """Read a model's JSON answer leniently: fenced or prose-wrapped JSON is fine."""
    pred = Prediction(raw=text)
    match = re.search(r'\{.*\}', text or '', re.S)
    if not match:
        pred.error = 'no JSON object in response'
        return pred
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        pred.error = f'invalid JSON: {exc}'
        return pred
    items = data.get('categories') if isinstance(data, dict) else None
    if not isinstance(items, list):
        pred.error = 'no "categories" list'
        return pred
    for item in items:
        key = item.get('category') if isinstance(item, dict) else item
        if key not in CATEGORIES:
            pred.invalid.append(str(key))
            continue
        pred.scores[key] = 1.0
        if isinstance(item, dict) and item.get('evidence'):
            pred.evidence[key] = item['evidence']
    return pred


class Provider:
    """Base class. ``name`` labels the provider in reports; ``identity`` keys the cache."""

    name: str = 'provider'
    cacheable: bool = True

    def identity(self) -> str:
        return self.name

    def predict(self, passage: dict) -> Prediction:
        raise NotImplementedError

    def predict_batch(self, passages: list[dict], workers: int) -> list[Prediction]:
        def one(p):
            start = time.monotonic()
            try:
                pred = self.predict(p)
            except Exception as exc:  # one bad call shouldn't sink the run
                pred = Prediction(error=f'{type(exc).__name__}: {exc}')
            pred.seconds = time.monotonic() - start
            return pred
        with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
            return list(pool.map(one, passages))


class KeywordProvider(Provider):
    """The production classifier: substring matches over the passage text alone."""

    name = 'keyword'
    cacheable = False

    def predict(self, passage: dict) -> Prediction:
        pred = Prediction()
        for category, phrase in _classify(passage['text']):
            pred.scores[category] = 1.0
            pred.evidence[category] = phrase
        return pred


class _ChatProvider(Provider):
    """Shared by the chat providers: the cache identity carries the prompt."""

    def __init__(self, model: str, options: dict):
        self.model = model
        self.options = options

    def identity(self) -> str:
        prompt_hash = hashlib.sha256(SYSTEM_PROMPT.encode()).hexdigest()[:12]
        opts = ','.join(f'{k}={v}' for k, v in sorted(self.options.items()))
        return f'{self.name}|{opts}|prompt={prompt_hash}'


class OpenAICompatibleProvider(_ChatProvider):
    """Every OpenAI-style /chat/completions endpoint, over plain HTTP.

    Options: ``temperature`` (default 0; ``none`` to omit it, which reasoning
    models require), ``max_tokens`` (default 1024), ``json_mode`` (send
    ``response_format: json_object``; the preset decides the default).
    """

    def __init__(self, preset: str, model: str, options: dict):
        super().__init__(model, options)
        base, key_env, json_mode = OPENAI_COMPATIBLE[preset]
        if preset == 'custom':
            base = os.environ.get('EVAL_OPENAI_BASE_URL')
            if not base:
                raise SystemExit('custom: set EVAL_OPENAI_BASE_URL (e.g. http://localhost:8000/v1)')
        self.base = base.rstrip('/')
        self.key = os.environ.get(key_env) if key_env else None
        if key_env and not self.key and preset != 'custom':
            raise SystemExit(f'{preset}: set {key_env}')
        self.json_mode = options.get('json_mode', str(json_mode)).lower() in ('1', 'true', 'yes')
        temperature = options.get('temperature', '0')
        self.temperature = None if temperature.lower() == 'none' else float(temperature)
        self.max_tokens = int(options.get('max_tokens', 1024))
        self.name = f'{preset}:{model}'

    def _post(self, url: str, headers: dict, body: dict) -> dict:
        import requests  # imported here so the test suite's requests stub is never hit

        for attempt in range(5):
            resp = requests.post(url, headers=headers, json=body, timeout=120)
            if resp.status_code in (429, 500, 502, 503, 504) and attempt < 4:
                time.sleep(2 ** attempt * 2)
                continue
            if resp.status_code >= 400:
                raise RuntimeError(f'HTTP {resp.status_code}: {resp.text[:300]}')
            return resp.json()
        raise RuntimeError('unreachable')

    def predict(self, passage: dict) -> Prediction:
        body = {
            'model': self.model,
            'messages': [
                {'role': 'system', 'content': SYSTEM_PROMPT},
                {'role': 'user', 'content': user_prompt(passage)},
            ],
            'max_tokens': self.max_tokens,
        }
        if self.temperature is not None:
            body['temperature'] = self.temperature
        if self.json_mode:
            body['response_format'] = {'type': 'json_object'}
        headers = {'Authorization': f'Bearer {self.key}'} if self.key else {}
        data = self._post(f'{self.base}/chat/completions', headers, body)
        text = data['choices'][0]['message'].get('content') or ''
        pred = parse_response(text, passage['text'])
        usage = data.get('usage') or {}
        pred.usage = {'input_tokens': usage.get('prompt_tokens', 0),
                      'output_tokens': usage.get('completion_tokens', 0)}
        return pred


# The answer shape, enforced by the API for providers that take a JSON schema.
RESPONSE_SCHEMA = {
    'type': 'object',
    'properties': {
        'categories': {
            'type': 'array',
            'items': {
                'type': 'object',
                'properties': {
                    'category': {'type': 'string', 'enum': CATEGORIES},
                    'evidence': {'type': 'string'},
                },
                'required': ['category', 'evidence'],
                'additionalProperties': False,
            },
        },
    },
    'required': ['categories'],
    'additionalProperties': False,
}


class AnthropicProvider(_ChatProvider):
    """Claude, through the official SDK (``pip install anthropic``; not a pipeline dependency).

    Credentials come from wherever the SDK finds them (``ANTHROPIC_API_KEY``,
    or an ``ant auth login`` profile). The answer is constrained to
    ``RESPONSE_SCHEMA``, so the category keys can't be misspelt. Options:
    ``effort`` (default ``low``, plenty for classification) and ``max_tokens``
    (default 4096, which has to leave room for the model's thinking).
    """

    def __init__(self, model: str, options: dict):
        super().__init__(model, options)
        try:
            import anthropic
        except ImportError:
            raise SystemExit('anthropic: pip install anthropic')
        self.client = anthropic.Anthropic(max_retries=5)
        self.effort = options.get('effort', 'low')
        self.max_tokens = int(options.get('max_tokens', 4096))
        self.name = f'anthropic:{model}'

    def predict(self, passage: dict) -> Prediction:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            # Identical on every call, so cache it (a no-op if it is under the
            # model's minimum cacheable length).
            system=[{'type': 'text', 'text': SYSTEM_PROMPT,
                     'cache_control': {'type': 'ephemeral'}}],
            messages=[{'role': 'user', 'content': user_prompt(passage)}],
            output_config={
                'effort': self.effort,
                'format': {'type': 'json_schema', 'schema': RESPONSE_SCHEMA},
            },
        )
        text = ''.join(b.text for b in response.content if b.type == 'text')
        if response.stop_reason in ('refusal', 'max_tokens'):
            pred = Prediction(raw=text, error=f'stop_reason={response.stop_reason}')
        else:
            pred = parse_response(text, passage['text'])
        u = response.usage
        pred.usage = {
            'input_tokens': (u.input_tokens or 0) + (getattr(u, 'cache_read_input_tokens', 0) or 0)
            + (getattr(u, 'cache_creation_input_tokens', 0) or 0),
            'output_tokens': u.output_tokens or 0,
        }
        return pred


class CommandProvider(Provider):
    """Run an external command once over every passage: the escape hatch.

    For decision models (Jev-style or an open one such as Strands Decider), a
    local Hugging Face model, or a provider with no preset here. The command
    reads JSON Lines on stdin, one object per passage:

        {"id", "merger_name", "source", "section", "heading", "text",
         "categories": [...], "definitions": {category: definition}, "guidelines": "..."}

    and writes JSON Lines on stdout, one per passage, in any order:

        {"id": "...", "scores": {"<category>": 0.83, ...}, "evidence": {...}}

    ``scores`` may be probabilities. A category left out scores 0. ``evidence``
    is optional. Add ``"error": "..."`` to report a failure for one passage.
    """

    def __init__(self, command: str):
        self.command = command
        # Reports show the program names only; the cache keys on the whole line.
        self.name = 'command:' + ' '.join(os.path.basename(t) for t in shlex.split(command))

    def identity(self) -> str:
        # Bump EVAL_COMMAND_VERSION when the model behind the command changes,
        # or its cached answers will be reused.
        return f'command:{self.command}|{os.environ.get("EVAL_COMMAND_VERSION", "")}'

    def predict_batch(self, passages: list[dict], workers: int) -> list[Prediction]:
        from .taxonomy import DEFINITIONS

        payload = ''.join(json.dumps({
            'id': p['id'], 'merger_name': p.get('merger_name'), 'source': p['source'],
            'section': p.get('section'), 'heading': p.get('heading'), 'text': p['text'],
            'categories': CATEGORIES, 'definitions': DEFINITIONS, 'guidelines': guidelines_text(),
        }, ensure_ascii=False) + '\n' for p in passages)
        start = time.monotonic()
        proc = subprocess.run(shlex.split(self.command), input=payload, capture_output=True,
                              text=True, check=False)
        elapsed = (time.monotonic() - start) / max(1, len(passages))
        if proc.returncode != 0:
            raise SystemExit(f'{self.command} exited {proc.returncode}:\n{proc.stderr[-2000:]}')
        by_id = {}
        for line in proc.stdout.splitlines():
            if line.strip():
                row = json.loads(line)
                by_id[row['id']] = row
        out = []
        for p in passages:
            row = by_id.get(p['id'])
            if row is None:
                out.append(Prediction(error='no output for this id', seconds=elapsed))
                continue
            scores = {k: float(v) for k, v in (row.get('scores') or {}).items() if k in CATEGORIES}
            invalid = [k for k in (row.get('scores') or {}) if k not in CATEGORIES]
            out.append(Prediction(scores=scores, evidence=row.get('evidence') or {},
                                  invalid=invalid, error=row.get('error'), seconds=elapsed))
        return out


def make_provider(spec: str) -> Provider:
    if spec == 'keyword':
        return KeywordProvider()
    if spec.startswith('command:'):
        return CommandProvider(spec.split(':', 1)[1].strip())
    head, *opts = spec.split(',')
    options = dict(o.split('=', 1) for o in opts if '=' in o)
    provider, _, model = head.partition(':')
    if not model:
        raise SystemExit(f'{spec}: name a model, e.g. {provider}:<model>')
    if provider == 'anthropic':
        return AnthropicProvider(model, options)
    if provider in OPENAI_COMPATIBLE:
        return OpenAICompatibleProvider(provider, model, options)
    known = ', '.join(['keyword', 'anthropic', 'command', *OPENAI_COMPATIBLE])
    raise SystemExit(f'unknown provider {provider!r}; one of: {known}')
