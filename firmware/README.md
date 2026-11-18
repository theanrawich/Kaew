# Firmware commissioning checkpoint

The opt-in [M4 AI recommendation path](../docs/design/m4-gateway-ai-loop.md) adds `AI_REFILL`: one local confirmation, one authenticated read-only device request to `/api/advice`, and validation through the existing SafetyController. `gateway_ai_compile` builds this path with pump commissioning still disabled. The AI refill path uses the device token. The new path is covered by deterministic fake-hardware/HTTP-to-C++ tests; physical operation remains blocked pending commissioning.

These programs are **not commissioned for physical pump operation**. Pin assignments are proposals for candidate boards, not verified wiring instructions. Gateway local refill integration now calls the shared SafetyController through a bounded validator, exercised with a fake actuator in host tests. GPIO, local manual refill and locally confirmed AI refill remain disabled by default; raw remote AI requests are always rejected. The physical emergency stop must independently remove pump power. Do not connect the TDS or level interface until voltage and pinout are verified. See [Arm's implementation report](../docs/design/m4-gateway-ai-loop.md), [command contract](../docs/design/gateway-refill-contract.md) and [executed validation](../docs/testing/validation/software-2026-11-17.md).

The node reads DS18B20. TDS input is disabled and reports the unknown sentinel 65535; a disconnected temperature sensor is invalid. The level interface remains disabled and reports unknown. Node and gateway exchange 20-byte, versioned UART frames with CRC16, boot session, sequence, ACK and bounded retries. The sender buffers one pending sample, drops it after four transmissions without ACK, then resumes with fresh data. Gateway refuses stale data after five seconds and does not refresh freshness on duplicates. CRC does **not** authenticate a peer; the UART is a trusted internal connection and must not be exposed as an untrusted control interface. There are no pump-control messages. A different boot session is accepted only after the prior session becomes stale; a random session ID is not replay protection.

Provisional UART pins: node (ESP32-S3) TX GPIO17 → gateway RX GPIO1, node RX GPIO18 ← gateway TX GPIO2, with a verified common GND reference. Power both boards off before wiring; check the power topology and ground voltage difference with a meter before joining GND. Use 3.3 V UART logic only (GPIO is not 5 V tolerant); do not join the boards’ power rails. Pin availability, ground/power topology and cable routing must be checked against actual board revisions before wiring. UART avoids the shared-channel constraint between ESP-NOW and gateway Wi-Fi; see the [Espressif FAQ](https://docs.espressif.com/projects/esp-faq/en/latest/esp-faq-en-master.pdf). It is not physically tested.

Gateway loads a versioned, checksum-protected HX711 calibration from NVS. For bench commissioning only, observe an unloaded raw value and a stable raw value with a known mass, then send `CAL <unloaded_raw> <loaded_raw> <known_mass_g>` over the gateway serial console. Verify with independent known masses before relying on it. With a stable empty cup present, `TARE` sets a volatile cup tare; volume uses the approximation 1 g/mL. Removal, instability, recalibration or reboot clears tare. This is preliminary filtering and cup detection with illustrative thresholds, not validated control. NVS corruption fails closed; actual write, interruption and reboot behavior needs hardware testing.

Install PlatformIO Core (`python3 -m pip install platformio==6.2.0` in a virtual environment if required) and run `pio run -d firmware`. The pinned platform and libraries are in `platformio.ini`. The S3 board definition is a candidate for N16R8; verify the received board and flash/PSRAM configuration before flashing.

The portable controller and protocol can be exercised on a host with:

```
g++ -std=c++17 -Ifirmware/include firmware/test/safety_test.cpp -o firmware/test/safety_test.exe
firmware/test/safety_test.exe
```

Use `python scripts/run_host_tests.py` from repository root to run all ten host programs, including `gateway_dispensing_test.cpp` (25 scenarios) and `ai_refill_test.cpp` (12 scenarios), plus the six-case configuration matrix and six GPIO compile checks. Four forbidden GPIO43/44 pump/stop assignments must fail with the reserved-pin assertion; two positive controls must compile. The GPIO fixtures use inert host stubs, not actual commissioning. GPIO43/44 stay reserved for the UART0 console even if a future build switches to USB CDC. The original `bash firmware/test/cloud_config_test.sh` also remains available. Protocol tests check corrupt-frame recovery and clock wraparound; integration covers missing, unknown, dry, malformed and stale tank data. The new suite combines the same scale/command/safety modules used by the gateway with fake hardware. The separate browser plant remains a distinct controller model, with a shared wire codec adapter but no formal equivalence claim.

All limits remain illustrative. Idle uses a five-sample median and stable-cup gate; dispensing/settling checks each calibrated sample directly so median delay cannot hide removal/target crossing. HX711 reading runs in a separate acquisition task because the installed library can block after a disconnect race; the main loop uses an eight-sample queue, checks freshness and faults on overflow (reboot/investigation required). Gateway development defaults are 500 ms scale stale, 5 s no progress, 30 s total and 1 s settling; the standalone SafetyController retains its older defaults for existing callers. Validated timing/noise limits, driver feedback, brownout and independent hardware interlocks remain pending. No test here demonstrates actual pump shutoff or water safety. See [physical measurement plan](../docs/testing/performance-test-plan.md).

Console `REFILL <boot> <id> <issued_gateway_ms> <total_water_ml>`, `STOP` and `RESET` now have explicit semantics in the [contract](../docs/design/gateway-refill-contract.md). A successful reset never starts the pump and the application requires a new empty-cup tare/request. Pump/stop pin defaults are still -1 in `pump_gpio.h`, with unspecified polarity and commissioning/local-enable flags both 0. Do not set them from provisional wiring numbers. Local console parsing is bounded and nonblocking; diagnostics can still affect scheduling and must be included in physical latency measurements.

For optional PDR measurements only, build `sensor_node_trace` and `gateway_trace`; trace is off in normal builds and forbidden with pump commissioning. Keep pump power disconnected. The [capture tool and procedure](../docs/testing/performance-test-plan.md#b--packet-delivery-rate) save actual key-level logs and distinguish unique frames, retries, duplicates, recovery and trace loss. No real trace was captured during software validation.

## Build and flash

The cloud is live at <https://kaew-cloud.onrender.com>; the physical node → UART → gateway → HTTPS path is still unproven. Keep the pump disconnected throughout this temperature-only checkpoint.

1. Verify board revisions, exposed UART pins, supply/ground topology and serial ports. Wire TX/RX/GND as above with both boards powered off. Verify the DS18B20 pinout and its 4.7 kΩ DQ pull-up to 3V3; do not infer probe wire colors.
2. In the gitignored `firmware/include/cloud_config.local.h`, fill **only your local Wi-Fi SSID/password placeholders** before building. The checkpoint setup supplies the full live telemetry URL, device token and ISRG Root X1 PEM. Keep credentials private; never paste tokens into chat. URL + token auto-enable the publisher without a forced enable flag. The gateway needs Wi-Fi internet access and NTP time synchronization for validated HTTPS.
3. From the repository root, build, then flash **gateway first, node second** (replace each port placeholder):

```bash
pio run -d firmware -e sensor_node
pio run -d firmware -e gateway
pio run -d firmware -e gateway_cloud_compile
pio run -d firmware -e gateway -t upload --upload-port <GATEWAY_PORT>
pio run -d firmware -e sensor_node -t upload --upload-port <NODE_PORT>
```

`gateway_cloud_compile` verifies enabled publisher/audio compilation; flash the normal `gateway` environment for this checkpoint. Host tests do not replace the PlatformIO builds or physical commissioning.

4. Open separate serial terminals at 115200 (exit a monitor with Ctrl-C before uploading to the same port):

```bash
pio device monitor -d firmware -e gateway --port <GATEWAY_PORT> --baud 115200
pio device monitor -d firmware -e sensor_node --port <NODE_PORT> --baud 115200
```

Node `tx` and `ack` should advance without sustained `dropped` growth. Gateway prints every second even without HX711: expect `hx711_ready=0`, increasing `rx`, `link_fresh=1`, `level=0`, and `pump=off`. `hx711_raw` is meaningful only when `hx711_ready=1`; scale fields are not validated measurements when the scale is missing. `dup` may rise on retries; `rejected`, `cloud_reject` and `cloud_error` expose receiver, enqueue/storage failures, but are **not HTTP-success counters**. UART ACK confirms durable local storage, not cloud delivery. With empty Wi-Fi placeholders ACKs can initially advance until the finite outbox fills; this does not prove HTTPS works.

5. Open <https://kaew-cloud.onrender.com/> and authenticate privately using the existing admin dashboard credential (never put that credential in firmware). Confirm new rows show `source=device`, advancing sequence, plausible temperature responding to gentle probe warming, level `unknown`, and TDS `—` (API `65535`). Dashboard refresh is every 5 s; the protected `/api/telemetry` response also contains session IDs if needed. A disconnected temperature probe should yield `—` (API `null`). Queued arrival time does not prove a current measurement.
6. Disconnect UART: gateway `link_fresh` must become 0 after 5 s and level display remain unknown. Reconnect and confirm new sequence values and dashboard rows. After a node reboot, allow the prior session’s 5 s freshness window to expire. Briefly interrupt Wi-Fi and confirm replay after reconnection; record duration/loss. The 16-slot queue and bounded node retries cannot cover unlimited outages. Power-cut recovery and actual TLS/NTP/Wi-Fi behavior still require board testing. No step authorizes pump operation.

## Experimental gateway publisher

Publisher configuration in `include/cloud_config.h` auto-enables when URL and token are both nonempty. Empty defaults keep it off. Copy `include/cloud_config.local.h.example` to ignored `include/cloud_config.local.h`; explicitly defining `KAEW_CLOUD_ENABLED=0` forces it off even with credentials. A build override of 1 (CI `gateway_cloud_compile`) still compiles without any local header. A private, gitignored `include/cloud_config.local.h` may define `KAEW_CLOUD_ENABLED`, `KAEW_WIFI_SSID`, `KAEW_WIFI_PASSWORD`, `KAEW_CLOUD_URL` (the complete `/api/telemetry` URL), `KAEW_CLOUD_TOKEN` and `KAEW_CLOUD_CA` (PEM trust anchor). HTTPS requires a nonempty CA and synchronized clock; no certificate-validation bypass is provided. For an isolated LAN experiment only, `KAEW_ALLOW_DEV_HTTP` can explicitly enable plain HTTP. Never commit credentials or use HTTP on an untrusted network.

The existing live endpoint is `https://kaew-cloud.onrender.com/api/telemetry`; no redeployment is needed for this checkpoint. For local/server environment setup see [cloud setup](../cloud/README.md). Put the device token (never the admin token) in the local header and use the full hosted `/api/telemetry` URL. Obtain the public CA from the current certificate chain (for ISRG Root X1, the example links the official PEM); it is not a private key. Never commit the populated header.

The publisher uses separate lower-priority persistence and network tasks. Sixteen NVS slots hold versioned UART frames and measured drink events with checksums and ordering metadata. The gateway emits a UART ACK only after the slot write succeeds; after an HTTP success the slot is removed, so interruption after backend acceptance may lead to an idempotent retry. Corrupt slots fail closed and require investigation. On saturation or NVS failure no ACK is sent; the node has bounded retries and may eventually discard a sample, reported by its counters. Finite storage cannot prevent loss during an unlimited outage. `KAEW_DURABLE_MIN_MS` sets minimum spacing between new writes (default 1000 ms); removals also write flash. This is not an endurance estimate or a guarantee against NVS failure. NVS has wear leveling, but erase wear and unstable power still need evaluation for the exact device and partition: [Espressif NVS](https://docs.espressif.com/projects/esp-idf/en/latest/esp32/api-reference/storage/nvs_flash.html). Actual power-cut recovery, flash wear, HTTPS, Wi-Fi reconnection, certificates, NTP and timing require hardware testing.

### Measured drinks

The gateway watches calibrated gross weight for a cup lift. It requires at least 200 ms at or below 15 g, then at least 600 ms of stable weight after the cup returns (at most 5 g spread). A 10–1000 g decrease is recorded at 1 g/mL; a weight increase establishes a new baseline. Detection uses HX711 calibration and works without cup tare. Recalibration, stale or invalid readings, and dispensing activity reset the detection cycle.

The publisher sends measured drinks to `/api/events` on the same host with the device token. It retries persisted drinks with the same event ID. The queue is shared with telemetry and can drop new readings when full. The thresholds still need physical validation. The detector has no pump output.

## Experimental I²S

`KAEW_AUDIO_ENABLED=1` enables 16 kHz mono speech capture using the same
INMP441 filtering and utterance detection as `mic_test`. INMP441 microphone
SD=GPIO6, SCK=GPIO7, WS=GPIO8. MAX98357A speaker DIN=GPIO9, BCLK=GPIO10,
LRC=GPIO11. Verify these provisional pins against the actual hardware.

Capture runs in its own FreeRTOS task with PSRAM clip storage. When
`KAEW_CLOUD_ENABLED` is also enabled, a separate task normalizes queued clips and
posts WAV to `/api/stt?command=1` via the publisher's Wi-Fi connection. A full
queue drops the newest clip. Set `KAEW_ADMIN_TOKEN` privately for this optional
STT path. It requires HTTPS, a verified CA, and synchronized time. The gateway
logs the transcript and command result. Voice has no access to gateway pump
controls. `gateway_cloud_compile` builds both paths. I²S timing and resource
contention with telemetry still require board testing.

## Mic + STT test

Standalone INMP441 test for the ESP32-S3 N16R8: VDD → 3V3, GND → GND,
SD → GPIO6, SCK/BCLK → GPIO7, WS → GPIO8, L/R → GND (left channel).
No amplifier is needed. Configure `KAEW_WIFI_SSID`, `KAEW_WIFI_PASSWORD`,
`KAEW_CLOUD_URL` and `KAEW_CLOUD_CA` in the ignored `include/cloud_config.local.h`.
Add optional `KAEW_ADMIN_TOKEN` with the STT admin credential;
empty or missing skips sending. Keep this header private. The test strips the
cloud URL path and posts to `/api/stt` with verified TLS (WiFi and NTP required).

```bash
pio run -d firmware -e mic_test -t upload && pio device monitor -d firmware -b 115200
```

After reset, wait for `Listening.` before speaking. The firmware discards the
first 500 ms of samples and measures ambient noise for another 500 ms. Keep the
usual background noise present during this measurement.

The detector compares 20 ms PCM frame energy against the background level.
Three consecutive loud frames start a clip, including up to 300 ms of recent
audio. A 700 ms pause or the 8 s maximum ends the clip. Speech-like background
noise can trigger this energy detector, so tune it with recordings and the
actual enclosure and listening distance.
At the length limit, varying speech can continue in the next clip without a
fresh onset. A steady level held to the limit is used as an updated noise floor.

The upload task normalizes selected clips with a 7× gain ceiling and sends them
while recording continues. Serial output pairs duration, pre-gain RMS, peak,
clipped sample count and the transcript by clip ID. If the queue fills, the
firmware logs and drops the newly completed clip. Network operations use 20 s
timeouts. This build does not initialize gateway controls.
