# ACCC Merger Tracker — Code Walkthrough

*2026-05-07T23:21:00Z by Showboat 0.6.1*
<!-- showboat-id: 28b53f60-5a04-4536-b663-0db1225cedb4 -->

## Overview

This codebase is a fully static web application that tracks and publishes ACCC merger review data. There is no backend server. Instead, a scheduled GitHub Actions pipeline scrapes the ACCC website, parses the HTML, and generates pre-built JSON files that a React SPA reads directly. Cloudflare Pages hosts the frontend and serves those JSON files as a pseudo-API.

The three major layers are:

1. **Data pipeline** — Bash + Python scripts in `scripts/` that scrape, parse, and generate JSON
2. **Frontend** — React 19 SPA in `merger-tracker/frontend/src/` that reads the JSON and renders the UI
3. **Automation** — GitHub Actions workflows in `.github/workflows/` that schedule and orchestrate the pipeline

## The Data Pipeline

### Step 1 — Scraping (`scripts/scrape.sh`)

The scraper is a Bash script that fetches every merger page from the ACCC public register. It is the first stage in a three-step pipeline: **scrape → extract → generate**.

The scraper's job is purely about fetching and storing raw HTML. All interpretation is left to the Python extraction step.

**Key design decisions:**

- Uses `pup` (a command-line HTML parser written in Go) to extract links from the register index page — no Python parsing needed at this stage.
- Fetches 24 pages in parallel using `xargs -P 24` to keep the scrape fast.
- After downloading each matter page it immediately runs `clean_file()`, a single-pass Perl rewrite that strips out dynamic tokens (cache-busted asset URLs, random DOM IDs, analytics snippets) so that git diffs only contain meaningful content changes.
- Reads `data/processed/mergers.json` (output of the previous run) and calls `cutoff.py` to get a list of URL paths that should be skipped — approved mergers more than 3 weeks old no longer need re-scraping.
- Saves each page as `data/raw/matters/{MATTER_NUMBER}.html`, where the matter number (e.g. `MN-12345` or `WA-67890`) is extracted via `pup` from the page itself.

```bash
sed -n '46,53p' scripts/scrape.sh
```

```output
# Export variables so they are available to subshells spawned by xargs.
export BASE_URL="https://www.accc.gov.au"
export REGISTER_URL="${BASE_URL}/public-registers/mergers-and-acquisitions-registers/acquisitions-register?init=1&items_per_page=50"
export MAIN_PAGE_FILE="data/raw/acquisitions-register.html"
export SUBFOLDER="data/raw/matters"
export USER_AGENT="Mozilla/5.0 (compatible; mergers-fyi/1.0; +https://mergers.fyi)"
export MERGERS_JSON="data/processed/mergers.json"
export SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
```

Variables are exported (not just set) because the parallel `xargs` workers each run in a child subshell that would not otherwise inherit them. `PARALLEL_JOBS=24` drives both the matter-page fetches and the register pagination fetches.

The `clean_file` function is the most important detail of the scraper. Without it every run would produce huge, noisy git diffs full of auto-generated asset fingerprints that have nothing to do with the actual merger data.

```bash
sed -n '67,86p' scripts/scrape.sh
```

```output
  perl -i -0777 -pe '
    s/js-view-dom-id-[a-f0-9]{64}/js-view-dom-id-STATIC/g;
    s/(id="edit-submit-accc-search-site--)[^"\n]+"/${1}STATIC"/g;
    s/(css\/css_)[^.\n]+\.css/${1}STATIC.css/g;
    s/(js\/js_)[^.\n]+\.js/${1}STATIC.js/g;
    s/("libraries":")[^"\n]+"/${1}STATIC_LIBRARIES"/g;
    s/("permissionsHash":")[^"\n]+"/${1}STATIC_HASH"/g;
    s/("view_dom_id":")[a-f0-9]{64}/${1}STATIC"/g;
    s/(views_dom_id:)[a-f0-9]{64}/${1}STATIC/g;
    s/include=[^"&>\n]+/include=STATIC/g;
    s/href="https:\/\/app\.readspeaker\.com\/[^"\n]+"/href="STATIC_READSPEAKER_URL"/g;
    s/(icons\.svg\?t)[^#\n]+#/${1}STATIC#/g;
    s/(\?t)[^">\n]+/${1}STATIC/g;
    s/("css_js_query_string":")[^"\n]+"/${1}STATIC"/g;
    s/[ \t]*\n[ \t]*<script>!function\(e\)\{var n="https:\/\/s\.go-mpulse\.net\/boomerang\/".*?\(window\);<\/script><\/head>/\n  <\/head>/s;
    s{(<meta name="dcterms\.modified"[^\n]*/>\n)(<meta name="dcterms\.created"[^\n]*/>\n)}{$2$1}g;
    s{(<link rel="canonical"[^\n]*/>\n)(<link rel="shortlink"[^\n]*/>\n)}{$2$1}g;
    s#(<a[^>]*class="[^"]*megamenu-page-link-level-3[^"]*"[^>]*href=")[^"]*("[^>]*>[[:space:]]*<span>)[^<]*(</span>)#${1}STATIC_HREF${2}STATIC_TEXT${3}#g;
    s/\n{3,}/\n\n/g;
  ' "$file"
```

