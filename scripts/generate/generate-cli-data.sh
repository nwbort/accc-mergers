#!/usr/bin/env bash
# scripts/generate/generate-cli-data.sh
#
# Generates three files consumed by the accc-mergers-cli companion tool:
#
#   data/output/cli/cli-manifest.json
#     Lightweight version file (~hundreds of bytes). The CLI fetches this
#     first to check whether its cached bundle is still current, without
#     committing to a full download.
#
#   data/output/cli/cli-bundle.json
#     Complete dataset (all mergers + questionnaires + noccs + stats +
#     industries) bundled into a single file. Only downloaded when the
#     manifest's bundle_sha256 differs from the client's cached copy.
#
#   data/output/cli/cli-merger-manifest.json
#     {merger_id: sha256} map of every individual merger file. Supports a
#     future per-record incremental sync path; the CLI only fetches this
#     when the main manifest's merger_manifest_sha256 has changed.
#
# These live under data/output/. Only cli-manifest.json is tracked in git — it
# carries the version counter and bundle checksum this script needs to detect
# change across runs. The bundle and per-merger manifest are gitignored build
# intermediates: the pipeline feeds the bundle straight to build_cli_sqlite.py
# in the same job, and the CLI downloads the resulting cli.sqlite (plus its own
# manifest) from the orphan `cli-dist` branch, not from main.
#
# Usage:
#   ./scripts/generate/generate-cli-data.sh            # no-op if data unchanged
#   ./scripts/generate/generate-cli-data.sh --force    # always regenerate + bump version
#   ./scripts/generate/generate-cli-data.sh --rebuild  # rewrite the bundle only, no bump
#
# --rebuild exists because the bundle is gitignored: a fresh checkout has the
# manifest but no bundle, so anything needing the bundle (e.g. the manual
# publish-cli-sqlite workflow) has to reconstruct it without disturbing the
# version counter.
#
# Dependencies: jq (>=1.6), python3, sha256sum (Linux) or shasum (macOS)

set -euo pipefail

FORCE=0
REBUILD=0
case "${1:-}" in
    --force)   FORCE=1 ;;
    --rebuild) REBUILD=1 ;;
    "")        ;;
    *)         echo "ERROR: unknown option: $1" >&2; exit 2 ;;
esac

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
# determination_text is a package module (python -m scripts.parse.…), so the
# repo root has to be importable no matter where this script is invoked from.
export PYTHONPATH="${REPO_ROOT}${PYTHONPATH:+:$PYTHONPATH}"

# Source: the generated data files.
#
# Mergers come from data/output/mergers.json rather than the deployed
# frontend/public/data/mergers/*.json. Both are written by the same generator
# run from the same enriched records, but the deployed files carry only what
# the site renders — the CLI indexes the full record (see build_cli_sqlite.py's
# all_determination_text column and raw_json), so it reads the complete copy.
SRC_DIR="$REPO_ROOT/frontend/public/data"
MERGERS_JSON="$REPO_ROOT/data/output/mergers.json"
QUESTIONNAIRES_DIR="$SRC_DIR/questionnaires"
NOCCS_DIR="$SRC_DIR/noccs"
STATS_FILE="$SRC_DIR/stats.json"
INDUSTRIES_FILE="$SRC_DIR/industries.json"

# Destination: offline outputs directory (not deployed)
OUT_DIR="$REPO_ROOT/data/output/cli"
BUNDLE_PATH="$OUT_DIR/cli-bundle.json"
MANIFEST_PATH="$OUT_DIR/cli-manifest.json"
MERGER_MANIFEST_PATH="$OUT_DIR/cli-merger-manifest.json"

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
# ---------------------------------------------------------------------------
[[ -f "$MERGERS_JSON" ]] || die "Mergers file not found: $MERGERS_JSON"

MERGER_COUNT=$(jq '.mergers | length' "$MERGERS_JSON")
[[ "$MERGER_COUNT" -gt 0 ]] || die "No mergers found in $MERGERS_JSON"
echo "Found $MERGER_COUNT merger records"

