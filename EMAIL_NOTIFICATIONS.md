# Email Notification System

This document describes the email notification system for the ACCC Mergers tracker.

## Overview

The notification system allows users to subscribe to daily digest emails that summarize:
- New mergers added to the database
- Updates to existing mergers (status changes, new documents, determinations)

## Features

- **Email-only subscriptions** (no passwords or user accounts required)
- **Double opt-in** via email verification
- **Daily digest emails** with merger activity
- **One-click unsubscribe** links in every email
- **Scheduled automatic sending** or manual triggering
- **Privacy-focused**: Database with user data is NOT committed to git

## Architecture

### Database Schema

The system adds two new tables:

1. **`subscribers`** - Stores email addresses and preferences
   - Email verification status
   - Unsubscribe status
   - Last digest sent timestamp

2. **notification_log** - Tracks all sent emails
   - For debugging and preventing duplicates
   - Stores email IDs from Resend for tracking

### Components

- **`email_service.py`** - Resend API integration and email templates
- **`subscription_service.py`** - Database operations for subscribers
- **`subscription_routes.py`** - API endpoints for subscription management
- **`digest_service.py`** - Daily digest generation and sending logic
- **`migrations/001_add_notifications.sql`** - Database migration

## Setup Instructions

### 1. Get a Resend API Key

