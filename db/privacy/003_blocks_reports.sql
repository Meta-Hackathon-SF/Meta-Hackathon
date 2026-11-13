-- Blocks and reports (owner: Patrik). Contract 2.0.0. PRIVATE: never returned
-- to another player. Kai's chat resolves anonymous handles to player ids
-- server-side and calls server/privacy/moderation.py; no route exposes rows.

CREATE TABLE IF NOT EXISTS blocks (
  community_id TEXT NOT NULL,
  blocker_id   TEXT NOT NULL REFERENCES players ON DELETE CASCADE,
  blocked_id   TEXT NOT NULL REFERENCES players ON DELETE CASCADE,
  created_at   TEXT NOT NULL,
  PRIMARY KEY (community_id, blocker_id, blocked_id),
  CHECK (blocker_id <> blocked_id)
);

CREATE TABLE IF NOT EXISTS reports (
  report_id       TEXT PRIMARY KEY,
  community_id    TEXT NOT NULL,
  room_id         TEXT NOT NULL,
  message_id      TEXT,
  reporter_id     TEXT NOT NULL REFERENCES players ON DELETE CASCADE,
  reported_handle TEXT NOT NULL CHECK (length(reported_handle) BETWEEN 1 AND 40),
  reason          TEXT NOT NULL CHECK (reason IN ('harassment', 'self_harm', 'spam', 'personal_info', 'other')),
  created_at      TEXT NOT NULL
);
-- One report per reporter per message (repeat taps are idempotent).
CREATE UNIQUE INDEX IF NOT EXISTS reports_once
  ON reports (reporter_id, room_id, coalesce(message_id, ''), reported_handle);
CREATE INDEX IF NOT EXISTS reports_message ON reports (room_id, message_id);
