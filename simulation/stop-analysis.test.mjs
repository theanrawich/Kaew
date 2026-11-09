import test from 'node:test';
import assert from 'node:assert/strict';
import { estimateStop } from './stop-analysis.mjs';

test('sampling, controller latency and residual flow add to delivered volume', () => {
  const r = estimateStop({targetMl: 100, flowMlMin: 120, sampleIntervalS: 1.5, responseDelayS: 0.25, residualMl: 2, tankMl: 500});
  // The target is reached at 50 s, first observed at 51 s; then 0.25 s and 2 mL remain.
  assert.equal(r.targetReachedS, 50);
  assert.equal(r.stopCommandS, 51.25);
  assert.equal(r.deliveredMl, 104.5);
  assert.equal(r.overshootMl, 4.5);
  assert.equal(r.targetReached, true);
});

test('reservoir depletion prevents an assumed target or residual volume', () => {
  const r = estimateStop({targetMl: 100, flowMlMin: 120, sampleIntervalS: 1, responseDelayS: 1, residualMl: 5, tankMl: 90});
  assert.equal(r.deliveredMl, 90);
  assert.equal(r.targetReached, false);
  assert.equal(r.stopCommandS, null);
  assert.equal(r.overshootMl, 0);
});

test('validates unsafe inputs and handles an exact sample boundary', () => {
  const base = {targetMl: 100, flowMlMin: 120, sampleIntervalS: 1, responseDelayS: 0, residualMl: 0, tankMl: 500};
  assert.equal(estimateStop(base).deliveredMl, 100);
  for (const input of [{flowMlMin: 0}, {sampleIntervalS: 0}, {residualMl: -1}, {responseDelayS: Infinity}, {tankMl: NaN}, {targetMl: 0}]) {
    assert.throws(() => estimateStop({...base, ...input}), RangeError);
  }
});
