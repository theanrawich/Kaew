// UART v1 codec shared semantically with firmware/include/wire_protocol.h.
export function crc16(bytes) {
  let c=0xffff; for (const byte of bytes) { c ^= byte << 8; for (let i=0;i<8;i++) c=((c & 0x8000) ? (c<<1)^0x1021 : c<<1)&0xffff; } return c;
}
function valid(p) { return p && p.node===1 && Number.isInteger(p.session) && p.session>0 && p.session<=0xffffffff && Number.isInteger(p.seq) && p.seq>=0 && p.seq<=0xffffffff && Number.isInteger(p.centiC) && (p.centiC===-32768 || (p.centiC>=-5500 && p.centiC<=12500)) && Number.isInteger(p.adc) && ((p.adc>=0 && p.adc<=4095) || p.adc===65535) && Number.isInteger(p.level) && p.level>=0 && p.level<=2; }
export function encodeFrame(p, ack=false) {
  if (!valid(p) || typeof ack !== 'boolean') throw new TypeError('invalid packet');
  const b=new Uint8Array(20), v=new DataView(b.buffer); b.set([0x4b,0x57,1,ack?2:1,p.node]);
  v.setUint32(5,p.session,true); v.setUint32(9,p.seq,true); v.setInt16(13,p.centiC,true); v.setUint16(15,p.adc,true); b[17]=p.level; v.setUint16(18,crc16(b.subarray(0,18)),true); return b;
}
export function decodeFrame(b) {
  if (!(b instanceof Uint8Array) || b.length!==20 || b[0]!==0x4b || b[1]!==0x57 || b[2]!==1 || ![1,2].includes(b[3])) return null;
  const v=new DataView(b.buffer,b.byteOffset,b.byteLength); if (v.getUint16(18,true)!==crc16(b.subarray(0,18))) return null;
  const p={node:b[4],session:v.getUint32(5,true),seq:v.getUint32(9,true),centiC:v.getInt16(13,true),adc:v.getUint16(15,true),level:b[17]};
  return valid(p) ? {...p,ack:b[3]===2} : null;
}
export function createWireReceiver() {
  let latest=null, at=0;
  const fresh = now => latest!==null && Number.isInteger(now) && now>=0 && now<=0xffffffff && ((now-at)>>>0)<5000;
  return {fresh, snapshot:()=>latest && {...latest,receivedAt:at}, receive(frame,now) {
    const p=decodeFrame(frame); if (!p || p.ack || !Number.isInteger(now) || now<0 || now>0xffffffff) return {status:'invalid'};
    if (latest && p.session!==latest.session && fresh(now)) return {status:'session_mismatch'};
    if (latest && p.session===latest.session) { if (p.seq===latest.seq) return {status:'duplicate',ack:encodeFrame(p,true)}; if (((p.seq-latest.seq)>>>0)>=0x80000000) return {status:'old'}; }
    latest=p; at=now; return {status:'accepted',ack:encodeFrame(p,true)};
  }};
}
