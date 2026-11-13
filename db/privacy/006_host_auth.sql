CREATE TABLE IF NOT EXISTS demo_host_sessions (
  session_id TEXT PRIMARY KEY REFERENCES sessions(session_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS demo_host_attempts (
  attempted_at TEXT NOT NULL
);
