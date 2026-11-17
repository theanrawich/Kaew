#pragma once
#include <Arduino.h>
#include <HTTPClient.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <time.h>
#include "ai_refill.h"
#include "cloud_config.h"

struct AdviceResponse { AdviceQuery query; AdviceProposal proposal; bool valid = false; };

// All HTTPS and bounded parsing run outside the control loop. One request per
// local intent, no automatic retry, no persisted commands, no admin credential.
class AiAdviceClient {
  QueueHandle_t requests_ = nullptr, responses_ = nullptr;
  bool ready_ = false;
  static void worker(void *self) { static_cast<AiAdviceClient *>(self)->run(); }
  bool fetch(const AdviceQuery &q, AdviceProposal &proposal) {
    if (uint32_t(millis()-q.issuedAtMs) >= AI_REQUEST_MS || WiFi.status() != WL_CONNECTED || time(nullptr) < 1577836800) return false;
    const char *base = KAEW_ADVICE_URL;
    if (strncmp(base,"https://",8) || !strlen(KAEW_CLOUD_CA) || !strlen(KAEW_CLOUD_TOKEN) || strchr(base,'?') || strchr(base,'#')) return false;
    char suffix[180];
    snprintf(suffix,sizeof suffix,"?gateway=1&boot_session=%lu&request_id=%lu&cup_session=%lu&nonce=%lu",
      static_cast<unsigned long>(q.bootSession),static_cast<unsigned long>(q.requestId),
      static_cast<unsigned long>(q.cupSession),static_cast<unsigned long>(q.nonce));
    WiFiClientSecure secure; secure.setCACert(KAEW_CLOUD_CA);
    HTTPClient http;
    http.setConnectTimeout(1000); http.setTimeout(1000);
    http.setFollowRedirects(HTTPC_DISABLE_FOLLOW_REDIRECTS);
    if (!http.begin(secure,String(base)+suffix)) return false;
    http.addHeader("Authorization",String("Bearer ")+KAEW_CLOUD_TOKEN);
    http.addHeader("Accept","application/json");
    const int status = http.GET(), length = http.getSize();
    bool valid = false;
    if (status == 200 && length > 0 && length <= int(AI_RESPONSE_BYTES)) {
      char bytes[AI_RESPONSE_BYTES+1]{};
      auto stream = http.getStreamPtr();
      if (stream) { // Peer may disconnect after the headers were accepted.
        stream->setTimeout(1000);
        const size_t received = stream->readBytes(bytes,size_t(length));
        valid = received == size_t(length) && uint32_t(millis()-q.issuedAtMs) < AI_REQUEST_MS && parseAdvice(bytes,received,proposal);
      }
    }
    http.end(); return valid;
  }
  void run() {
    if (!KAEW_CLOUD_ENABLED) {
      WiFi.mode(WIFI_STA); WiFi.begin(KAEW_WIFI_SSID,KAEW_WIFI_PASSWORD);
    }
    configTime(0,0,"pool.ntp.org"); // Async; do not wait for synchronization.
    for (;;) {
      AdviceQuery query{};
      if (xQueueReceive(requests_,&query,portMAX_DELAY) != pdTRUE) continue;
      if (!KAEW_CLOUD_ENABLED && WiFi.status() != WL_CONNECTED) WiFi.reconnect();
      AdviceResponse response{}; response.query=query;
      response.valid=fetch(query,response.proposal);
      xQueueSend(responses_,&response,0); // A full queue drops; consent still expires.
    }
  }
public:
  bool begin() {
    if (!KAEW_AI_REFILL_ENABLED || !strlen(KAEW_ADVICE_URL) || !strlen(KAEW_CLOUD_TOKEN)) return false;
    requests_=xQueueCreate(1,sizeof(AdviceQuery)); responses_=xQueueCreate(1,sizeof(AdviceResponse));
    if (!requests_ || !responses_ || xTaskCreatePinnedToCore(worker,"kaew-advice",6144,this,1,nullptr,0) != pdPASS) return false;
    ready_=true; return true;
  }
  bool submit(const AdviceQuery &query) { return ready_ && xQueueSend(requests_,&query,0) == pdTRUE; }
  bool take(AdviceResponse &response) { return ready_ && xQueueReceive(responses_,&response,0) == pdTRUE; }
};