The `-0777` flag puts Perl into "slurp mode" — the entire file is read as a single string — which allows the BOOMR analytics script pattern to match across multiple lines. Without it, multi-line patterns would silently fail while single-line patterns would still work. Each substitution targets a specific source of noise: fingerprinted CSS/JS filenames, 64-character DOM IDs, Readspeaker analytics URLs, and so on.

The cutoff filter runs before fetching to save bandwidth. `cutoff.py` reads the previous run's `mergers.json` and outputs the URL paths of any merger that was approved more than 3 weeks ago (or for waivers — any that received a determination more than 3 weeks ago). Those paths are passed to `grep -vxFf` to remove them from the link list before `xargs` starts fetching.

```bash
sed -n '254,268p' scripts/scrape.sh
```

```output

  if [ -f "$MERGERS_JSON" ]; then
    python3 "$SCRIPT_DIR/cutoff.py" --paths "$MERGERS_JSON" > "$skip_paths_file" 2>/dev/null || true
  fi

  skip_count=$(wc -l < "$skip_paths_file" | tr -d ' ')
  if [ "$skip_count" -gt 0 ]; then
    echo "Skipping $skip_count merger(s) past cutoff date (use --all to scrape all)"

    # Filter out links that exactly match a skip path. Single grep call vs.
    # spawning one per link.
    links_to_fetch=$(grep -vxFf "$skip_paths_file" <<< "$relative_links" || true)
  else
    links_to_fetch="$relative_links"
  fi
```

### Step 2 — Extraction (`scripts/extract_mergers.py`)

The extractor reads every HTML file in `data/raw/matters/`, parses it with BeautifulSoup, and writes a consolidated `data/processed/mergers.json`. It runs in parallel using `ProcessPoolExecutor` — each worker handles one HTML file independently.

The top-level `main()` function drives the flow in 11 numbered steps:

1. Load existing `mergers.json` into a dict keyed by merger ID (for incremental updates)
2. Determine which merger IDs to skip (cutoff logic)
3. Load frozen-events config and field overrides from `data/frozen_events_mergers.json`
4. Enumerate all `.html` files in `data/raw/matters/`
5. Dispatch `parse_merger_file()` for each file via `ProcessPoolExecutor`
6. Collect results, filtering out `None` (failed parses)
7. Re-append skipped mergers from the previous run (so they are not lost)
8. Enrich with questionnaire data, NOCC summaries, and auto-fix missing dates
9. Mark each merger as a waiver or notification
10. Sort by merger ID for stable diffs
11. Write to `data/processed/mergers.json`

```bash
sed -n '976,999p' scripts/extract_mergers.py
```

