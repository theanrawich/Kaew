#include <cassert>
#include <initializer_list>
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
  // Only a fresh, decoded wet sample may authorize dispensing.
  // Missing data, unknown and dry readings must fail even with all other inputs safe.
  for (uint8_t level : {uint8_t(0), uint8_t(2)}) {
    Receiver tank;
    Inputs safe{true, tank.fresh(100) && tank.latest().level==1, true, true, true, 100, 100, 100};
    SafetyController missing;
    assert(!missing.start(safe, 200));
    Packet reading{1, 43, 1, INT16_MIN, UINT16_MAX, level};
    encode(reading, false, frame);
    FrameParser stream; completed=false;
    for (auto byte : frame) completed = stream.push(byte, received, ack) || completed;
    assert(completed && !ack && tank.accept(received, 100)==Receive::Accepted);
    safe.tankWet=tank.fresh(100) && tank.latest().level==1;
    assert(!missing.start(safe, 200));
    // A valid wet reading permits the host controller, then unknown/dry stops it.
    reading.level=1; reading.seq++;
    assert(tank.accept(reading, 200)==Receive::Accepted);
    safe.nowMs=safe.scaleAtMs=200; safe.tankWet=tank.fresh(200) && tank.latest().level==1;
    assert(missing.start(safe, 200));
    reading.level=level; reading.seq++;
    assert(tank.accept(reading, 300)==Receive::Accepted);
    safe.nowMs=safe.scaleAtMs=300; safe.tankWet=tank.fresh(300) && tank.latest().level==1;
    missing.update(safe);
    assert(!missing.pumping() && missing.fault()==Fault::TankLow);
  }
  // A corrupt wet frame cannot establish a tank reading or authorize a start.
  Receiver malformed; FrameParser corrupt; completed=false;
  sample.level=1; encode(sample, false, frame); frame[18]^=1;
  for (auto byte : frame) {
    if (corrupt.push(byte, received, ack) && !ack) {
      completed=true; malformed.accept(received, 6000);
    }
  }
  assert(!completed);
  Inputs safe{true, malformed.fresh(6000) && malformed.latest().level==1, true, true, true, 100, 6000, 6000};
  SafetyController invalid; assert(!invalid.start(safe, 200));
  return 0;
}
