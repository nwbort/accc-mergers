# Data Directory

All data files for the ACCC Mergers Tracker, organised by processing stage.

This project's own data is licensed under CC BY 4.0 (see
[`LICENSE-DATA`](../LICENSE-DATA)). The third-party documents mirrored in
`raw/` are not: they remain subject to their owners' terms (see
[`raw/NOTICE.md`](raw/NOTICE.md)).

## Structure

### `raw/`

Raw data scraped from the ACCC website by `scripts/scrape/scrape.sh`:

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
- `NOTICE.md` — states that everything here is third-party material, outside
  this repository's licences

### `processed/`

Intermediate JSON written by the extraction pipeline (mainly
`extract_mergers.py`):

- `mergers.json` — master merger data extracted from `raw/`. A matter that
  has moved on to the public benefit phase also carries
  `stage_determinations`, the determination each phase reached, since the
  register's single headline determination can no longer say which was Phase
  2's (see `scripts/stage_determinations.py`)
- `questionnaire_data.json` — parsed questionnaire metadata
- `nocc_data.json` — parsed Notice of Competition Concerns summaries, keyed
  by `merger_id` (source of the generated `noccs/{id}.json`)
- `phase1_estimates.json` — frozen filing-time Phase 1 duration estimates,
  keyed by `merger_id` (written by
  `scripts/generate/static_data/phase1_estimate.py`)
- `commentary.json` — hand-authored commentary keyed by `merger_id`
  (edited via `scripts/tools/commentary.py`)
- `related_mergers.json` — manual `WA-*` → `MN-*` pairs for waivers that
  were re-filed as formal notifications, plus a `rejected` list of
  suggested pairs reviewed and found not to be refiles (the detector never
  suggests those again)
- `related_parties.json` — canonical party groups (same real-world entity),
  plus, once a suggestion has been turned down, a `rejected` list the detector
  never re-suggests (edited via `scripts/tools/related_parties.py`;
  suggestions from `scripts/detect/detect_related_parties.py`)
- `tribunal_appeals.json` — Australian Competition Tribunal appeals keyed by
  `merger_id`, one record per tribunal matter; hand-maintained apart from each
  record's `documents[]`, which `scripts/scrape/scrape_tribunal.py` fills in
- `judicial_reviews.json` — Federal Court judicial reviews keyed by
  `merger_id`, entirely hand-maintained
- `quarterly_commentary.json` — hand-written points for the quarterly report,
  keyed by quarter as the page URL names it (`26Q3`)
- `advisors.json.enc` — encrypted advisor data, backend-only and created by
  the first save in `scripts/tools/advisors.py` (see
  [`scripts/tools/README.md`](../scripts/tools/README.md)); the cleartext
  `advisors.json` is gitignored
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
- `linkedin_posts.json` — the same, for LinkedIn (see
  [`docs/linkedin.md`](../docs/linkedin.md)). Seeded separately, on the first
  run with LinkedIn posting enabled.

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
  regenerate them with `./scripts/generate/generate-cli-data.sh`. The CLI itself
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
  still updating the rest from the scraped page. Released with
  `python -m scripts.unfreeze_mergers`.
- `known_notification_dates.json` — manually confirmed or frozen notification
  dates, for matters whose register page doesn't give one (candidates are
  suggested by `scripts/fix_missing_notification_dates.py`).

## Pipeline flow

```
ACCC website
    │  scripts/scrape/scrape.sh
    ▼
data/raw/
    │  python -m scripts.extract_mergers
    ▼
data/processed/
    │  python -m scripts.generate.generate_static_data
    ├──────────────► frontend/public/data/                  (deployed)
    └──────────────► data/output/                           (offline analysis)
```

1. **Scrape**: ACCC register and matter pages → `raw/`
2. **Extract**: HTML/PDF parsing → `processed/`
3. **Generate**: enrich + write the static JSON → `frontend/public/data/` and
   `output/`
