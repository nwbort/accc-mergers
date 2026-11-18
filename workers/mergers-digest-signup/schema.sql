-- Feedback table for mergers.fyi
-- Run with: wrangler d1 execute mergers-feedback --file=schema.sql
CREATE TABLE IF NOT EXISTS feedback (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  message    TEXT    NOT NULL,
  email      TEXT,
  created_at TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- Privacy-preserving feature-usage counters. Each row is a per-day count for
-- one event type — never a per-user record (track_merger_{id} and
-- track_industry_{code} counts are per merger or industry, not per user),
-- and nothing here is ever joined against an IP address or identifier. Adding a new event
-- type to track needs no schema change: it just starts appearing as new
-- rows once the frontend pings it (see ALLOWED_EVENT_TYPES in src/index.js).
CREATE TABLE IF NOT EXISTS feature_events (
  event_type TEXT    NOT NULL,
  day        TEXT    NOT NULL, -- Australia/Sydney date, YYYY-MM-DD
  count      INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (event_type, day)
);

-- Key-gated API (functions/data/api/[[path]].js, docs/api.md). The Pages
-- project binds this same database as API_DB. Keys are issued and revoked with
-- workers/feedback-admin/scripts/api-keys.mjs, never by hand: only a key's
-- SHA-256 is stored, so a lost key is reissued, not recovered.
CREATE TABLE IF NOT EXISTS api_keys (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  label      TEXT    NOT NULL, -- the client, e.g. smith-legal; may hold several keys while rotating
  key_hash   TEXT    NOT NULL UNIQUE, -- hex SHA-256 of the full key
  key_hint   TEXT    NOT NULL, -- the key's first characters, to tell a client's keys apart
  created_at TEXT    NOT NULL DEFAULT (datetime('now')),
  revoked_at TEXT
);

-- Per-client, per-day request counts. Like feature_events, a count and nothing
-- else: no IP address, user agent or per-request row. Requests with a missing,
-- unknown or revoked key are counted together under the label '(rejected)'.
CREATE TABLE IF NOT EXISTS api_usage (
  label TEXT    NOT NULL,
  day   TEXT    NOT NULL, -- Australia/Sydney date, YYYY-MM-DD
  count INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (label, day)
);
