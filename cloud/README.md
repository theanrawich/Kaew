# Kaew telemetry cloud — M4/M5 checkpoint

One Python 3.11 Render web service serves both the API and dashboard over HTTPS. Hosted storage is Supabase Postgres selected by `DATABASE_URL`; with that variable unset/empty, local development uses stdlib-only SQLite. The service serves a dashboard with separate device-write and admin-read bearer tokens. It provisions only `node-1`. This is a small course checkpoint service, not a hardened production cloud: no production identity management or rate limiting. Run exactly one web-service instance per database (including the notification scheduler). The hosted cloud already exists; this AI change has not been deployed, and physical end-to-end delivery remains unverified.

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
| `KAEW_DEVICE_TOKEN`, `KAEW_ADMIN_TOKEN` | Required, nonempty, distinct; no default credentials. Device token writes telemetry; admin token reads history and controls app settings. |
| `KAEW_HOST` | Default `127.0.0.1`. Hosted services use `0.0.0.0`. |
| `KAEW_PORT` | Overrides platform `PORT`; otherwise `PORT` or `8080`. Leave unset on Render. |
| `KAEW_TRUST_EDGE_HTTPS=1` | Allows public bind behind a TLS-terminating platform. It does not add TLS to Python or trust arbitrary forwarding headers. Only use when external traffic reaches a verified HTTPS edge and the backend HTTP port stays private. |
| `KAEW_DEV_ALLOW_INSECURE_LAN=1` | Separate development-only opt-in for LAN HTTP, exposing bearer tokens in plaintext. Not the hosted deployment path. |
| `DATABASE_URL` | **Required secret for hosted Render/Fly**, copied privately from Supabase with `sslmode=require`. If empty/unset, select local SQLite. Never commit the URL, password or Supabase keys. |
| `KAEW_DB_PATH` | Local SQLite filename only; ignored when `DATABASE_URL` selects Postgres. Parent directory must exist and be writable. |
| `PORT` | Provided automatically by Render; do not add a fixed port in Dashboard. |
| `PYTHON_VERSION` | Blueprint sets `3.11.11`. |
| `PYTHONDONTWRITEBYTECODE` | Blueprint sets `1`. |
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

For a subsequent deliberate CLI deploy, install/login yourself if needed:

```bash
curl -fsSL https://raw.githubusercontent.com/render-oss/cli/refs/heads/main/bin/install.sh | sh
render login
# Export RENDER_SERVICE_ID, DATABASE_URL and the two matching tokens privately.
bash cloud/deploy.sh render
```