```output
    # 5. Use a ProcessPoolExecutor to run parsing in parallel
    with ProcessPoolExecutor() as executor:
        # Create a list of arguments for parse_merger_file
        tasks = []
        for fp in filepaths:
            merger_id = get_merger_id_from_file(fp)
            if merger_id:
                # Skip mergers past cutoff unless --all is specified
                if merger_id in skipped_merger_ids:
                    continue
                tasks.append((fp, existing_mergers.get(merger_id), frozen_events_mergers, field_overrides))
                processed_merger_ids.add(merger_id)
            else:
                print(f"Warning: Could not extract merger_id from {fp}", file=sys.stderr)

        # Most tasks are now fast (cached determination data, no PDF re-parse),
        # so per-task IPC dominates with the default chunksize=1. Send tasks
        # in small batches to amortise IPC across each worker.
        worker_count = executor._max_workers or 1
        chunksize = max(1, len(tasks) // (worker_count * 4))
        results = executor.map(run_parse_merger_file, tasks, chunksize=chunksize)

        # 6. Collect valid results, filtering out any None values from failed parses
        all_mergers_data = [data for data in results if data is not None]
```

The merger ID is pre-extracted with a regex (`get_merger_id_from_file`) before dispatching to the pool so the cutoff check can run in the main process without parsing the full HTML twice. The chunksize formula avoids the default of 1 task per IPC round-trip — batching tasks across workers amortises the overhead of pickling/unpickling each result, which matters when most files haven't changed and parse quickly.

#### `parse_merger_file()` — parsing a single HTML file

Each worker calls this function. It uses seven private helpers, each responsible for one logical slice of the page:

```bash
sed -n '639,666p' scripts/extract_mergers.py
```

```output
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            html_content = f.read()

        soup = BeautifulSoup(html_content, 'lxml')

        merger_data = _extract_basic_info(soup)
        merger_id = merger_data['merger_id']

        merger_data.update(_extract_dates_and_status(soup, merger_id, existing_merger_data))
        merger_data.update(_extract_consultation_date(soup, existing_merger_data))
        merger_data.update(_extract_parties(soup))
        merger_data['anzsic_codes'] = _extract_anzsic_codes(soup)

        description = _extract_description(soup)
        if description:
            merger_data['merger_description'] = description

        scraped_events = _scrape_events(soup, merger_id, existing_merger_data)
        merger_data['events'] = _merge_events(
            scraped_events, existing_merger_data, merger_id, frozen_events_mergers
        )
        _add_synthetic_events(merger_data)

        if field_overrides and merger_id in field_overrides:
            merger_data.update(field_overrides[merger_id])

        return merger_data
```

Several helpers preserve data from the previous run when a field is absent from the current HTML — `_extract_dates_and_status` keeps `end_of_determination_period` this way, and `_extract_consultation_date` keeps `consultation_response_due_date`. The ACCC frequently removes these fields from the page once the relevant deadline has passed, so without preservation they would silently disappear from the data.

Field overrides (`frozen_events_mergers.json`) are applied last, after all scraping, so they can always win over whatever the page says.

#### Events: scraping, merging, and synthetic events

Events are the most complex part of the extraction. There are three functions involved:

- **`_scrape_events`** — reads the attachment tables on the page to produce a fresh list of events, downloading any new PDF/DOCX attachments as a side-effect. Determination PDFs are parsed immediately (via `parse_determination_pdf`) to extract the commission division and decision table.
- **`_merge_events`** — reconciles the freshly-scraped events with the existing events from the previous run. Events are matched by attachment URL where possible, falling back to title. Events that disappear from the page get `status: removed` rather than being silently deleted. Frozen mergers have their existing events preserved and only genuinely new ones appended.
- **`_add_synthetic_events`** — appends two synthetic entries not present as documents on the page: a "Merger notified to ACCC" event (from `effective_notification_datetime`) and a phase determination event (from `determination_publication_date` + `accc_determination`). These make the timeline complete for the frontend without requiring separate scraping.

```bash
sed -n '555,620p' scripts/extract_mergers.py
```

