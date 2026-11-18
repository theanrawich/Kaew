#include <cassert>
#include <cstring>
#include "speech_capture.h"
#include "speech_upload.h"
int main() {
  assert(pcm32to16(0)==0); assert(pcm32to16(65536)==1);
  assert(pcm32to16(-65536)==-1);
  MicDcBlocker filter;
  assert(filter.convert(1000 * 65536) == 1000);
  assert(filter.convert(1000 * 65536) == 995);
  for (int i = 0; i < 2000; ++i) filter.convert(1000 * 65536);
  assert(filter.convert(1000 * 65536) == 0);
  filter.reset();
  assert(filter.convert(-1000 * 65536) == -1000);
  assert(filter.convert(INT32_MAX) == INT16_MAX);

  int16_t quiet[] = {1000, -1000};
  const auto quietStats = normalizeSpeech(quiet, 2);
  assert(quietStats.peak == 1000 && quietStats.rms == 1000 && quietStats.gain == 7);
  assert(quiet[0] == 7000 && quiet[1] == -7000);
  int16_t clipped[] = {INT16_MIN, INT16_MAX};
  const auto clippedStats = normalizeSpeech(clipped, 2);
  assert(clippedStats.clipped == 2 && clippedStats.peak == 32768);
  assert(clipped[0] == -23000 && clipped[1] == 22999);

  uint8_t header[speechWavHeaderSize];
  writeSpeechWavHeader(header, sizeof quiet);
  const uint8_t expected[] = {
    'R','I','F','F',40,0,0,0,'W','A','V','E','f','m','t',' ',16,0,0,0,
    1,0,1,0,128,62,0,0,0,125,0,0,2,0,16,0,'d','a','t','a',4,0,0,0
  };
  static_assert(sizeof expected == sizeof header, "WAV header size");
  assert(std::memcmp(header, expected, sizeof header) == 0);
  int16_t frame[SpeechCapture::frameSamples];
  static int16_t clip[SpeechCapture::maxSamples];
  SpeechCapture capture;
  const auto feed = [&](int16_t amplitude) {
    for (size_t i = 0; i < SpeechCapture::frameSamples; ++i)
      frame[i] = i % 2 ? amplitude : -amplitude;
    return capture.push(frame, clip);
  };
  for (int i = 0; i < 25; ++i) assert(feed(32767) == 0); // I2S startup
  assert(!capture.listening());
  for (int i = 0; i < 50; ++i) assert(feed(100) == 0);
  assert(capture.listening() && capture.backgroundRms() == 100);
  assert(feed(1800) == 0); // isolated transient
  for (int i = 0; i < 20; ++i) assert(feed(100) == 0);
  for (int i = 0; i < 10; ++i) assert(feed(400) == 0);
  for (int i = 0; i < 34; ++i) assert(feed(100) == 0);
  const auto count = feed(100);
  assert(count == (15 + 7 + 35) * SpeechCapture::frameSamples);
  assert(clip[0] == -100);
  assert(clip[12 * SpeechCapture::frameSamples] == -400);
  assert(clip[count - 1] == 100);
  for (int i = 0; i < 20; ++i) assert(feed(100) == 0);
  size_t longClip = 0;
  for (int i = 0; i < 420 && !longClip; ++i) longClip = feed(i % 2 ? 500 : 700);
  assert(longClip == SpeechCapture::maxSamples);
  size_t continuation = 0;
  for (int i = 0; i < 420 && !continuation; ++i) continuation = feed(i % 2 ? 500 : 700);
  assert(continuation == SpeechCapture::maxSamples && clip[0] == -700);
  assert(feed(100) == 0); // a short pause at the clip boundary
  assert(feed(200) == 0); // below the onset threshold, above the continuation threshold
  for (int i = 0; i < 34; ++i) assert(feed(100) == 0);
  assert(feed(100) == 37 * SpeechCapture::frameSamples && clip[SpeechCapture::frameSamples] == -200);
  capture = SpeechCapture{};
  for (int i = 0; i < 50; ++i) assert(feed(100) == 0);
  int uploads = 0;
  for (int i = 0; i < 1000; ++i) if (feed(300) > 0) ++uploads;
  assert(uploads == 1); // a new steady background should not keep retriggering
  return 0;
}
