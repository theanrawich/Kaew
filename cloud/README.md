# Kaew telemetry cloud — M4/M5 checkpoint

One Python 3.11 Render web service serves both the API and dashboard over HTTPS. Hosted storage is Supabase Postgres selected by `DATABASE_URL`; with that variable unset/empty, local development uses stdlib-only SQLite. The service serves a dashboard with separate device-write and admin-read bearer tokens. It provisions only `node-1`. This is a small course checkpoint service, not a hardened production cloud: no production identity management or rate limiting. Run exactly one web-service instance per database (including the notification scheduler). The hosted cloud already exists; this AI change has not been deployed, and physical end-to-end delivery remains unverified.

## Layout

- `server.py`: thin launcher; run `python cloud/server.py` from the repository root or `python server.py` from `cloud/`.
- `kaew/`: HTTP service, database adapters, notifications, advice and audio/voice services.
- `static/`: dashboard and speech-to-text pages, served at `/` and `/stt`.
- `migrations/`: numbered SQLite migrations and explicit Postgres schemas.
- `tests/`: unittest suite; discover from the repository root with `-s cloud/tests -t cloud`.

## Local run

From the repository root, generate two different long random tokens privately. Bash example (values stay out of command history):

```bash
read -rsp 'Device token: ' KAEW_DEVICE_TOKEN; echo
read -rsp 'Admin token: ' KAEW_ADMIN_TOKEN; echo
export KAEW_DEVICE_TOKEN KAEW_ADMIN_TOKEN
python cloud/server.py
```

Use `python3` if your system has no `python` alias. The server reads process environment, not `.env` automatically. `cloud/.env.example` lists placeholders; never commit your `.env`, database or tokens. Open `http://127.0.0.1:8080/` and enter the admin token; it stays in page memory until reload. The default database is `cloud/kaew.sqlite3` (ignored). Leave `DATABASE_URL` unset for SQLite; psycopg is neither imported nor required in this mode. Existing local SQLite data is not automatically copied to Postgres.

| Variable | Behavior |
| --- | --- |
| `KAEW_DEVICE_TOKEN`, `KAEW_ADMIN_TOKEN` | Required, nonempty, distinct; no default credentials. Device token writes telemetry and reads the restricted bound advice view; admin token reads history and controls app settings. |
| `KAEW_HOST` | Default `127.0.0.1`. Hosted services use `0.0.0.0`. |
| `KAEW_PORT` | Overrides platform `PORT`; otherwise `PORT` or `8080`. Leave unset on Render. |
| `KAEW_TRUST_EDGE_HTTPS=1` | Allows public bind behind a TLS-terminating platform. It does not add TLS to Python or trust arbitrary forwarding headers. Only use when external traffic reaches a verified HTTPS edge and the backend HTTP port stays private. |
| `KAEW_DEV_ALLOW_INSECURE_LAN=1` | Separate development-only opt-in for LAN HTTP, exposing bearer tokens in plaintext. Not the hosted deployment path. |
| `DATABASE_URL` | **Required secret for hosted Render**, copied privately from Supabase with `sslmode=require`. If empty/unset, select local SQLite. Never commit the URL, password or Supabase keys. |
| `KAEW_DB_PATH` | Local SQLite filename only; ignored when `DATABASE_URL` selects Postgres. Parent directory must exist and be writable. |
| `PORT` | Provided automatically by Render; do not add a fixed port in Dashboard. |
| `PYTHON_VERSION` | Blueprint sets `3.11.11`. |
| `PYTHONDONTWRITEBYTECODE` | Blueprint sets `1`. |
| `TYPHOON_API_KEY` | Optional **secret** at startup. Required for speech-to-text at `/api/stt`. |
| `GROQ_API_KEY` | Optional **secret**; enables the primary Groq Chat Completions provider. Missing key does not prevent startup. |
| `KAEW_AI_MODEL` | Optional non-secret model id, default `openai/gpt-oss-20b`. Used for Groq and optional OpenRouter. Set `openai/gpt-oss-120b` for the stronger Groq production option. |
| `OPENROUTER_API_KEY` | Optional **secret** secondary provider, used when Groq is absent or fails validation/transport. Same model id; availability and charges may differ on OpenRouter. |
| `KAEW_OLLAMA_MODEL` | Optional loopback Ollama model, used only when neither hosted key is set. Otherwise no provider means recorded deterministic fallback with no network. |
| `KAEW_TELEGRAM_TOKEN`, `KAEW_TELEGRAM_CHAT_ID` | Optional pair; both required to activate Telegram, otherwise mock provider. Configure privately in host environment. |

