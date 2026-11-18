/*
 * Kaew gateway INMP441 microphone wiring test (standalone Arduino sketch)
 *
 * Requires Arduino-ESP32 core 3.x (ESP32S3 Dev Module).
 * I2S uses the core 3.x ESP_I2S.h I2SClass API (not the older driver/i2s.h).
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
 * Libraries: none beyond Arduino-ESP32 core 3.x (ESP_I2S.h is bundled).
 *
 * Wiring (gateway, power off while connecting):
 *   INMP441 SD  -> GPIO6
 *   INMP441 SCK -> GPIO7
 *   INMP441 WS  -> GPIO8
 *   INMP441 L/R -> GND  (left channel)
 *   INMP441 VCC -> 3.3V
 *   INMP441 GND -> GND
 *
 * Hard rules: do not wire or configure GPIO13 (reserved pump relay).
 * Do not actuate the pump. Do not use GPIO21/47 (node UART).
 *
 * Every ~2.5 s prints a level and PASS/FAIL. All-zero or constant samples
 * are FAIL. Make a sound near the mic to see RMS rise.
 */

#include <ESP_I2S.h>
#include <math.h>

constexpr int MIC_SD = 6;
constexpr int MIC_SCK = 7;
constexpr int MIC_WS = 8;
constexpr int SAMPLE_RATE = 16000;
constexpr uint32_t REPORT_MS = 2500;
constexpr uint32_t CAPTURE_MS = 400;

I2SClass i2s;
bool micReady = false;

void setup() {
  Serial.begin(115200);
  delay(400);

  Serial.println();
  Serial.println("Kaew GATEWAY mic test | Arduino-ESP32 3.x (ESP_I2S.h I2SClass) | Serial 115200");
  Serial.println("INMP441  | SD GPIO6, SCK GPIO7, WS GPIO8, L/R to GND");

  // setPins(bclk, ws, dout, din). dout unused for a microphone-only test.
  i2s.setPins(MIC_SCK, MIC_WS, -1, MIC_SD);
  // INMP441: 24-bit data left-justified in a 32-bit slot, left channel (L/R to GND).
  micReady = i2s.begin(I2S_MODE_STD, SAMPLE_RATE, I2S_DATA_BIT_WIDTH_32BIT, I2S_SLOT_MODE_MONO);
  if (!micReady) {
    Serial.println("MIC     : FAIL  I2S init failed (check SD=GPIO6, SCK=GPIO7, WS=GPIO8, and tie L/R to GND)");
  }
}

void loop() {
  static uint32_t lastReport = 0;
  if (millis() - lastReport < REPORT_MS) {
    delay(10);
    return;
  }
  lastReport = millis();

  if (!micReady) {
    Serial.println("MIC     : FAIL  I2S init failed (check SD=GPIO6, SCK=GPIO7, WS=GPIO8, and tie L/R to GND)");
    return;
  }

  int32_t samples[256];
  double squares = 0;
  size_t count = 0;
  int32_t first = 0;
  bool varies = false;

  const uint32_t started = millis();
  while (millis() - started < CAPTURE_MS) {
    const size_t bytes = i2s.readBytes(reinterpret_cast<char *>(samples), sizeof(samples));
    if (bytes < sizeof(int32_t)) continue;
    const size_t n = bytes / sizeof(int32_t);
    for (size_t i = 0; i < n; ++i) {
      const int32_t value = samples[i] >> 8;  // 24-bit sample in a 32-bit slot
      if (count == 0) first = value;
      varies |= value != first;
      squares += static_cast<double>(value) * static_cast<double>(value);
      ++count;
    }
  }

  if (count == 0) {
    Serial.println("MIC     : FAIL  no samples (check SD/SCK/WS, VCC/GND, and tie L/R to GND)");
  } else if (!varies && first == 0) {
    Serial.println("MIC     : FAIL  all-zero samples (check SD/SCK/WS, VCC/GND, and tie L/R to GND)");
  } else if (!varies) {
    Serial.printf("MIC     : FAIL  constant samples=%ld (check SD/SCK/WS or tie L/R to GND)\n",
                  static_cast<long>(first));
  } else {
    Serial.printf("MIC     : PASS  RMS=%.1f (24-bit counts, n=%u) — make a sound to see it rise\n",
                  sqrt(squares / static_cast<double>(count)), static_cast<unsigned>(count));
  }
}
