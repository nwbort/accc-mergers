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
  (most workflows, `pipeline.yml` and `test.yml` among them, pin 3.11;
  `check-deploy-assets.yml` and `scrape-tribunal.yml` pin 3.12)
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

### ATmosphere publishing (`atproto/`, `scripts/atproto/`)

The register is republished into the AT Protocol network — the same network
Bluesky runs on — as typed records anything else can read without scraping.
Three independent pieces, all inert until configured, on the ntfy principle (no
secret means skip, not fail). See [`docs/atproto.md`](docs/atproto.md).

- **The handle.** `scripts/build.sh` writes `dist/.well-known/atproto-did` from
  the DID in `atproto/identity.json`, making `mergers.fyi` usable as an ATProto
  handle. Generated rather than committed, and only when a DID is set: a 200
  carrying a DID that resolves to nothing is worse than a 404. `atproto/identity.json`
  therefore reaches the deployment, so it is in the Pages **build watch paths** —
  see [`docs/deployment.md`](docs/deployment.md#dashboard-settings).
- **Lexicons and records.** `fyi.mergers` is `mergers.fyi` reversed, so
  `fyi.mergers.matter` is a name only this site can answer for. One record per
  matter, keyed by the ACCC's own identifier, so a matter is addressable as
  `at://{did}/fyi.mergers.matter/MN-01016` without a lookup. Built from the
  generated detail files the site itself serves, so the two can't drift.
  Date-shaped fields are published as `YYYY-MM-DD`, never as the pipeline's
  midday-UTC storage form; `indexedAt` is the only datetime and only moves when
  the matter does, which is what makes the incremental publish possible.
- **Bluesky posts.** Deliberately narrow (arrival, phase 2 referral,
  determination, public benefit application and determination, cessation,
  Tribunal/Federal Court review). Needs
  `ATPROTO_POST_ENABLED` on top of the credentials, and the first *enabled* run
  seeds rather than posts, so switching it on can't replay the back catalogue.

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
├── atproto/                  # ATProto identity + the fyi.mergers.* lexicons
├── wrangler.toml             # Cloudflare *Pages* project config (must stay at root)
├── docs/                     # Deployment, walkthrough, ADRs, accessibility, atproto
└── fixtures/                 # Cross-language test fixtures
    ├── slug-cases.json       # Golden fixture pinning slugify() across all 3 impls
    ├── shard-cases.json      # Golden fixture pinning the party shard hash across both impls
    └── industry-division-cases.json  # Golden fixture pinning which industries/ file
                              #   an ANZSIC code is packed into, across both impls
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
│   ├── Industries.jsx    # /industries (not in the navbar; reachable from the command
│                         #   palette and the `g i` shortcut)
│   ├── IndustryDetail.jsx # /industries/:code and /industries/:code/:slug
│   ├── Parties.jsx       # /parties (not in the navbar; reachable from the command palette)
│   ├── PartyDetail.jsx   # /parties/:id and /parties/:id/:slug
│   ├── Commentary.jsx    # /commentary
│   ├── Digest.jsx        # /digest
│   ├── Analysis.jsx      # /analysis
│   ├── CurrentStatus.jsx # /current-status (recent decision times vs the all-time
│                         #   baseline). Deliberately bare: the two medians, each
│                         #   coloured by whether it is running slower or faster than
│                         #   usual, the pre-notification average, a share-concluded
│                         #   curve per matter type over the selected window, and the
│                         #   trend chart. No methodology copy — see the generator
│                         #   docstrings
│   ├── Phase2.jsx        # /phase-2
│   ├── RefiledNotifications.jsx # /refiled-notifications
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
│                         #   - Outcome: MergerOutcomeHeading — the status line
│                         #     above every merger's title, stating the outcome
│                         #     once decided and the live status until then
│                         #     (utils/mergerOutcome.js getHeaderStatus, whose
│                         #     determination-over-status precedence mirrors
│                         #     StatusBadge). What merely qualifies that — "with
│                         #     conditions", a concluded appeal's result — is
│                         #     folded into its run of text, since those are
│                         #     part of what the outcome is. A live "under
│                         #     appeal" is not a qualifier but a second status
│                         #     the matter carries, so it is set in the same
│                         #     type and wears the gavel that is the appeal's
│                         #     own glyph everywhere it appears (AppealBadge
│                         #     too). Nothing on the line is shrunk into a chip,
│                         #     and the detail page shows no separate status or
│                         #     appeal badge. MergerDetail fills the whole title block
│                         #     from constants/outcomeHeader.js, which has two
│                         #     registers: a decided matter takes a deep fill
│                         #     with white text and flips the links and
│                         #     TrackButton inside it to their on-dark treatment
│                         #     (`onDark: true`), a live one takes a pale tint of
│                         #     its status colour and keeps the light treatment.
│                         #     Only the deep fills wash out to indigo when a
│                         #     matter is under appeal. The merger list cannot
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
│                         #   Charts live in Treemap.jsx,
│                         #   PhaseDurationComparison.jsx,
│                         #   TurnaroundTrendChart.jsx and
│                         #   DurationEcdfChart.jsx; all follow the
│                         #   canvas + sr-only data table pattern in docs/accessibility.md.
│                         #   DurationEcdfChart draws one "share concluded by
│                         #   day N" curve and is shared by Analysis (all-time,
│                         #   with its business/calendar-day toggle) and
│                         #   CurrentStatus (the selected 30/90-day window) —
│                         #   one component is what keeps the two readings
│                         #   comparable. The card, its <h2> and the statutory
│                         #   deadline to mark belong to the caller.
│                         #   TurnaroundTrendChart is memo()'d: CurrentStatus
│                         #   re-renders on the window toggle it doesn't depend
│                         #   on, and its only prop is the generated monthly
│                         #   block. It registers its own Chart.js scales rather
│                         #   than relying on the host page (as Analysis and
│                         #   Dashboard do for theirs), so it renders on any page.
│                         #   __tests__/ holds the vitest suites, incl. accessibility.test.jsx.
├── constants/            # Shared literal tables: navPages.js (single source of truth for
│                         #   the navbar, command palette and keyboard shortcuts — each
│                         #   entry declares which of those surfaces it appears on, and
│                         #   Navbar, CommandPalette, useKeyboardShortcuts and
│                         #   KeyboardShortcutsHelp all derive their lists from it rather
│                         #   than keeping copies. A shortcut-only page, on neither the
│                         #   navbar nor the palette, is fine. Array
│                         #   order is the shortcut help overlay's reading order; the
│                         #   other two surfaces sort by navOrder/paletteOrder.
│                         #   constants/__tests__/navPages.test.js pins the invariants:
│                         #   unique paths and chord keys, and every path a real route
│                         #   in App.jsx),
│                         #   mergerStatus.js, appeal.js, regime.js, cardStyles.js,
│                         #   chartColors.js, outcomeDotColors.js, outcomeHeader.js,
│                         #   outcomeIcons.js, outcomeRail.js, statutoryDeadlines.js
├── context/              # TrackingContext.jsx — global merger + industry follow state via localStorage
│                         #   (industry follows flag only new filings/determinations)
├── hooks/                # useDebounce.js, useFetchData.js, useKeyboardShortcuts.js,
│                         #   useDecodedParam.js, useTurnstile.js (the Cloudflare
│                         #   Turnstile widget lifecycle — script injection, explicit
│                         #   render, token, reset, teardown — shared by the digest
│                         #   signup and the feedback form), useBackgroundRefresh.js
│                         #   (mounted once from App.jsx; periodically re-fetches
│                         #   whatever data is currently on screen — on regaining tab
│                         #   visibility, plus a long fallback interval — via
│                         #   dataCache.revalidate, so an open tab picks up freshly
│                         #   published data without a full reload)
├── utils/                # chartSetup.js (the single Chart.js registration point — import it
│                         #   from any module that draws a chart; registering per page instead
│                         #   silently breaks a chart reused on a page that registered less,
│                         #   and jsdom cannot catch it, so utils/__tests__/chartSetup.test.js
│                         #   guards both halves), dates.js, dataCache.js, lastVisit.js,
│                         #   classNames.js, searchIndex.js,
│                         #   businessDayProgress.js, fetchAllMergers.js, formatMedian.js, phase2Summary.js,
│                         #   industryGroups.js, slug.js, shard.js, preNotification.js, pageMeta.js,
│                         #   industryDivision.js (which industries/ file an ANZSIC code is in —
│                         #   mirrors scripts/industry_division.py) and industryNode.js (reads one
│                         #   node back out of that file; the only module that knows the packing),
│                         #   treemapTail.js, mergerOutcome.js, partyMembers.js, durationEcdf.js,
│                         #   mergerSort.js (the merger list's ?sort= vocabulary: the field table
│                         #   the select is built from and the comparator it drives),
│                         #   timelineAxis.js (the horizontal milestone track's geometry —
│                         #   percentAlong, clampedLabelStyle and the above/below-line
│                         #   offsets — shared by Phase2Timeline and the refiled cards;
│                         #   MergerTimeline keeps its own positioning code but the same
│                         #   conventions)
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
├── fix_missing_notification_dates.py # Suggest freezing missing notification dates (review PR
│                         #   from pipeline.yml; carries its earlier guess forward, see its docstring)
├── compress_pdfs.py      # Shrink oversized PDFs so Pages will serve them
├── check_deploy_assets.py # CI check: no deploy asset exceeds Cloudflare Pages' 25 MiB limit
├── check_watchlist.py    # CI check: has a watchlisted merger changed this run? (see docs/notifications.md)
├── unfreeze_mergers.py   # Release frozen notification dates / phase-1 estimates
├── normalization.py      # Data cleaning utilities
├── date_utils.py         # Date parsing helpers
├── slug.py               # Human-readable URL slugs for merger detail pages
├── shard.py              # Which shard bucket a party record lives in (matches frontend/src/utils/shard.js)
├── industry_division.py  # Which industries/{division}.json file an ANZSIC code is packed into
│                         #   (matches frontend/src/utils/industryDivision.js)
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
│   ├── detect_duplicates.py  # Identify duplicate merger entries (review PR from pipeline.yml)
│   ├── detect_related_mergers.py # Suggest waiver→notification pairs (review PR from pipeline.yml)
│   ├── detect_related_parties.py # Suggest same-entity party groups (review PR from pipeline.yml)
│   ├── related_parties_batch.py # Batch LLM-assisted related-party suggestions
│   └── party_matching.py # Shared party normalisation + group matching
├── generate/
│   ├── generate_static_data.py  # Generate all frontend JSON files
│   ├── generate_similar_mergers.py # Suggest similar mergers by industry/party overlap
│   ├── generate_weekly_digest.py  # Generate digest.json for weekly summary
│   ├── generate_sitemap.py   # Generate sitemap.xml (runs in pipeline.yml beside the RSS feed)
│   ├── generate_rss_feed.py  # Generate RSS feed
│   ├── generate-cli-data.sh  # Build/version-bump the accc-mergers-cli bundle (gitignored) + tracked manifest
│   ├── build_cli_sqlite.py   # Build cli.sqlite from the CLI bundle
│   └── static_data/      # Generator package used by generate_static_data.py (outputs/, loaders, enrichment)
├── atproto/              # ATmosphere publishing (see docs/atproto.md). client.py is a
│                         #   hand-rolled XRPC client over requests; records.py maps a
│                         #   generated merger detail file to a fyi.mergers.matter record;
│                         #   publish_lexicons.py / publish_matters.py / post_bluesky.py are
│                         #   the entry points, each a no-op without ATPROTO_APP_PASSWORD.
│                         #   State lives in data/processed/atproto_{records,posts}.json
├── constants/            # Shared Python literals (merger_status.py, site.py, tribunal.py,
│                         #   regime.py — mirrors frontend/src/constants/regime.js; keep in step)
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
│                         #   pipeline. Each merger's estimate is computed once and
│                         #   frozen, so it stays an at-filing snapshot. The pool is the
│                         #   completed phase-1 reviews whose questionnaire asked a
│                         #   similar number of questions (buckets ≤3 / 4-5 / 6-9 / 10+,
│                         #   ≥8 peers, else the whole-of-market median); question count
│                         #   is the strongest filing-time signal available, since the
│                         #   ACCC publishes the questionnaire a median of 1 business day
│                         #   after notification. Pooling on ANZSIC industry (method
│                         #   version 1) scored worse than a plain global median and was
│                         #   dropped — see the module docstring for the backtest.
│                         #   Forward-chained: a merger's pool holds only reviews that had
│                         #   already concluded when it was filed (recorded as as_of), so
│                         #   a method migration recomputes history without hindsight. The
│                         #   earliest matters have too little history and get no estimate
│                         #   (invisible on the site — the forecast renders only while a
│                         #   matter is open). Attached to each notification merger as
│                         #   phase_1_estimate (see mergers/{id}.json). Backend-only.
│   processed/atproto_records.json # Digest of each fyi.mergers.matter record as last
│                         #   published, so a run rewrites only what moved. Written by
│                         #   scripts/atproto/publish_matters.py; an optimisation, not a
│                         #   source of truth (the publish is an upsert). Its sibling
│                         #   atproto_posts.json is the set of milestones already posted
│                         #   to Bluesky. Both only exist once publishing is configured
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

# ATmosphere publishing (from repo root; every entry point has --dry-run,
# which needs no credentials)
python -m scripts.atproto.publish_lexicons --dry-run
python -m scripts.atproto.publish_matters --dry-run
python -m scripts.atproto.post_bluesky --dry-run

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

### Public benefit phase

After a Phase 2 determination that refuses a merger or clears it on
conditions, the parties have 21 calendar days to apply for a public benefit
determination. The register's stage then becomes **"Public benefit phase"**
(lower-case "benefit", unlike the phase labels — match stages with
`merger_status.stage_phase()` / `isPublicBenefitStage()`, never a bare `in`).
The phase runs 50 business days: public benefit assessment by BD 20, the
parties' responses or remedy offer by BD 35. MN-65005 was the first matter
expected to reach it.

- **Per-phase determinations.** The register has one headline determination,
  so once the stage moves on it can't say which phase a determination belongs
  to. `scripts/stage_determinations.py` records each phase's determination as
  it is seen and carries it forward in `mergers.json` (`stage_determinations`,
  stored only when it differs from what the headline says). Enrichment reads
  `phase_*_determination` and `public_benefits_determination` from it, and
  extraction uses it to keep the Phase 2 determination event's title and flag.
- **The matter is live again.** While the application runs
  (`public_benefit_in_progress`), enrichment clears the headline determination
  and reads the status as under assessment, as for a matter still in Phase 2.
  The Phase 2 outcome stays in `phase_2_determination`, and the matter stays on
  the Phase 2 tracker and in every Phase 2 count (`enrichment.reached_phase_2`,
  not the stage).
- **Timetable.** A leftover Phase 2 deadline is replaced with BD 50 from the
  application (or dropped until one appears); `public_benefit_assessment_date`
  and `public_benefit_response_date` feed upcoming events and follow alerts.

## Static Data Files

All data files are pre-generated by `generate_static_data.py` (and other scripts).

Every generated directory below (`mergers/`, `parties/`, `industries/`,
`timeline/`, `questionnaires/`, `noccs/`) is **self-pruning**: each generator
deletes files it no longer writes (`scripts/generate/static_data/prune.py`), so a page
that stops being generated stops being served. This is what drops a trailing
paginated page when a list shrinks, and (in `parties/`) what removes a shard
bucket once nothing hashes into it. A generator that wrote nothing prunes
nothing, so a failed or empty load can never empty a directory.

The 20,000-file cap is guarded by `check-deploy-assets.yml`, which counts the
deployment on every push to `main` — including the prerendered HTML, derived
from the data files rather than measured, since it doesn't exist until build
time and is over half the total. Going over doesn't degrade gracefully: Pages
refuses the whole upload and keeps serving the previous deployment, so the
site stays up but silently stops updating, with every workflow still green.

### Party and industry files are packed, not one-per-item

Two directories hold many records per file, for the same reason: Cloudflare
Pages caps a deployment at 20,000 **files** (not bytes), so a one-kilobyte
file costs as much of that budget as a large one.

#### Parties are sharded

Party records are packed into a fixed set of 256 `shard-{nn}.json` buckets
keyed by party id: ~2,200 one-kilobyte party files cost as much of that budget
as 2,200 large ones. Sharding cut the deployment from ~8,600 files to ~7,200;
packing the industry nodes below took it to ~6,400.

The bucket is *computed* from the id, never looked up, so a party page is
still a single request. That makes the hash load-bearing across languages,
exactly like `slugify()`: `scripts/shard.py` writes the buckets and
`frontend/src/utils/shard.js` decides which one to fetch, and if they ever
disagree the SPA asks for the wrong bucket and *every* party page 404s.
`fixtures/shard-cases.json` pins the pair (both test suites read it), and
`prerender.js` re-checks every record's bucket against the JS function at
build time and **fails the build** on a mismatch — the whole real dataset as
a cross-language check, not just the fixture. FNV-1a is used because
Python's `hash()` is salted per process and JS has no built-in; it is not a
security primitive.

Changing `SHARD_COUNT` rehomes every party, invalidates every cached bucket
and rewrites the whole directory in one commit. It works (the generator
prunes the old names), but make it a deliberate choice.

#### Industry nodes are packed by ANZSIC division

`industries/` held one file per ANZSIC node — 825 of them, for every division,
subdivision, group and class. They are now packed one file per **division**:
`industries/F.json` carries every node under Wholesale Trade. That is 19 files
plus `_orphans.json` instead of 825, and 2.2 MB down to 0.7 MB (0.54 MB → 0.09
MB gzipped), because the bytes were mostly duplication: a merger tagged at a
class had its whole summary written four times over, into the class, its group,
its subdivision and its division, since every node lists the mergers rolled up
from its subtree. Inside one file each summary is stored once and referenced by
id.

Each file is `{division, nodes, mergers}`. A node entry holds its name, level,
parent code, child codes, stat counts, duration blocks (omitted when the node
has no completed reviews of that kind) and an ordered list of merger **ids** —
the order is load-bearing, since the summaries carry no sort keys. Breadcrumb
ancestors and each child's merger count are *not* stored: both are derivable
from the other nodes in the same file, and `frontend/src/utils/industryNode.js`
rebuilds them, handing the rest of the app the same node shape the per-node
files used to have. Nothing else knows about the packing.

The division is the right seam because every node has exactly one division
ancestor, and because `IndustryDetail` needs the *parent* node's durations for
its comparison chart — the parent is always in the same file, so the page went
from two fetches to one. Several followed industries under one division now
share a single fetch too.

Which file a code lives in is *computed*, never looked up, so an industry page
is still a single request — but unlike the party shard, the rule isn't derived
from the id: `45` sits under `H` only because of how ANZSIC numbers its
subdivisions. `scripts/industry_division.py` holds the 19-row range table and
`frontend/src/utils/industryDivision.js` mirrors it, making it load-bearing
across languages exactly like `slugify()` and the party shard hash: if they
disagree the SPA asks for the wrong file and every industry page 404s.
`fixtures/industry-division-cases.json` pins the pair (both suites read it),
the Python suite additionally checks the table against the real ANZSIC tree
(the fixture only proves the two copies agree with *each other*), and
`prerender.js` re-checks every node's file against the JS function at build
time and **fails the build** on a mismatch.

Placement follows that one rule for *every* code, including codes the ACCC has
mistyped: `5400` isn't a real ANZSIC node but its division is still derivable,
so it is filed under `J` — the frontend has nothing else to go on. Only a code
the table can't place at all (an unused subdivision number, a slashed tag) goes
to `_orphans.json`, which is written even when empty so the fallback always
exists rather than 404ing into the SPA's `index.html`.

| File | Description |
|------|-------------|
| `mergers/{id}.json` | Individual merger detail files |
| `mergers/list-page-{N}.json` | Paginated lightweight merger lists (50/page) |
| `mergers/list-meta.json` | Pagination metadata for merger list |
| `stats.json` | Aggregated statistics (counts, averages, medians) |
| `industries.json` | ANZSIC codes (as tagged on mergers) with merger counts |
| `industries/{division}.json` | One file per ANZSIC division, holding every node in its subtree (division/subdivision/group/class) — see *Industry nodes are packed by ANZSIC division* above. Each node carries hierarchy metadata (name, level, parent, children), stat counts, durations and an ordered list of merger ids; the summaries sit once per file in a `mergers` map (each carries `notification_date`/`determination_date` to drive industry-follow notifications). Generated for the full ANZSIC tree from `scripts/generate/static_data/anzsic_codes.json`. Codes outside that tree are filed by the same rule, falling to `_orphans.json` only when no division can be derived |
| `parties.json` | Every party (canonical group or single entity) with merger counts |
| `parties/shard-{nn}.json` | Mergers per party, grouped by role, packed into 256 buckets by party id — see *Party files are sharded* above |
| `upcoming-events.json` | Future consultation/determination dates |
| `commentary.json` | Mergers with user commentary |
| `digest.json` | Weekly digest of merger activity (from `generate_weekly_digest.py`) |
| `analysis.json` | Pre-computed analysis data. `current_status` (powering `/current-status`) re-cuts the same durations over rolling windows of recently *decided* matters (30/90 days), plus a per-decision-month series aligned index-for-index with `open_caseload`, so the filing-time question ("what is the ACCC turning around *now*") doesn't have to be answered from the all-time median. Each window's `notifications`/`waivers` block carries its own flat `duration_histogram` (business days → matters decided in exactly that many), the recent-window twin of the all-time histograms below, so the same ECDF can be drawn over just what was decided lately. Each window also carries `notifications_filed` and a `pre_notification` block (keyed by *filing* date, since that stage ends at filing rather than at a decision; the estimate is a calendar-day figure but is published here in business days, like every other duration on the page). No waiver inflow is published, since a waiver only reaches the register once decided. `phase1_duration`/`waiver_duration` each carry a `duration_histogram`: a nested count map, business days → calendar days → number of completed reviews with that exact pair. It replaced a flat list holding one object per review — same distribution (the records are anonymous, so a multiset of pairs is exactly the list), a third of the file. Read business days by summing each inner map; read calendar days by folding the inner keys together (`frontend/src/utils/durationEcdf.js`) |
| `referral-probability-by-day.json` | Modelled probability of a Phase 2 referral by elapsed business day |
| `serial-acquirers.json` | Serial-acquirer ("creeping acquisitions") detection |
| `theories_of_harm.json` | Keyword-classified theory-of-harm taxonomy |
| `phase2.json` | Current + completed Phase 2 matters with statutory milestones |
| `refiled-notifications.json` | Waivers declined then re-filed as notifications, split into current/completed |
| `extensions.json` | Phase 1 timeline extensions parsed from register notices (day counts, reasons, per-matter clock totals, Phase 2 correlation). Not read by the frontend since the `/extensions` page was removed |
| `questionnaires/{id}.json` | Lazy-loaded questionnaire files |
| `noccs/{id}.json` | Notice of Competition Concerns summaries (consumed by the CLI data bundle, not fetched by the frontend) |

## GitHub Actions Workflows

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| `pipeline.yml` | Push to `main`, weekdays 4×/day + Sunday once (Sydney time), `repository_dispatch` (email-triggered), manual | End-to-end scrape → extract → convert DOCX → enrich → generate static files (incl. `feed.xml` and `sitemap.xml`) → publish to the ATmosphere → commit; publishes `cli.sqlite`, opens tracking issues when needed, then runs all four detectors. The two ATmosphere steps are `continue-on-error` and skip without `ATPROTO_APP_PASSWORD` — an unreachable PDS must not cost the run its scrape |
| `publish-cli-sqlite.yml` | Manual | Republish `cli.sqlite` + manifest to the orphan `cli-dist` branch |
| `publish-lexicons.yml` | Push to `main` touching `atproto/lexicons/**` or the workflow itself, manual (with a `dry_run` input) | Publish the `fyi.mergers.*` schemas as `com.atproto.lexicon.schema` records. Its own workflow rather than a pipeline step: a lexicon changes only when a person edits one, so a path-filtered push fires exactly then, where `pipeline.yml` would re-read both records several times a day to learn nothing moved. A missing `ATPROTO_APP_PASSWORD` skips a push run and fails a manual one |
| `scrape-tribunal.yml` | Hourly at :23 from 8am-7pm Sydney time, weekdays only (`23 8-19 * * 1-5` with `timezone: Australia/Sydney`), manual | Scrape Australian Competition Tribunal matter pages into `tribunal_appeals.json` and commit. Drives a real Chrome via nodriver (headful under Xvfb) to get past the tribunal site's Cloudflare challenge, so it runs in CI. Deps: `scripts/requirements-tribunal.txt` |
| `weekly-digest.yml` | Weekly (Sunday, Sydney time), manual | Generate `digest.json` |
| `send-weekly-email.yml` | Manual (schedule currently disabled) | Send the weekly digest email via the Cloudflare Worker |
| `test.yml` | Pull requests touching `scripts/**`, `atproto/**` or `fixtures/*.json`, manual | Run the Python test suite |
| `frontend-test.yml` | Pull requests touching `frontend/**`, `functions/**` or `fixtures/*.json`, manual | Run the frontend test suite |
| `check-deploy-assets.yml` | Push touching `data/raw/matters/**`, `frontend/public/**` or the check itself, manual | Guards both Cloudflare Pages limits that fail silently: opens a tracking issue for any asset over the 25 MiB per-file limit, and for the deployment approaching the 20,000-**file** cap (reports at 80%, fails the run once over). See `scripts/check_deploy_assets.py` |
| `workers-test.yml` | Pull requests touching `workers/**`, manual | For each directory under `workers/`: `npm ci`, `npm test --if-present`, then `npm run deploy:dry` to bundle the Worker and validate its `wrangler.toml`. Discovers Workers by glob, so a new one is covered automatically |

There is no standalone workflow for any detector, or for the sitemap. All four
detectors and `generate_sitemap.py` run inside `pipeline.yml`; the
`detect-duplicates.yml`, `detect-related-mergers.yml`,
`detect-related-parties.yml`, `fix-missing-notification-dates.yml` and
`update-sitemap.yml` workflows that used to duplicate them have been deleted.
A detector's inputs only ever change when the pipeline changes them, so a cron
on a fresh checkout was guessing when that happened — and a separate sitemap
commit to `main` re-triggered the whole pipeline for no new data. Re-run any of
it by dispatching `pipeline.yml`.

That note is about *crons*, not about standalone workflows as such, which is
why `publish-lexicons.yml` is one. Its input is a person editing a schema in
`atproto/lexicons/`, so a path-filtered push knows exactly when it changed
rather than guessing — and the pipeline, running several times a day, would
re-read two records that move perhaps once a year.

### Composite actions (`.github/actions/`)

- `detection-pr/` — one detector's whole lifecycle: branch off the base sha,
  run it, force-push its well-known fix branch and open/refresh/auto-close the
  review PR. Used by all four detectors in `pipeline.yml`. It also recovers the
  previous run's copy of the detector's data file from the fix branch and
  exposes it as `$PREVIOUS_DATA_FILE`, because the branch is rebuilt from
  `main` every run: `fix_missing_notification_dates.py` needs it (its default
  is *today*, so re-deriving would re-date every unreviewed candidate and
  discard corrections made on the branch), the other three ignore it.
- `ntfy/` — publish a push notification to an [ntfy](https://ntfy.sh) topic.

### Push notifications

The workflows that open something for review push an ntfy notification to a
phone, so a candidate related-merger or related-party PR isn't lost in the
GitHub email stream. Configured entirely by a `NTFY_TOPIC` repo secret; without
it every notification is skipped and nothing else changes. `detection-pr`
fingerprints the suggested lines and stores the hash in the PR body so a
re-detection of the same unmerged candidates doesn't re-notify on every
pipeline run. See [`docs/notifications.md`](docs/notifications.md).
