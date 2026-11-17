#pragma once
#include <cerrno>
#include <cstdlib>
#include <cstring>
#include "dispensing.h"

// Fixed-size newline framing. Overflow/control bytes discard the WHOLE line;
// a valid-looking suffix must not become a second command. No blocking reads.
class CommandLine {
  char bytes_[128]{};
  unsigned size_ = 0;
  bool discard_ = false;
public:
  bool push(char ch) {
    if (ch == '\r') return false;
    if (ch == '\n') {
      bool ready = !discard_ && size_ > 0;
      bytes_[size_] = '\0'; size_ = 0; discard_ = false; return ready;
    }
    if (static_cast<unsigned char>(ch) < 32 || static_cast<unsigned char>(ch) > 126 || size_ >= sizeof bytes_ - 1) discard_ = true;
    if (!discard_) bytes_[size_++] = ch;
    return false;
  }
  const char *text() const { return bytes_; }
  bool idle() const { return size_ == 0 && !discard_; }
};
inline bool decimalU32(const char *s, uint32_t &out) {
  if (!s || !*s) return false;
  uint64_t value = 0;
  for (; *s; ++s) {
    if (*s < '0' || *s > '9') return false;
    value = value * 10 + unsigned(*s - '0');
    if (value > UINT32_MAX) return false;
  }
  out = static_cast<uint32_t>(value); return true;
}
inline bool parseRefill(const char *line, RefillRequest &out) {
  if (!line || std::strlen(line) >= 128) return false;
  char copy[128]; std::strcpy(copy, line);
  char *tokens[6]{}; unsigned count = 0;
  char *context = nullptr;
  for (char *part = strtok_r(copy, " ", &context); part; part = strtok_r(nullptr, " ", &context)) {
    if (count == 6) return false;
    tokens[count++] = part;
  }
  if (count != 5 || std::strcmp(tokens[0], "REFILL")) return false;
  RefillRequest r{1, 0, 0, 0, 0};
  if (!decimalU32(tokens[1], r.bootSession) || !decimalU32(tokens[2], r.requestId) || !decimalU32(tokens[3], r.issuedAtMs)) return false;
  char *end = nullptr; errno = 0; r.targetWaterMl = std::strtof(tokens[4], &end);
  if (errno || *end || !std::isfinite(r.targetWaterMl)) return false;
  out = r; return true;
}
inline bool parseCalibration(const char *line, Calibration &out) {
  if (!line || std::strlen(line) >= 128) return false;
  char copy[128]; std::strcpy(copy, line);
  char *tokens[4]{}; unsigned count = 0; char *context = nullptr;
  for (char *part = strtok_r(copy, " ", &context); part; part = strtok_r(nullptr, " ", &context)) {
    if (count == 4) return false;
    tokens[count++] = part;
  }
  if (count != 4 || std::strcmp(tokens[0], "CAL")) return false;
  int32_t raw[2]{};
  for (unsigned n=0; n<2; ++n) {
    const char *text = tokens[n+1]; const bool negative = *text == '-';
    uint32_t magnitude = 0;
    if (!decimalU32(text + (negative ? 1 : 0), magnitude) || magnitude > (negative ? 8388607u : 8388606u)) return false;
    raw[n] = negative ? -static_cast<int32_t>(magnitude) : static_cast<int32_t>(magnitude);
  }
  char *end = nullptr; errno = 0; const float grams = std::strtof(tokens[3], &end);
  return !errno && !*end && makeCalibration(raw[0], raw[1], grams, out);
}
