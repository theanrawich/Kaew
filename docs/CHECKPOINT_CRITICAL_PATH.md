# Checkpoint critical path — 20 November 2026

Status 10 November: **not physically demonstrated and no cloud service deployed**. The smallest checkpoint demonstration is a genuine DS18B20 temperature measurement on the sensor node, sent over UART to the gateway and published to a separately hosted HTTPS backend and dashboard. It is only a checkpoint subset, not evidence that M1's five sensors or the final dispenser are complete. Never present simulated samples as device readings.

## Procurement and readiness

Budget cap is 4,500 THB including structure, shipping and contingency. Previous 4,153 THB total is an estimate, not a current quote. Do not order on these historical prices.

| Priority and item | Decision | Confirmed reference / outstanding checks |
| --- | --- | --- |
| P0 ESP32 DevKit node, selected 30-pin USB-C | Borrow an identified board or purchase after matching pinout | Firmware targets `esp32dev`. ESP32 has GPIO4, GPIO25 and GPIO26; verify actual module, header and USB power input before use. |
| P0 ESP32-S3 N16R8 gateway | Borrow exact board or purchase after confirming variant | Current firmware assumes 16 MB QIO flash and 8 MB OPI PSRAM. Confirm seller's board schematic, memory, USB port, GPIO1/2 access and boot behavior; module family alone does not establish the breakout pinout. |
| P0 DS18B20, 4.7 kΩ resistor, breadboard/jumpers, two suitable USB data cables and regulated USB supplies | Borrow or buy after identifying pinout | Genuine DS18B20 supports 3.0–5.5 V; a 4.7 kΩ DQ pull-up is required. Probe wire colors and authenticity are not established. Use a dry bench test, not drinking water. |
| P0 meter and independent reference thermometer | Borrow | Check continuity, supply/logic voltage and temperature response. Ratings and calibration of the particular instruments remain to be checked. |
| P0 hosted backend and TLS domain | Prepare provisioning; deployment requires explicit user authorization | The existing Python HTTP server is a local development server, not a production-ready public service. HTTPS reverse proxy, persistent SQLite storage, backups, access controls, single process and device CA/time validation require an actual deployment and verification. No provider or service is assumed provisioned. |
| P1 TDS board/probe, level sensor, HX711/load cell, microphone | Supplier and electrical confirmation before connecting | Actual TDS output voltage, level output topology/polarity, breakout pinout and probe materials remain unknown. They are not needed for this checkpoint but are needed for the wider M1 design. |
| Hold: selected pump, power adapter, driver, fluid path and food-contact components | Do not order yet | Variant, adapter, control behavior, independent power interruption, materials, tubing compatibility and total cost remain unconfirmed. Do not substitute a different pump without user decision. |