```output
def _add_synthetic_events(merger_data):
    """Add notification and determination synthetic events if not already present."""
    events = merger_data['events']

    # Notification event
    if merger_data.get('effective_notification_datetime'):
        notification_title = 'Merger notified to ACCC'
        if not any(e['title'] == notification_title for e in events):
            events.append({
                'date': merger_data['effective_notification_datetime'],
                'title': notification_title,
                'display_title': notification_title,
            })

    # Determination event
    if not merger_data.get('determination_publication_date'):
        return

    determination = merger_data.get('accc_determination', 'Decision made')
    phase = merger_data.get('stage', 'Phase 1')
    determination_title = f"{phase} determination: {determination}"
    det_date = merger_data['determination_publication_date']

    # Remove old format determination events to avoid duplicates
    merger_data['events'] = [
        e for e in events
        if not (e['title'].startswith('Determination published:') and e['date'] == det_date)
    ]
    events = merger_data['events']

    # Look for an existing determination document event on the same date (or
    # ±1 day to handle cases where the ACCC publication date field and the
    # events table date differ by one day, e.g. MN-01090).
    # Also check the URL in case the event title is just the parties' names
    # while the attached PDF filename contains "determination".
    existing_det_event = next(
        (e for e in events
         if _dates_within_one_day(e.get('date'), det_date)
         and ('determination' in e.get('title', '').lower()
              or 'determination' in e.get('url', '').lower())
         and e.get('url')),
        None
    )

    if existing_det_event:
        existing_det_event['display_title'] = determination_title
        existing_det_event['is_determination_event'] = True
        if 'phase' not in existing_det_event:
            if 'waiver' in phase.lower():
                existing_det_event['phase'] = 'Waiver'
            else:
                existing_det_event['phase'] = phase.split(' - ')[0] if ' - ' in phase else phase
        # Remove any redundant plain-text status row with the same title that
        # the ACCC sometimes publishes alongside the document row.
        merger_data['events'] = [
            e for e in merger_data['events']
            if not (e['title'] == determination_title and not e.get('url'))
        ]
    else:
        if not any(e['title'] == determination_title for e in events):
            events.append({
                'date': det_date,
                'title': determination_title,
                'display_title': determination_title,
                'is_determination_event': True,
            })
```

The ±1 day tolerance in `_dates_within_one_day` is a real-world edge case: the ACCC's "determination publication date" field sometimes differs by a day from the date shown on the actual events table row (e.g. MN-01090). Without this tolerance a duplicate synthetic determination event would be created alongside the document event, resulting in two entries on the frontend timeline.

#### The cutoff module (`scripts/cutoff.py`)

Both `scrape.sh` and `extract_mergers.py` use this module to decide which mergers still need active attention. The rules are:

- **Waivers** (merger ID starts with `WA-` or stage contains "Waiver"): skip 3 weeks after *any* determination, regardless of outcome.
- **Notifications** (merger ID starts with `MN-`): skip 3 weeks after an *Approved* determination only. Declined or contested mergers remain in scope indefinitely.

```bash
sed -n '31,54p' scripts/cutoff.py
```

```output
def get_cutoff_date(merger: dict, cutoff_weeks: int = CUTOFF_WEEKS) -> datetime:
    """
    Get the cutoff date for a merger (date after which it should no longer be scraped).

    Returns None if the merger should still be actively processed.
    Returns a datetime if the merger has a cutoff date.
    """
    determination_date = parse_iso_datetime(merger.get('determination_publication_date'))

    if determination_date is None:
        # No determination yet, keep processing
        return None

    # For waivers: cut off after any determination (approved or denied)
    if is_waiver_merger(merger):
        return determination_date + timedelta(weeks=cutoff_weeks)

    # For regular notifications: only cut off if approved
    determination = merger.get('accc_determination', '')
    if determination == merger_status.APPROVED:
        return determination_date + timedelta(weeks=cutoff_weeks)

    # Not approved or no determination - keep processing
    return None
```

### Step 3 — Static data generation (`scripts/generate_static_data.py`)

Once `mergers.json` is written, `generate_static_data.py` turns it into all the individual JSON files the frontend reads. This script is a thin orchestrator: it loads source data, calls `enrich_merger()` once per merger, then delegates to specialised output generators in the `static_data/outputs/` package.

The enrichment step adds computed fields that would be expensive to recalculate on every frontend request:

- Phase-specific determination outcomes (`phase_1_determination`, `phase_2_determination`, `public_benefits_determination`)
- The expected competition concerns notice date for Phase 2 mergers (business day 25 of the Phase 2 window)
- Flags for whether questionnaire and NOCC data are available (`has_questionnaire`, `has_nocc`)
- Per-event `phase` labels extracted from event titles

Enriched mergers are then linked to related mergers (waiver-to-notification pairs) and semantically similar mergers (from a pre-computed embedding similarity file).

```bash
sed -n '112,152p' scripts/generate_static_data.py
```

