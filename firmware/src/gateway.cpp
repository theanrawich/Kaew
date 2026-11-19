#include <Arduino.h>
#include <HX711.h>

#include "sensor_publisher.h"

HX711 scale;
constexpr float calibrationFactor = 735.7f;
bool tared = false;

void setup() {
  Serial.begin(115200);
  scale.begin(5, 4);  // DT=GPIO5, SCK=GPIO4
  Serial.println("Keep the scale unloaded for tare");
#if __has_include("gateway_wifi.h")
  beginSensorPublisher();
#else
  Serial.println("Cloud upload disabled: configure include/gateway_wifi.h");
#endif
}

void loop() {
  if (!scale.is_ready()) {
    Serial.println("HX711 not ready");
  } else if (!tared) {
    scale.tare(8);
    tared = true;
    Serial.println("tare complete");
  } else {
    const long raw = scale.read();
    const float grams = (raw - scale.get_offset()) / calibrationFactor;
    Serial.printf("Raw    | %ld\n", raw);
    Serial.printf("Weight | %.2f g\n\n", grams);
#if __has_include("gateway_wifi.h")
    publishSensor(grams, "g", "HX711");
#endif
  }
  delay(500);
}
