#pragma once
#include <cmath>
#include <cstdint>
#include <cstdio>

struct ScaleUpload {
  float weightG;
  uint32_t sampledAt;
  bool stable;
  bool cup;
};

inline bool formatScaleUpload(const ScaleUpload &sample, uint32_t now, uint32_t staleMs,
                              char *body, size_t capacity) {
  if (uint32_t(now - sample.sampledAt) >= staleMs || !std::isfinite(sample.weightG) ||
      sample.weightG < -50 || sample.weightG > 1100) return false;
  const int len = std::snprintf(body, capacity,
      "{\"weight_g\":%.1f,\"stable\":%s,\"cup\":%s,\"calibrated\":true}",
      sample.weightG, sample.stable ? "true" : "false", sample.cup ? "true" : "false");
  return len > 0 && static_cast<size_t>(len) < capacity;
}
