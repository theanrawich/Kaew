#pragma once

#include <esp_heap_caps.h>
#include <new>
#include <atomic>
#include "audio_io.h"
#include "speech_playback.h"

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
  bool pollReminders_ = false;
  SemaphoreHandle_t microphone_ = nullptr;
  std::atomic<bool> pauseCapture_{false};
  ReminderPlayback reminder_;

  void playRemote(const String &id, const char *token) {
    if (!validReplyAudioId(id.c_str())) return;
    size_t bytes = 0;
    auto wav = speech_detail::fetchReplyWav(id.c_str(), token, bytes);
    if (!wav) {
      Serial.println("Speech audio unavailable.");
      return;
    }
    pauseCapture_ = true;
    if (xSemaphoreTake(microphone_, pdMS_TO_TICKS(250)) != pdTRUE) {
      pauseCapture_ = false;
      Serial.println("Microphone pause timed out; skipped speaker playback.");
      return;
    }
    capture_.resetUtterance();
    frameSize_ = 0;
    filter_.reset();
    if (!audio_.play(wav.get(), bytes)) Serial.println("Speaker write failed.");

    // The microphone keeps its clock during playback. Discard all buffered
    // RX DMA frames and allow a short quiet period before listening again.
    int32_t discard[256];
    for (size_t i = 0; i < 10; ++i)
      audio_.readMicrophoneRaw(discard, 256, pdMS_TO_TICKS(30));
    xSemaphoreGive(microphone_);
    pauseCapture_ = false;
  }

  static void uploadTask(void *context) {
    auto &pipeline = *static_cast<SpeechPipeline *>(context);
    constexpr uint32_t reminderPollMs = 5000;
    uint32_t lastPoll = millis();
    for (;;) {
      if (pipeline.pollReminders_ && millis() - lastPoll >= reminderPollMs) {
        const String id = speech_detail::fetchReminderId();
        // Attempt once per observed ID, including when synthesis is down.
        if (pipeline.reminder_.take(id.c_str()))
          pipeline.playRemote(id, KAEW_CLOUD_TOKEN);
        lastPoll = millis();
      }
      Clip *clip = nullptr;
      const uint32_t elapsed = millis() - lastPoll;
      const TickType_t wait = pipeline.pollReminders_
          ? pdMS_TO_TICKS(elapsed < reminderPollMs ? reminderPollMs - elapsed : 0)
          : portMAX_DELAY;
      if (xQueueReceive(pipeline.readyClips_, &clip, wait) != pdTRUE) continue;
      const auto stats = normalizeSpeech(clip->pcm, clip->samples);
      Serial.printf("[clip %lu] peak %ld rms %.1f clipped %u gain %.3fx\n",
                    static_cast<unsigned long>(clip->id), static_cast<long>(stats.peak),
                    stats.rms, static_cast<unsigned>(stats.clipped), stats.gain);
      const size_t pcmBytes = clip->samples * sizeof(int16_t);
      writeSpeechWavHeader(clip->header, pcmBytes);
      // Use the enclosing object representation to span both arrays.
      auto *wav = reinterpret_cast<uint8_t *>(clip) + offsetof(Clip, header);
      String replyAudioId;
      speech_detail::sendWav(clip->id, wav, speechWavHeaderSize + pcmBytes,
                             pipeline.mode_, replyAudioId);
      xQueueSend(pipeline.freeClips_, &clip, 0);
      if (pipeline.mode_ == SpeechUpload::Command)
        pipeline.playRemote(replyAudioId, KAEW_ADMIN_TOKEN);
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
  bool begin(SpeechUpload mode, bool backgroundCapture, bool pollReminders = false) {
    mode_ = mode;
    pollReminders_ = pollReminders;
    const bool upload = mode != SpeechUpload::Disabled;
    auto *storage = static_cast<uint8_t *>(heap_caps_malloc(
        (upload ? bufferCount : 1) * sizeof(Clip), MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT));
    if (!storage) return false;
    captureBuffer_ = new (storage) Clip;

    TaskHandle_t worker = nullptr;
    const bool speaker = mode == SpeechUpload::Command || pollReminders_;
    if (speaker) microphone_ = xSemaphoreCreateMutex();
    bool ready = !speaker || microphone_;
    if (ready && (upload || pollReminders_)) {
      readyClips_ = xQueueCreate(bufferCount - 1, sizeof(Clip *));
      if (upload) freeClips_ = xQueueCreate(bufferCount - 1, sizeof(Clip *));
      ready = readyClips_ && (!upload || freeClips_);
      if (ready) {
        if (upload) {
          for (size_t i = 1; i < bufferCount; ++i) {
            Clip *clip = new (storage + i * sizeof(Clip)) Clip;
            xQueueSend(freeClips_, &clip, 0);
          }
        }
        ready = xTaskCreatePinnedToCore(uploadTask, "speech_worker", 10240, this, 1,
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
    if (microphone_) vSemaphoreDelete(microphone_);
    microphone_ = nullptr;
    heap_caps_free(storage);
    captureBuffer_ = nullptr;
    return false;
  }

  void poll() {
    if (pauseCapture_ || (microphone_ && xSemaphoreTake(microphone_, 0) != pdTRUE)) {
      delay(20);
      return;
    }
    captureFrame();
    if (microphone_) xSemaphoreGive(microphone_);
  }

 private:
  void captureFrame() {
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
