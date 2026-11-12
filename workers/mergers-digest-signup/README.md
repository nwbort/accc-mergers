# Cloudflare Worker — `mergers-digest-signup`

Handles four endpoints used by the [mergers.fyi](https://mergers.fyi)
frontend:

- `POST /` — weekly-digest email signup. Validates a Cloudflare
  Turnstile token and adds the contact to a Resend audience.
- `POST /app-signup`, `GET /confirm`, `POST /confirm` — the same signup from
  the Android app (`nwbort/accc-mergers-app`), double opt-in instead of
  Turnstile (see below).
- `POST /feedback` — stores feedback submissions in a Cloudflare D1
  database.
- `POST /event` — bumps a privacy-preserving, aggregate-only
  feature-usage counter in D1 (see below).
- `POST /push/topics` — subscribes a browser's Firebase Cloud Messaging
  token to the topics for what it follows, and unsubscribes it from the rest,
  for the site's browser notifications (`src/push.js`; see
  [`docs/android-push.md`](../../docs/android-push.md#browsers)). The token
  and topics go to Google and are not kept. Needs the `FCM_SERVICE_ACCOUNT`
  secret; without it the route answers 503. Unlike the other routes, it also
  answers the site's Cloudflare Pages previews (`mergers-fyi.pages.dev` and
  `*.mergers-fyi.pages.dev`), so notifications can be tried on a branch
  before it ships.

The corresponding admin viewer lives in [`../feedback-admin/`](../feedback-admin/),
which reads from the same `mergers-feedback` D1 database.

## The Android app's signup (double opt-in)

The app isn't a browser, so it can't show Turnstile. `POST /app-signup` with
`{ "email": "..." }` takes no CAPTCHA and adds nobody: it emails the address a
link to confirm, so only someone who can read that inbox can subscribe it, and
the open route can't sign up other people. The link
(`/confirm?t=…&s=…`) opens a page whose form posts back to `/confirm`, which
adds the contact. The page submits that form itself from script once it's
showing, so the reader lands straight on "You're subscribed"; its **Confirm**
button is the fallback without script. Confirming on the GET itself would let
the link scanners in work mail (Outlook Safe Links and the like) subscribe the
reader without them; a scanner that merely fetches the page runs no script and
adds nobody. (One that renders pages with script could still confirm: an
accepted trade for one tap fewer, since the subscriber can unsubscribe from the
first email.)

The link is an HMAC-signed `{email, expiry}` and lasts 7 days; nothing is stored
until it is used. The key is `CONFIRM_SECRET` if that secret is set, otherwise
one derived from `RESEND_API_KEY` (rotating either voids links not yet used).
The email comes from `SEND_FROM` if set as a var, else the digest's own sender.

`npm test` covers it (`test/`, Node's built-in runner, Resend and KV faked).

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
accepted, plus the per-merger follow counters `track_merger_{id}` (e.g.
`track_merger_MN-01016`), matched by `TRACK_MERGER_EVENT_RE`, and the
per-industry follow counters `track_industry_{code}` (e.g.
`track_industry_4520`, `track_industry_F`), matched by
`TRACK_INDUSTRY_EVENT_RE`. To start tracking a new feature's usage:

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
- `POST /app-signup`: 5 requests per 10 minutes per IP; at most one
  confirmation email per address per hour (a repeat is answered as sent, and
  nothing goes out); and 50 confirmation emails a day in all, well under
  Resend's free-plan limit of 100 transactional emails a day.
- `POST /confirm`: 10 requests per 10 minutes per IP.
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

Pushes to `main` that touch this directory deploy it automatically via
`deploy-workers.yml` (see [`../README.md`](../README.md#deploying-from-github)),
so `npm run deploy` is only needed for a deploy outside that.

After deploying, attach a custom domain or route in the Cloudflare
dashboard (see comments in `wrangler.toml`).

## Files

| File | Purpose |
| --- | --- |
| `src/index.js` | Worker entry point — signup, feedback and event handlers, CORS, Turnstile verification. |
| `schema.sql` | D1 schema for the `feedback` and `feature_events` tables. |
| `wrangler.toml` | Worker config, D1 binding, env vars. |