```output
    # Small single-file outputs: call generator → write result
    single_file_outputs = [
        ("stats.json", stats.generate(enriched)),
        ("industries.json", industries.generate_index(enriched)),
        ("upcoming-events.json", upcoming_events.generate(enriched)),
        ("commentary.json", commentary_out.generate(enriched, commentary)),
        ("analysis.json", analysis.generate(enriched)),
    ]
    for filename, payload in single_file_outputs:
        out_path = OUTPUT_DIR / filename
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(payload, f, indent=2)
        print(f"✓ Generated {out_path}")

    print("\nGenerating individual merger files...")
    n = individual.generate(enriched, OUTPUT_DIR)
    print(f"✓ Generated {n} individual merger files in {OUTPUT_DIR / 'mergers'}")

    print("\nGenerating paginated list files...")
    pages = list_out.generate(enriched, OUTPUT_DIR, page_size=50)
    print(f"✓ Generated {pages} paginated list files (50 mergers/page)")

    print("\nGenerating paginated timeline files...")
    pages = timeline.generate(enriched, OUTPUT_DIR, page_size=100)
    print(f"✓ Generated {pages} paginated timeline files (100 events/page)")

    print("\nGenerating individual industry files...")
    n = industries.generate_detail_files(enriched, OUTPUT_DIR)
    print(f"✓ Generated {n} individual industry files in {OUTPUT_DIR / 'industries'}")

    if questionnaire_data:
        print("\nGenerating questionnaire files...")
        q_count = questionnaires.generate(questionnaire_data, OUTPUT_DIR)
        print(f"✓ Generated {q_count} questionnaire files in {OUTPUT_DIR / 'questionnaires'}")

    if nocc_data:
        print("\nGenerating NOCC files...")
        n_count = noccs.generate(nocc_data, OUTPUT_DIR)
        print(f"✓ Generated {n_count} NOCC files in {OUTPUT_DIR / 'noccs'}")

    print("\nDone!")
```

The output files are written directly into `merger-tracker/frontend/public/data/`, which is the Vite project's static assets folder. Because these files are committed to git, Cloudflare Pages picks them up on every push and serves them without any build step or server-side rendering.

Large collections (mergers, timeline events) are paginated: 50 mergers per list page, 100 events per timeline page. This keeps initial page loads fast — the frontend only fetches the first page and loads more on demand.

Individual merger files (`mergers/{id}.json`) are written separately from the paginated list files. The list pages contain lightweight records (no events, no description) for the searchable list view; individual files contain the full detail including events, parties, and documents.

## The Frontend

### App structure (`src/main.jsx` and `src/App.jsx`)

The entry point (`main.jsx`) mounts the React root in strict mode. `App.jsx` wraps everything in four providers before the route tree is rendered:

1. **`HelmetProvider`** — manages `<head>` tags (title, meta, Open Graph) via the `SEO` component on each page
2. **`BrowserRouter`** — React Router's history-based router
3. **`TrackingProvider`** — global merger-tracking state (described below)
4. **`ErrorBoundary`** — catches render errors and shows a fallback UI instead of a blank screen

The keyboard shortcut system lives inside `AppContent` (the inner component) rather than at the provider level so it can reference React Router's navigation context.

```bash
sed -n '36,50p' merger-tracker/frontend/src/App.jsx
```

```output
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/mergers" element={<Mergers />} />
            <Route path="/mergers/:id" element={<MergerDetail />} />
            <Route path="/timeline" element={<Timeline />} />
            <Route path="/industries" element={<Industries />} />
            <Route path="/industries/:code" element={<IndustryDetail />} />
            <Route path="/commentary" element={<Commentary />} />
            <Route path="/digest" element={<Digest />} />
            <Route path="/analysis" element={<Analysis />} />
            <Route path="/nick-twort" element={<NickTwort />} />
            <Route path="/privacy" element={<PrivacyPolicy />} />
            <Route path="/feedback" element={<Feedback />} />
            <Route path="*" element={<NotFound />} />
          </Routes>
```

### Data fetching (`src/hooks/useFetchData.js` + `src/utils/dataCache.js`)

Every page that needs JSON uses the `useFetchData` hook. It provides three things that plain `fetch` does not:

