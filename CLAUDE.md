# ACCC Merger Tracker

A public-facing web application for tracking Australian Competition and Consumer Commission (ACCC) merger reviews. Live at https://mergers.fyi.

## Architecture

Fully static — no backend server. Cloudflare Pages serves the React SPA plus generated JSON data files. Data is refreshed by `pipeline.yml`, which scrapes, extracts, and regenerates the static JSON files several times a day (plus on-demand via an email-triggered `repository_dispatch`) and commits the result, triggering auto-deploy.

### Frontend (`frontend/`)

- **React 19** SPA with **React Router 8** for client-side routing
- **Vite 7** build tool, **Tailwind CSS 3** for styling
- **Chart.js 4** for data visualizations
- **date-fns 4** for date manipulation
- Static JSON files in `public/data/` serve as the "API"

### Data Pipeline (`scripts/`)

- **Python 3.11/3.12** scripts for scraping, extracting, and generating data
  (`test.yml` pins 3.11, the pipeline workflows 3.12)
- `scrape/scrape.sh` → `extract_mergers.py` → `generate/generate_static_data.py`
- `scripts/` is a package: entry points run as `python -m scripts.…` from the
  repo root, never by file path (the modules import each other absolutely)
- Dependencies (`scripts/requirements.txt`): beautifulsoup4, lxml, requests,
  markdownify, pdfplumber, cryptography, pytesseract

### Cloudflare Workers (`workers/`)

One directory per Worker, each named after the Worker it deploys (the directory name matches `name` in its `wrangler.toml`). All are deployed separately via wrangler — see [`workers/README.md`](workers/README.md).

- `workers/mergers-digest-signup/` — public HTTP API: digest email signup (validates Cloudflare Turnstile tokens, adds to a Resend audience) and `POST /feedback` writes to the `mergers-feedback` D1 database
- `workers/accc-register-watcher/` — Email Worker bound to a mailbox subscribed to the ACCC's register update mailing list; fires a `repository_dispatch` (`new_merger_detected`) to trigger `pipeline.yml` immediately on each email. See its README for the Cloudflare Email Routing setup
- `workers/feedback-admin/` — private read-only viewer over the same feedback D1 database, gated behind an `x-secret` header

### Cloudflare Pages Functions (`functions/`)

Run on the Pages project alongside the SPA, not as standalone Workers. Pages requires this directory at the build root, so it stays out of `workers/`. Currently just the PDF viewer wrapper for `/mergers/{matter}/*.pdf`.

## Project Structure

Top level:

```
.
├── frontend/                 # React SPA (the deployed site)
├── scripts/                  # Python data pipeline + its tests
├── data/                     # Scraped/processed data (the "database")
├── workers/                  # Standalone Cloudflare Workers, one dir per Worker
├── functions/                # Cloudflare Pages Functions (must stay at root)
├── wrangler.toml             # Cloudflare *Pages* project config (must stay at root)
├── docs/                     # Deployment, walkthrough, ADRs, accessibility
└── fixtures/                 # Cross-language test fixtures
    └── slug-cases.json       # Golden fixture pinning slugify() across all 3 impls
```

Frontend:

