import http from 'node:http';
import { readFile } from 'node:fs/promises';
import { join, extname } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(fileURLToPath(new URL('.', import.meta.url)), 'public');
const port = Number(process.env.PORT || 3000);
let latest = null;
const history = [];
const send = (res, status, body, type = 'application/json; charset=utf-8') => {
  res.writeHead(status, { 'Content-Type': type, 'Access-Control-Allow-Origin': '*' });
  res.end(type.startsWith('application/json') ? JSON.stringify(body) : body);
};

http.createServer(async (req, res) => {
  if (req.method === 'OPTIONS') { res.writeHead(204, { 'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Methods': 'GET,POST,OPTIONS', 'Access-Control-Allow-Headers': 'Content-Type' }); return res.end(); }
  const url = new URL(req.url, `http://${req.headers.host}`);
  if (url.pathname === '/api/sensors' && req.method === 'GET') return send(res, 200, { latest, history });
  if (url.pathname === '/api/sensors' && req.method === 'POST') {
    let raw = '';
    for await (const chunk of req) raw += chunk;
    try {
      const data = JSON.parse(raw);
      const value = Number(data.value ?? data.hx711_raw);
      if (!Number.isFinite(value)) return send(res, 400, { error: 'ส่ง value เป็นตัวเลข' });
      latest = { value, unit: String(data.unit || 'raw'), sensor: String(data.sensor || 'HX711'), timestamp: new Date().toISOString() };
      history.push(latest); if (history.length > 100) history.shift();
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
