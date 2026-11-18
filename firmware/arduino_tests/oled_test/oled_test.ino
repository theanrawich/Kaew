/*
 * Kaew gateway OLED wiring test (standalone Arduino sketch)
 *
 * Requires Arduino-ESP32 core 3.x (ESP32S3 Dev Module).
 *
 * Arduino IDE board settings:
 *   Tools > Board:            "ESP32S3 Dev Module"
 *   Tools > USB CDC On Boot:  "Enabled"
 *   Tools > Flash Size:       "16MB (128Mb)"
 *   Tools > PSRAM:            "OPI PSRAM"
 *   Tools > Partition Scheme: "16M Flash (3MB APP/9.9MB FATFS)"
 *   Tools > Port:             "COM15"   (Windows; Kaew gateway is usually COM15)
 *   Serial Monitor:           115200 baud
 *
 * Libraries (Sketch > Include Library > Manage Libraries):
 *   - U8g2 by olikraus
 *
 * Wiring (gateway, power off while connecting):
 *   OLED VCC -> 3.3V
 *   OLED GND -> GND
 *   OLED SDA -> GPIO17
 *   OLED SCL -> GPIO18
 *   I2C address 0x3C (default)
 *
 * Hard rules: do not wire or configure GPIO13 (reserved pump relay).
 * Do not actuate the pump. Do not use GPIO21/47 (node UART).
 *
 * Every ~2.5 s the sketch scans I2C, prints found addresses, and draws a
 * test pattern plus a counter. It alternates SSD1306 and SH1106 drivers
 * so you can see which controller matches your panel.
 */

#include <Wire.h>
#include <U8g2lib.h>

constexpr int SDA_PIN = 17;
constexpr int SCL_PIN = 18;
constexpr uint8_t OLED_ADDR = 0x3C;
constexpr uint32_t REPORT_MS = 2500;

U8G2_SSD1306_128X64_NONAME_F_HW_I2C ssd1306(U8G2_R0, U8X8_PIN_NONE, SCL_PIN, SDA_PIN);
U8G2_SH1106_128X64_NONAME_F_HW_I2C sh1106(U8G2_R0, U8X8_PIN_NONE, SCL_PIN, SDA_PIN);

bool driversStarted = false;
uint32_t counter = 0;

void drawPattern(U8G2 &panel, const char *driver) {
  char line[32];
  panel.clearBuffer();
  panel.drawFrame(0, 0, 128, 64);
  panel.drawLine(0, 0, 127, 63);
  panel.drawLine(0, 63, 127, 0);
  panel.drawBox(2, 2, 8, 8);
  panel.drawBox(118, 54, 8, 8);
  panel.setFont(u8g2_font_6x12_tf);
  panel.drawStr(16, 16, "Kaew OLED test");
  panel.drawStr(16, 30, driver);
  snprintf(line, sizeof(line), "count %lu", static_cast<unsigned long>(counter));
  panel.drawStr(16, 46, line);
  panel.sendBuffer();
}

bool scanBus(bool &foundExpected, unsigned &found) {
  foundExpected = false;
  found = 0;
  for (uint8_t address = 0x08; address <= 0x77; ++address) {
    Wire.beginTransmission(address);
    if (Wire.endTransmission() == 0) {
      if (found++ == 0) Serial.print("I2C     : INFO  found");
      Serial.printf(" 0x%02X", address);
      if (address == OLED_ADDR) foundExpected = true;
    }
  }
  if (found) Serial.println();
  return foundExpected;
}

void setup() {
  Serial.begin(115200);
  delay(400);
  Wire.begin(SDA_PIN, SCL_PIN);
  Wire.setTimeOut(20);
  ssd1306.setI2CAddress(OLED_ADDR << 1);
  sh1106.setI2CAddress(OLED_ADDR << 1);

  Serial.println();
  Serial.println("Kaew GATEWAY OLED test | Arduino-ESP32 3.x | Serial 115200");
  Serial.println("OLED     | SDA GPIO17, SCL GPIO18, address 0x3C");
  Serial.println("Alternates SSD1306 and SH1106. If one image looks shifted or garbled, wait for the other.");
}

void loop() {
  static uint32_t lastReport = 0;
  if (millis() - lastReport < REPORT_MS) {
    delay(10);
    return;
  }
  lastReport = millis();

  bool foundExpected = false;
  unsigned found = 0;
  if (!scanBus(foundExpected, found)) {
    driversStarted = false;
    if (found) {
      Serial.printf(
          "OLED    : WARN  I2C device(s) listed above, expected 0x%02X (check address or solder jumper)\n",
          OLED_ADDR);
    } else {
      Serial.println("OLED    : FAIL  no I2C device at 0x3C (check VCC 3.3V/GND, then try swapping SDA/SCL)");
    }
    return;
  }

  if (!driversStarted) {
    ssd1306.begin();
    sh1106.begin();
    driversStarted = true;
  }

  // Alternate drivers every two reports so each image stays up ~5 s.
  const bool useSh1106 = ((counter / 2) % 2) == 1;
  const char *driver = useSh1106 ? "SH1106" : "SSD1306";
  drawPattern(useSh1106 ? static_cast<U8G2 &>(sh1106) : static_cast<U8G2 &>(ssd1306), driver);
  Serial.printf("OLED    : PASS  I2C ACK at 0x%02X, drawing with %s (counter=%lu)\n",
                OLED_ADDR, driver, static_cast<unsigned long>(counter));
  ++counter;
}