```
frontend/src/
├── main.jsx              # React root
├── App.jsx               # Router + layout (Navbar, Footer, KeyboardShortcutsHelp)
├── config.js             # API endpoint constants, SUBSCRIBE_ENDPOINT, TURNSTILE_SITE_KEY
├── pages/                # Route components
│   ├── Dashboard.jsx     # /
│   ├── Mergers.jsx       # /mergers
│   ├── MergerDetail.jsx  # /mergers/:id and /mergers/:id/:slug
│   ├── Timeline.jsx      # /timeline
│   ├── Industries.jsx    # /industries
│   ├── IndustryDetail.jsx # /industries/:code and /industries/:code/:slug
│   ├── Parties.jsx       # /parties (not in the navbar; reachable from the command palette)
│   ├── PartyDetail.jsx   # /parties/:id and /parties/:id/:slug
│   ├── Commentary.jsx    # /commentary
│   ├── Digest.jsx        # /digest
│   ├── Analysis.jsx      # /analysis
│   ├── Phase2.jsx        # /phase-2
│   ├── RefiledNotifications.jsx # /refiled-notifications
│   ├── Extensions.jsx    # /extensions (Phase 1 timeline extensions; not linked from the navbar)
│   ├── NickTwort.jsx     # /nick-twort
│   ├── PrivacyPolicy.jsx # /privacy
│   ├── Feedback.jsx      # /feedback
│   └── NotFound.jsx      # * (404)
├── components/           # ~45 reusable components, flat (no subdirectories).
│                         #   Deliberately not enumerated here — `ls` is accurate and
│                         #   this list was not. The ones worth knowing before you
│                         #   add another:
│                         #   - Layout/chrome: Navbar, Footer, Breadcrumb, SEO,
│                         #     ScrollToTop, ErrorBoundary, ErrorCard, ErrorMessage
│                         #   - Badges (all role="img", never role="status"):
│                         #     StatusBadge, WaiverBadge, NewBadge, AppealBadge,
│                         #     RefiledBadge. StatusBadge marks each decided
│                         #     outcome with a glyph (constants/outcomeIcons.js,
│                         #     shared with MergerOutcomeHeading) and has two
│                         #     forms (both in mergerStatus.js): a tint
│                         #     (STATUS_COLORS) that fills only for the rare
│                         #     adverse outcomes (EMPHATIC_OUTCOMES), and the
│                         #     `solid` form (SOLID_STATUS_COLORS) that fills
│                         #     every outcome, worn by the merger list
│                         #   - Card scaffolding reused across pages: CollapsibleCard,
│                         #     CardCollapseGrid, ShowMoreDivider, EmptyStateCard,
│                         #     StatCard, DetailStatGrid, MergerCardBody
│                         #   - Timelines: MergerTimeline, Phase2Timeline,
│                         #     UpcomingEventsTimeline, BusinessDayProgress
│                         #   - Outcome: MergerOutcomeHeading — the result line
│                         #     above a decided merger's title. MergerDetail
│                         #     fills that whole title block with the outcome's
│                         #     colour (constants/outcomeHeader.js) and flips
│                         #     the links and TrackButton inside it to their
│                         #     on-dark treatment; both read the verdict from
│                         #     utils/mergerOutcome.js. The merger list cannot
│                         #     borrow that fill — nine in ten matters are
│                         #     "Approved", so it would colour the whole page.
│                         #     It leads each card with a solid StatusBadge
│                         #     above the title instead, in the outcome's
│                         #     reading position rather than the far corner,
│                         #     over a left-edge rail in the same outcome colour
│                         #     (constants/outcomeRail.js).
│                         #   - Tracking/notifications: TrackButton, NotificationPanel,
│                         #     BellIcon
│                         #   - Global UI: CommandPalette, KeyboardShortcutsHelp,
│                         #     SearchInput, FeedbackPopup
│                         #   Charts live in Treemap.jsx and
│                         #   PhaseDurationComparison.jsx; both follow the
│                         #   canvas + sr-only data table pattern in docs/accessibility.md.
│                         #   __tests__/ holds the vitest suites, incl. accessibility.test.jsx.
├── constants/            # Shared literal tables: navPages.js (single source of truth for
│                         #   the navbar, command palette and keyboard shortcuts),
│                         #   mergerStatus.js, appeal.js, regime.js, cardStyles.js,
│                         #   chartColors.js, outcomeDotColors.js, outcomeHeader.js,
│                         #   outcomeIcons.js, outcomeRail.js
├── context/              # TrackingContext.jsx — global merger + industry follow state via localStorage
│                         #   (industry follows flag only new filings/determinations)
├── hooks/                # useDebounce.js, useFetchData.js, useKeyboardShortcuts.js,
│                         #   useDecodedParam.js
├── utils/                # dates.js, dataCache.js, lastVisit.js, classNames.js, searchIndex.js,
│                         #   businessDayProgress.js, fetchAllMergers.js, formatMedian.js,
│                         #   industryGroups.js, slug.js, preNotification.js, pageMeta.js,
│                         #   treemapTail.js, mergerOutcome.js, partyMembers.js
└── data/                 # ACT public holidays JSON
                          #   (act-public-holidays.json — source of truth for both the Python
                          #   pipeline and the frontend; authoritative list published at
                          #   https://www.cmtedd.act.gov.au/communication/holidays. Substitute-day
                          #   rules: a weekend ANZAC Day moves to the following Monday; Christmas
                          #   Day/Boxing Day substitutes are moot since the statutory 23 Dec-10 Jan
                          #   shutdown already excludes that period. The pipeline and a frontend
                          #   vitest test both fail loudly if the calendar's horizon shrinks to
                          #   less than ~1 year ahead — extend this file when that happens.)

scripts/                  # A Python package — entry points run as `python -m scripts.…`
├── extract_mergers.py    # Parse HTML → merger data JSON
├── enrich_pdfs.py        # Run questionnaire/NOCC/Phase 2 Notice PDF parsing, auto-fix missing dates
├── check_phase2_notice_ocr_needed.py # CI helper: does a pending Phase 2 Notice need OCR?
├── send_weekly_email.py  # Send weekly digest email via Cloudflare Worker
├── fix_missing_notification_dates.py # Suggest freezing missing notification dates (daily PR)
├── compress_pdfs.py      # Shrink oversized PDFs so Pages will serve them
├── check_deploy_assets.py # CI check: no deploy asset exceeds Cloudflare Pages' 25 MiB limit
├── unfreeze_mergers.py   # Release frozen notification dates / phase-1 estimates
├── normalization.py      # Data cleaning utilities
├── date_utils.py         # Date parsing helpers
├── slug.py               # Human-readable URL slugs for merger detail pages
├── cutoff.py             # Skip old mergers logic
├── merger_filters.py     # Canonical merger loading/filtering helpers (single source of truth)
├── paths.py              # REPO_ROOT / SCRIPTS_DIR anchors, so no module hardcodes its own depth
├── build.sh              # Cloudflare Pages build entry point (`bash scripts/build.sh`):
│                         #   builds the frontend, then copies data/raw/matters PDFs into dist/
├── scrape/
│   ├── scrape.sh         # Bash wrapper using pup to scrape ACCC register
│   ├── scrape_targets.py # Decide which matters need re-scraping
│   ├── scrape_summary.py # Human-readable summary of a scrape run for the Actions log
│   └── scrape_tribunal.py # Scrape Australian Competition Tribunal matter pages (drives a
│                         #   real Chrome via nodriver; deps in requirements-tribunal.txt)
├── parse/
│   ├── parse_determination.py   # Extract text from determination PDFs
│   ├── parse_questionnaire.py   # Process questionnaire documents
│   ├── parse_nocc.py     # Parse Notice of Competition Concerns summary PDFs
│   ├── parse_phase2_notice.py # Parse "decision to proceed to Phase 2" notice PDFs
│   └── determination_text.py # Clean PDF-extracted determination text for the CLI bundle
├── detect/
│   ├── detect_duplicates.py  # Identify duplicate merger entries (daily PR)
│   ├── detect_related_mergers.py # Suggest waiver→notification pairs (daily PR)
│   ├── detect_related_parties.py # Suggest same-entity party groups (daily PR)
│   ├── related_parties_batch.py # Batch LLM-assisted related-party suggestions
│   └── party_matching.py # Shared party normalisation + group matching
├── generate/
│   ├── generate_static_data.py  # Generate all frontend JSON files
│   ├── generate_similar_mergers.py # Suggest similar mergers by industry/party overlap
│   ├── generate_weekly_digest.py  # Generate digest.json for weekly summary
│   ├── generate_sitemap.py   # Generate sitemap.xml
│   ├── generate_rss_feed.py  # Generate RSS feed
│   ├── generate-cli-data.sh  # Build/version-bump the accc-mergers-cli bundle (gitignored) + tracked manifest
│   ├── build_cli_sqlite.py   # Build cli.sqlite from the CLI bundle
│   └── static_data/      # Generator package used by generate_static_data.py (outputs/, loaders, enrichment)
├── constants/            # Shared Python literals (merger_status.py, site.py, tribunal.py)
├── tools/                # Interactive admin web UIs (resolver, commentary, advisors, related_parties)
└── tests/                # Pytest suite covering the pipeline, generators, and CI checks

data/
├── raw/                  # Scraped HTML files and PDFs
├── processed/            # Intermediate JSON (mergers.json, commentary.json, advisors.json.enc)
│                         #   advisors data is backend-only: never published to the frontend, and
│                         #   stored encrypted as advisors.json.enc (cleartext advisors.json is
│                         #   gitignored). See scripts/tools/README.md (ADVISORS_PASSPHRASE).
│                         #   tribunal_appeals.json is a hand-maintained overlay of Australian
│                         #   Competition Tribunal appeals, keyed by merger_id, merged in at
│                         #   generate_static_data time (loaders.load_tribunal_appeals +
│                         #   enrichment.link_tribunal_appeals). It sets the merger's under_appeal
│                         #   flag + appeal record and folds the appeal documents into the event
│                         #   timeline, without touching the ACCC-scraped status/determination.
│                         #   The documents[] list is filled in automatically from the live
│                         #   tribunal matter pages by scripts/scrape/scrape_tribunal.py (the daily
│                         #   scrape-tribunal.yml workflow, which drives a real Chrome via
│                         #   nodriver to clear Cloudflare); the other fields are hand-maintained.
│                         #   That scrape is additive: the tribunal prunes its own filings table
│                         #   (superseded documentary indexes, say), and a document it removes is
│                         #   kept in documents[] — still mirrored, still a timeline event — and
│                         #   reported on the run. Delete one by hand to drop it for good.
│                         #   judicial_reviews.json is a hand-maintained overlay of Federal Court
│                         #   judicial reviews, keyed by merger_id, merged in at
│                         #   generate_static_data time (loaders.load_judicial_reviews +
│                         #   enrichment.link_judicial_reviews). Sets the merger's
│                         #   judicial_review record (applicant, filed date, case number, case
│                         #   URL) for a link-out card to the Commonwealth Courts Portal. Unlike
│                         #   tribunal_appeals.json there is no scraping and no documents are
│                         #   mirrored — every field is entered by hand.
├── README.md             # Layout + provenance of everything under data/
├── known_notification_dates.json # Manually-confirmed/frozen notification dates
├── frozen_events_mergers.json # Mergers whose event timeline is pinned against re-scrape
│   processed/phase1_estimates.json # Frozen filing-time phase-1 duration estimates,
│                         #   keyed by merger_id. Written by generate_static_data.py
│                         #   (static_data/phase1_estimate.py) and committed by the
│                         #   pipeline. Each merger's estimate is computed once, from the
│                         #   history of completed phase-1 reviews in its ANZSIC
│                         #   industries (pooled-median with hierarchical backoff:
│                         #   class→group→subdivision→division, ≥8 completed peers, else
│                         #   the global median), then frozen so it stays an at-filing
│                         #   snapshot. Attached to each notification merger as
│                         #   phase_1_estimate (see mergers/{id}.json). Backend-only.
├── digest-archive/       # Past weekly digest.json snapshots
└── output/               # Not deployed. Full enriched mergers.json (offline analysis)
    └── cli/              # Bundled data files for accc-mergers-cli (manifest + bundle)
```

