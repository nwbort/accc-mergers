#!/usr/bin/env bash
# scripts/generate-cli-data.sh
#
# Generates two files consumed by the accc-mergers-cli companion tool:
#
#   data/output/cli/cli-manifest.json
#     Lightweight version file. The CLI fetches this first to check if its
#     cached bundle is still current, without committing to a full download.
#
#   data/output/cli/cli-bundle.json
#     Complete dataset (all mergers + questionnaires + stats + industries)
#     bundled into a single file. Only downloaded when the manifest's
#     bundle_sha256 differs from the client's cached copy.
#
# These live under data/output/ (not deployed to Cloudflare Pages); the CLI
# fetches them directly from raw.githubusercontent.com.
#
# Usage:
#   ./scripts/generate-cli-data.sh          # no-op if data unchanged
#   ./scripts/generate-cli-data.sh --force  # always regenerate + bump version
#
# Dependencies: jq (>=1.6), python3, sha256sum (Linux) or shasum (macOS)

set -euo pipefail

FORCE=0
[[ "${1:-}" == "--force" ]] && FORCE=1

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Source: the already-generated per-merger frontend data files
SRC_DIR="$REPO_ROOT/merger-tracker/frontend/public/data"
MERGERS_DIR="$SRC_DIR/mergers"
QUESTIONNAIRES_DIR="$SRC_DIR/questionnaires"
STATS_FILE="$SRC_DIR/stats.json"
INDUSTRIES_FILE="$SRC_DIR/industries.json"

# Destination: offline outputs directory (not deployed)
OUT_DIR="$REPO_ROOT/data/output/cli"
BUNDLE_PATH="$OUT_DIR/cli-bundle.json"
MANIFEST_PATH="$OUT_DIR/cli-manifest.json"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
die() { echo "ERROR: $*" >&2; exit 1; }

sha256_file() {
    if command -v sha256sum &>/dev/null; then
        sha256sum "$1" | awk '{print $1}'
    else
        shasum -a 256 "$1" | awk '{print $1}'
    fi
}

command -v jq      &>/dev/null || die "jq is required (brew install jq / apt install jq)"
command -v python3 &>/dev/null || die "python3 is required"

mkdir -p "$OUT_DIR"

# ---------------------------------------------------------------------------
# Collect source files
#
# The mergers/ directory also contains list.json and list-page-*.json (the
# paginated lightweight lists used by the frontend). We only want the full
# per-merger records, which follow the MN-*.json / WA-*.json naming.
# ---------------------------------------------------------------------------
[[ -d "$MERGERS_DIR" ]] || die "Mergers directory not found: $MERGERS_DIR"

MERGER_FILES=()
for f in "$MERGERS_DIR"/MN-*.json "$MERGERS_DIR"/WA-*.json; do
    [[ -f "$f" ]] && MERGER_FILES+=("$f")
