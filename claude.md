# ACCC Merger Tracker

A public-facing web application for tracking Australian Competition and Consumer Commission (ACCC) merger reviews. Live at https://mergers.fyi.

## Architecture

Fully static — no backend server. Cloudflare Pages serves the React SPA plus generated JSON data files. Data is refreshed by `pipeline.yml`, which scrapes, extracts, and regenerates the static JSON files several times a day (plus on-demand via an email-triggered `repository_dispatch`) and commits the result, triggering auto-deploy.

### Frontend (`merger-tracker/frontend/`)

- **React 19** SPA with **React Router 7** for client-side routing
- **Vite 7** build tool, **Tailwind CSS 3** for styling
- **Chart.js 4** for data visualizations
- **date-fns 4** for date manipulation
- Static JSON files in `public/data/` serve as the "API"

### Data Pipeline (`scripts/`)

- **Python 3.10** scripts for scraping, extracting, and generating data
- `scrape.sh` → `extract_mergers.py` → `generate_static_data.py`
- Dependencies: beautifulsoup4, requests, pdfplumber, markdownify

### Cloudflare Worker (`cloudflare-worker/`)

- Handles digest email signup form submissions
- Validates Cloudflare Turnstile tokens
- Deployed separately via wrangler

### ACCC Register Watcher (`accc-register-watcher/`)

- Cloudflare Email Worker bound to a mailbox subscribed to the ACCC's register update mailing list
- Fires a `repository_dispatch` (`new_merger_detected`) to trigger `pipeline.yml` immediately on each email
- Deployed separately via wrangler; see its README for the Cloudflare Email Routing setup

## Project Structure

```
merger-tracker/frontend/src/
├── main.jsx              # React root
├── App.jsx               # Router + layout (Navbar, Footer, KeyboardShortcutsHelp)
├── config.js             # API endpoint constants, SUBSCRIBE_ENDPOINT, TURNSTILE_SITE_KEY
├── pages/                # Route components
│   ├── Dashboard.jsx     # /
│   ├── Mergers.jsx       # /mergers
│   ├── MergerDetail.jsx  # /mergers/:id
│   ├── Timeline.jsx      # /timeline
│   ├── Industries.jsx    # /industries
│   ├── IndustryDetail.jsx # /industries/:code
│   ├── PartyDetail.jsx   # /parties/:id
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
├── components/           # Reusable UI
│   ├── Navbar.jsx, Footer.jsx, ErrorBoundary.jsx, ErrorCard.jsx, SEO.jsx, ScrollToTop.jsx
│   ├── StatusBadge.jsx, WaiverBadge.jsx, NewBadge.jsx, StatCard.jsx, LoadingSpinner.jsx
│   ├── CollapsibleCard.jsx, CardCollapseGrid.jsx, ShowMoreDivider.jsx
│   ├── UpcomingEventsTimeline.jsx, RecentDeterminationsCards.jsx, RecentMergersCards.jsx
│   ├── MergerTimeline.jsx, Phase2Timeline.jsx, Phase2NoticeMattersSection.jsx
│   ├── BusinessDayProgress.jsx, PhaseDurationComparison.jsx, PreNotificationEstimate.jsx
│   ├── DeterminationExplanationSection.jsx, QuestionnaireSection.jsx
│   ├── IndustryTreemap.jsx, IndustryMergerGroups.jsx
│   ├── NotificationPanel.jsx, BellIcon.jsx
│   ├── CommandPalette.jsx, KeyboardShortcutsHelp.jsx
│   ├── FeedbackPopup.jsx
│   └── ExternalLinkIcon.jsx
├── context/              # TrackingContext.jsx — global merger + industry follow state via localStorage
│                         #   (industry follows flag only new filings/determinations)
├── hooks/                # useDebounce.js, useFetchData.js, useKeyboardShortcuts.js
├── utils/                # dates.js, dataCache.js, lastVisit.js, classNames.js, searchIndex.js,
│                         #   businessDayProgress.js, fetchAllMergers.js, formatMedian.js,
│                         #   industryGroups.js, slug.js, preNotification.js
└── data/                 # ACT public holidays JSON
                          #   (act-public-holidays.json — source of truth for both the Python
                          #   pipeline and the frontend; authoritative list published at
                          #   https://www.cmtedd.act.gov.au/communication/holidays. Substitute-day
                          #   rules: a weekend ANZAC Day moves to the following Monday; Christmas
                          #   Day/Boxing Day substitutes are moot since the statutory 23 Dec-10 Jan
                          #   shutdown already excludes that period. The pipeline and a frontend
                          #   vitest test both fail loudly if the calendar's horizon shrinks to
                          #   less than ~1 year ahead — extend this file when that happens.)

scripts/
├── scrape.sh             # Bash wrapper using pup to scrape ACCC register
├── extract_mergers.py    # Parse HTML → merger data JSON
├── enrich_pdfs.py        # Run questionnaire/NOCC/Phase 2 Notice PDF parsing, auto-fix missing dates
├── generate_static_data.py  # Generate all frontend JSON files
├── generate_similar_mergers.py # Suggest similar mergers by industry/party overlap
├── generate_weekly_digest.py  # Generate digest.json for weekly summary
├── generate_sitemap.py   # Generate sitemap.xml
├── generate_rss_feed.py  # Generate RSS feed
├── generate-cli-data.sh  # Build/version-bump the accc-mergers-cli bundle (gitignored) + tracked manifest
├── build_cli_sqlite.py   # Build cli.sqlite from the CLI bundle
├── send_weekly_email.py  # Send weekly digest email via Cloudflare Worker
├── parse_determination.py   # Extract text from determination PDFs
├── parse_questionnaire.py   # Process questionnaire documents
├── parse_nocc.py          # Parse Notice of Competition Concerns summary PDFs
├── parse_phase2_notice.py # Parse "decision to proceed to Phase 2" notice PDFs
├── check_phase2_notice_ocr_needed.py # CI helper: does a pending Phase 2 Notice need OCR?
├── determination_text.py # Clean PDF-extracted determination text for the CLI bundle
├── normalization.py      # Data cleaning utilities
├── date_utils.py         # Date parsing helpers
├── slug.py               # Human-readable URL slugs for merger detail pages
├── cutoff.py             # Skip old mergers logic
├── merger_filters.py     # Canonical merger loading/filtering helpers (single source of truth)
├── detect_duplicates.py  # Identify duplicate merger entries (daily PR)
├── detect_related_mergers.py # Suggest waiver→notification pairs (daily PR)
├── detect_related_parties.py # Suggest same-entity party groups (daily PR)
├── fix_missing_notification_dates.py # Suggest freezing missing notification dates (daily PR)
├── party_matching.py     # Shared party normalisation + group matching
├── static_data/          # Generator package used by generate_static_data.py (outputs/, loaders, enrichment)
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
│                         #   tribunal matter pages by scripts/scrape_tribunal.py (the daily
│                         #   scrape-tribunal.yml workflow, which drives a real Chrome via
│                         #   nodriver to clear Cloudflare); the other fields are hand-maintained.
├── known_notification_dates.json # Manually-confirmed/frozen notification dates
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
cd merger-tracker/frontend
npm install
npm run dev       # Vite dev server at localhost:5173
npm run build     # Production build to dist/
npm run lint      # ESLint
npm run preview   # Preview production build

# Data pipeline (from repo root)
pip install -r scripts/requirements.txt
./scripts/scrape.sh
python scripts/extract_mergers.py
python scripts/generate_static_data.py

# Tests
python -m pytest scripts/tests/
```