## Render + Supabase (chosen hosted stack)

The target Supabase project already exists: **`kaew`**, ref **`hhzukhrznuvtwsgipyio`**, region `ap-southeast-1`, organization `emb-sengkeng`, free plan. The ref identifies the target project only; no connection URI is constructed from it. Render is connected on the owner's side. This change does not open either dashboard, retrieve passwords, apply remote SQL, create accounts or deploy. The parent/operator performs these steps later:

1. In that Supabase project, apply **[`cloud/migrations/postgres/001_initial.sql`](migrations/postgres/001_initial.sql)** followed by **[`002_advice_loop.sql`](migrations/postgres/002_advice_loop.sql)** (existing installations need only 002) through the Supabase connector or SQL editor. It creates all nine tables, indexes, telemetry dedup constraint and `node-1`, inside one transaction. `IF NOT EXISTS` allows reapplying this initial schema; it does not upgrade an incompatible existing schema. Tables use epoch-second `DOUBLE PRECISION` times, `BIGINT` UART IDs and `BIGSERIAL` generated IDs. RLS is enabled without browser policies: connect the backend as the table owner; no Supabase browser/service keys are used.
2. Copy the actual Postgres connection URI from the project's **Connect** dialog privately into Render's **`DATABASE_URL`** secret. Include `sslmode=require`, adding it to any existing query options. Never paste it into source files, Git, logs or chat. Prefer the **Session pooler** for this long-running service and IPv4 compatibility. The **Transaction pooler** also works: the adapter disables automatic prepared statements and uses transaction-scoped locks, not session state. Do not use a Data API URL or Supabase API key as a Postgres URI. Use the project's actual URI/password; none is supplied or guessed here. See [Supabase connection options](https://supabase.com/docs/guides/database/connecting-to-postgres) and [psycopg prepared-statement behavior](https://www.psycopg.org/psycopg3/docs/advanced/prepare.html).
3. When ready, make this branch available remotely yourself. In the connected Render account, apply the existing root `render.yaml` Blueprint for `theanrawich/Kaew`, selecting **`prod`** after merge (or the reviewed branch). There is exactly **one web service**, `kaew-cloud`; `/` serves the dashboard and `/api/*` serves the backend. The Blueprint installs `cloud/requirements.txt` and starts `python cloud/server.py`. It does not create a Render database or a separate dashboard service.
4. Set the three **required secrets**: `DATABASE_URL`, `KAEW_DEVICE_TOKEN` and `KAEW_ADMIN_TOKEN`. Use distinct long random device/admin tokens. New Blueprints prompt for the `sync: false` variables; for an existing service, add/update them in **Environment** because later Blueprint syncs do not replace secret values. Optionally set **both** `KAEW_TELEGRAM_TOKEN` and `KAEW_TELEGRAM_CHAT_ID` there for alerts. They are dashboard-only optionals, not mandatory Blueprint inputs.
5. Keep Blueprint values `KAEW_HOST=0.0.0.0`, `KAEW_TRUST_EDGE_HTTPS=1`, `PYTHON_VERSION=3.11.11`, `PYTHONDONTWRITEBYTECODE=1`. Let Render supply `PORT`; leave `KAEW_PORT` and `KAEW_DB_PATH` unset on Render. Automatic deploy is disabled. After applying Postgres 002, set optional `GROQ_API_KEY` privately on `kaew-cloud` and deliberately deploy from `prod` after merge (or the reviewed branch). This implementation does not deploy. Startup verifies the Postgres tables/columns and seed device; missing schema fails with the SQL file path. It never runs SQLite PRAGMA/migrations on Postgres and never silently falls back if a configured Postgres connection fails.
6. Check `https://<service>.onrender.com/api/health`, POST the labeled test sample below with the device token, then open `https://<service>.onrender.com/` and enter the admin token to read it back. Verify readback after a web-service restart: records live in Supabase, not Render's ephemeral disk. Keep backups/exports according to the database plan; persistent hosting alone is not a backup. The unauthenticated health route is a process check, not a continuous database readiness probe.

No Render disk is required for hosted telemetry now. Free web-service sleep/cold starts still pause scheduled reminders and may trigger gateway retries; wake and check the service before recording. Supabase free-plan availability/limits should also be checked before the checkpoint. No hosted deployment or physical end-to-end test has been performed here.

## Local Postgres verification and implementation

