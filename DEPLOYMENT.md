# Deployment Configuration

This document describes the optimized deployment setup for the ACCC Merger Tracker, which separates code deployments from data updates.

## Overview

The deployment architecture is designed to minimize unnecessary redeployments:

- **Code changes** → Full Railway redeployment
- **Data changes** (mergers.json) → Webhook triggers data sync without redeployment

## Architecture

```
GitHub Actions (hourly/daily)
    ↓
Updates mergers.json on main branch
    ↓
Triggers sync-to-railway.yml workflow
    ↓
Calls Railway webhook endpoint
    ↓
Railway downloads latest mergers.json from GitHub
    ↓
Updates SQLite database
    ↓
Clears cache
```

## Railway Configuration

### Environment Variables

Set the following environment variables in your Railway project:

#### Required

- **`WEBHOOK_SECRET`**: Secret token for webhook authentication
  - Generate with: `openssl rand -hex 32`
  - Used by GitHub Actions to authenticate webhook calls

#### Optional (Recommended)

- **`GITHUB_TOKEN`**: GitHub personal access token (PAT)
  - Provides higher API rate limits
  - Required for private repositories
  - Create at: https://github.com/settings/tokens
  - Required scopes: `repo` (for private repos) or `public_repo` (for public repos)

- **`GITHUB_REPO`**: Repository in format "owner/repo"
  - Default: `nwbort/accc-mergers`

- **`GITHUB_BRANCH`**: Branch to pull mergers.json from
  - Default: `main`

#### Existing Variables

- **`ADMIN_API_KEY`**: For admin endpoints (commentary CRUD)
- **`BACKUP_API_KEY`**: For database backup endpoint

### Watch Patterns

The `railway.toml` file is configured to exclude data files from triggering deployments:

```toml
watchPatterns = [
  "**/*",           # Watch all files
  "!mergers.json",  # Except mergers.json
  "!matters/**"     # And matters directory
]
```

This ensures Railway only redeploys when actual code changes are pushed.

## GitHub Configuration

### Repository Secrets

Set the following secrets in your GitHub repository:
Settings → Secrets and variables → Actions → New repository secret

1. **`RAILWAY_WEBHOOK_SECRET`**: Same value as Railway's `WEBHOOK_SECRET`
2. **`RAILWAY_API_URL`**: Your Railway app URL (e.g., `https://your-app.railway.app`)

### Workflows

#### `.github/workflows/sync-to-railway.yml`

Triggers on:
- Push to main branch with changes to `mergers.json`
- Manual dispatch (for testing)

Actions:
1. Calls Railway webhook endpoint
2. Verifies success with HTTP status code
3. Creates workflow summary

## API Endpoints

### Webhook Endpoint

**POST** `/api/webhook/sync-data`

Triggers data sync from GitHub without redeployment.

**Headers:**
- `X-Webhook-Secret`: Must match `WEBHOOK_SECRET` environment variable

**Response:**
```json
{
  "success": true,
  "message": "Data synced successfully from GitHub",
  "timestamp": "2025-11-28T10:30:00Z",
  "source": {
    "repo": "nwbort/accc-mergers",
    "branch": "main"
  }
}
```

**Rate Limit:** 30 requests/hour

## Deployment Workflow

### For Code Changes

1. Push code changes to your feature branch
2. Create PR and merge to main (or deployment branch)
3. Railway automatically detects changes and redeploys
4. Database syncs from local mergers.json on startup

### For Data Updates

1. GitHub Actions scrapes ACCC website (hourly)
2. GitHub Actions extracts data to mergers.json (daily)
3. Changes committed to main branch
4. `sync-to-railway.yml` workflow triggers automatically
5. Webhook calls Railway endpoint
6. Railway downloads latest mergers.json from GitHub
7. Database updates without redeployment
8. Cache cleared to serve fresh data

### Manual Data Sync

You can manually trigger a data sync:

```bash
curl -X POST https://your-app.railway.app/api/webhook/sync-data \
  -H "X-Webhook-Secret: your_webhook_secret"
```

Or use the GitHub Actions workflow dispatch:
1. Go to Actions → Sync Data to Railway
2. Click "Run workflow"
3. Select branch and run

## Testing

### Test Webhook Locally

1. Start the backend: `cd merger-tracker/backend && uvicorn main:app --reload`
2. Set environment variables:
   ```bash
   export WEBHOOK_SECRET=test_secret_123
   export GITHUB_TOKEN=your_github_token  # optional
   ```
3. Call webhook:
   ```bash
   curl -X POST http://localhost:8000/api/webhook/sync-data \
     -H "X-Webhook-Secret: test_secret_123"
   ```

### Test Workflow

1. Make a test change to mergers.json
2. Push to main branch
3. Check Actions tab for workflow run
4. Verify webhook was called successfully

## Troubleshooting

### Webhook Returns 401

- Check `WEBHOOK_SECRET` matches between Railway and GitHub secrets
- Verify header name is `X-Webhook-Secret` (case-sensitive)

### Webhook Returns 500

- Check Railway logs for detailed error message
- Verify GitHub token has correct permissions
- Ensure mergers.json exists on the specified branch

### Data Not Updating

- Check GitHub Actions workflow completed successfully
- Verify Railway received webhook call (check logs)
- Confirm cache was cleared (should happen automatically)
- Try manual webhook trigger

### Railway Still Redeploying on Data Changes

- Verify `railway.toml` has correct `watchPatterns`
- Check Railway dashboard build logs
- May need to push a code change to update Railway configuration

## Migration Notes

### First-Time Setup

1. Add environment variables to Railway
2. Add secrets to GitHub repository
3. Push the updated `railway.toml` to trigger a redeployment
4. After deployment, Railway will use webhook-based sync
5. Test with a manual workflow dispatch

### Rollback

If you need to revert to the old deployment model:

1. Remove `watchPatterns` from `railway.toml`
2. Disable `.github/workflows/sync-to-railway.yml` workflow
3. Push changes - Railway will resume redeploying on all changes

## Benefits

✅ **Faster Updates**: Data updates happen in ~5 seconds instead of ~2 minutes

✅ **Cost Savings**: Fewer build minutes consumed on Railway

✅ **Better Control**: Manual control over code deployments

✅ **No Downtime**: Database updates without service restart

✅ **Instant Sync**: Data updates trigger immediately on push to main

## Monitoring

Check the following to monitor the system:

1. **GitHub Actions**: Actions tab → Sync Data to Railway workflow
2. **Railway Logs**: Look for "Data synced successfully" messages
3. **API Health**: GET `/` endpoint should return 200 OK
4. **Data Freshness**: Check `/api/stats` for `total_mergers` count

---

Last updated: 2025-11-28
