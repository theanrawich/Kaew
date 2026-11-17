#include <Arduino.h>
#include <HX711.h>
#include <Preferences.h>
#include <atomic>
#include <esp_system.h>
#include "gateway_commands.h"
#include "pump_gpio.h"
#include "packet_trace.h"
#include "wire_protocol.h"
#include "cloud_publisher.h"
#include "ai_advice_client.h"
#include "audio_io.h"
#ifndef KAEW_AUDIO_ENABLED
#define KAEW_AUDIO_ENABLED 0
#endif
#ifndef KAEW_DISPENSE_TIMEOUT_MS
#define KAEW_DISPENSE_TIMEOUT_MS 30000
#endif
#ifndef KAEW_NO_FLOW_MS
#define KAEW_NO_FLOW_MS 5000
#endif
#ifndef KAEW_SCALE_STALE_MS
#define KAEW_SCALE_STALE_MS 500
#endif

namespace {
constexpr int HX_DATA = 17, HX_CLOCK = 18;
constexpr int LINK_RX = 1, LINK_TX = 2;
HX711 scale;
struct RawScaleSample { int32_t raw; uint32_t atMs; };
QueueHandle_t scaleSamples = nullptr;
std::atomic<bool> scaleOverflow{false};
Preferences preferences;
Calibration calibration{};
ScaleProcessor scaleInputs;
FrameParser parser;
Receiver receiver;
Receiver safetyReceiver; // Safety data is independent of outbox backpressure.
CloudPublisher cloud;
AiAdviceClient adviceClient;
AudioIO audio;
GpioPump pump;
CommandLine commands;
PacketTrace trace;
uint32_t accepted = 0, duplicates = 0, rejected = 0;
SafetyLimits safetyLimits() {
  SafetyLimits limits;
  limits.timeoutMs = KAEW_DISPENSE_TIMEOUT_MS;
  limits.noFlowMs = KAEW_NO_FLOW_MS;
  limits.scaleStaleMs = KAEW_SCALE_STALE_MS;
  limits.settleMs = 1000;
  return limits; // Provisional development limits, not hardware acceptance values.
}
GatewayDispenser *dispenser = nullptr;
AiRefillBridge *aiRefill = nullptr;
uint32_t cupSession = 0;
Inputs inputs{false, false, false, false, false, 0, 0, 0};
uint32_t lastPrint = 0, bootSession = 0;

void acquireScale(void *) {
  for (;;) {
    if (scale.is_ready()) {
      // HX711 0.7.5 read() internally waits again. A disconnect race may
      // block this acquisition task, but can never block the safety loop.
      RawScaleSample sample{static_cast<int32_t>(scale.read()), millis()};
      if (xQueueSend(scaleSamples, &sample, 0) != pdTRUE) scaleOverflow.store(true);
    }
    vTaskDelay(pdMS_TO_TICKS(5));
  }
}

bool activeScale() {
  const auto state = dispenser->safety().state();
  return state == DispenseState::Dispensing || state == DispenseState::Settling;
}
void refreshInputs() {
  inputs.nowMs = millis();
  scaleInputs.expire(inputs.nowMs, KAEW_SCALE_STALE_MS);
  if (scaleOverflow.load()) scaleInputs.accept(8388607, inputs.nowMs, activeScale());
  inputs.cupPresent = scaleInputs.cupPresent();
  inputs.scaleValid = scaleInputs.valid() && (activeScale() || scaleInputs.stable());
  inputs.calibrated = scaleInputs.calibrated();
  inputs.weightG = scaleInputs.weightG();
  inputs.scaleAtMs = scaleInputs.sampledAt();
  inputs.tankWet = safetyReceiver.fresh(inputs.nowMs) && safetyReceiver.latest().level == 1;
  inputs.estopOk = pump.estopOk();
}
void controlTick() {
  refreshInputs();
  dispenser->update(inputs); // Apply output BEFORE optional I/O/diagnostics.
  aiRefill->update(inputs,scaleInputs.tare(),cupSession);
  if (dispenser->safety().state() == DispenseState::Faulted) scaleInputs.clearTare();
}
void command(const char *line) {
  controlTick();
  if (!strcmp(line, "STOP")) { aiRefill->cancel(); dispenser->stop(); scaleInputs.clearTare(); return; }
  if (!strcmp(line, "RESET")) {
    aiRefill->cancel();
    Serial.println(dispenser->recover(inputs) ? "reset accepted; new TARE and REFILL required" : "reset rejected");
    scaleInputs.clearTare(); return;
  }
  RefillRequest request{};
  if (parseRefill(line, request)) {
    aiRefill->cancel(); // A manual decision supersedes any in-flight AI intent.
    const auto result = dispenser->request(request, CommandSource::LocalOperator, inputs, scaleInputs.tare());
    Serial.printf("refill_result=%u request=%lu target_ml=%.1f\n", unsigned(result),
                  static_cast<unsigned long>(request.requestId), request.targetWaterMl);
    return;
  }
  if (dispenser->safety().state() != DispenseState::Idle) { Serial.println("command rejected: not idle"); return; }
  if (!strcmp(line, "AI_REFILL")) {
    AdviceQuery query{}; uint32_t nonce=esp_random(); if (!nonce) nonce=1;
    const auto result=aiRefill->arm(inputs,scaleInputs.tare(),cupSession,nonce,query);
    if (result == AiResult::Armed && !adviceClient.submit(query)) { aiRefill->cancel(); Serial.println("AI request unavailable; intent discarded"); }
    else Serial.printf("ai_intent=%u request=%lu\n",unsigned(result),static_cast<unsigned long>(query.requestId));
    return;
  }
  if (!strcmp(line, "TARE")) {
    aiRefill->cancel();
    const bool set=cupSession < UINT32_MAX && scaleInputs.setTare();
    if (set) ++cupSession;
    Serial.println(set ? "cup tare set (operator confirms EMPTY cup)" : "cup tare rejected"); return;
  }
  Calibration next{};
  if (parseCalibration(line, next)) {
    aiRefill->cancel();
    if (preferences.putBytes("cal-v1", &next, sizeof next) == sizeof next) {
      calibration = next; scaleInputs.calibrate(next); Serial.println("calibration saved; verify with independent masses");
    } else Serial.println("calibration rejected or storage failed");
    return;
  }
  Serial.println("command rejected: syntax");
}
}