## Common Commands

```bash
# Frontend development
cd frontend
npm install
npm run dev       # Vite dev server at localhost:5173
npm run build     # Production build to dist/
npm run lint      # ESLint
npm run preview   # Preview production build
npm test          # Vitest suite (~333 tests); npm run test:watch to iterate

# Data pipeline (from repo root)
pip install -r scripts/requirements.txt
./scripts/scrape/scrape.sh
python -m scripts.extract_mergers
python -m scripts.generate.generate_static_data

# Tests
python -m pytest scripts/tests/
cd workers/<worker-name> && npm test   # per-Worker suite, where one exists

# Cloudflare Workers (same scripts in every workers/* directory)
cd workers/<worker-name>   # dir name == deployed Worker name
npm install
npm run dev          # local wrangler dev server
npm run deploy:dry   # build without uploading
npm run deploy       # production deploy
npm run tail         # stream live logs
```

## Code Conventions

- **React**: Function components with hooks. PascalCase for components, camelCase for functions/utilities.
- **State**: React Context (TrackingContext) for global tracking. localStorage for persistence. URL search params for filter state. Module-level in-memory cache (dataCache.js) to prevent refetch flicker.
- **Styling**: Utility-first Tailwind. Custom colors: primary `#335145`, accent `#10b981`. Mobile-first responsive design with sm/md/lg breakpoints. No scoped CSS — all Tailwind utility classes.
- **Python**: Type hints in function signatures. Docstrings for modules and functions. ProcessPoolExecutor for concurrent extraction in extract_mergers.py.
- **ESLint**: Flat config (eslint.config.js). Unused vars ignore pattern `^[A-Z_]`.
- **Accessibility**: WCAG 2.2 AA. Colour families in `tailwind.config.js` keep text on the `dark` shade (the `DEFAULT`s are fills and several fail as small text); badges are `role="img"`, never `role="status"`; charts pair a presentational canvas with a labelled wrapper and an `sr-only` data table; every route has an `h1`. See `docs/accessibility.md` for the conventions and how to re-run the axe audit.
- **Node version**: 24.18.0 (pinned in both `.nvmrc` and `.node-version`)
- **Commit messages**: describe the change only — no Claude/AI attribution. `.claude/settings.json` turns the default trailers off (`attribution.commit`/`pr` empty, `sessionUrl` false) and a `PreToolUse` hook (`.claude/hooks/check_commit_message.py`) denies any `git commit` whose message carries a `Co-Authored-By: Claude` trailer, a "Generated with Claude Code" line, or a claude.ai session link. Mentioning Claude Code in a message is fine; claiming it as the author is not.

