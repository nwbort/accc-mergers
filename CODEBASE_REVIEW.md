# ACCC Merger Tracker — Comprehensive Codebase Review

**Date:** 2026-03-20
**Scope:** Full codebase — Python scripts, React frontend, GitHub Actions workflows, Cloudflare Worker, infrastructure

---

## Table of Contents

1. [Security Issues](#1-security-issues)
2. [Accessibility Issues](#2-accessibility-issues)
3. [Bugs](#3-bugs)
4. [Workflow Streamlining](#4-workflow-streamlining)
5. [Enhancement Opportunities](#5-enhancement-opportunities)
6. [Code Quality & Maintenance](#6-code-quality--maintenance)

---

## 1. Security Issues

### 1.1 CRITICAL: Hardcoded Localhost CORS in Cloudflare Worker

**File:** `cloudflare-worker/src/index.js:29-30`

```javascript
const allowedOrigins = [ALLOWED_ORIGIN, "http://localhost:5173", "http://localhost:4173"];
```

Localhost origins are hardcoded in production code. Any attacker running a local server on these ports can bypass CORS restrictions.

**Fix:** Use Cloudflare environment variables to conditionally allow localhost only in development:
```javascript
const allowedOrigins = env.ENVIRONMENT === 'development'
  ? [ALLOWED_ORIGIN, "http://localhost:5173", "http://localhost:4173"]
  : [ALLOWED_ORIGIN];
```

### 1.2 HIGH: Overly Broad GitHub Actions Permissions

**Files:** `scrape.yml:9-11`, `extract.yml:12-14`, `convert.yml:9-11`, `all-mergers.yml:6-7`

All pipeline workflows grant `actions: write`. Only the orchestrating workflow needs this to trigger downstream workflows. The others should be restricted.

**Files:** `claude.yml:21-26`

The Claude workflow has `id-token: write` which is unnecessary for code review.

**Fix:** Remove `actions: write` from `extract.yml` and `convert.yml`. Remove `id-token: write` from `claude.yml`.

### 1.3 HIGH: No URL Validation Before Download (SSRF Risk)

**File:** `scripts/extract_mergers.py:148`

```python
response = requests.get(attachment_url, stream=True)
```

URLs parsed from HTML are fetched without domain validation. A crafted page could trigger requests to internal services.

**Fix:** Validate URLs before downloading:
```python
from urllib.parse import urlparse
def is_safe_url(url):
    parsed = urlparse(url)
    return parsed.scheme in ('http', 'https') and parsed.netloc.endswith('accc.gov.au')
```

### 1.4 HIGH: Cloudflare Turnstile Script Without SRI

**File:** `merger-tracker/frontend/src/pages/Digest.jsx:302`

Turnstile script loaded dynamically without Subresource Integrity check. CDN compromise could execute malicious script.

**Fix:** Add `scriptEl.integrity` and `scriptEl.crossOrigin` attributes.

### 1.5 MEDIUM: Path Traversal Edge Cases in Filename Handling

**File:** `scripts/extract_mergers.py:22-51`

`sanitize_filename()` uses a character blacklist approach. Unicode normalization bypasses are possible.

**Fix:** Use `unicodedata.normalize('NFKC', filename)` before validation, and switch to a whitelist pattern.

### 1.6 MEDIUM: Floating Dependency Versions

**File:** `requirements.txt`

```
requests>=2.31.0        # Floating
markdownify>=0.11.0     # Floating
pdfplumber>=0.9.0       # Floating
```

Non-reproducible builds; potentially pulls versions with breaking changes or vulnerabilities.

**Fix:** Pin exact versions: `requests==2.32.3`, etc.

### 1.7 MEDIUM: Missing Secret Rotation Documentation

No documented rotation policy for `RESEND_API_KEY`, `RESEND_AUDIENCE_ID`, `CLAUDE_CODE_OAUTH_TOKEN`, or Cloudflare Worker secrets.

**Fix:** Add "Security & Secret Management" section to `docs/deployment.md`.

### 1.8 LOW: No HTTPS Enforcement / Timeout on HTTP Requests

**File:** `scripts/extract_mergers.py:148`, `scripts/send_weekly_email.py:557`

`requests.get()` and `requests.post()` lack explicit timeouts. Hung connections could block the pipeline indefinitely.

**Fix:** Add `timeout=30` to all requests calls.

---

## 2. Accessibility Issues

### 2.1 HIGH: Timeline Events Not Keyboard Accessible

**File:** `merger-tracker/frontend/src/pages/Timeline.jsx:203`

Timeline event cards use `role="link"` with `onClick` on a `<div>` but don't handle keyboard events (Enter/Space). Keyboard-only users cannot navigate timeline.

**Fix:** Convert to `<Link>` component from React Router, or add `onKeyDown` handler.

### 2.2 HIGH: Industry Table Expand/Collapse Lacks Semantic Role

**File:** `merger-tracker/frontend/src/pages/Industries.jsx:195-217`

Expandable rows have `tabIndex={0}` but the expand arrow icon has no proper button role. Screen readers can't convey the expand/collapse affordance.

**Fix:** Wrap the arrow in a `<button>` with `aria-expanded` and `aria-label`.

### 2.3 MEDIUM: Chart Accessibility

**File:** `merger-tracker/frontend/src/pages/Dashboard.jsx:305`

Doughnut chart's `aria-label` dumps raw data as a comma-separated string. Difficult for screen reader users to parse.

**Fix:** Provide structured `aria-describedby` linking to a hidden summary table.

### 2.4 MEDIUM: Mobile Table Header Mismatch

**File:** `merger-tracker/frontend/src/components/UpcomingEventsTable.jsx:67-117`

Mobile view uses a combined "Date/Event" column header but actual cells are split. Screen readers will misread the table structure.

**Fix:** Use separate `<th>` elements per column on all breakpoints.

### 2.5 MEDIUM: Markdown Content Missing Accessible Container

**File:** `merger-tracker/frontend/src/pages/Commentary.jsx:118`, `Digest.jsx:458`

`ReactMarkdown` output has no `aria-label` on the prose container. Links within rendered markdown may also have poor color contrast.

**Fix:** Add `role="article"` and `aria-label` to the markdown container. Verify link contrast meets WCAG AA.

### 2.6 LOW: StatCard Definition List Semantics

**File:** `merger-tracker/frontend/src/components/StatCard.jsx:20-34`

`<dl>/<dt>/<dd>` elements lack clear associations for screen readers.

**Fix:** Use `aria-labelledby` to associate values with their labels.

---

## 3. Bugs

### 3.1 HIGH: Determination Event Date Matching Fails on Timezone Mismatch

**File:** `merger-tracker/frontend/src/pages/MergerDetail.jsx:151-160`

```javascript
event.date === merger.determination_publication_date
```

Strict string equality. If one date includes time info (`2026-03-01T12:00:00Z`) and the other doesn't (`2026-03-01`), the determination PDF link silently won't appear.

**Fix:** Compare date-only portions: `event.date?.split('T')[0] === merger.determination_publication_date?.split('T')[0]`

### 3.2 HIGH: Circular Workflow Dependency — Potential Infinite Loop

**Files:** `scrape.yml:63` → `extract.yml:58` → `convert.yml:88` → `extract.yml`

Chain: scrape triggers extract, extract triggers convert, convert triggers extract. If convert commits new PDFs, extract reruns and may trigger convert again.

**Fix:** Add a guard in extract.yml to only trigger convert when new DOCX files are detected, and in convert.yml to not trigger extract if no conversions occurred.

### 3.3 HIGH: Git Operations Suppress Errors in CI

**Files:** `scrape.yml:54`, `extract.yml:49`, `all-mergers.yml:61`

```yaml
git commit -m "..." || exit 0   # Suppresses ALL commit failures
git pull --rebase               # No conflict handling
git push                        # No retry or error handling
```

If rebase fails (concurrent pushes from multiple workflows), the workflow silently fails. Downstream workflows then pull stale data.

**Fix:** Add explicit error handling:
```yaml
git pull --rebase || { git rebase --abort; exit 1; }
git push || { echo "Push failed"; exit 1; }
```

### 3.4 HIGH: Timeline Race Condition on Rapid Scroll

**File:** `merger-tracker/frontend/src/pages/Timeline.jsx:86-89`

`loadMoreEvents()` uses `displayedEvents.length` which can be stale if two batch loads trigger concurrently during fast scrolling.

**Fix:** Use a ref to track the current length, or debounce the load trigger.

### 3.5 MEDIUM: Page Fetch Failure Crashes Entire Mergers List

**File:** `merger-tracker/frontend/src/pages/Mergers.jsx:114-156`

If any single page fetch fails, the entire fetch chain fails. No per-page error handling.

**Fix:** Use `Promise.allSettled()` and skip failed pages:
```javascript
const results = await Promise.allSettled(fetches);
const mergers = results.filter(r => r.status === 'fulfilled').flatMap(r => r.value.mergers);
```

### 3.6 MEDIUM: Race Condition Between Digest Generation and Email Send

**Files:** `weekly-digest.yml:7` (cron: Saturday 22:00 UTC), `send-weekly-email.yml:7` (cron: Sunday 23:00 UTC)

If digest generation is delayed by GitHub Actions queueing, the email workflow may send stale data.

**Fix:** Chain the email workflow as a `workflow_run` trigger from the digest workflow instead of independent cron.

### 3.7 MEDIUM: `decodeURIComponent` Can Crash IndustryDetail

**File:** `merger-tracker/frontend/src/pages/IndustryDetail.jsx:11`

`decodeURIComponent(code)` throws if the URL param contains invalid percent-encoding (e.g., `%ZZ`).

**Fix:** Wrap in try-catch.

### 3.8 MEDIUM: Date Range Formatting Edge Case

**File:** `merger-tracker/frontend/src/pages/Digest.jsx:334-351`

`formatDateRange()` doesn't handle `startDate === endDate`. Output would be "1-1 January 2026".

**Fix:** Return `formatDate(startDate)` when dates are equal.

### 3.9 LOW: Silent JSON Parse Failure in extract_mergers.py

**File:** `scripts/extract_mergers.py:647-665`

JSON decode errors cause `sys.exit(1)` with no fallback. If `mergers.json` is corrupted by a partial write, the entire pipeline halts.

**Fix:** Keep a `.bak` copy before writing, and fall back to it on parse failure.

---

## 4. Workflow Streamlining

### 4.1 HIGH: Consolidate Duplicate Pipeline Logic in all-mergers.yml

**File:** `.github/workflows/all-mergers.yml`

Duplicates 130+ lines from `scrape.yml`, `extract.yml`, and `convert.yml`. Any change to the pipeline must be made in two places.

**Fix:** Create a reusable composite workflow that both the individual triggers and the manual all-mergers workflow call.

### 4.2 HIGH: Consolidate Date Parsing Across Python Scripts

**Files:** `scripts/send_weekly_email.py:59-85`, `scripts/generate_static_data.py:125-129`, `scripts/date_utils.py`

`date_utils.py` already has centralized date parsing, but `send_weekly_email.py` and `generate_static_data.py` have their own inline implementations.

**Fix:** Import from `date_utils.py` everywhere.

### 4.3 MEDIUM: Consolidate Duplicate `is_waiver_merger()` Function

**Files:** `scripts/cutoff.py:23-27`, `scripts/generate_static_data.py:228-233`

Same function duplicated in two files.

**Fix:** Remove from `generate_static_data.py` and import from `cutoff.py`.

### 4.4 MEDIUM: Consolidate HTML Escaping

**Files:** `scripts/send_weekly_email.py:111-119` (custom `esc()`), `scripts/generate_rss_feed.py:15` (stdlib `escape`)

Custom escape function duplicates `xml.sax.saxutils.escape`.

**Fix:** Use `from xml.sax.saxutils import escape` everywhere.

### 4.5 MEDIUM: Standardize Python Versions Across Workflows

**Files:** `scrape.yml`, `extract.yml` use Python 3.10; `send-weekly-email.yml`, `update-sitemap.yml`, `weekly-digest.yml` use Python 3.11.

Python 3.10 reached EOL October 2024. Inconsistency risks subtle behavior differences.

**Fix:** Standardize on Python 3.11+ across all workflows.

### 4.6 LOW: Cache Configuration Inconsistency

Pip caching is enabled in some workflows (`weekly-digest.yml`) but disabled in others (`extract.yml`). Go binary caching is also inconsistent.

**Fix:** Standardize `cache: 'pip'` across all Python workflows.

---

## 5. Enhancement Opportunities

### 5.1 Data Validation Pipeline

**New script:** `scripts/validate_data.py`

Add automated consistency checks:
- All events have valid ISO dates
- Notification date precedes determination date
- Merger IDs match expected format (`MN-\d{5}` or `WA-\d{5}`)
- Required fields (`merger_id`, `merger_name`, `status`) are present
- ANZSIC codes are valid

Run as a CI step after extraction.

### 5.2 Incremental Processing

**File:** `scripts/extract_mergers.py`

Currently re-parses all HTML files on every run. Track file hashes to only process changed files.

**Impact:** Significantly faster CI runs when only a few mergers update.

### 5.3 Network Retry Logic for Attachment Downloads

**File:** `scripts/extract_mergers.py:148`

No retry on transient network failures. Attachments silently fail to download.

**Fix:** Use `requests.adapters.HTTPAdapter` with `urllib3.util.retry.Retry`:
```python
retry = Retry(total=3, backoff_factor=0.5, status_forcelist=[408, 429, 500, 502, 503, 504])
```

### 5.4 Data Backup Before Writes

**Files:** `scripts/extract_mergers.py`, `scripts/generate_static_data.py`

No backup of `mergers.json` before overwriting. A partial write or bug corrupts the file with no recovery path.

**Fix:** Write to a `.tmp` file, validate, then atomically rename. Keep last N backups.

### 5.5 User-Facing Error States in Frontend

**Files:** `Dashboard.jsx:96`, `Mergers.jsx:138`, `TrackingContext.jsx:77-81`

Failed async operations silently set empty state. Users see an empty page with no explanation.

**Fix:** Add error banners/toasts for failed data loads. Track failed merger IDs in TrackingContext and warn users.

### 5.6 Fuzzy Search

**File:** `merger-tracker/frontend/src/utils/searchIndex.js`

Only exact substring matching. Typos like "Ampol" vs "Ampal" return no results.

**Fix:** Add Levenshtein distance or trigram-based fuzzy matching.

### 5.7 Digest Export/Share

**File:** `merger-tracker/frontend/src/pages/Digest.jsx`

Users can subscribe to email digest but can't export/share individual digests.

**Fix:** Add PDF export or "copy link" functionality for digest pages.

### 5.8 Merger Progress Indicator

**File:** `merger-tracker/frontend/src/pages/MergerDetail.jsx`

For mergers "Under assessment", show a visual progress bar or countdown to determination deadline (business days remaining).

### 5.9 Notification Filtering

**File:** `merger-tracker/frontend/src/components/NotificationPanel.jsx`

Users can only track/untrack entire mergers. No ability to filter by event type (e.g., "only notify me about determinations").

### 5.10 Proper Logging Framework for Python Scripts

**Files:** All scripts in `scripts/`

All scripts use `print()` for logging. No log levels, no structured output, no file logging.

**Fix:** Use Python `logging` module with configurable levels.

---

## 6. Code Quality & Maintenance

### 6.1 Long Functions Need Decomposition

- `parse_merger_file()` in `extract_mergers.py` — 338 lines
- `build_html_email()` in `send_weekly_email.py` — 121 lines

Break into smaller, testable functions.

### 6.2 Magic Numbers

- `generate_static_data.py:99` — `divmod(total_days, 7)`
- `send_weekly_email.py:106` — `max_chars * 0.7` truncation threshold
- `Industries.jsx:267` — `industryMergers.length > 6` scroll threshold

Extract as named constants.

### 6.3 No Test Suite

The codebase has no automated tests. Given the data transformation pipeline, unit tests for:
- Date parsing (`date_utils.py`)
- Filename sanitization (`extract_mergers.py`)
- HTML parsing edge cases
- Business day calculations (`generate_static_data.py`)
- Waiver detection logic

...would significantly improve reliability.

### 6.4 LibreOffice Version Not Pinned

**Files:** `convert.yml:50-52`, `all-mergers.yml:111-112`

```yaml
sudo apt-get install -y libreoffice-writer --no-install-recommends
```

Different runner images may install different versions, causing inconsistent PDF conversions.

### 6.5 ESLint Rule Too Broad

**File:** `merger-tracker/frontend/eslint.config.js:26`

`varsIgnorePattern: '^[A-Z_]'` allows any unused variable starting with a capital letter to pass linting.

### 6.6 No Error Reporting Integration

**File:** `merger-tracker/frontend/src/components/ErrorBoundary.jsx`

Errors are only logged to console. No integration with an error tracking service (Sentry, etc.).

---

## Priority Summary

| Priority | Count | Category |
|----------|-------|----------|
| **CRITICAL** | 1 | Security (CORS) |
| **HIGH** | 12 | Security (4), Accessibility (2), Bugs (4), Streamlining (2) |
| **MEDIUM** | 16 | Security (3), Accessibility (3), Bugs (4), Streamlining (3), Other (3) |
| **LOW** | 6 | Various |
| **Enhancements** | 10 | New features and analysis opportunities |

### Recommended Fix Order

1. Hardcoded localhost CORS in Cloudflare Worker
2. Git error handling in CI workflows
3. Circular workflow dependency guards
4. URL validation for attachment downloads
5. Turnstile SRI integrity check
6. Timeline keyboard accessibility
7. Determination date matching bug
8. Merge fetch error handling (Promise.allSettled)
9. Consolidate duplicate pipeline logic
10. Add data validation pipeline