1. **Module-level in-memory cache** — `dataCache` is a `Map` stored at module scope, so it survives route changes. When the user switches from the Dashboard to the Mergers list and back, stats data is returned synchronously from the cache without a network round-trip or a loading spinner. The cache has no TTL — it lives for the session.

2. **Abort on unmount** — an `AbortController` is created per fetch. The cleanup function returned from `useEffect` calls `controller.abort()`, so responses that arrive after a component unmounts are discarded rather than touching state on a dead component.

3. **SPA 404 detection** — Cloudflare Pages serves `index.html` for any unknown path (to support client-side routing). That means a missing `.json` file returns HTTP 200 with HTML, which `JSON.parse` rejects with a `SyntaxError`. The hook catches this and converts it to an HTTP 404 error so callers can distinguish "file missing" from real network errors.

```bash
sed -n '25,35p' merger-tracker/frontend/src/utils/dataCache.js
```

```output
  },
};
```

```bash
cat merger-tracker/frontend/src/utils/dataCache.js
```

```output
// Simple in-memory data cache to prevent reload flicker when switching tabs
// Data persists across route changes since this is a module-level cache

const cache = new Map();

export const dataCache = {
  get(key) {
    return cache.get(key);
  },

  set(key, data) {
    cache.set(key, data);
  },

  has(key) {
    return cache.has(key);
  },

  clear(key) {
    if (key) {
      cache.delete(key);
    } else {
      cache.clear();
    }
  },
};
```

### API endpoints (`src/config.js`)

All JSON file paths are defined in one place. Each endpoint is either a static string (e.g. `/data/stats.json`) or a function that produces a path from an ID (e.g. `mergerDetail(id) => `/data/mergers/${id}.json``). This means a change to the file naming convention only needs to happen in `config.js`.

```bash
cat merger-tracker/frontend/src/config.js
```

```output
// API configuration for static JSON files
// These files are generated by generate_static_data.py and served from /data/

// Cloudflare Worker endpoints — both served from signup.mergers.fyi
export const SUBSCRIBE_ENDPOINT = "https://signup.mergers.fyi";
export const FEEDBACK_ENDPOINT = "https://signup.mergers.fyi/feedback";

// Cloudflare Turnstile site key (public — safe to commit).
// 1. Go to Cloudflare Dashboard > Turnstile > Add site
// 2. Paste the Site Key here.
// 3. Add the Secret Key to your Worker: wrangler secret put TURNSTILE_SECRET_KEY
export const TURNSTILE_SITE_KEY = "0x4AAAAAACg1KC_xTS0WAPpu";

export const API_ENDPOINTS = {
  mergersListPage: (page) => `/data/mergers/list-page-${page}.json`,  // Paginated merger list
  mergersListMeta: '/data/mergers/list-meta.json',  // Pagination metadata for mergers list
  mergerDetail: (id) => `/data/mergers/${id}.json`,  // Individual merger file
  stats: '/data/stats.json',
  timelinePage: (page) => `/data/timeline-page-${page}.json`,  // Paginated timeline
  timelineMeta: '/data/timeline-meta.json',  // Pagination metadata for timeline
  industries: '/data/industries.json',
  industryDetail: (code) => `/data/industries/${code}.json`,  // Individual industry file with mergers
  upcomingEvents: '/data/upcoming-events.json',
  commentary: '/data/commentary.json',  // Mergers with user commentary
  digest: '/data/digest.json',  // Weekly digest of merger activity
  analysis: '/data/analysis.json',  // Pre-computed analysis data
  questionnaire: (id) => `/data/questionnaires/${id}.json`,  // Questionnaire data (lazy-loaded)
};
```

### Global state — merger tracking (`src/context/TrackingContext.jsx`)

Users can "track" individual mergers to receive notifications when new events or upcoming deadlines appear. All tracking state is managed in `TrackingContext`, which wraps the entire app.

**What it stores (all persisted to `localStorage`):**

- `trackedMergerIds` — array of merger IDs the user is watching
- `seenEventKeys` — Set of event keys (derived from `merger_id + date + title`) that the user has already seen in the notification panel

**How events are fetched:**

When `trackedMergerIds` changes, the context fetches individual merger detail files in parallel (one `fetch` per tracked merger). This is deliberately more targeted than fetching the full timeline — it avoids downloading hundreds of events for mergers the user doesn't care about.

