CREATE TABLE IF NOT EXISTS notification_jobs (
  id TEXT PRIMARY KEY, kind TEXT NOT NULL, text TEXT NOT NULL, status TEXT NOT NULL,
  attempts INTEGER NOT NULL DEFAULT 0, next_attempt REAL NOT NULL, created_at REAL NOT NULL,
  delivered_at REAL, provider TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS alert_state (key TEXT PRIMARY KEY, value TEXT NOT NULL);
PRAGMA user_version = 4;
