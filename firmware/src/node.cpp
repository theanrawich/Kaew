#include <Arduino.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include <esp_system.h>
#include "wire_protocol.h"
#include "packet_trace.h"

namespace {
constexpr int TEMP_PIN = 6;
// TDS analog output; board must output <= 3.3 V.
constexpr int TDS_PIN = 4;
// Digital water-level output.
constexpr int LEVEL_PIN = 5;
OneWire oneWire(TEMP_PIN);
DallasTemperature temp(&oneWire);
uint32_t started = 0, sequence = 0;
bool waiting = false;
// ESP32-S3 N16R8: GPIO26-37 are flash/PSRAM, so UART uses GPIO17 (TX) / GPIO18 (RX).
constexpr int LINK_RX = 18, LINK_TX = 17;
uint32_t sessionId = 0, sentCount = 0, ackCount = 0, droppedCount = 0;
Sender sender;
FrameParser parser;
PacketTrace trace;
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
    if (parser.push(static_cast<uint8_t>(Serial2.read()), p, ack) && ack && sender.acknowledge(p.session, p.seq)) {
      ++ackCount; trace.emit("ack", p, now);
    }
  }
  if (sender.expired(now)) { trace.emit("drop", sender.packet(), now); sender.drop(); ++droppedCount; }
  if (sender.due(now)) {
    uint8_t bytes[FRAME_SIZE]; encode(sender.packet(), false, bytes); Serial2.write(bytes, sizeof bytes);
    trace.emit("tx", sender.packet(), now); sender.sent(now); ++sentCount;
  }
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
    Serial.printf("node seq=%lu level=%u tx=%lu ack=%lu dropped=%lu trace_dropped=%lu\n", static_cast<unsigned long>(sequence), level,
      static_cast<unsigned long>(sentCount), static_cast<unsigned long>(ackCount), static_cast<unsigned long>(droppedCount), static_cast<unsigned long>(trace.dropped()));
    waiting = false;
  }
  delay(5);
}
