# The key-gated API

A single endpoint for clients who want the register as data rather than as a
website: every merger, as the site's own list carries it, plus a condensed
pre-notification estimate.

```
GET https://mergers.fyi/data/api/v1/mergers.json
Authorization: Bearer mfyi_live_…
```

Nothing new is deployed to serve it. The data is a static file the pipeline
already commits, and one Pages Function (`functions/data/api/[[path]].js`)
sits in front of it, checks the key and counts the request. Keys and counts
live in the `mergers-feedback` D1 database the signup Worker and
`feedback-admin` already share.

## For clients

### Request

| | |
|---|---|
| URL | `https://mergers.fyi/data/api/v1/mergers.json` |
| Method | `GET` (or `HEAD`) |
| Auth | `Authorization: Bearer <key>` |
| Freshness | The file changes when the pipeline runs (several times a weekday). Send the previous response's `ETag` back as `If-None-Match` and an unchanged file comes back as a bodiless `304`. |

```bash
curl -H "Authorization: Bearer $MERGERS_FYI_KEY" \
  https://mergers.fyi/data/api/v1/mergers.json
```

| Status | Meaning |
|---|---|
| `200` | The file |
| `304` | Unchanged since the `ETag` you sent |
| `401` | Missing, unknown or revoked key |
| `404` | No such file under `/data/api/` |
| `503` | The key check couldn't be made; retry later |

### Response

```json
{"version":"v1","licence":"CC BY 4.0 (…)","attribution":"mergers.fyi (…)","mergers":[
{"merger_id":"MN-40039", "merger_name":"…", "status":"…", "pre_notification":{"kind":"around","start_date":"2026-09-14","confidence":"high"}, …},
…
]}
```

Each entry is exactly what the site's merger list (`mergers/list.json`)
carries, plus `pre_notification`:

| Field | |
|---|---|
| `merger_id` | ACCC identifier (`MN-…` notification, `WA-…` waiver) |
| `merger_name` | As on the register |
| `status`, `stage` | The register's status and stage |
| `accc_determination`, `has_conditions` | The outcome, once decided |
| `is_waiver` | A waiver application rather than a notification |
| `under_appeal`, `appeal` | Australian Competition Tribunal review (`appeal` only when there is one) |
| `under_judicial_review` | Federal Court review; present only while true |
| `materially_incomplete` | Notification held materially incomplete; present only while true |
| `reached_phase_2` | Went to Phase 2 even though the stage no longer says so; present only while true |
| `is_refiled` | Later re-filed as a separate matter |
| `effective_notification_datetime`, `determination_publication_date`, `end_of_determination_period` | Register dates (stored at midday UTC; read the date part) |
| `latest_event_date`, `page_modified_datetime` | When the matter last changed |
| `acquirers`, `targets`, `other_parties` | `[{name, canonical?: {name}}]` |
| `anzsic_codes` | `[{code, name}]` |
| `pre_notification` | See below; `null` for waivers, voluntary-period notifications (before 1 Jan 2026) and matters with no estimate |

`pre_notification` is mergers.fyi's estimate of when the matter's
pre-notification engagement with the ACCC began, inferred from the order case
numbers were issued in — it is never on the public register.

| `kind` | `start_date` reads as |
|---|---|
| `around` | Approximately this date |
| `after` | No earlier than this date (only a floor is known) |
| `before` | No later than this date (only a ceiling is known) |
| `none` | No pre-notification period was detectable; `start_date` is `null` |

`confidence` is `high` when the start is pinned to within about a fortnight,
`medium` within six weeks, and `low` otherwise or whenever only one bound is
known.

### Stability

`v1` only grows: fields may be added, never renamed, retyped or removed. A
breaking change would be a new `v2` path alongside it. The set of `v1` fields is
pinned by `API_ENTRY_KEYS` in `scripts/generate/static_data/outputs/api.py`,
and `scripts/tests/test_api_output.py` fails if the site's list changes it.

## Administration

Everything runs from `workers/feedback-admin/` with the same Cloudflare login
used to deploy it. Add `--local` to any command to try it against `wrangler
dev`'s local database.

```bash
cd workers/feedback-admin
npm run api-key:create -- smith-legal      # prints a new key once
npm run api-key:list                        # every key, created/revoked, usage
npm run api-key:revoke -- smith-legal       # revoke all the client's keys
npm run api-usage                           # per-day counts, last 30 days
npm run api-usage -- --days 90
```

- **Issuing.** The key is printed once and only its SHA-256 is stored, with
  its first few characters (`mfyi_live_3f9a1c`) as a hint. Send it over
  something better than plain email if you can. A lost key is revoked and
  reissued, never recovered.
- **Revoking** takes effect on the next request. The row is kept, marked
  revoked, so its history stays readable.
- **Rotating.** Create a second key under the same label, hand it over, then
  revoke the old one by its hint: `npm run api-key:revoke -- smith-legal --key
  mfyi_live_3f9a1c`. Usage is counted per label, so it carries across.
- **Usage** is also on the `feedback-admin` UI (`ui/index.html`), under *API
  usage*: each key, and per-client daily counts for the last 90 days.

## What is tracked

One row per client per Sydney day: `api_usage(label, day, count)`. Every
request that passes the key check adds one, `304`s included. Requests with a
missing, unknown or revoked key are counted together under `(rejected)`. No IP
address, user agent, URL or per-request record is kept, and the privacy policy
says so. Totals across all clients, with errors, are also in the Cloudflare
dashboard under the Pages project's Functions metrics.

There is no rate limit. With a handful of known clients the daily count shows
abuse and revoking ends it; a Cloudflare rate-limiting rule on
`/data/api/*` can be added later without code changes.

## One-time setup

1. Create the tables in the real database (idempotent):

   ```bash
   cd workers/mergers-digest-signup
   npx wrangler d1 execute mergers-feedback --remote --file=schema.sql
   ```

2. Merge. The Pages project picks up the `API_DB` binding from the root
   `wrangler.toml` on its next deploy. Until both steps are done the endpoint
   answers `503` — it fails closed and never serves the file ungated.
3. Redeploy `feedback-admin` (`npm run deploy` in its directory) for the usage
   view.
4. `npm run api-key:create -- <client>`.

## How it fits together

- `scripts/generate/static_data/outputs/api.py` writes
  `frontend/public/data/api/v1/mergers.json` on every `generate_static_data`
  run, from the same entries as `mergers/list.json`. The pre-notification
  summary is the site's own reading (`getPreNotificationEstimate` in
  `frontend/src/utils/preNotification.js`), hand-copied to Python and pinned to
  it by `fixtures/pre-notification-summary-cases.json`, which both test suites
  read.
- `functions/data/api/[[path]].js` answers every path under `/data/api/`. Pages
  runs a Function before a static file at the same path, so the file is never
  reachable without it; `env.ASSETS.fetch` then serves the file without
  re-entering the Function. Tested in
  `frontend/src/utils/__tests__/apiFunction.test.js`.
- The raw `pre_notification` block (its bounds and the matters that witness
  them) is still in each public `mergers/{id}.json`, because the site's detail
  page reads it. The API doesn't hide that; it gives clients a documented,
  stable reading of it instead.
