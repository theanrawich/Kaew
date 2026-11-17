#include <cassert>
#include "speech_capture.h"
#include "audio_processing.h"
int main() {
  assert(pcm32to16(0)==0); assert(pcm32to16(65536)==1);
  assert(pcm32to16(-65536)==-1);
  int16_t silent[4]={0,0,0,0}, loud[4]={1000,-1000,500,-500};
  assert(!voiceActivity(silent,4,300)); assert(voiceActivity(loud,4,300));
  assert(!voiceActivity(loud,0,300));
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
  assert(feed(200) == 0); // below the onset threshold, above the continuation threshold
  for (int i = 0; i < 34; ++i) assert(feed(100) == 0);
  assert(feed(100) == 36 * SpeechCapture::frameSamples && clip[0] == -200);
  capture = SpeechCapture{};
  for (int i = 0; i < 50; ++i) assert(feed(100) == 0);
  int uploads = 0;
  for (int i = 0; i < 1000; ++i) if (feed(300) > 0) ++uploads;
  assert(uploads == 1); // a new steady background should not keep retriggering
  return 0;
}
