#pragma once
#include <Arduino.h>
#include <atomic>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <time.h>
#include <esp_system.h>
#include <esp_timer.h>
#include <cJSON.h>
#include "cloud_config.h"
#include "scale_upload.h"
#include "cloud_outbox_record.h"
#include "nvs_queue_store.h"
#include "reminder_countdown.h"

// Persistence and network use separate tasks; the control loop never waits for either.
class CloudPublisher {
  NvsQueueStore store_;
  DurableOutbox<CloudOutboxRecord, CloudOutboxRecord> durable_{store_};
  QueueHandle_t pending_=nullptr, acknowledgements_=nullptr;
  SemaphoreHandle_t lock_=nullptr;
  std::atomic<uint32_t> rejected_{0}, errors_{0};
  portMUX_TYPE reminderLock_ = portMUX_INITIALIZER_UNLOCKED;
  ReminderSnapshot reminder_{};

  void readReminder(HTTPClient &http) {
    char body[128]{};
    const int length = http.getSize();
    auto *stream = http.getStreamPtr();
    if (!stream || length <= 0 || length >= int(sizeof body)) return;

    // Telemetry was already accepted. Bound the time spent on display metadata.
    const uint32_t started = millis();
    int offset = 0;
    while (offset < length && millis() - started < 250) {
      const int available = stream->available();
      if (available > 0) {
        const int count = stream->read(reinterpret_cast<uint8_t *>(body + offset),
                                       min(available, length - offset));
        if (count <= 0) return;
        offset += count;
      } else if (!stream->connected()) {
        return;
      } else {
        vTaskDelay(1);
      }
    }
    if (offset != length) return;

    cJSON *json = cJSON_ParseWithOpts(body, nullptr, true);
    const auto *due = cJSON_GetObjectItemCaseSensitive(json, "next_reminder_at");
    // The supported calendar range ends at 9999-12-31.
    if (cJSON_IsNull(due) || (cJSON_IsNumber(due) && due->valuedouble >= CLOCK_MIN_EPOCH &&
        due->valuedouble <= 253402300799.0 &&
        due->valuedouble == static_cast<int64_t>(due->valuedouble))) {
      const ReminderSnapshot snapshot{
        cJSON_IsNull(due) ? 0 : static_cast<int64_t>(due->valuedouble),
        esp_timer_get_time() / 1000
      };
      portENTER_CRITICAL(&reminderLock_);
      reminder_ = snapshot;
      portEXIT_CRITICAL(&reminderLock_);
    }
    cJSON_Delete(json);
  }

  bool ready_=false, keepConnected_=false;
  QueueHandle_t scaleUpdates_=nullptr;
  uint32_t scaleStaleMs_=0;
  static void persistTask(void *p) { static_cast<CloudPublisher*>(p)->persist(); }
  static void networkTask(void *p) { static_cast<CloudPublisher*>(p)->network(); }
  static void scaleTask(void *p) { static_cast<CloudPublisher*>(p)->publishScale(); }

  void publishScale() {
    String url(KAEW_CLOUD_URL);
    const bool tls = url.startsWith("https://");
    if (!(tls ? strlen(KAEW_CLOUD_CA) : KAEW_ALLOW_DEV_HTTP && url.startsWith("http://"))
        || !strlen(KAEW_CLOUD_TOKEN)) { vTaskDelete(nullptr); return; }
    const int path = url.indexOf('/', tls ? 8 : 7);
    if (path >= 0) url.remove(path);
    url += "/api/scale";
    for (;;) {
      vTaskDelay(pdMS_TO_TICKS(2000));
      if (WiFi.status() != WL_CONNECTED || (tls && time(nullptr) < CLOCK_MIN_EPOCH)) continue;
      ScaleUpload sample{};
      if (xQueueReceive(scaleUpdates_, &sample, 0) != pdTRUE) continue;
      char body[96];
      if (!formatScaleUpload(sample, millis(), scaleStaleMs_, body, sizeof body)) continue;

      WiFiClient plain;
      WiFiClientSecure secure;
      if (tls) secure.setCACert(KAEW_CLOUD_CA);
      HTTPClient http;
      if (!(tls ? http.begin(secure, url) : http.begin(plain, url))) continue;
      http.setConnectTimeout(3000);
      http.setTimeout(3000);
      http.addHeader("Content-Type", "application/json");
      http.addHeader("Authorization", String("Bearer ") + KAEW_CLOUD_TOKEN);
      http.POST(reinterpret_cast<uint8_t*>(body), strlen(body));
      http.end();
    }
  }

