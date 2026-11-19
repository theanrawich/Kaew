#include <Arduino.h>
#include <DallasTemperature.h>
#include <OneWire.h>

namespace {
constexpr int TEMP_PIN = 6;
constexpr int TDS_PIN = KAEW_TDS_PIN;
constexpr int LEVEL_PIN = KAEW_LEVEL_PIN;

OneWire oneWire(TEMP_PIN);
DallasTemperature temperature(&oneWire);
}

void setup() {
  Serial.begin(115200);
  temperature.begin();
  analogReadResolution(12);
  if (LEVEL_PIN >= 0) pinMode(LEVEL_PIN, INPUT);
}

void loop() {
  const uint32_t started = millis();
  temperature.requestTemperatures();
  const float tempC = temperature.getTempCByIndex(0);

  char tempText[12] = "unknown";
  if (tempC >= -55.0f && tempC <= 125.0f) {
    snprintf(tempText, sizeof tempText, "%.2f", tempC);
  }

  char tdsText[8] = "unknown";
  if (TDS_PIN >= 0) {
    snprintf(tdsText, sizeof tdsText, "%d", analogRead(TDS_PIN));
  }

  const char* waterLevel = "unknown";
  if (LEVEL_PIN >= 0) {
    waterLevel = digitalRead(LEVEL_PIN) == KAEW_LEVEL_WET_STATE ? "wet" : "dry";
  }

  Serial.printf("temp_c=%s tds_adc=%s water_level=%s\n", tempText, tdsText, waterLevel);
  const uint32_t elapsed = millis() - started;
  if (elapsed < 1000) delay(1000 - elapsed);
}
