#include <cassert>
#include <cstdio>
#include <limits>
#include <string>
#include "gateway_commands.h"
#include "wire_protocol.h"

struct FakePump : PumpActuator {
  bool ready = true, on = false;
  unsigned starts = 0;
  bool available() const override { return ready; }
  void set(bool next) override { if (next && !on) ++starts; on = next; }
};
SafetyLimits testLimits() {
  SafetyLimits l; l.timeoutMs = 30000; l.noFlowMs = 5000;
  l.scaleStaleMs = 500; l.settleMs = 1000; return l;
}
Calibration syntheticCalibration() {
  Calibration c{}; assert(makeCalibration(0, 10000, 100, c)); return c;
}
struct Bench {
  FakePump pump;
  ScaleProcessor scale{syntheticCalibration()};
  Receiver tank;
  Packet packet{1, 55, 0, 2500, UINT16_MAX, 1};
  Inputs i{false, false, true, false, false, 0, 0, 0};
  GatewayDispenser gateway;
  uint32_t nextId = 1;
  explicit Bench(SafetyLimits limits = testLimits()) : gateway(pump, 77, true, limits) {
    tank.accept(packet, 0);
    for (unsigned n = 0; n < 7; ++n) { i.nowMs = n * 100; scale.accept(10000, i.nowMs, false); sync(); }
    assert(scale.cupPresent() && scale.setTare()); assert(!pump.on);
  }
  void sync() {
    scale.expire(i.nowMs, 500);
    i.cupPresent = scale.cupPresent(); i.calibrated = scale.calibrated();
    const auto state = gateway.safety().state();
    i.scaleValid = scale.valid() && (state == DispenseState::Dispensing || state == DispenseState::Settling || scale.stable());
    i.weightG = scale.weightG(); i.scaleAtMs = scale.sampledAt();
    i.tankWet = tank.fresh(i.nowMs) && tank.latest().level == 1;
    gateway.update(i);
    if (gateway.safety().state() == DispenseState::Faulted) scale.clearTare();
    assert(pump.on == gateway.safety().pumping());
  }
  void sample(float grams, uint32_t dt = 100) {
    i.nowMs += dt; sync(); // No reconnection may conceal an already stale gap.
    const auto state = gateway.safety().state();
    scale.accept(static_cast<int32_t>(grams * 100), i.nowMs,
                 state == DispenseState::Dispensing || state == DispenseState::Settling);
    sync();
  }
  void wet() { packet.seq++; packet.level = 1; tank.accept(packet, i.nowMs); }
  RefillRequest request(float total = 100) { return {1, 77, nextId++, i.nowMs, total}; }
  RefillResult start(float total = 100) { return send(request(total)); }
  RefillResult send(RefillRequest r, CommandSource source = CommandSource::LocalOperator) {
    return gateway.request(r, source, i, scale.tare());
  }
  void fault(Fault expected) { assert(!pump.on && gateway.safety().fault() == expected); }
};

