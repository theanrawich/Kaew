#pragma once
#include <Arduino.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <time.h>
#include <esp_system.h>
#include "cloud_config.h"
#include "wire_protocol.h"

// Cloud work is confined to a lower-priority FreeRTOS task. This bounded queue
// is RAM-only, deliberately not called durable storage.
class CloudPublisher {
  QueueHandle_t queue_ = nullptr;
  uint32_t dropped_ = 0;
  static void worker(void *ctx) { static_cast<CloudPublisher*>(ctx)->run(); }
  void run() {
    WiFi.mode(WIFI_STA); WiFi.begin(KAEW_WIFI_SSID, KAEW_WIFI_PASSWORD);
    Packet packet{};
    bool clockRequested = false;
    uint32_t retryMs = 1000;
    for (;;) {
      if (xQueuePeek(queue_, &packet, pdMS_TO_TICKS(1000)) != pdTRUE) continue;
      if (WiFi.status() != WL_CONNECTED) { WiFi.reconnect(); vTaskDelay(pdMS_TO_TICKS(retryMs + esp_random() % (retryMs / 4 + 1))); retryMs = min(retryMs * 2, uint32_t(60000)); continue; }
      const char *url = KAEW_CLOUD_URL;
      const bool tls = strncmp(url, "https://", 8) == 0;
      const bool dev = KAEW_ALLOW_DEV_HTTP && strncmp(url, "http://", 7) == 0;
      if ((!tls && !dev) || !strlen(KAEW_CLOUD_TOKEN) || (tls && !strlen(KAEW_CLOUD_CA))) { vTaskDelay(pdMS_TO_TICKS(10000)); continue; }
      if (tls && !clockRequested) { configTime(0, 0, "pool.ntp.org"); clockRequested = true; }
      if (tls && time(nullptr) < 1577836800) { vTaskDelay(pdMS_TO_TICKS(5000)); continue; }
      WiFiClient plain; WiFiClientSecure secure;
      if (tls) secure.setCACert(KAEW_CLOUD_CA);
      HTTPClient http;
      bool began = tls ? http.begin(secure, url) : http.begin(plain, url);
      if (!began) { vTaskDelay(pdMS_TO_TICKS(retryMs)); retryMs = min(retryMs * 2, uint32_t(60000)); continue; }
      http.setTimeout(3000);
      http.addHeader("Content-Type", "application/json");
      http.addHeader("Authorization", String("Bearer ") + KAEW_CLOUD_TOKEN);
      char temp[24];
      if (packet.centiC == INT16_MIN) strcpy(temp, "null");
      else snprintf(temp, sizeof temp, "%.2f", packet.centiC / 100.0);
      const char *level = packet.level == 1 ? "wet" : packet.level == 2 ? "dry" : "unknown";
      char body[256];
      snprintf(body, sizeof body, "{\"device_id\":\"node-1\",\"session\":%lu,\"seq\":%lu,\"level\":\"%s\",\"temperature_c\":%s,\"tds_adc\":%u}",
               (unsigned long)packet.session, (unsigned long)packet.seq, level, temp, packet.adc);
      int result = http.POST((uint8_t*)body, strlen(body)); http.end();
      if (result == 200 || result == 201) { xQueueReceive(queue_, &packet, 0); retryMs = 1000; }
      else { vTaskDelay(pdMS_TO_TICKS(retryMs + esp_random() % (retryMs / 4 + 1))); retryMs = min(retryMs * 2, uint32_t(60000)); } // Retain even terminal failures.
    }
  }
public:
  bool begin() {
    if (!KAEW_CLOUD_ENABLED) return false;
    queue_ = xQueueCreate(16, sizeof(Packet));
    if (!queue_) return false;
    if (xTaskCreatePinnedToCore(worker, "kaew-cloud", 8192, this, 1, nullptr, 0) != pdPASS) { vQueueDelete(queue_); queue_=nullptr; return false; }
    return true;
  }
  bool enabled() const { return queue_ != nullptr; }
  bool hasSpace() const { return !queue_ || uxQueueSpacesAvailable(queue_) > 0; }
  bool enqueue(const Packet &p) {
    if (!queue_) return true;
    if (xQueueSend(queue_, &p, 0) == pdTRUE) return true;
    ++dropped_; return false;
  }
  uint32_t rejected() const { return dropped_; }
};
