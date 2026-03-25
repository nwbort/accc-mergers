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

# 1. Build the frontend
cd "$FRONTEND_DIR"
npm run build

# 2. Copy PDF files from data/raw/matters into the build output
# so they're served at /mergers/<matter-path>/<file>.pdf
if [ -d "../../$DATA_DIR" ]; then
  find "../../$DATA_DIR" -type f -name "*.pdf" | while IFS= read -r f; do
    rel="${f#../../$DATA_DIR/}"
    mkdir -p "dist/mergers/$(dirname "$rel")"
    cp "$f" "dist/mergers/$(dirname "$rel")/"
  done
  echo "Copied PDFs from $DATA_DIR into dist/mergers/"
else
  echo "Warning: $DATA_DIR not found, skipping PDF copy"
fi
