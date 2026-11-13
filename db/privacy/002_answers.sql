-- Private daily answers and prevalence guesses (owner: Patrik). Contract 2.0.0.
--
-- PRIVATE: read only through server/privacy/answers.py by the author's own
-- server-side request or by server jobs. Never returned to another player.
--
-- Retention: cycle_locks records when each cycle locked (mark_locked). Answers
-- and guesses of a cycle are purged 14 days after that lock.
-- safety_flag is the M1 result; only 'none' may ever reach formation or output.
-- Deleting an answer removes its row: no tombstone text survives.

CREATE TABLE IF NOT EXISTS answers (
  answer_id       TEXT PRIMARY KEY,
  player_id       TEXT NOT NULL REFERENCES players ON DELETE CASCADE,
  cycle_id        TEXT NOT NULL,
  day             INTEGER NOT NULL CHECK (day BETWEEN 1 AND 5),
  question_id     TEXT NOT NULL,
  text            TEXT NOT NULL CHECK (length(text) BETWEEN 1 AND 400),
  source          TEXT NOT NULL CHECK (source IN ('voice', 'text')),
  is_catch_up     INTEGER NOT NULL CHECK (is_catch_up IN (0, 1)),
  follow_up_used  INTEGER NOT NULL CHECK (follow_up_used IN (0, 1)),
  weight          REAL NOT NULL CHECK (weight > 0 AND weight <= 1.1),
  safety_flag     TEXT NOT NULL CHECK (safety_flag IN ('none', 'distress', 'harm')),
  created_at      TEXT NOT NULL,
  edited_at       TEXT,
  UNIQUE (player_id, cycle_id, day)
);
CREATE INDEX IF NOT EXISTS answers_cycle ON answers (cycle_id);

CREATE TABLE IF NOT EXISTS guesses (
  player_id  TEXT NOT NULL REFERENCES players ON DELETE CASCADE,
  cycle_id   TEXT NOT NULL,
  percent    INTEGER NOT NULL CHECK (percent BETWEEN 0 AND 100),
  updated_at TEXT NOT NULL,
  PRIMARY KEY (player_id, cycle_id)
);

CREATE TABLE IF NOT EXISTS cycle_locks (
  cycle_id  TEXT PRIMARY KEY,
  locked_at TEXT NOT NULL
);
