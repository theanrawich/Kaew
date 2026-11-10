#include <Arduino.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include <esp_system.h>
#include "wire_protocol.h"

namespace {
constexpr int TEMP_PIN = 4;
// Disabled until the exact TDS board output and GPIO voltage are verified.
constexpr int TDS_PIN = -1;
// Do not configure the level input before its output interface is verified.
constexpr int LEVEL_PIN = -1;
OneWire oneWire(TEMP_PIN);
DallasTemperature temp(&oneWire);
uint32_t started = 0, sequence = 0;
bool waiting = false;
constexpr int LINK_RX = 26, LINK_TX = 25;
uint32_t sessionId = 0, sentCount = 0, ackCount = 0, droppedCount = 0;
Sender sender;
FrameParser parser;
}

void setup() {
  Serial.begin(115200);
  Serial2.begin(115200, SERIAL_8N1, LINK_RX, LINK_TX);
  sessionId = esp_random(); if (!sessionId) sessionId = 1;
  analogReadResolution(12);
  temp.begin();
  temp.setWaitForConversion(false);
  if (LEVEL_PIN >= 0) pinMode(LEVEL_PIN, INPUT);
}

void loop() {
  uint32_t now = millis();
  while (Serial2.available()) {
    Packet p{}; bool ack = false;
    if (parser.push(static_cast<uint8_t>(Serial2.read()), p, ack) && ack && sender.acknowledge(p.session, p.seq)) ++ackCount;
  }
  if (sender.expired(now)) { sender.drop(); ++droppedCount; }
  if (sender.due(now)) { uint8_t bytes[FRAME_SIZE]; encode(sender.packet(), false, bytes); Serial2.write(bytes, sizeof bytes); sender.sent(now); ++sentCount; }
  if (!waiting) { temp.requestTemperatures(); started = now; waiting = true; }
  if (waiting && uint32_t(now - started) >= 1000) {
    float c = temp.getTempCByIndex(0);
    bool valid = c != DEVICE_DISCONNECTED_C && c >= -55.0f && c <= 125.0f;
    // Raw ADC is not a calibrated TDS measurement. Unknown level fails closed.
    uint16_t adc = TDS_PIN < 0 ? UINT16_MAX : static_cast<uint16_t>(analogRead(TDS_PIN));
    uint8_t level = LEVEL_PIN < 0 ? 0 : (digitalRead(LEVEL_PIN) ? 1 : 2);
    if (!sender.pending()) {
      Packet p{1, sessionId, sequence++, static_cast<int16_t>(valid ? c * 100.0f : INT16_MIN), adc, level};
      sender.begin(p, now);
    }
    Serial.printf("node seq=%lu level=%u tx=%lu ack=%lu dropped=%lu\n", static_cast<unsigned long>(sequence), level,
      static_cast<unsigned long>(sentCount), static_cast<unsigned long>(ackCount), static_cast<unsigned long>(droppedCount));
    waiting = false;
  }
  delay(5);
}
