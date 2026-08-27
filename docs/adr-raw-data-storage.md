# ADR: Storage of raw scraped data (`data/raw/`)

- **Status:** Proposed
- **Date:** 2026-07-07
- **Spec:** item 30 in [repo-review-specs.md](repo-review-specs.md)
- **Decision:** Adopt Option A (orphan `raw-data` branch) as a follow-up
  implementation item; apply Option C's partial-clone guidance immediately;
  defer Option B (Cloudflare R2) unless Pages platform limits start to bite.

This ADR is investigation only — nothing in the repo's behaviour changes with
this document. Implementation is a separate follow-up item.

## Context

`data/raw/matters/` holds the scraped ACCC register pages and their attachment
documents. It lives in the same repository whose pushes to `main` trigger
Cloudflare Pages deploys, and it only ever grows: matter pages are re-scraped
in place, but every attachment (PDF/DOCX) is kept forever.

### Measured size and growth

Measured at commit `3b282fd` (2026-07-07). The directory first appeared on
2026-01-20, when the new merger regime data started flowing.

| Date | `data/raw` (git tree bytes) | Files |
|------------|------|-------|
| 2026-02-01 | 12 MB | 102 |
| 2026-03-01 | 28 MB | 240 |
| 2026-04-01 | 49 MB | 404 |
| 2026-05-01 | 77 MB | 610 |
| 2026-06-01 | 104 MB | 843 |
| 2026-07-06 | 136 MB | 1,213 |

That is roughly **22 MB and 200 files per month**, with no natural ceiling.
The on-disk breakdown today: 103 MB of PDFs (622 files), 18 MB of DOCX (170),
15 MB of HTML (421). The DOCX files are the originals of converted PDFs; the
HTML files are re-scraped in place and churn on every pipeline run.

Of the full-history pack (~119 MB of packed blobs), `data/raw` accounts for
51.5 MB — the single largest contributor, though not the only one
(`data/output` 35.5 MB and `data/processed` 15.7 MB churn on every pipeline
run and delta-compress less well over time).

### Measured clone times

Fresh clones of `github.com/nwbort/accc-mergers` from a datacenter-hosted
container (2026-07-07). Treat these as relative comparisons — a residential
connection will be slower across the board.

| Clone variant | Time | `.git` size | Worktree |
|---|---|---|---|
| Full (`git clone`) | 14.8 s | 121 MB | 184 MB |
| Blobless (`--filter=blob:none`) | 6.0 s | 56 MB | 184 MB |
| Shallow (`--depth=1`, what `actions/checkout` does) | 5.4 s | 54 MB | 184 MB |
| Blobless + sparse-checkout excluding `data/raw` | 3.1 s | 9 MB | 44 MB |

The honest read: clone pain today is **modest** (15 s worst case), but growth
is monotonic — at the measured rate the worktree grows ~260 MB/year and the
full-history pack ~120 MB/year, and every Actions job and Pages build pays
the download on every run.

## How PDFs get into the deployed site (verified)

This is the load-bearing dependency any move must preserve. The full path,
verified against the current code:

1. `pipeline.yml` scrapes matter pages into `data/raw/matters/` and
   `extract_mergers.py` downloads attachments into per-matter directories
   (`data/raw/matters/MN-XXXXX/…`). DOCX attachments are converted to PDF by
   LibreOffice in the same run. Everything is committed to `main`
   (`git add … data/raw/matters/ …`) and pushed.
2. The push to `main` triggers a Cloudflare Pages build (git integration),
   which runs `bash scripts/build.sh` from the repo root.
3. `scripts/build.sh` runs `npm ci && npm run build`, then **copies every
   `*.pdf` under `data/raw/matters/` into
   `frontend/dist/mergers/`**, preserving the per-matter
   directory structure. The PDFs thereby become static assets of the deployed
   site at `/mergers/{id}/{file}.pdf`. HTML and DOCX files are *not* copied —
   only PDFs ever ship.
4. The Pages Function `functions/mergers/[matter]/[[path]].js` intercepts all
   `*.pdf` requests under `/mergers/`:
   - `?raw=1` requests and mobile user agents get the raw PDF via
     `env.ASSETS.fetch(...)` — i.e. **served from the static assets copied in
     step 3**.
   - Desktop browsers get an HTML viewer page whose embedded `<object>` loads
     the same URL with `?raw=1`, which again resolves through
     `env.ASSETS.fetch`.

So `env.ASSETS.fetch` only works because the build copied the PDFs out of
`data/raw` into the build output. Any option that removes `data/raw` from the
checkout that Cloudflare Pages builds from must either put the PDFs back at
build time (Option A) or replace `env.ASSETS.fetch` with a different origin
(Option B).

