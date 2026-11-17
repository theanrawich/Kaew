#pragma once

#include <algorithm>
#include <array>
#include <cmath>
#include <cstddef>
#include <cstdint>

// Energy-based speech segmentation for 16 kHz mono PCM. Feed complete 20 ms
// frames and keep the output buffer until push returns a completed sample count.
class SpeechCapture {
 public:
  static constexpr uint32_t sampleRate = 16000;
  static constexpr size_t frameSamples = sampleRate / 50;
  static constexpr size_t maxSamples = sampleRate * 8;

  size_t push(const int16_t *frame, int16_t *output) {
    if (warmupFrames_ > 0) {
      --warmupFrames_;
      return 0;
    }

    uint64_t squares = 0;
    for (size_t i = 0; i < frameSamples; ++i) {
      const int32_t sample = frame[i];
      squares += sample * sample;
    }
    const float power = static_cast<float>(squares) / frameSamples;
    if (baselineFrames_ > 0) {
      noisePower_ += (power - noisePower_) / (startupFrames + 1 - baselineFrames_);
      --baselineFrames_;
      return 0;
    }

    const bool audible = power >= std::fmax(stopFloorPower, noisePower_ * stopNoiseRatioSquared);
    if (continuing_) {
      continuing_ = false;
      if (audible) {
        std::copy_n(frame, frameSamples, output);
        captured_ = frameSamples;
        minSpeechPower_ = maxSpeechPower_ = power;
        return 0;
      }
    }
    if (captured_ > 0) {
      std::copy_n(frame, frameSamples, output + captured_);
      captured_ += frameSamples;
      quietFrames_ = audible ? 0 : quietFrames_ + 1;
      minSpeechPower_ = std::fmin(minSpeechPower_, power);
      maxSpeechPower_ = std::fmax(maxSpeechPower_, power);
      if (quietFrames_ == endFrames || captured_ == maxSamples) {
        const size_t completed = captured_;
        const bool reachedLimitWhileAudible = completed == maxSamples && audible;
        // A step up in steady background can otherwise trigger indefinitely.
        const bool steadyBackground = reachedLimitWhileAudible &&
                                      maxSpeechPower_ <= minSpeechPower_ * 1.5f;
        if (steadyBackground) noisePower_ = minSpeechPower_;
        resetUtterance();
        continuing_ = reachedLimitWhileAudible && !steadyBackground;
        return completed;
      }
      return 0;
    }

    std::copy_n(frame, frameSamples, history_[historyNext_].begin());
    historyNext_ = (historyNext_ + 1) % historyFrames;
    if (historySize_ < historyFrames) ++historySize_;
    if (power < std::fmax(startFloorPower, noisePower_ * startNoiseRatioSquared)) {
      onsetFrames_ = 0;
      // Adapt during background frames and freeze the estimate during speech.
      noisePower_ += (power - noisePower_) * 0.02f;
      return 0;
    }
    if (++onsetFrames_ < startFrames) return 0;

    minSpeechPower_ = maxSpeechPower_ = power;
    size_t oldest = (historyNext_ + historyFrames - historySize_) % historyFrames;
    for (size_t i = 0; i < historySize_; ++i) {
      std::copy_n(history_[oldest].begin(), frameSamples, output + captured_);
      captured_ += frameSamples;
      oldest = (oldest + 1) % historyFrames;
    }
    return 0;
  }

  bool listening() const { return warmupFrames_ == 0 && baselineFrames_ == 0; }
  float backgroundRms() const { return std::sqrt(noisePower_); }

  void resetUtterance() {
    captured_ = historySize_ = historyNext_ = onsetFrames_ = quietFrames_ = 0;
    continuing_ = false;
  }

 private:
  static constexpr size_t startFrames = 3;
  static constexpr size_t historyFrames = 15;
  static constexpr size_t endFrames = 35;
  static constexpr size_t startupFrames = 25;
  static constexpr float startFloorPower = 150.0f * 150.0f;
  static constexpr float stopFloorPower = 90.0f * 90.0f;
  static constexpr float startNoiseRatioSquared = 2.5f * 2.5f;
  static constexpr float stopNoiseRatioSquared = 1.6f * 1.6f;

  std::array<std::array<int16_t, frameSamples>, historyFrames> history_{};
  size_t historyNext_ = 0;
  size_t historySize_ = 0;
  size_t captured_ = 0;
  size_t onsetFrames_ = 0;
  size_t quietFrames_ = 0;
  size_t warmupFrames_ = startupFrames;
  size_t baselineFrames_ = startupFrames;
  float noisePower_ = 0;
  float minSpeechPower_ = 0;
  float maxSpeechPower_ = 0;
  bool continuing_ = false;
};
