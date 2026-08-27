# Cloudflare Pages Functions

[Pages Functions](https://developers.cloudflare.com/pages/functions/)
that run on the same project that serves the React SPA. They intercept
specific URLs before falling through to the static asset bundle.

These are **not** standalone Workers — those live under
[`workers/`](../workers/), one directory each. This directory has to stay at
the repository root because Pages resolves `functions/` relative to the build
root (see the root `wrangler.toml`), and because the frontend's slug-sync test
imports `mergers/[matter]/[[path]].js` by a root-relative path.

## Routes

| Path | File | Behaviour |
| --- | --- | --- |
| `/mergers/{MN,WA}-NNNNN/<file>.pdf` | `mergers/[matter]/[[path]].js` | Wraps the underlying PDF in a custom viewer (`_lib/pdf-viewer.js`) on desktop browsers. Mobile UAs and `?raw=1` requests get the raw PDF straight from `env.ASSETS`. |

## Files

- `_lib/pdf-viewer.js` — Shared HTML/CSS for the PDF viewer banner
  (back link, document name, download button).
- `mergers/[matter]/[[path]].js` — Pages Function entry point. Uses
  `[[path]]` to capture nested filenames under a matter directory.

Functions are deployed automatically by Cloudflare Pages alongside the
frontend; no separate build step.
