# Scripts

Python and Bash entry points for the data pipeline. Library modules
(`merger_filters.py`, `date_utils.py`, etc.) sit alongside the runnable
scripts; subdirectories group related code by role.

## Pipeline stages

```
scrape.sh ──► extract_mergers.py ──► generate_static_data.py ──► frontend
                                  └─► generate_weekly_digest.py
                                  └─► generate_rss_feed.py
                                  └─► generate_sitemap.py
                                  └─► generate_similar_mergers.py
                                  └─► embed.py
                                  └─► generate-cli-data.sh
```

### Scrape

| File | Purpose |
| --- | --- |
| `scrape.sh` | Bash wrapper using `pup`/`curl` to fetch the ACCC acquisitions register and individual matter pages into `data/raw/`. |
| `cutoff.py` | Determines which mergers are old enough to skip during scraping/extraction. Used as a module *and* as a CLI by `scrape.sh`. |

### Extract

| File | Purpose |
| --- | --- |
| `extract_mergers.py` | Parse `data/raw/` HTML and supporting PDFs into `data/processed/mergers.json`. |
| `parse_determination.py` | Extract structured info (decision, division, tables) from determination PDFs. |
| `parse_nocc.py` | Extract structured sections (numbered paragraphs, headings, bullets) from Notice of Competition Concerns summary PDFs. |
| `parse_questionnaire.py` | Extract consultation deadlines and questions from questionnaire PDFs. |
| `normalization.py` | Shared string/value normalisation (e.g. determination labels). |
| `date_utils.py` | Date parsing helpers shared across the pipeline. |
| `merger_filters.py` | Canonical predicates and loaders over `mergers.json` (single source of truth for "active", "waiver", etc.). |

### Generate

| File | Purpose |
| --- | --- |
| `generate_static_data.py` | Thin orchestrator — emits all per-merger / list / stats JSON for the frontend. Heavy lifting lives in `static_data/`. |
| `generate_weekly_digest.py` | Weekly summary of new, cleared, phase-2, and declined deals. |
| `generate_similar_mergers.py` | Per-merger suggestions of related mergers (party + ANZSIC overlap). |
| `generate_rss_feed.py` | Atom feed of recent merger events. |
| `generate_sitemap.py` | `sitemap.xml` for search-engine crawlers. |
| `embed.py` | Sentence-Transformer embeddings used by the frontend semantic search. |
| `generate-cli-data.sh` | Bundles processed data for the `accc-mergers-cli` consumer. |
| `send_weekly_email.py` | Renders and sends the weekly digest via Resend. |
| `build.sh` | Cloudflare Pages build entry point (`bash scripts/build.sh`). |

### CI checks

| File | Purpose |
| --- | --- |
| `detect_duplicates.py` | Reports duplicate event entries within a merger record. Run by the `detect-duplicates.yml` workflow and imported by the resolver tool. |
| `detect_related_mergers.py` | Suggests new `WA-*` → `MN-*` pairs that aren't yet in `related_mergers.json`. |

## Subdirectories

- [`tools/`](tools/) — Interactive admin web UIs (`resolver.py`,
  `commentary.py`). Not part of the automated pipeline; run by hand to
  edit the processed JSON.
- [`tests/`](tests/) — Pytest suite covering the pipeline,
  duplicate-detection, filters, and static-data generators.
- `constants/` — Canonical string constants (e.g. merger status
  values).
- `static_data/` — Building blocks for `generate_static_data.py`
  (loaders, filters, enrichment, individual output writers).

## Requirements

- `requirements.txt` — base pipeline dependencies.
- `requirements-embed.txt` — extra deps for `embed.py` (heavy ML
  packages, kept separate so most workflows skip them).

## Running the pipeline locally

```bash
pip install -r scripts/requirements.txt
./scripts/scrape.sh                       # → data/raw/
python scripts/extract_mergers.py         # → data/processed/mergers.json
python scripts/generate_static_data.py    # → frontend public/data/
python -m pytest scripts/tests/           # tests
```
