#include <cassert>
#include <array>
#include <cstring>
#include "durable_queue.h"
#include "cloud_outbox_record.h"

struct MemoryStore : SlotStore {
  std::array<std::array<uint8_t, DURABLE_RECORD_SIZE>, DURABLE_SLOTS> data{};
  bool present[DURABLE_SLOTS]{}; bool failWrite=false, failRemove=false;
  int read(unsigned n,uint8_t *out) override { if (!present[n]) return 0; std::memcpy(out,data[n].data(),DURABLE_RECORD_SIZE); return 1; }
  bool write(unsigned n,const uint8_t *in) override { if(failWrite)return false; std::memcpy(data[n].data(),in,DURABLE_RECORD_SIZE); present[n]=true; return true; }
  bool remove(unsigned n) override { if(failRemove)return false; present[n]=false; return true; }
};
int main() {
  MemoryStore store; DurableQueue q(store); assert(q.recover());
  Packet p{1,1,1,2500,1000,1}; assert(q.append(p)==QueueResult::Added);
  assert(q.append(p)==QueueResult::Duplicate);
  Packet conflict=p; conflict.level=2; assert(q.append(conflict)==QueueResult::Conflict);
  Packet got{}; assert(q.peek(got) && got.seq==1);
  store.failWrite=true; p.seq=2; assert(q.append(p)==QueueResult::StorageError);
  store.failWrite=false; DurableQueue reboot(store); assert(reboot.recover());
  assert(reboot.peek(got) && got.seq==1); assert(reboot.append(p)==QueueResult::Added);
  store.failRemove=true; assert(!reboot.pop()); store.failRemove=false;
  DurableQueue again(store); assert(again.recover()); assert(again.peek(got) && got.seq==1);
  assert(again.pop()); assert(again.peek(got) && got.seq==2);
  for(unsigned n=0;n<DURABLE_SLOTS-1;n++){p.seq++;assert(again.append(p)==QueueResult::Added);}
  p.seq++; assert(again.append(p)==QueueResult::Full);
  store.data[1][0]^=0x80; DurableQueue corrupt(store); assert(!corrupt.recover());
  assert(corrupt.append(p)==QueueResult::StorageError);
  // Existing on-device telemetry can be replayed after upgrade, alongside
  // a measured drink whose ID and volume survive a restart.
  MemoryStore mixedStore;
  DurableQueue legacy(mixedStore);
  assert(legacy.recover() && legacy.append(p)==QueueResult::Added);
  using MixedOutbox = DurableOutbox<CloudOutboxRecord, CloudOutboxRecord>;
  MixedOutbox mixed(mixedStore);
  assert(mixed.recover());
  CloudOutboxRecord drink{{}, {0x11223344, p.session, p.seq, 123}};
  assert(mixed.append(drink)==QueueResult::Added);
  assert(mixed.append(drink)==QueueResult::Duplicate);
  auto changedDrink=drink;
  changedDrink.drink.volumeMl=124;
  assert(mixed.append(changedDrink)==QueueResult::Conflict);
  MixedOutbox rebootMixed(mixedStore);
  CloudOutboxRecord head{};
  assert(rebootMixed.recover() && rebootMixed.peek(head));
  assert(!head.isDrink() && head.telemetry.seq==p.seq);
  assert(rebootMixed.pop() && rebootMixed.peek(head));
  assert(head.isDrink() && CloudOutboxRecord::sameId(head,drink) && head.drink.volumeMl==123);
  uint8_t bytes[FRAME_SIZE];
  bool ack=false;
  CloudOutboxRecord::encodeRecord(head,bytes);
  assert(!decode(bytes,got,ack));
  assert(rebootMixed.pop() && !rebootMixed.peek(head));
  return 0;
}
