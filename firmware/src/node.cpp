#include <Arduino.h>
#include <DallasTemperature.h>
#include <OneWire.h>
#include "sensor_publisher.h"

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
#if __has_include("gateway_wifi.h")
  beginSensorPublisher();
#else
  Serial.println("Cloud upload disabled: configure include/gateway_wifi.h");
#endif
  if (LEVEL_PIN >= 0) pinMode(LEVEL_PIN, INPUT);
}

void loop() {
  const uint32_t started = millis();
  temperature.requestTemperatures();
  const float tempC = temperature.getTempCByIndex(0);

  char tempText[12] = "unknown";
  const bool validTemperature = tempC >= -55.0f && tempC <= 125.0f;
  if (validTemperature) {
    snprintf(tempText, sizeof tempText, "%.2f", tempC);
  }

  char tdsText[8] = "unknown";
  const int tdsAdc = TDS_PIN >= 0 ? analogRead(TDS_PIN) : -1;
  if (tdsAdc >= 0) {
    snprintf(tdsText, sizeof tdsText, "%d", tdsAdc);
  }

  const bool wet = LEVEL_PIN >= 0 && digitalRead(LEVEL_PIN) == KAEW_LEVEL_WET_STATE;
  const char* waterLevel = "unknown";
  if (LEVEL_PIN >= 0) {
    waterLevel = wet ? "wet" : "dry";
  }

  Serial.printf("temp_c=%s tds_adc=%s water_level=%s\n", tempText, tdsText, waterLevel);
#if __has_include("gateway_wifi.h")
  if (tdsAdc >= 0) publishSensor(tdsAdc, "ADC", "TDS");
  if (validTemperature) publishSensor(tempC, "°C", "Temperature");
  if (LEVEL_PIN >= 0) publishSensor(wet ? 1 : 0, "", "Water Level");
#endif
  const uint32_t elapsed = millis() - started;
  if (elapsed < 1000) delay(1000 - elapsed);
}
