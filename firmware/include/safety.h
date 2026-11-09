#pragma once
#include <cmath>
#include <cstdint>

enum class Fault { None, Estop, CupMissing, TankLow, StaleScale, InvalidScale, Timeout, AbnormalWeight, NoFlow };
enum class DispenseState { Idle, Dispensing, Settling, Faulted };
// Simulation parameters only: calibrate and validate with the actual pump and scale.
struct SafetyLimits {
  uint32_t timeoutMs=180000, noFlowMs=30000, settleMs=0;
  float minProgressG=3, maxRiseGPerSec=1000, removalG=20, stopMarginG=0;
};
struct Inputs {
  bool cupPresent, tankWet, estopOk, scaleValid, calibrated;
  float weightG;
  uint32_t nowMs, scaleAtMs;
};

// Example limits only. Physical commissioning must establish safe values.
class SafetyController {
  DispenseState state_ = DispenseState::Idle;
  Fault fault_ = Fault::None;
  float target_ = 0;
  float highestWeight_ = 0;
  float progressWeight_ = 0, lastWeight_ = 0;
  uint32_t started_ = 0, progressAt_ = 0, lastSampleAt_ = 0, stoppedAt_ = 0;
  SafetyLimits limits_;
  Fault check(const Inputs &i) const {
    if (!i.estopOk) return Fault::Estop;
    if (!i.cupPresent) return Fault::CupMissing;
    if (!i.tankWet) return Fault::TankLow;
    if (!i.scaleValid || !i.calibrated || !std::isfinite(i.weightG) || i.weightG < 0 || i.weightG > 1000) return Fault::InvalidScale;
    if (uint32_t(i.nowMs - i.scaleAtMs) >= 2000) return Fault::StaleScale;
    return Fault::None;
  }
public:
  explicit SafetyController(SafetyLimits limits = SafetyLimits{}) : limits_(limits) {}
  bool pumping() const { return state_ == DispenseState::Dispensing; }
  DispenseState state() const { return state_; }
  Fault fault() const { return fault_; }
  bool start(const Inputs &i, float targetG) {
    if (state_ != DispenseState::Idle || fault_ != Fault::None || check(i) != Fault::None || !std::isfinite(targetG) || targetG <= i.weightG + limits_.stopMarginG || targetG > 900) return false;
    target_ = targetG; highestWeight_ = progressWeight_ = lastWeight_ = i.weightG;
    started_ = progressAt_ = i.nowMs; lastSampleAt_ = i.scaleAtMs; state_ = DispenseState::Dispensing; return true;
  }
  void update(const Inputs &i) {
    if (state_ == DispenseState::Settling) { if (uint32_t(i.nowMs-stoppedAt_) >= limits_.settleMs) state_ = DispenseState::Idle; return; }
    if (!pumping()) return;
    Fault f = check(i);
    if (f == Fault::None && i.weightG < highestWeight_ - limits_.removalG) f = Fault::AbnormalWeight;
    const uint32_t sampleDt = uint32_t(i.scaleAtMs-lastSampleAt_);
    if (f == Fault::None && sampleDt && i.weightG-lastWeight_ > limits_.maxRiseGPerSec * (sampleDt/1000.0f)) f = Fault::AbnormalWeight;
    if (f == Fault::None && uint32_t(i.nowMs - started_) >= limits_.timeoutMs) f = Fault::Timeout;
    if (i.weightG >= progressWeight_ + limits_.minProgressG) { progressWeight_ = i.weightG; progressAt_ = i.nowMs; }
    if (f == Fault::None && uint32_t(i.nowMs-progressAt_) >= limits_.noFlowMs) f = Fault::NoFlow;
    if (f != Fault::None) { state_ = DispenseState::Faulted; fault_ = f; }
    else if (i.weightG >= target_ - limits_.stopMarginG) { state_ = limits_.settleMs ? DispenseState::Settling : DispenseState::Idle; stoppedAt_ = i.nowMs; }
    else if (i.weightG > highestWeight_) highestWeight_ = i.weightG;
    if (sampleDt) { lastSampleAt_ = i.scaleAtMs; lastWeight_ = i.weightG; }
  }
  bool reset(const Inputs &i) {
    if (pumping() || state_ == DispenseState::Settling || check(i) != Fault::None) return false;
    fault_ = Fault::None; state_ = DispenseState::Idle; return true;
  }
};
