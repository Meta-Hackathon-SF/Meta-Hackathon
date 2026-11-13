-- D010: optional activity signals for matching (Groups, Events, friends, post topics).
-- A row exists only while the player has turned "use my activity" on; turning it
-- off or DELETE /me/data removes the row. Post/comment TEXT is never stored:
-- only allowlisted topic labels derived by code (server/privacy/activity.py).
CREATE TABLE IF NOT EXISTS activity_signals (
  player_id    TEXT NOT NULL,
  community_id TEXT NOT NULL,
  profile_id   TEXT,                        -- opaque Facebook-side id, only to count mutual friends
  group_ids    TEXT NOT NULL DEFAULT '[]',  -- JSON array of ids
  event_ids    TEXT NOT NULL DEFAULT '[]',
  friend_ids   TEXT NOT NULL DEFAULT '[]',
  topics       TEXT NOT NULL DEFAULT '[]',  -- JSON array of allowlisted labels
  updated_at   TEXT NOT NULL,
  PRIMARY KEY (player_id, community_id),
  FOREIGN KEY (community_id, player_id)
    REFERENCES memberships (community_id, player_id) ON DELETE CASCADE
);

-- Cross-Group play: one Facebook-wide pool. Groups are matching signals (above), not boundaries.
INSERT OR IGNORE INTO communities (community_id, name, time_zone, is_demo)
VALUES ('facebook-space', 'Facebook Space (all Groups)', 'America/Los_Angeles', 1);
