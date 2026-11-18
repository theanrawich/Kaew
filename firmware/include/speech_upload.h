#pragma once

#include <cstring>
#include "audio_processing.h"
#include "speech_capture.h"

// INMP441 sends 24-bit left-aligned samples. Convert to true 16-bit scale
// before filtering the mic's DC offset.
class MicDcBlocker {
  float prevIn_ = 0, prevOut_ = 0;

 public:
  int16_t convert(int32_t raw) {
    const float x = static_cast<float>(pcm32to16(raw));
    const float y = x - prevIn_ + 0.995f * prevOut_;
    prevIn_ = x;
    prevOut_ = y;
    const int32_t sample = static_cast<int32_t>(y);
    return static_cast<int16_t>(sample > 32767 ? 32767 : sample < -32768 ? -32768 : sample);
  }

  void reset() { prevIn_ = prevOut_ = 0; }
};

struct SpeechClipStats {
  int32_t peak;
  float rms;
  size_t clipped;
  float gain;
};

inline SpeechClipStats normalizeSpeech(int16_t *pcm, size_t count) {
  int32_t peak = 0;
  uint64_t squares = 0;
  size_t clipped = 0;
  for (size_t i = 0; i < count; ++i) {
    const int32_t sample = pcm[i];
    peak = std::max(peak, sample < 0 ? -sample : sample);
    squares += sample * sample;
    if (sample == INT16_MIN || sample == INT16_MAX) ++clipped;
  }
  const float rms = count ? sqrtf(static_cast<float>(squares) / count) : 0;
  const float gain = std::min(7.0f, 23000.0f / std::max(peak, int32_t{1}));
  for (size_t i = 0; i < count; ++i) pcm[i] = static_cast<int16_t>(pcm[i] * gain);
  return {peak, rms, clipped, gain};
}

constexpr size_t speechWavHeaderSize = 44;

namespace speech_detail {
inline void put16(uint8_t *p, uint16_t value) {
  p[0] = value;
  p[1] = value >> 8;
}

inline void put32(uint8_t *p, uint32_t value) {
  put16(p, value);
  put16(p + 2, value >> 16);
}
} // namespace speech_detail

inline void writeSpeechWavHeader(uint8_t *wav, size_t pcmBytes) {
  using speech_detail::put16;
  using speech_detail::put32;
  constexpr uint32_t rate = SpeechCapture::sampleRate;
  std::memset(wav, 0, speechWavHeaderSize);
  std::memcpy(wav, "RIFF", 4); put32(wav + 4, speechWavHeaderSize + pcmBytes - 8);
  std::memcpy(wav + 8, "WAVEfmt ", 8); put32(wav + 16, 16);
  put16(wav + 20, 1); put16(wav + 22, 1);
  put32(wav + 24, rate); put32(wav + 28, rate * 2);
  put16(wav + 32, 2); put16(wav + 34, 16);
  std::memcpy(wav + 36, "data", 4); put32(wav + 40, pcmBytes);
}

#ifdef ARDUINO
#include <Arduino.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <cJSON.h>
#include <time.h>
#include "cloud_config.h"

enum class SpeechUpload { Disabled, Transcript, Command };

namespace speech_detail {
// A server response must never echo local credentials onto the console.
inline void printSafe(String value) {
  const char *secrets[] = {KAEW_ADMIN_TOKEN, KAEW_CLOUD_TOKEN,
                           KAEW_WIFI_PASSWORD, KAEW_WIFI_SSID};
  for (const char *secret : secrets)
    if (*secret) value.replace(secret, "[redacted]");
  value.replace("\r", " ");
  value.replace("\n", " ");
  Serial.println(value);
}

inline void logCommand(const String &label, const cJSON *command) {
  const auto *intent = cJSON_GetObjectItemCaseSensitive(command, "intent");
  const auto *executed = cJSON_GetObjectItemCaseSensitive(command, "executed");
  const auto *reply = cJSON_GetObjectItemCaseSensitive(command, "reply");
  const auto *error = cJSON_GetObjectItemCaseSensitive(command, "error");
  if (cJSON_IsString(intent) && cJSON_IsBool(executed) && cJSON_IsString(reply)) {
    printSafe(label + "command: " + intent->valuestring +
              (cJSON_IsTrue(executed) ? " executed=true " : " executed=false ") + reply->valuestring);
  } else if (cJSON_IsString(error)) {
    printSafe(label + "command error: " + error->valuestring);
  } else {
    Serial.println(label + "STT response missing a valid command.");
  }
}

inline void sendWav(uint32_t id, uint8_t *wav, size_t size, SpeechUpload mode) {
  constexpr uint32_t timeoutMs = 20000;
  const String label = String("[clip ") + id + "] ";
  const bool standalone = mode == SpeechUpload::Transcript;
  if (!KAEW_ADMIN_TOKEN[0]) {
    Serial.println(label + "KAEW_ADMIN_TOKEN is missing or empty; skipping STT.");
    return;
  }
  String base(KAEW_CLOUD_URL);
  if (!base.startsWith("https://") || !KAEW_CLOUD_CA[0] || !KAEW_WIFI_SSID[0]) {
    Serial.println(label + "STT requires HTTPS KAEW_CLOUD_URL, KAEW_CLOUD_CA and WiFi configuration.");
    return;
  }
  int path = base.indexOf('/', 8);
  if (path >= 0) base.remove(path);
  // Reject ambiguous authorities rather than forwarding the admin token elsewhere.
  if (base.length() <= 8 || base.indexOf('@') >= 0 || base.indexOf('?') >= 0 ||
      base.indexOf('#') >= 0) {
    Serial.println(label + "Invalid STT base URL.");
    return;
  }
  Serial.println(label + "sending...");
  if (WiFi.status() != WL_CONNECTED) {
    if (standalone) {
      WiFi.mode(WIFI_STA);
      WiFi.begin(KAEW_WIFI_SSID, KAEW_WIFI_PASSWORD);
    }
    const uint32_t start = millis();
    while (WiFi.status() != WL_CONNECTED && millis() - start < timeoutMs) delay(20);
    if (WiFi.status() != WL_CONNECTED) {
      Serial.println(label + "WiFi connection timed out.");
      return;
    }
  }
  if (time(nullptr) < 1700000000) {
    if (standalone) configTime(0, 0, "pool.ntp.org", "time.google.com");
    const uint32_t start = millis();
    while (time(nullptr) < 1700000000 && millis() - start < timeoutMs) delay(20);
    if (time(nullptr) < 1700000000) {
      Serial.println(label + "TLS clock synchronization timed out.");
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
  if (!http.begin(client, base + (standalone ? "/api/stt" : "/api/stt?command=1"))) {
    Serial.println(label + "Unable to initialize STT request.");
    return;
  }
  http.addHeader("Authorization", String("Bearer ") + KAEW_ADMIN_TOKEN);
  http.addHeader("Content-Type", "audio/wav");
  int code = http.POST(wav, size);
  String body = http.getString();
  http.end();
  cJSON *json = cJSON_Parse(body.c_str());
  const cJSON *text = json ? cJSON_GetObjectItemCaseSensitive(json, "text") : nullptr;
  if (code >= 200 && code < 300 && cJSON_IsString(text)) {
    printSafe(label + "text: " + text->valuestring);
    if (!standalone) logCommand(label, cJSON_GetObjectItemCaseSensitive(json, "command"));
  } else {
    printSafe(label + "HTTP " + code + " " + body);
  }
  cJSON_Delete(json);
}
} // namespace speech_detail
#endif
