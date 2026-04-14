# ACCC Merger Tracker

A public-facing web application for tracking Australian Competition and Consumer Commission (ACCC) merger reviews. Live at https://mergers.fyi.

## Architecture

Fully static — no backend server. Cloudflare Pages serves the React SPA plus generated JSON data files. Data is refreshed via GitHub Actions (hourly scrapes, daily extraction) which commit updated JSON files, triggering auto-deploy.

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
│   ├── Commentary.jsx    # /commentary
│   ├── Digest.jsx        # /digest
│   ├── Analysis.jsx      # /analysis
│   ├── NickTwort.jsx     # /nick-twort
│   ├── PrivacyPolicy.jsx # /privacy
│   └── NotFound.jsx      # * (404)
├── components/           # Reusable UI
│   ├── Navbar.jsx, Footer.jsx, ErrorBoundary.jsx, SEO.jsx
│   ├── StatusBadge.jsx, WaiverBadge.jsx, NewBadge.jsx
│   ├── StatCard.jsx, LoadingSpinner.jsx
│   ├── UpcomingEventsTable.jsx, RecentDeterminationsTable.jsx
│   ├── NotificationPanel.jsx, BellIcon.jsx
│   ├── KeyboardShortcutsHelp.jsx
│   └── ExternalLinkIcon.jsx
├── context/              # TrackingContext.jsx — global merger tracking state via localStorage
├── hooks/                # useDebounce.js, useKeyboardShortcuts.js
├── utils/                # dates.js, dataCache.js, lastVisit.js, classNames.js, searchIndex.js
└── data/                 # ACT public holidays JSON

scripts/
├── scrape.sh             # Bash wrapper using pup to scrape ACCC register
├── extract_mergers.py    # Parse HTML → merger data JSON
├── generate_static_data.py  # Generate all frontend JSON files
├── generate_weekly_digest.py  # Generate digest.json for weekly summary
├── generate_sitemap.py   # Generate sitemap.xml
├── generate_rss_feed.py  # Generate RSS feed
├── send_weekly_email.py  # Send weekly digest email via Cloudflare Worker
├── parse_determination.py   # Extract text from determination PDFs
├── parse_questionnaire.py   # Process questionnaire documents
├── normalization.py      # Data cleaning utilities
├── date_utils.py         # Date parsing helpers
├── cutoff.py             # Skip old mergers logic
├── resolver.py           # Merge/resolve duplicate merger records
├── detect_duplicates.py  # Identify duplicate merger entries
└── tests/                # test_pipeline.py, test_utils.py

data/
├── raw/                  # Scraped HTML files and PDFs
├── processed/            # Intermediate JSON (mergers.json, commentary.json)
└── output/               # Full enriched mergers.json (for offline analysis, not deployed)
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

## Key Data Flow

1. GitHub Actions scrapes ACCC website hourly → raw HTML in `data/raw/`
2. Daily extraction parses HTML → `data/processed/mergers.json`
3. `generate_static_data.py` produces frontend JSON files in `merger-tracker/frontend/public/data/`
4. Cloudflare Pages auto-deploys on push to main

## Static Data Files

All data files are pre-generated by `generate_static_data.py` (and other scripts):

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

## GitHub Actions Workflows

| Workflow | Schedule | Purpose |
|----------|----------|---------|
| `scrape.yml` | Hourly | Scrape ACCC website for new merger pages |
| `extract.yml` | Daily + on matters/ changes | Extract merger data → generate static files → deploy |
| `convert.yml` | After extract | Convert DOCX attachments to PDF |
| `detect-duplicates.yml` | On push | Check for duplicate merger entries |
| `test.yml` | On push | Run Python test suite |
| `update-sitemap.yml` | Daily | Regenerate sitemap.xml |
| `weekly-digest.yml` | Weekly | Generate and send weekly digest email |
| `send-weekly-email.yml` | Triggered | Send digest via Cloudflare Worker |
| `all-mergers.yml` | Manual | Full re-extraction of all mergers |
