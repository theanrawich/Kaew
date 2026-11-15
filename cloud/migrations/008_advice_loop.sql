BEGIN;
ALTER TABLE advice_log ADD COLUMN model TEXT;
ALTER TABLE advice_log ADD COLUMN fallback INTEGER NOT NULL DEFAULT 0 CHECK (fallback IN (0,1));
PRAGMA user_version = 8;
COMMIT;
