// Simulation-only message contract; this does not authenticate a node or implement transport.
const identifier = s => typeof s === 'string' && /^[A-Za-z0-9_-]{1,32}$/.test(s);
const valid = m => m && m.version === 1 && identifier(m.nodeId) && identifier(m.sessionId) &&
  Number.isSafeInteger(m.seq) && m.seq >= 0 && m.readings &&
  ['wet', 'dry', 'unknown'].includes(m.readings.level) &&
  Number.isFinite(m.readings.temperatureC) && m.readings.temperatureC >= -55 && m.readings.temperatureC <= 125 &&
  Number.isInteger(m.readings.tdsRaw) && m.readings.tdsRaw >= 0 && m.readings.tdsRaw <= 4095;

export function createReceiver() {
  let nodeId = null, sessionId = null, lastSeq = -1, current = null;
  return {
    enroll(node, session) {
      if (!identifier(node) || !identifier(session)) throw new TypeError('invalid enrollment');
      nodeId = node; sessionId = session; lastSeq = -1; current = null;
    },
    receive(message, receivedAt) {
      if (!valid(message) || !Number.isFinite(receivedAt) || receivedAt < 0 || (current && receivedAt < current.receivedAt)) return {status: 'invalid'};
      if (nodeId === null) { nodeId = message.nodeId; sessionId = message.sessionId; }
      if (message.nodeId !== nodeId || message.sessionId !== sessionId) return {status: 'session_mismatch'};
      if (message.seq === lastSeq) return {status: 'duplicate', ack: lastSeq};
      if (message.seq < lastSeq) return {status: 'old'};
      lastSeq = message.seq;
      current = {nodeId, sessionId, seq: lastSeq, receivedAt, readings: {...message.readings}};
      return {status: 'accepted', ack: lastSeq};
    },
    snapshot() { return current ? {...current, readings: {...current.readings}} : null; },
    isFresh(now, maxAge) {
      return !!current && Number.isFinite(now) && Number.isFinite(maxAge) && maxAge > 0 && now >= current.receivedAt && now - current.receivedAt < maxAge;
    }
  };
}
