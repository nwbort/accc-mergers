# `feedback-admin`

Tiny private admin viewer for feedback submissions and feature-usage
counters captured by the public
[`mergers-digest-signup`](../mergers-digest-signup/) Worker (`POST /feedback`,
`POST /event`).

Two pieces:

- `src/index.js` — Cloudflare Worker that exposes `GET /feedback`,
  `GET /events` and `GET /api-usage` (the key-gated API's keys and daily
  request counts — see [`docs/api.md`](../../docs/api.md)), all gated behind an `x-secret` header, returning rows
  from the shared `mergers-feedback` D1 database.
- `ui/index.html` + `ui/app.js` — standalone single-page UI that prompts
  for the worker URL and the secret, then renders feedback submissions and
  aggregate feature-usage counts in two tables. It is *not* served by the
  Worker; open it locally or host it anywhere static.

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

## API keys

`scripts/api-keys.mjs` issues, revokes and lists keys for the key-gated API
and prints its usage, via `wrangler d1 execute` against the same database:

```bash
npm run api-key:create -- smith-legal   # prints the key once
npm run api-key:list
npm run api-key:revoke -- smith-legal [--key mfyi_live_3f9a1c]
npm run api-usage [-- --days 90]
```

`npm test` covers its key generation, hashing and SQL validation. See
[`docs/api.md`](../../docs/api.md).
