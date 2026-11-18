# Gateway standalone Arduino IDE tests

Four single-file sketches for checking gateway wiring one module at a time on the ESP32-S3 N16R8 DevKit. They do not use PlatformIO, Wi-Fi, the cloud, UART to the node, or the pump. Leave GPIO13 unconnected (reserved pump relay).

These are separate from the PlatformIO `mic_test` environment and from `node_selftest` / `gateway_selftest`.

## Arduino IDE settings

Install [Arduino-ESP32 core 3.x](https://docs.espressif.com/projects/arduino-esp32/en/latest/installing.html) (Boards Manager: **esp32** by Espressif, version 3.x). Then, for every sketch:

| Tools menu | Setting |
| --- | --- |
| Board | ESP32S3 Dev Module |
| USB CDC On Boot | Enabled |
| Flash Size | 16MB (128Mb) |
| PSRAM | OPI PSRAM |
| Partition Scheme | 16M Flash (3MB APP/9.9MB FATFS) |
| Port | COM15 (Windows; the Kaew gateway is usually COM15) |
| Serial Monitor | 115200 baud |

## Libraries (Library Manager)

| Sketch | Libraries |
| --- | --- |
| `loadcell_test` | **HX711 Arduino Library** by Bogdan Necula (do not install the similarly named "HX711" by Rob Tillaart) |
| `oled_test` | **U8g2** by olikraus |
| `mic_test` | none (uses bundled `ESP_I2S.h` from Arduino-ESP32 3.x) |
| `speaker_test` | none (uses bundled `ESP_I2S.h` from Arduino-ESP32 3.x) |

## Windows upload (COM15)

1. Open the `.ino` inside its matching folder, for example `firmware/arduino_tests/oled_test/oled_test.ino`.
2. Set the Tools menu as above, port **COM15**.
3. Click Upload. Then open the Serial Monitor at **115200**.

Reports print about every 2–3 seconds.

If you use Arduino CLI from the repository root (same board options):

```bash
arduino-cli compile --fqbn esp32:esp32:esp32s3:CDCOnBoot=cdc,FlashSize=16M,PSRAM=opi,PartitionScheme=app3M_fat9M_16MB firmware/arduino_tests/oled_test
arduino-cli upload -p COM15 --fqbn esp32:esp32:esp32s3:CDCOnBoot=cdc,FlashSize=16M,PSRAM=opi,PartitionScheme=app3M_fat9M_16MB firmware/arduino_tests/oled_test
arduino-cli monitor -p COM15 -c baudrate=115200
```

Replace `oled_test` with `loadcell_test`, `mic_test`, or `speaker_test`.

## What each test does

### loadcell_test — HX711 (SCK GPIO4, DT GPIO5)

Tares on boot, then prints raw, tare, and delta from tare. Press on the load cell; delta should change.

- `PASS` — HX711 is ready and the raw value is changing.
- `WARN` — raw value stuck constant. Press on it; if it never changes, check DT/SCK and the load-cell wires.
- `FAIL` — HX711 never ready. Check DT/SCK swapped, VCC, or GND.

### oled_test — SSD1306/SH1106 (SDA GPIO17, SCL GPIO18, address 0x3C)

Scans I2C, lists found addresses, and draws a test pattern plus a counter. Alternates the **SSD1306** and **SH1106** drivers every few seconds and prints which one is in use. If one image looks shifted or garbled, wait for the other.

- `PASS` — device ACK at 0x3C, pattern is being drawn.
- `WARN` — some other I2C address responded. Check the address or solder jumper.
- `FAIL` — no I2C device. Check VCC 3.3V and GND, then try swapping SDA and SCL.

### mic_test — INMP441 (SD GPIO6, SCK GPIO7, WS GPIO8, L/R to GND)

Uses the Arduino-ESP32 3.x `I2SClass` API. Prints a level every few seconds. Make a sound near the mic to see RMS rise.

- `PASS` — varying samples, with RMS in 24-bit counts.
- `FAIL` — I2S init failed, no samples, all-zero samples, or a constant value. Check SD/SCK/WS, VCC/GND, and tie L/R to GND.

### speaker_test — MAX98357A (DIN GPIO9, BCLK GPIO10, LRC GPIO11)

Plays three short beeps once at boot (150 ms tone, 150 ms gap, moderate volume), then stays silent. This test cannot hear the speaker, so later Serial lines only repeat the boot result.

- `INFO` — 3 beeps played at boot. Listen at startup, not later.
- `FAIL` — I2S init or write failed. Check DIN/BCLK/LRC, VIN (5V or 3.3V), GND, speaker wires, and that the SD (shutdown) pin is not held low.

After debugging, re-flash the normal PlatformIO `gateway` or `gateway_cloud_compile` image for regular operation.
