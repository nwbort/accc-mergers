#!/bin/bash
# SessionStart hook: install the dependencies a Claude Code on the web session
# needs to run the test suites and linters.
#
# Web sessions start from a clean container, so without this the pytest suite
# fails on import (scrape_tribunal.py needs beautifulsoup4 + lxml) and the
# frontend has no node_modules at all.
#
# Deliberately skipped: scripts/requirements-tribunal.txt (nodriver drives a
# real Chrome) and scripts/requirements-embed.txt (~750MB of torch). Neither is
# needed by the tests — the tribunal tests only use bs4/lxml/requests from the
# main requirements file.
set -euo pipefail

# Local machines manage their own environments; only set up the remote one.
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "$CLAUDE_PROJECT_DIR"

echo "Installing Python dependencies (scripts/requirements.txt + pytest)..."
python3 -m pip install --quiet --disable-pip-version-check \
  -r scripts/requirements.txt pytest

echo "Installing frontend dependencies (merger-tracker/frontend)..."
npm install --prefix merger-tracker/frontend --no-audit --no-fund --loglevel=error

echo "Session setup complete."
