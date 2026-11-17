// Software integration probe only. No Arduino or GPIO; synthetic safe inputs.
#include <iostream>
#include <iterator>
#include <string>
#include "ai_refill.h"
struct ProbePump : PumpActuator {
  bool on=false;
  bool available() const override { return true; }
  void set(bool value) override { on=value; }
};
int main() {
  std::string body((std::istreambuf_iterator<char>(std::cin)),{});
  AdviceProposal proposal{};
  if (!parseAdvice(body.data(),body.size(),proposal)) return 2;
  ProbePump pump; Inputs i{true,true,true,true,true,100,1000,1000}; CupTare tare;
  if (!tare.set(true,true,100)) return 3;
  GatewayDispenser gateway(pump,77,false,{}, {},true); AiRefillBridge bridge(gateway); AdviceQuery query{};
  if (bridge.arm(i,tare,1,123,query)!=AiResult::Armed) return 4;
  const auto result=bridge.deliver(proposal,i,tare,1);
  const bool started=result==AiResult::Started && pump.on;
  const float target=gateway.safety().targetG();
  i.nowMs+=1000; i.scaleAtMs=i.nowMs; i.weightG=target; gateway.update(i);
  std::cout << "{\"simulation\":true,\"started\":" << (started?"true":"false")
            << ",\"target_g\":" << target << ",\"pump_after_target\":" << (pump.on?"true":"false") << "}";
}
