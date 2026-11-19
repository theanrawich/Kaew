#pragma once
#include <cstdint>
inline int16_t pcm32to16(int32_t sample) { return static_cast<int16_t>(sample >> 16); }
