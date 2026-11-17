#include <cassert>
#include <cstdio>
#include <string>
#include "ai_refill.h"

struct FakeAiPump : PumpActuator {
  bool on=false, enabled=true;
  bool available() const override { return enabled; }
  void set(bool value) override { on=value; }
};
struct AiBench {
  FakeAiPump pump;
  Inputs i{true,true,true,true,true,100,1000,1000};
  CupTare tare;
  GatewayDispenser gateway;
  AiRefillBridge bridge;
  AdviceQuery query{};
  uint32_t cup=1, nonce=123;
  explicit AiBench(bool enabled=true) : gateway(pump,77,true,{}, {},enabled),bridge(gateway) { assert(tare.set(true,true,100)); }
  AiResult arm() { return bridge.arm(i,tare,cup,nonce++,query); }
  AdviceProposal proposal(uint32_t ml=150, uint32_t id=1) {
    AdviceProposal a; a.version=1; a.bootSession=query.bootSession; a.requestId=query.requestId;
    a.cupSession=query.cupSession; a.nonce=query.nonce; a.adviceId=id; a.ageMs=100;
    a.suggestedMl=ml; a.modelBacked=true; return a;
  }
  AiResult deliver(const AdviceProposal &a) { return bridge.deliver(a,i,tare,cup); }
};

