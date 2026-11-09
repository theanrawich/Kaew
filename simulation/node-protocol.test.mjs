import test from 'node:test';
import assert from 'node:assert/strict';
import {createReceiver} from './node-protocol.mjs';

const sample = () => ({version: 1, nodeId: 'node-1', sessionId: 'boot-1', seq: 0,
  readings: {level: 'wet', temperatureC: 25, tdsRaw: 1200}});

test('valid readings are acknowledged and retries do not apply twice', () => {
  const r = createReceiver(); const m = sample();
  assert.equal(r.receive(m, 10).status, 'accepted');
  assert.equal(r.receive(m, 11).status, 'duplicate');
  assert.equal(r.snapshot().readings.level, 'wet');
  assert.equal(r.snapshot().receivedAt, 10);
});

test('invalid data and out-of-order packets do not refresh the safety reading', () => {
  const r = createReceiver(); const m = sample();
  r.receive({...m, seq: 2}, 10);
  assert.equal(r.receive({...m, seq: 1}, 11).status, 'old');
  assert.equal(r.receive({...m, seq: 3, readings: {...m.readings, level: '75%'}}, 12).status, 'invalid');
  assert.equal(r.snapshot().receivedAt, 10);
  assert.equal(r.isFresh(15, 5), false);
});

test('a new boot session requires explicit enrollment and cannot replay the retired session', () => {
  const r = createReceiver(); const m = sample(); r.receive(m, 1);
  assert.equal(r.receive({...m, sessionId: 'boot-2'}, 2).status, 'session_mismatch');
  r.enroll('node-1', 'boot-2');
  assert.equal(r.receive({...m, sessionId: 'boot-2'}, 3).status, 'accepted');
  assert.equal(r.receive({...m, seq: 1}, 4).status, 'session_mismatch');
});