(The same function also uses `env.ASSETS.fetch` to read merger JSON for bot
OG pages; that data comes from `frontend/public/data/` and is
unaffected by any option here.)

### Everything else that touches `data/raw`

| Consumer | Access |
|---|---|
| `scripts/scrape.sh` | writes/re-cleans matter HTML |
| `scripts/extract_mergers.py` | reads **all** matter HTML each run; downloads attachments |
| `scripts/parse_questionnaire.py`, `scripts/parse_nocc.py` | read PDFs during extraction |
| `pipeline.yml`, `extract.yml`, `convert.yml`, `scrape.yml` | shallow-checkout the repo, read/write/commit `data/raw/matters/` |
| `scripts/build.sh` (Cloudflare Pages) | copies PDFs into build output |

Note the extraction step re-parses *all* matter HTML on every run, so the raw
HTML must remain persistently available to pipeline jobs — it cannot simply be
re-scraped on demand (the cutoff logic deliberately stops re-fetching old
matters, and hammering the ACCC site defeats the point of the cache).

## Options

### Option A — orphan `raw-data` branch

Move `data/raw/` to a dedicated `raw-data` branch (branch root = contents of
`data/raw`, i.e. `matters/` at the top level). Pipeline jobs check it out at
the pinned path `data/raw` via a second `actions/checkout` step with `ref:
raw-data` and `path: data/raw`; the Pages build fetches it in `build.sh`. The
repo already proves this pattern with the `cli-dist` orphan branch that
`pipeline.yml` force-pushes `cli.sqlite` to.

**Workflow changes**

