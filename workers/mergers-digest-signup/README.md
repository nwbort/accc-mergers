# Cloudflare Worker — `mergers-digest-signup`

Handles two endpoints used by the [mergers.fyi](https://mergers.fyi)
frontend:

- `POST /` — weekly-digest email signup. Validates a Cloudflare
  Turnstile token and adds the contact to a Resend audience.
- `POST /feedback` — stores feedback submissions in a Cloudflare D1
  database.
- `POST /event` — bumps a privacy-preserving, aggregate-only
  feature-usage counter in D1 (see below).

The corresponding admin viewer lives in [`../feedback-admin/`](../feedback-admin/),
which reads from the same `mergers-feedback` D1 database.

## Feature-usage events

`POST /event` with `{ "type": "..." }` increments a per-day counter in the
`feature_events` D1 table, keyed on `(event_type, day)`. `day` is the
request's date in `Australia/Sydney` local time (not UTC), so it lines up
with the site's Sydney-time audience and stays correct across the DST
transition. No IP, cookie, or other identifier is ever written to that
table — only a running count of how many times an event fired that day — so
the data can never be tied back to an individual visitor. Turnstile isn't
used here (there's no user content to protect), just the same per-IP KV
rate limit as the other routes.

Only event names listed in `ALLOWED_EVENT_TYPES` (`src/index.js`) are
accepted. To start tracking a new feature's usage:

1. Add its event name to `ALLOWED_EVENT_TYPES`.
2. In the frontend, call `pingFeatureEvent('your_event_name')` from
   `frontend/src/utils/trackEvent.js` at the point the feature is used, and
   add the name to `FEATURE_EVENTS` in that file.

No schema change, new endpoint, or new Worker is needed — new event types
just start appearing as new rows. View the counts via `feedback-admin`'s
`/events` endpoint (or its UI), or query D1 directly:

```sql
SELECT * FROM feature_events ORDER BY day DESC, event_type ASC;
```

See [`../README.md`](../README.md) for the index of all Workers.

## Setup

```bash
npm install

# Create the D1 database, copy its id into wrangler.toml
wrangler d1 create mergers-feedback
wrangler d1 execute mergers-feedback --file=schema.sql

# Create the KV namespace used for rate limiting, copy its id into wrangler.toml
wrangler kv namespace create RATE_LIMIT_KV

# Set required secrets
wrangler secret put RESEND_API_KEY
wrangler secret put RESEND_AUDIENCE_ID
wrangler secret put TURNSTILE_SECRET_KEY
```

## Rate limiting

All three endpoints enforce a per-IP fixed-window limit using the
`RATE_LIMIT_KV` namespace (keyed on `CF-Connecting-IP`):

- `POST /` (signup): 5 requests per 10 minutes per IP, plus Turnstile.
- `POST /feedback`: 5 requests per 10 minutes per IP, plus a 20-per-day cap
  to bound D1 row growth from a single IP, plus Turnstile.
- `POST /event`: 60 requests per 10 minutes per IP. No Turnstile — the
  handler only ever increments a counter, it never grows a table per
  request (rows are capped at one per event type per day via an upsert),
  so there's nothing worth gating behind a CAPTCHA.

Requests over the limit get a `429` with the same `{ "error": "..." }` shape
as other validation errors, which the frontend already renders inline.

## Develop and deploy

```bash
npm run dev          # local wrangler dev server
npm run deploy:dry   # build without uploading
npm run deploy       # production deploy
```

After deploying, attach a custom domain or route in the Cloudflare
dashboard (see comments in `wrangler.toml`).

## Files

| File | Purpose |
| --- | --- |
| `src/index.js` | Worker entry point — signup, feedback and event handlers, CORS, Turnstile verification. |
| `schema.sql` | D1 schema for the `feedback` and `feature_events` tables. |
| `wrangler.toml` | Worker config, D1 binding, env vars. |
