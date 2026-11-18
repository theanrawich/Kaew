#pragma once

#include "speech_upload.h"

constexpr size_t maxReplyWavBytes = speechWavHeaderSize + SpeechCapture::sampleRate * 2 * 15;

inline bool validReplyWav(const uint8_t *header, size_t size) {
  if (!header || size <= speechWavHeaderSize || size > maxReplyWavBytes ||
      (size - speechWavHeaderSize) % 2 != 0) return false;
  uint8_t expected[speechWavHeaderSize];
  writeSpeechWavHeader(expected, size - speechWavHeaderSize);
  return std::memcmp(header, expected, sizeof expected) == 0;
}

inline bool validReplyAudioId(const char *id) {
  if (!id || std::strlen(id) != 32) return false;
  for (size_t i = 0; i < 32; ++i)
    if (!(id[i] >= '0' && id[i] <= '9') && !(id[i] >= 'a' && id[i] <= 'f')) return false;
  return true;
}

class ReminderPlayback {
  char last_[33]{};

 public:
  bool take(const char *id) {
    if (!validReplyAudioId(id) || std::strcmp(last_, id) == 0) return false;
    std::memcpy(last_, id, sizeof last_);
    return true;
  }
};

#ifdef ARDUINO
#include <esp_heap_caps.h>
#include <memory>

namespace speech_detail {
inline bool beginAudioGet(HTTPClient &http, WiFiClientSecure &client, const String &path,
                          const char *token, uint16_t readTimeout) {
  const String base = cloudAudioBase();
  if (!base.length() || !token[0] || WiFi.status() != WL_CONNECTED ||
      time(nullptr) < 1700000000) return false;
  client.setCACert(KAEW_CLOUD_CA);
  client.setHandshakeTimeout(5);
  http.setConnectTimeout(5000);
  http.setTimeout(readTimeout);
  http.setFollowRedirects(HTTPC_DISABLE_FOLLOW_REDIRECTS);
  http.useHTTP10(); // Both endpoints send Content-Length. No chunk decoder or whole-body String.
  if (!http.begin(client, base + path)) return false;
  http.addHeader("Authorization", String("Bearer ") + token);
  return true;
}

inline String fetchReminderId() {
  WiFiClientSecure client;
  HTTPClient http;
  if (!beginAudioGet(http, client, "/api/gateway/reminder", KAEW_CLOUD_TOKEN, 5000) ||
      http.GET() != 200) return {};
  const int size = http.getSize();
  char json[128]{};
  if (size <= 0 || size >= int(sizeof json) ||
      !readResponse(http, reinterpret_cast<uint8_t *>(json), size, millis())) return {};
  cJSON *body = cJSON_Parse(json);
  const cJSON *id = cJSON_GetObjectItemCaseSensitive(body, "reminder_id");
  String result;
  if (cJSON_IsString(id) && validReplyAudioId(id->valuestring)) result = id->valuestring;
  cJSON_Delete(body);
  return result;
}

using ReplyWav = std::unique_ptr<uint8_t, decltype(&heap_caps_free)>;

inline ReplyWav fetchReplyWav(const char *id, const char *token, size_t &size) {
  ReplyWav wav(nullptr, heap_caps_free);
  size = 0;
  if (!validReplyAudioId(id)) return wav;
  WiFiClientSecure client;
  HTTPClient http;
  if (!beginAudioGet(http, client, String("/api/tts/") + id, token, 20000) ||
      http.GET() != 200) return wav;
  const uint32_t start = millis();
  const int length = http.getSize();
  uint8_t header[speechWavHeaderSize];
  if (length <= 0 || size_t(length) > maxReplyWavBytes || size_t(length) <= sizeof header ||
      !readResponse(http, header, sizeof header, start) || !validReplyWav(header, length)) return wav;
  const size_t pcmBytes = length - sizeof header;
  wav.reset(static_cast<uint8_t *>(heap_caps_malloc(pcmBytes, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT)));
  if (wav && readResponse(http, wav.get(), pcmBytes, start)) size = pcmBytes;
  else wav.reset();
  return wav;
}
} // namespace speech_detail
#endif
