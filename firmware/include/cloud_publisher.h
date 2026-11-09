#pragma once
#include <Arduino.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <time.h>
#include <esp_system.h>
#include "cloud_config.h"
#include "nvs_queue_store.h"

// Persistence and network use separate tasks; the control loop never waits for either.
class CloudPublisher {
  NvsQueueStore store_;
  DurableQueue durable_{store_};
  QueueHandle_t pending_=nullptr, acknowledgements_=nullptr;
  SemaphoreHandle_t lock_=nullptr;
  volatile uint32_t rejected_=0, errors_=0;
  bool ready_=false;
  static void persistTask(void *p) { static_cast<CloudPublisher*>(p)->persist(); }
  static void networkTask(void *p) { static_cast<CloudPublisher*>(p)->network(); }
  void persist() {
    uint32_t last=0; bool wrote=false, haveRecent=false; Packet packet{}, recent{};
    for (;;) {
      if(xQueueReceive(pending_,&packet,portMAX_DELAY)!=pdTRUE) continue;
      if(haveRecent && packet.node==recent.node && packet.session==recent.session && packet.seq==recent.seq) {
        uint8_t a[FRAME_SIZE],b[FRAME_SIZE]; encode(packet,false,a); encode(recent,false,b);
        if(memcmp(a,b,FRAME_SIZE)==0) { xQueueSend(acknowledgements_,&packet,portMAX_DELAY); continue; }
        ++errors_; continue; // Same ID with different data is not acknowledged.
      }
      if(wrote) { uint32_t elapsed=uint32_t(millis()-last); if(elapsed<KAEW_DURABLE_MIN_MS) vTaskDelay(pdMS_TO_TICKS(KAEW_DURABLE_MIN_MS-elapsed)); }
      xSemaphoreTake(lock_,portMAX_DELAY); QueueResult result=durable_.append(packet); xSemaphoreGive(lock_);
      if(result==QueueResult::Added || result==QueueResult::Duplicate) {
        if(result==QueueResult::Added) {last=millis();wrote=true;}
        recent=packet; haveRecent=true;
        xQueueSend(acknowledgements_,&packet,portMAX_DELAY);
      } else if(result==QueueResult::Full) ++rejected_;
      else ++errors_; // No ACK on full, invalid or damaged storage.
    }
  }
  void network() {
    WiFi.mode(WIFI_STA); WiFi.begin(KAEW_WIFI_SSID,KAEW_WIFI_PASSWORD);
    bool clockRequested=false, storageErrorReported=false; uint32_t retryMs=1000;
    for (;;) {
      Packet packet{};
      xSemaphoreTake(lock_,portMAX_DELAY); bool found=durable_.peek(packet); bool healthy=durable_.healthy(); xSemaphoreGive(lock_);
      if(!healthy && !storageErrorReported) { ++errors_; storageErrorReported=true; }
      if(!found) {vTaskDelay(pdMS_TO_TICKS(1000));continue;}
      if(WiFi.status()!=WL_CONNECTED) { WiFi.reconnect(); vTaskDelay(pdMS_TO_TICKS(retryMs+esp_random()%(retryMs/4+1))); retryMs=min(retryMs*2,uint32_t(60000));continue; }
      const char *url=KAEW_CLOUD_URL; bool tls=strncmp(url,"https://",8)==0;
      bool dev=KAEW_ALLOW_DEV_HTTP && strncmp(url,"http://",7)==0;
      if((!tls && !dev) || !strlen(KAEW_CLOUD_TOKEN) || (tls && !strlen(KAEW_CLOUD_CA))) {vTaskDelay(pdMS_TO_TICKS(10000));continue;}
      if(tls && !clockRequested) {configTime(0,0,"pool.ntp.org");clockRequested=true;}
      if(tls && time(nullptr)<1577836800) {vTaskDelay(pdMS_TO_TICKS(5000));continue;}
      WiFiClient plain; WiFiClientSecure secure; if(tls) secure.setCACert(KAEW_CLOUD_CA);
      HTTPClient http; bool began=tls ? http.begin(secure,url) : http.begin(plain,url);
      if(!began) {vTaskDelay(pdMS_TO_TICKS(retryMs));retryMs=min(retryMs*2,uint32_t(60000));continue;}
      http.setTimeout(3000); http.addHeader("Content-Type","application/json");
      http.addHeader("Authorization",String("Bearer ")+KAEW_CLOUD_TOKEN);
      char temp[24]; if(packet.centiC==INT16_MIN)strcpy(temp,"null");else snprintf(temp,sizeof temp,"%.2f",packet.centiC/100.0);
      const char *level=packet.level==1?"wet":packet.level==2?"dry":"unknown";
      char body[256]; snprintf(body,sizeof body,"{\"device_id\":\"node-1\",\"session\":%lu,\"seq\":%lu,\"level\":\"%s\",\"temperature_c\":%s,\"tds_adc\":%u,\"source\":\"device\"}",
        (unsigned long)packet.session,(unsigned long)packet.seq,level,temp,packet.adc);
      int result=http.POST((uint8_t*)body,strlen(body)); http.end();
      if(result==200 || result==201) {
        xSemaphoreTake(lock_,portMAX_DELAY); Packet head{};
        if(durable_.peek(head) && head.node==packet.node && head.session==packet.session && head.seq==packet.seq) {if(!durable_.pop())++errors_;}
        xSemaphoreGive(lock_); retryMs=1000;
      } else {vTaskDelay(pdMS_TO_TICKS(retryMs+esp_random()%(retryMs/4+1)));retryMs=min(retryMs*2,uint32_t(60000));}
    }
  }
public:
  bool begin() {
    if(!KAEW_CLOUD_ENABLED)return false;
    if(!store_.begin() || !durable_.recover()) {++errors_;return false;}
    lock_=xSemaphoreCreateMutex(); pending_=xQueueCreate(8,sizeof(Packet)); acknowledgements_=xQueueCreate(8,sizeof(Packet));
    if(!lock_ || !pending_ || !acknowledgements_) {++errors_;return false;}
    // Fail closed if either task fails to start; no UART ACKs then leave the loop.
    TaskHandle_t persistent=nullptr;
    if(xTaskCreatePinnedToCore(persistTask,"kaew-store",4096,this,1,&persistent,0)!=pdPASS) {++errors_;return false;}
    if(xTaskCreatePinnedToCore(networkTask,"kaew-cloud",8192,this,1,nullptr,0)!=pdPASS) {vTaskDelete(persistent);++errors_;return false;}
    ready_=true; return true;
  }
  bool enabled() const {return KAEW_CLOUD_ENABLED;}
  bool enqueue(const Packet &p) {if(!enabled())return true; if(!ready_ || xQueueSend(pending_,&p,0)!=pdTRUE){++rejected_;return false;} return true;}
  bool takeAck(Packet &p) {return ready_ && xQueueReceive(acknowledgements_,&p,0)==pdTRUE;}
  uint32_t rejected() const {return rejected_;}
  uint32_t errors() const {return errors_;}
};
