# `feedback-admin`

Tiny private admin viewer for feedback submissions captured by the
public [`cloudflare-worker`](../cloudflare-worker/) (`POST /feedback`).

Two pieces:

- `index.js` — Cloudflare Worker that exposes `GET /feedback`, gated
  behind an `x-secret` header, returning rows from the shared
  `mergers-feedback` D1 database.
- `index.html` — single-page UI that prompts for the worker URL and the
  secret, then renders submissions in a table.

## Deploy

```bash
wrangler secret put SECRET   # any opaque string; must match the UI input
wrangler deploy
```

The D1 binding (`DB`) points to the same `mergers-feedback` database
used by `cloudflare-worker`. Open `index.html` locally (or host it
anywhere static) and paste the worker URL plus the secret to view
feedback.