done
MERGER_COUNT=${#MERGER_FILES[@]}
[[ $MERGER_COUNT -gt 0 ]] || die "No merger files found in $MERGERS_DIR"
echo "Found $MERGER_COUNT merger files"

QUESTIONNAIRE_FILES=()
if [[ -d "$QUESTIONNAIRES_DIR" ]]; then
    for f in "$QUESTIONNAIRES_DIR"/*.json; do
        [[ -f "$f" ]] && QUESTIONNAIRE_FILES+=("$f")
    done
fi
echo "Found ${#QUESTIONNAIRE_FILES[@]} questionnaire files"

# ---------------------------------------------------------------------------
# Build bundle into a temp file
#
# The individual JSON chunks (mergers array, questionnaires map, stats,
# industries) are staged to temp files rather than shell variables because
# the mergers array is large enough to exceed ARG_MAX.
# ---------------------------------------------------------------------------
BUNDLE_TMP="$(mktemp)"
MERGERS_TMP="$(mktemp)"
QUESTIONNAIRES_TMP="$(mktemp)"
STATS_TMP="$(mktemp)"
INDUSTRIES_TMP="$(mktemp)"
trap 'rm -f "$BUNDLE_TMP" "$MERGERS_TMP" "$QUESTIONNAIRES_TMP" "$STATS_TMP" "$INDUSTRIES_TMP"' EXIT

echo "Building bundle..."

jq -s '.' "${MERGER_FILES[@]}" > "$MERGERS_TMP"

if [[ ${#QUESTIONNAIRE_FILES[@]} -gt 0 ]]; then
    python3 - "${QUESTIONNAIRE_FILES[@]}" > "$QUESTIONNAIRES_TMP" <<'PYEOF'
import json, os, sys
result = {}
for path in sys.argv[1:]:
    merger_id = os.path.splitext(os.path.basename(path))[0]
    with open(path) as f:
        result[merger_id] = json.load(f)
print(json.dumps(result, separators=(',', ':'), sort_keys=True))
PYEOF
else
    echo "{}" > "$QUESTIONNAIRES_TMP"
fi

if [[ -f "$STATS_FILE" ]]; then
    cp "$STATS_FILE" "$STATS_TMP"
else
    echo "null" > "$STATS_TMP"
fi

if [[ -f "$INDUSTRIES_FILE" ]]; then
    cp "$INDUSTRIES_FILE" "$INDUSTRIES_TMP"
else
    echo "null" > "$INDUSTRIES_TMP"
fi

# Combine using jq's `input` (reads one JSON value per file) to avoid argv limits.
jq -n \
    '{
        mergers:        input,
        questionnaires: input,
        stats:          input,
        industries:     input
    }' "$MERGERS_TMP" "$QUESTIONNAIRES_TMP" "$STATS_TMP" "$INDUSTRIES_TMP" \
    > "$BUNDLE_TMP"

# ---------------------------------------------------------------------------
# Check whether content actually changed
# ---------------------------------------------------------------------------
BUNDLE_SHA256=$(sha256_file "$BUNDLE_TMP")

PREV_SHA256=""
PREV_VERSION=0
if [[ -f "$MANIFEST_PATH" ]]; then
    PREV_SHA256=$(jq -r '.bundle_sha256 // ""' "$MANIFEST_PATH")
    PREV_VERSION=$(jq -r '.version // 0' "$MANIFEST_PATH")
fi

if [[ "$BUNDLE_SHA256" == "$PREV_SHA256" && "$FORCE" -eq 0 ]]; then
    echo "Bundle unchanged (sha256 matches v${PREV_VERSION}). Nothing to do."
    exit 0
fi

NEW_VERSION=$((PREV_VERSION + 1))
mv "$BUNDLE_TMP" "$BUNDLE_PATH"
echo "Bundle updated: v${PREV_VERSION} -> v${NEW_VERSION}"

# ---------------------------------------------------------------------------
# Per-merger checksums support a future per-record incremental sync where the
# CLI fetches only changed merger files instead of the full bundle.
# ---------------------------------------------------------------------------
echo "Computing per-merger checksums..."
MERGER_CHECKSUMS=$(python3 - "${MERGER_FILES[@]}" <<'PYEOF'
import hashlib, json, os, sys
result = {}
for path in sys.argv[1:]:
    merger_id = os.path.splitext(os.path.basename(path))[0]
    with open(path, 'rb') as f:
        result[merger_id] = hashlib.sha256(f.read()).hexdigest()
print(json.dumps(result, separators=(',', ':'), sort_keys=True))
PYEOF
)

# ---------------------------------------------------------------------------
# Write manifest
# ---------------------------------------------------------------------------
GENERATED_AT=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

jq -n \
    --argjson version          "$NEW_VERSION" \
    --arg     generated_at     "$GENERATED_AT" \
    --argjson merger_count     "$MERGER_COUNT" \
    --arg     bundle_sha256    "$BUNDLE_SHA256" \
    --argjson merger_checksums "$MERGER_CHECKSUMS" \
    '{
        version:          $version,
        generated_at:     $generated_at,
        merger_count:     $merger_count,
        bundle_sha256:    $bundle_sha256,
        merger_checksums: $merger_checksums
    }' > "$MANIFEST_PATH"

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
BUNDLE_KB=$(( $(wc -c < "$BUNDLE_PATH") / 1024 ))
echo ""
echo "CLI data generated"
echo "  Version:   $NEW_VERSION"
echo "  Generated: $GENERATED_AT"
echo "  Mergers:   $MERGER_COUNT"
echo "  Bundle:    $BUNDLE_PATH (${BUNDLE_KB} KB)"
echo "  Manifest:  $MANIFEST_PATH"
echo "  SHA256:    $BUNDLE_SHA256"
