# ACCC Merger Query CLI — Specification

## Purpose

A local command-line tool for querying the ACCC merger register — searching past determinations, finding similar cases by industry or issue, reading the ACCC's reasoning, and browsing questionnaire questions. Designed for personal use by a practitioner working on new merger matters, and documented so Claude Code can operate it autonomously via a `skill.md`.

---

## Data Source

The source of truth is the public GitHub repository **`nwbort/accc-mergers`**. All data needed for this CLI lives in the frontend static data directory and is available over HTTPS without authentication.

### Key URLs

| Resource | URL |
|---|---|
| All mergers (index) | `https://raw.githubusercontent.com/nwbort/accc-mergers/main/merger-tracker/frontend/public/data/mergers.json` |
| Individual merger | `https://raw.githubusercontent.com/nwbort/accc-mergers/main/merger-tracker/frontend/public/data/mergers/MN-01016.json` |
| Stats | `https://raw.githubusercontent.com/nwbort/accc-mergers/main/merger-tracker/frontend/public/data/stats.json` |
| Questionnaire index | `https://raw.githubusercontent.com/nwbort/accc-mergers/main/merger-tracker/frontend/public/data/questionnaire_data.json` |
| Industries | `https://raw.githubusercontent.com/nwbort/accc-mergers/main/merger-tracker/frontend/public/data/industries.json` |

### Data Schema

**Per merger (`MN-XXXXX.json`):**
- `merger_id`, `merger_name`, `status`, `stage`, `is_waiver`
- `acquirers[]`, `targets[]` — name + ABN/ACN
- `anzsic_codes[]` — industry codes and names
- `merger_description` — 1,500–2,000 char narrative of the deal
- `accc_determination` — `"Approved"`, `"Denied"`, or `null`
- `phase_1_determination`, `phase_2_determination`
- `effective_notification_datetime`, `determination_publication_date`
- `events[]` — timeline entries, each potentially containing:
  - `determination_table_content[]` — the full determination text, broken into sections:
    - `"Notified acquisition"` — transaction description
    - `"Determination"` — legal outcome statement
    - `"Parties to the Acquisition"` — party backgrounds
    - `"Overlap and relationship between the parties"` — competitive analysis
    - `"Reasons for determination"` — the ACCC's actual reasoning (most valuable)
    - `"Applications for review"` — appeal procedures
- `comments[]` — editorial commentary with tags (e.g. `["landmark"]`)

**Questionnaire data (`questionnaire_data.json`):**
- Keyed by merger ID
- Contains `deadline`, `questions[]` (numbered, with full text), `questions_count`

---

## Local Data Management

### Cache location
`~/.accc-mergers/` — created automatically on first run.

### Cache structure
```
~/.accc-mergers/
  db.sqlite          # FTS index + all merger data
  last_sync.txt      # ISO timestamp of last sync
```

### Sync behaviour
- On first run of any command, automatically sync if no cache exists.
- On subsequent runs, warn if cache is older than 7 days but do not auto-sync.
- `accc sync` forces a fresh download.
- Sync fetches the index (`mergers.json`) first, then fetches all individual merger files concurrently (cap at 4 concurrent requests to respect GitHub rate limits).
- Sync also fetches `questionnaire_data.json` and `stats.json`.

---

## Search Architecture

