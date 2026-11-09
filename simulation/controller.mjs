// Deterministic software model. Values are assumptions, not hardware measurements.
export function createSimulation({tankMl = 1500, flowMlPerMinute = 120} = {}) {
  if (!Number.isFinite(tankMl) || tankMl < 0 || !Number.isFinite(flowMlPerMinute) || flowMlPerMinute <= 0) throw new RangeError('invalid plant');
  // Two seconds is an illustrative timeout, not a measured hardware setting.
  const staleAfterS = 2;
  const state = {tankMl, cupMl: 0, cupPresent: false, pump: false, scaleOk: true, scaleUpdates: true, lastScaleSampleS: 0, stopPressed: false, fault: null, targetMl: 0, elapsed: 0, flowMlPerMinute, time: 0, events: []};
  const log = message => { state.events.unshift({time: state.time, message}); state.events.length = Math.min(state.events.length, 100); };
  const stop = reason => { state.pump = false; if (reason) {state.fault = reason; log(reason);} };
  const freshScale = () => state.scaleOk && state.time - state.lastScaleSampleS < staleAfterS;
  return {state,
    placeCup() { state.cupPresent = true; log('cup placed'); },
    removeCup() { state.cupPresent = false; stop('cup removed'); },
    pressStop() { state.stopPressed = true; stop('stop pressed'); },
    failScale() { state.scaleOk = false; stop('scale fault'); },
    reset() { if (state.stopPressed || !freshScale() || !state.cupPresent || state.tankMl <= 0) return false; state.fault = null; log('fault reset'); return true; },
    releaseStop() { state.stopPressed = false; },
    repairScale() { state.scaleOk = true; if (state.scaleUpdates) state.lastScaleSampleS = state.time; },
    pauseScaleUpdates() { state.scaleUpdates = false; log('scale updates paused'); },
    resumeScaleUpdates() { state.scaleUpdates = true; if (state.scaleOk) state.lastScaleSampleS = state.time; log('scale updates resumed'); },
    reboot() { state.pump = false; state.fault = 'reboot'; state.elapsed = 0; log('reboot: pump off'); },
    start(target) {
      if (!Number.isFinite(target) || target <= 0 || target > 300 || target <= state.cupMl || !state.cupPresent || state.stopPressed || !freshScale() || state.fault || state.tankMl <= 0) return false;
      state.targetMl = target; state.elapsed = 0; state.pump = true; log('pump started'); return true;
    },
    step(dt) {
      if (!Number.isFinite(dt) || dt < 0) throw new RangeError('invalid time');
      const before = state.time;
      const untilStale = state.scaleUpdates ? Infinity : Math.max(0, staleAfterS - (before - state.lastScaleSampleS));
      state.time += dt;
      if (state.scaleUpdates && state.scaleOk) state.lastScaleSampleS = state.time;
      if (!state.pump) return;
      if (!state.cupPresent || state.stopPressed || !state.scaleOk) { stop('interlock'); return; }
      const activeDt = Math.min(dt, untilStale);
      state.elapsed += activeDt; if (state.elapsed > 180) { stop('timeout'); return; }
      const amount = Math.min(state.flowMlPerMinute * activeDt / 60, state.tankMl, state.targetMl - state.cupMl);
      state.tankMl = Math.max(0, state.tankMl - amount); state.cupMl += amount;
      if (state.tankMl <= 0) stop('tank empty');
      else if (state.cupMl >= state.targetMl) {state.pump = false; log('target reached');}
      else if (dt >= untilStale) stop('scale stale');
    }
  };
}
