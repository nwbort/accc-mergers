# The API

A single endpoint for clients who want the register as data rather than as a
website: every merger, as the site's own list carries it, plus a condensed
pre-notification estimate.

```
GET https://mergers.fyi/data/api/v1/mergers
Authorization: Bearer mfyi_live_…
```

**For now it is open:** `API_REQUIRE_KEY = "false"` in the root
`wrangler.toml`, so no key is needed. See [Requiring a key](#requiring-a-key)
to switch the gate on.

Nothing new is deployed to serve it. The data is a static file the pipeline
already commits, and one Pages Function (`functions/data/api/[[path]].js`)
sits in front of it, checks the key (when one is required) and counts the
request. Keys and counts
live in the `mergers-feedback` D1 database the signup Worker and
`feedback-admin` already share.

## For clients

### Request

| | |
|---|---|
| URL | `https://mergers.fyi/data/api/v1/mergers` (no extension; the `.json` name is a `404`) |
| Method | `GET` (or `HEAD`) |
| Auth | `Authorization: Bearer <key>`, or `?key=<key>` on the URL for clients that can only set a URL (a spreadsheet's web import, say). The header wins if both are sent. Not needed while the API is open, but worth sending: it is accepted then too, and it keeps working once a key is required. Email contact@mergers.fyi for a key |
| Freshness | The file can change whenever the pipeline runs (several times a weekday). `updated_at` in the body says when its content last changed. Send the previous response's `ETag` back as `If-None-Match` and an unchanged file comes back as a bodiless `304`. |

```bash
curl -H "Authorization: Bearer $MERGERS_FYI_KEY" \
  https://mergers.fyi/data/api/v1/mergers

# or, where only a URL can be set
curl "https://mergers.fyi/data/api/v1/mergers?key=$MERGERS_FYI_KEY"
```

Prefer the header where you can: a key in a URL tends to end up in proxy
logs, shell history and browser history. The key never travels past the key
check — the static file is fetched without the query string.

A refused request (`401`) says what to do next:

```json
{"error":"An API key is required. Email contact@mergers.fyi to request one, then send it as \"Authorization: Bearer <key>\" or append ?key=<key> to the URL.","request_a_key":"mailto:contact@mergers.fyi"}
```

An unknown or revoked key gets `"Invalid or revoked API key. Email
contact@mergers.fyi if you need a new one."` with the same `request_a_key`.
The address is `KEY_CONTACT` in `functions/data/api/[[path]].js`.

| Status | Meaning |
|---|---|
| `200` | The data |
| `304` | Unchanged since the `ETag` you sent |
| `401` | Missing, unknown or revoked key (only while a key is required) |
| `404` | No such endpoint under `/data/api/` |
| `503` | The key check couldn't be made; retry later (only while a key is required) |

### Response

```json
{"version":"v1","updated_at":"2026-11-19T03:12:45Z","licence":"CC BY 4.0 (…)","attribution":"mergers.fyi (…)","mergers":[
{"merger_id":"MN-40039", "merger_name":"…", "status":"…", "pre_notification":{"kind":"around","start_date":"2026-09-14","confidence":"high"}, …},
…
]}
```

`updated_at` (UTC) is when anything in the response last changed: a matter on
the register, or one of mergers.fyi's own readings of it, such as a refined
pre-notification estimate. It is not when the file was last regenerated; a run
that changes nothing leaves it, and the whole file, as it was.

Matters are ordered most recently updated first, as the site's "Last updated"
sort orders them: by `latest_event_date` (when the matter itself last changed),
newest first, with `page_modified_datetime` ordering matters updated on the
same day. The page's modified time never outranks a newer event, so an old
matter whose page the ACCC merely reformatted stays where it was.

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

## Requiring a key

`API_REQUIRE_KEY` in the root `wrangler.toml` is the switch. It is `"false"`
for now, which opens the API to anyone. Anything else, including deleting the
line, requires a key, so the gate can't be dropped by a typo. To switch it on,
set it to `"true"`, merge, and the next Pages deploy enforces it. Hand clients
their keys first: anyone without one starts getting `401`s.

While it is open:

- a valid key is still credited to its client in the usage counts, so clients
  who already send one show up by name;
- a request with no key, or an invalid or revoked one, is served and counted
  as `(open)`;
- it works without the D1 tables or binding: counting is skipped or fails
  quietly, and the data is served regardless.

## What is tracked

One row per label per Sydney day: `api_usage(label, day, count)`. Every
request served adds one, `304`s included, under the client's label when it sent
a valid key and `(open)` when the API is open and it didn't. While a key is
required, refused requests are counted together under `(rejected)`. No IP
address, user agent, URL or per-request record is kept. Totals across all clients, with errors, are also in the Cloudflare
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
   `wrangler.toml` on its next deploy. While the API is open it serves either
   way; once a key is required, it answers `503` until both steps are done —
   it fails closed and never serves the data ungated.
3. Redeploy `feedback-admin` (`npm run deploy` in its directory) for the usage
   view.
4. `npm run api-key:create -- <client>`, then, when you want the gate, set
   `API_REQUIRE_KEY = "true"` (above).

## How it fits together

- `scripts/generate/static_data/outputs/api.py` writes
  `frontend/public/data/api/v1/mergers.json` (served as `/data/api/v1/mergers`) on every `generate_static_data`
  run, from the same entries as `mergers/list.json`. The pre-notification
  summary is the site's own reading (`getPreNotificationEstimate` in
  `frontend/src/utils/preNotification.js`), hand-copied to Python and pinned to
  it by `fixtures/pre-notification-summary-cases.json`, which both test suites
  read.
- `updated_at` comes from `data/processed/api_updated.json`: a hash of the
  rest of the response and the time it was first seen. The generator restamps
  only when the hash changes, and the pipeline commits the file with the rest
  of `data/processed/`. Deleting it restamps the API with the next run's time.
- `functions/data/api/[[path]].js` answers every path under `/data/api/`,
  serving an extensionless endpoint from the `.json` file of the same name.
  Pages runs a Function before a static file at the same path, so the file is
  never reachable without it (its own `.json` URL is a `404`);
  `env.ASSETS.fetch` then serves the file without re-entering the Function. Tested in
  `frontend/src/utils/__tests__/apiFunction.test.js`.
- The raw `pre_notification` block (its bounds and the matters that witness
  them) is still in each public `mergers/{id}.json`, because the site's detail
  page reads it. The API doesn't hide that; it gives clients a documented,
  stable reading of it instead.