  void persist() {
    uint32_t last=0; bool wrote=false, haveRecent=false; CloudOutboxRecord record{}; Packet recent{};
    for (;;) {
      if(xQueueReceive(pending_,&record,portMAX_DELAY)!=pdTRUE) continue;
      const Packet &packet=record.telemetry;
      if(!record.isDrink() && haveRecent && packet.node==recent.node && packet.session==recent.session && packet.seq==recent.seq) {
        uint8_t a[FRAME_SIZE],b[FRAME_SIZE]; encode(packet,false,a); encode(recent,false,b);
        if(memcmp(a,b,FRAME_SIZE)==0) { xQueueSend(acknowledgements_,&packet,portMAX_DELAY); continue; }
        ++errors_; continue; // Same ID with different data is not acknowledged.
      }
      if(wrote) { uint32_t elapsed=uint32_t(millis()-last); if(elapsed<KAEW_DURABLE_MIN_MS) vTaskDelay(pdMS_TO_TICKS(KAEW_DURABLE_MIN_MS-elapsed)); }
      xSemaphoreTake(lock_,portMAX_DELAY); QueueResult result=durable_.append(record); xSemaphoreGive(lock_);
      if(result==QueueResult::Added || result==QueueResult::Duplicate) {
        if(result==QueueResult::Added) {last=millis();wrote=true;}
        if(!record.isDrink()) {
          recent=packet; haveRecent=true;
          xQueueSend(acknowledgements_,&packet,portMAX_DELAY);
        }
      } else if(result==QueueResult::Full) ++rejected_;
      else ++errors_; // No ACK on full, invalid or damaged storage.
    }
  }
  void network() {
    WiFi.mode(WIFI_STA); WiFi.begin(KAEW_WIFI_SSID,KAEW_WIFI_PASSWORD);
    bool clockRequested=false, storageErrorReported=false; uint32_t retryMs=1000;
    const char *url=KAEW_CLOUD_URL; bool tls=strncmp(url,"https://",8)==0;
    bool dev=KAEW_ALLOW_DEV_HTTP && strncmp(url,"http://",7)==0;
    for (;;) {
      // STT shares this station and clock even when the telemetry outbox is empty.
      if (tls && !clockRequested && WiFi.status() == WL_CONNECTED) {
        configTime(0,0,"pool.ntp.org","time.google.com");
        clockRequested=true;
      }
      CloudOutboxRecord record{};
      xSemaphoreTake(lock_,portMAX_DELAY); bool found=durable_.peek(record); bool healthy=durable_.healthy(); xSemaphoreGive(lock_);
      if(!healthy && !storageErrorReported) { ++errors_; storageErrorReported=true; }
      if(!found && !keepConnected_ && !scaleUpdates_) {vTaskDelay(pdMS_TO_TICKS(1000));continue;}
      if(WiFi.status()!=WL_CONNECTED) { WiFi.reconnect(); vTaskDelay(pdMS_TO_TICKS(retryMs+esp_random()%(retryMs/4+1))); retryMs=min(retryMs*2,uint32_t(60000));continue; }
      if(!found) {vTaskDelay(pdMS_TO_TICKS(1000));continue;}
      if((!tls && !dev) || !strlen(KAEW_CLOUD_TOKEN) || (tls && !strlen(KAEW_CLOUD_CA))) {vTaskDelay(pdMS_TO_TICKS(10000));continue;}
      if(tls && time(nullptr)<CLOCK_MIN_EPOCH) {vTaskDelay(pdMS_TO_TICKS(5000));continue;}
      WiFiClient plain; WiFiClientSecure secure; if(tls) secure.setCACert(KAEW_CLOUD_CA);
      String requestUrl(url);
      if(record.isDrink()) {
        const int path=requestUrl.indexOf('/',tls ? 8 : 7);
        if(path>=0) requestUrl.remove(path);
        requestUrl += "/api/events";
      }
      HTTPClient http; bool began=tls ? http.begin(secure,requestUrl) : http.begin(plain,requestUrl);
      if(!began) {vTaskDelay(pdMS_TO_TICKS(retryMs));retryMs=min(retryMs*2,uint32_t(60000));continue;}
      http.setTimeout(record.isDrink() ? 25000 : 3000);
      http.addHeader("Content-Type","application/json");
      http.addHeader("Authorization",String("Bearer ")+KAEW_CLOUD_TOKEN);
      char body[256];
      if(record.isDrink()) {
        const auto &drink=record.drink;
        snprintf(body,sizeof body,"{\"event_id\":\"gateway-1:%08lx:%08lx:%08lx\",\"kind\":\"drink\",\"source\":\"measured\",\"volume_ml\":%u}",
          (unsigned long)drink.bootHigh,(unsigned long)drink.bootLow,(unsigned long)drink.sequence,drink.volumeMl);
      } else {
        const auto &packet=record.telemetry;
        char temp[24]; if(packet.centiC==INT16_MIN)strcpy(temp,"null");else snprintf(temp,sizeof temp,"%.2f",packet.centiC/100.0);
        const char *level=packet.level==1?"wet":packet.level==2?"dry":"unknown";
        snprintf(body,sizeof body,"{\"device_id\":\"node-1\",\"session\":%lu,\"seq\":%lu,\"level\":\"%s\",\"temperature_c\":%s,\"tds_adc\":%u,\"source\":\"device\"}",
          (unsigned long)packet.session,(unsigned long)packet.seq,level,temp,packet.adc);
      }
      int result=http.POST((uint8_t*)body,strlen(body));
      if (!record.isDrink() && (result == 200 || result == 201)) readReminder(http);
      http.end();
      if(result==200 || result==201) {
        xSemaphoreTake(lock_,portMAX_DELAY); CloudOutboxRecord head{};
        if(durable_.peek(head) && CloudOutboxRecord::sameId(head,record)) {if(!durable_.pop())++errors_;}
        xSemaphoreGive(lock_); retryMs=1000;
      } else {vTaskDelay(pdMS_TO_TICKS(retryMs+esp_random()%(retryMs/4+1)));retryMs=min(retryMs*2,uint32_t(60000));}
    }
  }
public:
  ReminderSnapshot reminderSnapshot() {
    portENTER_CRITICAL(&reminderLock_);
    const auto snapshot = reminder_;
    portEXIT_CRITICAL(&reminderLock_);
    return snapshot;
  }

