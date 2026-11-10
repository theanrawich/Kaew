import test from 'node:test';
import assert from 'node:assert/strict';
import {encodeFrame, decodeFrame, createWireReceiver} from './wire-codec.mjs';

const packet = {node:1, session:7, seq:0, centiC:2500, adc:1234, level:1};
test('unconnected ADC has an explicit unknown sentinel', () => {
  const unknown={...packet,adc:65535};
  assert.deepEqual(decodeFrame(encodeFrame(unknown)),{...unknown,ack:false});
  assert.throws(()=>encodeFrame({...packet,adc:4096}));
});
test('golden UART frame round trips and corruption is rejected', () => {
  const frame = encodeFrame(packet);
  assert.equal(Buffer.from(frame).toString('hex'), '4b570101010700000000000000c409d20401eb72');
  assert.deepEqual(decodeFrame(frame), {...packet, ack:false});
  frame[15] ^= 1; assert.equal(decodeFrame(frame), null);
});
test('retries do not refresh freshness and a session changes only after timeout', () => {
  const r = createWireReceiver();
  assert.equal(r.receive(encodeFrame(packet),100).status, 'accepted');
  assert.equal(r.receive(encodeFrame(packet),1000).status, 'duplicate');
  assert.equal(r.fresh(5100), false);
  assert.equal(r.receive(encodeFrame({...packet,session:8}), 5100).status, 'accepted');
  assert.equal(r.receive(encodeFrame(packet), 5101).status, 'session_mismatch');
});
test('sequence wraps without accepting an old pre-wrap packet', () => {
  const r=createWireReceiver(); const p={...packet,seq:0xffffffff};
  assert.equal(r.receive(encodeFrame(p),1).status,'accepted');
  assert.equal(r.receive(encodeFrame({...p,seq:0}),2).status,'accepted');
  assert.equal(r.receive(encodeFrame(p),3).status,'old');
});
