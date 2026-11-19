#include <Arduino.h>
#include <HX711.h>

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

void publishWeight(float grams) {
  if (WiFi.status() != WL_CONNECTED || std::time(nullptr) < 1700000000 ||
      !std::isfinite(grams) || (uploadFailed && millis() - lastUploadFailureMs < uploadRetryMs)) {
    return;
  }

  char payload[96];
  snprintf(payload, sizeof(payload),
           "{\"value\":%.2f,\"unit\":\"g\",\"sensor\":\"HX711\"}", grams);

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
#endif

HX711 scale;
constexpr float calibrationFactor = 735.7f;
bool tared = false;

void setup() {
  Serial.begin(115200);
  scale.begin(5, 4);  // DT=GPIO5, SCK=GPIO4
  Serial.println("Keep the scale unloaded for tare");
#if __has_include("gateway_wifi.h")
  sensorClient.setCACert(renderCa);
  sensorClient.setHandshakeTimeout(3);
  sensorRequest.setReuse(true);
  sensorRequest.setConnectTimeout(3000);
  sensorRequest.setTimeout(3000);
  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  WiFi.begin(wifiSsid, wifiPassword);
  configTime(0, 0, "time.google.com", "pool.ntp.org");
#else
  Serial.println("Cloud upload disabled: configure include/gateway_wifi.h");
#endif
}

void loop() {
  if (!scale.is_ready()) {
    Serial.println("HX711 not ready");
  } else if (!tared) {
    scale.tare(8);
    tared = true;
    Serial.println("tare complete");
  } else {
    const long raw = scale.read();
    const float grams = (raw - scale.get_offset()) / calibrationFactor;
    Serial.printf("Raw    | %ld\n", raw);
    Serial.printf("Weight | %.2f g\n\n", grams);
#if __has_include("gateway_wifi.h")
    publishWeight(grams);
#endif
  }
  delay(500);
}
