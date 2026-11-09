#pragma once
#include <cstddef>
#include <cstdint>
inline int16_t pcm32to16(int32_t sample) { return static_cast<int16_t>(sample >> 16); }
inline bool voiceActivity(const int16_t *samples, size_t count, uint16_t threshold) {
  if(!samples || !count)return false;
  uint64_t total=0; for(size_t i=0;i<count;i++) {int32_t v=samples[i];total+=v<0?-v:v;}
  return total/count >= threshold;
}
