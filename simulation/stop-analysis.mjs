// Analytical illustration only: fixed flow, instantaneous samples and fixed residual.
// This is not a pump controller or a model of measured hardware.
export function estimateStop({targetMl, flowMlMin, sampleIntervalS, responseDelayS, residualMl, tankMl}) {
  const inputs = {targetMl, flowMlMin, sampleIntervalS, responseDelayS, residualMl, tankMl};
  if (Object.values(inputs).some(n => !Number.isFinite(n)) || targetMl <= 0 || flowMlMin <= 0 || sampleIntervalS <= 0 || responseDelayS < 0 || residualMl < 0 || tankMl < 0) {
    throw new RangeError('invalid scenario');
  }
  const rate = flowMlMin / 60;
  const theoreticalTargetS = targetMl / rate;
  const depletionS = tankMl / rate;
  if (depletionS < theoreticalTargetS) return {targetReached: false, targetReachedS: null, stopCommandS: null, deliveredMl: tankMl, overshootMl: 0, stoppedBy: 'empty'};
  const observedS = Math.ceil(theoreticalTargetS / sampleIntervalS) * sampleIntervalS;
  const requestedStopS = observedS + responseDelayS;
  if (!Number.isFinite(requestedStopS)) throw new RangeError('scenario exceeds numeric range');
  if (depletionS < requestedStopS) return {targetReached: true, targetReachedS: theoreticalTargetS, stopCommandS: null, deliveredMl: tankMl, overshootMl: Math.max(0, tankMl - targetMl), stoppedBy: 'empty'};
  const deliveredMl = Math.min(tankMl, requestedStopS * rate + residualMl);
  return {targetReached: true, targetReachedS: theoreticalTargetS, stopCommandS: requestedStopS, deliveredMl, overshootMl: Math.max(0, deliveredMl - targetMl), stoppedBy: 'target'};
}
