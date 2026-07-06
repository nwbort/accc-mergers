# Cloudflare Worker — `mergers-digest-signup`

Handles two endpoints used by the [mergers.fyi](https://mergers.fyi)
frontend:

- `POST /` — weekly-digest email signup. Validates a Cloudflare
  Turnstile token and adds the contact to a Resend audience.
- `POST /feedback` — stores feedback submissions in a Cloudflare D1
  database.

The corresponding admin viewer lives in [`../feedback-admin/`](../feedback-admin/).

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

Both endpoints enforce a per-IP fixed-window limit using the `RATE_LIMIT_KV`
namespace (keyed on `CF-Connecting-IP`), on top of Turnstile:

- `POST /` (signup): 5 requests per 10 minutes per IP.
- `POST /feedback`: 5 requests per 10 minutes per IP, plus a 20-per-day cap
  to bound D1 row growth from a single IP.

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
| `src/index.js` | Worker entry point — signup + feedback handlers, CORS, Turnstile verification. |
| `schema.sql` | D1 schema for the `feedback` table. |
| `wrangler.toml` | Worker config, D1 binding, env vars. |
