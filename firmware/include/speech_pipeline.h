#pragma once

#include <esp_heap_caps.h>
#include <new>
#include "audio_io.h"
#include "speech_upload.h"

class SpeechPipeline {
  static constexpr size_t bufferCount = 4;
  struct Clip {
    uint32_t id;
    size_t samples;
    uint8_t header[speechWavHeaderSize];
    int16_t pcm[SpeechCapture::maxSamples];
  };
  static_assert(offsetof(Clip, pcm) == offsetof(Clip, header) + speechWavHeaderSize,
                "WAV header and little-endian PCM must be contiguous");

  AudioIO &audio_;
  SpeechCapture capture_;
  MicDcBlocker filter_;
  uint32_t nextClipId_ = 0;
  int16_t frame_[SpeechCapture::frameSamples];
  size_t frameSize_ = 0;
  Clip *captureBuffer_ = nullptr;
  QueueHandle_t freeClips_ = nullptr, readyClips_ = nullptr;
  SpeechUpload mode_ = SpeechUpload::Disabled;

  static void uploadTask(void *context) {
    auto &pipeline = *static_cast<SpeechPipeline *>(context);
    for (;;) {
      Clip *clip = nullptr;
      if (xQueueReceive(pipeline.readyClips_, &clip, portMAX_DELAY) != pdTRUE) continue;
      const auto stats = normalizeSpeech(clip->pcm, clip->samples);
      Serial.printf("[clip %lu] peak %ld rms %.1f clipped %u gain %.3fx\n",
                    static_cast<unsigned long>(clip->id), static_cast<long>(stats.peak),
                    stats.rms, static_cast<unsigned>(stats.clipped), stats.gain);
      const size_t pcmBytes = clip->samples * sizeof(int16_t);
      writeSpeechWavHeader(clip->header, pcmBytes);
      // Use the enclosing object representation to span both arrays.
      auto *wav = reinterpret_cast<uint8_t *>(clip) + offsetof(Clip, header);
      speech_detail::sendWav(clip->id, wav, speechWavHeaderSize + pcmBytes, pipeline.mode_);
      xQueueSend(pipeline.freeClips_, &clip, 0);
    }
  }

  static void captureTask(void *context) {
    auto &pipeline = *static_cast<SpeechPipeline *>(context);
    for (;;) pipeline.poll();
  }

  void completeClip(size_t samples) {
    const auto id = static_cast<unsigned long>(++nextClipId_);
    Clip *next = nullptr;
    if (freeClips_ && xQueueReceive(freeClips_, &next, 0) != pdTRUE) {
      Serial.printf("[clip %lu] upload backlog full, dropped\n", id);
      return;
    }
    Serial.printf("[clip %lu] captured %u ms\n", id,
                  static_cast<unsigned>(samples * 1000 / SpeechCapture::sampleRate));
    if (next) {
      captureBuffer_->id = nextClipId_;
      captureBuffer_->samples = samples;
      xQueueSend(readyClips_, &captureBuffer_, 0);
      captureBuffer_ = next;
    }
  }

 public:
  explicit SpeechPipeline(AudioIO &audio) : audio_(audio) {}

  // Call once after I2S setup. The bench test polls from its Arduino loop.
  bool begin(SpeechUpload mode, bool backgroundCapture) {
    mode_ = mode;
    const bool upload = mode != SpeechUpload::Disabled;
    auto *storage = static_cast<uint8_t *>(heap_caps_malloc(
        (upload ? bufferCount : 1) * sizeof(Clip), MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT));
    if (!storage) return false;
    captureBuffer_ = new (storage) Clip;

    TaskHandle_t worker = nullptr;
    bool ready = true;
    if (upload) {
      freeClips_ = xQueueCreate(bufferCount - 1, sizeof(Clip *));
      readyClips_ = xQueueCreate(bufferCount - 1, sizeof(Clip *));
      ready = freeClips_ && readyClips_;
      if (ready) {
        for (size_t i = 1; i < bufferCount; ++i) {
          Clip *clip = new (storage + i * sizeof(Clip)) Clip;
          xQueueSend(freeClips_, &clip, 0);
        }
        ready = xTaskCreatePinnedToCore(uploadTask, "stt_upload", 8192, this, 1,
                                       &worker, 0) == pdPASS;
      }
    }
    if (ready && (!backgroundCapture ||
                  xTaskCreatePinnedToCore(captureTask, "speech_capture", 4096, this, 1,
                                          nullptr, 0) == pdPASS)) return true;

    if (worker) vTaskDelete(worker); // No clips have been enqueued.
    if (readyClips_) vQueueDelete(readyClips_);
    if (freeClips_) vQueueDelete(freeClips_);
    readyClips_ = freeClips_ = nullptr;
    heap_caps_free(storage);
    captureBuffer_ = nullptr;
    return false;
  }

  void poll() {
    if (!captureBuffer_) {
      delay(1000);
      return;
    }
    int32_t raw[256];
    const size_t count = audio_.readMicrophoneRaw(raw, 256, pdMS_TO_TICKS(100));
    if (count == 0) {
      capture_.resetUtterance();
      frameSize_ = 0;
      filter_.reset();
      Serial.println("Microphone read interrupted; discarded partial audio.");
      delay(20);
      return;
    }
    for (size_t i = 0; i < count; ++i) {
      frame_[frameSize_++] = filter_.convert(raw[i]);
      if (frameSize_ != SpeechCapture::frameSamples) continue;
      frameSize_ = 0;
      const bool wasListening = capture_.listening();
      const size_t completed = capture_.push(frame_, captureBuffer_->pcm);
      if (!wasListening && capture_.listening())
        Serial.printf("Listening. Background RMS %.1f\n", capture_.backgroundRms());
      if (completed > 0) completeClip(completed);
    }
  }
};
