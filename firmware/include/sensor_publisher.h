#pragma once

#if __has_include("gateway_wifi.h")
#include <HTTPClient.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <cmath>
#include <ctime>
#include "gateway_wifi.h"
#include "render_ca.h"

constexpr char sensorEndpoint[] = "https://kaew-cloud.onrender.com/api/sensors";
constexpr unsigned long uploadRetryMs = 5000;
unsigned long lastUploadFailureMs = 0;
bool uploadFailed = false;
WiFiClientSecure sensorClient;
HTTPClient sensorRequest;

inline void publishSensor(float value, const char* unit, const char* sensor) {
  if (WiFi.status() != WL_CONNECTED || std::time(nullptr) < 1700000000 ||
      !std::isfinite(value) || (uploadFailed && millis() - lastUploadFailureMs < uploadRetryMs)) {
    return;
  }

  char payload[96];
  snprintf(payload, sizeof(payload),
           "{\"value\":%.2f,\"unit\":\"%s\",\"sensor\":\"%s\"}", value, unit, sensor);

  if (!sensorRequest.begin(sensorClient, sensorEndpoint)) {
    Serial.println("Could not initialize sensor HTTPS request");
    uploadFailed = true;
    lastUploadFailureMs = millis();
    return;
  }
  sensorRequest.addHeader("Content-Type", "application/json");
  const int status = sensorRequest.POST(payload);
  if (status > 0) {
    sensorRequest.getString();  // Drain the response so the TLS connection can be reused.
  }
  sensorRequest.end();
  uploadFailed = status != 201;
  if (uploadFailed) {
    lastUploadFailureMs = millis();
    Serial.printf("Sensor upload failed (%d)\n", status);
  }
}

inline void beginSensorPublisher() {
  sensorClient.setCACert(renderCa);
  sensorClient.setHandshakeTimeout(3);
  sensorRequest.setReuse(true);
  sensorRequest.setConnectTimeout(3000);
  sensorRequest.setTimeout(3000);
  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  WiFi.begin(wifiSsid, wifiPassword);
  configTime(0, 0, "time.google.com", "pool.ntp.org");
}
#endif
