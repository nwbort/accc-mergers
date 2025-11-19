-- Migration: Add email notification system for daily digests
-- Created: 2025-11-19

-- Store email subscribers
CREATE TABLE IF NOT EXISTS subscribers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,

    -- Verification
    verification_token TEXT UNIQUE NOT NULL,
    verified BOOLEAN DEFAULT 0,
    verified_at TIMESTAMP,

    -- Unsubscribe
    unsubscribe_token TEXT UNIQUE NOT NULL,
    unsubscribed BOOLEAN DEFAULT 0,
    unsubscribed_at TIMESTAMP,

    -- Preferences (daily digest only for now)
    receive_daily_digest BOOLEAN DEFAULT 1,

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_digest_sent_at TIMESTAMP,

    -- Metadata
    subscription_source TEXT DEFAULT 'web', -- 'web', 'api', etc.
    user_agent TEXT,
    ip_address TEXT -- For security/abuse prevention only
);

-- Log all sent notifications (for debugging and preventing duplicates)
CREATE TABLE IF NOT EXISTS notification_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subscriber_id INTEGER NOT NULL,
    notification_type TEXT NOT NULL, -- 'daily_digest', 'verification', 'welcome'

    -- Digest metadata
    digest_date DATE, -- The date the digest covers (e.g., 2025-11-18 for Nov 18 activity)
    merger_count INTEGER, -- Number of mergers included in digest

    -- Delivery
    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'sent', -- 'sent', 'failed', 'bounced'
    error_message TEXT,

    -- Email metadata
    email_subject TEXT,
    resend_email_id TEXT, -- ID from email provider for tracking

    FOREIGN KEY (subscriber_id) REFERENCES subscribers(id) ON DELETE CASCADE
);

-- Index for faster lookups
CREATE INDEX IF NOT EXISTS idx_subscribers_email ON subscribers(email);
CREATE INDEX IF NOT EXISTS idx_subscribers_verified ON subscribers(verified);
CREATE INDEX IF NOT EXISTS idx_subscribers_unsubscribed ON subscribers(unsubscribed);
CREATE INDEX IF NOT EXISTS idx_notification_log_subscriber ON notification_log(subscriber_id);
CREATE INDEX IF NOT EXISTS idx_notification_log_digest_date ON notification_log(digest_date);
CREATE INDEX IF NOT EXISTS idx_verification_token ON subscribers(verification_token);
CREATE INDEX IF NOT EXISTS idx_unsubscribe_token ON subscribers(unsubscribe_token);