QUESTIONNAIRE_FILES=()
if [[ -d "$QUESTIONNAIRES_DIR" ]]; then
    for f in "$QUESTIONNAIRES_DIR"/*.json; do
        [[ -f "$f" ]] && QUESTIONNAIRE_FILES+=("$f")
    done
fi
echo "Found ${#QUESTIONNAIRE_FILES[@]} questionnaire files"

NOCC_FILES=()
if [[ -d "$NOCCS_DIR" ]]; then
    for f in "$NOCCS_DIR"/*.json; do
        [[ -f "$f" ]] && NOCC_FILES+=("$f")
    done
fi
echo "Found ${#NOCC_FILES[@]} NOCC files"

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
NOCCS_TMP="$(mktemp)"
STATS_TMP="$(mktemp)"
INDUSTRIES_TMP="$(mktemp)"
trap 'rm -f "$BUNDLE_TMP" "$MERGERS_TMP" "$QUESTIONNAIRES_TMP" "$NOCCS_TMP" "$STATS_TMP" "$INDUSTRIES_TMP"' EXIT

echo "Building bundle..."

# Aggregate merger records while applying determination-text cleaning. The
# raw record contains PDF layout newlines inside determination_table_content
# (see determination_text.py); the frontend strips those at render time, but
# the CLI has no rendering layer, so we pre-clean here. Records come out
# ordered by merger_id.
python3 -m scripts.parse.determination_text --mergers-json "$MERGERS_JSON" > "$MERGERS_TMP"

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

if [[ ${#NOCC_FILES[@]} -gt 0 ]]; then
    python3 - "${NOCC_FILES[@]}" > "$NOCCS_TMP" <<'PYEOF'
import json, os, sys
result = {}
for path in sys.argv[1:]:
    merger_id = os.path.splitext(os.path.basename(path))[0]
    with open(path) as f:
        result[merger_id] = json.load(f)
print(json.dumps(result, separators=(',', ':'), sort_keys=True))
PYEOF
else
    echo "{}" > "$NOCCS_TMP"
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
        noccs:          input,
        stats:          input,
        industries:     input
    }' "$MERGERS_TMP" "$QUESTIONNAIRES_TMP" "$NOCCS_TMP" "$STATS_TMP" "$INDUSTRIES_TMP" \
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

# --rebuild reconstructs the gitignored bundle to match the tracked manifest and
# stops there: no version bump, no manifest rewrite. A checksum mismatch means
# the generated data in this checkout no longer matches what produced the
# recorded version, so the caller would be publishing something other than
# v${PREV_VERSION} — fail rather than silently mislabel it.
if [[ "$REBUILD" -eq 1 ]]; then
    if [[ -z "$PREV_SHA256" ]]; then
        die "--rebuild needs an existing $MANIFEST_PATH to rebuild against"
    fi
    if [[ "$BUNDLE_SHA256" != "$PREV_SHA256" ]]; then
        die "--rebuild produced a bundle that does not match v${PREV_VERSION}
  manifest sha256: $PREV_SHA256
  rebuilt sha256:  $BUNDLE_SHA256
Run without --rebuild to regenerate and bump the version."
    fi
    mv "$BUNDLE_TMP" "$BUNDLE_PATH"
    echo "Bundle rebuilt at v${PREV_VERSION} (sha256 matches manifest)."
    echo "  Bundle: $BUNDLE_PATH"
    exit 0
fi

if [[ "$BUNDLE_SHA256" == "$PREV_SHA256" && "$FORCE" -eq 0 ]]; then
    echo "Bundle unchanged (sha256 matches v${PREV_VERSION}). Nothing to do."
    exit 0
fi

NEW_VERSION=$((PREV_VERSION + 1))
mv "$BUNDLE_TMP" "$BUNDLE_PATH"
echo "Bundle updated: v${PREV_VERSION} -> v${NEW_VERSION}"

# ---------------------------------------------------------------------------
# Write per-merger manifest (separate file)
#
# Per-merger checksums support a future per-record incremental sync where the
# CLI fetches only changed merger files instead of the full bundle. Kept in
# its own file so the main cli-manifest.json stays small; the CLI only fetches
# this one when it wants to do an incremental sync.
# ---------------------------------------------------------------------------
echo "Computing per-merger checksums..."
python3 - "$MERGERS_JSON" > "$MERGER_MANIFEST_PATH" <<'PYEOF'
import hashlib, json, sys

# Each record is hashed as it would be serialised on its own (indent=2, the
# same form generate_static_data writes a merger file in), so a record's
# checksum depends only on the record itself.
with open(sys.argv[1]) as f:
    mergers = json.load(f)["mergers"]
result = {
    m["merger_id"]: hashlib.sha256(json.dumps(m, indent=2).encode()).hexdigest()
    for m in mergers
    if m.get("merger_id")
}
print(json.dumps(result, indent=2, sort_keys=True))
PYEOF

MERGER_MANIFEST_SHA256=$(sha256_file "$MERGER_MANIFEST_PATH")

# ---------------------------------------------------------------------------
# Write top-level manifest
#
# merger_manifest_sha256 lets the CLI detect whether cli-merger-manifest.json
# needs to be re-fetched without downloading it.
# ---------------------------------------------------------------------------
GENERATED_AT=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

jq -n \
    --argjson version                "$NEW_VERSION" \
    --arg     generated_at           "$GENERATED_AT" \
    --argjson merger_count           "$MERGER_COUNT" \
    --arg     bundle_sha256          "$BUNDLE_SHA256" \
    --arg     merger_manifest_sha256 "$MERGER_MANIFEST_SHA256" \
    '{
        version:                $version,
        generated_at:           $generated_at,
        merger_count:           $merger_count,
        bundle_sha256:          $bundle_sha256,
        merger_manifest_sha256: $merger_manifest_sha256
    }' > "$MANIFEST_PATH"

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
BUNDLE_KB=$(( $(wc -c < "$BUNDLE_PATH") / 1024 ))
echo ""
echo "CLI data generated"
echo "  Version:         $NEW_VERSION"
echo "  Generated:       $GENERATED_AT"
echo "  Mergers:         $MERGER_COUNT"
echo "  Bundle:          $BUNDLE_PATH (${BUNDLE_KB} KB)"
echo "  Manifest:        $MANIFEST_PATH"
echo "  Merger manifest: $MERGER_MANIFEST_PATH"
echo "  Bundle SHA256:   $BUNDLE_SHA256"
