# Deployment configuration

This document describes the deployment setup for the ACCC Merger Tracker using Cloudflare Pages.

## Overview

The architecture is fully static:

- **GitHub Actions** runs the pipeline (scrape, extract, generate) and commits updated data files
- **Cloudflare Pages** serves the React frontend and static JSON data
- **Cloudflare Worker** handles email digest signup form submissions
- No backend server required

```
GitHub Actions (pipeline.yml — hourly)
    ↓
Scrapes ACCC → data/raw/matters/*.html
    ↓
Extracts → data/processed/mergers.json
    ↓
Generates static data files:
  - merger-tracker/frontend/public/data/
  - data/output/ (CLI bundle)
  - merger-tracker/frontend/public/feed.xml (RSS)
    ↓
Commits to main branch
    ↓
Cloudflare Pages auto-deploys
```

## Cloudflare Pages configuration

Build configuration is codified in the repo:

- **`wrangler.toml`** — Pages project settings (name, output directory, compatibility date)
- **`scripts/build.sh`** — Build script that compiles the frontend and copies PDFs into the output

The build script runs `npm ci && npm run build`, then copies all PDFs from `data/raw/matters/` into `dist/mergers/`, preserving the folder structure (e.g., `dist/mergers/MN-40008/file.pdf`). Documents are served at `mergers.fyi/mergers/{id}/file.pdf`.

### Dashboard settings

These settings must still be configured in the Cloudflare Pages dashboard:

- **Framework preset**: None
- **Build command**: `bash scripts/build.sh`
- **Build output directory**: `merger-tracker/frontend/dist`
- **Root directory**: `/` (repo root)

### Custom domain

Configure your custom domain (e.g., `mergers.fyi`) in Cloudflare Pages settings.

## Cloudflare Worker

The `cloudflare-worker/` directory contains a Worker that handles digest email signup form submissions and validates Cloudflare Turnstile tokens. It is deployed separately via wrangler:

```bash
cd cloudflare-worker
npx wrangler deploy
```

## GitHub workflows

### `pipeline.yml` — Main pipeline (hourly + on push to main)

The primary automated workflow. Runs end-to-end on a schedule and on every push to `main`:

1. **Scrape** — runs `scripts/scrape.sh` to fetch new/updated ACCC merger pages into `data/raw/matters/`
2. **Extract** — runs `extract_mergers.py`, `generate_similar_mergers.py`, `generate_static_data.py`, `generate-cli-data.sh`, `generate_rss_feed.py`
3. **Convert** — detects unconverted DOCX attachments, installs LibreOffice, converts to PDF; re-runs extraction if any were converted
4. **Commit** — commits all staged changes in a single commit, rebases, and pushes

Also accepts a `workflow_dispatch` with an `all_mergers` boolean input to force full re-extraction.

### `extract.yml` — Manual extraction

Manual-only (`workflow_dispatch`). Runs extraction and static data generation without scraping. Useful for regenerating data files without triggering a full scrape.

### `scrape.yml` — Manual scrape

Manual-only (`workflow_dispatch`). Runs only the scrape step.

### `convert.yml` — Manual DOCX conversion

Manual-only (`workflow_dispatch`). Converts any unconverted DOCX attachments to PDF.

### `detect-duplicates.yml` — Daily duplicate check (02:00 UTC)

Runs `detect_duplicates.py` to identify duplicate merger entries and reports any found.

### `detect-related-mergers.yml` — Daily related-merger check (02:30 UTC)

Runs `detect_related_mergers.py` to suggest waiver→notification pairs.

### `update-sitemap.yml` — Daily sitemap update (22:00 UTC)

Runs `generate_sitemap.py` to regenerate `sitemap.xml`.

### `weekly-digest.yml` — Weekly digest generation (Sat 22:00 UTC)

Runs `generate_weekly_digest.py` to generate `digest.json` for the weekly summary.

### `send-weekly-email.yml` — Weekly email send (Sun 23:00 UTC)

Sends the weekly digest email via the Cloudflare Worker using `send_weekly_email.py`.

### `test.yml` — Python test suite

Manual-only (`workflow_dispatch`). Runs `pytest scripts/tests/`.

### `frontend-test.yml` — Frontend tests

Manual-only (`workflow_dispatch`). Runs the frontend test suite.

### `embed.yml` — Semantic embeddings

Manual-only (`workflow_dispatch`). Generates semantic embeddings for merger similarity.

## Static data files

All data files are pre-generated into `merger-tracker/frontend/public/data/`:

| File | Description |
|------|-------------|
| `mergers/{id}.json` | Individual merger detail files |
| `mergers/list-page-{N}.json` | Paginated lightweight merger lists (50/page) |
| `mergers/list-meta.json` | Pagination metadata for merger list |
| `stats.json` | Aggregated statistics (counts, averages, medians) |
| `timeline-page-{N}.json` | Paginated timeline events (100/page) |
| `timeline-meta.json` | Pagination metadata for timeline |
| `industries.json` | ANZSIC codes with merger counts |
| `industries/{code}.json` | Mergers per industry code |
| `upcoming-events.json` | Future consultation/determination dates |
| `commentary.json` | Mergers with user commentary |
| `digest.json` | Weekly digest of merger activity |
| `analysis.json` | Pre-computed analysis data |
| `similar_mergers.json` | Similarity pairs between mergers |

Additional output:
- `merger-tracker/frontend/public/feed.xml` — RSS feed
- `data/output/cli/` — CLI bundle (manifest + data files)

### Regenerating data locally

```bash
python scripts/extract_mergers.py
python scripts/generate_similar_mergers.py
python scripts/generate_static_data.py
./scripts/generate-cli-data.sh
python scripts/generate_rss_feed.py
```

## Local development

```bash
cd merger-tracker/frontend
npm install
npm run dev
```

The dev server serves static JSON from `public/data/`.

### Full pipeline (optional)

```bash
# 1. Scrape (or use existing matters/ data)
./scripts/scrape.sh

# 2. Extract merger data
python scripts/extract_mergers.py

# 3. Generate static files
python scripts/generate_similar_mergers.py
python scripts/generate_static_data.py
python scripts/generate_rss_feed.py

# 4. Run frontend
cd merger-tracker/frontend
npm run dev
```

## Business day calculations

Business day calculations happen client-side using:
- `merger-tracker/frontend/src/utils/dates.js`
- `merger-tracker/frontend/src/data/act-public-holidays.json`

The static data includes raw dates; the frontend calculates business days at render time.

## Benefits

- **$0/month** hosting (Cloudflare Pages free tier)
- **Global CDN** with fast load times
- **No server maintenance**
- **Version controlled data** with full git history
- **Simple deployment** — just push to main

## Limitations

- **No real-time updates** — data refreshes on GitHub Actions schedule
- **No user-generated content** — all data is public/read-only

## Monitoring

1. **GitHub Actions**: Check workflow runs for pipeline success
2. **Cloudflare Pages**: Check deployment status in dashboard
3. **Data freshness**: Compare `mergers.json` timestamps with ACCC website

## Troubleshooting

### Data not updating

1. Check `pipeline.yml` workflow completed successfully
2. Verify `data/processed/mergers.json` was updated (check git history)
3. Verify static data files were regenerated in `merger-tracker/frontend/public/data/`
4. Check Cloudflare Pages deployment succeeded

### Build failures

1. Check Node.js version matches `.nvmrc` (20.19.0)
2. Run `npm install` locally to verify dependencies
3. Check for errors in build output
