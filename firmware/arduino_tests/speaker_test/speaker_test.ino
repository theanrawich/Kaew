/*
 * Kaew gateway MAX98357A speaker wiring test (standalone Arduino sketch)
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
 *   MAX98357A DIN  -> GPIO9
 *   MAX98357A BCLK -> GPIO10
 *   MAX98357A LRC  -> GPIO11
 *   MAX98357A VIN  -> 5V or 3.3V (as marked on the module)
 *   MAX98357A GND  -> GND
 *   Speaker        -> SPK+ / SPK-
 *   SD (shutdown)  -> do not hold low; leave per the module docs or pull high to enable
 *
 * Hard rules: do not wire or configure GPIO13 (reserved pump relay).
 * Do not actuate the pump. Do not use GPIO21/47 (node UART).
 *
 * Every ~3 s plays a short 400-2400 Hz tone sweep at moderate volume and
 * prints what it is doing. This test cannot hear the speaker itself.
 */

#include <ESP_I2S.h>
#include <math.h>
#include <string.h>

constexpr int SPK_DIN = 9;
constexpr int SPK_BCLK = 10;
constexpr int SPK_LRC = 11;
constexpr int SAMPLE_RATE = 16000;
constexpr int AMPLITUDE = 5000;  // ~15% of full scale, moderate volume
constexpr int SWEEP_MS = 500;
constexpr uint32_t PERIOD_MS = 3000;

I2SClass i2s;
bool speakerReady = false;

bool playSweep() {
  constexpr int frames = SAMPLE_RATE * SWEEP_MS / 1000;
  constexpr float f0 = 400.0f;
  constexpr float f1 = 2400.0f;
  int16_t stereo[128 * 2];
  float phase = 0.0f;

  for (int offset = 0; offset < frames; offset += 128) {
    const int n = min(128, frames - offset);
    for (int i = 0; i < n; ++i) {
      const float freq = f0 + (f1 - f0) * static_cast<float>(offset + i) / static_cast<float>(frames);
      phase += 2.0f * PI * freq / static_cast<float>(SAMPLE_RATE);
      if (phase > 2.0f * PI) phase -= 2.0f * PI;
      const int16_t sample = static_cast<int16_t>(AMPLITUDE * sinf(phase));
      stereo[2 * i] = stereo[2 * i + 1] = sample;
    }
    const size_t bytes = static_cast<size_t>(n) * 2 * sizeof(int16_t);
    if (i2s.write(reinterpret_cast<const uint8_t *>(stereo), bytes) != bytes) {
      Serial.println("SPEAKER : FAIL  I2S write failed (check DIN/BCLK/LRC)");
      return false;
    }
  }

  memset(stereo, 0, sizeof(stereo));
  for (int i = 0; i < 4; ++i) {
    i2s.write(reinterpret_cast<const uint8_t *>(stereo), sizeof(stereo));
  }
  return true;
}

void setup() {
  Serial.begin(115200);
  delay(400);

  Serial.println();
  Serial.println("Kaew GATEWAY speaker test | Arduino-ESP32 3.x (ESP_I2S.h I2SClass) | Serial 115200");
  Serial.println("MAX98357A | DIN GPIO9, BCLK GPIO10, LRC GPIO11");
  Serial.println("This test cannot self-verify. Listen for a short rising beep every few seconds.");

  // setPins(bclk, ws, dout, din). din unused for a speaker-only test.
  i2s.setPins(SPK_BCLK, SPK_LRC, SPK_DIN, -1);
  speakerReady = i2s.begin(I2S_MODE_STD, SAMPLE_RATE, I2S_DATA_BIT_WIDTH_16BIT, I2S_SLOT_MODE_STEREO);
  if (!speakerReady) {
    Serial.println("SPEAKER : FAIL  I2S init failed (check DIN=GPIO9, BCLK=GPIO10, LRC=GPIO11)");
    Serial.println("          Also check VIN (5V or 3.3V), GND, speaker wires, and SD pin not held low.");
  }
}

void loop() {
  static uint32_t last = 0;
  if (millis() - last < PERIOD_MS) {
    delay(10);
    return;
  }
  last = millis();

  if (!speakerReady) {
    Serial.println("SPEAKER : FAIL  I2S init failed (check DIN/BCLK/LRC, VIN 5V/3.3V, GND, speaker wires, SD pin)");
    return;
  }

  Serial.println("SPEAKER : INFO  playing 400-2400 Hz sweep (~0.5 s, moderate volume)");
  Serial.println("          No sound? Check VIN (5V or 3.3V), GND, speaker +/- wires, and SD (shutdown) pin not held low.");
  if (playSweep()) {
    Serial.println("SPEAKER : INFO  sweep sent (listen — this test cannot hear the speaker)");
  }
}
