#pragma once
#include <cstdint>
#include <cstring>

// Dedicated UART: CRC detects accidental corruption, it is not authentication.
constexpr unsigned FRAME_SIZE = 20;
struct Packet { uint8_t node; uint32_t session, seq; int16_t centiC; uint16_t adc; uint8_t level; };
inline uint16_t crc16(const uint8_t *p, unsigned len) {
  uint16_t c = 0xffff; while (len--) { c ^= uint16_t(*p++) << 8; for (int i=0;i<8;++i) c = (c & 0x8000) ? uint16_t((c<<1)^0x1021) : uint16_t(c<<1); } return c;
}
inline void put32(uint8_t *b, uint32_t x) { for (int i=0;i<4;++i) b[i]=uint8_t(x>>(8*i)); }
inline uint32_t get32(const uint8_t *b) { uint32_t x=0; for(int i=0;i<4;++i) x |= uint32_t(b[i])<<(8*i); return x; }
inline void encode(const Packet &p, bool ack, uint8_t *b) {
  b[0]=0x4b; b[1]=0x57; b[2]=1; b[3]=ack?2:1; b[4]=p.node; put32(b+5,p.session); put32(b+9,p.seq);
  uint16_t t=static_cast<uint16_t>(p.centiC); b[13]=uint8_t(t); b[14]=uint8_t(t>>8);
  b[15]=uint8_t(p.adc); b[16]=uint8_t(p.adc>>8); b[17]=p.level;
  uint16_t c=crc16(b,18); b[18]=uint8_t(c); b[19]=uint8_t(c>>8);
}
inline bool decode(const uint8_t *b, Packet &p, bool &ack) {
  if(b[0]!=0x4b || b[1]!=0x57 || b[2]!=1 || (b[3]!=1 && b[3]!=2) ||
     crc16(b,18)!=(uint16_t(b[18]) | (uint16_t(b[19])<<8))) return false;
  Packet q{b[4],get32(b+5),get32(b+9),int16_t(uint16_t(b[13])|(uint16_t(b[14])<<8)),uint16_t(uint16_t(b[15])|(uint16_t(b[16])<<8)),b[17]};
  if(q.node!=1 || q.session==0 || (q.adc>4095 && q.adc!=UINT16_MAX) || q.level>2 || (q.centiC != INT16_MIN && (q.centiC < -5500 || q.centiC > 12500))) return false;
  p=q; ack=b[3]==2; return true;
}
class FrameParser {
  uint8_t buf_[FRAME_SIZE]{}; unsigned size_=0;
public:
  bool push(uint8_t byte, Packet &p, bool &ack) {
    if(size_ < FRAME_SIZE) buf_[size_++]=byte;
    while(size_ && (buf_[0]!=0x4b || (size_>1 && buf_[1]!=0x57))) { std::memmove(buf_,buf_+1,--size_); }
    if(size_ < FRAME_SIZE) return false;
    if(decode(buf_,p,ack)) { size_=0; return true; }
    std::memmove(buf_,buf_+1,--size_); return false;
  }
};
enum class Receive { Accepted, Duplicate, Old, SessionMismatch };
class Receiver {
  bool have_=false; Packet latest_{}; uint32_t at_=0;
public:
  bool fresh(uint32_t now) const { return have_ && uint32_t(now-at_) < 5000; }
  uint32_t receivedAt() const { return at_; }
  const Packet &latest() const { return latest_; }
  Receive accept(const Packet &p,uint32_t now) {
    if(have_ && p.session!=latest_.session && fresh(now)) return Receive::SessionMismatch;
    if(have_ && p.session==latest_.session) {
      if(p.seq==latest_.seq) return Receive::Duplicate;
      if(uint32_t(p.seq-latest_.seq)>=0x80000000u) return Receive::Old;
    }
    have_=true; latest_=p; at_=now; return Receive::Accepted;
  }
};
class Sender {
  Packet packet_{}; bool pending_=false; unsigned attempts_=0; uint32_t sentAt_=0;
public:
  void begin(const Packet &p,uint32_t) { packet_=p; pending_=true; attempts_=0; }
  bool pending() const { return pending_; }
  bool due(uint32_t now) const { return pending_ && (attempts_==0 || uint32_t(now-sentAt_)>=500); }
  void sent(uint32_t now) { ++attempts_; sentAt_=now; }
  bool expired(uint32_t now) const { return pending_ && attempts_>=4 && uint32_t(now-sentAt_)>=500; }
  void drop() { pending_=false; }
  bool acknowledge(uint32_t session,uint32_t seq) { if(!pending_ || packet_.session!=session || packet_.seq!=seq) return false; pending_=false; return true; }
  const Packet &packet() const { return packet_; }
};
