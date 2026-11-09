#include <cassert>
#include "safety.h"

int main() {
  SafetyController c;
  Inputs i{true, true, true, true, true, 100.0f, 1000, 1000};
  assert(!c.pumping());
  assert(c.start(i, 200.0f));
  assert(!c.start(i, 200.0f));
  i.nowMs = 1200; i.scaleAtMs = 1200; i.weightG = 200;
  c.update(i); assert(!c.pumping());
  assert(!c.start(i, 200));
  assert(c.start(i, 250));
  i.nowMs = 3300; c.update(i); assert(!c.pumping());
  assert(c.fault() == Fault::StaleScale);
  assert(!c.start(i, 250));
  i.scaleAtMs = i.nowMs; assert(c.reset(i));
  assert(c.start(i, 250)); i.estopOk = false; c.update(i);
  assert(!c.pumping()); assert(c.fault() == Fault::Estop);
  assert(!c.reset(i));
  i.estopOk = true; assert(c.reset(i)); assert(c.start(i, 250));
  i.nowMs += 180001; i.scaleAtMs = i.nowMs; c.update(i);
  assert(c.fault() == Fault::Timeout);
  i.scaleAtMs = i.nowMs; assert(c.reset(i));
  assert(c.start(i, 250)); i.cupPresent = false; c.update(i);
  assert(c.fault() == Fault::CupMissing); assert(!c.pumping());
  i.cupPresent = true; assert(c.reset(i)); assert(c.start(i, 250));
  i.tankWet = false; c.update(i); assert(c.fault() == Fault::TankLow);
  i.tankWet = true; assert(c.reset(i)); assert(c.start(i, 250));
  i.weightG = NAN; c.update(i); assert(c.fault() == Fault::InvalidScale);
  i.weightG = 100; assert(c.reset(i));
  i.nowMs = 0xfffffff0u; i.scaleAtMs = i.nowMs; assert(c.start(i, 250));
  i.nowMs = 0x00000800u; c.update(i); assert(c.fault() == Fault::StaleScale);
  return 0;
}
