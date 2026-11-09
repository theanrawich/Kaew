CREATE TABLE IF NOT EXISTS devices (
  id TEXT PRIMARY KEY,
  last_seen REAL
);
CREATE TABLE IF NOT EXISTS telemetry (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  device_id TEXT NOT NULL REFERENCES devices(id),
  session INTEGER NOT NULL,
  seq INTEGER NOT NULL,
  level TEXT NOT NULL,
  temperature_c REAL,
  tds_adc INTEGER NOT NULL,
  received_at REAL NOT NULL,
  UNIQUE (device_id, session, seq)
);
CREATE INDEX IF NOT EXISTS telemetry_device_time ON telemetry(device_id, received_at);
PRAGMA user_version = 1;
