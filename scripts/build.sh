#!/usr/bin/env bash
set -euo pipefail

# Cloudflare Pages build script
# Set this as the build command in the Cloudflare dashboard:
#   bash scripts/build.sh
#
# Root directory (in dashboard): /  (repo root)
# Build output (in dashboard):   merger-tracker/frontend/dist

FRONTEND_DIR="merger-tracker/frontend"
DATA_DIR="data/raw/matters"

# 1. Install and build the frontend
# --no-audit/--no-fund drop two registry round-trips whose output nobody reads
# here; `npm audit` still runs in CI and locally.
cd "$FRONTEND_DIR"
npm ci --no-audit --no-fund
npm run build

# 2. Copy PDF files from data/raw/matters into the build output
# so they're served at /mergers/<matter-path>/<file>.pdf
#
# The PDFs are ~140 MB across ~790 files, so this is done as one batched
# `cp --parents` rather than a mkdir+cp per file, and as hard links where the
# filesystem allows it — dist/ and the data dir live in the same checkout, and
# nothing mutates either tree between here and the asset upload, so a link is
# equivalent to a copy while skipping the bulk data write entirely.
#
# The destination is shared with the prerendered merger pages
# (dist/mergers/<id>/<slug>/index.html), so this step must only ever add files
# to dist/mergers — never clear it.
data_root="$(cd "../../$DATA_DIR" 2>/dev/null && pwd -P)" || data_root=""
if [ -n "$data_root" ]; then
  dest="$PWD/dist/mergers"
  mkdir -p "$dest"

  # Probe hard-link support once, up front, so the copy itself can't fail
  # halfway and leave a half-linked tree behind.
  cp_opts=(--parents)
  probe=$(find "$data_root" -type f -name "*.pdf" -print -quit)
  if [ -n "$probe" ] && ln "$probe" "$dest/.hardlink-probe" 2>/dev/null; then
    cp_opts=(-l --parents)
  fi
  rm -f "$dest/.hardlink-probe"

  # `cp --parents` recreates each file's path relative to the current
  # directory, so run it from the data dir to get <matter-path>/<file>.pdf.
  (cd "$data_root" && find . -type f -name "*.pdf" -exec cp "${cp_opts[@]}" -t "$dest" {} +)
  echo "Copied PDFs from $DATA_DIR into dist/mergers/"
else
  echo "Warning: $DATA_DIR not found, skipping PDF copy"
fi
