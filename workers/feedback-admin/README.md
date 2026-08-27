# `feedback-admin`

Tiny private admin viewer for feedback submissions captured by the public
[`mergers-digest-signup`](../mergers-digest-signup/) Worker (`POST /feedback`).

Two pieces:

- `src/index.js` — Cloudflare Worker that exposes `GET /feedback`, gated
  behind an `x-secret` header, returning rows from the shared
  `mergers-feedback` D1 database.
- `ui/index.html` + `ui/app.js` — standalone single-page UI that prompts
  for the worker URL and the secret, then renders submissions in a table.
  It is *not* served by the Worker; open it locally or host it anywhere
  static.

## Deploy

```bash
wrangler secret put SECRET   # any opaque string; must match the UI input
wrangler deploy
```

The D1 binding (`DB`) points to the same `mergers-feedback` database used
by `mergers-digest-signup` — `database_id` is duplicated in both
`wrangler.toml` files, so change one and change the other. Open
`ui/index.html` locally (or host it anywhere static) and paste the worker
URL plus the secret to view feedback.
