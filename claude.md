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

## Project Structure

```
merger-tracker/frontend/src/
├── main.jsx              # React root
├── App.jsx               # Router + layout (Navbar, Footer)
├── config.js             # API endpoint constants
├── pages/                # Route components (Dashboard, Mergers, MergerDetail, Timeline, Industries, Commentary)
├── components/           # Reusable UI (Navbar, StatusBadge, StatCard, SEO, ErrorBoundary, etc.)
├── context/              # TrackingContext — global merger tracking state via localStorage
├── utils/                # dates.js, dataCache.js, lastVisit.js
└── data/                 # ACT public holidays JSON

scripts/
├── scrape.sh             # Bash wrapper using pup to scrape ACCC register
├── extract_mergers.py    # Parse HTML → merger data JSON
├── generate_static_data.py  # Generate all frontend JSON files
├── parse_determination.py   # Extract text from determination PDFs
├── parse_questionnaire.py   # Process questionnaire documents
├── normalization.py      # Data cleaning utilities
└── cutoff.py             # Skip old mergers logic

data/
├── raw/                  # Scraped HTML files and PDFs
└── processed/            # Intermediate JSON (mergers.json, commentary.json)
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
pip install -r requirements.txt
./scripts/scrape.sh
python scripts/extract_mergers.py
python scripts/generate_static_data.py
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
