#include <Arduino.h>
#include <HX711.h>
#include "safety.h"

namespace {
constexpr int HX_DATA = 17, HX_CLOCK = 18;
// These interfaces are intentionally disabled until the exact hardware is verified.
constexpr int PUMP_PIN = -1;
constexpr int ESTOP_PIN = -1;
constexpr bool CALIBRATED = false;
HX711 scale;
SafetyController controller;
Inputs inputs{false, false, false, false, CALIBRATED, 0, 0, 0};
uint32_t lastPrint = 0;
}

void setup() {
  // An enabled driver must have a hardware pull-down and independent power cut.
  if (PUMP_PIN >= 0) { digitalWrite(PUMP_PIN, LOW); pinMode(PUMP_PIN, OUTPUT); }
  if (ESTOP_PIN >= 0) pinMode(ESTOP_PIN, INPUT_PULLUP);
  Serial.begin(115200);
  scale.begin(HX_DATA, HX_CLOCK);
}

void loop() {
  inputs.nowMs = millis();
  inputs.estopOk = ESTOP_PIN >= 0 && digitalRead(ESTOP_PIN) == HIGH;
  if (scale.is_ready()) {
    long raw = scale.read();
    // Raw samples are observable, but never treated as grams without calibration.
    inputs.scaleValid = false;
    inputs.scaleAtMs = inputs.nowMs;
    if (uint32_t(inputs.nowMs - lastPrint) >= 1000) {
      Serial.printf("hx711_raw=%ld pump=off commissioning_required=1\n", raw);
      lastPrint = inputs.nowMs;
    }
  }
  controller.update(inputs);
  if (PUMP_PIN >= 0) digitalWrite(PUMP_PIN, controller.pumping() ? HIGH : LOW);
  delay(5);
}