## Code Conventions

- **React**: Function components with hooks. PascalCase for components, camelCase for functions/utilities.
- **State**: React Context (TrackingContext) for global tracking. localStorage for persistence. URL search params for filter state. Module-level in-memory cache (dataCache.js) to prevent refetch flicker.
- **Styling**: Utility-first Tailwind. Custom colors: primary `#335145`, accent `#10b981`. Mobile-first responsive design with sm/md/lg breakpoints. No scoped CSS — all Tailwind utility classes.
- **Python**: Type hints in function signatures. Docstrings for modules and functions. ProcessPoolExecutor for concurrent extraction in extract_mergers.py.
- **ESLint**: Flat config (eslint.config.js). Unused vars ignore pattern `^[A-Z_]`.
- **Node version**: 20.19.0 (see `.nvmrc`)
- **Commit messages**: describe the change only — no Claude/AI attribution. `.claude/settings.json` turns the default trailers off (`attribution.commit`/`pr` empty, `sessionUrl` false) and a `PreToolUse` hook (`.claude/hooks/check_commit_message.py`) denies any `git commit` whose message carries a `Co-Authored-By: Claude` trailer, a "Generated with Claude Code" line, or a claude.ai session link. Mentioning Claude Code in a message is fine; claiming it as the author is not.

## Key Data Flow

1. `pipeline.yml` scrapes the ACCC website → raw HTML in `data/raw/`
2. It extracts new/changed matters → `data/processed/mergers.json`
3. `generate_static_data.py` produces frontend JSON files in `merger-tracker/frontend/public/data/`
4. Cloudflare Pages auto-deploys on push to main

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
deletes files it no longer writes (`scripts/static_data/prune.py`), so a page
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
| `industries/{code}.json` | One file per ANZSIC node (division/subdivision/group/class), with hierarchy metadata (name, level, breadcrumb ancestors, parent, children) and mergers rolled up from the node's subtree (each merger summary carries `notification_date`/`determination_date` to drive industry-follow notifications). Generated for the full ANZSIC tree from `scripts/static_data/anzsic_codes.json` |
| `parties.json` | Every party (canonical group or single entity) with merger counts |
| `parties/{id}.json` | Mergers per party, grouped by role |
| `upcoming-events.json` | Future consultation/determination dates |
| `commentary.json` | Mergers with user commentary |
| `digest.json` | Weekly digest of merger activity (from `generate_weekly_digest.py`) |
| `analysis.json` | Pre-computed analysis data |
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
| `scrape-tribunal.yml` | Daily (6:23 AM UTC), manual | Scrape Australian Competition Tribunal matter pages into `tribunal_appeals.json` and commit. Drives a real Chrome via nodriver (headful under Xvfb) to get past the tribunal site's Cloudflare challenge, so it runs in CI. Deps: `scripts/requirements-tribunal.txt` |
| `detect-duplicates.yml` | Daily (2:00 AM UTC), manual | Detect duplicate merger entries, open a fix PR |
| `detect-related-mergers.yml` | Daily (2:30 AM UTC), manual | Suggest waiver↔notification merger links, open a PR |
| `detect-related-parties.yml` | Daily (2:45 AM UTC), manual | Suggest same-entity party groupings, open a PR |
| `fix-missing-notification-dates.yml` | Daily (3:00 AM UTC), manual | Auto-fix missing notification dates, open a PR |
| `update-sitemap.yml` | Daily (8 AM AEST), manual | Regenerate `sitemap.xml` |
| `weekly-digest.yml` | Weekly (Sunday, Sydney time), manual | Generate `digest.json` |
| `send-weekly-email.yml` | Manual (schedule currently disabled) | Send the weekly digest email via the Cloudflare Worker |
| `test.yml` | Manual | Run the Python test suite |
| `frontend-test.yml` | Pull requests touching `merger-tracker/frontend/**`, manual | Run the frontend test suite |
