#include <cassert>
#include "wire_protocol.h"
#include "safety.h"

int main() {
  Packet sample{1, 42, 1, 2500, 1000, 1}; Sender tx; Receiver rx; FrameParser parser;
  tx.begin(sample, 100); assert(tx.due(100)); tx.sent(100);
  uint8_t frame[FRAME_SIZE]; encode(sample, false, frame);
  Packet received{}; bool ack=false; bool completed=false;
  for (auto byte : frame) completed = parser.push(byte, received, ack) || completed;
  assert(completed && !ack); assert(rx.accept(received, 100)==Receive::Accepted);
  // Drop first acknowledgement; retry is acknowledged but must not refresh level age.
  assert(tx.due(600)); tx.sent(600); assert(rx.accept(received, 600)==Receive::Duplicate);
  encode(received, true, frame); completed=false;
  for (auto byte : frame) completed = parser.push(byte, received, ack) || completed;
  assert(completed && ack && tx.acknowledge(received.session, received.seq));
  SafetyController controller;
  Inputs i{true, rx.fresh(600) && rx.latest().level==1, true, true, true, 100, 600, 600};
  assert(controller.start(i, 200));
  i.nowMs=5100; i.scaleAtMs=i.nowMs; i.tankWet=rx.fresh(i.nowMs) && rx.latest().level==1;
  controller.update(i); assert(!controller.pumping() && controller.fault()==Fault::TankLow);
  SafetyController rebooted; assert(!rebooted.pumping()); assert(!rebooted.start(i, 200));
  // Fresh packet after reconnect still requires an explicit reset and new start.
  sample.seq++; assert(rx.accept(sample, 5200)==Receive::Accepted);
  i.nowMs=5200; i.scaleAtMs=5200; i.tankWet=true;
  assert(!controller.start(i, 200)); assert(controller.reset(i));
  assert(controller.start(i, 200));
  return 0;
}