`cloud/kaew/database.py` loads pinned psycopg v3 only when a Postgres target is selected. The adapter converts `?` to `%s` outside literals/comments and uses dictionary rows. Portable `ON CONFLICT` upserts work on both databases. An explicit transaction plus a transaction-level advisory writer lock preserves SQLite's read-before-write dedup/notification behavior for `BEGIN IMMEDIATE` paths. Connection/query failures use the existing retryable database-error family without logging credentials. Short-lived connections and one service instance suit this checkpoint, not a large-scale service.

Local SQLite tests need no dependency install. For a **disposable local** Postgres database, install `python -m pip install -r cloud/requirements.txt`, export `KAEW_TEST_POSTGRES_URL` to its loopback connection URL, and run `python -m unittest discover -s cloud/tests -t cloud -p 'test_postgres.py' -v`. These opt-in tests apply the schema twice and truncate Kaew tables; never point them at a real project. They reject non-loopback hosts and do not use `DATABASE_URL` to opt in. Without that test variable they skip before importing psycopg.

## Verify telemetry and gateway

Set `KAEW_BASE_URL=https://<your-host>` (or `http://127.0.0.1:8080` locally). With the private tokens exported:

```bash
curl --fail "$KAEW_BASE_URL/api/health"
curl --fail -X POST "$KAEW_BASE_URL/api/telemetry" \
  -H "Authorization: Bearer $KAEW_DEVICE_TOKEN" -H 'Content-Type: application/json' \
  -d '{"device_id":"node-1","session":9001,"seq":1,"level":"unknown","temperature_c":25.0,"tds_adc":65535,"source":"simulated"}'
curl --fail "$KAEW_BASE_URL/api/telemetry" -H "Authorization: Bearer $KAEW_ADMIN_TOKEN"
```

This sample is **simulated**, not hardware proof. Expect 201 on first insert and 200 on the same sample retry. Open the base URL, enter the admin token and reload history to find the row. Do not capture tokens in screenshots or shell tracing. A raw ADC count is not calibrated TDS, and a single level switch does not measure tank volume.

For real telemetry copy [the local header example](../firmware/include/cloud_config.local.h.example) to ignored `firmware/include/cloud_config.local.h`. Set Wi-Fi, `KAEW_CLOUD_URL` to the **full** `https://<host>/api/telemetry`, the **device** token and the verified public root CA PEM for the host's current certificate chain. URL + token now auto-enable publishing; explicit `KAEW_CLOUD_ENABLED=0` forces it off. A nonempty CA and synchronized clock are still required; no TLS bypass is provided. Flash the gateway as in [firmware instructions](../firmware/README.md). Prove `source=device` arrives from the physical node, changes with measurements and survives dashboard reload; verify hosted service restart persistence in Supabase. See [checkpoint path](../docs/course/checkpoint-critical-path.md).

Run tests:

```bash
python -m unittest discover -s cloud/tests -t cloud -p 'test_*.py' -v
```

Admin-authenticated `GET /api/events` returns event history, and `GET /api/summary` returns the rolling last 24 hours split by source. Admin event producers can post drink or fault events with a `measured`, `estimated`, or `simulated` source. The device token can post only measured drinks of 10–1000 mL, with IDs in the reserved `gateway-1:<boot-high>:<boot-low>:<sequence>` namespace (three eight-digit lowercase hexadecimal fields). Retries reuse the same ID.

Admin `GET/POST /api/profile` returns `body_weight_kg` and the derived `goal_ml`. Send only `body_weight_kg` (20–250 kg); it is stored to the nearest gram. The goal is 33 mL/kg rounded to the nearest milliliter and bounded to 1,000–4,000 mL. Both values are null until weight is saved. Admin `GET /api/goal` returns the derived goal alone, and `GET /api/reminder` returns the current schedule. The scheduler creates durable notification jobs for reminders, low-water transitions, fault events and offline transitions. A single delivery worker retries with backoff, marks a job failed after eight attempts, and limits sends to approximately one per second; low-water, fault and offline jobs have a five-minute per-kind cooldown. The default provider is a mock and sends nothing externally.

For Telegram, explicitly configure both `KAEW_TELEGRAM_TOKEN` and `KAEW_TELEGRAM_CHAT_ID` in the server process environment. This enables real outgoing notifications to that chat. Never commit or print the token. The adapter uses Telegram's HTTPS `sendMessage` API; integration tests inject a mock transport and **no real Telegram delivery has been verified**. A crash after Telegram accepts a message but before SQLite records success may cause a duplicate on retry. Run only one service instance per database; multi-process notification leasing is not implemented. Existing jobs remain bound to their original provider and are not silently redirected if configuration changes.

