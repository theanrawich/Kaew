-- Apply once to the target Supabase project before starting the web service.
-- Same logical schema as SQLite migrations 001–007. Times are Unix epoch seconds.
BEGIN;
CREATE TABLE IF NOT EXISTS public.devices (
  id TEXT PRIMARY KEY,
  last_seen DOUBLE PRECISION
);
CREATE TABLE IF NOT EXISTS public.telemetry (
  id BIGSERIAL PRIMARY KEY,
  device_id TEXT NOT NULL REFERENCES public.devices(id),
  session BIGINT NOT NULL,
  seq BIGINT NOT NULL,
  level TEXT NOT NULL,
  temperature_c DOUBLE PRECISION,
  tds_adc INTEGER NOT NULL,
  received_at DOUBLE PRECISION NOT NULL,
  source TEXT NOT NULL DEFAULT 'unknown',
  UNIQUE (device_id, session, seq)
);
CREATE INDEX IF NOT EXISTS telemetry_device_time ON public.telemetry(device_id, received_at);
CREATE TABLE IF NOT EXISTS public.events (
  id TEXT PRIMARY KEY,
  kind TEXT NOT NULL,
  source TEXT NOT NULL,
  volume_ml DOUBLE PRECISION,
  received_at DOUBLE PRECISION NOT NULL
);
CREATE INDEX IF NOT EXISTS events_received_time ON public.events(received_at);
CREATE TABLE IF NOT EXISTS public.reminders (
  id INTEGER PRIMARY KEY CHECK (id=1),
  interval_minutes INTEGER NOT NULL,
  next_due DOUBLE PRECISION NOT NULL,
  repeat_enabled INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS public.notifications (
  id BIGSERIAL PRIMARY KEY,
  reminder_due DOUBLE PRECISION NOT NULL UNIQUE,
  provider TEXT NOT NULL,
  created_at DOUBLE PRECISION NOT NULL
);
CREATE TABLE IF NOT EXISTS public.settings (
  key TEXT PRIMARY KEY,
  value INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS public.notification_jobs (
  id TEXT PRIMARY KEY,
  kind TEXT NOT NULL,
  text TEXT NOT NULL,
  status TEXT NOT NULL,
  attempts INTEGER NOT NULL DEFAULT 0,
  next_attempt DOUBLE PRECISION NOT NULL,
  created_at DOUBLE PRECISION NOT NULL,
  delivered_at DOUBLE PRECISION,
  provider TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS notification_jobs_pending ON public.notification_jobs(provider, status, next_attempt);
CREATE TABLE IF NOT EXISTS public.alert_state (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS public.advice_log (
  id BIGSERIAL PRIMARY KEY,
  created_at DOUBLE PRECISION NOT NULL,
  input_json TEXT NOT NULL,
  output_json TEXT NOT NULL,
  simulated INTEGER NOT NULL
);
INSERT INTO public.devices(id) VALUES ('node-1') ON CONFLICT (id) DO NOTHING;
-- Backend connects as the table owner. No browser/anon Data API policies/grants.
ALTER TABLE public.devices ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.telemetry ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.reminders ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.notifications ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.notification_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.alert_state ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.advice_log ENABLE ROW LEVEL SECURITY;
COMMIT;
