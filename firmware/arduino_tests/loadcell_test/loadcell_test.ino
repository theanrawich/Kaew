/*
 * Kaew gateway load-cell wiring test (standalone Arduino sketch)
 *
 * Requires Arduino-ESP32 core 3.x (ESP32S3 Dev Module).
 *
 * Arduino IDE board settings:
 *   Tools > Board:            "ESP32S3 Dev Module"
 *   Tools > USB CDC On Boot:  "Enabled"
 *   Tools > Flash Size:       "16MB (128Mb)"
 *   Tools > PSRAM:            "OPI PSRAM"
 *   Tools > Partition Scheme: "16M Flash (3MB APP/9.9MB FATFS)"
 *   Tools > Port:             "COM15"   (Windows; Kaew gateway is usually COM15)
 *   Serial Monitor:           115200 baud
 *
 * Libraries (Sketch > Include Library > Manage Libraries):
 *   - HX711 by Bogdan Necula
 *
 * Wiring (gateway, power off while connecting):
 *   HX711 SCK -> GPIO4
 *   HX711 DT  -> GPIO5
 *   HX711 VCC -> 3.3V or 5V as marked on the module
 *   HX711 GND -> GND
 *
 * Hard rules: do not wire or configure GPIO13 (reserved pump relay).
 * Do not actuate the pump. Do not use GPIO21/47 (node UART).
 *
 * On boot the sketch tares the scale, then every ~2.5 s prints PASS/WARN/FAIL,
 * the raw reading, the tare, and delta from tare. Press on the load cell to
 * see delta change.
 */

#include <HX711.h>

constexpr int HX_DT = 5;
constexpr int HX_SCK = 4;
constexpr uint32_t REPORT_MS = 2500;

HX711 scale;
long tareRaw = 0;
bool tared = false;
long previousRaw = 0;
unsigned identical = 0;

bool tryTare(uint32_t timeoutMs) {
  const uint32_t start = millis();
  while (millis() - start < timeoutMs) {
    if (scale.is_ready()) {
      tareRaw = scale.read_average(8);
      scale.set_offset(tareRaw);
      tared = true;
      Serial.printf("TARE    : INFO  tare raw=%ld (delta is 0 until you press the cell)\n", tareRaw);
      return true;
    }
    delay(10);
  }
  return false;
}

void setup() {
  Serial.begin(115200);
  delay(400);
  scale.begin(HX_DT, HX_SCK);

  Serial.println();
  Serial.println("Kaew GATEWAY load-cell test | Arduino-ESP32 3.x | Serial 115200");
  Serial.println("HX711    | DT GPIO5, SCK GPIO4");
  Serial.println("Press on the load cell after tare to see delta change.");

  if (!tryTare(2000)) {
    Serial.println("HX711   : FAIL  not ready at boot — will keep trying");
    Serial.println("          Hint: check DT/SCK swapped, VCC, GND, and the load-cell wires to the HX711.");
  }
}

void loop() {
  static uint32_t lastReport = 0;
  if (millis() - lastReport < REPORT_MS) {
    delay(10);
    return;
  }
  lastReport = millis();

  if (!scale.is_ready()) {
    identical = 0;
    Serial.println("HX711   : FAIL  HX711 not ready (check DT/SCK swapped, VCC, or GND)");
    return;
  }

  const long raw = scale.read();
  if (!tared) {
    tareRaw = raw;
    scale.set_offset(tareRaw);
    tared = true;
    Serial.printf("TARE    : INFO  tare raw=%ld (first ready sample)\n", tareRaw);
  }

  const long delta = raw - tareRaw;
  const bool hadBaseline = identical != 0;
  identical = hadBaseline && raw == previousRaw ? min(identical + 1u, 3u) : 1u;
  previousRaw = raw;

  if (identical >= 3) {
    Serial.printf(
        "HX711   : WARN  raw=%ld  tare=%ld  delta=%ld  (stuck constant — press on it; "
        "if this never changes, check DT/SCK or load-cell wiring)\n",
        raw, tareRaw, delta);
  } else if (!hadBaseline) {
    Serial.printf("HX711   : INFO  raw=%ld  tare=%ld  delta=%ld\n", raw, tareRaw, delta);
  } else {
    Serial.printf("HX711   : PASS  raw=%ld  tare=%ld  delta=%ld\n", raw, tareRaw, delta);
  }
}
