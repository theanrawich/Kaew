#pragma once
#include <cmath>
#include <cstdint>

enum class Fault { None, Estop, CupMissing, TankLow, StaleScale, InvalidScale, Timeout, AbnormalWeight };
struct Inputs {
  bool cupPresent, tankWet, estopOk, scaleValid, calibrated;
  float weightG;
  uint32_t nowMs, scaleAtMs;
};

// Example limits only. Physical commissioning must establish safe values.
class SafetyController {
  bool pump_ = false;
  Fault fault_ = Fault::None;
  float target_ = 0;
  float highestWeight_ = 0;
  uint32_t started_ = 0;
  Fault check(const Inputs &i) const {
    if (!i.estopOk) return Fault::Estop;
    if (!i.cupPresent) return Fault::CupMissing;
    if (!i.tankWet) return Fault::TankLow;
    if (!i.scaleValid || !i.calibrated || !std::isfinite(i.weightG) || i.weightG < 0 || i.weightG > 1000) return Fault::InvalidScale;
    if (uint32_t(i.nowMs - i.scaleAtMs) >= 2000) return Fault::StaleScale;
    return Fault::None;
  }
public:
  bool pumping() const { return pump_; }
  Fault fault() const { return fault_; }
  bool start(const Inputs &i, float targetG) {
    if (pump_ || fault_ != Fault::None || check(i) != Fault::None || !std::isfinite(targetG) || targetG <= i.weightG || targetG > 900) return false;
    target_ = targetG; highestWeight_ = i.weightG; started_ = i.nowMs; pump_ = true; return true;
  }
  void update(const Inputs &i) {
    if (!pump_) return;
    Fault f = check(i);
    if (f == Fault::None && i.weightG < highestWeight_ - 20.0f) f = Fault::AbnormalWeight;
    if (f == Fault::None && uint32_t(i.nowMs - started_) >= 180000) f = Fault::Timeout;
    if (f != Fault::None) { pump_ = false; fault_ = f; }
    else if (i.weightG >= target_) pump_ = false;
    else if (i.weightG > highestWeight_) highestWeight_ = i.weightG;
  }
  bool reset(const Inputs &i) {
    if (pump_ || check(i) != Fault::None) return false;
    fault_ = Fault::None; return true;
  }
};
