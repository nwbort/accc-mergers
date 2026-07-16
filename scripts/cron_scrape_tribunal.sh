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

# scrape_tribunal.py exits 2 specifically when one or more pages failed to
# fetch (e.g. blocked by Cloudflare) — distinct from exit 0, which covers
# both "ran clean, genuinely nothing new" and "ran clean, found changes".
# Capture the real exit code via PIPESTATUS rather than the pipeline's
# overall status, so BLOCKED and a genuine crash aren't both just "failed".
set +e
python3 scripts/scrape_tribunal.py 2>&1 | tee "$SCRAPE_LOG"
SCRAPE_EXIT="${PIPESTATUS[0]}"
set -e

if [ "$SCRAPE_EXIT" -eq 2 ]; then
  log "STATUS=BLOCKED one or more tribunal pages failed to fetch — see FAILED/curl lines above (likely a Cloudflare challenge, an outage, or a network blip, not a real 'nothing new' result). Nothing committed; $BASE_BRANCH left checked out."
  git switch "$BASE_BRANCH"
  exit 2
elif [ "$SCRAPE_EXIT" -ne 0 ]; then
  log "STATUS=ERROR scrape_tribunal.py crashed (exit $SCRAPE_EXIT); see output above. Nothing committed; $BASE_BRANCH left checked out."
  git switch "$BASE_BRANCH"
  exit 1
fi

git add data/processed/tribunal_appeals.json data/raw/matters

if git diff --cached --quiet -- data/processed/tribunal_appeals.json data/raw/matters; then
  log "STATUS=OK-NO-CHANGES"
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
  log "STATUS=OK-PR-UPDATED #$EXISTING_PR"
  gh pr edit "$EXISTING_PR" --title "$PR_TITLE" --body-file "$PR_BODY_FILE"
else
  log "STATUS=OK-PR-OPENED"
  gh pr create --head "$BRANCH" --base "$BASE_BRANCH" --title "$PR_TITLE" --body-file "$PR_BODY_FILE"
fi

git switch "$BASE_BRANCH"
log "Done."
