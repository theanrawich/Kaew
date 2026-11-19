#include <Arduino.h>
#include <HX711.h>

constexpr int kLoadCellDataPin = 5;
constexpr int kLoadCellClockPin = 4;
constexpr unsigned long kLogIntervalMs = 500;

HX711 loadCell;

void setup() {
  Serial.begin(115200);
  loadCell.begin(kLoadCellDataPin, kLoadCellClockPin);
}

void loop() {
  if (loadCell.is_ready()) {
    Serial.printf("hx711_raw=%ld\n", loadCell.read());
  } else {
    Serial.println("HX711 not ready");
  }
  delay(kLogIntervalMs);
}
