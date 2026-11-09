#include <cassert>
#include "audio_processing.h"
int main() {
  assert(pcm32to16(0)==0); assert(pcm32to16(65536)==1);
  assert(pcm32to16(-65536)==-1);
  int16_t silent[4]={0,0,0,0}, loud[4]={1000,-1000,500,-500};
  assert(!voiceActivity(silent,4,300)); assert(voiceActivity(loud,4,300));
  assert(!voiceActivity(loud,0,300));
  return 0;
}