The helper refuses missing/equal tokens or missing `DATABASE_URL` and never prints their values. It **does not upload or rotate Render secrets**, apply schema, or push local commits: set matching secrets in Dashboard first. It deploys the remote branch configured on the service. Missing CLI prints install/login guidance and exits non-zero. Official references: [Blueprint secret inputs](https://render.com/docs/blueprint-spec), [free instance limits](https://render.com/docs/free), [CLI](https://render.com/docs/cli).

## Local Postgres verification and implementation

`cloud/database.py` loads pinned psycopg v3 only when a Postgres target is selected. The adapter converts `?` to `%s` outside literals/comments and uses dictionary rows. Portable `ON CONFLICT` upserts work on both databases. An explicit transaction plus a transaction-level advisory writer lock preserves SQLite's read-before-write dedup/notification behavior for `BEGIN IMMEDIATE` paths. Connection/query failures use the existing retryable database-error family without logging credentials. Short-lived connections and one service instance suit this checkpoint, not a large-scale service.

Local SQLite tests need no dependency install. For a **disposable local** Postgres database, install `python -m pip install -r cloud/requirements.txt`, export `KAEW_TEST_POSTGRES_URL` to its loopback connection URL, and run `python -m unittest discover -s cloud -p 'test_postgres.py' -v`. These opt-in tests apply the schema twice and truncate Kaew tables; never point them at a real project. They reject non-loopback hosts and do not use `DATABASE_URL` to opt in. Without that test variable they skip before importing psycopg.

## Fly / Docker (secondary)

Render + Supabase is the selected path; existing Fly config remains an alternative, not a guaranteed free tier. Apply the same schema first. Export `KAEW_FLY_APP`, **`DATABASE_URL`** and the two distinct tokens privately, then run `bash cloud/deploy.sh fly` after installing/logging in to flyctl and provisioning an authorized app. The helper imports these three secrets over stdin and deploys with `cloud/fly.toml`, one Machine and a remote Docker builder. No Supabase URI belongs in TOML. See [Fly configuration](https://fly.io/docs/reference/configuration/) and [secret import](https://fly.io/docs/flyctl/secrets-import/).

The non-root Docker image includes psycopg from `cloud/requirements.txt`, Python 3.11 and `PYTHONDONTWRITEBYTECODE=1`. Build from repo root with `docker build -f cloud/Dockerfile -t kaew-cloud .`. Supply `DATABASE_URL` and both tokens at runtime behind a TLS edge. Without `DATABASE_URL`, the image falls back to `/data/kaew.sqlite3` for local experiments; retain it with a volume writable by UID 10001. Optional voice/model packages are not installed.

## Verify telemetry and gateway

Set `KAEW_BASE_URL=https://<your-host>` (or `http://127.0.0.1:8080` locally). With the private tokens exported:

```bash
curl --fail "$KAEW_BASE_URL/api/health"
curl --fail -X POST "$KAEW_BASE_URL/api/telemetry" \
  -H "Authorization: Bearer $KAEW_DEVICE_TOKEN" -H 'Content-Type: application/json' \
  -d '{"device_id":"node-1","session":9001,"seq":1,"level":"unknown","temperature_c":25.0,"tds_adc":65535,"source":"simulated"}'
curl --fail "$KAEW_BASE_URL/api/telemetry" -H "Authorization: Bearer $KAEW_ADMIN_TOKEN"
```

This sample is **simulated**, not hardware proof. Expect 201 on first insert and 200 on the same sample retry. Open the base URL, enter the admin token and reload history to find the row. Do not capture tokens in screenshots or shell tracing. An alternative Node.js 20+ simulator is `node cloud/simulate.mjs` with `KAEW_CLOUD_URL` set to the base URL and the device token exported. A raw ADC count is not calibrated TDS, and a single level switch does not measure tank volume.

For real telemetry copy [the local header example](../firmware/include/cloud_config.local.h.example) to ignored `firmware/include/cloud_config.local.h`. Set Wi-Fi, `KAEW_CLOUD_URL` to the **full** `https://<host>/api/telemetry`, the **device** token and the verified public root CA PEM for the host's current certificate chain. URL + token now auto-enable publishing; explicit `KAEW_CLOUD_ENABLED=0` forces it off. A nonempty CA and synchronized clock are still required; no TLS bypass is provided. Flash the gateway as in [firmware instructions](../firmware/README.md). Prove `source=device` arrives from the physical node, changes with measurements and survives dashboard reload; verify hosted service restart persistence in Supabase. See [checkpoint path](../docs/CHECKPOINT_CRITICAL_PATH.md).

Run tests:

```bash
python -m unittest discover -s cloud -p 'test_*.py' -v
```

The simulated gateway adapter persists a bounded SQLite outbox before delivery. `python cloud/gateway_push.py --worker` retries with backoff/jitter; use one worker per outbox. `--flush` performs one pass. Entries are removed only after HTTP 200/201. Set `KAEW_OUTBOX_PATH` for the ignored local database. HTTP failures remain queued, including permanent failures; dead-letter handling and multi-process leasing are not implemented.

Admin-authenticated `/api/events` records drink or fault events with a `measured`, `estimated`, or `simulated` source; `/api/summary` returns the rolling last 24 hours split by source. `/api/goal` stores a user-selected goal and is not medical guidance. `/api/reminder` stores one repeating reminder. The scheduler creates durable notification jobs for reminders, low-water transitions, fault events and offline transitions. A single delivery worker retries with backoff, marks a job failed after eight attempts, and limits sends to approximately one per second; low-water, fault and offline jobs have a five-minute per-kind cooldown. The default provider is a mock and sends nothing externally.

For Telegram, explicitly configure both `KAEW_TELEGRAM_TOKEN` and `KAEW_TELEGRAM_CHAT_ID` in the server process environment. This enables real outgoing notifications to that chat. Never commit or print the token. The adapter uses Telegram's HTTPS `sendMessage` API; integration tests inject a mock transport and **no real Telegram delivery has been verified**. A crash after Telegram accepts a message but before SQLite records success may cause a duplicate on retry. Run only one service instance per database; multi-process notification leasing is not implemented. Existing jobs remain bound to their original provider and are not silently redirected if configuration changes.

The admin-authenticated `/api/voice` endpoint accepts Thai text transcripts, not microphone audio. It handles wake-word-prefixed reminder and level queries, and explicitly declines refill and remote stop: no voice path can operate the pump. Reminders created by voice are one-shot and replace the existing reminder. The most recent level reports an observed switch state and may be delayed; it does not estimate remaining volume. `voice_pipeline.py` allows mock ASR/TTS injection for tests. There is no hardware audio or wake-word integration yet. Calendar-day statistics, production TLS/deployment and physical integration remain outstanding. Firmware actuation remains disabled.

## Experimental WAV and advisory paths

`audio_cli.py` accepts an explicitly selected mono 16-bit PCM 16 kHz WAV (maximum 15 s), runs local Faster-Whisper, calls the authenticated text-command API and writes the Google Cloud Thai TTS response as a WAV. This is an explicit file-based invocation; it is not a continuous wake-word detector. Audio input remains local, while the response text is sent to Google Cloud TTS. Use a private OAuth access token in `KAEW_GOOGLE_TTS_TOKEN`; the service can incur charges. Do not commit the token or private recordings. The existing `KAEW_ADMIN_TOKEN` is also required.

Install optional dependencies from `cloud/requirements-voice.txt` and provide a local CTranslate2 Faster-Whisper model directory. For example, after independently downloading a suitable multilingual model:

```powershell
$env:KAEW_ADMIN_TOKEN = '<local-admin-token>'
$env:KAEW_GOOGLE_TTS_TOKEN = '<short-lived-google-oauth-token>'
python cloud/audio_cli.py input.wav output.wav --model C:\path\to\local-model
```

If command execution succeeds but speech output fails, the result explicitly reports `audio_written: false`; the command is not repeated. The current tested Faster-Whisper tiny produced an inaccurate transcript on one public Thai sample, so model suitability and accuracy need representative evaluation. Real Google TTS was not tested without credentials. `AudioIO` contains opt-in I²S read/write drivers for the candidate pins, but microphone capture, invocation, buffering and streaming to this service, as well as actual speaker playback, are **not integrated or hardware-tested**.

For an isolated smoke test with a local model and WAV, run `python cloud/asr_smoke.py --model <local-model-dir> --wav <16k-mono-wav>`. This starts a temporary loopback backend and exercises real ASR and command handling; its TTS output is a generated test tone, not speech. A public Thai sample used for development is available from [Thai Speech 20K](https://huggingface.co/datasets/hotdogs/thai-speech-20k). Neither that single sample nor the mock tests establish Thai command accuracy.

### Local experimental Thai speech and model evaluation

For an optional no-credential TTS path install `cloud/requirements-local-models.txt` into a separate Python environment and download the [Meta MMS Thai model](https://huggingface.co/facebook/mms-tts-tha) to a local directory. Its model license is **CC-BY-NC-4.0**; assess usage rights before deployment. Model binaries and generated voice files must remain outside Git. `audio_cli.py` accepts `--tts-model <local-mms-dir>` instead of the Google token. Output is mono 16 kHz signed 16-bit PCM WAV. The local provider accepts Thai text and decimal integers only, and rejects unsupported characters. It is not a streaming or interruptible playback implementation.

For a reproducible isolated smoke run with real ASR and real TTS, use:

```powershell
python cloud/asr_smoke.py --model <whisper-dir> --wav <input.wav> --tts-model <mms-dir> --output <response.wav>
```

This does not force an intent or demonstrate a simulated refill. A `no_wake` response means the recognizer failed to detect the invocation and no action was executed. No personal audio is stored by the server; explicitly supplied input and output files are retained by the caller.

`cloud/generate_asr_corpus.py --model <mms-dir> --out <private-dir>` generates nine synthetic phrases from the tracked `asr_commands.json`. Run `cloud/asr_eval.py --model <whisper-dir> --manifest <private-dir>/manifest.json --output <private-dir>/results.json`. CER uses normalized Thai characters without whitespace; WER uses PyThaiNLP newmm tokens. This tiny, single synthetic voice corpus cannot establish real-world recognition accuracy or represent different speakers and noise conditions. Do not use its intent results to authorize physical dispensing.

`cloud/evaluate_hydration.py --model <qwen-dir>` runs three local advisory cases using the optional Transformers provider. Outputs are strictly validated, rejected on invalid JSON or invalid values, and always have `actuation_allowed: false`. The model is not integrated into the backend advice endpoint. Model output may contain unsupported medical claims and is not medical advice. The small-model experiment documented in `docs/EXECUTION.md` failed to produce acceptable decisions.

The experimental `--backend transformers` option in `audio_cli.py`, `asr_smoke.py`, and `asr_eval.py` supports a local [Thai-finetuned Whisper](https://huggingface.co/biodatlab/whisper-th-small-combined) model. For example, add `--backend transformers` to the smoke or evaluator command above. This is an offline CPU implementation, not a verified wake-word recognizer. The nine-phrase synthetic trial detected only one intended command correctly; do not enable unattended dispensing from it. Evaluate unrelated speech and representative human recordings before considering false activation rates or deployment. See the execution ledger for model-specific measurements.

For a schema-constrained local experiment, add `--constrained` to `evaluate_hydration.py`. JSON structure does not prove that a decision or its explanation is factually correct: the evaluated small model fabricated data in its explanation. Unknown goal or cup content remains null context; the advisory volume never authorizes actuation. Ollama requests also include the JSON schema, but no live Ollama server was tested.

`simulation/voice-bridge.mjs` is a standalone typed-command adapter to the existing UART simulation and plant, with tests for cup, tank, stale data and stop interlocks. It is **not connected to the backend voice endpoint**, does not persist actions, and cannot control hardware. Backend tank responses expire observations after five seconds of server receipt; receipt time does not prove the source measurement is fresh if an outbox delayed delivery.

## Closed-loop AI reminders (M4)

The model selects `next_reminder_minutes`; the server validates and clamps it to **15–180 minutes**, clamps advisory `suggested_ml` to **100–400 mL**, and writes the single `reminders` row (`id=1`, repeating, `next_due = decision timestamp + interval × 60`). This is a real software closed loop: persisted drinking/telemetry history → model decision → scheduled reminder → notification job → existing delivery worker → new history/next decision. Model output drives an actual timing decision rather than an if/else threshold. A model-backed decision has `fallback=false` even when clamped. **Suggested volume is advisory only. AI never controls the pump; stored outputs and API responses always have `actuation_allowed:false`.** No medical claims or invented volume sensors are intended.

Admin `POST /api/advice` with `{"include_simulated":false}` runs the full decision/log/schedule path and can replace a pending one-shot voice reminder for a demo. Admin `GET /api/advice` returns `{"advice": ...}` (null before the first decision), including interval, suggested volume, reason, model, fallback, epoch timestamp, `scheduled`, and `actuation_allowed:false`. The dashboard shows it and provides a manual trigger. Inputs and full outputs are recorded in the existing `advice_log`; model id and fallback are also separate columns. Old log rows remain historical records of the previous advisory contract.

New, non-duplicate drink events also decide and reschedule, without enqueueing an immediate “drink now” job. Simulated drink triggers include simulated history and label the log accordingly; normal automatic/manual decisions exclude simulated events and telemetry by default. Pending one-shot voice reminders (including overdue reminders awaiting delivery) are preserved by automatic decisions. Fault events never run inference. Repeating reminders first commit the notification job and temporarily advance the due time using their previous interval, then call the model **outside the SQLite writer transaction / Postgres advisory lock**, and commit the next decision and schedule together. Voice one-shots fire once and stay one-shot. A comparison with the reminder snapshot prevents a slow decision from overwriting a newer manual/voice schedule; such a logged decision reports `scheduled:false`.

We chose **decision-on-request plus a hook in the existing in-process reminder_loop**, with one process-local decision lock. There is no new cron, worker service, or paid addon; this fits the single free Render web service. Cold starts/free-plan sleep already pause the scheduler: late reminders fire after wakeup, so wake and check the service before the checkpoint video. Inference may delay an HTTP drink/manual response by up to about 9 seconds per provider (18 seconds with both hosted keys). Run one service instance per database; this is not a multi-process inference/notification leasing design.

Context is short and non-medical: rolling 24-hour drink count/volume, minutes since the last drink, Bangkok time of day, goal if set, latest persisted temperature and tank switch state with telemetry source, and previous reminder time/interval. Null cup content is unknown, not a dispensing authorization. Provider order is Groq, optional OpenRouter on failure or absence, then Ollama only if neither hosted key is set, then no-network fallback. HTTPS adapters use stdlib urllib, NoRedirect, a Kaew User-Agent, JSON response format and a 9-second timeout; no SDK dependency is added. Markdown JSON fences are accepted defensively; bad JSON, missing/extra fields, invalid types, nonfinite numbers, HTTP/transport errors or absent provider produce a **60-minute / 200 mL default** with `fallback=true` and still schedule. The model id is null when no model was attempted. Keys and transport exception details are never logged.

The default **`openai/gpt-oss-20b`** was confirmed in Groq's live models list on 2026-11-15 (11 models, no Llama chat model). It is a current Groq production model, the official replacement for deprecated free-tier `llama-3.1-8b-instant` after Llama chat was removed from free/developer tiers on 2026-08-16. Its approximately 1000 tokens/s speed suits a live demo, and the stated free-tier 30 RPM / 1K RPD limits are ample for one dispenser. Set **`KAEW_AI_MODEL=openai/gpt-oss-120b`** for the stronger Groq production option (also on that list). No other model id is hardcoded; limits/availability can change. OpenRouter uses the same `KAEW_AI_MODEL` value; check its availability separately.

After review/merge the operator must apply Postgres **002** in Supabase, set the **`GROQ_API_KEY` secret on `kaew-cloud` in Render**, then deploy from **`prod` (or the reviewed branch)**. Existing database/admin/device secrets remain private. No AI key is required to start, and no AI secrets have been added as mandatory Blueprint inputs. The server reads process environment and does not load `.env` itself. No live SQL or deployment is performed by this change. Software tests establish scheduling and mock delivery; hardware and live Telegram delivery still require checkpoint evidence.