  bool begin(bool keepConnected = false, uint32_t scaleStaleMs = 0) {
    if(!KAEW_CLOUD_ENABLED)return false;
    keepConnected_ = keepConnected;
    if(!store_.begin() || !durable_.recover()) {++errors_;return false;}
    lock_=xSemaphoreCreateMutex(); pending_=xQueueCreate(8,sizeof(CloudOutboxRecord)); acknowledgements_=xQueueCreate(8,sizeof(Packet));
    if(!lock_ || !pending_ || !acknowledgements_) {++errors_;return false;}
    scaleStaleMs_ = scaleStaleMs;
    if (scaleStaleMs_) scaleUpdates_ = xQueueCreate(1, sizeof(ScaleUpload));
    // Fail closed if either task fails to start; no UART ACKs then leave the loop.
    TaskHandle_t persistent=nullptr;
    if(xTaskCreatePinnedToCore(persistTask,"kaew-store",4096,this,1,&persistent,0)!=pdPASS) {++errors_;return false;}
    if(xTaskCreatePinnedToCore(networkTask,"kaew-cloud",8192,this,1,nullptr,0)!=pdPASS) {vTaskDelete(persistent);++errors_;return false;}
    if (scaleStaleMs_ && (!scaleUpdates_ ||
        xTaskCreatePinnedToCore(scaleTask, "kaew-scale-cloud", 8192, this, 1, nullptr, 0) != pdPASS)) {
      ++errors_;
    }
    ready_=true; return true;
  }
  bool enabled() const {return KAEW_CLOUD_ENABLED;}
  bool enqueue(const CloudOutboxRecord &record) {
    if(!enabled()) return true;
    if(!ready_ || xQueueSend(pending_, &record, 0)!=pdTRUE) { ++rejected_; return false; }
    return true;
  }
  bool enqueue(const Packet &packet) { return enqueue(CloudOutboxRecord{packet, {}}); }
  bool enqueueDrink(const MeasuredDrink &drink) { return enqueue(CloudOutboxRecord{{}, drink}); }
  void enqueueScale(const ScaleUpload &sample) {
    if (ready_ && scaleUpdates_) xQueueOverwrite(scaleUpdates_, &sample);
  }
  bool takeAck(Packet &p) {return ready_ && xQueueReceive(acknowledgements_,&p,0)==pdTRUE;}
  uint32_t rejected() const {return rejected_.load();}
  uint32_t errors() const {return errors_.load();}
};
