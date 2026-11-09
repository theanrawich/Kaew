import test from 'node:test';
import assert from 'node:assert/strict';
import { createLocalPipeline } from './telemetry.mjs';

const sample = (seq, nodeId = 'node-1') => ({ nodeId, sessionId: 'sim-session', seq, timeS: seq, readings: { tankMl: 1000 - seq } });

test('forwards simulated readings and deduplicates retries', () => {
  const p = createLocalPipeline({ capacity: 2 });
  assert.equal(p.receive(sample(1)), 'forwarded');
  assert.equal(p.receive(sample(1)), 'duplicate');
  assert.equal(p.snapshot().history.length, 1);
  assert.equal(p.receive(sample(1, 'node-2')), 'forwarded');
  assert.deepEqual(p.snapshot().history.map(x => x.nodeId), ['node-1', 'node-2']);
});

test('buffers offline, rejects overflow, and replays accepted records once', () => {
  const p = createLocalPipeline({ capacity: 2 }); p.setOnline(false);
  assert.equal(p.receive(sample(1)), 'buffered');
  assert.equal(p.receive(sample(1)), 'duplicate');
  assert.equal(p.receive(sample(2)), 'buffered');
  assert.equal(p.receive(sample(3)), 'queue_full');
  assert.equal(p.snapshot().history.length, 0);
  p.setOnline(true);
  assert.deepEqual(p.snapshot().history.map(x => x.seq), [1, 2]);
  assert.equal(p.snapshot().pending.length, 0);
  assert.equal(p.receive(sample(3)), 'forwarded');
});

test('rejects malformed samples and isolates stored data from later mutation', () => {
  const p = createLocalPipeline({ capacity: 2 });
  for (const data of [sample(-1), {...sample(1), nodeId: ''}, {...sample(1), timeS: NaN}, {...sample(1), readings: {tankMl: Infinity}}]) {
    assert.equal(p.receive(data), 'invalid');
  }
  const m = sample(1); p.receive(m); m.readings.tankMl = 3;
  const snapshot = p.snapshot(); snapshot.history[0].readings.tankMl = 5;
  assert.equal(p.snapshot().history[0].readings.tankMl, 999);
});