void valid_refill() {
  Bench b; assert(b.start() == RefillResult::Started); assert(b.pump.on);
  assert(b.gateway.safety().targetG() == 200); // empty cup 100 g + TOTAL water 100 mL
}
void no_cup() {
  Bench b; for (int n=0; n<5; ++n) b.sample(0);
  assert(b.start() != RefillResult::Started && !b.pump.on);
}
void cup_removed_first_sample() {
  Bench b; assert(b.start() == RefillResult::Started); b.sample(0);
  b.fault(Fault::CupMissing); // no three-sample median delay
  b.sample(100); assert(!b.pump.on);
}
void partial_lift() {
  Bench b; assert(b.start() == RefillResult::Started); b.sample(70);
  b.fault(Fault::AbnormalWeight); // still above the cup-presence threshold
}
void estop() {
  Bench b; assert(b.start() == RefillResult::Started);
  b.i.estopOk = false; b.sync(); b.fault(Fault::Estop);
  assert(!b.gateway.recover(b.i)); b.i.estopOk = true; b.sync(); assert(!b.pump.on);
}
void tank_low_unknown() {
  for (uint8_t level : {uint8_t(0), uint8_t(2)}) {
    Bench b; assert(b.start() == RefillResult::Started);
    b.packet.seq++; b.packet.level = level; b.tank.accept(b.packet, b.i.nowMs); b.sync();
    b.fault(Fault::TankLow); b.wet(); b.sync(); assert(!b.pump.on);
    Bench idle; idle.packet.seq++; idle.packet.level = level;
    idle.tank.accept(idle.packet, idle.i.nowMs); idle.sync(); assert(idle.start() != RefillResult::Started);
  }
}
void invalid_hx711() {
  for (int32_t raw : {int32_t(-8388608), int32_t(8388607), int32_t(9000000)}) {
    Bench b; assert(b.start() == RefillResult::Started);
    b.scale.accept(raw, b.i.nowMs, true); b.sync(); b.fault(Fault::InvalidScale);
  }
  Bench b; b.scale.calibrate({}); b.sync(); assert(b.start() != RefillResult::Started);
}
void stale_scale() {
  Bench b; assert(b.start() == RefillResult::Started);
  b.i.nowMs += 499; b.sync(); assert(b.pump.on);
  b.i.nowMs++; b.sync(); b.fault(Fault::StaleScale);
  float volume; assert(!b.scale.tare().volume(true, 100, volume));
}
void no_progress() {
  Bench b; assert(b.start() == RefillResult::Started);
  for (int n=0; n<50; ++n) { b.wet(); b.sample(100); }
  b.fault(Fault::NoFlow);
}
void excessive_rise() {
  Bench b; assert(b.start(300) == RefillResult::Started);
  b.sample(250); b.fault(Fault::AbnormalWeight);
}
void timeout() {
  auto l = testLimits(); l.timeoutMs = 1000; Bench b(l);
  assert(b.start() == RefillResult::Started);
  for (int n=1; n<=10; ++n) b.sample(100+n);
  b.fault(Fault::Timeout);
}
void duplicates_overlap() {
  Bench b; auto first = b.request(); assert(b.send(first) == RefillResult::Started);
  assert(b.send(first) == RefillResult::Duplicate);
  auto overlap = b.request(150); assert(b.send(overlap) == RefillResult::Busy);
  assert(b.gateway.safety().targetG() == 200 && b.pump.starts == 1);
  for (int n=1; n<=10; ++n) b.sample(100+n*10);
  for (int n=0; n<10; ++n) b.sample(200);
  assert(!b.pump.on && b.gateway.safety().state() == DispenseState::Idle);
  assert(b.send(first) == RefillResult::Duplicate);
  assert(b.send(overlap) == RefillResult::Duplicate); // no deferred start
  assert(b.start(100) == RefillResult::InvalidVolume); // already contains 100 mL
  assert(b.start(150) == RefillResult::Started);
  assert(b.gateway.safety().targetG() == 250); // total target, not another 150 mL
}
void invalid_target() {
  Bench b;
  for (float ml : {-1.0f, 0.0f, 300.1f, NAN, INFINITY}) assert(b.start(ml) == RefillResult::InvalidVolume);
  assert(!b.pump.on); b.scale.clearTare(); assert(b.start() == RefillResult::TareRequired);
}
void reboot_off() {
  Bench b; assert(b.start() == RefillResult::Started);
  FakePump pump; pump.on = true; GatewayDispenser reboot(pump, 78, true, testLimits());
  assert(!pump.on && !reboot.safety().pumping());
  assert(reboot.request(b.request(), CommandSource::LocalOperator, b.i, b.scale.tare()) == RefillResult::InvalidEnvelope);
  ScaleProcessor scale(syntheticCalibration()); float volume;
  assert(!scale.tare().volume(true, 100, volume));
}
void explicit_recovery() {
  Bench b; assert(b.start() == RefillResult::Started); b.gateway.stop(); b.sync(); b.fault(Fault::ManualStop);
  assert(b.start() == RefillResult::Busy);
  assert(b.gateway.recover(b.i)); assert(!b.pump.on);
  assert(b.start() == RefillResult::TareRequired);
  assert(b.scale.setTare()); assert(b.start() == RefillResult::Started);
}
void remote_network_failure() {
  Bench b; assert(b.send(b.request(), CommandSource::RemoteAI) == RefillResult::RemoteDisabled);
  assert(!b.pump.on); assert(b.start() == RefillResult::Started);
  b.i.nowMs += 500; // No cloud callback or AI response is needed to stop.
  auto r = b.request(); assert(b.send(r, CommandSource::RemoteAI) == RefillResult::RemoteDisabled);
  assert(!b.pump.on);
}
void target_reached() {
  Bench b; assert(b.start() == RefillResult::Started);
  for (int n=1; n<=9; ++n) { b.sample(100+n*10); assert(b.pump.on); }
  b.sample(200); assert(!b.pump.on && b.gateway.safety().state() == DispenseState::Settling);
}
void tank_stops_updating() {
  Bench b; assert(b.start() == RefillResult::Started);
  for (int n=1; n<=44; ++n) b.sample(100+n);
  b.fault(Fault::TankLow); // 5 seconds after the sole wet packet
}
void repeated_operations() {
  Bench b;
  for (int cycle=0; cycle<20; ++cycle) {
    b.wet(); assert(b.start() == RefillResult::Started); b.gateway.stop(); b.sync();
    assert(b.gateway.recover(b.i)); assert(!b.pump.on);
    assert(b.scale.setTare()); b.sample(100);
  }
  assert(b.pump.starts == 20);
}
void envelope_age_and_rejected_replay() {
  Bench b; auto old = b.request(); old.issuedAtMs -= 2000;
  assert(b.send(old) == RefillResult::Expired);
  old.issuedAtMs = b.i.nowMs; assert(b.send(old) == RefillResult::Duplicate);
  auto future = b.request(); future.issuedAtMs++; assert(b.send(future) == RefillResult::Expired);
  auto wrong = b.request(); wrong.version = 2; assert(b.send(wrong) == RefillResult::InvalidEnvelope);
  wrong.version = 1; wrong.bootSession++; assert(b.send(wrong) == RefillResult::InvalidEnvelope);
  auto rejected = b.request(); b.i.tankWet = false; assert(b.send(rejected) == RefillResult::Unsafe);
  b.sync(); assert(b.send(rejected) == RefillResult::Duplicate);
}
void disabled_actuator_and_limits() {
  Bench b; b.pump.ready = false; assert(b.start() == RefillResult::Disabled && !b.pump.on);
  b.pump.ready = true; assert(b.start() == RefillResult::Started);
  b.pump.ready = false; b.sync(); assert(!b.pump.on);
  FakePump pump; GatewayDispenser defaults(pump, 77);
  assert(defaults.request(b.request(), CommandSource::LocalOperator, b.i, b.scale.tare()) == RefillResult::Disabled);
  auto l = testLimits(); l.noFlowMs = 0; SafetyController invalid(l);
  assert(!invalid.start(b.i, 200)); l = testLimits(); l.removalG = NAN;
  SafetyController nan(l); assert(!nan.start(b.i, 200));
  RefillLimits bad; bad.maxWaterMl = INFINITY; GatewayDispenser bounds(pump, 77, true, {}, bad);
  assert(bounds.request(b.request(), CommandSource::LocalOperator, b.i, b.scale.tare()) == RefillResult::Disabled);
}
void parser_framing() {
  RefillRequest r{}; assert(parseRefill("REFILL 77 1 600 100", r) && r.targetWaterMl == 100);
  Calibration c{}; assert(parseCalibration("CAL -10000 0 100", c));
  for (const char *s : {"CAL 999999999999999999 0 100", "CAL 0 8388607 100", "CAL 0 10000 nan", "CAL 0 10000 100 suffix"})
    assert(!parseCalibration(s, c));
  for (const char *s : {"REFILL -77 1 600 100", "REFILL 77 4294967296 600 100", "REFILL 77 1 600 nan",
       "REFILL 77 1 600 100 extra", "REFILL 77 1 600", "REFILL 77 1 600 100junk"}) assert(!parseRefill(s, r));
  CommandLine line; assert(line.idle());
  for (int n=0; n<140; ++n) assert(!line.push('x'));
  assert(!line.idle());
  for (char ch : std::string("REFILL 77 1 600 100\n")) assert(!line.push(ch));
  assert(line.idle());
  for (char ch : std::string("STOP")) assert(!line.push(ch));
  assert(!line.idle()); // An incomplete STOP must defer a pending AI reply.
  assert(line.push('\n') && std::string(line.text()) == "STOP");
  assert(line.idle());
  assert(!line.push('\0')); for (char ch : std::string("STOP\n")) assert(!line.push(ch));
}
void stale_idle_and_clock_wrap() {
  Bench b; b.i.nowMs += 500; b.sync(); assert(b.start() != RefillResult::Started);
  for (int n=0; n<7; ++n) b.sample(100);
  assert(b.scale.cupPresent()); assert(b.start() == RefillResult::TareRequired);
  assert(b.scale.setTare());
  FakePump pump; GatewayDispenser g(pump, 77, true, testLimits());
  Inputs i{true,true,true,true,true,100,0xfffffff0u,0xfffffff0u};
  CupTare tare; assert(tare.set(true,true,100));
  assert(g.request({1,77,1,i.nowMs,100}, CommandSource::LocalOperator,i,tare) == RefillResult::Started);
  i.nowMs += 500; g.update(i); assert(!pump.on && g.safety().fault() == Fault::StaleScale);
}
void storage_backpressure_cannot_hide_dry() {
  Bench b; assert(b.start() == RefillResult::Started);
  Receiver delivery = b.tank, before = delivery;
  auto dry = b.packet; dry.seq++; dry.level = 2;
  assert(b.tank.accept(dry,b.i.nowMs) == Receive::Accepted);
  assert(delivery.accept(dry,b.i.nowMs) == Receive::Accepted);
  delivery = before; // enqueue failed: retry/ACK receiver rolls back, safety never does.
  b.sync(); b.fault(Fault::TankLow);
  b.wet(); b.sync(); assert(!b.pump.on);
}
void calibration_stability() {
  Calibration c{}; assert(makeCalibration(10000,0,100,c)); assert(toGrams(c,5000) == 50);
  assert(!makeCalibration(-8388608,0,100,c)); assert(!makeCalibration(0,8388607,100,c));
  Bench b; b.sample(110); assert(!b.scale.cupPresent() && !b.scale.setTare());
  b.scale.calibrate(syntheticCalibration()); assert(!b.scale.cupPresent());
  float ml; assert(!b.scale.tare().volume(true,100,ml));
}

int main() {
#define RUN(name) name(); std::puts("PASS " #name)
  RUN(valid_refill); RUN(no_cup); RUN(cup_removed_first_sample); RUN(partial_lift);
  RUN(estop); RUN(tank_low_unknown); RUN(invalid_hx711); RUN(stale_scale);
  RUN(no_progress); RUN(excessive_rise); RUN(timeout); RUN(duplicates_overlap);
  RUN(invalid_target); RUN(reboot_off); RUN(explicit_recovery); RUN(remote_network_failure);
  RUN(target_reached); RUN(tank_stops_updating); RUN(repeated_operations);
  RUN(envelope_age_and_rejected_replay); RUN(disabled_actuator_and_limits);
  RUN(parser_framing); RUN(stale_idle_and_clock_wrap); RUN(storage_backpressure_cannot_hide_dry);
  RUN(calibration_stability);
}