The admin-authenticated `/api/voice` endpoint accepts text transcripts. With the wake word `แก้ว`, it reports device connection status or today’s water intake, and declines refill requests. For example, `แก้ว วันนี้ดื่มไปเท่าไหร่` reads the Asia/Bangkok calendar-day total, the weight-based goal used by the hydration adviser, and progress toward that goal. It uses measured and estimated drinks when available and labels any simulated-only total. Other wake-word commands return `unknown`. Text without the wake word returns `no_wake`. Invalid inputs receive HTTP 400. Voice refill remains blocked and firmware actuation remains disabled.

## Closed-loop AI reminders (M4)

Gateway integration adds a read-only device view: `GET /api/advice?gateway=1&boot_session=...&request_id=...&cup_session=...&nonce=...` with the existing device token returns only version, echoed identifiers, advice ID/age, suggested mL, model-backed status and `actuation_allowed:false`. It excludes simulated-input decisions, rejects missing/stale data and exposes no history/reason. The device token can trigger inference by submitting a new measured drink. Admin advice history is read-only. See [full contract, consent/freshness gates and deployment handoff](../docs/design/m4-gateway-ai-loop.md). This source change has not been deployed to production by the implementation task.

The model selects `next_reminder_minutes`; the server validates and clamps it to **15–180 minutes**, clamps advisory `suggested_ml` to **100–400 mL**, and writes the single `reminders` row (`id=1`, repeating, `next_due = decision timestamp + interval × 60`). This is a real software closed loop: persisted drinking/telemetry history → model decision → scheduled reminder → notification job → existing delivery worker → new history/next decision. Model output drives an actual timing decision rather than an if/else threshold. A model-backed decision has `fallback=false` even when clamped. **Suggested volume is advisory; the cloud never authorizes a pump and all outputs retain `actuation_allowed:false`.** The optional [locally confirmed gateway AI path](../docs/design/m4-gateway-ai-loop.md) can use a fresh suggestion as a bounded target only after separate local consent and all gateway/hardware interlocks. No medical claims or invented volume sensors are intended.

Admin `GET /api/advice` returns `{"advice": ...}` (null before the first decision), including interval, suggested volume, reason, model, fallback, epoch timestamp, `scheduled`, and `actuation_allowed:false`. The dashboard shows the latest decision. Inputs and full outputs are recorded in the existing `advice_log`; model id and fallback are also separate columns. Old log rows remain historical records of the previous advisory contract.

At startup, the server runs advice if the reminder row is missing, including before body weight has been saved. The reminder loop also checks for a missing schedule and attempts to restore it at most once per minute. Saving body weight and recording a new, non-duplicate drink both run advice immediately. A decision updates the schedule without sending an immediate reminder. Simulated drink triggers include simulated history and label the log accordingly; other automatic decisions exclude simulated events and telemetry. Fault events skip inference. When a repeating reminder fires, the scheduler commits the notification job and temporarily advances the due time using the previous interval. It then runs inference outside the writer transaction and commits the decision and schedule together. The reminder snapshot prevents a slow decision from overwriting a newer schedule.

We chose **decision-on-request plus a hook in the existing in-process reminder_loop**, with one process-local decision lock. There is no new cron, worker service, or paid addon; this fits the single free Render web service. Cold starts/free-plan sleep already pause the scheduler: late reminders fire after wakeup, so wake and check the service before the checkpoint video. Inference may delay startup or an HTTP drink/profile response by up to about 9 seconds per provider (18 seconds with both hosted keys). Run one service instance per database; this is not a multi-process inference/notification leasing design.

Context is short and non-medical: rolling 24-hour drink count/volume, minutes since the last drink, Bangkok time of day, body weight and goal if set, latest persisted temperature and tank switch state with telemetry source, and previous reminder time/interval. Null cup content is unknown, not a dispensing authorization. Provider order is Groq, optional OpenRouter on failure or absence, then Ollama only if neither hosted key is set, then no-network fallback. HTTPS adapters use stdlib urllib, NoRedirect, a Kaew User-Agent, JSON response format and a 9-second timeout; no SDK dependency is added. Markdown JSON fences are accepted defensively; bad JSON, missing/extra fields, invalid types, nonfinite numbers, HTTP/transport errors or absent provider produce a **60-minute / 200 mL default** with `fallback=true` and still schedule. The model id is null when no model was attempted. Keys and transport exception details are never logged.

