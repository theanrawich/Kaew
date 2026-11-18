#pragma once
#include <cmath>
#include <cstdint>

// Calibrated gross grams, before cup tare. A confirmed lift must expose the
// unloaded platform, so a bump or a partial lift cannot start a drink cycle.
class DrinkDetector {
  static constexpr float unloadedG = 15;
  static constexpr float cupMinG = 30;
  static constexpr float stableSpreadG = 5;
  static constexpr uint32_t stableMs = 600, liftMs = 200;
  enum class State { Baseline, OnScale, Lifted };
  State state_ = State::Baseline;
  float before_ = 0, low_ = 0, high_ = 0;
  uint32_t since_ = 0, last_ = 0;
  bool stableWindow_ = false, liftWindow_ = false, sampled_ = false;

  bool stable(float grams, uint32_t now) {
    if (!stableWindow_ || grams < high_ - stableSpreadG || grams > low_ + stableSpreadG) {
      low_ = high_ = grams;
      since_ = now;
      stableWindow_ = true;
    }
    if (grams < low_) low_ = grams;
    if (grams > high_) high_ = grams;
    return uint32_t(now - since_) >= stableMs;
  }

public:
  void reset() { *this = DrinkDetector{}; }

  unsigned update(float grams, uint32_t now, uint32_t maxGapMs = 500) {
    if (sampled_ && uint32_t(now - last_) >= maxGapMs) reset();
    if (!std::isfinite(grams) || grams < -50 || grams > 1100) {
      reset();
      return 0;
    }
    sampled_ = true;
    last_ = now;

    if (grams < cupMinG) {
      stableWindow_ = false;
      if (state_ == State::OnScale && grams <= unloadedG) {
        if (!liftWindow_) { liftWindow_ = true; since_ = now; }
        if (uint32_t(now - since_) >= liftMs) state_ = State::Lifted;
      } else {
        liftWindow_ = false;
      }
      return 0;
    }

    liftWindow_ = false;
    if (!stable(grams, now)) return 0;
    const float settled = (low_ + high_) / 2;
    const float loss = before_ - settled;
    const bool drank = state_ == State::Lifted && loss >= 10 && loss <= 1000;
    before_ = settled;
    state_ = State::OnScale;
    return drank ? static_cast<unsigned>(std::lround(loss)) : 0;
  }
};
