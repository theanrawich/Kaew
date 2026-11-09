#pragma once
#include <cmath>
#include <cstdint>
#include <cstring>

struct Calibration { uint32_t version; int32_t zero; float countsPerGram; uint32_t checksum; };
inline uint32_t calibrationChecksum(const Calibration &c) {
  uint32_t bits; std::memcpy(&bits, &c.countsPerGram, sizeof bits);
  uint32_t hash = 2166136261u;
  const uint32_t words[] = {c.version, static_cast<uint32_t>(c.zero), bits};
  for (auto word : words) for (int i = 0; i < 4; ++i) { hash ^= (word >> (8*i)) & 255; hash *= 16777619u; }
  return hash;
}
inline bool validCalibration(const Calibration &c) {
  return c.version == 1 && std::isfinite(c.countsPerGram) && std::fabs(c.countsPerGram) >= 1 &&
    std::fabs(c.countsPerGram) <= 100000 && c.checksum == calibrationChecksum(c);
}
inline bool makeCalibration(int32_t zero, int32_t known, float grams, Calibration &out) {
  if (!std::isfinite(grams) || grams < 10 || grams > 1000) return false;
  Calibration c{1, zero, static_cast<float>(static_cast<int64_t>(known) - zero) / grams, 0};
  c.checksum = calibrationChecksum(c); if (!validCalibration(c)) return false;
  out = c; return true;
}
inline float toGrams(const Calibration &c, int32_t raw) {
  return static_cast<float>(static_cast<int64_t>(raw) - c.zero) / c.countsPerGram;
}
class WeightFilter {
  float samples_[5]{}; unsigned count_ = 0, next_ = 0; bool stable_ = false; float weight_ = 0;
public:
  bool push(float value) {
    if (!std::isfinite(value) || value < -50 || value > 1100) { count_ = next_ = 0; stable_ = false; return false; }
    samples_[next_] = value; next_ = (next_ + 1) % 5; if (count_ < 5) ++count_;
    if (count_ < 5) return false;
    float sorted[5]; std::memcpy(sorted, samples_, sizeof sorted);
    for (int i=1; i<5; ++i) for (int j=i; j>0 && sorted[j]<sorted[j-1]; --j) { float t=sorted[j]; sorted[j]=sorted[j-1]; sorted[j-1]=t; }
    weight_ = sorted[2]; stable_ = sorted[4]-sorted[0] <= 5.0f; return true;
  }
  bool stable() const { return stable_; }
  float weight() const { return weight_; }
};
class CupDetector {
  unsigned count_ = 0; bool present_ = false;
public:
  bool update(bool stable, float grams) {
    if (!stable || !std::isfinite(grams) || grams < 30 || grams > 900) { count_ = 0; return present_ = false; }
    if (count_ < 3) ++count_; return present_ = count_ >= 3;
  }
};
// Only valid for the cup explicitly tared while empty; reset on removal/reboot.
class CupTare {
  bool valid_ = false; float emptyG_ = 0;
public:
  bool set(bool present, bool stable, float grams) {
    if (!present || !stable || !std::isfinite(grams) || grams < 30 || grams > 900) return false;
    emptyG_ = grams; valid_ = true; return true;
  }
  void clear() { valid_ = false; }
  bool volume(bool present, float grams, float &ml) const {
    if (!valid_ || !present || !std::isfinite(grams) || grams < emptyG_ || grams > 1000) return false;
    ml = grams - emptyG_; return true; // 1 g/mL approximation, not a measurement of intake.
  }
};
