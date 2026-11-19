#pragma once

#include "scale_processing.h"

// Display-only fallback. The platform must be empty during the first ten conversions.
class BootTaredScale {
  static constexpr int Window = 10;
  static constexpr float CountsPerGram = 735.7f;
  int32_t samples_[Window]{};
  unsigned count_ = 0, next_ = 0;
  int32_t zero_ = 0;
  bool tared_ = false, stable_ = false, cupPresent_ = false;
  float grams_ = 0;
  CupDetector cup_;

public:
  void resetWindow() {
    count_ = next_ = 0;
    stable_ = cupPresent_ = false;
    cup_ = CupDetector{};
  }

  bool accept(int32_t raw) {
    if (!validScaleRaw(raw)) {
      resetWindow();
      return false;
    }
    samples_[next_] = raw;
    next_ = (next_ + 1) % Window;
    if (count_ < Window) ++count_;
    if (count_ < Window) return false;

    int32_t sum = 0, low = raw, high = raw;
    for (int32_t sample : samples_) {
      sum += sample;
      if (sample < low) low = sample;
      if (sample > high) high = sample;
    }
    const int32_t average = sum / Window;
    if (!tared_) {
      zero_ = average;
      tared_ = true;
      count_ = next_ = 0;
      return false;
    }

    grams_ = (average - zero_) / CountsPerGram;
    if (std::fabs(grams_) < 0.2f) grams_ = 0;
    stable_ = (high - low) / CountsPerGram <= 5.0f;
    cupPresent_ = cup_.update(stable_, grams_);
    return true;
  }

  float grams() const { return grams_; }
  bool stable() const { return stable_; }
  bool cup() const { return cupPresent_; }
};
