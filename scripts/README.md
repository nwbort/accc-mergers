# Scripts

Python and Bash entry points for the data pipeline. `scripts/` is a Python
package: modules are grouped into sub-packages by the verb in their name
(`scrape/`, `parse/`, `detect/`, `generate/`), and the shared library modules
(`merger_filters.py`, `date_utils.py`, etc.) stay at the top level where every
stage can reach them.

## Running a script

Entry points are run as modules from the repository root, not by file path:

```bash
python -m scripts.extract_mergers            # not: python scripts/extract_mergers.py
python -m scripts.generate.generate_static_data
```

Modules import each other absolutely (`from scripts.slug import slugify`), so
the repository root has to be on `sys.path`. `python -m` puts it there; a path
invocation puts the script's own directory there instead and the imports fail.
The two Bash entry points export `PYTHONPATH` themselves, so they can be run
from anywhere.

## Pipeline stages

```
scrape/scrape.sh ──► extract_mergers.py ──► generate/generate_static_data.py ──► frontend
                                         └─► generate/generate_weekly_digest.py
                                         └─► generate/generate_rss_feed.py
                                         └─► generate/generate_sitemap.py
                                         └─► generate/generate_similar_mergers.py
                                         └─► generate/generate-cli-data.sh
```

### `scrape/` — fetching

| File | Purpose |
| --- | --- |
| `scrape/scrape.sh` | Bash wrapper using `pup`/`curl` to fetch the ACCC acquisitions register and individual matter pages into `data/raw/`. |
| `scrape/scrape_targets.py` | Chooses which matter pages `scrape.sh` fetches: applies `cutoff.py`, de-duplicates the listing, and recovers matters the register listing dropped (its pagination sort is unstable). |
| `scrape/scrape_summary.py` | Renders the Markdown run summary for a scrape (merger IDs fetched, which pages changed, what was skipped past cutoff) from the report `scrape.sh` writes when `SCRAPE_REPORT_DIR` is set. |
| `scrape/scrape_tribunal.py` | Scrapes Australian Competition Tribunal matter pages into `tribunal_appeals.json`, driving a real Chrome via nodriver to get past the site's Cloudflare challenge. |

### `parse/` — reading the documents

| File | Purpose |
| --- | --- |
| `parse/parse_determination.py` | Extract structured info (decision, division, tables) from determination PDFs. |
| `parse/parse_nocc.py` | Extract structured sections (numbered paragraphs, headings, bullets) from Notice of Competition Concerns summary PDFs. |
| `parse/parse_phase2_notice.py` | Extract the referral details from a Phase 2 Notice PDF, with an OCR fallback for scanned notices. |
| `parse/parse_questionnaire.py` | Extract consultation deadlines and questions from questionnaire PDFs. |
| `parse/determination_text.py` | Flattens determination text for the CLI bundle. |

### `detect/` — cross-merger analysis

| File | Purpose |
| --- | --- |
| `detect/detect_duplicates.py` | Reports duplicate event entries within a merger record. Run by the `detect-duplicates.yml` workflow and imported by the resolver tool. |
| `detect/detect_related_mergers.py` | Suggests new `WA-*` → `MN-*` pairs that aren't yet in `related_mergers.json`. |
| `detect/detect_related_parties.py` | Suggests party groupings for `related_parties.json`. |
| `detect/related_parties_batch.py` | Batch-review CLI over those suggestions. |
| `detect/party_matching.py` | Shared party name/identifier matching used by the detectors and the static-data outputs. |

### `generate/` — writing the published outputs

| File | Purpose |
| --- | --- |
| `generate/generate_static_data.py` | Thin orchestrator — emits all per-merger / list / stats JSON for the frontend. Heavy lifting lives in `generate/static_data/`. |
| `generate/generate_weekly_digest.py` | Weekly summary of new, cleared, phase-2, and declined deals. |
| `generate/generate_similar_mergers.py` | Per-merger suggestions of related mergers (party + ANZSIC overlap). |
| `generate/generate_rss_feed.py` | Atom feed of recent merger events. |
| `generate/generate_sitemap.py` | `sitemap.xml` for search-engine crawlers. |
| `generate/generate-cli-data.sh` | Bundles processed data for the `accc-mergers-cli` consumer. |
| `generate/build_cli_sqlite.py` | Builds the SQLite database the CLI ships. |