1. Sign up at [resend.com](https://resend.com)
2. Verify your domain (or use their testing domain for development)
3. Create an API key at https://resend.com/api-keys
4. Copy the API key (starts with `re_...`)

### 2. Configure Environment Variables

Copy the example environment file:

```bash
cd merger-tracker/backend
cp .env.example .env
```

Edit `.env` and set:

```bash
# Required
RESEND_API_KEY=re_your_api_key_here

# Email sender (must be verified in Resend)
FROM_EMAIL=ACCC Mergers <notifications@mergers.fyi>

# Base URL for links in emails
BASE_URL=https://mergers.fyi

# Enable automatic daily digest sending
ENABLE_DIGEST_SCHEDULER=true

# Send time (UTC) - default 9 AM UTC = 7 PM AEST / 8 PM AEDT
DIGEST_HOUR=9
DIGEST_MINUTE=0
```

### 3. Install Dependencies

```bash
cd merger-tracker/backend
pip install -r requirements.txt
```

New dependencies:
- `resend` - Email sending API
- `apscheduler` - Scheduled job runner
- `pydantic-settings` - Environment variable management

### 4. Run Database Migration

The migration runs automatically on backend startup, but you can also run it manually:

```bash
cd merger-tracker/backend
python run_migration.py
```

This creates the `subscribers` and `notification_log` tables.

### 5. Start the Backend

```bash
cd merger-tracker/backend
uvicorn main:app --reload
```

The backend will:
- Apply the notification migration
- Start the daily digest scheduler (if enabled)
- Expose subscription API endpoints at `/api/subscribe/*`

## API Endpoints

### Public Endpoints

**Subscribe to daily digest:**
```http
POST /api/subscribe
Content-Type: application/json

{
  "email": "user@example.com"
}
```

**Verify email address:**
```http
POST /api/subscribe/verify
Content-Type: application/json

{
  "token": "verification_token_from_email"
}
```

**Unsubscribe:**
```http
POST /api/subscribe/unsubscribe
Content-Type: application/json

{
  "token": "unsubscribe_token_from_email"
}
```

**Get subscriber stats:**
```http
GET /api/subscribe/stats
```

### Admin/Testing Endpoints

**Manually send daily digest:**
```http
POST /api/subscribe/admin/send-digest?dry_run=true
POST /api/subscribe/admin/send-digest?digest_date=2025-11-18
```

**Send test digest to specific email:**
```http
POST /api/subscribe/admin/send-test-digest?email=test@example.com&digest_date=2025-11-18
```

## Email Flow

### 1. Subscription

1. User submits email via form (to be built on frontend)
2. Backend creates subscriber record with `verified=false`
3. Verification email sent with unique token link
4. User clicks link → `/verify?token=xxx`
5. Frontend calls `/api/subscribe/verify` with token
6. Subscriber marked as `verified=true`
7. User now receives daily digests

### 2. Daily Digest

**Automatic (scheduled):**
- Scheduler runs at configured time (default: 9 AM UTC)
- Queries database for yesterday's activity
- Sends digest to all verified, active subscribers
- Logs each sent email in `notification_log`

**Manual (testing):**
- Call `/api/subscribe/admin/send-digest`
- Optionally specify date and dry_run mode

### 3. Unsubscribe

1. User clicks unsubscribe link in email → `/unsubscribe?token=xxx`
2. Frontend calls `/api/subscribe/unsubscribe` with token
3. Subscriber marked as `unsubscribed=true`
4. No more emails sent to this address

## Email Templates

Emails are HTML + plain text with inline CSS for maximum compatibility.

### Verification Email

- Subject: "Confirm your ACCC Mergers subscription"
- Contains: Verification button/link
- Styling: Blue theme matching site

### Daily Digest Email

- Subject: "ACCC Mergers Daily Digest - [Date] ([X] new, [Y] updates)"
- Sections:
  - New mergers (green boxes)
  - Updated mergers (orange boxes)
  - No activity message (if nothing to report)
- Footer: View all link, unsubscribe link

## Testing

### Test with Dry Run

```bash
curl -X POST "http://localhost:8000/api/subscribe/admin/send-digest?dry_run=true"
```

Returns what would be sent without actually sending emails.

### Test with Your Email

```bash
curl -X POST "http://localhost:8000/api/subscribe/admin/send-test-digest?email=your@email.com"
```

Sends a real digest email to your address.

### Test Full Flow

1. Subscribe with your email
2. Check inbox for verification email
3. Click verification link
4. Wait for scheduled digest OR manually trigger
5. Check digest email received
6. Test unsubscribe link

## Deployment

### Railway Environment Variables

Add these to Railway environment variables:

```
RESEND_API_KEY=re_your_key_here
FROM_EMAIL=ACCC Mergers <notifications@mergers.fyi>
BASE_URL=https://mergers.fyi
ENABLE_DIGEST_SCHEDULER=true
DIGEST_HOUR=9
DIGEST_MINUTE=0
```

### Domain Verification in Resend

To send from `@mergers.fyi`:

1. Add domain in Resend dashboard
2. Add DNS records (SPF, DKIM, DMARC)
3. Wait for verification (usually a few minutes)
4. Use verified email in `FROM_EMAIL`

For testing, you can use Resend's testing domain.

## Privacy & Security

### Database Not Committed

- ✅ `.gitignore` excludes `*.db` files
- ✅ `mergers.db` removed from git tracking
- ✅ Database regenerated from `mergers.json` on startup
- ✅ User email addresses never committed to repository

### Email Security

- Double opt-in prevents unauthorized subscriptions
- Unsubscribe tokens are unique and secure (URL-safe random)
- Verification tokens expire via database records
- IP addresses stored only for abuse prevention
- Minimal data collection (just email + preferences)

### GDPR Considerations

- ✅ Clear consent via double opt-in
- ✅ Easy unsubscribe in every email
- ✅ Minimal data storage
- ✅ Audit trail in notification_log

Consider adding:
- Privacy policy link in emails
- Data export functionality
- Data deletion on request

## Monitoring

### Check Subscriber Stats

```bash
curl http://localhost:8000/api/subscribe/stats
```

Returns:
```json
{
  "success": true,
  "stats": {
    "total": 100,
    "verified": 80,
    "active": 75,
    "unsubscribed": 5,
    "pending_verification": 20
  }
}
```

### Check Notification Log

Query the database:

```sql
SELECT * FROM notification_log
ORDER BY sent_at DESC
LIMIT 10;
```

### Resend Dashboard

Monitor email delivery, bounces, and complaints at:
https://resend.com/emails

## Future Enhancements

Potential additions (not currently implemented):

1. **Track specific mergers** - Users can subscribe to updates on individual mergers
2. **Weekly digest option** - Alternative to daily emails
3. **Instant notifications** - Email when new mergers added (high activity only)
4. **Email preferences** - Customize which types of updates to receive
5. **Frontend subscription form** - UI for subscribing/managing preferences
6. **Admin dashboard** - View subscribers, send test emails, etc.
7. **Webhook integration** - Trigger digests when data is updated
8. **Multiple digest times** - Support different timezones

## Troubleshooting

### Emails not sending

1. Check `RESEND_API_KEY` is set correctly
2. Verify domain/email in Resend dashboard
3. Check Resend dashboard for error logs
4. Test with admin endpoint and check response

### Scheduler not running

1. Check `ENABLE_DIGEST_SCHEDULER=true` in env
2. Check backend logs for "Daily digest scheduled" message
3. Verify time configuration (UTC)

### Database errors

1. Check migration ran successfully
2. Verify database file exists and is writable
3. Check database schema with: `sqlite3 mergers.db .schema`

### Verification/Unsubscribe links not working

1. Check `BASE_URL` matches your frontend URL
2. Verify tokens in database are unique
3. Check CORS configuration allows frontend domain

## Support

For issues or questions:
- Check backend logs
- Review Resend dashboard
- Test with dry_run mode first
- Use admin endpoints for debugging
