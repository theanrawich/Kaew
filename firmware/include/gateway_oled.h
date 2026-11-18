#pragma once
#include <Arduino.h>
#include <U8g2lib.h>
#include <Wire.h>
#include <esp_timer.h>
#include <time.h>
#include "cloud_publisher.h"

static_assert(KAEW_OLED_ADDRESS >= 0x08 && KAEW_OLED_ADDRESS <= 0x77,
              "OLED address must be an unreserved 7-bit I2C address");
static_assert(KAEW_OLED_DRIVER == 1306 || KAEW_OLED_DRIVER == 1106,
              "Select SSD1306 (1306) or SH1106 (1106)");

class GatewayOled {
#if KAEW_OLED_DRIVER == 1106
  U8G2_SH1106_128X64_NONAME_F_HW_I2C panel_{U8G2_R0, U8X8_PIN_NONE, KAEW_OLED_SCL, KAEW_OLED_SDA};
#else
  U8G2_SSD1306_128X64_NONAME_F_HW_I2C panel_{U8G2_R0, U8X8_PIN_NONE, KAEW_OLED_SCL, KAEW_OLED_SDA};
#endif
  CloudPublisher &cloud_;

  void centered(const char *text, uint8_t baseline, const uint8_t *font) {
    panel_.setFont(font);
    if (panel_.getStrWidth(text) > 128) panel_.setFont(u8g2_font_6x12_tr);
    panel_.drawStr((128 - panel_.getStrWidth(text)) / 2, baseline, text);
  }

  void drawClock(time_t epoch) {
    // Bangkok uses UTC+07:00 year-round. Leave the process timezone alone.
    const time_t bangkok = epoch + 7 * 3600;
    tm local{};
    if (epoch < CLOCK_MIN_EPOCH || !gmtime_r(&bangkok, &local)) {
      centered("Clock syncing", 36, u8g2_font_6x12_tr);
      return;
    }
    char clock[6], date[16];
    strftime(clock, sizeof clock, "%H:%M", &local);
    strftime(date, sizeof date, "%d/%m/%Y", &local);
    centered(clock, 34, u8g2_font_logisoso24_tn);
    centered(date, 55, u8g2_font_6x12_tr);
  }

  bool responds() {
    Wire.beginTransmission(KAEW_OLED_ADDRESS);
    return Wire.endTransmission() == 0;
  }

  void run() {
    if (!Wire.begin(KAEW_OLED_SDA, KAEW_OLED_SCL, 400000)) return;
    Wire.setTimeOut(10);
    if (!responds()) return;
    panel_.setI2CAddress(KAEW_OLED_ADDRESS << 1);
    panel_.setBusClock(400000);
    panel_.begin();
    const int64_t startedMs = esp_timer_get_time() / 1000;
    TickType_t lastFrame = xTaskGetTickCount();
    while (responds()) {
      const time_t epoch = time(nullptr);
      const auto snapshot = cloud_.reminderSnapshot();
      const int64_t uptimeMs = esp_timer_get_time() / 1000;
      panel_.clearBuffer();
      if ((uptimeMs - startedMs) / 5000 % 2 == 0) {
        drawClock(epoch);
      } else {
        const auto countdown = reminderCountdown(snapshot, epoch, uptimeMs);
        centered(countdown.label, countdown.digits[0] ? 15 : 36, u8g2_font_6x12_tr);
        if (countdown.digits[0]) centered(countdown.digits, 49, u8g2_font_logisoso24_tn);
      }
      panel_.sendBuffer();
      vTaskDelayUntil(&lastFrame, pdMS_TO_TICKS(1000));
    }
  }

  static void task(void *context) {
    static_cast<GatewayOled *>(context)->run();
    vTaskDelete(nullptr);
  }

public:
  explicit GatewayOled(CloudPublisher &cloud) : cloud_(cloud) {}

  void begin() {
    // I2C waits stay in this low-priority task on the gateway loop core.
    xTaskCreatePinnedToCore(task, "kaew-oled", 4096, this, tskIDLE_PRIORITY, nullptr, ARDUINO_RUNNING_CORE);
  }
};
