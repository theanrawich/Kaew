#pragma once
#include "safety.h"
#include "scale_processing.h"

// set(false) must be usable before other initialization. This is a command
// interface, not driver feedback or proof that electrical power was removed.
class PumpActuator {
public:
  virtual ~PumpActuator() = default;
  virtual bool available() const = 0;
  virtual void set(bool on) = 0;
};

enum class CommandSource { LocalOperator, RemoteAI };
struct RefillRequest {
  uint32_t version, bootSession, requestId, issuedAtMs;
  float targetWaterMl; // TOTAL water in the explicitly tared cup, not extra mL.
};
enum class RefillResult {
  Started, RemoteDisabled, Disabled, InvalidEnvelope, Duplicate,
  Expired, Busy, InvalidVolume, TareRequired, Unsafe
};
struct RefillLimits {
  float maxWaterMl = 300; // Illustrative hard ceiling; not measured cup capacity.
  uint32_t maxAgeMs = 2000;
  bool valid() const {
    return std::isfinite(maxWaterMl) && maxWaterMl > 0 && maxWaterMl <= 300 &&
      maxAgeMs > 0 && maxAgeMs <= 2000;
  }
};

class GatewayDispenser {
  PumpActuator &actuator_;
  SafetyController safety_;
  RefillLimits limits_;
  uint32_t boot_, lastRequest_ = 0;
  bool localEnabled_;
public:
  GatewayDispenser(PumpActuator &actuator, uint32_t bootSession,
                   bool localEnabled = false, SafetyLimits safety = {}, RefillLimits limits = {})
    : actuator_(actuator), safety_(safety), limits_(limits), boot_(bootSession), localEnabled_(localEnabled) {
    actuator_.set(false); // No operation/target/ID survives construction/reboot.
  }
  void update(const Inputs &i) {
    if (safety_.pumping() && !actuator_.available()) safety_.stop();
    safety_.update(i);
    actuator_.set(safety_.pumping() && actuator_.available());
  }
  RefillResult request(const RefillRequest &r, CommandSource source, const Inputs &i, const CupTare &tare) {
    update(i); // A malformed/duplicate request must never defer a safety stop.
    if (source != CommandSource::LocalOperator) return RefillResult::RemoteDisabled;
    if (!localEnabled_ || !actuator_.available() || !limits_.valid()) return RefillResult::Disabled;
    if (r.version != 1 || !boot_ || r.bootSession != boot_ || !r.requestId) return RefillResult::InvalidEnvelope;
    // Strictly increasing IDs in one gateway boot. Never wrap; start a new boot
    // session if exhausted. Consume rejected requests too: no deferred replay.
    if (r.requestId <= lastRequest_) return RefillResult::Duplicate;
    lastRequest_ = r.requestId;
    if (uint32_t(i.nowMs - r.issuedAtMs) >= limits_.maxAgeMs) return RefillResult::Expired;
    if (safety_.state() != DispenseState::Idle) return RefillResult::Busy;
    if (!std::isfinite(r.targetWaterMl) || r.targetWaterMl <= 0 || r.targetWaterMl > limits_.maxWaterMl)
      return RefillResult::InvalidVolume;
    float currentMl = 0;
    if (!tare.volume(i.cupPresent, i.weightG, currentMl)) return RefillResult::TareRequired;
    if (r.targetWaterMl <= currentMl) return RefillResult::InvalidVolume;
    const float targetG = i.weightG + (r.targetWaterMl - currentMl);
    if (!safety_.start(i, targetG)) return RefillResult::Unsafe;
    actuator_.set(true);
    return RefillResult::Started;
  }
  void stop() { safety_.stop(); actuator_.set(false); }
  bool recover(const Inputs &i) { update(i); return safety_.reset(i); }
  const SafetyController &safety() const { return safety_; }
};
