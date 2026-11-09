#include <cassert>
#include "safety.h"
#include "scale_processing.h"

int main() {
  SafetyLimits limits; limits.settleMs=1000; limits.noFlowMs=5000; limits.minProgressG=3;
  limits.maxRiseGPerSec=50; limits.stopMarginG=5;
  SafetyController c(limits); Inputs i{true,true,true,true,true,100,0,0};
  assert(c.start(i,200));
  for (int n=1;n<=8;++n) { i.nowMs=n*500; i.scaleAtMs=i.nowMs; i.weightG=100+n*10; c.update(i); assert(c.pumping()); }
  i.nowMs=4500; i.scaleAtMs=4500; i.weightG=195; c.update(i);
  assert(!c.pumping() && c.state()==DispenseState::Settling);
  assert(!c.start(i,250)); i.nowMs=5500; i.scaleAtMs=5500; c.update(i);
  assert(c.state()==DispenseState::Idle);
  assert(c.start(i,250)); i.nowMs=6000; i.scaleAtMs=6000; i.weightG=160; c.update(i);
  assert(!c.pumping() && c.fault()==Fault::AbnormalWeight);
  i.weightG=100; assert(c.reset(i)); assert(c.start(i,200));
  for (int n=1;n<=5;++n) { i.nowMs=6000+n*1000; i.scaleAtMs=i.nowMs; c.update(i); }
  assert(!c.pumping() && c.fault()==Fault::NoFlow);
  assert(c.reset(i)); assert(c.start(i,200)); i.nowMs+=100; i.scaleAtMs=i.nowMs; i.weightG=180;
  c.update(i); assert(c.fault()==Fault::AbnormalWeight);
  CupDetector cup; for(int n=0;n<3;++n) cup.update(true,100);
  assert(cup.updateDispensing(true, 110)); assert(cup.updateDispensing(true, 120));
  assert(!cup.updateDispensing(false, 120));
  return 0;
}
