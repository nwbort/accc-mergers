# Data Directory

All data files for the ACCC Mergers Tracker, organised by processing stage.

## Structure

### `raw/`

Raw data scraped from the ACCC website by `scripts/scrape.sh`:

- `acquisitions-register.html` — main acquisitions register listing page.
  This is a transient working artifact: it is re-fetched fresh at the start
  of every scrape run and only used within that run to derive matter links,
  so it is **git-ignored** rather than committed (it changes on every fetch
  even when no merger data has).
- `matters/MN-*.html`, `matters/WA-*.html` — individual merger detail pages
  (one HTML file per matter)
- `matters/MN-*/`, `matters/WA-*/` — subdirectories containing supporting
  documents (determinations, questionnaires, submissions) as PDFs and DOCX
  files

### `processed/`

Intermediate JSON written by the extraction pipeline (mainly
`extract_mergers.py`):

- `mergers.json` — master merger data extracted from `raw/`. A matter that
  has moved on to the public benefit phase also carries
  `stage_determinations`, the determination each phase reached, since the
  register's single headline determination can no longer say which was Phase
  2's (see `scripts/stage_determinations.py`)
- `questionnaire_data.json` — parsed questionnaire metadata
- `commentary.json` — hand-authored commentary keyed by `merger_id`
  (edited via `scripts/tools/commentary.py`)
- `related_mergers.json` — manual `WA-*` → `MN-*` pairs for waivers that
  were re-filed as formal notifications
- `similar_mergers.json` — generated suggestions of related mergers per
  merger (from `generate_similar_mergers.py`)
- `atproto_records.json` — content digest of each `fyi.mergers.matter` record
  as last published to the ATmosphere, so a pipeline run rewrites only the
  matters that moved (see [`docs/atproto.md`](../docs/atproto.md)). An
  optimisation, not a source of truth: the publish is an upsert, so losing
  this file costs one full republish and no correctness. Only exists once
  ATmosphere publishing is configured.
- `atproto_posts.json` — merger milestones already posted to Bluesky, keyed
  `{merger_id}:{kind}:{date}`, so a re-run cannot repost them. The first
  enabled run writes every existing milestone here without posting, which is
  what stops switching posting on from replaying the whole register.

### `output/`

Generated artefacts that are **not** deployed to the frontend. Used for
offline analysis and external consumers.

- `mergers.json` — full enriched merger data (the same shape served to
  the frontend, but as one file)
- `cli/` — build inputs for the
  [`accc-mergers-cli`](https://github.com/nwbort/accc-mergers-cli) tool.
  Only `cli-manifest.json` is tracked; it holds the version counter and
  bundle checksum that `generate-cli-data.sh` uses to detect change between
  runs. `cli-bundle.json` and `cli-merger-manifest.json` are gitignored —
  regenerate them with `./scripts/generate-cli-data.sh`. The CLI itself
  downloads `cli.sqlite` from the orphan `cli-dist` branch, built from the
  bundle during the pipeline run; nothing consumes these files from `main`.

### `digest-archive/`

Past weekly digests (`digest-YYYY-MM-DD.json`), retained so the next run
of `generate_weekly_digest.py` can deduplicate against the prior week.

### Top-level files

- `frozen_events_mergers.json` — mergers whose events are protected from
  being overwritten during extraction (manual edits). Set `freeze_events: true`
  (or use an empty object) to freeze the whole event list, or
  `freeze_events: ["Event title", ...]` to freeze only specific events while
  still updating the rest from the scraped page.

## Pipeline flow

```
ACCC website
    │  scripts/scrape.sh
    ▼
data/raw/
    │  scripts/extract_mergers.py
    ▼
data/processed/
    │  scripts/generate_static_data.py
    ├──────────────► frontend/public/data/                  (deployed)
    └──────────────► data/output/                           (offline analysis)
```

1. **Scrape**: ACCC register and matter pages → `raw/`
2. **Extract**: HTML/PDF parsing → `processed/`
3. **Generate**: enrich + paginate → `frontend/public/data/` and
   `output/`
