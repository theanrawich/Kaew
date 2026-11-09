BEGIN;
ALTER TABLE telemetry ADD COLUMN source TEXT NOT NULL DEFAULT 'unknown';
PRAGMA user_version = 6;
COMMIT;