void setup() {
  pump.begin(); pump.set(false);
  bootSession = esp_random(); if (!bootSession) bootSession = 1;
  static GatewayDispenser control(pump, bootSession, KAEW_LOCAL_REFILL_ENABLED, safetyLimits(), {}, KAEW_AI_REFILL_ENABLED);
  dispenser = &control;
  static AiRefillBridge bridge(control); aiRefill=&bridge;
  Serial.begin(115200);
  Serial1.begin(115200, SERIAL_8N1, LINK_RX, LINK_TX);
  if (preferences.begin("kaew-scale", false) && preferences.getBytesLength("cal-v1") == sizeof calibration)
    preferences.getBytes("cal-v1", &calibration, sizeof calibration);
  if (!validCalibration(calibration)) calibration = Calibration{};
  scaleInputs.calibrate(calibration);
  scale.begin(HX_DATA, HX_CLOCK);
  scaleSamples = xQueueCreate(8, sizeof(RawScaleSample));
  if (!scaleSamples || xTaskCreatePinnedToCore(acquireScale, "kaew-scale", 3072, nullptr, 1, nullptr, 0) != pdPASS)
    Serial.println("scale acquisition unavailable; dispensing remains blocked");
  cloud.begin();
  adviceClient.begin();
  if (KAEW_AUDIO_ENABLED && !audio.begin()) Serial.println("audio driver init failed");
}

