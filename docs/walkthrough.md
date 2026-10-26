# ACCC Merger Tracker — Code Walkthrough

*2026-05-07T23:21:00Z by Showboat 0.6.1*
<!-- showboat-id: 28b53f60-5a04-4536-b663-0db1225cedb4 -->

## Overview

This codebase is a fully static web application that tracks and publishes ACCC merger review data. There is no backend server. Instead, a GitHub Actions pipeline (scheduled, and also triggered by pushes and by the ACCC's register update emails) scrapes the ACCC website, parses the HTML, and generates pre-built JSON files that a React SPA reads directly. Cloudflare Pages hosts the frontend and serves those JSON files as a pseudo-API.

The three major layers are:

1. **Data pipeline** — Bash + Python scripts in `scripts/` that scrape, parse, and generate JSON
2. **Frontend** — React 19 SPA in `frontend/src/` that reads the JSON and renders the UI
3. **Automation** — GitHub Actions workflows in `.github/workflows/` that schedule and orchestrate the pipeline

## The Data Pipeline

### Step 1 — Scraping (`scripts/scrape/scrape.sh`)

The scraper is a Bash script that fetches every merger page from the ACCC public register. It is the first stage in a three-step pipeline: **scrape → extract → generate**.

The scraper's job is purely about fetching and storing raw HTML. All interpretation is left to the Python extraction step.

**Key design decisions:**

- Uses `pup` (a command-line HTML parser written in Go) to extract links from the register index page — no Python parsing needed at this stage.
- Fetches 24 pages in parallel using `xargs -P 24` to keep the scrape fast.
- After downloading each matter page it immediately runs `clean_file()`, a single-pass Perl rewrite that strips out dynamic tokens (cache-busted asset URLs, random DOM IDs, form build IDs, the Drupal settings blob, analytics snippets) so that git diffs only contain meaningful content changes.
- Pipes the register's links, together with `data/processed/mergers.json` (output of the previous run), through `scripts/scrape/scrape_targets.py`, which drops matters past the cutoff (approved mergers more than 3 weeks old no longer need re-scraping) and adds back any still-active matter the listing failed to mention.
- Saves each page as `data/raw/matters/{MATTER_NUMBER}.html`, where the matter number (e.g. `MN-12345` or `WA-67890`) is extracted via `pup` from the page itself.

```bash
sed -n '53,63p' scripts/scrape/scrape.sh
```

```output
# Export variables so they are available to subshells spawned by xargs.
export BASE_URL="https://www.accc.gov.au"
export REGISTER_URL="${BASE_URL}/public-registers/acquisitions-and-mergers-registers/acquisitions-register?init=1&items_per_page=50"
export MAIN_PAGE_FILE="data/raw/acquisitions-register.html"
export SUBFOLDER="data/raw/matters"
export USER_AGENT="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
export MERGERS_JSON="data/processed/mergers.json"
export REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# The Python helpers are package modules (python -m scripts.…), so the repo
# root has to be importable no matter where this script is invoked from.
export PYTHONPATH="${REPO_ROOT}${PYTHONPATH:+:$PYTHONPATH}"
```

Variables are exported (not just set) because the parallel `xargs` workers each run in a child subshell that would not otherwise inherit them. `PARALLEL_JOBS=24` drives both the matter-page fetches and the register pagination fetches.

The `clean_file` function is the most important detail of the scraper. Without it every run would produce huge, noisy git diffs full of auto-generated asset fingerprints that have nothing to do with the actual merger data.

```bash
sed -n '101,125p' scripts/scrape/scrape.sh
```

```output
  perl -i -0777 -pe '
    # Collapse the entire Drupal settings JSON blob to a static placeholder.
    # It is machine config full of per-request churn (session/build tokens such
    # as libraries, permissionsHash, css_js_query_string, view_dom_id, ct,
    # _bhlid, brid, ...) that nothing in the pipeline consumes. Replacing it
    # wholesale beats stripping each field individually, so new tokens the
    # upstream site adds inside it never produce diff noise again.
    s{(<script type="application/json" data-drupal-selector="drupal-settings-json">).*?(</script>)}{${1}STATIC_DRUPAL_SETTINGS${2}}s;
    s/js-view-dom-id-[a-f0-9]{64}/js-view-dom-id-STATIC/g;
    s/(id="edit-submit-accc-search-site--)[^"\n]+"/${1}STATIC"/g;
    s/(id="edit-actions)--[0-9]+"/${1}"/g;
    s/(data-drupal-selector="form-)[^"\n]+(" type="hidden" name="form_build_id")/${1}STATIC${2}/g;
    s/(name="form_build_id" value="form-)[^"\n]+"/${1}STATIC"/g;
    s/(css\/css_)[^.\n]+\.css/${1}STATIC.css/g;
    s/(js\/js_)[^.\n]+\.js/${1}STATIC.js/g;
    s/include=[^"&>\n]+/include=STATIC/g;
    s/href="https:\/\/app\.readspeaker\.com\/[^"\n]+"/href="STATIC_READSPEAKER_URL"/g;
    s/(icons\.svg\?t)[^#\n]+#/${1}STATIC#/g;
    s/(\?t)[^">\n]+/${1}STATIC/g;
    s/[ \t]*\n[ \t]*<script>!function\(e\)\{var n="https:\/\/s\.go-mpulse\.net\/boomerang\/".*?\(window\);<\/script><\/head>/\n  <\/head>/s;
    s{(<meta name="dcterms\.modified"[^\n]*/>\n)(<meta name="dcterms\.created"[^\n]*/>\n)}{$2$1}g;
    s{(<link rel="canonical"[^\n]*/>\n)(<link rel="shortlink"[^\n]*/>\n)}{$2$1}g;
    s{(<nav class="accc-entity-hierarchy-megamenu"[^>]*>).*?</nav>}{${1}STATIC_MEGAMENU</nav>}s;
    s/\n{3,}/\n\n/g;
  ' "$file"
```

The `-0777` flag puts Perl into "slurp mode" — the entire file is read as a single string — which allows the Drupal settings blob, the BOOMR analytics script and the megamenu patterns to match across multiple lines. Without it, multi-line patterns would silently fail while single-line patterns would still work. Each substitution targets a specific source of noise: fingerprinted CSS/JS filenames, 64-character DOM IDs, form build IDs, Readspeaker analytics URLs, and so on.

The target selection runs before fetching to save bandwidth. `scrape_targets.py` reads the previous run's `mergers.json` and drops the link of any merger past its cutoff (see [the cutoff module](#the-cutoff-module-scriptscutoffpy) below), de-duplicates the listing, and unions it with the still-active matters already recorded — the register paginates over an unstable sort, so a matter can silently drop out of one crawl's listing. Comparisons use a normalised key, since the ACCC serves each matter under two spellings of the register path.

```bash
sed -n '339,358p' scripts/scrape/scrape.sh
```

```output
# 4. Work out which matters to fetch.
#
# scrape_targets.py drops matters past cutoff (unless --all), de-duplicates the
# listing, and — importantly — adds back any matter we already know about that
# this crawl's listing failed to mention. The register paginates over an
# unstable sort, so a matter can silently drop out of the listing and then
# never be re-scraped again; see scripts/scrape/scrape_targets.py for detail.
if [ "$SCRAPE_ALL" = true ]; then
  echo "Scraping all mergers (--all flag specified)"
  select_args=(--all)
else
  select_args=()
fi

if [ -n "$SCRAPE_REPORT_DIR" ]; then
  select_args+=(--stats-json "${SCRAPE_REPORT_DIR}/targets.json")
fi

links_to_fetch=$(printf '%s\n' "$relative_links" \
  | python3 -m scripts.scrape.scrape_targets "${select_args[@]}" "$MERGERS_JSON")
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
8. Enrich with questionnaire data, NOCC summaries, and auto-fix missing dates — skipped under `--skip-pdf-enrich`, which the pipeline passes so it can convert DOCX attachments first and then run this pass separately via `scripts/enrich_pdfs.py`
9. Mark each merger as a waiver or notification
10. Sort by merger ID for stable diffs
11. Write to `data/processed/mergers.json` (through the shared `save_mergers` writer)

```bash
sed -n '2458,2481p' scripts/extract_mergers.py
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

Each worker calls this function. A set of private helpers each handle one logical slice of the page, followed by a few inference passes and the per-phase determination records (`scripts/stage_determinations.py`):

```bash
sed -n '1536,1569p' scripts/extract_mergers.py
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

        _infer_determination_date_from_events(merger_data)
        _infer_determination_date_from_unlinked_event(merger_data)
        _calculate_missing_end_of_determination_period(merger_data, merger_id)
        records = stage_determinations.resolve(merger_data, existing_merger_data)
        persisted = stage_determinations.to_persist(merger_data, records)
        if persisted:
            merger_data[stage_determinations.FIELD] = persisted
        _add_synthetic_events(merger_data, records)

        if field_overrides and merger_id in field_overrides:
            merger_data.update(field_overrides[merger_id])
```

Several helpers preserve data from the previous run when a field is absent from the current HTML — `_extract_dates_and_status` keeps `end_of_determination_period` this way, and `_extract_consultation_date` keeps `consultation_response_due_date`. The ACCC frequently removes these fields from the page once the relevant deadline has passed, so without preservation they would silently disappear from the data.

Field overrides (`data/frozen_events_mergers.json`) are applied last, after all scraping, so they can always win over whatever the page says.

#### Events: scraping, merging, and synthetic events

Events are the most complex part of the extraction. There are three functions involved:

- **`_scrape_events`** — reads the attachment tables on the page to produce a fresh list of events, downloading any new PDF/DOCX attachments as a side-effect. Determination PDFs are parsed immediately (via `parse_determination_pdf`) to extract the commission division and decision table, reusing the previous run's parse when the attachment URL is unchanged. It also calls `_scrape_consultation_events` to read the questionnaire out of the ACCC's newer structured Consultation section, flagging those events `is_questionnaire_event`.
- **`_merge_events`** — reconciles the freshly-scraped events with the existing events from the previous run. Events are matched by attachment URL where possible, falling back to title (and, for consultation documents re-uploaded under a new URL, to the normalised attachment filename). Events that disappear from the page get `status: removed` rather than being silently deleted. Fully frozen mergers have their existing events preserved and only genuinely new ones appended; a merger can instead freeze just a listed set of event titles.
- **`_add_synthetic_events`** — appends a synthetic "Merger notified to ACCC" event (from `effective_notification_datetime`), then calls `_flag_determination_event` for the headline determination (from `determination_publication_date` + `accc_determination`) and for every other phase's recorded determination. Each call flags the matching document event as the determination event, or adds a synthetic one if there is none. These make the timeline complete for the frontend without requiring separate scraping.

```bash
sed -n '1423,1454p' scripts/extract_mergers.py
```

```output
def _flag_determination_event(merger_data, phase, determination, det_date):
    """Mark the event holding ``phase``'s determination, or add one.

    ``phase`` is the register's stage label the determination was made in;
    it titles the event "<phase> determination: <determination>".
    """
    events = merger_data['events']
    determination_title = f"{phase} determination: {determination}"

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
    # The ACCC publishes the determination instrument alongside "Summary of
    # reasons"/"Statement of reasons" documents on the same date; attach the
    # determination outcome to the instrument itself, not its reasons.
    candidate_events = [
        e for e in events
        if _dates_within_one_day(e.get('date'), det_date)
        and ('determination' in e.get('title', '').lower()
             or 'determination' in e.get('url', '').lower())
        and e.get('url')
    ]
    existing_det_event = min(candidate_events, key=_mentions_reasons, default=None)
```

The ±1 day tolerance in `_dates_within_one_day` is a real-world edge case: the ACCC's "determination publication date" field sometimes differs by a day from the date shown on the actual events table row (e.g. MN-01090). Without this tolerance a duplicate synthetic determination event would be created alongside the document event, resulting in two entries on the frontend timeline. When nothing matches within a day, a determination PDF up to 4 days earlier is accepted instead (MN-30008 was decided on 11 June but registered on 15 June), and among same-day candidates the instrument is preferred over its "Summary/Statement of reasons".

#### The cutoff module (`scripts/cutoff.py`)

Both `scrape.sh` (via `scrape_targets.py`) and `extract_mergers.py` use this module to decide which mergers still need active attention. The rules are:

- **Waivers** (merger ID starts with `WA-` or stage contains "Waiver"): skip 3 weeks after *any* determination, regardless of outcome.
- **Notifications** (merger ID starts with `MN-`): skip 3 weeks after an *Approved* determination only — 5 weeks when it was approved with conditions. Declined or contested mergers remain in scope indefinitely.

```bash
sed -n '37,64p' scripts/cutoff.py
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
        # Imported here: enrichment imports this module.
        from scripts.generate.static_data.enrichment import detect_has_conditions
        if detect_has_conditions(merger):
            cutoff_weeks = max(cutoff_weeks, CONDITIONAL_CUTOFF_WEEKS)
        return determination_date + timedelta(weeks=cutoff_weeks)

    # Not approved or no determination - keep processing
    return None
```

### Step 3 — Static data generation (`scripts/generate/generate_static_data.py`)

Once `mergers.json` is written, `generate_static_data.py` turns it into all the individual JSON files the frontend reads. This script is a thin orchestrator: it loads source data, calls `enrich_merger()` once per merger, then delegates to specialised output generators in the `static_data/outputs/` package.

The enrichment step adds computed fields that would be expensive to recalculate on every frontend request:

- Phase-specific determination outcomes (`phase_1_determination`, `phase_2_determination`, `public_benefits_determination`)
- The expected competition concerns notice date for Phase 2 mergers (business day 25 of the Phase 2 window)
- Flags for whether questionnaire and NOCC data are available (`has_questionnaire`, `has_nocc`)
- Per-event `phase` labels extracted from event titles

Enriched mergers are then linked to related mergers (waiver-to-notification pairs), similar mergers (from `data/processed/similar_mergers.json`, pre-computed by `generate_similar_mergers.py` from party and ANZSIC overlap), canonical party groups, Tribunal appeals and Federal Court judicial reviews, and given their frozen phase-1 estimate and pre-notification bounds.

```bash
sed -n '204,255p' scripts/generate/generate_static_data.py
```

```output
    # Small single-file outputs: call generator → write result
    single_file_outputs = [
        ("stats.json", stats.generate(enriched)),
        ("industries.json", industries.generate_index(enriched)),
        ("parties.json", parties.generate_index(party_groups)),
        ("upcoming-events.json", upcoming_events.generate(enriched)),
        ("commentary.json", commentary_out.generate(enriched, commentary)),
        ("analysis.json", analysis.generate(enriched)),
        ("quarterly.json", quarterly.generate(enriched, commentary=load_quarterly_commentary())),
        ("serial-acquirers.json", serial_acquirers.generate(enriched)),
        ("theories_of_harm.json", theories_of_harm.generate(enriched, nocc_data)),
        ("phase2.json", phase2.generate(enriched)),
        ("refiled-notifications.json", refiled.generate(enriched)),
        ("extensions.json", extensions.generate(enriched)),
        # P(Phase 2 referral | still undecided at business day N); not consumed
        # by the frontend yet — a building block for a future per-merger risk feature.
        ("referral-probability-by-day.json", referral_probability_by_day(enriched)),
    ]
    for filename, payload in single_file_outputs:
        out_path = OUTPUT_DIR / filename
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(payload, f, indent=2)
        print(f"✓ Generated {out_path}")

    print("\nGenerating individual merger files...")
    n = individual.generate(enriched, OUTPUT_DIR)
    print(f"✓ Generated {n} individual merger files in {OUTPUT_DIR / 'mergers'}")

    print("\nGenerating merger list file...")
    n = list_out.generate(enriched, OUTPUT_DIR)
    print(f"✓ Generated {OUTPUT_DIR / 'mergers' / 'list.json'} ({n} mergers)")

    print("\nGenerating industry division files...")
    n = industries.generate_detail_files(enriched, OUTPUT_DIR)
    print(f"✓ Generated {n} industry division files in {OUTPUT_DIR / 'industries'}")

    print("\nGenerating party detail files...")
    n = parties.generate_detail_files(party_groups, OUTPUT_DIR)
    print(f"✓ Generated {n} party records in {OUTPUT_DIR / 'parties'} "
          f"({SHARD_COUNT} shard buckets)")

    if questionnaire_data:
        print("\nGenerating questionnaire files...")
        q_count = questionnaires.generate(questionnaire_data, OUTPUT_DIR, mergers=enriched)
        print(f"✓ Generated {q_count} questionnaire files in {OUTPUT_DIR / 'questionnaires'}")

    if nocc_data:
        print("\nGenerating NOCC files...")
        n_count = noccs.generate(nocc_data, OUTPUT_DIR)
        print(f"✓ Generated {n_count} NOCC files in {OUTPUT_DIR / 'noccs'}")

    print("\nDone!")
```

The output files are written directly into `frontend/public/data/`, which is the Vite project's static assets folder. Because these files are committed to git, Cloudflare Pages picks them up on every push; the Vite build copies them through unchanged and serves them as plain static files, with no server-side rendering (the build does prerender static HTML for each merger page from them).

The merger list is a single file, `mergers/list.json`, holding a lightweight record (no events, no description) for every merger. The /mergers page searches, filters and sorts it entirely in the browser, so it needs all of it up front; at ~110 KB gzipped, one request beats paging it in. It was once split into 50-merger pages, which cost a round trip each and reshuffled the list as they arrived.

Individual merger files (`mergers/{id}.json`) are written separately from the list file and contain the full detail including events, parties, and documents.

## The Frontend

### App structure (`src/main.jsx` and `src/App.jsx`)

The entry point (`main.jsx`) mounts the React root in strict mode. `App.jsx` wraps everything in four providers before the route tree is rendered:

1. **`HelmetProvider`** — manages `<head>` tags (title, meta, Open Graph) via the `SEO` component on each page
2. **`BrowserRouter`** — React Router's history-based router
3. **`TrackingProvider`** — global merger-tracking state (described below)
4. **`ErrorBoundary`** — catches render errors and shows a fallback UI instead of a blank screen

The keyboard shortcut system lives inside `AppContent` (the inner component) rather than at the provider level so it can reference React Router's navigation context.

```bash
sed -n '56,80p' frontend/src/App.jsx
```

```output
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/mergers" element={<Mergers />} />
            <Route path="/mergers/:id" element={<MergerDetail />} />
            <Route path="/mergers/:id/:slug" element={<MergerDetail />} />
            <Route path="/industries" element={<Industries />} />
            <Route path="/industries/:code" element={<IndustryDetail />} />
            <Route path="/industries/:code/:slug" element={<IndustryDetail />} />
            <Route path="/parties" element={<Parties />} />
            <Route path="/parties/:id" element={<PartyDetail />} />
            <Route path="/parties/:id/:slug" element={<PartyDetail />} />
            <Route path="/commentary" element={<Commentary />} />
            <Route path="/digest" element={<Digest />} />
            <Route path="/analysis" element={<Analysis />} />
            <Route path="/phase-2" element={<Phase2 />} />
            <Route path="/refiled-notifications" element={<RefiledNotifications />} />
            <Route path="/current-status" element={<CurrentStatus />} />
            <Route path="/quarterly" element={<Quarterly />} />
            <Route path="/quarterly/:quarter" element={<Quarterly />} />
            <Route path="/nick-twort" element={<NickTwort />} />
            <Route path="/privacy" element={<PrivacyPolicy />} />
            <Route path="/copyright" element={<Copyright />} />
            <Route path="/feedback" element={<Feedback />} />
            <Route path="*" element={<NotFound />} />
          </Routes>
```

### Data fetching (`src/hooks/useFetchData.js` + `src/utils/dataCache.js`)

Every page that needs JSON uses the `useFetchData` hook. It provides three things that plain `fetch` does not:

1. **Module-level in-memory cache** — `dataCache` is a `Map` stored at module scope, so it survives route changes. When the user switches from the Dashboard to the Mergers list and back, stats data is returned synchronously from the cache without a network round-trip or a loading spinner. The cache has no TTL — it lives for the session — but whatever is on screen is kept fresh in the background: `useBackgroundRefresh` (mounted once from `App.jsx`) calls `dataCache.revalidate` when the tab regains visibility and on a long fallback interval, and mounted hooks re-render only if the data actually changed.

2. **Abort on unmount** — an `AbortController` is created per fetch. The cleanup function returned from `useEffect` calls `controller.abort()`, so responses that arrive after a component unmounts are discarded rather than touching state on a dead component.

3. **SPA 404 detection** — Cloudflare Pages serves `index.html` for any unknown path (to support client-side routing). That means a missing `.json` file returns HTTP 200 with HTML, which `JSON.parse` rejects with a `SyntaxError`. The hook catches this and converts it to an HTTP 404 error so callers can distinguish "file missing" from real network errors.

```bash
sed -n '72,93p' frontend/src/utils/dataCache.js
```

```output
  // Re-fetches `url` in the background and, if the result differs from
  // what's cached under `key`, stores it and notifies subscribers so any
  // mounted useFetchData hooks re-render with the fresh data. `no-store`
  // bypasses the browser's HTTP cache — the whole point is checking whether
  // the pipeline has published something new since the last fetch. Errors
  // (offline, a bad response) are swallowed: this runs silently, leaving
  // whatever's already cached in place.
  async revalidate(key, url) {
    try {
      const res = await fetch(url, { cache: 'no-store' });
      if (!res.ok) return;
      const data = await res.json();
      const previous = cache.get(key);
      cache.set(key, { data, fetchedAt: Date.now() });
      if (!previous || JSON.stringify(previous.data) !== JSON.stringify(data)) {
        listeners.get(key)?.forEach((cb) => cb(data));
      }
    } catch {
      // Offline, aborted, or an unparseable body — leave the cache as-is.
    }
  },
};
```

### API endpoints (`src/config.js`)

All JSON file paths are defined in one place. Each endpoint is either a static string (e.g. `/data/stats.json`) or a function that produces a path from an ID (e.g. `mergerDetail(id) => `/data/mergers/${id}.json``). This means a change to the file naming convention only needs to happen in `config.js` — except for the packed party and industry files, whose file names are computed by `utils/shard.js` and `utils/industryDivision.js`.

```bash
cat frontend/src/config.js
```

```output
// API configuration for static JSON files
// These files are generated by generate_static_data.py and served from /data/

// Party records are packed into fixed shard buckets rather than one file per
// party — see frontend/src/utils/shard.js for why, and note that the SPA and
// the Python generator have to agree on the bucketing rule exactly.
import { partyShardName } from './utils/shard';
// Industry nodes are likewise packed one file per ANZSIC division rather than
// one per node — see frontend/src/utils/industryDivision.js.
import { industryDivisionUrl } from './utils/industryDivision';

// Cloudflare Worker endpoints — all served from signup.mergers.fyi
export const SUBSCRIBE_ENDPOINT = "https://signup.mergers.fyi";
export const FEEDBACK_ENDPOINT = "https://signup.mergers.fyi/feedback";
// Privacy-preserving feature-usage ping — see frontend/src/utils/trackEvent.js
export const EVENT_ENDPOINT = "https://signup.mergers.fyi/event";

// The site's Bluesky account (handle mergers.fyi, see atproto/identity.json).
export const BLUESKY_PROFILE_URL = "https://bsky.app/profile/mergers.fyi";

// Cloudflare Turnstile site key (public — safe to commit).
// 1. Go to Cloudflare Dashboard > Turnstile > Add site
// 2. Paste the Site Key here.
// 3. Add the Secret Key to your Worker: wrangler secret put TURNSTILE_SECRET_KEY
export const TURNSTILE_SITE_KEY = "0x4AAAAAACg1KC_xTS0WAPpu";

export const API_ENDPOINTS = {
  mergersList: '/data/mergers/list.json',  // Every merger, lightweight — the /mergers page and command palette
  mergerDetail: (id) => `/data/mergers/${id}.json`,  // Individual merger file
  stats: '/data/stats.json',
  industries: '/data/industries.json',
  industryDivision: industryDivisionUrl,  // Division file holding this node (and every other node under the same division)
  parties: '/data/parties.json',
  partyShard: (id) => `/data/parties/${partyShardName(id)}`,  // Bucket holding this party's record
  upcomingEvents: '/data/upcoming-events.json',
  commentary: '/data/commentary.json',  // Mergers with user commentary
  digest: '/data/digest.json',  // Weekly digest of merger activity
  analysis: '/data/analysis.json',  // Pre-computed analysis data
  quarterly: '/data/quarterly.json',  // Quarter-by-quarter report (volume, outcomes, timing, milestones)
  quarterlyReportPdf: (filename) => `/data/reports/${filename}`,  // A quarter's PDF, named by its quarterly.json block's report_pdf
  phase2: '/data/phase2.json',  // Current + completed Phase 2 matters with statutory milestones
  refiledNotifications: '/data/refiled-notifications.json',  // Waivers declined then re-filed as notifications
  referralProbabilityByDay: '/data/referral-probability-by-day.json',  // P(Phase 2 referral | still undecided at business day N), positional by day
  questionnaire: (id) => `/data/questionnaires/${id}.json`,  // Questionnaire data (lazy-loaded)
};
```

### Global state — merger tracking (`src/context/TrackingContext.jsx`)

Users can "track" individual mergers to receive notifications when new events or upcoming deadlines appear, and follow industries to hear about new filings and determinations in them. All tracking state is managed in `TrackingContext`, which wraps the entire app.

**What it stores (all persisted to `localStorage`):**

- `trackedMergerIds` — array of merger IDs the user is watching
- `trackedIndustries` — followed industries (code and name)
- `seenEventKeys` — Set of event keys (derived from `merger_id + date + title`) that the user has already seen in the notification panel
- the auto-track settings: re-filed matters already auto-tracked, and the opt-in to auto-track every matter that reaches Phase 2

**How events are fetched:**

When `trackedMergerIds` changes, the context fetches individual merger detail files in parallel (one `fetch` per tracked merger). This is deliberately more targeted than fetching the full timeline — it avoids downloading hundreds of events for mergers the user doesn't care about.

The context then synthesises upcoming events directly from the individual merger data for tracked mergers. This matters because `upcoming-events.json` only contains events within a 60-day window — Phase 2 mergers whose determination deadline is months away would otherwise be invisible in the notification panel.

**Seen event deduplication:**

Events are identified by a stable key: `${merger_id}_${date}_${display_title}` (prefixed with `ind_${industry_code}_` for industry-follow events; a Tribunal appeal document is keyed by its link instead, since its title is edited by hand). When a merger is first tracked, all its current events are immediately marked as seen (via `newlyTrackedIds`), so only events that appear *after* tracking began show as new.

```bash
sed -n '45,57p' frontend/src/context/TrackingContext.jsx
```

```output
// Generate a unique key for an event
// Use a consistent order and normalize the title field for stability
const getEventKey = (event) => {
  // A tribunal appeal document is keyed by its document link, not its title:
  // the title carries a comment added by hand, often after followers have
  // already been notified, and a title-based key would announce the same
  // document again.
  const docUrl = event.is_appeal && (event.url || event.url_gh);
  if (docUrl) return `${event.merger_id}_${event.date}_appeal_${docUrl}`;
  // Normalize title: prefer display_title, then title, then event_type_display, finally type
  const title = event.display_title || event.title || event.event_type_display || event.type || '';
  return titleKey(event, title);
};
```

The title normalisation cascade (`display_title → title → event_type_display → type`) is necessary because events from different sources use different field names. Timeline events from the individual merger files use `title`/`display_title`; upcoming events from `upcoming-events.json` use `event_type_display`. Using a consistent preference order ensures the key is stable across sources, so the same real-world event generates the same key regardless of which JSON file it came from.

## GitHub Actions Automation

### The pipeline workflow (`.github/workflows/pipeline.yml`)

The pipeline runs on four triggers:

- **Schedule** — four times a day on weekdays at 7:08, 11:08, 15:08, 19:08 Sydney time; once on Sundays at 7:08
- **Push to main** — immediately after any commit (so manual data fixes are picked up without waiting for the next schedule)
- **`repository_dispatch`** (`new_merger_detected`) — fired by the `accc-register-watcher` Cloudflare Email Worker whenever the ACCC's register update mailing list sends an email (near-real-time updates)
- **`workflow_dispatch`** — manual trigger, with an `all_mergers` boolean to force a full re-extraction

The pipeline runs as a single job with no parallelism — the steps are inherently sequential (scrape → extract → generate). An important detail: extraction is split into *two* phases. The download phase (`extract_mergers.py --skip-pdf-enrich`) parses the HTML and downloads attachments; if any DOCX files arrive (the ACCC sometimes publishes documents in Word format), LibreOffice converts them to PDF; then the enrich phase (`scripts/enrich_pdfs.py`) parses questionnaire, NOCC and Phase 2 Notice PDFs, so the converted documents are picked up in the same run.

```bash
sed -n '230,246p' .github/workflows/pipeline.yml
```

```output
      - name: Check for scrape changes
        id: scrape-changes
        run: |
          git add -A
          if git diff --staged --quiet; then
            echo "changed=false" >> $GITHUB_OUTPUT
          else
            echo "changed=true" >> $GITHUB_OUTPUT
          fi

      # --- Extract phase 1: HTML parse + attachment download ---
      # extract_mergers.py downloads attachment PDFs / DOCX files as a side
      # effect of parsing each matter page. We skip questionnaire/NOCC PDF
      # parsing here so we can convert any newly downloaded DOCX files first,
      # then do the PDF-parse pass in phase 2 below.

      - name: Run extraction (download phase)
```

The "check for scrape changes" step is a key optimisation. On scheduled runs, extraction only proceeds if the scrape actually changed something. The paginated index page, `acquisitions-register.html`, never enters this check at all: it changes slightly on every fetch (a timestamp, a session token) even when no merger data has changed, and it is only ever used as a transient working file within a single scrape run to derive matter links. Rather than committing it and then filtering it back out, it is **git-ignored** (see `.gitignore`), so `git add -A` never stages it and it can never be mistaken for a change signal.

### Concurrent-run safety and rebase handling

Pipeline runs are serialised by a `concurrency` group, but other things still push to `main` while a run is scraping (the tribunal scraper, the quarterly report, a person), so the commit step uses `git pull --rebase` to incorporate those commits before pushing. This avoids rejected pushes. A genuine rebase conflict is not hand-merged: the run gives up its commit and dispatches a fresh pipeline run on the new `main` (at most three times in a chain).

A subtle problem arises from the rebase: after a merge, HTML files that both runs touched are reconstructed from the merge base plus patches from each side. This can reintroduce the raw dynamic tokens that `clean_file` already stripped, because git's three-way merge applies text patches without understanding Perl regex semantics. The pipeline detects this: after rebasing it checks which HTML files were in the rebased commit and re-runs `scrape.sh --clean-file` on each one, then amends the commit if anything changed.

```bash
sed -n '618,638p' .github/workflows/pipeline.yml
```

```output
            # After rebase, re-clean any HTML files that changed. A 3-way merge
            # during rebase can reintroduce raw dynamic tokens if both the local
            # commit and the pulled commits touched the same file.
            rebase_html=$(git diff HEAD^..HEAD --name-only 2>/dev/null | grep '\.html$' || true)
            if [ -n "$rebase_html" ]; then
              echo "HTML files in rebased commit:"
              echo "$rebase_html" | sed 's/^/  /'
              while IFS= read -r f; do
                if [ -f "$f" ]; then
                  ./scripts/scrape/scrape.sh --clean-file "$f"
                  git add "$f"
                  echo "Re-cleaned: $f"
                fi
              done <<< "$rebase_html"
              if ! git diff --staged --quiet; then
                echo "WARNING: Rebase introduced uncleaned HTML — amending commit to fix"
                git commit --amend --no-edit
              fi
            fi

            git push
```

## End-to-End Data Flow Summary

Putting it all together, here is the full path from ACCC website to browser:

```
ACCC website
  └─ scrape.sh (pipeline.yml: weekdays 4×/day, Sundays, on push, on register email)
       ├─ pup extracts matter page links from register index
       ├─ xargs -P24 fetches each matter page in parallel
       ├─ clean_file() strips dynamic tokens via Perl
       └─ data/raw/matters/{MN,WA}-*.html (committed to git)
            └─ extract_mergers.py + enrich_pdfs.py (on scrape changes, or any non-scheduled run)
                 ├─ ProcessPoolExecutor parses all HTML in parallel
                 ├─ Downloads attachments, parses determination PDFs
                 ├─ Merges with previous run's data (preserving frozen events)
                 ├─ Enriches with questionnaire/NOCC data
                 └─ data/processed/mergers.json (committed to git)
                      └─ generate_static_data.py
                           ├─ Enriches mergers (phase determinations, BD dates)
                           ├─ Links related + similar mergers
                           └─ frontend/public/data/*.json (committed)
                                └─ Cloudflare Pages auto-deploy on git push
                                     └─ React SPA reads /data/*.json at runtime
                                          ├─ useFetchData hook + in-memory cache
                                          ├─ TrackingContext for merger notifications
                                          └─ Pages: Dashboard, Mergers, Industries, Analysis, etc.
```

## Key Design Decisions Worth Knowing

**No server, no database.** The entire backend is pre-rendered JSON files committed to git. This means zero hosting cost for the data layer, instant global CDN distribution via Cloudflare Pages, and trivial rollback (just revert the commit). The downside is that every data change requires a CI run.

**git is the database.** Raw HTML and generated JSON are both committed. This gives a complete audit history of every status change on every merger, and means any team member can reproduce the full dataset from the git history.

**Incremental by default, full rebuild on demand.** The cutoff logic and existing-data merging mean normal runs only touch active mergers. The `--all` flag on both `scrape.sh` and `extract_mergers.py` forces a full rebuild — used rarely, for fixing historical data or recovering from bugs.

**Frozen events.** `data/frozen_events_mergers.json` is the escape hatch for cases where the ACCC's website has incorrect or missing data. Any merger listed there has its events array preserved exactly as last scraped, with only genuinely new events (matched by URL) appended — or, if it lists specific event titles, just those events are frozen. Field overrides in the same file can correct any other field.
