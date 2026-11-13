-- v3 (D012) event signals: opt-in, private interest and RSVP storage (owner: Patrik).
--
-- PRIVATE. Nothing here is returned to another player. Other owners get only a
-- bucket ("none" | "3-5" | "6-10" | "11+") or a confirmed yes/no, never a count
-- or a player id, through server/privacy/events.py.
--
-- event_signal_optins: a row exists only while the player has eventSignals on.
-- Turning it off, DELETE /me/data, or leaving deletes every interest and RSVP.
-- Retention: interest and RSVP rows carry the cycle they belong to and are
-- purged 14 days after that cycle locks (AnswerStore.purge_expired).

CREATE TABLE IF NOT EXISTS event_signal_optins (
  player_id    TEXT NOT NULL,
  community_id TEXT NOT NULL,
  updated_at   TEXT NOT NULL,
  PRIMARY KEY (player_id, community_id),
  FOREIGN KEY (community_id, player_id)
    REFERENCES memberships (community_id, player_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS event_interests (
  player_id    TEXT NOT NULL,
  community_id TEXT NOT NULL,
  event_id     TEXT NOT NULL,
  cycle_id     TEXT NOT NULL,
  created_at   TEXT NOT NULL,
  PRIMARY KEY (player_id, community_id, event_id),
  FOREIGN KEY (community_id, player_id)
    REFERENCES memberships (community_id, player_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS event_interests_event ON event_interests (community_id, event_id);
CREATE INDEX IF NOT EXISTS event_interests_cycle ON event_interests (cycle_id);

-- Custom-event invites (S14). Issued by the pipeline only to opted-in adults.
CREATE TABLE IF NOT EXISTS event_invites (
  invite_id    TEXT PRIMARY KEY,
  community_id TEXT NOT NULL,
  cycle_id     TEXT NOT NULL,
  event_id     TEXT NOT NULL,
  status       TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'confirmed', 'cancelled')),
  created_at   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS event_invites_cycle ON event_invites (cycle_id);

CREATE TABLE IF NOT EXISTS event_invite_recipients (
  invite_id  TEXT NOT NULL REFERENCES event_invites ON DELETE CASCADE,
  player_id  TEXT NOT NULL REFERENCES players ON DELETE CASCADE,
  rsvp       TEXT NOT NULL DEFAULT 'none' CHECK (rsvp IN ('none', 'going', 'not_going')),
  updated_at TEXT NOT NULL,
  PRIMARY KEY (invite_id, player_id)
);