The default **`openai/gpt-oss-20b`** was confirmed in Groq's live models list on 2026-11-15 (11 models, no Llama chat model). It is a current Groq production model, the official replacement for deprecated free-tier `llama-3.1-8b-instant` after Llama chat was removed from free/developer tiers on 2026-08-16. Its approximately 1000 tokens/s speed suits a live demo, and the stated free-tier 30 RPM / 1K RPD limits are ample for one dispenser. Set **`KAEW_AI_MODEL=openai/gpt-oss-120b`** for the stronger Groq production option (also on that list). No other model id is hardcoded; limits/availability can change. OpenRouter uses the same `KAEW_AI_MODEL` value; check its availability separately.

After review/merge the operator must apply Postgres **002** in Supabase, set the **`GROQ_API_KEY` secret on `kaew-cloud` in Render**, then deploy from **`prod` (or the reviewed branch)**. Existing database/admin/device secrets remain private. No AI key is required to start, and no AI secrets have been added as mandatory Blueprint inputs. The server reads process environment and does not load `.env` itself. No live SQL or deployment is performed by this change. Software tests establish scheduling and mock delivery; hardware and live Telegram delivery still require checkpoint evidence.

## Gateway speech

Set `TYPHOON_API_KEY` privately in the server environment. On Render, set it
on the `kaew-cloud` service. The server uses the hosted
[`typhoon-asr-realtime` file transcription API](https://docs.opentyphoon.ai/en/asr/).

POST raw `audio/wav` to `/api/stt` with the admin Bearer token. Input must be
non-silent mono 16-bit 16 kHz PCM WAV, at most 15 seconds and 2,000,000 bytes.
The response contains `text` and `model`. Add `?command=1` to process the
transcript through the same command logic as `/api/voice`. A missing key
returns 503 (`stt_unavailable`). Transcription failures return 422
(`stt_failed`).

Install `cloud/requirements.txt` for spoken replies. EdgeTTS tries Niwat
then Premwadee, twice per voice, and miniaudio decodes MP3 in-process.
When speech succeeds, the command includes `reply_audio_id`. Use the same
admin bearer token to GET `/api/tts/<id>` within two minutes. The download
is mono 16-bit PCM WAV at 16 kHz, up to 15 seconds. The JSON reply works
on its own when synthesis is unavailable or when the wake word is absent.

With its device token, the gateway polls `GET /api/gateway/reminder` for
`reminder_id`. It can fetch that ID from `/api/tts/<id>` using the device
token for two minutes after the reminder fires. The two fixed Thai phrases
are cached in memory. Command downloads are held in a 16-entry bounded cache.

At `/stt`, enter the admin token (whitespace and surrounding quotes are trimmed;
it is stored in sessionStorage). This display-only page polls `/api/stt/recent`
every two seconds and shows ESP32 clips newest first with Bangkok times.
The admin-only history keeps the last 50 Typhoon attempts in memory until
restart. Each entry includes the transcript or error, model, timestamp, and
elapsed milliseconds including the provider network round trip.

### Live dashboard sensors

The dashboard uses authenticated `GET /api/telemetry/stream` SSE via streaming
fetch with the admin Bearer header; tokens stay out of the URL. Each connection
receives the newest 100 telemetry rows plus the latest gateway scale reading.
The server checks committed data every 500 ms and sends a snapshot when either
changes, including writes from other processes sharing the database. This adds
up to about 500 ms plus database, network and rendering time after cloud ingestion;
physical sampling and gateway upload rates still limit how fresh readings can be.

The stream sends a heartbeat after 15 seconds of silence. The browser aborts a
connection after 25 seconds without a complete event/heartbeat and retries after
two seconds. Until the first snapshot and during failures, the existing five-second
telemetry refresh and three-second scale refresh provide fallback. Other dashboard
panels retain their five-second cadence. Scale readings expire after 10 seconds
without a new measurement, including while SSE remains connected.

Each open dashboard uses a handler thread, one read database connection and four
SQL queries per second (two SELECTs per 500 ms check). This is intended for a small project dashboard. Keep
proxy response buffering disabled for this route (`X-Accel-Buffering: no` is sent).
Deploy backend and dashboard together and verify the hosting proxy delivers events
without buffering; local tests do not prove hosted latency.

Tests: `python3 -m unittest discover -s cloud/tests -t cloud -p 'test_realtime.py' -v`
and `node --test cloud/tests/*.test.mjs` from the repository root.
