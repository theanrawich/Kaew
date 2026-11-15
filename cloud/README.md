# Kaew telemetry cloud — M5 checkpoint

The stdlib-only Python 3.11 service can run locally or behind a platform HTTPS edge. It stores raw telemetry in SQLite and serves a dashboard with separate device-write and admin-read bearer tokens. It provisions only `node-1`. This is a small course checkpoint service, not a hardened production cloud: no production identity management or rate limiting. Run exactly one instance per database. Hosting configuration is ready; **no service has been deployed or tested against hardware**.

## Local run

From the repository root, generate two different long random tokens privately. Bash example (values stay out of command history):

```bash
read -rsp 'Device token: ' KAEW_DEVICE_TOKEN; echo
read -rsp 'Admin token: ' KAEW_ADMIN_TOKEN; echo
export KAEW_DEVICE_TOKEN KAEW_ADMIN_TOKEN
python cloud/server.py
```

Use `python3` if your system has no `python` alias. The server reads process environment, not `.env` automatically. `cloud/.env.example` lists placeholders; never commit your `.env`, database or tokens. Open `http://127.0.0.1:8080/` and enter the admin token; it stays in page memory until reload. The default database is `cloud/kaew.sqlite3` (ignored).

| Variable | Behavior |
| --- | --- |
| `KAEW_DEVICE_TOKEN`, `KAEW_ADMIN_TOKEN` | Required, nonempty, distinct; no default credentials. Device token writes telemetry; admin token reads history and controls app settings. |
| `KAEW_HOST` | Default `127.0.0.1`. Hosted services use `0.0.0.0`. |
| `KAEW_PORT` | Overrides platform `PORT`; otherwise `PORT` or `8080`. Leave unset on Render. |
| `KAEW_TRUST_EDGE_HTTPS=1` | Allows public bind behind a TLS-terminating platform. It does not add TLS to Python or trust arbitrary forwarding headers. Only use when external traffic reaches a verified HTTPS edge and the backend HTTP port stays private. |
| `KAEW_DEV_ALLOW_INSECURE_LAN=1` | Separate development-only opt-in for LAN HTTP, exposing bearer tokens in plaintext. Not the hosted deployment path. |
| `KAEW_DB_PATH` | SQLite filename; parent directory must exist and be writable. |
| `KAEW_TELEGRAM_TOKEN`, `KAEW_TELEGRAM_CHAT_ID` | Optional pair; both required to activate Telegram, otherwise mock provider. Configure privately in host environment. |

## Render (primary, free HTTPS)

Required from the owner: a **Render account logged in at https://dashboard.render.com**, permission to connect this GitHub repo, a chosen deploy branch/commit, two distinct private tokens, and later the service URL. GitHub CLI login alone does not authorize Render. No credentials need to be sent in chat.

1. Make this committed branch available on GitHub when you choose to publish it; this task does not push it. In Render choose **New → Blueprint**, select `theanrawich/Kaew`, the branch containing these files, and root `render.yaml`.
2. Supply `KAEW_DEVICE_TOKEN` and `KAEW_ADMIN_TOKEN` when prompted. They are `sync: false`, so update/rotate them through Dashboard Environment later. The Blueprint uses native Python 3.11, `python cloud/server.py`, `/api/health`, and platform `PORT`. No Docker is required. Automatic deploy is disabled; deploy deliberately.
3. Wait for health to pass. Copy the assigned `https://<service>.onrender.com` URL; check `/api/health`. The domain is assigned by Render, not promised by this repo.
4. For subsequent one-command deploys, install/login yourself, export `RENDER_SERVICE_ID` (the `srv-...` ID) and the same device/admin tokens privately, then run `bash cloud/deploy.sh render`. The helper validates local tokens but **does not upload or rotate Render secrets**; set matching values in Dashboard first. It deploys the remote branch configured on the service, not unpushed local code.

Missing CLI setup (the helper prints this and exits non-zero; it never installs or logs in automatically):

```bash
curl -fsSL https://raw.githubusercontent.com/render-oss/cli/refs/heads/main/bin/install.sh | sh
render login
```

