-- Facebook Space privacy store (owner: Patrik). Contract 2.0.0. SQLite dialect.
--
-- Applied by server/privacy/store.py on open (idempotent). No server process,
-- no container: the store is a single SQLite file (or :memory: in tests).
--
-- Access model: there is no database-level RLS in SQLite. Every read and write
-- goes through server/privacy/service.py, which keys each private query to the
-- player of a server-verified session. Nothing else may open this file.
--
-- Sessions store only SHA-256 token hashes. Consent revisions are append-only
-- (booleans + timestamps). Synthetic players never hold sessions.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS players (
  player_id    TEXT PRIMARY KEY,
  display_name TEXT NOT NULL CHECK (length(display_name) BETWEEN 1 AND 40),
  avatar_color TEXT NOT NULL CHECK (avatar_color GLOB '#[0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]'),
  is_synthetic INTEGER NOT NULL DEFAULT 0 CHECK (is_synthetic IN (0, 1)),
  created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS communities (
  community_id TEXT PRIMARY KEY,
  name         TEXT NOT NULL CHECK (length(name) BETWEEN 1 AND 80),
  time_zone    TEXT NOT NULL,
  is_demo      INTEGER NOT NULL DEFAULT 0 CHECK (is_demo IN (0, 1))
);

CREATE TABLE IF NOT EXISTS memberships (
  community_id TEXT NOT NULL REFERENCES communities ON DELETE CASCADE,
  player_id    TEXT NOT NULL REFERENCES players ON DELETE CASCADE,
  is_operator  INTEGER NOT NULL DEFAULT 0 CHECK (is_operator IN (0, 1)),
  joined_at    TEXT NOT NULL,
  left_at      TEXT,
  PRIMARY KEY (community_id, player_id)
);

CREATE TABLE IF NOT EXISTS consents (
  player_id      TEXT NOT NULL,
  community_id   TEXT NOT NULL,
  version        INTEGER NOT NULL CHECK (version >= 1),
  match_answers  INTEGER NOT NULL CHECK (match_answers IN (0, 1)),
  anonymous_chat INTEGER NOT NULL CHECK (anonymous_chat IN (0, 1)),
  is_adult       INTEGER NOT NULL CHECK (is_adult IN (0, 1)),
  revoked_at     TEXT,
  created_at     TEXT NOT NULL,
  PRIMARY KEY (player_id, community_id, version),
  FOREIGN KEY (community_id, player_id)
    REFERENCES memberships (community_id, player_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS sessions (
  session_id   TEXT PRIMARY KEY,
  token_hash   BLOB NOT NULL UNIQUE CHECK (length(token_hash) = 32),
  player_id    TEXT NOT NULL,
  community_id TEXT NOT NULL,
  created_at   TEXT NOT NULL,
  expires_at   TEXT NOT NULL,
  revoked_at   TEXT,
  FOREIGN KEY (community_id, player_id)
    REFERENCES memberships (community_id, player_id) ON DELETE CASCADE
);

CREATE VIEW IF NOT EXISTS current_consents AS
  SELECT c.* FROM consents c
  WHERE c.version = (SELECT max(version) FROM consents x
                     WHERE x.player_id = c.player_id AND x.community_id = c.community_id);

-- Demo community matching contracts/fixtures/week-sample.json (synthetic).
INSERT OR IGNORE INTO communities (community_id, name, time_zone, is_demo)
VALUES ('community-demo', 'Demo Campus Group (synthetic)', 'America/Los_Angeles', 1);