Primary component references: [ESP32 datasheet](https://documentation.espressif.com/esp32_datasheet_en.html), [DS18B20 datasheet](https://www.analog.com/media/en/technical-documentation/data-sheets/ds18b20.pdf), [Analog Devices pull-up guidance](https://support.analog.com/en-US/knowledgebase/article/000094969), and [ESP32-S3 datasheet](https://www.espressif.com/sites/default/files/documentation/esp32-s3_datasheet_en.pdf). These establish chip-level facts, not the seller's exact board or probe.

## Bench wiring and power — conditional on identifying the actual boards

Turn both boards off before wiring. Power each from its own suitable regulated 5 V USB supply through its designated USB input; do not join their 5 V or 3.3 V rails. Check each board's regulator and supply rating against the actual schematic. Join grounds only after checking common reference and no voltage difference with a meter. Do not connect mains wiring. All GPIO signals below are 3.3 V logic, not 5 V tolerant. Cable lengths and signal integrity are untested.

| From | To | Notes |
| --- | --- | --- |
| Node 3V3 | DS18B20 VDD and one end of 4.7 kΩ | Externally powered three-wire mode; confirm actual probe wires, do not infer colors. |
| Node GND | DS18B20 GND and gateway GND | Verify board pins and common ground. |
| Node GPIO4 | DS18B20 DQ and other end of 4.7 kΩ | GPIO4 on classic ESP32; verify breakout exposes it. |
| Node GPIO25 TX | S3 GPIO1 RX | 115200 8N1, cross connection. |
| Node GPIO26 RX | S3 GPIO2 TX | 115200 8N1, cross connection. |

Before connecting each signal, measure supply and idle signal against its local ground; verify within the receiving board's recommended operating limits and check for shorts. GPIO mapping is confirmed against firmware and chip documentation, **not** the physical boards. GPIO34 ADC is disabled; level remains unknown. HX711, audio, TDS, level, motor and stop wiring are unnecessary for this subset. The gateway still initializes its HX711 input; no sensor is required to publish temperature, but serial diagnostics currently depend on HX711 readiness. No pump or driver power may be connected.

## Provision, flash and verify

1. Confirm the exact board identities and pin mappings above; check continuity with power off. Identify each serial port. With only USB power, measure 3V3 and UART idle voltages before adding signal wires. Never assume a waterproof probe is food-contact safe.
2. Set up a user-authorized HTTPS service for `cloud/server.py` only after addressing its deployment limitations in `cloud/README.md`. Preserve SQLite on persistent storage and run exactly one instance. Use two distinct long random device/admin tokens. Record the DNS name, certificate chain/CA and backup plan privately. No cloud deployment has been performed here.
3. Configure ignored `firmware/include/cloud_config.local.h` with `KAEW_CLOUD_ENABLED=1`, Wi-Fi credentials, HTTPS `KAEW_CLOUD_URL` ending in `/api/telemetry`, the device token and verified PEM CA. Synchronize time for TLS. Never share the file, serial output containing secrets, or the admin token. Compile and flash the gateway first, then node: `pio run -d firmware -e gateway -t upload --upload-port <GATEWAY_PORT>` and `pio run -d firmware -e sensor_node -t upload --upload-port <NODE_PORT>`. Verify exact board and port before each upload. The compile-only audio environment is not a deployment configuration.
4. Connect the powered-off UART wiring, power on, and inspect node serial at 115200 for increasing TX and ACK, and no sustained dropped count. A gateway without HX711 does not currently print its periodic UART diagnostics. Use dashboard/API to verify received `source=device`, matching changing session/sequence, plausible temperature, level unknown, and TDS unknown. Compare against a reference thermometer; warm the probe by hand and observe a corresponding trend. A recently received queued sample is not proof of fresh measurement.
5. Disconnect node-to-gateway UART and show dashboard data ceases advancing. Reconnect, allow for session freshness, and show new sequence values. Disconnect Wi-Fi briefly, reconnect and verify bounded queue replay and deduplication. Record outage length and any loss. The 16-slot queue and node retries are finite; test power-loss recovery separately, not by assumption. For cloud proof show the service host/domain and HTTPS, dashboard and physical boards in the same continuous recording.

## Acceptance record and calibration

Record operator, date, firmware commit, board markings, supply and logic voltages, thermometer ID, network, endpoint (no secrets), session and sequences, expected and observed result. DS18B20: compare stable readings at room temperature and a second safe dry/externally contained temperature against reference; record differences and uncertainty rather than inventing a pass threshold. Unplug DQ: require invalid temperature rather than a plausible value; restore and verify recovery. UART: record ACK/drop counters; disconnect and reconnect. Cloud: verify device-source rows, persistence across service restart, duplicate behavior, outage and queue recovery. Measure timings and test after actual power cycling. Each check is **pending physical hardware**. Full-project HX711 calibration and pump cutoff tests remain separate and are not prerequisites for this temperature-only video.

## ≤2 minute checkpoint video and evidence checklist

* 0–15 s: introduce Kaew and label physical node, gateway, temperature probe, and pump disconnected.
* 15–35 s: show powered wiring and node UART TX/ACK counters; demonstrate probe warming and reference thermometer.
* 35–65 s: show hosted HTTPS address and dashboard, `source=device`, session/sequence and changing temperature. Avoid displaying tokens or Wi-Fi credentials.
* 65–95 s: disconnect UART, observe no new samples, reconnect and observe new samples. Explain level and TDS are unknown and there is no physical pump actuation.
* 95–115 s: summarize real measurement, gateway forwarding, persisted cloud record and dashboard. Clearly label remaining sensors, calibration and safety commissioning as future work.

Save the unedited take, a screenshot of dashboard rows, sanitized wiring photographs, commit/build output, serial counters, calibration record and an operator sign-off. Confirm course upload and actual submission status separately.

## Course evidence matrix, refreshed 10 November

| Requirement | Evidence in this checkout | Still required |
| --- | --- | --- |
| M1 | Proposed five sensor types; temperature firmware compiles when verified in build | Five real types, at least two on each board, working and recorded. One-sensor checkpoint is insufficient. |
| M2 | Simulation only; physical output disabled | Commission driver, independent cutoff and real actuator under supervision. |
| M3 | UART codec, ACK/retry and host tests | Demonstrate real node-to-gateway link and data. |
| M4 | Model inference experiments and separate simulation adapter | Connect backend to adapter, persist decisions/events, show valid genuine inference alters simulated control, prove interlocks override it and evaluate output; current models have not passed. |
| M5 | Local persistent API/dashboard and firmware HTTPS publisher code | Authorized hosted service and actual sensor-to-cloud-to-dashboard test. |
| M6 | Notification job implementation with mocked tests | Configure and demonstrate a real recipient and delivery. |
| M7 | Software safety tests and draft wiring | Verify independent electrical cutoff, power recovery and physical installation. |
| M8 | Local Git history | Verify remote access and contributions by every member; no push authorized in this task. |