## Key Data Flow

1. `pipeline.yml` scrapes the ACCC website → raw HTML in `data/raw/`
2. It extracts new/changed matters → `data/processed/mergers.json`
3. `generate_static_data.py` produces frontend JSON files in `frontend/public/data/`
4. Cloudflare Pages auto-deploys on push to main — but only for pushes
   matching the dashboard's **build watch paths**, which name top-level
   directories and are not set from this repo. Renaming one silently stops
   deploys; see [`docs/deployment.md`](docs/deployment.md#dashboard-settings).

### Consultation section: two ACCC page formats

From Aug 2026 the ACCC began rewriting each matter page's **Consultation**
section, page by page as each matter is next edited (MN-40039 was among the
first published with it). `extract_mergers.py` handles both formats and will
need to until the rollout finishes:

- **Old**: a prose blurb (`field_acccgov_consultation_text`) stating the
  response deadline, plus a table of consultation documents using the same
  markup as "Decisions and key events" — so `_scrape_events` picked the
  questionnaire up as an ordinary attachment row.
- **New**: a structured consultation paragraph with its own header,
  description, status, open/closing dates and a questionnaire file reference
  (now served from `/system/files/moderated_files/`). The document table is
  gone, so `_scrape_consultation_events` reads the questionnaire out of that
  section and rebuilds the same timeline event, and the deadline comes from the
  "Closing date" field rather than from prose.

Two consequences worth knowing:

- Events for questionnaires read out of the new section carry
  `is_questionnaire_event: true`, because the consultation header the ACCC uses
  as the title does not always contain the word "questionnaire" (MN-45024's is
  "OEConnection-Epyx - Phase 1 consultation"). Anything that classifies an
  event as a questionnaire checks the flag first and the title second.
- When a page switches format the questionnaire is re-uploaded under a new URL
  and is sometimes re-titled and re-dated, so `_merge_events` re-binds these
  events by normalised attachment filename (`_same_consultation_document`)
  rather than the usual title+date rule.

The ACCC also now deletes the whole Consultation section once a consultation
closes, where it previously left a "the period … has concluded" blurb behind —
`consultation_response_due_date` still falls back to the stored value.

## Static Data Files

All data files are pre-generated by `generate_static_data.py` (and other scripts).

Every per-item directory below (`mergers/`, `parties/`, `industries/`,
`timeline/`, `questionnaires/`, `noccs/`) is **self-pruning**: each generator
deletes files it no longer writes (`scripts/generate/static_data/prune.py`), so a page
that stops being generated stops being served. This is what retires a party's
standalone page when it is folded into a canonical group in
`related_parties.json`, and what drops a trailing paginated page when a list
shrinks. A generator that wrote nothing prunes nothing, so a failed or empty
load can never empty a directory.

| File | Description |
|------|-------------|
| `mergers/{id}.json` | Individual merger detail files |
| `mergers/list-page-{N}.json` | Paginated lightweight merger lists (50/page) |
| `mergers/list-meta.json` | Pagination metadata for merger list |
| `stats.json` | Aggregated statistics (counts, averages, medians) |
| `timeline/timeline-page-{N}.json` | Paginated timeline events (100/page) |
| `timeline/timeline-meta.json` | Pagination metadata for timeline |
| `industries.json` | ANZSIC codes (as tagged on mergers) with merger counts |
| `industries/{code}.json` | One file per ANZSIC node (division/subdivision/group/class), with hierarchy metadata (name, level, breadcrumb ancestors, parent, children) and mergers rolled up from the node's subtree (each merger summary carries `notification_date`/`determination_date` to drive industry-follow notifications). Generated for the full ANZSIC tree from `scripts/generate/static_data/anzsic_codes.json` |
| `parties.json` | Every party (canonical group or single entity) with merger counts |
| `parties/{id}.json` | Mergers per party, grouped by role |
| `upcoming-events.json` | Future consultation/determination dates |
| `commentary.json` | Mergers with user commentary |
| `digest.json` | Weekly digest of merger activity (from `generate_weekly_digest.py`) |
| `analysis.json` | Pre-computed analysis data |
| `timeline.json` | Unpaginated timeline (alongside the paginated `timeline/` directory) |
| `referral-probability-by-day.json` | Modelled probability of a Phase 2 referral by elapsed business day |
| `serial-acquirers.json` | Serial-acquirer ("creeping acquisitions") detection |
| `theories_of_harm.json` | Keyword-classified theory-of-harm taxonomy |
| `phase2.json` | Current + completed Phase 2 matters with statutory milestones |
| `refiled-notifications.json` | Waivers declined then re-filed as notifications, split into current/completed |
| `extensions.json` | Phase 1 timeline extensions parsed from register notices (day counts, reasons, per-matter clock totals, Phase 2 correlation). Powers `/extensions` |
| `questionnaires/{id}.json` | Lazy-loaded questionnaire files |
| `noccs/{id}.json` | Notice of Competition Concerns summaries (consumed by the CLI data bundle, not fetched by the frontend) |

## GitHub Actions Workflows

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| `pipeline.yml` | Push to `main`, weekdays 4×/day + Sunday once (Sydney time), `repository_dispatch` (email-triggered), manual | End-to-end scrape → extract → convert DOCX → enrich → generate static files → commit; publishes `cli.sqlite` and opens tracking issues when needed |
| `scrape.yml` | Manual | Standalone scrape of the ACCC register (outside the pipeline) |
| `extract.yml` | Manual | Standalone extraction of merger data from raw HTML and commit |
| `convert.yml` | Manual | Convert any unconverted DOCX attachments to PDF and commit |
| `publish-cli-sqlite.yml` | Manual | Republish `cli.sqlite` + manifest to the orphan `cli-dist` branch |
| `scrape-tribunal.yml` | Hourly at :23 from 8am-7pm Sydney time, weekdays only (`23 8-19 * * 1-5` with `timezone: Australia/Sydney`), manual | Scrape Australian Competition Tribunal matter pages into `tribunal_appeals.json` and commit. Drives a real Chrome via nodriver (headful under Xvfb) to get past the tribunal site's Cloudflare challenge, so it runs in CI. Deps: `scripts/requirements-tribunal.txt` |
| `detect-duplicates.yml` | Manual | Detect duplicate merger entries, open a fix PR. **No longer scheduled** — this now runs inside `pipeline.yml` on every run; the standalone workflow is kept for manual re-runs |
| `detect-related-mergers.yml` | Manual | Suggest waiver↔notification merger links, open a PR. **No longer scheduled** — runs inside `pipeline.yml`; kept for manual re-runs |
| `detect-related-parties.yml` | Manual | Suggest same-entity party groupings, open a PR. **No longer scheduled** — runs inside `pipeline.yml`; kept for manual re-runs |
| `fix-missing-notification-dates.yml` | Daily (3:00 AM UTC), manual | Auto-fix missing notification dates, open a PR |
| `update-sitemap.yml` | Daily (8 AM Sydney time), manual | Regenerate `sitemap.xml` |
| `weekly-digest.yml` | Weekly (Sunday, Sydney time), manual | Generate `digest.json` |
| `send-weekly-email.yml` | Manual (schedule currently disabled) | Send the weekly digest email via the Cloudflare Worker |
| `test.yml` | Manual | Run the Python test suite |
| `frontend-test.yml` | Pull requests touching `frontend/**`, `functions/**` or `fixtures/slug-cases.json`, manual | Run the frontend test suite |
| `check-deploy-assets.yml` | Push touching `data/raw/matters/**`, `frontend/public/**` or the check itself, manual | Fail if any deploy asset exceeds Cloudflare Pages' 25 MiB per-file limit |
| `workers-test.yml` | Manual | For each directory under `workers/`: `npm ci`, `npm test --if-present`, then `npm run deploy:dry` to bundle the Worker and validate its `wrangler.toml`. Discovers Workers by glob, so a new one is covered automatically |
