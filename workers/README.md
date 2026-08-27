# Cloudflare Workers

Standalone Workers, each deployed on its own with `wrangler` and each
independent of the Cloudflare Pages project that serves the site.

**Every directory here is named after the Worker it deploys** — the
directory name matches `name` in its `wrangler.toml` and the name shown in
the Cloudflare dashboard, so `workers/<name>/` is always where `<name>`
lives.

| Directory | Trigger | What it does |
| --- | --- | --- |
| [`mergers-digest-signup/`](mergers-digest-signup/) | HTTP | Public API for the site: `POST /` (weekly-digest signup via Resend + Turnstile) and `POST /feedback` (writes to the `mergers-feedback` D1 database). |
| [`accc-register-watcher/`](accc-register-watcher/) | Email | Bound to a Cloudflare Email Routing address subscribed to the ACCC register update mailing list. Fires a `repository_dispatch` (`new_merger_detected`) so [`pipeline.yml`](../.github/workflows/pipeline.yml) runs immediately. |
| [`feedback-admin/`](feedback-admin/) | HTTP | Private read-only viewer over the same `mergers-feedback` D1 database, gated behind an `x-secret` header. Ships a standalone static UI in `ui/`. |

## Layout convention

Each Worker directory follows the same shape:

```
workers/<worker-name>/
├── README.md        # what it does, setup, deploy
├── package.json     # pinned wrangler + the standard scripts below
├── wrangler.toml    # name/main/bindings; documents its secrets, never holds them
└── src/
    └── index.js     # entry point (main = "src/index.js")
```

and the same npm scripts, so you never have to look them up:

```bash
npm install
npm run dev          # local wrangler dev server
npm run deploy:dry   # build without uploading
npm run deploy       # production deploy
npm run tail         # stream live logs
```

Secrets are never committed. Each `wrangler.toml` lists the
`wrangler secret put ...` commands its Worker needs in a comment.

## What is *not* here

Two pieces of Cloudflare config have to stay at the repository root and
cannot be moved under `workers/`:

- **`/wrangler.toml`** — the **Pages** project config (`merger-tracker`),
  not a Worker. Wrangler reads it from the project root.
- **`/functions/`** — [Pages Functions](https://developers.cloudflare.com/pages/functions/),
  which run on the Pages project alongside the SPA. Pages requires the
  directory to sit at the build root. See [`functions/README.md`](../functions/README.md).

## Shared state

`mergers-digest-signup` and `feedback-admin` both bind the **same**
`mergers-feedback` D1 database (`database_id` is duplicated in both
`wrangler.toml` files — change one, change the other). The schema lives in
[`mergers-digest-signup/schema.sql`](mergers-digest-signup/schema.sql);
that Worker writes, `feedback-admin` only reads.
