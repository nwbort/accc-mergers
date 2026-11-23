# Cloudflare Pages Functions

[Pages Functions](https://developers.cloudflare.com/pages/functions/)
that run on the same project that serves the React SPA. They intercept
specific URLs before falling through to the static asset bundle.

These are **not** standalone Workers — those live under
[`workers/`](../workers/), one directory each. This directory has to stay at
the repository root because Pages resolves `functions/` relative to the build
root (see the root `wrangler.toml`), and because frontend tests (the slug and
`og_card` sync checks in `slug.test.js` and `pageMeta.test.js`, and
`pdfViewerFunction.test.js`) import `mergers/[matter]/[[path]].js` by a
relative path into this directory.

## Routes

| Path | File | Behaviour |
| --- | --- | --- |
| `/` | `index.js` | The homepage, served from the copy `frontend/prerender.js` stamps at `/prerendered/home` (canonical, title, JSON-LD and a body in the raw HTML). `dist/index.html` can't carry those itself: it is also the SPA fallback for every URL without a file of its own, so it would say them for all of those too. Drops the copy's `X-Robots-Tag: noindex` (set in `public/_headers` so its own URL isn't indexed) and keeps its `ETag`, forwarding the client's `If-None-Match` for `304`s. Falls back to the plain shell if the copy is missing or anything fails. |
| `/mergers/{mn,wa}-NNNNN[/...]` (lower-case ID) | `mergers/[matter]/[[path]].js` | `301` to the same URL with the matter ID upper-cased (the rest of the path untouched), before any other handling. |
| `/mergers/{MN,WA}-NNNNN[/<slug>]` (link-preview bots only) | `mergers/[matter]/[[path]].js` | A minimal page of Open Graph tags for the matter, with `og:image` pointing at its generic milestone card in `/og/` (the detail file's `og_card`, else the shared `og-image.png`). Everyone else falls through to the SPA. |
| `/mergers/{MN,WA}-NNNNN/<file>.pdf` | `mergers/[matter]/[[path]].js` | Wraps the underlying PDF in a custom viewer (`_lib/pdf-viewer.js`) on desktop browsers. Mobile UAs and `?raw=1` requests get the raw PDF straight from `env.ASSETS`; if that doesn't come back as a PDF (documents over Pages' 25 MiB limit are left out of the deployment by `scripts/build.sh`), it `302`s to the document's source URL from the matter's event data. Every form checks the file first: a byte-identical duplicate the pipeline deleted (listed in its event's `retired_url_gh`; see `scripts/document_versions.py`) `302`s to the copy that replaced it, keeping `?raw`; an undeployed document with a source URL `302`s there, and a path matching neither gets a `404` "Document not found" page in the viewer's chrome, linking back to the matter (or to `/mergers` if the matter doesn't exist) — rather than the SPA shell, which would read the filename as a slug and silently land on the matter page. |
| `/data/api/**` | `data/api/[[path]].js` | The API ([`docs/api.md`](../docs/api.md)). Serves each extensionless endpoint (`/data/api/v1/mergers`) from the `.json` file of the same name through `env.ASSETS` (`304` against the client's `ETag`); a `.json` URL itself is a `404`, as is any path Pages would answer with the SPA shell. When `API_REQUIRE_KEY` (root `wrangler.toml`) is anything but `"false"`, checks `Authorization: Bearer <key>` against `api_keys` in D1 (`API_DB`): `401` for a missing, unknown or revoked key, `503` — never the data — when the database isn't bound or can't be read. Counts every request served in `api_usage`. |

## Files

- `index.js` — serves the prerendered homepage at `/`. Tested in
  `frontend/src/utils/__tests__/homeFunction.test.js`.
- `_lib/pdf-viewer.js` — Shared HTML/CSS for the PDF viewer banner
  (back link, document name, download button).
- `data/api/[[path]].js` — serves (and, when switched on, gates) the API. Tested in
  `frontend/src/utils/__tests__/apiFunction.test.js`.
- `mergers/[matter]/[[path]].js` — Pages Function entry point. Uses
  `[[path]]` to capture nested filenames under a matter directory.

Functions are deployed automatically by Cloudflare Pages alongside the
frontend; no separate build step.