### Top level — extraction, shared helpers, maintenance

| File | Purpose |
| --- | --- |
| `extract_mergers.py` | Parse `data/raw/` HTML and supporting PDFs into `data/processed/mergers.json`. |
| `enrich_pdfs.py` | Second extraction phase — the PDF parsing `extract_mergers.py --skip-pdf-enrich` defers. |
| `cutoff.py` | Determines which mergers are old enough to skip during scraping/extraction. Used as a module *and* as a CLI. |
| `normalization.py` | Shared string/value normalisation (e.g. determination labels). |
| `date_utils.py` | Date parsing helpers shared across the pipeline. |
| `merger_filters.py` | Canonical predicates and loaders over `mergers.json` (single source of truth for "active", "waiver", etc.). |
| `slug.py` | URL slugs for mergers, parties and industries. Pinned to `slug-cases.json`. |
| `paths.py` | `REPO_ROOT` / `SCRIPTS_DIR` anchors, so no module has to know how deep it sits. |
| `compress_pdfs.py` | Shrinks oversized PDFs so Cloudflare Pages will deploy them. |
| `check_deploy_assets.py` | Safety net: reports files still over the Pages asset limit. |
| `check_phase2_notice_ocr_needed.py` | Tells the extract workflow whether it needs to install Tesseract. |
| `fix_missing_notification_dates.py` | Suggests default notification dates for records missing one. |
| `unfreeze_mergers.py` | Clears frozen event data so a merger is re-parsed from scratch. |
| `send_weekly_email.py` | Renders and sends the weekly digest via Resend. |
| `build.sh` | Cloudflare Pages build entry point (`bash scripts/build.sh`). |

## Subdirectories

- [`tools/`](tools/) — Interactive admin web UIs (`resolver.py`,
  `commentary.py`). Not part of the automated pipeline; run by hand to
  edit the processed JSON.
- [`tests/`](tests/) — Pytest suite covering the pipeline,
  duplicate-detection, filters, and static-data generators.
- `constants/` — Canonical string constants (e.g. merger status
  values).
- `generate/static_data/` — Building blocks for `generate_static_data.py`
  (loaders, filters, enrichment, per-merger estimators, individual output
  writers). Two estimators attach derived fields to every merger:
  `phase1_estimate.py` (`phase_1_estimate`, frozen at filing time) and
  `prenotification.py` (`pre_notification`, recomputed each run — how long a
  notification sat in pre-notification, read off the ACCC's merger ID counter,
  as a proven floor, a best estimate and a generous ceiling, each in days and
  as the date pre-notification started).

## Requirements

- `requirements.txt` — base pipeline dependencies.
- `requirements-tribunal.txt` — extras for `scrape/scrape_tribunal.py`.

## Running the pipeline locally

```bash
pip install -r scripts/requirements.txt
./scripts/scrape/scrape.sh                          # → data/raw/
python -m scripts.extract_mergers                   # → data/processed/mergers.json
python -m scripts.generate.generate_static_data     # → frontend public/data/
python -m pytest scripts/tests/                     # tests
```

To see which merger IDs a scrape touched — the same summary the pipeline
writes to its GitHub Actions run summary — point the scraper at a report
directory:

```bash
SCRAPE_REPORT_DIR=/tmp/scrape-report ./scripts/scrape/scrape.sh
git status --porcelain -- data/raw/matters/ | awk '{print $NF}' > /tmp/changed.txt
python -m scripts.scrape.scrape_summary --report-dir /tmp/scrape-report \
  --changed-paths /tmp/changed.txt
```