The context then synthesises upcoming events directly from the individual merger data for tracked mergers. This matters because `upcoming-events.json` only contains events within a 60-day window — Phase 2 mergers whose determination deadline is months away would otherwise be invisible in the notification panel.

**Seen event deduplication:**

Events are identified by a stable key: `${merger_id}_${date}_${display_title}`. When a merger is first tracked, all its current events are immediately marked as seen (via `newlyTrackedIds`), so only events that appear *after* tracking began show as new.

```bash
sed -n '12,17p' merger-tracker/frontend/src/context/TrackingContext.jsx
```

```output
// Use a consistent order and normalize the title field for stability
const getEventKey = (event) => {
  // Normalize title: prefer display_title, then title, then event_type_display, finally type
  const title = event.display_title || event.title || event.event_type_display || event.type || '';
  return `${event.merger_id}_${event.date}_${title}`;
};
```

The title normalisation cascade (`display_title → title → event_type_display → type`) is necessary because events from different sources use different field names. Timeline events from the individual merger files use `title`/`display_title`; upcoming events from `upcoming-events.json` use `event_type_display`. Using a consistent preference order ensures the key is stable across sources, so the same real-world event generates the same key regardless of which JSON file it came from.

## GitHub Actions Automation

### The pipeline workflow (`.github/workflows/pipeline.yml`)

The pipeline runs on four triggers:

- **Schedule** — four times a day on weekdays at 7:08, 11:08, 15:08, 19:08 AEST; once on Sundays at 7:08 AEST
- **Push to main** — immediately after any commit (so manual data fixes are picked up without waiting for the next schedule)
- **`repository_dispatch`** — fired by the scraper workflow when a new merger is detected (near-real-time updates)
- **`workflow_dispatch`** — manual trigger, with an `all_mergers` boolean to force a full re-extraction

The pipeline runs as a single job with no parallelism — the steps are inherently sequential (scrape → extract → generate). An important detail: extraction can run *twice* in one pipeline run. If the scraper downloads any DOCX files (the ACCC sometimes publishes documents in Word format), LibreOffice converts them to PDF and then extraction runs again to pick up the questionnaire data that was just unlocked.

```bash
sed -n '110,132p' .github/workflows/pipeline.yml
```

```output
        id: scrape-changes
        run: |
          git add -A
          if git diff --staged --quiet; then
            echo "changed=false" >> $GITHUB_OUTPUT
          else
            # acquisitions-register.html alone isn't worth committing: any meaningful
            # change (new merger, status update) is also reflected in individual matter
            # pages. Unstage it if it's the only thing that changed.
            non_register=$(git diff --staged --name-only | grep -v "^data/raw/acquisitions-register\.html$" | wc -l)
            if [ "$non_register" -gt 0 ]; then
              echo "changed=true" >> $GITHUB_OUTPUT
            else
              git restore --staged --worktree data/raw/acquisitions-register.html
              echo "changed=false" >> $GITHUB_OUTPUT
            fi
          fi

      # --- Extract (first pass) ---
      # Always runs on non-scheduled triggers; on schedule only if scrape found changes.

      - name: Run extraction
        if: steps.scrape-changes.outputs.changed == 'true' || github.event_name != 'schedule'
```

The "check for scrape changes" step is a key optimisation. On scheduled runs, extraction only proceeds if the scrape actually changed something. The `acquisitions-register.html` file (the paginated index page) is intentionally excluded from this check — it changes slightly on every fetch (a timestamp, a session token) even when no merger data has changed. Treating it as a signal would cause unnecessary extractions on every hourly run.

### Concurrent-run safety and rebase handling

Because the pipeline can run multiple times simultaneously (e.g. a scheduled run overlaps with a push-triggered run), the commit step uses `git pull --rebase` to incorporate any commits made by the concurrent run before pushing. This avoids rejected pushes.

A subtle problem arises from the rebase: after a merge, HTML files that both runs touched are reconstructed from the merge base plus patches from each side. This can reintroduce the raw dynamic tokens that `clean_file` already stripped, because git's three-way merge applies text patches without understanding Perl regex semantics. The pipeline detects this: after rebasing it checks which HTML files were in the rebased commit and re-runs `scrape.sh --clean-file` on each one, then amends the commit if anything changed.

