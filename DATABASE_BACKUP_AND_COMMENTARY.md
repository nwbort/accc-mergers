# Database Backup and Commentary Features

This document explains how to set up and use the database backup and commentary features for the ACCC Merger Tracker backend.

## Overview

Two new features have been added to the backend API:

1. **Database Backup**: API endpoint for downloading SQLite database backups
2. **Commentary System**: Add your own notes and analysis to mergers (admin-only)

## Setup

### 1. Configure Environment Variables on Railway

You need to add two API keys as environment variables in your Railway project:

#### BACKUP_API_KEY
- **Purpose**: Protects the database backup endpoint
- **How to generate**: Create a strong random key (32+ characters recommended)
  ```bash
  # Example: Generate a random key
  openssl rand -hex 32
  ```
- **Add to Railway**:
  1. Go to your Railway project
  2. Navigate to Variables tab
  3. Add new variable: `BACKUP_API_KEY` = `<your-generated-key>`

#### ADMIN_API_KEY
- **Purpose**: Authenticates requests to create/edit/delete commentary
- **How to generate**: Create a strong random key (32+ characters recommended)
  ```bash
  # Example: Generate a random key
  openssl rand -hex 32
  ```
- **Add to Railway**:
  1. Go to your Railway project
  2. Navigate to Variables tab
  3. Add new variable: `ADMIN_API_KEY` = `<your-generated-key>`

## Using the Features

### Database Backups

The `/api/backup` endpoint allows you to download a copy of the SQLite database at any time.

#### Manual Backup via API
Download a backup using curl:

```bash
curl -H "X-Backup-Key: YOUR_BACKUP_API_KEY" \
     -o backup-$(date +%Y%m%d-%H%M%S).db \
     https://your-app.railway.app/api/backup
```

#### Automated Backup Options

**Option 1: Cron Job (Local Server/VPS)**
If you have a server that runs 24/7, set up a cron job:

```bash
# Add to crontab (crontab -e)
# Runs daily at 2:30 AM, keeps last 7 backups
30 2 * * * cd /path/to/backups && curl -H "X-Backup-Key: YOUR_KEY" -o "backup-$(date +\%Y\%m\%d).db" https://your-app.railway.app/api/backup && ls -t backup-*.db | tail -n +8 | xargs rm -f
```

**Option 2: Cloud Storage (Backblaze B2, AWS S3)**
Create a script that downloads and uploads to cloud storage:

```bash
#!/bin/bash
# backup-to-cloud.sh
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
BACKUP_FILE="backup-${TIMESTAMP}.db"

# Download from Railway
curl -H "X-Backup-Key: ${BACKUP_API_KEY}" \
     -o "${BACKUP_FILE}" \
     "${BACKEND_URL}/api/backup"

# Upload to Backblaze B2 (or AWS S3)
b2 upload-file your-bucket-name "${BACKUP_FILE}" "backups/${BACKUP_FILE}"

# Clean up local file
rm "${BACKUP_FILE}"
```

**Option 3: Railway Volumes (Built-in)**
Railway volumes are persistent, so your database is already protected against:
- Deployments/redeploys
- Service restarts
- Code updates

You only need manual backups for:
- Protection against data corruption
- Ability to restore to a previous state
- Off-site backup redundancy

**Recommendation**: Set up a weekly/monthly manual backup routine using Option 1 or 2, depending on your infrastructure.

#### Restoring from Backup
To restore a backup on Railway:

1. Download your backup file
2. Use Railway CLI to upload:
   ```bash
   railway volume mount <volume-id>
   # Copy backup file to mounted volume location
   cp backup.db /app/merger-tracker/backend/mergers.db
   ```
3. Restart the backend service

Or restore by temporarily adding an upload endpoint (for one-time use).

### Commentary System

The commentary system allows you to add your own notes and analysis to specific mergers. Only you (with the admin API key) can create/edit/delete commentary, but anyone can read it.

#### API Endpoints

**Get commentary for a merger** (Public - no auth required)
```bash
GET /api/mergers/{merger_id}/commentary
```

Example:
```bash
curl https://your-app.railway.app/api/mergers/MN-01016/commentary
```

