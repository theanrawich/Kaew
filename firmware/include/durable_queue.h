#pragma once
#include <cstdint>
#include <cstring>
#include "wire_protocol.h"

// Storage adapter must provide atomic whole-slot write/remove semantics.
constexpr unsigned DURABLE_SLOTS=16, DURABLE_RECORD_SIZE=30;
struct SlotStore {
  virtual int read(unsigned slot, uint8_t *out)=0; // 0 empty, 1 record, -1 error
  virtual bool write(unsigned slot, const uint8_t *record)=0;
  virtual bool remove(unsigned slot)=0;
  virtual ~SlotStore() = default;
};
enum class QueueResult { Added, Duplicate, Conflict, Full, StorageError };
struct TelemetryQueueCodec {
  static void encodeRecord(const Packet &p, uint8_t *bytes) { encode(p, false, bytes); }
  static bool decodeRecord(const uint8_t *bytes, Packet &p) {
    bool ack = false;
    return decode(bytes, p, ack) && !ack;
  }
  static bool sameId(const Packet &a, const Packet &b) {
    return a.node == b.node && a.session == b.session && a.seq == b.seq;
  }
};

template<class Record, class Codec>
class DurableOutbox {
  SlotStore &store_; bool valid_=false; unsigned count_=0, first_=DURABLE_SLOTS, free_=DURABLE_SLOTS; uint64_t max_=0, min_=UINT64_MAX;
  static uint64_t ticket(const uint8_t *b) { uint64_t x=0; for(int i=0;i<8;i++) x|=uint64_t(b[i])<<(8*i); return x; }
  static bool checksumValid(const uint8_t *record) {
    return crc16(record, 28) == (uint16_t(record[28]) | (uint16_t(record[29]) << 8));
  }
public:
  explicit DurableOutbox(SlotStore &store):store_(store) {}
  bool recover() {
    valid_=false; count_=0; first_=free_=DURABLE_SLOTS; max_=0; min_=UINT64_MAX;
    for(unsigned n=0;n<DURABLE_SLOTS;n++) {
      uint8_t b[DURABLE_RECORD_SIZE]; int r=store_.read(n,b);
      if(r<0) return false;
      if(!r) { if(free_==DURABLE_SLOTS)free_=n; continue; }
      Record p{};
      if(!checksumValid(b) || !ticket(b) || !Codec::decodeRecord(b+8,p)) return false;
      uint64_t t=ticket(b); if(t<min_){min_=t;first_=n;} if(t>max_)max_=t; ++count_;
    }
    valid_=true; return true;
  }
  unsigned count() const { return count_; }
  bool healthy() const { return valid_; }
  QueueResult append(const Record &p) {
    if(!valid_)return QueueResult::StorageError;
    uint8_t frame[FRAME_SIZE]; Codec::encodeRecord(p,frame); Record check{};
    if(!Codec::decodeRecord(frame,check))return QueueResult::StorageError;
    for(unsigned n=0;n<DURABLE_SLOTS;n++) {
      uint8_t b[DURABLE_RECORD_SIZE]; int r=store_.read(n,b); if(r<0){valid_=false;return QueueResult::StorageError;}
      if(r) { Record other{}; if(!checksumValid(b) || !Codec::decodeRecord(b+8,other)){valid_=false;return QueueResult::StorageError;}
        if(Codec::sameId(other,p)) return std::memcmp(b+8,frame,FRAME_SIZE)==0 ? QueueResult::Duplicate : QueueResult::Conflict; }
    }
    if(free_==DURABLE_SLOTS)return QueueResult::Full;
    if(max_==UINT64_MAX)return QueueResult::StorageError;
    uint8_t record[DURABLE_RECORD_SIZE]{}; uint64_t t=max_+1;
    for(int i=0;i<8;i++)record[i]=uint8_t(t>>(8*i)); std::memcpy(record+8,frame,FRAME_SIZE);
    uint16_t crc=crc16(record,28); record[28]=uint8_t(crc); record[29]=uint8_t(crc>>8);
    if(!store_.write(free_,record))return QueueResult::StorageError;
    return recover() ? QueueResult::Added : QueueResult::StorageError;
  }
  bool peek(Record &p) {
    if(!valid_ || first_==DURABLE_SLOTS)return false;
    uint8_t b[DURABLE_RECORD_SIZE];
    if(store_.read(first_,b)!=1 || !checksumValid(b)) {valid_=false;return false;}
    return Codec::decodeRecord(b+8,p);
  }
  bool pop() {
    if(!valid_ || first_==DURABLE_SLOTS || !store_.remove(first_))return false;
    return recover();
  }
};

using DurableQueue = DurableOutbox<Packet, TelemetryQueueCodec>;
