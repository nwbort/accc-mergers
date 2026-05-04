# Cloudflare Pages Functions

[Pages Functions](https://developers.cloudflare.com/pages/functions/)
that run on the same project that serves the React SPA. They intercept
specific URLs before falling through to the static asset bundle.

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
