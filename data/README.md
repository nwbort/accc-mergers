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

- `mergers.json` — master merger data extracted from `raw/`
- `questionnaire_data.json` — parsed questionnaire metadata
- `commentary.json` — hand-authored commentary keyed by `merger_id`
  (edited via `scripts/tools/commentary.py`)
- `related_mergers.json` — manual `WA-*` → `MN-*` pairs for waivers that
  were re-filed as formal notifications
- `similar_mergers.json` — generated suggestions of related mergers per
  merger (from `generate_similar_mergers.py`)

### `output/`

Generated artefacts that are **not** deployed to the frontend. Used for
offline analysis and external consumers.

- `mergers.json` — full enriched merger data (the same shape served to
  the frontend, but as one file)
- `cli/` — bundle and manifests for the
  [`accc-mergers-cli`](https://github.com/nwbort/accc-mergers-cli) tool
  (`cli-bundle.json`, `cli-manifest.json`, `cli-merger-manifest.json`)

### `digest-archive/`

Past weekly digests (`digest-YYYY-MM-DD.json`), retained so the next run
of `generate_weekly_digest.py` can deduplicate against the prior week.

### Top-level files

- `embeddings.json` — sentence-level embedding metadata (one record per
  chunk: merger_id, section label, text)
- `embeddings.bin` — packed Float32 vectors for those chunks, in the
  same order as `embeddings.json`. Both are produced by
  `scripts/embed.py` and consumed by the frontend semantic-search UI.
- `frozen_events_mergers.json` — merger IDs whose event lists are frozen
  (manual edits, do not overwrite during extraction).

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
    ├──────────────► merger-tracker/frontend/public/data/   (deployed)
    └──────────────► data/output/                           (offline analysis)
```

1. **Scrape**: ACCC register and matter pages → `raw/`
2. **Extract**: HTML/PDF parsing → `processed/`
3. **Generate**: enrich + paginate → `frontend/public/data/` and
   `output/`
