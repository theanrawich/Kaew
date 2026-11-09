# Kaew local telemetry checkpoint

This is an early local-development service, **not a production cloud deployment**. It binds to `127.0.0.1` by default, stores data in SQLite, serves a basic dashboard and requires separate bearer tokens for device writes and admin reads. It implements one provisioned device (`node-1`), not general device enrollment. The built-in server has no TLS, rate limits or production identity management; do not expose it to the Internet or put real credentials into the repository. Optional LAN HTTP requires explicit `KAEW_HOST` and `KAEW_DEV_ALLOW_INSECURE_LAN=1` and transmits bearer tokens without encryption; use only an isolated development network.

Requires Python 3.11+ and Node.js 20+. In PowerShell terminal 1, generate two different long random tokens and keep them private:

```powershell
$env:KAEW_DEVICE_TOKEN = 'replace-with-a-long-random-device-token'
$env:KAEW_ADMIN_TOKEN = 'replace-with-a-different-long-random-admin-token'
python cloud/server.py
```

In terminal 2 use the same device token and run the simulated node → UART codec → gateway adapter → HTTP ingestion path:

```powershell
$env:KAEW_DEVICE_TOKEN = 'the-same-device-token'
node cloud/simulate.mjs
```

Open `http://127.0.0.1:8080/` and enter the admin token to see the last 100 persisted samples and online/offline status. The token remains in page memory until reload. The default database is `cloud/kaew.sqlite3` (gitignored); `KAEW_DB_PATH`, `KAEW_PORT`, and `KAEW_CLOUD_URL` can override local defaults. Raw ADC is not a TDS measurement, and a single level switch does not measure volume.

Run the reproducible API, SQLite restart and simulated-pipeline smoke tests:

```powershell
python -m unittest discover -s cloud -p 'test_*.py' -v
```

The simulated gateway adapter saves samples to a bounded SQLite outbox before delivery. Run `python cloud/gateway_push.py --worker` in a separate terminal with the device token and endpoint set for automatic retries with backoff and jitter. Use one worker per outbox. `--flush` performs one manual pass. Delivery is idempotent, and the outbox is removed only after HTTP 200 or 201. Set `KAEW_OUTBOX_PATH` for its local database. HTTP failures remain queued, including permanent failures; dead-letter handling and multi-process leasing are not implemented.

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

`POST /api/advice` with admin authentication and `{"include_simulated":false}` obtains an advisory from an optional loopback Ollama model selected with `KAEW_OLLAMA_MODEL`, using persisted intake and goal data. Without a running model or with invalid/low-confidence output it falls back to zero refill and a 60-minute reminder. It records the request and response. Model-reported confidence is not a calibrated probability; recommendations are not medical advice. Cup data is currently unknown to this endpoint, so suggested refill is zero and `actuation_allowed` is always false. No actual Ollama model inference has been tested or connected to the dispensing controller. This feature is not a completed course AI closed loop.
