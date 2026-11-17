# Kaew (แก้ว)

ESP32-S3 smart water dispenser prototype: sensor node → CRC16/ACK UART → gateway → Python cloud API and dashboard. AI provides hydration advice; dispensing remains subject to local safety checks. Physical pump commissioning is disabled by default, and software tests do not establish hardware readiness.

| Path | Purpose |
| --- | --- |
| [firmware/](firmware/README.md) | PlatformIO firmware, protocol, safety and C++ host tests |
| [cloud/](cloud/README.md) | Python API/dashboard, SQLite/Postgres migrations, AI advice, Groq STT and voice tools |
| [simulation/](simulation/index.html) | JavaScript simulation, browser viewer and protocol tests; also used by `cloud/simulate.mjs` |
| [scripts/](scripts/) | Host test runner and measurement capture/analysis tools |
| [docs/](docs/) | Wiring, hardware procedures, contracts and historical validation records |
| [render.yaml](render.yaml) | Render service configuration; hosted storage uses Supabase Postgres |

## Cloud quick start

Use Python 3.11+ from the repository root. Local SQLite needs no third-party packages. In Bash, enter two distinct private tokens:

```bash
read -rsp 'Device token: ' KAEW_DEVICE_TOKEN; echo
read -rsp 'Admin token: ' KAEW_ADMIN_TOKEN; echo
export KAEW_DEVICE_TOKEN KAEW_ADMIN_TOKEN
python3 cloud/server.py
```

Leave `DATABASE_URL` unset for SQLite. Open <http://127.0.0.1:8080/> and enter the admin token. The server reads process environment; it does not load `.env` automatically. See [environment examples](cloud/.env.example) and [cloud setup](cloud/README.md) for Postgres, Render, reminders and Groq STT and the WAV voice CLI. SQLite migrations run automatically; Postgres migrations must be applied explicitly before startup.

## Firmware

Install PlatformIO Core (CI uses 6.2.0), then:

```bash
pio run -d firmware                     # sensor_node and gateway
pio run -d firmware -e mic_test          # standalone microphone/STT test
```

Additional CI environments are `gateway_cloud_compile`, `sensor_node_trace`, `gateway_trace` and `gateway_ai_compile`. See [build/flash instructions](firmware/README.md#build-and-flash), [pin map](docs/wiring.md) and [refill safety contract](docs/GATEWAY_REFILL_CONTRACT.md) before using hardware. Private gateway settings belong in the ignored `firmware/include/cloud_config.local.h`, using the [example](firmware/include/cloud_config.local.h.example). Never commit this header, `.env`, tokens or Wi-Fi credentials.

## Tests and simulator

Python 3.11+, Node.js 20+ and g++ are required. These match [CI](.github/workflows/firmware.yml):

```bash
python3 -m unittest discover -s cloud -p 'test_*.py' -v
npm test --prefix simulation
python3 scripts/run_host_tests.py
python3 -m unittest discover -s scripts -p 'test_*.py' -v
pio run -d firmware -e sensor_node -e gateway -e mic_test -e gateway_cloud_compile -e sensor_node_trace -e gateway_trace -e gateway_ai_compile
```

Postgres integration tests skip unless `KAEW_TEST_POSTGRES_URL` selects a disposable loopback database; see [Postgres verification](cloud/README.md#local-postgres-verification-and-implementation). JavaScript tests need no dependency installation. For the browser viewer, run `npm ci --prefix simulation`, serve the repository with `python3 -m http.server 8000`, and open <http://localhost:8000/simulation/>.

For hardware work, start with the [checkpoint procedure](docs/CHECKPOINT_CRITICAL_PATH.md), [measurement plan](docs/PERFORMANCE_TEST_PLAN.md) and [gateway AI loop](docs/M4_GATEWAY_AI_LOOP.md). Codex contributors should read [AGENTS.md](AGENTS.md).