- `pipeline.yml` / `extract.yml` / `convert.yml` / `scrape.yml`: add a second
  checkout (`ref: raw-data`, `path: data/raw`, depth 1); commit and push raw
  changes to `raw-data` *before* pushing processed changes to `main` (so a
  deploy never references a PDF that isn't on `raw-data` yet). The existing
  `concurrency: pipeline-main` group already serialises runs, so the two-push
  sequence doesn't add a new race beyond today's rebase handling.
- `scripts/build.sh`: before the PDF copy, fetch the branch (the repo is
  public, so no credentials are needed in the Pages build):
  `git clone --depth=1 --branch raw-data https://github.com/nwbort/accc-mergers …`
  — roughly the same bytes the Pages clone downloads today, so build time is
  approximately neutral.
- `main`: `git rm -r --cached data/raw && echo 'data/raw/' >> .gitignore` in
  one commit. **No history rewrite** — rewriting would invalidate every clone,
  open PR and issue permalink to save ~50 MB of pack; the win accrues to
  future history instead.
- Local dev: one-liner helper (or documented command) to populate `data/raw`
  from the branch.

**Branch history policy.** Two sub-options: force-push a single commit each
run (like `cli-dist` — remote stays ~worktree-sized forever but scrape history
is lost), or append normally (keeps the audit trail of how matter pages
changed; growth continues but is quarantined on a branch every consumer
fetches at depth 1, so nobody pays for it). Recommend **append**, revisit if
the branch itself becomes a hosting concern.

**Effects**

- `main` clones/checkouts stop growing with scraped data; a blobless+sparse
  dev clone is ~9 MB of `.git` instead of 56–121 MB.
- Raw-only commits (e.g. HTML re-clean churn with no data change) stop
  triggering pointless Pages deploys. Edge case: a new PDF whose extraction
  produces *no* processed-JSON change would sit on `raw-data` undeployed until
  the next `main` push — in practice a new attachment always changes the
  matter's JSON (attachment lists), and the pipeline pushes both together.
- No new infrastructure, credentials, or billing surface. Everything stays
  version-controlled in one repo.

**Rollback.** `git checkout raw-data -- .` into `data/raw` on `main`, commit,
revert the workflow/`build.sh`/`.gitignore` changes, delete the branch. All
data is still in git; nothing is destroyed by migrating or rolling back.

### Option B — Cloudflare R2

Store documents in an R2 bucket; the pipeline syncs new files up
(`rclone`/`wrangler r2 object put`) and the site serves PDFs from R2 instead
of static assets.

**Workflow changes**

- `pipeline.yml`: add an R2 sync step and an R2 API token as a repo secret.
  Sync must complete before the `main` push (same ordering argument as A).
- `scripts/build.sh`: drop the PDF copy step entirely.
- `functions/mergers/[matter]/[[path]].js`: **rework required** — the two
  `env.ASSETS.fetch` PDF paths (raw/mobile) become an R2 binding read
  (`env.RAW_DOCS.get(key)`), with the binding declared in `wrangler.toml`.
  The function must decode the URL path to the object key (filenames contain
  spaces — e.g. `Asahi warehouse lease - Determination - September 5.pdf`),
  set `Content-Type: application/pdf` and cache headers itself, and handle
  missing objects as 404s. Preview deployments and `wrangler pages dev` need
  the binding configured too.
- The raw **HTML** cannot move to R2 without extra plumbing: extraction
  re-reads all matter HTML every run, so the pipeline would need a
  download-from-R2 step at job start (and upload at end) — R2 becomes a
  second source of truth that git no longer versions. Alternatively HTML/DOCX
  (33 MB) stay in git and only PDFs (103 MB) move, which halves the benefit
  to the repo.

**Effects**

- Removes PDFs from the repo *and* from every deploy upload; sidesteps the
  Pages per-deployment limits (20,000 files / 25 MiB per file) permanently.
  For scale: the current deploy ships ~3,900 files and the largest PDF is
  under 10 MiB, so those limits are years away at current growth — real, but
  not pressing.
- Free tier (10 GB storage, free egress) covers this comfortably; still a new
  billing/credentials/monitoring surface, a sync that can drift from the
  deploy, and the loss of git versioning for whatever moves.

**Rollback.** Objects mirror `data/raw/matters/` paths, so restore is
`rclone copy` back into the repo, revert the function/build/workflow changes.
Keep the git copy until the R2 setup has proven itself to make this trivial.

### Option C — status quo + clone hygiene

Keep everything in the repo; document the cheap mitigations:

- Dev clones: `git clone --filter=blob:none` (56 MB) — or add
  `--sparse` + `git sparse-checkout set --no-cone '/*' '!data/raw'` when the
  raw files aren't needed (9 MB `.git`, 44 MB worktree, 3 s).
- CI already uses depth-1 checkouts (`actions/checkout` default), so `git gc`
  offers nothing server-side; there is no local action that shrinks what
  GitHub serves.

Zero effort and zero risk now, but the underlying curve is untouched: every
Actions run and Pages build downloads ~184 MB and grows ~22 MB/month, and
GitHub's soft repository-size guidance (~1 GB) is on the horizon in a few
years. This is a deferral, not a fix — though the measured pain today is
small enough that deferring is a legitimate choice.

## Comparison

| | A: orphan branch | B: R2 | C: status quo |
|---|---|---|---|
| Removes growth from `main` | ✅ (quarantined on branch) | ✅ PDFs (HTML needs extra work) | ❌ |
| New infrastructure/secrets | none | bucket + API token + binding | none |
| Pages Function rework | none | required (`env.ASSETS` → R2 binding) | none |
| `build.sh` change | fetch branch | drop copy step | none |
| Data stays git-versioned | ✅ | ❌ (for moved files) | ✅ |
| Precedent in repo | `cli-dist` | none | — |
| Effort | low–medium | medium–high | none |
| Rollback | trivial, lossless | easy while git copy retained | — |

## Decision

**Adopt Option A** as the follow-up implementation item: it is the only
option that fixes the growth problem for near-zero new operational surface,
it reuses a pattern this repo already runs in production (`cli-dist`), and
its rollback is lossless. **Do not rewrite `main`'s history** as part of it.

**Immediately** (no code change): document Option C's
blobless/sparse-checkout commands as the recommended way to clone for
development — they make the current pain nearly free while A is pending.

**Defer Option B.** It is the right long-term shape if the deployment ever
approaches the Pages file-count limit or the site needs documents that don't
ship well as build assets, and adopting A first makes a later A→B migration
no harder (the sync source just changes from a branch to a checkout).

### Migration steps (for the follow-up item)

1. Create the `raw-data` branch: orphan commit whose root is the current
   contents of `data/raw/` (i.e. `matters/` at top level); push.
2. Update `build.sh` to depth-1-clone `raw-data` into place before the PDF
   copy; verify a Pages preview deploy serves an existing PDF at
   `/mergers/{id}/{file}.pdf` both raw (`?raw=1`) and via the viewer.
3. Update `pipeline.yml`, `extract.yml`, `convert.yml`, `scrape.yml` to
   checkout `raw-data` at `data/raw` and push raw changes there **before**
   the `main` push.
4. Remove `data/raw` from `main` (`git rm -r --cached`, `.gitignore` entry) —
   only after 2–3 are verified.
5. Update docs (`CLAUDE.md`, `docs/deployment.md`, `data/README.md`,
   `scripts/README.md`) and add the local-dev fetch helper.
6. Watch one full scheduled pipeline cycle end-to-end (scrape → convert →
   commit → deploy → PDF served) before closing.

Rollback at any point: restore `data/raw` on `main` from the branch and
revert the workflow/build changes (see Option A above).
