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
const voiceHistory = [];

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

function validGatewayWav(wav) {
  if (wav.length < 44 || wav.toString('ascii', 0, 4) !== 'RIFF' || wav.toString('ascii', 8, 12) !== 'WAVE') return false;
  const declaredLength = wav.readUInt32LE(4) + 8;
  if (declaredLength > wav.length || declaredLength < 44) return false;
  let format;
  let channels;
  let sampleRate;
  let byteRate;
  let blockAlign;
  let bitsPerSample;
  let dataLength;
  for (let offset = 12; offset + 8 <= declaredLength;) {
    const chunkId = wav.toString('ascii', offset, offset + 4);
    const chunkLength = wav.readUInt32LE(offset + 4);
    const chunkData = offset + 8;
    if (chunkData + chunkLength > declaredLength) return false;
    if (chunkId === 'fmt ' && chunkLength >= 16) {
      format = wav.readUInt16LE(chunkData);
      channels = wav.readUInt16LE(chunkData + 2);
      sampleRate = wav.readUInt32LE(chunkData + 4);
      byteRate = wav.readUInt32LE(chunkData + 8);
      blockAlign = wav.readUInt16LE(chunkData + 12);
      bitsPerSample = wav.readUInt16LE(chunkData + 14);
    }
    if (chunkId === 'data') dataLength = chunkLength;
    offset = chunkData + chunkLength + (chunkLength % 2);
  }
  return format === 1 && channels === 1 && sampleRate === 16000 && byteRate === 32000 && blockAlign === 2 && bitsPerSample === 16 && Number.isInteger(dataLength) && dataLength > 0 && dataLength % 2 === 0 && dataLength <= 16000 * 2 * 8;
}

async function readBody(req, maxBytes) {
  const chunks = [];
  let length = 0;
  for await (const chunk of req) {
    length += chunk.length;
    if (length > maxBytes) throw new RangeError('BODY_TOO_LARGE');
    chunks.push(chunk);
  }
  return Buffer.concat(chunks, length);
}

async function transcribeTyphoon(wav) {
  const form = new FormData();
  form.set('file', new Blob([wav], { type: 'audio/wav' }), 'gateway.wav');
  form.set('model', 'typhoon-asr-realtime');
  const response = await fetch('https://api.opentyphoon.ai/v1/audio/transcriptions', {
    method: 'POST',
    headers: { Authorization: `Bearer ${process.env.TYPHOON_API_KEY}` },
    body: form,
    signal: AbortSignal.timeout(60000),
  });
  const result = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(result.error?.message || result.error || 'Typhoon ASR ประมวลผลไม่สำเร็จ');
    error.status = response.status === 429 ? 429 : 502;
    throw error;
  }
  const text = String(result.text || '').trim();
  if (!text) {
    const error = new Error('ไม่พบคำพูดในเสียงที่ส่งมา');
    error.status = 422;
    throw error;
  }
  return text;
}

http.createServer(async (req, res) => {
  if (req.method === 'OPTIONS') { res.writeHead(204, { 'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Methods': 'GET,POST,OPTIONS', 'Access-Control-Allow-Headers': 'Authorization, Content-Type' }); return res.end(); }
  const url = new URL(req.url, `http://${req.headers.host}`);
  if (url.pathname === '/api/sensors/events' && req.method === 'GET') return openSensorStream(res);
  if (url.pathname === '/api/stt/typhoon' && req.method === 'POST') {
    const deviceToken = process.env.KAEW_DEVICE_TOKEN;
    if (!deviceToken) return send(res, 503, { error: 'เซิร์ฟเวอร์ยังไม่ได้ตั้งค่า KAEW_DEVICE_TOKEN' });
    const bearer = /^Bearer\s+(.+)$/i.exec(req.headers.authorization || '');
    if (!bearer || bearer[1] !== deviceToken) return send(res, 401, { error: 'Bearer token ไม่ถูกต้อง' });
    if (!process.env.TYPHOON_API_KEY) return send(res, 503, { error: 'เซิร์ฟเวอร์ยังไม่ได้ตั้งค่า TYPHOON_API_KEY' });
    let wav;
    try { wav = await readBody(req, 300 * 1024); }
    catch (error) {
      if (error instanceof RangeError) return send(res, 413, { error: 'WAV ต้องมีความยาวไม่เกิน 8 วินาที' });
      return send(res, 400, { error: 'อ่านไฟล์ WAV ไม่สำเร็จ' });
    }
    if (!validGatewayWav(wav)) return send(res, 400, { error: 'WAV ไม่ถูกต้อง ต้องเป็น PCM 16 บิต mono 16 kHz และยาวไม่เกิน 8 วินาที' });
    try {
      const text = await transcribeTyphoon(wav);
      const item = { text, timestamp: new Date().toISOString() };
      voiceHistory.unshift(item);
      if (voiceHistory.length > 50) voiceHistory.length = 50;
      return send(res, 201, item);
    } catch (error) {
      const status = error.name === 'TimeoutError' ? 504 : (error.status || 502);
      const message = error.name === 'TimeoutError' ? 'Typhoon ASR ใช้เวลานานเกินกำหนด' : error.message;
      return send(res, status, { error: message });
    }
  }
  if (url.pathname === '/api/voice' && req.method === 'GET') {
    res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store', 'Access-Control-Allow-Origin': '*' });
    return res.end(JSON.stringify({ history: voiceHistory }));
  }
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
  const path = url.pathname === '/' || url.pathname === '/voice' ? '/index.html' : url.pathname;
  if (path.includes('..')) return send(res, 400, { error: 'Bad path' });
  try {
    const content = await readFile(join(root, path));
    const types = { '.html': 'text/html; charset=utf-8', '.css': 'text/css; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.svg': 'image/svg+xml' };
    send(res, 200, content, types[extname(path)] || 'application/octet-stream');
  } catch { send(res, 404, 'Not found', 'text/plain; charset=utf-8'); }
}).listen(port, '0.0.0.0', () => console.log(`Dashboard listening on ${port}`));