```bash
sed -n '242,279p' .github/workflows/pipeline.yml
```

```output
              git pull --rebase || { git rebase --abort; exit 1; }

              # After rebase, re-clean any HTML files that changed. A 3-way merge
              # during rebase can reintroduce raw dynamic tokens if both the local
              # commit and the pulled commits touched the same file.
              rebase_html=$(git diff HEAD^..HEAD --name-only 2>/dev/null | grep '\.html$' || true)
              if [ -n "$rebase_html" ]; then
                echo "HTML files in rebased commit:"
                echo "$rebase_html" | sed 's/^/  /'
                while IFS= read -r f; do
                  if [ -f "$f" ]; then
                    ./scripts/scrape.sh --clean-file "$f"
                    git add "$f"
                    echo "Re-cleaned: $f"
                  fi
                done <<< "$rebase_html"
                if ! git diff --staged --quiet; then
                  echo "WARNING: Rebase introduced uncleaned HTML — amending commit to fix"
                  git commit --amend --no-edit
                fi
              fi

              # After rebase (and any amend), check whether our commit was reduced to
              # only acquisitions-register.html. This can happen if a concurrent run
              # already committed the shared matter-page/processed-data changes, leaving
              # only the slightly-different acquisitions-register.html in our rebased
              # commit. Drop it rather than push noise.
              post_rebase_non_register=$(git diff HEAD^..HEAD --name-only 2>/dev/null \
                | grep -v "^data/raw/acquisitions-register\.html$" | wc -l)
              if git diff HEAD^..HEAD --name-only 2>/dev/null \
                  | grep -q "acquisitions-register" \
                  && [ "$post_rebase_non_register" -eq 0 ]; then
                echo "Rebase reduced commit to acquisitions-register.html only — dropping, not pushing"
                git reset --hard HEAD^
              else
                git push
              fi
            fi
```

## End-to-End Data Flow Summary

Putting it all together, here is the full path from ACCC website to browser:

```
ACCC website
  └─ scrape.sh (hourly GitHub Actions)
       ├─ pup extracts matter page links from register index
       ├─ xargs -P24 fetches each matter page in parallel
       ├─ clean_file() strips dynamic tokens via Perl
       └─ data/raw/matters/{MN,WA}-*.html (committed to git)
            └─ extract_mergers.py (daily, or on scrape changes)
                 ├─ ProcessPoolExecutor parses all HTML in parallel
                 ├─ Downloads attachments, parses determination PDFs
                 ├─ Merges with previous run's data (preserving frozen events)
                 ├─ Enriches with questionnaire/NOCC data
                 └─ data/processed/mergers.json (committed to git)
                      └─ generate_static_data.py
                           ├─ Enriches mergers (phase determinations, BD dates)
                           ├─ Links related + similar mergers
                           └─ merger-tracker/frontend/public/data/*.json (committed)
                                └─ Cloudflare Pages auto-deploy on git push
                                     └─ React SPA reads /data/*.json at runtime
                                          ├─ useFetchData hook + in-memory cache
                                          ├─ TrackingContext for merger notifications
                                          └─ Pages: Dashboard, Mergers, Timeline, etc.
```

## Key Design Decisions Worth Knowing

**No server, no database.** The entire backend is pre-rendered JSON files committed to git. This means zero hosting cost for the data layer, instant global CDN distribution via Cloudflare Pages, and trivial rollback (just revert the commit). The downside is that every data change requires a CI run.

**git is the database.** Raw HTML and generated JSON are both committed. This gives a complete audit history of every status change on every merger, and means any team member can reproduce the full dataset from the git history.

**Incremental by default, full rebuild on demand.** The cutoff logic and existing-data merging mean normal runs only touch active mergers. The `--all` flag on both `scrape.sh` and `extract_mergers.py` forces a full rebuild — used rarely, for fixing historical data or recovering from bugs.

**Frozen events.** `data/frozen_events_mergers.json` is the escape hatch for cases where the ACCC's website has incorrect or missing data. Any merger listed there has its events array preserved exactly as last scraped, with only genuinely new events (matched by URL) appended. Field overrides in the same file can correct any other field.
