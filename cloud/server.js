import http from 'node:http';
import { readFile } from 'node:fs/promises';
import { join, extname } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(fileURLToPath(new URL('.', import.meta.url)), 'public');
const port = Number(process.env.PORT || 3000);
let latest = null;
const history = [];
const latestBySensor = Object.create(null);
const dashboardSensors = new Set(["HX711", "TDS", "Temperature", "Water Level"]);
const streams = new Set();

function sensorEvent() {
  return `data: ${JSON.stringify({ latest, latestBySensor, count: history.length })}\n\n`;
}

function openSensorStream(res) {
  res.writeHead(200, {
    'Content-Type': 'text/event-stream',
    'Cache-Control': 'no-cache, no-transform',
    'X-Accel-Buffering': 'no',
  });
  streams.add(res);
  const heartbeat = setInterval(() => {
    if (!res.write(': heartbeat\n\n')) res.destroy();
  }, 15000);
  res.on('close', () => {
    clearInterval(heartbeat);
    streams.delete(res);
  });
  res.write(sensorEvent());
}
const send = (res, status, body, type = 'application/json; charset=utf-8') => {
  res.writeHead(status, { 'Content-Type': type, 'Access-Control-Allow-Origin': '*' });
  res.end(type.startsWith('application/json') ? JSON.stringify(body) : body);
};

http.createServer(async (req, res) => {
  if (req.method === 'OPTIONS') { res.writeHead(204, { 'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Methods': 'GET,POST,OPTIONS', 'Access-Control-Allow-Headers': 'Content-Type' }); return res.end(); }
  const url = new URL(req.url, `http://${req.headers.host}`);
  if (url.pathname === '/api/sensors/events' && req.method === 'GET') return openSensorStream(res);
  if (url.pathname === '/api/sensors' && req.method === 'GET') return send(res, 200, { latest, latestBySensor, history });
  if (url.pathname === '/api/sensors' && req.method === 'POST') {
    let raw = '';
    for await (const chunk of req) raw += chunk;
    try {
      const data = JSON.parse(raw);
      const value = Number(data.value ?? data.hx711_raw);
      if (!Number.isFinite(value)) return send(res, 400, { error: 'ส่ง value เป็นตัวเลข' });
      latest = { value, unit: String(data.unit || 'raw'), sensor: String(data.sensor || 'HX711'), timestamp: new Date().toISOString() };
      if (dashboardSensors.has(latest.sensor)) latestBySensor[latest.sensor] = latest;
      history.push(latest); if (history.length > 100) history.shift();
      const event = sensorEvent();
      for (const stream of streams) {
        if (!stream.write(event)) stream.destroy();
      }
      return send(res, 201, latest);
    } catch { return send(res, 400, { error: 'JSON ไม่ถูกต้อง' }); }
  }
  const path = url.pathname === '/' ? '/index.html' : url.pathname;
  if (path.includes('..')) return send(res, 400, { error: 'Bad path' });
  try {
    const content = await readFile(join(root, path));
    const types = { '.html': 'text/html; charset=utf-8', '.css': 'text/css; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.svg': 'image/svg+xml' };
    send(res, 200, content, types[extname(path)] || 'application/octet-stream');
  } catch { send(res, 404, 'Not found', 'text/plain; charset=utf-8'); }
}).listen(port, '0.0.0.0', () => console.log(`Dashboard listening on ${port}`));
