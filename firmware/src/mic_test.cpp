// Standalone bench test: no gateway, actuator or speaker initialization.
#include <Arduino.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <driver/i2s.h>
#include <esp_heap_caps.h>
#include <cJSON.h>
#include <time.h>
#include "cloud_config.h"

#ifndef KAEW_ADMIN_TOKEN
#define KAEW_ADMIN_TOKEN ""
#endif

namespace {
constexpr uint32_t sampleRate = 16000;
constexpr uint32_t clipSeconds = 5;
constexpr size_t sampleCount = clipSeconds * sampleRate;
constexpr size_t wavSize = 44 + sampleCount * sizeof(int16_t);
constexpr uint32_t captureTimeoutMs = clipSeconds * 1000 + 2000;
constexpr uint32_t timeoutMs = 20000;
bool micReady = false;

// INMP441 sends 24-bit left-aligned samples: >>16 gives true 16-bit scale
// (the old >>14 was 4x too hot and clipped). A one-pole DC blocker removes the
// mic's DC offset, which otherwise reads as constant "noise".
float dcPrevIn = 0, dcPrevOut = 0;
void resetDc() { dcPrevIn = dcPrevOut = 0; }
int16_t toPcm(int32_t raw) {
  float x = static_cast<float>(raw >> 16);
  float y = x - dcPrevIn + 0.995f * dcPrevOut;
  dcPrevIn = x; dcPrevOut = y;
  int32_t sample = static_cast<int32_t>(y);
  return static_cast<int16_t>(sample > 32767 ? 32767 : sample < -32768 ? -32768 : sample);
}

// Scale the finished clip so its peak sits near 70% full scale (max 8x gain),
// so quiet speech is audible to STT without clipping loud speech.
void normalize(uint8_t *pcm, size_t count) {
  int32_t peak = 0;
  for (size_t i = 0; i < count; ++i) {
    int16_t v = static_cast<int16_t>(pcm[2 * i] | (pcm[2 * i + 1] << 8));
    peak = max(peak, abs(static_cast<int32_t>(v)));
  }
  if (peak < 64) return;
  float gain = min(8.0f, 23000.0f / peak);
  for (size_t i = 0; i < count; ++i) {
    int16_t v = static_cast<int16_t>(pcm[2 * i] | (pcm[2 * i + 1] << 8));
    int32_t o = static_cast<int32_t>(v * gain);
    o = o > 32767 ? 32767 : o < -32768 ? -32768 : o;
    pcm[2 * i] = o & 0xff; pcm[2 * i + 1] = (o >> 8) & 0xff;
  }
  Serial.printf("peak %ld gain %.1fx\n", static_cast<long>(peak), gain);
}

// A server error must never echo local credentials onto the console.
void printSafe(String value) {
  const char *secrets[] = {KAEW_ADMIN_TOKEN, KAEW_CLOUD_TOKEN,
                           KAEW_WIFI_PASSWORD, KAEW_WIFI_SSID};
  for (const char *secret : secrets)
    if (*secret) value.replace(secret, "[redacted]");
  value.replace("\r", " ");
  value.replace("\n", " ");
  Serial.println(value);
}

bool beginMic() {
  i2s_config_t config{};
  config.mode = static_cast<i2s_mode_t>(I2S_MODE_MASTER | I2S_MODE_RX);
  config.sample_rate = sampleRate;
  config.bits_per_sample = I2S_BITS_PER_SAMPLE_32BIT;
  config.channel_format = I2S_CHANNEL_FMT_ONLY_LEFT;
  config.communication_format = I2S_COMM_FORMAT_STAND_I2S;
  config.intr_alloc_flags = ESP_INTR_FLAG_LEVEL1;
  config.dma_buf_count = 4;
  config.dma_buf_len = 256;
  if (i2s_driver_install(I2S_NUM_0, &config, 0, nullptr) != ESP_OK) return false;
  i2s_pin_config_t pins{};
  pins.mck_io_num = I2S_PIN_NO_CHANGE;
  pins.bck_io_num = 7;
  pins.ws_io_num = 8;
  pins.data_out_num = I2S_PIN_NO_CHANGE;
  pins.data_in_num = 6;
  if (i2s_set_pin(I2S_NUM_0, &pins) == ESP_OK) return true;
  i2s_driver_uninstall(I2S_NUM_0);
  return false;
}

void put16(uint8_t *p, uint16_t value) {
  p[0] = value; p[1] = value >> 8;
}
void put32(uint8_t *p, uint32_t value) {
  put16(p, value); put16(p + 2, value >> 16);
}
void wavHeader(uint8_t *wav) {
  memset(wav, 0, 44);
  memcpy(wav, "RIFF", 4); put32(wav + 4, wavSize - 8);
  memcpy(wav + 8, "WAVEfmt ", 8); put32(wav + 16, 16);
  put16(wav + 20, 1); put16(wav + 22, 1);
  put32(wav + 24, sampleRate); put32(wav + 28, sampleRate * 2);
  put16(wav + 32, 2); put16(wav + 34, 16);
  memcpy(wav + 36, "data", 4); put32(wav + 40, sampleCount * 2);
}

void sendWav(uint8_t *wav) {
  if (!KAEW_ADMIN_TOKEN[0]) {
    Serial.println("KAEW_ADMIN_TOKEN is missing or empty; skipping STT.");
    return;
  }
  String base(KAEW_CLOUD_URL);
  if (!base.startsWith("https://") || !KAEW_CLOUD_CA[0] || !KAEW_WIFI_SSID[0]) {
    Serial.println("STT requires HTTPS KAEW_CLOUD_URL, KAEW_CLOUD_CA and WiFi configuration.");
    return;
  }
  int path = base.indexOf('/', 8);
  if (path >= 0) base.remove(path);
  // Reject ambiguous authorities rather than forwarding the admin token elsewhere.
  if (base.length() <= 8 || base.indexOf('@') >= 0 || base.indexOf('?') >= 0 ||
      base.indexOf('#') >= 0) {
    Serial.println("Invalid STT base URL.");
    return;
  }
  Serial.println("sending...");
  if (WiFi.status() != WL_CONNECTED) {
    WiFi.mode(WIFI_STA);
    WiFi.begin(KAEW_WIFI_SSID, KAEW_WIFI_PASSWORD);
    const uint32_t start = millis();
    while (WiFi.status() != WL_CONNECTED && millis() - start < timeoutMs) delay(20);
    if (WiFi.status() != WL_CONNECTED) {
      Serial.println("WiFi connection timed out.");
      return;
    }
  }
  if (time(nullptr) < 1700000000) {
    configTime(0, 0, "pool.ntp.org", "time.google.com");
    const uint32_t start = millis();
    while (time(nullptr) < 1700000000 && millis() - start < timeoutMs) delay(20);
    if (time(nullptr) < 1700000000) {
      Serial.println("TLS clock synchronization timed out.");
      return;
    }
  }
  WiFiClientSecure client;
  client.setCACert(KAEW_CLOUD_CA);
  client.setTimeout(timeoutMs);
  client.setHandshakeTimeout(20);
  HTTPClient http;
  http.setConnectTimeout(timeoutMs);
  http.setTimeout(timeoutMs);
  http.setFollowRedirects(HTTPC_DISABLE_FOLLOW_REDIRECTS);
  if (!http.begin(client, base + "/api/stt")) {
    Serial.println("Unable to initialize STT request.");
    return;
  }
  http.addHeader("Authorization", String("Bearer ") + KAEW_ADMIN_TOKEN);
  http.addHeader("Content-Type", "audio/wav");
  int code = http.POST(wav, wavSize);
  String body = http.getString();
  http.end();
  cJSON *json = cJSON_Parse(body.c_str());
  const cJSON *text = json ? cJSON_GetObjectItemCaseSensitive(json, "text") : nullptr;
  if (code >= 200 && code < 300 && cJSON_IsString(text)) {
    printSafe(String("text: ") + text->valuestring);
  } else {
    printSafe(String("HTTP ") + code + " " + body);
  }
  cJSON_Delete(json);
}

void recordAndSend() {
  uint8_t *wav = static_cast<uint8_t *>(heap_caps_malloc(wavSize, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT));
  if (!wav) {
    Serial.println("PSRAM allocation failed.");
    delay(1000);
    return;
  }
  wavHeader(wav);
  Serial.printf("recording %lus...\n", static_cast<unsigned long>(clipSeconds));
  // Discard samples queued while the previous clip was being uploaded.
  int32_t raw[256];
  size_t bytes = 0;
  do {
    bytes = 0;
    i2s_read(I2S_NUM_0, raw, sizeof(raw), &bytes, 0);
  } while (bytes);
  size_t captured = 0;
  resetDc();
  const uint32_t start = millis();
  while (captured < sampleCount && millis() - start < captureTimeoutMs) {
    size_t wanted = min(size_t(256), sampleCount - captured);
    bytes = 0;
    if (i2s_read(I2S_NUM_0, raw, wanted * sizeof(int32_t), &bytes, pdMS_TO_TICKS(100)) != ESP_OK) break;
    for (size_t i = 0; i < bytes / sizeof(int32_t); ++i)
      put16(wav + 44 + 2 * captured++, static_cast<uint16_t>(toPcm(raw[i])));
  }
  if (captured == sampleCount) { normalize(wav + 44, captured); sendWav(wav); }
  else {
    Serial.println("Microphone capture incomplete; skipping STT.");
    delay(1000);
  }
  heap_caps_free(wav);
}
} // namespace

void setup() {
  Serial.begin(115200);
  micReady = beginMic();
  if (!micReady) Serial.println("Microphone initialization failed.");
}

void loop() {
  if (micReady) recordAndSend();
  else delay(1000);
}