**Create commentary** (Admin only)
```bash
POST /api/mergers/{merger_id}/commentary
Headers: X-Admin-Key: YOUR_ADMIN_API_KEY
Body: {"content": "Your commentary here"}
```

Example:
```bash
curl -X POST \
  -H "X-Admin-Key: YOUR_ADMIN_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"content": "This merger is particularly interesting because..."}' \
  https://your-app.railway.app/api/mergers/MN-01016/commentary
```

**Update commentary** (Admin only)
```bash
PUT /api/commentary/{commentary_id}
Headers: X-Admin-Key: YOUR_ADMIN_API_KEY
Body: {"content": "Updated commentary"}
```

Example:
```bash
curl -X PUT \
  -H "X-Admin-Key: YOUR_ADMIN_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"content": "Updated analysis: ..."}' \
  https://your-app.railway.app/api/commentary/1
```

**Delete commentary** (Admin only)
```bash
DELETE /api/commentary/{commentary_id}
Headers: X-Admin-Key: YOUR_ADMIN_API_KEY
```

Example:
```bash
curl -X DELETE \
  -H "X-Admin-Key: YOUR_ADMIN_API_KEY" \
  https://your-app.railway.app/api/commentary/1
```

#### Frontend Integration

To integrate commentary into your frontend:

1. **Display commentary** (no auth needed):
   ```javascript
   const response = await fetch(`/api/mergers/${mergerId}/commentary`);
   const { commentary } = await response.json();
   ```

2. **Create commentary** (requires admin key):
   ```javascript
   const adminKey = localStorage.getItem('adminApiKey');
   const response = await fetch(`/api/mergers/${mergerId}/commentary`, {
     method: 'POST',
     headers: {
       'Content-Type': 'application/json',
       'X-Admin-Key': adminKey
     },
     body: JSON.stringify({ content: 'Your commentary' })
   });
   ```

3. **Show edit UI conditionally**:
   - Store admin API key in localStorage
   - Only show create/edit/delete buttons if key is present
   - Add a simple settings page to input/save the API key

## Database Schema

### Commentary Table

```sql
CREATE TABLE commentary (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    merger_id TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (merger_id) REFERENCES mergers(merger_id)
);

CREATE INDEX idx_commentary_merger_id ON commentary(merger_id);
```

## Security Considerations

1. **API Keys**:
   - Never commit API keys to the repository
   - Use strong, randomly generated keys (32+ characters)
   - Rotate keys periodically
   - Store in environment variables only

2. **CORS**:
   - POST/PUT/DELETE methods are now allowed for admin endpoints
   - X-Admin-Key and X-Backup-Key headers are whitelisted

3. **Rate Limiting**:
   - Backup endpoint: 10 requests per hour
   - Commentary endpoints: 30 requests per minute (write), 100/min (read)

4. **Frontend Security**:
   - Admin API key stored in localStorage (user's browser only)
   - Key never exposed in frontend code or commits
   - Consider adding a "logout" feature to clear the key from localStorage

## Troubleshooting

### Backup endpoint returns 401
- Verify `BACKUP_API_KEY` is set in Railway environment variables
- Check that you're sending the correct header: `X-Backup-Key`
- Ensure the key in your request matches the Railway environment variable

### Commentary endpoints return 401
- Verify `ADMIN_API_KEY` is set in Railway
- Check that you're sending the correct header: `X-Admin-Key`
- Ensure the key in your request matches the Railway environment variable

### Database not updating
- Check Railway logs for errors
- Verify database volume is mounted correctly at `/app/merger-tracker/backend`
- Ensure `DATABASE_PATH` environment variable is set correctly (or using default `mergers.db`)

## Future Enhancements

Possible improvements to consider:

1. **Rich text commentary**: Support Markdown formatting in commentary
2. **Multiple users**: Add proper user authentication system
3. **Commentary attachments**: Allow uploading files with commentary
4. **Commentary history**: Track edit history for commentary
5. **Backup to cloud storage**: Store backups in S3/Backblaze instead of GitHub
6. **Incremental backups**: Only backup changes since last backup
