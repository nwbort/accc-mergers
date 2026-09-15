-- Feedback table for mergers.fyi
-- Run with: wrangler d1 execute mergers-feedback --file=schema.sql
CREATE TABLE IF NOT EXISTS feedback (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  message    TEXT    NOT NULL,
  email      TEXT,
  created_at TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- Privacy-preserving feature-usage counters. Each row is a per-day count for
-- one event type — never a per-user or per-merger record, and nothing here
-- is ever joined against an IP address or identifier. Adding a new event
-- type to track needs no schema change: it just starts appearing as new
-- rows once the frontend pings it (see ALLOWED_EVENT_TYPES in src/index.js).
CREATE TABLE IF NOT EXISTS feature_events (
  event_type TEXT    NOT NULL,
  day        TEXT    NOT NULL, -- UTC date, YYYY-MM-DD
  count      INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (event_type, day)
);
