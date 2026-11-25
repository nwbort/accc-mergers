# Data Directory

All data files for the ACCC Mergers Tracker, organised by processing stage.

This project's own data is licensed under CC BY 4.0 (see
[`LICENSE-DATA`](../LICENSE-DATA)). The third-party documents mirrored in
`raw/` are not: they remain subject to their owners' terms (see
[`raw/NOTICE.md`](raw/NOTICE.md)).

## Structure

### `raw/`

Raw data scraped from the ACCC website by `scripts/scrape/scrape.py`:

- `acquisitions-register.html` — main acquisitions register listing page.
  This is a transient working artifact: it is re-fetched fresh at the start
  of every scrape run and only used within that run to derive matter links,
  so it is **git-ignored** rather than committed (it changes on every fetch
  even when no merger data has).
- `matters/MN-*.html`, `matters/WA-*.html` — individual merger detail pages
  (one HTML file per matter), stored without the ACCC site chrome: the
  scraper drops the skip links, header and megamenu, breadcrumb, footer,
  scripts, stylesheets and the subscribe modal (`trim_chrome` in
  `scripts/scrape/scrape.py`), keeping every `<meta>`, `<link>` and `<title>`
  in `<head>` and everything else on the page. Not a byte-for-byte copy of
  what the ACCC served: the markup is reserialised by lxml
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
  by `merger_id` (carried into the CLI bundle; the site has no NOCC files)
- `phase1_estimates.json` — frozen filing-time Phase 1 duration estimates,
  keyed by `merger_id` (written by
  `scripts/generate/static_data/phase1_estimate.py`)
- `commentary.json` — hand-authored commentary keyed by `merger_id`
  (edited via `scripts/tools/commentary.py`)
- `related_mergers.json` — pairs of matters where one was re-filed as
  another: a declined waiver re-filed as a notification (`waiver_refiled`),
  a suspended matter re-filed (`suspended_refiled`), or the same transaction
  resubmitted as the same kind of matter after its acquirer or scope changed
  (`resubmitted`, e.g. WA-35048 → WA-10054). A pair may carry hand-written
  `from_label` / `to_label` text for each side's detail-page link. Plus a `rejected` list of
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
  `merger_id`, one record per Federal Court file; hand-maintained apart from
  each record's `portal` block (the file's listings, orders, judgments,
  documents filed and parties, as the Commonwealth Courts Portal shows them),
  which `scripts/scrape/scrape_federal_court.py` fills in. The parties' contact
  details are kept here but never published
- `quarterly_commentary.json` — hand-written points for the quarterly report,
  keyed by quarter as the page URL names it (`26Q3`)
- `quarterly_versions.json` — each quarterly report's version history,
  keyed the same way: a new version (with the date it appeared) whenever the
  quarter's block in `quarterly.json` changes — minor (`v2.1`) when only its
  histograms moved, major (`v3`) otherwise (written by
  `scripts/generate/static_data/quarterly_versions.py`; delete a quarter to
  restart it at v1)
- `api_updated.json` — the API's `updated_at`: a hash of the API response
  and the time that hash was first seen, so the stamp moves only when the
  content does (written by `scripts/generate/static_data/outputs/api.py`;
  delete it to restamp with the next run's time)
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
  run with the Make.com webhook (or share links) configured.

### `output/`

Generated artefacts that are **not** deployed to the frontend, all written by
`python -m scripts.generate.generate_static_data`. Only one file here is
tracked.

- `mergers.json` — full enriched merger data (every field, including the ones
  the deployed per-merger files drop), as one file, for offline analysis.
  **Gitignored, not committed**: run the generator locally to get a copy.
  Nothing in the pipeline reads it.
- `cli/` — build inputs for the
  [`accc-mergers-cli`](https://github.com/nwbort/accc-mergers-cli) tool,
  written by `scripts/generate/cli_bundle.py` from the generator's in-memory
  records. Only `cli-manifest.json` is tracked; it holds the version counter
  and bundle checksum used to detect change between runs, and changes only when
  the bundle's content does. `cli-bundle.json` and `cli-merger-manifest.json`
  are gitignored. The CLI itself downloads `cli.sqlite` from the orphan
  `cli-dist` branch, built from the bundle during the pipeline run; nothing
  consumes these files from `main`.

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
    └──────────────► data/output/        (CLI bundle; offline analysis, gitignored)
```

1. **Scrape**: ACCC register and matter pages → `raw/`
2. **Extract**: HTML/PDF parsing → `processed/`
3. **Generate**: enrich + write the static JSON → `frontend/public/data/` and
   `output/`
