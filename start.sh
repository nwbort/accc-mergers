#!/bin/bash
set -e

# Print debug information
echo "Current directory: $(pwd)"
echo "Contents of current directory:"
ls -la
echo ""
echo "Looking for merger-tracker/backend:"
ls -la merger-tracker/backend/ || echo "Backend directory not found!"
echo ""

# Change to backend directory
cd merger-tracker/backend

echo "Changed to: $(pwd)"
echo "Contents:"
ls -la
echo ""

# Sync data from GitHub on startup
echo "Syncing mergers.json from GitHub..."
python3 -c "
from sync_data import download_mergers_json_from_github, sync_from_json
import os

repo = os.getenv('GITHUB_REPO', 'nwbort/accc-mergers')
branch = os.getenv('GITHUB_BRANCH', 'main')
token = os.getenv('GITHUB_TOKEN')

print(f'Downloading from {repo}@{branch}...')
json_path = download_mergers_json_from_github(repo=repo, branch=branch, github_token=token)
print('Syncing to database...')
sync_from_json(json_path)
print('Startup sync complete!')
" || echo "Warning: Startup sync failed, continuing with existing data..."

echo ""
echo "Starting uvicorn..."

# Start the application
exec uvicorn main:app --host 0.0.0.0 --port "${PORT:-8000}"
