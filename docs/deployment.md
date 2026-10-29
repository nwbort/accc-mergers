# Deployment configuration

This document describes the deployment setup for the ACCC Merger Tracker using Cloudflare Pages.

## Overview

The architecture is fully static:

- **GitHub Actions** runs the pipeline (scrape, extract, generate) and commits updated data files
- **Cloudflare Pages** serves the React frontend and static JSON data
- **Cloudflare Workers** handle digest signup and feedback submissions, and trigger the pipeline when the ACCC's register mailing list sends an email
- No backend server required

```
GitHub Actions (pipeline.yml — weekdays 4×/day, Sundays once, on push, on register email)
    ↓
Scrapes ACCC → data/raw/matters/*.html
    ↓
Extracts → data/processed/mergers.json
    ↓
Generates static data files:
  - frontend/public/data/
  - data/output/ (CLI bundle)
  - frontend/public/feed.xml (RSS), frontend/public/sitemap.xml
    ↓
Commits to main branch
    ↓
Cloudflare Pages auto-deploys
```

## Cloudflare Pages configuration

Build configuration is codified in the repo:

- **`wrangler.toml`** — Pages project settings (name, output directory, compatibility date)
- **`scripts/build.sh`** — Build script that compiles the frontend and copies PDFs into the output

The build script runs `npm ci && npm run build`, then writes the site's ATProto DID to `dist/.well-known/atproto-did` (only when one is configured — see [`atproto.md`](atproto.md)) and copies all PDFs from `data/raw/matters/` into `dist/mergers/`, preserving the folder structure (e.g., `dist/mergers/MN-40008/file.pdf`). PDFs over Pages' 25 MiB per-asset limit are left out of `dist/`; the Pages Function redirects those to the document's source URL. Documents are served at `mergers.fyi/mergers/{id}/file.pdf`.

### Dashboard settings

These settings live only in the Cloudflare Pages dashboard — nothing in the
repo sets them:

- **Framework preset**: None
- **Build command**: `bash scripts/build.sh`
- **Root directory**: `/` (repo root)

The **build output directory** is *not* one of them: `pages_build_output_dir`
in the root [`wrangler.toml`](../wrangler.toml) is the source of truth, and the
dashboard shows that field read-only. Change it in the repo, not the dashboard.

#### Build watch paths

Under **Settings → Build → Build watch paths**. Include paths:

```
frontend/*
functions/*
data/raw/matters/*
atproto/identity.json
scripts/build.sh
wrangler.toml
```

Between them these cover everything that reaches the deployed output: the SPA
and its committed JSON (`frontend/`), the Pages Function serving
`/mergers/{matter}/*.pdf` and the link-preview page for bots (`functions/`), the PDFs `build.sh` copies into
`dist/mergers/` (`data/raw/matters/`), the DID `build.sh` writes to
`/.well-known/atproto-did` (`atproto/identity.json` — see
[`atproto.md`](atproto.md)), and the two files that decide how the build
itself runs.

Two things to know before editing this list:

- A push matching none of the include paths **skips the build silently** —
  no failed deployment, no warning, just no deploy. A stale entry here
  therefore fails in the worst possible way, and data-pipeline commits keep
  deploying via `data/raw/matters/*` while a purely frontend change quietly
  does not. Re-check this list whenever a top-level directory is renamed.
- Cloudflare's wildcard is not an ordinary glob: `*` matches zero or more
  characters **including `/`**, so `frontend/*` already covers
  `frontend/src/App.jsx` and `frontend/public/data/stats.json`. There is no
  need for the `dir`, `dir/*`, `dir/**` triples that accumulate if you assume
  otherwise, and `**` is not documented as supported.

### Custom domain

Configure your custom domain (e.g., `mergers.fyi`) in Cloudflare Pages settings.

## Cloudflare Worker

Standalone Workers all live under [`workers/`](../workers/), one directory
per Worker, each named after the Worker it deploys. See
[`workers/README.md`](../workers/README.md) for the full index and the
layout convention.

`workers/mergers-digest-signup/` handles digest email signup form
submissions (validating Cloudflare Turnstile tokens) and stores feedback
submissions in D1. It is deployed separately via wrangler:

```bash
cd workers/mergers-digest-signup
npx wrangler deploy
```

`workers/feedback-admin/` is the private read-only viewer over that same
feedback database.

## Cloudflare Email Worker — ACCC register watcher

