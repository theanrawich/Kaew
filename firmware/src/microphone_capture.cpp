#include "microphone_capture.h"
#include <Arduino.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <driver/i2s.h>
#include <esp_heap_caps.h>
#include <time.h>
#include <cmath>
#include <new>
#include "render_ca.h"
#if __has_include("gateway_wifi.h")
#include "gateway_wifi.h"
#endif
#ifndef KAEW_DEVICE_TOKEN
#define KAEW_DEVICE_TOKEN ""
#endif
#include "audio_processing.h"
#include "speech_capture.h"

namespace {
constexpr const char *uploadToken = KAEW_DEVICE_TOKEN;

constexpr uint32_t sampleRate = SpeechCapture::sampleRate;
constexpr size_t wavHeaderSize = 44;
constexpr uint32_t timeoutMs = 20000;
constexpr size_t bufferCount = 4;
struct Clip {
  uint32_t id;
  size_t samples;
  uint8_t header[wavHeaderSize];
  int16_t pcm[SpeechCapture::maxSamples];
};
static_assert(offsetof(Clip, pcm) == offsetof(Clip, header) + wavHeaderSize,
              "WAV header and little-endian PCM must be contiguous");

QueueHandle_t freeClips = nullptr;
QueueHandle_t readyClips = nullptr;
Clip *captureBuffer = nullptr;
SpeechCapture speechCapture;
uint32_t nextClipId = 0;
int16_t frame[SpeechCapture::frameSamples];
size_t frameSize = 0;

// INMP441 sends 24-bit left-aligned samples: >>16 gives true 16-bit scale
// (the old >>14 was 4x too hot and clipped). A one-pole DC blocker removes the
// mic's DC offset, which otherwise reads as constant "noise".
float dcPrevIn = 0, dcPrevOut = 0;
int16_t removeDc(int16_t sampleIn) {
  float x = static_cast<float>(sampleIn);
  float y = x - dcPrevIn + 0.995f * dcPrevOut;
  dcPrevIn = x; dcPrevOut = y;
  int32_t sample = static_cast<int32_t>(y);
  return static_cast<int16_t>(sample > 32767 ? 32767 : sample < -32768 ? -32768 : sample);
}

void normalize(Clip &clip) {
  int32_t peak = 0;
  uint64_t squares = 0;
  size_t clipped = 0;
  for (size_t i = 0; i < clip.samples; ++i) {
    const int32_t sample = clip.pcm[i];
    peak = max(peak, abs(sample));
    squares += sample * sample;
    if (sample == INT16_MIN || sample == INT16_MAX) ++clipped;
  }
  const float rms = sqrtf(static_cast<float>(squares) / clip.samples);
  const float gain = min(7.0f, 23000.0f / max(peak, int32_t{1}));
  Serial.printf("[clip %lu] peak %ld rms %.1f clipped %u gain %.3fx\n",
                static_cast<unsigned long>(clip.id), static_cast<long>(peak),
                rms, static_cast<unsigned>(clipped), gain);
  // The target peak keeps all normalized samples within the int16_t range.
  for (size_t i = 0; i < clip.samples; ++i)
    clip.pcm[i] = static_cast<int16_t>(clip.pcm[i] * gain);
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
void wavHeader(uint8_t *wav, size_t pcmBytes) {
  memset(wav, 0, wavHeaderSize);
  memcpy(wav, "RIFF", 4); put32(wav + 4, wavHeaderSize + pcmBytes - 8);
  memcpy(wav + 8, "WAVEfmt ", 8); put32(wav + 16, 16);
  put16(wav + 20, 1); put16(wav + 22, 1);
  put32(wav + 24, sampleRate); put32(wav + 28, sampleRate * 2);
  put16(wav + 32, 2); put16(wav + 34, 16);
  memcpy(wav + 36, "data", 4); put32(wav + 40, pcmBytes);
}

void sendWav(Clip &clip) {
  const String label = String("[clip ") + clip.id + "] ";
  const size_t pcmBytes = clip.samples * sizeof(int16_t);
  wavHeader(clip.header, pcmBytes);
  // Use the enclosing object representation so the payload spans both arrays.
  auto *wav = reinterpret_cast<uint8_t *>(&clip) + offsetof(Clip, header);
  constexpr char endpoint[] = "https://kaew-cloud.onrender.com/api/stt/typhoon";
  Serial.println(label + "sending...");
  if (WiFi.status() != WL_CONNECTED) {
    const uint32_t start = millis();
    while (WiFi.status() != WL_CONNECTED && millis() - start < timeoutMs) delay(20);
    if (WiFi.status() != WL_CONNECTED) {
      Serial.println(label + "WiFi connection timed out.");
      return;
    }
  }
  if (time(nullptr) < 1700000000) {
    const uint32_t start = millis();
    while (time(nullptr) < 1700000000 && millis() - start < timeoutMs) delay(20);
    if (time(nullptr) < 1700000000) {
      Serial.println(label + "TLS clock synchronization timed out.");
      return;
    }
  }
  WiFiClientSecure client;
  client.setCACert(renderCa);
  client.setHandshakeTimeout(20);
  HTTPClient http;
  http.setConnectTimeout(timeoutMs);
  http.setTimeout(65000);  // Cloud allows 60 s for Typhoon.
  http.setFollowRedirects(HTTPC_DISABLE_FOLLOW_REDIRECTS);
  if (!http.begin(client, endpoint)) {
    Serial.println(label + "Unable to initialize STT request.");
    return;
  }
  http.addHeader("Authorization", String("Bearer ") + uploadToken);
  http.addHeader("Content-Type", "audio/wav");
  int code = http.POST(wav, wavHeaderSize + pcmBytes);
  http.end();
  Serial.printf("[clip %lu] upload HTTP result: %d\n", static_cast<unsigned long>(clip.id), code);
}


void uploadClips(void *) {
  for (;;) {
    Clip *clip = nullptr;
    if (xQueueReceive(readyClips, &clip, portMAX_DELAY) == pdTRUE) {
      normalize(*clip);
      sendWav(*clip);
      xQueueSend(freeClips, &clip, 0);
    }
  }
}

void queueClip(size_t samples) {
  captureBuffer->id = ++nextClipId;
  captureBuffer->samples = samples;
  Clip *next = nullptr;
  if (xQueueReceive(freeClips, &next, 0) != pdTRUE) {
    Serial.printf("[clip %lu] upload backlog full, dropped\n",
                  static_cast<unsigned long>(captureBuffer->id));
    return;
  }
  Serial.printf("[clip %lu] captured %u ms\n",
                static_cast<unsigned long>(captureBuffer->id),
                static_cast<unsigned>(samples * 1000 / sampleRate));
  xQueueSend(readyClips, &captureBuffer, 0);
  captureBuffer = next;
}

void acquireMicrophone(void *) {
  for (;;) readMicrophoneCapture();
}
} // namespace

bool startMicrophoneCapture() {
  if (!uploadToken[0]) return false;
  auto *storage = static_cast<uint8_t *>(
      heap_caps_malloc(bufferCount * sizeof(Clip), MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT));
  freeClips = xQueueCreate(bufferCount, sizeof(Clip *));
  readyClips = xQueueCreate(bufferCount - 1, sizeof(Clip *));
  if (storage && freeClips && readyClips) {
    for (size_t i = 0; i < bufferCount; ++i) {
      Clip *clip = new (storage + i * sizeof(Clip)) Clip;
      if (i == 0) captureBuffer = clip;
      else xQueueSend(freeClips, &clip, 0);
    }
    if (beginMic()) {
      TaskHandle_t uploader = nullptr;
      if (xTaskCreatePinnedToCore(uploadClips, "stt_upload", 8192, nullptr, 1,
                                  &uploader, 0) == pdPASS) {
        if (xTaskCreatePinnedToCore(acquireMicrophone, "kaew-mic", 4096, nullptr, 1,
                                    nullptr, 0) == pdPASS) {
          Serial.println("Calibrating microphone background noise.");
          return true;
        }
        vTaskDelete(uploader);
      }
      i2s_driver_uninstall(I2S_NUM_0);
    }
  }
  if (readyClips) vQueueDelete(readyClips);
  if (freeClips) vQueueDelete(freeClips);
  if (storage) heap_caps_free(storage);
  captureBuffer = nullptr;
  return false;
}
void readMicrophoneCapture() {
  if (!captureBuffer) {
    delay(1000);
    return;
  }
  int32_t raw[256];
  size_t bytes = 0;
  if (i2s_read(I2S_NUM_0, raw, sizeof(raw), &bytes, pdMS_TO_TICKS(100)) != ESP_OK ||
      bytes == 0 || bytes % sizeof(raw[0]) != 0) {
    speechCapture.resetUtterance();
    frameSize = 0;
    dcPrevIn = dcPrevOut = 0;
    Serial.println("Microphone read interrupted; discarded partial audio.");
    delay(20);
    return;
  }

  for (size_t i = 0; i < bytes / sizeof(raw[0]); ++i) {
    const int16_t pcm = pcm32to16(raw[i]);
    frame[frameSize++] = removeDc(pcm);
    if (frameSize != SpeechCapture::frameSamples) continue;
    frameSize = 0;
    const bool wasListening = speechCapture.listening();
    const size_t completed = speechCapture.push(frame, captureBuffer->pcm);
    if (!wasListening && speechCapture.listening())
      Serial.printf("Listening. Background RMS %.1f\n", speechCapture.backgroundRms());
    if (completed > 0) queueClip(completed);
  }
}
