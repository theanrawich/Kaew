// Volatile in-browser demonstration. Not an authenticated transport, database,
// durable queue, or device safety controller.
export function createLocalPipeline({ capacity = 20, historyLimit = 100 } = {}) {
  if (!Number.isSafeInteger(capacity) || capacity < 1 || !Number.isSafeInteger(historyLimit) || historyLimit < 1) throw new RangeError('invalid limits');
  let online = true;
  const pending = [], history = [];
  const key = m => JSON.stringify([m.nodeId, m.sessionId, m.seq]);
  const valid = m => m && typeof m.nodeId === 'string' && m.nodeId.trim().length > 0 &&
    typeof m.sessionId === 'string' && m.sessionId.trim().length > 0 &&
    Number.isSafeInteger(m.seq) && m.seq >= 0 && Number.isFinite(m.timeS) && m.timeS >= 0 &&
    m.readings && Number.isFinite(m.readings.tankMl) && m.readings.tankMl >= 0;
  const clone = m => ({nodeId: m.nodeId, sessionId: m.sessionId, seq: m.seq, timeS: m.timeS, readings: {tankMl: m.readings.tankMl}});
  function store(m) { history.push(m); if (history.length > historyLimit) history.shift(); }
  return {
    receive(m) {
      if (!valid(m)) return 'invalid';
      if ([...pending, ...history].some(existing => key(existing) === key(m))) return 'duplicate';
      if (!online && pending.length >= capacity) return 'queue_full';
      const copy = clone(m);
      if (!online) { pending.push(copy); return 'buffered'; }
      store(copy); return 'forwarded';
    },
    setOnline(value) {
      if (typeof value !== 'boolean') throw new TypeError('online must be boolean');
      online = value;
      if (online) while (pending.length) store(pending.shift());
    },
    snapshot() { return {online, capacity, pending: pending.map(clone), history: history.map(clone)}; }
  };
}