void model_changes_the_target_and_stops() {
  for (uint32_t ml : {120u,240u}) {
    AiBench b; assert(b.arm()==AiResult::Armed); auto a=b.proposal(ml);
    assert(!a.actuationAllowed && b.deliver(a)==AiResult::Started && b.pump.on);
    assert(b.gateway.safety().targetG()==100+ml);
    b.i.nowMs+=1000; b.i.scaleAtMs=b.i.nowMs; b.i.weightG=100+ml; b.gateway.update(b.i);
    assert(!b.pump.on && b.gateway.safety().fault()==Fault::None);
  }
  AiBench stopped; assert(stopped.arm()==AiResult::Armed);
  assert(stopped.deliver(stopped.proposal())==AiResult::Started);
  stopped.i.estopOk=false; stopped.gateway.update(stopped.i);
  assert(!stopped.pump.on && stopped.gateway.safety().fault()==Fault::Estop);
  stopped.i.estopOk=true; stopped.gateway.update(stopped.i);
  assert(!stopped.pump.on && stopped.arm()==AiResult::Busy); // E-stop release never resumes AI dispensing.
}
void no_local_consent_or_feature_no_start() {
  AiBench disabled(false); assert(disabled.arm()==AiResult::Disabled);
  AiBench b; assert(b.deliver(b.proposal())==AiResult::NotArmed && !b.pump.on);
  assert(b.gateway.request({1,77,1,1000,150},CommandSource::RemoteAI,b.i,b.tare)==RefillResult::RemoteDisabled);
  assert(!b.pump.on);
}
void context_binding_overlap_and_duplicate_response() {
  AiBench b; assert(b.arm()==AiResult::Armed); assert(b.arm()==AiResult::Busy);
  auto a=b.proposal(); auto wrong=a;
  wrong.nonce++; assert(b.deliver(wrong)==AiResult::WrongContext && !b.pump.on);
  wrong=a; wrong.bootSession++; assert(b.deliver(wrong)==AiResult::WrongContext);
  wrong=a; wrong.cupSession++; assert(b.deliver(wrong)==AiResult::WrongContext);
  wrong=a; wrong.requestId++; assert(b.deliver(wrong)==AiResult::WrongContext);
  assert(b.deliver(a)==AiResult::Started); assert(b.deliver(a)==AiResult::NotArmed);
}
void advice_is_used_once_even_after_safe_recovery() {
  AiBench b; assert(b.arm()==AiResult::Armed); assert(b.deliver(b.proposal())==AiResult::Started);
  b.gateway.stop(); b.bridge.cancel(); b.tare.clear(); assert(b.gateway.recover(b.i));
  assert(!b.pump.on && b.arm()==AiResult::Unsafe);
  assert(b.tare.set(true,true,100)); assert(b.arm()==AiResult::Armed);
  assert(b.deliver(b.proposal())==AiResult::DuplicateAdvice && !b.pump.on);
  assert(b.arm()==AiResult::Armed); assert(b.deliver(b.proposal(180,2))==AiResult::Started);
}
void over_limit_and_zero_volume_rejected() {
  for (uint32_t ml : {0u,301u,400u,UINT32_MAX}) {
    AiBench b; assert(b.arm()==AiResult::Armed);
    assert(b.deliver(b.proposal(ml))==AiResult::Rejected);
    assert(b.bridge.refillResult()==RefillResult::InvalidVolume && !b.pump.on);
  }
}
void fallback_flags_and_stale_advice_rejected() {
  for (int kind=0;kind<4;++kind) {
    AiBench b; assert(b.arm()==AiResult::Armed); auto a=b.proposal();
    if (kind==0) a.modelBacked=false;
    if (kind==1) a.actuationAllowed=true;
    if (kind==2) a.ageMs=AI_ADVICE_MAX_AGE_MS;
    if (kind==3) { a.ageMs=AI_ADVICE_MAX_AGE_MS-100; b.i.nowMs+=100; b.i.scaleAtMs=b.i.nowMs; }
    assert(b.deliver(a)==AiResult::InvalidAdvice && !b.pump.on && !b.bridge.pending());
  }
}
void timeout_failure_cancel_and_old_reply() {
  AiBench b; assert(b.arm()==AiResult::Armed); auto a=b.proposal();
  b.i.nowMs+=AI_REQUEST_MS; b.i.scaleAtMs=b.i.nowMs;
  assert(b.deliver(a)==AiResult::Expired && !b.pump.on);
  assert(b.arm()==AiResult::Armed); auto old=b.query; b.bridge.fail(old);
  assert(!b.bridge.pending()); assert(b.arm()==AiResult::Armed);
  b.bridge.fail(old); assert(b.bridge.pending()); // Old HTTP failure cannot cancel a new intent.
  assert(b.deliver(a)==AiResult::WrongContext && !b.pump.on);
  b.bridge.cancel(); assert(b.deliver(b.proposal())==AiResult::NotArmed);
  AiBench running; assert(running.arm()==AiResult::Armed);
  assert(running.deliver(running.proposal())==AiResult::Started);
  running.i.nowMs+=180000; running.i.scaleAtMs=running.i.nowMs; running.gateway.update(running.i);
  assert(!running.pump.on && running.gateway.safety().fault()==Fault::Timeout);
  AiBench wrap; wrap.i.nowMs=wrap.i.scaleAtMs=0xfffffff0u;
  assert(wrap.arm()==AiResult::Armed); auto across=wrap.proposal();
  wrap.i.nowMs+=100; wrap.i.scaleAtMs=wrap.i.nowMs;
  assert(wrap.deliver(across)==AiResult::Started); // Consent age survives millis wrap.
}
void unsafe_during_network_wait_cancels_permanently() {
  for (int kind=0;kind<8;++kind) {
    AiBench b; assert(b.arm()==AiResult::Armed); auto a=b.proposal();
    if (kind==0) b.i.cupPresent=false;
    if (kind==1) b.i.estopOk=false;
    if (kind==2) b.i.tankWet=false;
    if (kind==3) b.i.scaleValid=false;
    if (kind==4) b.i.calibrated=false;
    if (kind==5) b.i.nowMs+=2000;
    if (kind==6) b.tare.clear();
    if (kind==7) b.cup++;
    b.bridge.update(b.i,b.tare,b.cup); assert(!b.bridge.pending());
    b.i={true,true,true,true,true,100,4000,4000}; b.cup=1; b.tare.set(true,true,100);
    assert(b.deliver(a)==AiResult::NotArmed && !b.pump.on); // Restore does not re-arm.
  }
}
void unsafe_at_delivery_and_hardware_disabled() {
  AiBench b; assert(b.arm()==AiResult::Armed); auto a=b.proposal();
  b.i.estopOk=false; assert(b.deliver(a)==AiResult::Unsafe && !b.pump.on);
  AiBench disabled; disabled.pump.enabled=false;
  assert(disabled.arm()==AiResult::Armed);
  assert(disabled.deliver(disabled.proposal())==AiResult::Rejected && !disabled.pump.on);
  assert(disabled.bridge.refillResult()==RefillResult::Disabled);
}
void manual_start_and_stop_override_pending_ai() {
  AiBench b; assert(b.arm()==AiResult::Armed); auto a=b.proposal();
  assert(b.gateway.request({1,77,2,b.i.nowMs,250},CommandSource::LocalOperator,b.i,b.tare)==RefillResult::Started);
  b.bridge.update(b.i,b.tare,b.cup); assert(b.deliver(a)==AiResult::NotArmed);
  assert(b.gateway.safety().targetG()==350);
  b.gateway.stop(); b.bridge.update(b.i,b.tare,b.cup);
  assert(!b.pump.on && b.gateway.safety().fault()==Fault::ManualStop);
}
void reboot_and_id_wrap_do_not_start() {
  AiBench b; assert(b.arm()==AiResult::Armed); auto a=b.proposal();
  FakeAiPump pump; GatewayDispenser reboot(pump,78,false,{}, {},true); AiRefillBridge bridge(reboot);
  assert(bridge.deliver(a,b.i,b.tare,1)==AiResult::NotArmed && !pump.on);
  AdviceQuery q{}; assert(bridge.arm(b.i,b.tare,1,123,q)==AiResult::Armed);
  assert(bridge.deliver(a,b.i,b.tare,1)==AiResult::WrongContext && !pump.on);
  b.bridge.cancel();
  assert(b.gateway.request({1,77,UINT32_MAX,b.i.nowMs,0},CommandSource::LocalOperator,b.i,b.tare)==RefillResult::InvalidVolume);
  assert(b.arm()==AiResult::Disabled);
}
void strict_bounded_json() {
  const std::string valid="{\"version\":1,\"boot_session\":77,\"request_id\":1,\"cup_session\":1,\"nonce\":123,\"advice_id\":1,\"age_ms\":100,\"suggested_ml\":180,\"model_backed\":true,\"actuation_allowed\":false}";
  AdviceProposal a{}; assert(parseAdvice(valid.data(),valid.size(),a) && a.suggestedMl==180);
  const std::string reverse="{\"actuation_allowed\":false,\"model_backed\":true,\"suggested_ml\":180,\"age_ms\":0,\"advice_id\":1,\"nonce\":123,\"cup_session\":1,\"request_id\":1,\"boot_session\":77,\"version\":1}";
  assert(parseAdvice(reverse.data(),reverse.size(),a));
  for (const std::string replacement : {"-1","NaN","180.5","true","\"180\"","4294967296","01","1e2"}) {
    std::string bad=valid; bad.replace(bad.find("180"),3,replacement);
    assert(!parseAdvice(bad.data(),bad.size(),a));
  }
  for (std::string bad : {valid+"{}",valid+std::string(512,' '),valid.substr(0,valid.size()-1),
                          valid.substr(0,valid.size()-1)+",\"version\":1}",std::string("{}")})
    assert(!parseAdvice(bad.data(),bad.size(),a));
  std::string duplicate=valid; duplicate.replace(duplicate.find("age_ms"),6,"nonce");
  assert(!parseAdvice(duplicate.data(),duplicate.size(),a));
  std::string nul=valid; nul.insert(20,1,'\0'); assert(!parseAdvice(nul.data(),nul.size(),a));
}
int main() {
#define RUN(test) test(); std::puts("PASS " #test)
  RUN(model_changes_the_target_and_stops); RUN(no_local_consent_or_feature_no_start);
  RUN(context_binding_overlap_and_duplicate_response); RUN(advice_is_used_once_even_after_safe_recovery);
  RUN(over_limit_and_zero_volume_rejected); RUN(fallback_flags_and_stale_advice_rejected);
  RUN(timeout_failure_cancel_and_old_reply); RUN(unsafe_during_network_wait_cancels_permanently);
  RUN(unsafe_at_delivery_and_hardware_disabled); RUN(manual_start_and_stop_override_pending_ai);
  RUN(reboot_and_id_wrap_do_not_start); RUN(strict_bounded_json);
}
