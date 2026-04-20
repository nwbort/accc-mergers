-- Feedback table for mergers.fyi
-- Run with: wrangler d1 execute mergers-feedback --file=schema.sql
CREATE TABLE IF NOT EXISTS feedback (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  message    TEXT    NOT NULL,
  email      TEXT,
  created_at TEXT    NOT NULL DEFAULT (datetime('now'))
);
