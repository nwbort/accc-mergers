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

# Set required secrets
wrangler secret put RESEND_API_KEY
wrangler secret put RESEND_AUDIENCE_ID
wrangler secret put TURNSTILE_SECRET_KEY
```

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