void loop() {
  controlTick(); // Includes E-stop/freshness even if serial input never terminates.
  bool scaleReady = false;
  long raw = 0;
  RawScaleSample sample{};
  for (unsigned n = 0; n < 8 && scaleSamples && xQueueReceive(scaleSamples, &sample, 0) == pdTRUE; ++n) {
    scaleReady = true; raw = sample.raw;
    scaleInputs.accept(sample.raw, sample.atMs, activeScale());
    controlTick(); // Each queued removal is checked, not overwritten by a later sample.
  }
  controlTick(); // Raw cup removal/target crossing is applied in this iteration.

  // Work budgets stop continuous UART/console input starving safety updates.
  Packet persisted{};
  for (unsigned n = 0; n < 8 && cloud.takeAck(persisted); ++n) {
    uint8_t bytes[FRAME_SIZE]; encode(persisted, true, bytes); Serial1.write(bytes, sizeof bytes);
  }
  for (unsigned n = 0; n < 256 && Serial1.available(); ++n) {
    Packet p{}; bool ack = false;
    if (parser.push(static_cast<uint8_t>(Serial1.read()), p, ack) && !ack) {
      const auto safetyResult = safetyReceiver.accept(p, millis());
      controlTick(); // Latch low/unknown immediately, even if a wet frame follows.
      if (safetyResult == Receive::Accepted || safetyResult == Receive::Duplicate) trace.emit("rx", p, millis());
      Receiver previous = receiver;
      Receive result = receiver.accept(p, millis());
      if (result == Receive::Accepted || result == Receive::Duplicate) {
        if (cloud.enabled()) {
          if (!cloud.enqueue(p)) { if (result == Receive::Accepted) receiver = previous; ++rejected; continue; }
        } else {
          uint8_t bytes[FRAME_SIZE]; encode(p, true, bytes); Serial1.write(bytes, sizeof bytes);
        }
        if (result == Receive::Accepted) ++accepted; else ++duplicates;
      } else ++rejected;
    }
  }
  controlTick(); // Includes newly received low/unknown level.
  for (unsigned n = 0; n < 64 && Serial.available(); ++n) {
    if (commands.push(static_cast<char>(Serial.read()))) command(commands.text());
  }
  controlTick(); // Local STOP/RESET/manual decisions precede an AI reply.
  AdviceResponse response{};
  if (commands.idle() && !Serial.available() && adviceClient.take(response)) {
    controlTick();
    if (!response.valid) { aiRefill->fail(response.query); Serial.println("AI response rejected: transport/schema/expiry"); }
    else {
      const auto result=aiRefill->deliver(response.proposal,inputs,scaleInputs.tare(),cupSession);
      Serial.printf("ai_result=%u refill_result=%u advice=%lu suggested_ml=%lu\n",unsigned(result),unsigned(aiRefill->refillResult()),
        static_cast<unsigned long>(response.proposal.adviceId),static_cast<unsigned long>(response.proposal.suggestedMl));
    }
  }
  controlTick();
  if (uint32_t(inputs.nowMs - lastPrint) >= 1000 && Serial.availableForWrite() >= 64) {
    float volume = 0; bool known = scaleInputs.tare().volume(inputs.cupPresent, inputs.weightG, volume);
    // Finite diagnostic output can still affect timing; measure on the board.
    Serial.printf("hx711_ready=%d hx711_raw=%ld calibrated=%d weight=%.1f stable=%d cup=%d volume_known=%d volume_ml=%.1f link_fresh=%d level=%u rx=%lu dup=%lu rejected=%lu cloud_reject=%lu cloud_error=%lu pump=%s state=%u fault=%u boot=%lu now_ms=%lu trace_dropped=%lu\n",
      scaleReady, raw, inputs.calibrated, inputs.weightG, scaleInputs.stable(), inputs.cupPresent, known, volume,
      receiver.fresh(inputs.nowMs), receiver.fresh(inputs.nowMs) ? receiver.latest().level : 0,
      static_cast<unsigned long>(accepted), static_cast<unsigned long>(duplicates), static_cast<unsigned long>(rejected),
      static_cast<unsigned long>(cloud.rejected()), static_cast<unsigned long>(cloud.errors()),
      dispenser->safety().pumping() ? "on" : "off", unsigned(dispenser->safety().state()), unsigned(dispenser->safety().fault()),
      static_cast<unsigned long>(bootSession), static_cast<unsigned long>(inputs.nowMs), static_cast<unsigned long>(trace.dropped()));
    lastPrint = inputs.nowMs;
  }
  delay(5);
}
