const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const filename = path.join(__dirname, 'kaew-wiring-data.cjs');
assert.ok(fs.existsSync(filename), 'A reviewable terminal-to-terminal wiring map must exist');
const data = require(filename);
assert.equal(data.status, 'proposal');
assert.equal(data.boards.gateway.left.length, 22);
assert.equal(data.boards.gateway.right.length, 22);
assert.equal(data.boards.node.left.length, 15);
assert.equal(data.boards.node.right.length, 15);
let total = 0;
for (const [boardId, board] of Object.entries(data.boards)) {
  const ends = new Set([...board.left, ...board.right].map(p => 'board.' + p));
  const devices = new Set(board.devices.map(d => d.id));
  assert.equal(devices.size, board.devices.length, 'Unique module ids');
  for (const d of board.devices) for (const p of d.pins) ends.add(d.id + '.' + p);
  const assigned = new Set();
  for (const c of board.connections) {
    assert.ok(ends.has(c.from), boardId + ' unknown source ' + c.from);
    assert.ok(ends.has(c.to), boardId + ' unknown destination ' + c.to);
    assert.ok(devices.has(c.device), 'Selectable device for every wire');
    assert.match(c.color, /^#[0-9a-f]{6}$/i);
    assert.ok(c.note, 'Explain what each connection does');
    for (const end of [c.from, c.to]) {
      if (!end.startsWith('board.GPIO')) continue;
      assert.ok(!assigned.has(end), 'GPIO assigned to more than one signal: ' + end);
      assigned.add(end);
      const pin = Number(end.slice(10));
      if (boardId === 'gateway') assert.ok(![0,3,19,20,35,36,37,38,45,46,48].includes(pin), 'Leave memory / boot / USB / LED pins free');
      if (c.status === 'hold') assert.match(c.note, /รอ|ตรวจ|ยืนยัน/);
    }
    total++;
  }
  assert.ok(board.connections.some(c => c.from === 'supply.5V' && c.to === 'board.5V'));
  assert.ok(board.connections.some(c => c.from === 'board.3V3' && c.to === 'rail.3V3'));
}
const gateway = data.boards.gateway.connections;
assert.ok(gateway.some(c => c.from === 'amp.SPK+' && c.to === 'speaker.+'));
assert.ok(gateway.some(c => c.from === 'amp.SPK-' && c.to === 'speaker.-'));
assert.ok(!gateway.some(c => c.device === 'speaker' && /GND/.test(c.from + c.to)), 'BTL speaker output must never be grounded');
assert.ok(data.boards.node.connections.some(c => c.from === 'pullup.B' && c.to === 'temperature.DQ'), 'DS18B20 needs a real pullup branch');
assert.ok(data.boards.node.connections.some(c => c.from === 'tds.OUT' && c.to === 'analog.IN'));
assert.ok(data.boards.node.connections.some(c => c.from === 'analog.OUT3V3' && c.to === 'board.GPIO34' && c.status === 'hold'));
assert.ok(gateway.filter(c => c.device === 'flow').every(c => c.status === 'hold'));
assert.ok(gateway.filter(c => c.device === 'pump').every(c => c.status === 'hold'));
console.log(JSON.stringify({wiring: 'valid', boards: Object.keys(data.boards).length, connections: total}));
