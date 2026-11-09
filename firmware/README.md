# Firmware commissioning checkpoint

These two programs are incomplete and **must not be used to operate a pump**. Pin assignments are proposals for candidate boards, not verified wiring instructions. The gateway keeps pump and emergency-stop pins disabled and never issues a start request; the physical emergency stop must independently remove pump power. Do not connect the TDS or level interface until voltage and pinout are verified.

The node reads DS18B20 and uncalibrated ADC counts. A disconnected temperature sensor is invalid. The level interface remains disabled and reports unknown. Node and gateway exchange 20-byte, versioned UART frames with CRC16, boot session, sequence, ACK and bounded retries. The sender buffers one pending sample, drops it after four transmissions without ACK, then resumes with fresh data. Gateway refuses stale data after five seconds and does not refresh freshness on duplicates. CRC does **not** authenticate a peer; the UART is a trusted internal connection and must not be exposed as an untrusted control interface. There are no pump-control messages. A different boot session is accepted only after the prior session becomes stale; a random session ID is not replay protection.

Provisional UART pins: node TX GPIO25 → gateway RX GPIO1, node RX GPIO26 ← gateway TX GPIO2, with a verified common 3.3 V logic reference. Pin availability, ground/power topology and cable routing must be checked against actual board revisions before wiring. UART avoids the shared-channel constraint between ESP-NOW and gateway Wi-Fi; see the [Espressif FAQ](https://docs.espressif.com/projects/esp-faq/en/latest/esp-faq-en-master.pdf). It is not physically tested.

Gateway loads a versioned, checksum-protected HX711 calibration from NVS. For bench commissioning only, observe an unloaded raw value and a stable raw value with a known mass, then send `CAL <unloaded_raw> <loaded_raw> <known_mass_g>` over the gateway serial console. Verify with independent known masses before relying on it. With a stable empty cup present, `TARE` sets a volatile cup tare; volume uses the approximation 1 g/mL. Removal, instability, recalibration or reboot clears tare. This is preliminary filtering and cup detection with illustrative thresholds, not validated control. NVS corruption fails closed; actual write, interruption and reboot behavior needs hardware testing.

Install PlatformIO Core and run `pio run -d firmware`. The pinned platform and libraries are in `platformio.ini`. The S3 board definition is a candidate for N16R8; verify the received board and flash/PSRAM configuration before flashing.

The portable controller and protocol can be exercised on a host with:

```
g++ -std=c++17 -Ifirmware/include firmware/test/safety_test.cpp -o firmware/test/safety_test.exe
firmware/test/safety_test.exe
```

Repeat for `scale_test.cpp`, `protocol_test.cpp`, and `integration_test.cpp`. The integration test uses the same C++ packet, receiver and safety classes as the firmware; the separate browser simulation has not yet been migrated to this wire protocol.

All limits are illustrative. Cup detection now permits changing weight during the simulated dispensing state, but its filtering, lifecycle and tare handling are not yet validated for actual dispensing. Controller command integration, validated timing/noise limits, driver feedback, brownout and hardware interlocks remain incomplete. No test here demonstrates actual pump shutoff or water safety. See `docs/EXECUTION.md` for the continuation point.

## Experimental gateway publisher

Publisher configuration defaults to disabled in `include/cloud_config.h`. A private, gitignored `include/cloud_config.local.h` may define `KAEW_CLOUD_ENABLED`, `KAEW_WIFI_SSID`, `KAEW_WIFI_PASSWORD`, `KAEW_CLOUD_URL` (the complete `/api/telemetry` URL), `KAEW_CLOUD_TOKEN` and `KAEW_CLOUD_CA` (PEM trust anchor). HTTPS requires a nonempty CA and synchronized clock; no certificate-validation bypass is provided. For an isolated LAN experiment only, `KAEW_ALLOW_DEV_HTTP` can explicitly enable plain HTTP. Never commit credentials or use HTTP on an untrusted network.

The publisher uses separate lower-priority persistence and network tasks. Sixteen NVS slots hold versioned UART frames with checksums and ordering metadata. The gateway emits a UART ACK only after the slot write succeeds; after an HTTP success the slot is removed, so interruption after backend acceptance may lead to an idempotent retry. Corrupt slots fail closed and require investigation. On saturation or NVS failure no ACK is sent; the node has bounded retries and may eventually discard a sample, reported by its counters. Finite storage cannot prevent loss during an unlimited outage. `KAEW_DURABLE_MIN_MS` sets minimum spacing between new writes (default 1000 ms); removals also write flash. This is not an endurance estimate or a guarantee against NVS failure. NVS has wear leveling, but erase wear and unstable power still need evaluation for the exact device and partition: [Espressif NVS](https://docs.espressif.com/projects/esp-idf/en/latest/esp32/api-reference/storage/nvs_flash.html). Actual power-cut recovery, flash wear, HTTPS, Wi-Fi reconnection, certificates, NTP and timing require hardware testing.

## Experimental I²S

`audio_io.h` provides nonblocking candidate INMP441 receive and MAX98357A transmit drivers at 16 kHz; startup is disabled unless `KAEW_AUDIO_ENABLED=1` is compiled. `gateway_cloud_compile` compiles the enabled path. It does not yet capture a complete utterance, detect a wake word, send audio, receive TTS audio, or invoke `readMicrophone`/`play` in the application. GPIO4/5/6 (microphone) and GPIO10/11/12 (amplifier) remain provisional and must be checked against the actual board and breakouts. I²S audio and publisher resource contention require physical measurement.

At 16 kHz, mono 16-bit PCM uses 32,000 bytes/second before protocol overhead; a 15-second recording needs about 480 kB. The N16R8 board profile selects 8 MB octal PSRAM, but available PSRAM, DMA placement, audio channel alignment, clipping and timing cannot be validated until a real board is present. See [Espressif I²S documentation](https://docs.espressif.com/projects/esp-idf/en/v5.2.2/esp32s3/api-reference/peripherals/i2s.html). The VAD threshold in `audio_processing.h` is illustrative, not calibrated for the microphone or noise environment.
