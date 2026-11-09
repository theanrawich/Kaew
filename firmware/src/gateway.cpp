#include <Arduino.h>
#include <HX711.h>
#include <Preferences.h>
#include "safety.h"
#include "scale_processing.h"
#include "wire_protocol.h"
#include "cloud_publisher.h"
#include "audio_io.h"
#ifndef KAEW_AUDIO_ENABLED
#define KAEW_AUDIO_ENABLED 0
#endif

namespace {
constexpr int HX_DATA = 17, HX_CLOCK = 18;
// These interfaces are intentionally disabled until the exact hardware is verified.
constexpr int PUMP_PIN = -1;
constexpr int ESTOP_PIN = -1;
constexpr int LINK_RX = 1, LINK_TX = 2;
HX711 scale;
Preferences preferences;
Calibration calibration{};
WeightFilter filter;
CupDetector cup;
CupTare cupTare;
FrameParser parser;
Receiver receiver;
CloudPublisher cloud;
AudioIO audio;
uint32_t accepted = 0, duplicates = 0, rejected = 0;
SafetyController controller;
Inputs inputs{false, false, false, false, false, 0, 0, 0};
uint32_t lastPrint = 0;
}

void setup() {
  // An enabled driver must have a hardware pull-down and independent power cut.
  if (PUMP_PIN >= 0) { digitalWrite(PUMP_PIN, LOW); pinMode(PUMP_PIN, OUTPUT); }
  if (ESTOP_PIN >= 0) pinMode(ESTOP_PIN, INPUT_PULLUP);
  Serial.begin(115200);
  Serial.setTimeout(10);
  Serial1.begin(115200, SERIAL_8N1, LINK_RX, LINK_TX);
  if (preferences.begin("kaew-scale", false) && preferences.getBytesLength("cal-v1") == sizeof calibration)
    preferences.getBytes("cal-v1", &calibration, sizeof calibration);
  if (!validCalibration(calibration)) calibration = Calibration{};
  scale.begin(HX_DATA, HX_CLOCK);
  cloud.begin();
  if (KAEW_AUDIO_ENABLED && !audio.begin()) Serial.println("audio driver init failed");
}

void loop() {
  inputs.nowMs = millis();
  Packet persisted{};
  while (cloud.takeAck(persisted)) {
    uint8_t bytes[FRAME_SIZE]; encode(persisted, true, bytes); Serial1.write(bytes, sizeof bytes);
  }
  while (Serial1.available()) {
    Packet p{}; bool ack = false;
    if (parser.push(static_cast<uint8_t>(Serial1.read()), p, ack) && !ack) {
      Receiver previous = receiver;
      Receive result = receiver.accept(p, inputs.nowMs);
      if (result == Receive::Accepted || result == Receive::Duplicate) {
        if (cloud.enabled()) {
          if (!cloud.enqueue(p)) { if (result == Receive::Accepted) receiver = previous; ++rejected; continue; }
        } else {
          uint8_t bytes[FRAME_SIZE]; encode(p, true, bytes); Serial1.write(bytes, sizeof bytes);
        }
        if (result == Receive::Accepted) ++accepted; else ++duplicates;
      } else ++rejected;
    }
  }
  inputs.tankWet = receiver.fresh(inputs.nowMs) && receiver.latest().level == 1;
  inputs.estopOk = ESTOP_PIN >= 0 && digitalRead(ESTOP_PIN) == HIGH;
  if (Serial.available() && !controller.pumping()) {
    String line = Serial.readStringUntil('\n'); long zero, known; float grams;
    if (line == "TARE") {
      Serial.println(cupTare.set(inputs.cupPresent, inputs.scaleValid, inputs.weightG) ? "cup tare set (must be empty)" : "cup tare rejected");
    } else if (sscanf(line.c_str(), "CAL %ld %ld %f", &zero, &known, &grams) == 3) {
      Calibration next{};
      if (makeCalibration(zero, known, grams, next) && preferences.putBytes("cal-v1", &next, sizeof next) == sizeof next) {
        calibration = next; filter = WeightFilter{}; cup = CupDetector{}; cupTare.clear(); Serial.println("calibration saved; verify with known masses");
      } else Serial.println("calibration rejected or storage failed");
    }
  }
  if (scale.is_ready()) {
    long raw = scale.read();
    inputs.calibrated = validCalibration(calibration);
    if (inputs.calibrated && filter.push(toGrams(calibration, raw))) {
      inputs.weightG = filter.weight(); inputs.scaleValid = controller.pumping() || filter.stable();
      inputs.scaleAtMs = inputs.nowMs;
      inputs.cupPresent = controller.pumping() ? cup.updateDispensing(true, inputs.weightG) : cup.update(inputs.scaleValid, inputs.weightG);
    } else { inputs.scaleValid = false; inputs.cupPresent = false; }
    if (!inputs.cupPresent) cupTare.clear();
    if (uint32_t(inputs.nowMs - lastPrint) >= 1000) {
      float volume = 0; bool volumeKnown = cupTare.volume(inputs.cupPresent, inputs.weightG, volume);
      Serial.printf("hx711_raw=%ld calibrated=%d weight=%.1f stable=%d cup=%d volume_known=%d volume_ml=%.1f link_fresh=%d level=%u rx=%lu dup=%lu rejected=%lu cloud_reject=%lu cloud_error=%lu pump=off\n",
        raw, inputs.calibrated, inputs.weightG, inputs.scaleValid, inputs.cupPresent, volumeKnown, volume,
        receiver.fresh(inputs.nowMs), receiver.fresh(inputs.nowMs) ? receiver.latest().level : 0, static_cast<unsigned long>(accepted),
        static_cast<unsigned long>(duplicates), static_cast<unsigned long>(rejected), static_cast<unsigned long>(cloud.rejected()), static_cast<unsigned long>(cloud.errors()));
      lastPrint = inputs.nowMs;
    }
  }
  controller.update(inputs);
  if (PUMP_PIN >= 0) digitalWrite(PUMP_PIN, controller.pumping() ? HIGH : LOW);
  delay(5);
}