`workers/accc-register-watcher/` is a separate Email Worker
that watches a mailbox subscribed to the ACCC's register update mailing
list. On each email it fires a `repository_dispatch` event
(`new_merger_detected`) so `pipeline.yml` runs immediately rather than
waiting for its next scheduled run. See
[`workers/accc-register-watcher/README.md`](../workers/accc-register-watcher/README.md)
for setup (Cloudflare Email Routing configuration and the GitHub token
secret).

## GitHub workflows

The main ones are below. `quarterly-report.yml`, `linkedin-share-links.yml`,
`publish-lexicons.yml`, `check-deploy-assets.yml`, `revert-auto-merge.yml` and
`publish-cli-sqlite.yml` are covered in the root
[`CLAUDE.md`](../CLAUDE.md#github-actions-workflows).

### `pipeline.yml` — Main pipeline (scheduled + on push to main)

The primary automated workflow. Runs end-to-end on a schedule and on every push to `main`:

1. **Scrape** — runs `scripts/scrape/scrape.sh` to fetch new/updated ACCC merger pages into `data/raw/matters/`
2. **Extract** — runs `extract_mergers.py --skip-pdf-enrich` to parse new/changed matters into `data/processed/mergers.json` and download their attachments
3. **Convert** — detects unconverted DOCX attachments, installs LibreOffice, converts to PDF
4. **Enrich and generate** — runs `enrich_pdfs.py`, `generate_similar_mergers.py`, `generate_static_data.py`, `generate-cli-data.sh`, `generate_rss_feed.py`, `generate_sitemap.py`, then compresses oversized PDFs
5. **Publish** — publishes matters to the ATmosphere and posts new milestones to Bluesky and LinkedIn (see [`atproto.md`](atproto.md), [`linkedin.md`](linkedin.md)); each step is `continue-on-error` and skips without its credentials
6. **Commit** — commits all staged changes in a single commit, rebases, and pushes
7. **Detect** — runs all four detectors, each opening, refreshing or auto-closing its own review PR (see below)

Also accepts a `workflow_dispatch` with an `all_mergers` boolean input to force full re-extraction, and a `repository_dispatch` event (`new_merger_detected`) fired by the `accc-register-watcher` Cloudflare Email Worker when the ACCC's register update mailing list sends an email.

#### The four detectors

All four run as the last steps of every pipeline run, via the shared
[`detection-pr`](../.github/actions/detection-pr/action.yml) composite action.
Each branches off the latest `main`, applies its own suggestions to its own
data file, force-pushes a well-known fix branch, and opens/refreshes — or
auto-closes — a review PR. Each writes and commits only its own file, so they
never collide with each other or with the pipeline's own commit.

| Detector | Fix branch | Data file |
|---|---|---|
| `detect_duplicates.py` — duplicate event entries within a merger record | `fix/duplicate-events` | `data/processed/mergers.json` |
| `detect_related_mergers.py` — re-filed merger pairs (declined waiver→notification, or suspended→re-filed) | `fix/related-mergers` | `data/processed/related_mergers.json` |
| `detect_related_parties.py` — parties that are the same real-world entity under different names/ABNs | `fix/related-parties` | `data/processed/related_parties.json` |
| `fix_missing_notification_dates.py` — mergers whose ACCC page never published a notification date | `fix/missing-notification-dates` | `data/known_notification_dates.json` |

Two detectors auto-merge a batch whose every suggestion is beyond reasonable
doubt, and open a `needs-verification` issue instead of waiting on review
(`.github/actions/auto-merge-detection`): an exact-match waiver refile from
`detect_related_mergers.py`, and a high-confidence group from
`detect_related_parties.py` (names identical apart from punctuation, or one
name extending another under the same ABN — `is_high_confidence`). A mixed
batch waits for review in its entirety.

The related-parties issue can be undone from the issue itself: commenting
`/revert` (as a repo owner, member or collaborator) runs
`revert-auto-merge.yml`, which moves the batch's groups from `groups` into
`related_parties.json`'s `rejected` list, pushes that to `main`, dispatches the
pipeline and closes the issue. A plain `git revert` would not stick — the next
run would re-detect the same groups and merge them straight back — which is
why `/revert` is offered only for a detector that keeps a rejection list.

These four previously had standalone workflows of their own
(`detect-duplicates.yml`, `detect-related-mergers.yml`,
`detect-related-parties.yml`, `fix-missing-notification-dates.yml`), which have
been deleted — they were exact duplicates of these steps, and a cron on a fresh
checkout only ever guessed when `mergers.json` last moved. To re-run a detector
by hand, `workflow_dispatch` the pipeline.

Because the fix branch is rebuilt from `main` on every run, nothing a detector
wrote last run survives into the next one. Three of them re-derive their
suggestions from the data and lose nothing. The fourth can't: a missing
notification date defaults to *today*, so re-deriving it would re-date every
unreviewed candidate on every run and discard any correction made on the
branch. The action therefore recovers the previous run's copy of the data file
from the fix branch and hands it to the detector as `$PREVIOUS_DATA_FILE`;
`fix_missing_notification_dates.py` reads it via `--previous-known-dates` and
carries each existing entry forward verbatim.

### `weekly-digest.yml` — Weekly digest generation (Sun 8:36 AM Sydney time)

Runs `generate_weekly_digest.py` to generate `digest.json` for the weekly summary.

### `send-weekly-email.yml` — Weekly email send (manual)

Sends the weekly digest email via the Cloudflare Worker using `send_weekly_email.py`. Its Monday schedule is currently commented out, so it runs only on `workflow_dispatch` (with `dry_run`, `audience` and `banner` inputs).

### `test.yml` — Python test suite

Runs `pytest scripts/tests/` on pull requests touching `scripts/**`,
`atproto/**` or `fixtures/*.json`, and on demand (`workflow_dispatch`).

### `frontend-test.yml` — Frontend tests

Runs the frontend test suite on pull requests touching
`frontend/**`, `functions/**` or `fixtures/*.json`, and on
demand (`workflow_dispatch`).

### `workers-test.yml` — Cloudflare Worker tests

Runs on pull requests touching `workers/**`, and on demand
(`workflow_dispatch`). For every directory under `workers/`, runs
`npm ci`, then `npm test --if-present` (only `accc-register-watcher` has a
test suite today), then `npm run deploy:dry` to bundle the Worker and
validate its `wrangler.toml` without deploying. Discovers Workers by
globbing `workers/*/package.json`, so a new Worker is covered automatically.

### `scrape-tribunal.yml` — Tribunal matter scraper (scheduled + manual)

Runs hourly at :23 from 8am to 7pm Sydney time on weekdays, and on demand (`workflow_dispatch`, with an optional space-separated `merger_ids` input and a `save_pages` input that uploads each fetched matter page as an artifact). Runs `scrape_tribunal.py` to fill in `data/processed/tribunal_appeals.json`'s `documents[]` from the live Australian Competition Tribunal matter pages, mirrors the linked PDFs into `data/raw/matters/`, and commits the result.

The tribunal site is behind Cloudflare's managed challenge, so the scraper drives a real Chrome (headful, under Xvfb) via [nodriver](https://github.com/ultrafunkamsterdam/nodriver) to solve it — a genuine browser executing the challenge JS, which a plain `curl`/`requests` fetch can't do. That's what lets this run unattended in CI. If a matter's challenge doesn't clear within the timeout, that entry is left untouched and the run is flagged with a `::warning::` annotation (and a non-zero exit), while any matters that did scrape are still committed. See [Running the tribunal scraper](#running-the-tribunal-scraper) below.

## Static data files

All data files are pre-generated into `frontend/public/data/`:

| File | Description |
|------|-------------|
| `mergers/{id}.json` | Individual merger detail files |
| `mergers/list.json` | Lightweight list of every merger, one per line (the /mergers page and command palette) |
| `stats.json` | Aggregated statistics (counts, averages, medians) |
| `industries.json` | ANZSIC codes with merger counts |
| `industries/{division}.json` | Every ANZSIC node under that division, with its mergers |
| `parties.json` | Every party with merger counts |
| `parties/shard-{nn}.json` | Mergers per party, packed into 256 buckets by party id |
| `upcoming-events.json` | Future consultation/determination dates |
| `commentary.json` | Mergers with user commentary |
| `digest.json` | Weekly digest of merger activity |
| `analysis.json` | Pre-computed analysis data |

The root [`CLAUDE.md`](../CLAUDE.md#static-data-files) lists the rest.

Additional output:
- `frontend/public/feed.xml` — RSS (Atom) feed
- `frontend/public/sitemap.xml` — sitemap
- `data/processed/similar_mergers.json` — similarity pairs between mergers (an input to `generate_static_data.py`)
- `data/output/cli/` — CLI build inputs. Only `cli-manifest.json` is tracked
  (version counter + bundle checksum); `cli-bundle.json` and
  `cli-merger-manifest.json` are gitignored and regenerated on demand.

### Regenerating data locally

```bash
python -m scripts.extract_mergers
python -m scripts.generate.generate_similar_mergers
python -m scripts.generate.generate_static_data
./scripts/generate/generate-cli-data.sh
python -m scripts.generate.generate_rss_feed
```

### Running the tribunal scraper

`scripts/scrape/scrape_tribunal.py` fills in tribunal filing documents in `data/processed/tribunal_appeals.json` from the live Australian Competition Tribunal matter pages. It normally runs unattended from the [`scrape-tribunal.yml`](#scrape-tribunalyml--tribunal-matter-scraper-scheduled--manual) workflow (hourly on weekdays + on demand), so there's usually nothing to do by hand — but it works anywhere a Chrome/Chromium binary is available if you want to run it yourself:

```bash
pip install -r scripts/requirements-tribunal.txt   # nodriver, requests, beautifulsoup4, lxml

python -m scripts.scrape.scrape_tribunal                # scrape every entry that has a tribunal_url
python -m scripts.scrape.scrape_tribunal MN-01068        # scrape just this merger_id
python -m scripts.scrape.scrape_tribunal --dry-run       # parse and report only, write nothing
python -m scripts.scrape.scrape_tribunal --no-download   # record metadata only, skip file downloads

git add data/processed/tribunal_appeals.json data/raw/matters
git commit -m "Update scraped tribunal data"
git push
```

The scraper drives a real Chrome via nodriver to get past the tribunal site's Cloudflare challenge. On a headless machine run it under an X server so Chrome runs headful (far less likely to be flagged than headless), exactly as the workflow does:

```bash
xvfb-run -a python -m scripts.scrape.scrape_tribunal
```

The linked PDFs are downloaded by that same browser, via a `fetch()` run inside the matter page once its challenge has cleared. Handing the browser's cookies to `requests` is *not* sufficient — Cloudflare ties the clearance to the client that earned it (down to its TLS fingerprint), so a Python-side download replaying those cookies comes back `403 Forbidden` and the document is recorded in `documents[]` with no `url_gh` mirror. The `requests` path is kept only as a fallback.

Cloudflare also judges each request on its own, and occasionally decides to challenge one of those document fetches. A `fetch()` is a subresource request with nowhere to display a challenge, so it is refused outright with a `403` carrying `cf-mitigated: challenge` — which is how, on 21 August 2026, a single new filing was recorded without a mirror while the seventeen documents alongside it downloaded fine. The scraper answers that in two steps: it retries the fetch a few seconds later (Cloudflare usually waves the next one through), and if it is still refused it *navigates* to the document — a top-level request can be challenged and cleared — then returns to the matter page and fetches it again.

A document that couldn't be mirrored raises a `::warning::` annotation naming it, so it shows on the run summary instead of hiding behind a green tick; it is retried on the next run, so a transient failure heals itself. Off-domain links are never mirrored by design and are not flagged. Unlike an uncleared challenge, a failed mirror doesn't fail the run — the document is still recorded and served from its tribunal URL.

New matters are still added to `tribunal_appeals.json` by hand (tribunal number, URL, appeal type, appellant) — the scraper only fills in the `documents[]` list for entries that already have a `tribunal_url`.

## Local development

```bash
cd frontend
npm install
npm run dev
```

The dev server serves static JSON from `public/data/`.

### Full pipeline (optional)

```bash
# 1. Scrape (or use existing matters/ data)
./scripts/scrape/scrape.sh

# 2. Extract merger data
python -m scripts.extract_mergers

# 3. Generate static files
python -m scripts.generate.generate_similar_mergers
python -m scripts.generate.generate_static_data
python -m scripts.generate.generate_rss_feed

# 4. Run frontend
cd frontend
npm run dev
```

## Business day calculations

Business day calculations happen client-side using:
- `frontend/src/utils/dates.js`
- `frontend/src/data/act-public-holidays.json`

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
3. Verify static data files were regenerated in `frontend/public/data/`
4. Check Cloudflare Pages deployment succeeded

### Build failures

1. Check Node.js version matches `.node-version` / `frontend/.nvmrc` (26.13.0)
2. Run `npm install` locally to verify dependencies
3. Check for errors in build output
