#include <cassert>
#include "wire_protocol.h"
int main() {
  Packet p{1, 7, 0, 2500, 1234, 1}; uint8_t b[FRAME_SIZE]; encode(p, false, b);
  Packet decoded{}; bool ack = false;
  assert(decode(b, decoded, ack) && !ack && decoded.session == 7 && decoded.adc == 1234);
  b[15] ^= 1; assert(!decode(b, decoded, ack)); b[15] ^= 1;
  Receiver r; assert(r.accept(p, 100) == Receive::Accepted);
  assert(r.accept(p, 200) == Receive::Duplicate); assert(r.receivedAt() == 100);
  assert(!r.fresh(5100));
  Packet old = p; old.seq = 0; old.session = 8;
  assert(r.accept(old, 200) == Receive::SessionMismatch);
  assert(r.accept(old, 5100) == Receive::Accepted);
  p.session = 8; p.seq = 2; assert(r.accept(p, 5200) == Receive::Accepted);
  p.seq = 1; assert(r.accept(p, 5300) == Receive::Old);
  p.seq = 2;
  Sender sender; sender.begin(p, 100); assert(sender.due(100)); sender.sent(100);
  assert(!sender.due(599)); assert(sender.due(600));
  assert(!sender.acknowledge(7, 2)); assert(sender.acknowledge(8, 2));
  assert(!sender.pending());
  sender.begin(p, 1000); for (uint32_t t=1000; t<=2500; t+=500) { assert(sender.due(t)); sender.sent(t); }
  assert(!sender.expired(2999)); assert(sender.expired(3000)); sender.drop(); assert(!sender.pending());
  FrameParser parser; bool done=false; encode(p, false, b);
  parser.push(0xff, decoded, ack); parser.push(0x4b, decoded, ack); parser.push(0x11, decoded, ack);
  for (auto byte : b) done = parser.push(byte, decoded, ack) || done;
  assert(done && !ack && decoded.seq==p.seq);
  encode(p, false, b); b[2]=2; assert(!decode(b, decoded, ack));
  return 0;
}
