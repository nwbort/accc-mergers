#!/bin/bash
#
# Runs scrape_tribunal.py against a fresh copy of main and, if it found any
# changes, pushes them on a well-known branch and opens (or updates) a pull
# request via the gh CLI. Intended to be run on a schedule (cron/systemd
# timer) from a machine that isn't a GitHub Actions runner — the tribunal
# site's Cloudflare bot management JS-challenges Actions' hosted-runner IPs,
# so this can't run there. See docs/deployment.md#running-the-tribunal-scraper-on-a-schedule.
#
# Requires: git, python3 (with scripts/requirements.txt installed), curl,
# and the gh CLI already authenticated (`gh auth login`) with repo access.
#
# This script mutates the repo it's run from (fetches, resets a branch,
# commits, force-pushes) — point it at a clone dedicated to this cron job,
# not one you also use for manual development.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

BRANCH="tribunal-scrape"
BASE_BRANCH="main"
LOG_PREFIX="[$(date '+%Y-%m-%d %H:%M:%S')]"

log() {
  echo "$LOG_PREFIX $*"
}

for cmd in git python3 curl gh; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    log "ERROR: required command '$cmd' not found on PATH"
    exit 1
  fi
done

# Refuse to run against a dirty tree — this script is meant for a dedicated
# clone, so unexpected local changes mean something unrelated is going on.
if [ -n "$(git status --porcelain)" ]; then
  log "ERROR: working tree is not clean; refusing to run. Investigate $REPO_ROOT before retrying."
  exit 1
fi

log "Fetching latest $BASE_BRANCH"
git fetch origin "$BASE_BRANCH"

log "Resetting local branch '$BRANCH' onto origin/$BASE_BRANCH"
git switch -C "$BRANCH" "origin/$BASE_BRANCH"

log "Installing dependencies"
pip install -q -r scripts/requirements.txt

log "Running scrape_tribunal.py"
SCRAPE_LOG="$(mktemp)"
trap 'rm -f "$SCRAPE_LOG"' EXIT
if ! python3 scripts/scrape_tribunal.py 2>&1 | tee "$SCRAPE_LOG"; then
  log "ERROR: scrape_tribunal.py failed; see output above. Leaving $BASE_BRANCH checked out."
  git switch "$BASE_BRANCH"
  exit 1
fi

git add data/processed/tribunal_appeals.json data/raw/matters

if git diff --cached --quiet -- data/processed/tribunal_appeals.json data/raw/matters; then
  log "No changes; nothing to push."
  git switch "$BASE_BRANCH"
  exit 0
fi

TIMESTAMP="$(TZ='Australia/Sydney' date)"
git commit -m "Update scraped tribunal data: $TIMESTAMP"

log "Pushing $BRANCH"
git push origin "$BRANCH" --force

PR_TITLE="Update scraped tribunal data ($(date -u +%Y-%m-%d))"
PR_BODY_FILE="$(mktemp)"
trap 'rm -f "$SCRAPE_LOG" "$PR_BODY_FILE"' EXIT
{
  echo "Automated scrape of Australian Competition Tribunal matter pages, run locally on $(hostname) at $TIMESTAMP."
  echo ""
  echo "\`\`\`"
  cat "$SCRAPE_LOG"
  echo "\`\`\`"
} > "$PR_BODY_FILE"

EXISTING_PR="$(gh pr list --head "$BRANCH" --state open --json number --jq '.[0].number' 2>/dev/null || echo "")"

if [ -n "$EXISTING_PR" ]; then
  log "Updating existing PR #$EXISTING_PR"
  gh pr edit "$EXISTING_PR" --title "$PR_TITLE" --body-file "$PR_BODY_FILE"
else
  log "Creating new PR"
  gh pr create --head "$BRANCH" --base "$BASE_BRANCH" --title "$PR_TITLE" --body-file "$PR_BODY_FILE"
fi

git switch "$BASE_BRANCH"
log "Done."
