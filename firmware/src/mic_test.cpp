// Standalone bench test: no gateway, actuator or speaker initialization.
#include "speech_pipeline.h"

namespace {
AudioIO audio;
SpeechPipeline speech(audio);
}

void setup() {
  Serial.begin(115200);
  if (!audio.beginMicrophone() || !speech.begin(SpeechUpload::Transcript, false)) {
    audio.stop();
    Serial.println("Microphone pipeline initialization failed.");
  } else {
    Serial.println("Calibrating background noise. Wait for Listening.");
  }
}

void loop() {
  speech.poll();
}
