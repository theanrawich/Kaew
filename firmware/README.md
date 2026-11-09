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

All limits are illustrative. Stable-only cup detection currently fails closed during changing weight and clears tare; it is not yet suitable for actual dispensing. Controller command integration, full cup lifecycle, validated timing/noise limits, driver feedback, brownout and hardware interlocks remain incomplete. No test here demonstrates actual pump shutoff or water safety. See `docs/EXECUTION.md` for the continuation point.
