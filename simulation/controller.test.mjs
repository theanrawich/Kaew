import test from 'node:test';
import assert from 'node:assert/strict';
import { createSimulation } from './controller.mjs';

test('fills to target and stops without exceeding it', () => {
  const s = createSimulation(); s.placeCup(); assert.equal(s.start(200), true);
  for (let i = 0; i < 200; i++) s.step(1);
  assert.equal(s.state.pump, false); assert.equal(s.state.cupMl, 200);
});
test('rejects unsafe targets and absent cup', () => {
  const s = createSimulation(); assert.equal(s.start(100), false); s.placeCup();
  for (const n of [-1, 0, 301, NaN, Infinity]) assert.equal(s.start(n), false);
});
test('cup removal, physical stop, sensor failure and timeout stop the pump', () => {
  for (const fault of ['removeCup', 'pressStop', 'failScale', 'timeout']) {
    const s = createSimulation(); s.placeCup(); s.start(200);
    if (fault === 'timeout') s.step(181); else s[fault]();
    assert.equal(s.state.pump, false, fault);
    assert.equal(s.start(100), false, fault);
  }
});
test('empty tank stops and reboot never resumes pumping', () => {
  const s = createSimulation({tankMl: 2}); s.placeCup(); s.start(100); s.step(10);
  assert.equal(s.state.pump, false); assert.equal(s.state.tankMl, 0);
  const x = createSimulation(); x.placeCup(); x.start(200); x.reboot();
  assert.equal(x.state.pump, false);
});
test('invalid time cannot move water or bypass safety', () => {
  const s = createSimulation(); s.placeCup(); s.start(100);
  for (const dt of [-1, NaN, Infinity]) assert.throws(() => s.step(dt));
  assert.equal(s.state.cupMl, 0);
});

test('stale scale stops a running pump and requires fresh data plus reset', () => {
  const s = createSimulation(); s.placeCup(); s.start(100); s.pauseScaleUpdates();
  s.step(1); assert.equal(s.state.pump, true);
  s.step(1); assert.equal(s.state.pump, false); assert.equal(s.state.fault, 'scale stale');
  assert.equal(s.reset(), false);
  s.resumeScaleUpdates(); assert.equal(s.start(100), false);
  assert.equal(s.reset(), true); assert.equal(s.start(100), true);
});

test('stale scale blocks start even when the pump is idle', () => {
  const s = createSimulation(); s.placeCup(); s.pauseScaleUpdates(); s.step(2);
  assert.equal(s.start(100), false);
  assert.equal(s.state.pump, false);
});

test('large steps cannot move water past the simulated stale deadline', () => {
  const s = createSimulation(); s.placeCup(); s.start(100); s.pauseScaleUpdates(); s.step(10);
  assert.equal(s.state.fault, 'scale stale');
  assert.equal(s.state.cupMl, 4); // 120 mL/min for two simulated seconds.
});

test('a second start cannot reset the running pump timeout', () => {
  const s = createSimulation({flowMlPerMinute: 1});
  s.placeCup();
  assert.equal(s.start(200), true);
  s.step(179);
  assert.equal(s.start(200), false);
  s.step(2);
  assert.equal(s.state.pump, false);
  assert.equal(s.state.fault, 'timeout');
});
