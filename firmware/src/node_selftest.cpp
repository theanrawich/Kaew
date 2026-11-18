#include <Arduino.h>
#include <DallasTemperature.h>
#include <OneWire.h>
#include <cmath>
#include <cstring>

namespace {
constexpr int TDS = 4, LEVEL = 5, TEMP = 6;
constexpr int LINK_RX = 47, LINK_TX = 21;
constexpr uint32_t REPORT_MS = 3000;

OneWire bus(TEMP);
DallasTemperature sensor(&bus);
DeviceAddress probe;
bool probeFound = false, heardPeer = false;
uint32_t lastPeer = 0, lastPing = 0, lastReport = 0;

void serviceUart() {
  static char line[6];
  static size_t length = 0;
  static bool discard = false;
  // Bound work even if the peer is still sending production binary frames.
  for (int budget = 256; budget > 0 && Serial2.available(); --budget) {
    const int byte = Serial2.read();
    if (byte == '\n') {
      if (!discard && length == sizeof(line)) {
        const bool ping = memcmp(line, "G-PING", sizeof(line)) == 0;
        if (ping || memcmp(line, "G-PONG", sizeof(line)) == 0) {
          lastPeer = millis();
          heardPeer = true;
          if (ping) Serial2.print("N-PONG\n");
        }
      }
      length = 0;
      discard = false;
    } else if (!discard && length < sizeof(line)) {
      line[length++] = static_cast<char>(byte);
    } else {
      discard = true;
    }
  }

  const uint32_t now = millis();
  if (heardPeer && now - lastPeer >= 5000) heardPeer = false;
  if (now - lastPing >= 1000) {
    lastPing = now;
    Serial2.print("N-PING\n");
  }
}

void reportUart() {
  serviceUart();
  if (heardPeer) {
    Serial.printf("UART    : PASS  heard gateway %lu ms ago\n",
                  static_cast<unsigned long>(millis() - lastPeer));
  } else {
    Serial.println("UART    : FAIL  no ping from gateway (check node GPIO21 TX -> gateway GPIO21 RX, "
                   "node GPIO47 RX <- gateway GPIO47 TX, and common GND)");
  }
}

void startTemperature() {
  // Rediscover the probe each cycle so reconnecting it needs no reboot.
  probeFound = sensor.getAddress(probe, 0);
  if (probeFound) sensor.requestTemperaturesByAddress(probe);
}

void reportTemperature() {
  const float celsius = probeFound ? sensor.getTempC(probe) : DEVICE_DISCONNECTED_C;
  if (celsius == DEVICE_DISCONNECTED_C) {
    Serial.println("DS18B20 : FAIL  no DS18B20 (check DQ on GPIO6, 4.7k pull-up to 3.3V, and GND)");
  } else if (celsius == 85.0f) {
    Serial.println("DS18B20 : WARN  reading 85 C (conversion failed or wiring intermittent)");
  } else if (!std::isfinite(celsius) || celsius < -55.0f || celsius > 125.0f) {
    Serial.printf("DS18B20 : FAIL  %.2f C (outside sensor range - check probe and DQ wiring)\n", celsius);
  } else {
    Serial.printf("DS18B20 : PASS  %.2f C\n", celsius);
  }
}

void reportTds() {
  // Check several samples before calling either ADC rail stuck.
  unsigned total = 0;
  constexpr unsigned samples = 8;
  for (unsigned i = 0; i < samples; ++i) total += analogRead(TDS);
  if (total == 0) {
    Serial.println("TDS     : WARN  ADC=0 (stuck at 0 - check VCC/GND or floating analog pin)");
  } else if (total == samples * 4095) {
    Serial.println("TDS     : WARN  ADC=4095 (stuck at 4095 - check for short to 3.3V or sensor output over-range)");
  } else {
    Serial.printf("TDS     : PASS  ADC=%u (raw average)\n", (total + samples / 2) / samples);
  }
}
}  // namespace

void setup() {
  Serial.begin(115200);
  Serial2.begin(115200, SERIAL_8N1, LINK_RX, LINK_TX);
  pinMode(LEVEL, INPUT);
  analogReadResolution(12);
  sensor.begin();
  sensor.setWaitForConversion(false);
  startTemperature();
  lastReport = millis();

  Serial.println("\nKaew NODE wiring self-test | USB Serial 115200");
  Serial.println("Module   | Pin(s)");
  Serial.println("TDS      | GPIO4 analog (sensor output <= 3.3 V)");
  Serial.println("LEVEL    | GPIO5 digital input");
  Serial.println("DS18B20  | GPIO6 DQ with 4.7k pull-up to 3.3 V");
  Serial.println("UART     | node GPIO21 TX -> gateway GPIO21 RX");
  Serial.println("         | node GPIO47 RX <- gateway GPIO47 TX; common GND");
}

void loop() {
  serviceUart();
  if (millis() - lastReport >= REPORT_MS) {
    Serial.println("\n======== Kaew NODE self-test ========");
    reportTemperature();
    reportTds();
    Serial.printf("LEVEL   : INFO  GPIO5=%s\n", digitalRead(LEVEL) == HIGH ? "HIGH" : "LOW");
    reportUart();
    Serial.println("=====================================");
    startTemperature();
    lastReport = millis();
  }
  delay(1);
}