Render Free sleeps when idle and **has no persistent disk**. `/tmp/kaew.sqlite3` can disappear on restart/redeploy; do not treat it as durable checkpoint evidence. Export sanitized evidence before restarting. For restart-persistence proof, use a paid instance with a persistent disk mounted at `/var/data`, set `KAEW_DB_PATH=/var/data/kaew.sqlite3`, and back it up with SQLite's backup API. A single instance and a volume do not replace backups. Wake the service and verify health before recording; cold starts may exceed the gateway's request timeout and cause retries. Scheduled Telegram reminders will not run while a free service sleeps.

Official references: [Blueprint schema and secret inputs](https://render.com/docs/blueprint-spec), [free instance limits](https://render.com/docs/free), [CLI install/login](https://render.com/docs/cli), [deploy command](https://render.com/docs/cli-reference).

## Fly (secondary)

Fly is an alternative HTTPS host, **not a guaranteed free tier**; account/billing approval may be required. The user must provide a logged-in Fly account, organization/app name and secrets. Install and provision deliberately:

```bash
curl -L https://fly.io/install.sh | sh
export PATH="$HOME/.fly/bin:$PATH"
flyctl auth login
flyctl apps create <unique-app-name>
export KAEW_FLY_APP=<unique-app-name>
# Read/export distinct KAEW_DEVICE_TOKEN and KAEW_ADMIN_TOKEN privately as above.
bash cloud/deploy.sh fly
```

The helper imports secrets over stdin and builds from repo root with `cloud/Dockerfile`, `cloud/fly.toml`, a remote builder and one Machine (`--ha=false`). No local Docker is required. The config sets `force_https`, private port 8080, `/api/health` and explicit edge trust. `/tmp/kaew.sqlite3` is ephemeral here too. For durable storage create a Fly volume in the app's region, add `[mounts]` with `source = "kaew_data"` and `destination = "/data"`, and set `KAEW_DB_PATH=/data/kaew.sqlite3`. Ensure the mounted directory is writable by container UID 10001 (volume ownership must be provisioned separately); only one Machine may use this SQLite file. Keep independent backups. See [Fly config](https://fly.io/docs/reference/configuration/) and [secret import](https://fly.io/docs/flyctl/secrets-import/).

The non-root Docker image uses Python 3.11, no voice/model dependencies, and `PYTHONDONTWRITEBYTECODE=1`. Build from repo root with `docker build -f cloud/Dockerfile -t kaew-cloud .`. Publish its internal HTTP port only through a TLS edge; supply both secrets at runtime and mount writable storage if retaining records.

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

For real telemetry copy [the local header example](../firmware/include/cloud_config.local.h.example) to ignored `firmware/include/cloud_config.local.h`. Set Wi-Fi, `KAEW_CLOUD_URL` to the **full** `https://<host>/api/telemetry`, the **device** token and the verified public root CA PEM for the host's current certificate chain. URL + token now auto-enable publishing; explicit `KAEW_CLOUD_ENABLED=0` forces it off. A nonempty CA and synchronized clock are still required; no TLS bypass is provided. Flash the gateway as in [firmware instructions](../firmware/README.md). Prove `source=device` arrives from the physical node, changes with measurements and survives dashboard reload; verify service restart persistence only on durable storage. See [checkpoint path](../docs/CHECKPOINT_CRITICAL_PATH.md).

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

For a schema-constrained local experiment, add `--constrained` to `evaluate_hydration.py`. JSON structure does not prove that a decision or its explanation is factually correct: the evaluated small model fabricated data in its explanation. Missing goal or cup content causes a deterministic fallback; model outputs do not authorize actuation. Ollama requests also include the JSON schema, but no live Ollama server was tested.

`simulation/voice-bridge.mjs` is a standalone typed-command adapter to the existing UART simulation and plant, with tests for cup, tank, stale data and stop interlocks. It is **not connected to the backend voice endpoint**, does not persist actions, and cannot control hardware. Backend tank responses expire observations after five seconds of server receipt; receipt time does not prove the source measurement is fresh if an outbox delayed delivery.

`POST /api/advice` with admin authentication and `{"include_simulated":false}` obtains an advisory from an optional loopback Ollama model selected with `KAEW_OLLAMA_MODEL`, using persisted intake and goal data. Without a running model or with invalid/low-confidence output it falls back to zero refill and a 60-minute reminder. It records the request and response. Model-reported confidence is not a calibrated probability; recommendations are not medical advice. Cup data is currently unknown to this endpoint, so suggested refill is zero and `actuation_allowed` is always false. No actual Ollama model inference has been tested or connected to the dispensing controller. This feature is not a completed course AI closed loop.
