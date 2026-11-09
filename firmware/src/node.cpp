#include <Arduino.h>
#include <OneWire.h>
#include <DallasTemperature.h>

namespace {
constexpr int TEMP_PIN = 4;
constexpr int TDS_PIN = 34;
// Do not configure the level input before its output interface is verified.
constexpr int LEVEL_PIN = -1;
OneWire oneWire(TEMP_PIN);
DallasTemperature temp(&oneWire);
uint32_t started = 0, sequence = 0;
bool waiting = false;
}

void setup() {
  Serial.begin(115200);
  analogReadResolution(12);
  temp.begin();
  temp.setWaitForConversion(false);
  if (LEVEL_PIN >= 0) pinMode(LEVEL_PIN, INPUT);
}

void loop() {
  uint32_t now = millis();
  if (!waiting) { temp.requestTemperatures(); started = now; waiting = true; }
  if (waiting && uint32_t(now - started) >= 1000) {
    float c = temp.getTempCByIndex(0);
    bool valid = c != DEVICE_DISCONNECTED_C && c >= -55.0f && c <= 125.0f;
    // Raw ADC is not a calibrated TDS measurement. Unknown level fails closed.
    Serial.printf("{\"seq\":%lu,\"temp_valid\":%s,\"temp_c\":%.2f,\"tds_adc\":%d,\"level\":\"%s\"}\n",
      static_cast<unsigned long>(sequence++), valid ? "true" : "false", valid ? c : 0.0f,
      analogRead(TDS_PIN), LEVEL_PIN < 0 ? "unknown" : (digitalRead(LEVEL_PIN) ? "wet" : "dry"));
    waiting = false;
  }
  delay(5);
}
