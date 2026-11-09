# Kaew local telemetry checkpoint

This is an early local-development service, **not a production cloud deployment**. It binds only to `127.0.0.1`, stores data in SQLite, serves a basic dashboard and requires separate bearer tokens for device writes and admin reads. It implements one provisioned device (`node-1`), not general device enrollment. The built-in server has no TLS, rate limits, durable gateway queue or production identity management; do not expose it to the Internet or put real credentials into the repository.

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

The simulated gateway adapter saves samples to a bounded SQLite outbox before delivery. After a connection failure, run `python cloud/gateway_push.py --flush` with the device token and endpoint set to retry pending samples; delivery is idempotent, and the outbox is removed only after HTTP 200 or 201. Set `KAEW_OUTBOX_PATH` for its local database. Automatic background retries and the real ESP32 gateway publisher are not implemented. Multi-device provisioning, event history, drinking history, reminders, notifications, TLS and deployment architecture also remain outstanding. Firmware actuation remains disabled.