Use **SQLite FTS5** (available in Python's stdlib `sqlite3` module — no extra dependencies). Build two tables:

### `mergers` table
Stores structured fields: `merger_id`, `merger_name`, `status`, `stage`, `is_waiver`, `acquirers_text`, `targets_text`, `industries_text`, `determination`, `phase`, `notification_date`, `determination_date`.

### `merger_content` FTS5 virtual table
Full-text indexed columns:
- `merger_name`
- `acquirers_text` (joined party names)
- `targets_text` (joined party names)
- `industries_text` (ANZSIC names joined)
- `merger_description`
- `determination_reasons` (extracted from `determination_table_content` where `item` = `"Reasons for determination"`)
- `determination_overlap` (from `"Overlap and relationship between the parties"`)
- `all_determination_text` (all `determination_table_content` sections concatenated)

FTS5 ranks results by relevance using BM25 (built in). No embeddings required.

---

## Command Reference

### `accc sync`
Download and index the latest data from GitHub.

```
accc sync
accc sync --force      # re-download even if cache is fresh
```

Output: progress indicator while downloading merger files, then a summary line (e.g. "Indexed 186 mergers.").

---

### `accc search <query>`
Full-text search across merger descriptions and determination text.

```
accc search "warehouse lease beverage"
accc search "fuel retail geographic" --outcome approved
accc search "software vertical integration" --industry software --phase 1
accc search "pharmaceutical" --waiver
accc search "grocery" --year 2025
```

**Options:**

| Flag | Values | Description |
|---|---|---|
| `--outcome` | `approved`, `denied`, `phase2`, `pending` | Filter by determination |
| `--industry` | partial string | Filter by ANZSIC industry name (case-insensitive) |
| `--phase` | `1`, `2` | Filter by assessment phase |
| `--waiver` / `--no-waiver` | — | Filter to waivers or notifications only |
| `--year` | e.g. `2025` | Filter by notification year |
| `--limit N` | integer | Max results (default 10) |
| `--json` | — | Output raw JSON |

**Output per result (compact list):**
```
MN-01016  Asahi – Warehouse site (Deer Park)        Approved   Phase 1   Beverage Mfg   Sep 2025
MN-00987  ...
```

---

### `accc show <id>`
Display full detail on a single merger.

```
accc show MN-01016
accc show MN-01016 --section reasons
accc show MN-01016 --json
```

**Options:**

| Flag | Values | Description |
|---|---|---|
| `--section` | `all`, `reasons`, `overlap`, `parties`, `determination` | Show only one determination section |
| `--json` | — | Raw JSON output |

**Output sections (rendered with `rich` in terminal):**
1. **Header** — ID, name, status, outcome, dates
2. **Parties** — acquirers and targets with ABNs/ACNs
3. **Industries** — ANZSIC codes and names
4. **Description** — full merger description paragraph
5. **Determination** — each `determination_table_content` section with heading and body
6. **Questionnaire** — if available, numbered list of questions
7. **Commentary** — editorial comments and tags

---

### `accc list`
Browse mergers with filters, no search query required.

```
accc list
accc list --outcome approved --industry health --year 2025
accc list --phase 2
accc list --waiver --outcome pending
accc list --sort date-desc
```

**Options:** same filters as `search`, plus:

| Flag | Values | Description |
|---|---|---|
| `--sort` | `date-asc`, `date-desc` (default), `name`, `duration` | Sort order |

Output: tabular list (same format as search results).

---

### `accc questions [id]`
Browse questionnaire questions.

```
accc questions                              # list all mergers that have questionnaires
accc questions MN-01016                     # show questions for a specific merger
accc questions --search "geographic market" # search question text across all mergers
```

**Output for `accc questions MN-01016`:**
```
MN-01016 — Asahi – Warehouse site (Deer Park, Vic)
Deadline: 25 August 2025  |  3 questions

1. Outline any concerns regarding the impact of the proposed acquisition on competition...
2. Provide any additional information...
3. Provide a brief description of your business...
```

---

### `accc industries`
Show a breakdown of merger activity by industry.

```
accc industries
accc industries --show software     # list mergers in that industry
```

**Output:**
```
Industry                     Notifications  Waivers  Approved  Phase 2
Computer System Design              18         8        24        1
Software Publishing                 12         9        21        0
...
```

---

### `accc stats`
Print summary statistics from the cached `stats.json`.

```
accc stats
```

Shows totals, phase duration averages, top industries, and recent determinations.

---

## Output Design

- Use **`rich`** for terminal formatting — tables, panels, markdown rendering, colour.
- Default output is human-readable. `--json` on any command outputs structured JSON (useful for piping into Claude Code or `jq`).
- Colour-code outcomes: green = Approved, red = Denied / Phase 2 referral, yellow = Pending.
- Long text (determination reasons) word-wraps at terminal width.
- If stdout is not a TTY (piped), strip colour and use plain text automatically.

---

## Implementation Stack

| Component | Choice | Rationale |
|---|---|---|
| Language | Python 3.11+ | Matches existing repo scripts; stdlib has `sqlite3`, `http`, `json` |
| CLI framework | `typer` | Type-annotated commands, auto-generates `--help` |
| Terminal output | `rich` | Tables, panels, colour, markdown — excellent for this use case |
| HTTP | `httpx` | Async-capable, good for concurrent downloads |
| Database | SQLite FTS5 | Zero extra dependencies, built into Python, fast full-text search |

**Install:** `pip install typer rich httpx` — the complete dependency list.

**Entry point:** `accc` — registered in `pyproject.toml` under `[project.scripts]`.

---

## Project Layout (new repository)

```
accc-merger-cli/
  pyproject.toml           # package metadata, dependencies, entry point
  README.md                # installation + quick start
  skill.md                 # Claude Code skill documentation (see below)
  accc/
    __init__.py
    cli.py                 # typer app, all command definitions
    sync.py                # data fetching + SQLite indexing
    db.py                  # database helpers, FTS queries
    display.py             # rich output formatting
    models.py              # dataclasses for Merger, Event, Questionnaire
  tests/
    test_sync.py
    test_search.py
    test_display.py
```

---

## `skill.md` Design

The `skill.md` file (placed in `~/.claude/` or the project root) documents the CLI so Claude Code can use it without trial and error.

### Required sections

**What the tool does** — one paragraph on the data source and purpose.

**When to use it** — e.g. "Use this when the user asks about past ACCC merger decisions, similar industries, what the ACCC considered in past cases, or whether a particular type of deal has been reviewed before."

**Command reference** — the full command table with concrete examples for each realistic query type.

**Output format** — note that `--json` produces structured output and should be used when Claude needs to parse results programmatically.

**Typical query patterns** — worked examples:

| User question | Command |
|---|---|
| Has the ACCC reviewed mergers in grocery retail before? | `accc search "grocery retail" --json` |
| What did the ACCC say about geographic markets in the fuel sector? | `accc search "geographic fuel" --section reasons` |
| Show me all Phase 2 cases | `accc list --phase 2 --json` |
| What questions did the ACCC ask in the Ampol merger? | `accc questions MN-01019` |
| What industries see the most scrutiny? | `accc industries` |
| How long does a typical Phase 1 review take? | `accc stats` |

**Limitations** — searches are keyword-based using FTS5 ranking; there is no semantic/conceptual similarity without embeddings. Phase 2 determinations that are still in progress do not yet have full reasoning text available.

---

## Future Considerations

- **Semantic search**: If keyword search proves insufficient, the natural upgrade is Anthropic embeddings stored in `sqlite-vec`. The CLI interface stays identical — only `sync.py` and `db.py` change.
- **`accc compare <id1> <id2>`**: Output both determinations side by side for analysis.
- **`--context` flag on `show`**: Output a prompt-ready context block formatted for pasting into a Claude session.
