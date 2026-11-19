import http from 'node:http';
import { readFile } from 'node:fs/promises';
import { join, extname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { EdgeTTS } from 'node-edge-tts';
import { MPEGDecoder } from 'mpg123-decoder';

const root = join(fileURLToPath(new URL('.', import.meta.url)), 'public');
const port = Number(process.env.PORT || 3000);
let latest = null;
const history = [];
const latestBySensor = Object.create(null);
const dashboardSensors = new Set(["HX711", "TDS", "Temperature", "Water Level"]);
const streams = new Set();
const voiceHistory = [];
const ttsQueue = [];
let ttsPending = 0;
let nextTtsId = 1;

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

async function synthesizeEdgeWav(text, voice) {
  const edgeTts = new EdgeTTS({
    voice,
    lang: 'th-TH',
    timeout: 30000,
  });
  const mp3Chunks = [];
  let mp3Length = 0;
  for await (const chunk of edgeTts.streamAudio(text)) {
    if (!Buffer.isBuffer(chunk)) continue;
    mp3Length += chunk.length;
    if (mp3Length > 4 * 1024 * 1024) throw new Error('ไฟล์เสียงที่สร้างมีขนาดใหญ่เกินไป');
    mp3Chunks.push(chunk);
  }
  if (!mp3Length) throw new Error('Edge TTS ไม่ได้ส่งข้อมูลเสียงกลับมา');
  const decoder = new MPEGDecoder();
  await decoder.ready;
  let decoded;
  try { decoded = decoder.decode(Buffer.concat(mp3Chunks, mp3Length)); }
  finally { decoder.free(); }
  const channels = decoded.channelData;
  if (!decoded.samplesDecoded || !channels.length) throw new Error('ถอดรหัสเสียง Edge TTS ไม่สำเร็จ');
  const sourceRate = decoded.sampleRate;
  const sourceLength = decoded.samplesDecoded;
  const targetLength = Math.floor(sourceLength * 16000 / sourceRate);
  const pcm = Buffer.alloc(targetLength * 2);
  for (let i = 0; i < targetLength; i++) {
    const sourcePosition = i * sourceRate / 16000;
    const leftIndex = Math.min(Math.floor(sourcePosition), sourceLength - 1);
    const rightIndex = Math.min(leftIndex + 1, sourceLength - 1);
    const fraction = sourcePosition - leftIndex;
    let sample = 0;
    for (const channel of channels) sample += channel[leftIndex] * (1 - fraction) + channel[rightIndex] * fraction;
    sample /= channels.length;
    const value = Math.max(-1, Math.min(1, sample));
    pcm.writeInt16LE(value < 0 ? value * 0x8000 : value * 0x7fff, i * 2);
  }
  const wavHeader = Buffer.alloc(44);
  wavHeader.write('RIFF', 0); wavHeader.writeUInt32LE(36 + pcm.length, 4); wavHeader.write('WAVEfmt ', 8);
  wavHeader.writeUInt32LE(16, 16); wavHeader.writeUInt16LE(1, 20); wavHeader.writeUInt16LE(1, 22);
  wavHeader.writeUInt32LE(16000, 24); wavHeader.writeUInt32LE(32000, 28); wavHeader.writeUInt16LE(2, 32); wavHeader.writeUInt16LE(16, 34);
  wavHeader.write('data', 36); wavHeader.writeUInt32LE(pcm.length, 40);
  return Buffer.concat([wavHeader, pcm]);
}

http.createServer(async (req, res) => {
  if (req.method === 'OPTIONS') { res.writeHead(204, { 'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Methods': 'GET,POST,OPTIONS', 'Access-Control-Allow-Headers': 'Authorization, Content-Type' }); return res.end(); }
  const url = new URL(req.url, `http://${req.headers.host}`);
  if (url.pathname === '/api/sensors/events' && req.method === 'GET') return openSensorStream(res);
  if (url.pathname === '/api/tts' && req.method === 'POST') {
    let raw;
    try { raw = await readBody(req, 16 * 1024); }
    catch (error) {
      return error instanceof RangeError
        ? send(res, 413, { error: 'คำขอยาวเกินไป' })
        : send(res, 400, { error: 'อ่านคำขอไม่สำเร็จ' });
    }
    let data;
    try { data = JSON.parse(raw.toString('utf8')); }
    catch { return send(res, 400, { error: 'JSON ไม่ถูกต้อง' }); }
    const text = typeof data?.text === 'string' ? data.text.trim() : '';
    const voice = String(data?.voice || 'th-TH-PremwadeeNeural');
    const supportedVoices = new Set(['th-TH-PremwadeeNeural', 'th-TH-NiwatNeural']);
    if (!text) return send(res, 400, { error: 'กรุณาพิมพ์ข้อความก่อนสร้างเสียง' });
    if (text.length > 2000) return send(res, 400, { error: 'ข้อความยาวได้ไม่เกิน 2000 ตัวอักษร' });
    if (!supportedVoices.has(voice)) return send(res, 400, { error: 'ไม่รองรับเสียงที่เลือก' });
    if (ttsQueue.length + ttsPending >= 10) return send(res, 429, { error: 'คิวเสียงเต็ม กรุณารอให้ Gateway รับเสียงก่อน' });
    ttsPending += 1;
    try {
      const audio = await synthesizeEdgeWav(text, voice);
      const item = { id: String(nextTtsId++), text, voice, audio, createdAt: new Date().toISOString() };
      ttsQueue.push(item);
      return send(res, 202, { id: item.id, status: 'queued', queueLength: ttsQueue.length });
    } catch (error) {
      console.error('Edge TTS synthesis failed:', error.message);
      return send(res, 502, { error: 'Edge TTS สร้างเสียงไม่สำเร็จ ลองใหม่อีกครั้ง' });
    } finally { ttsPending -= 1; }
  }
  if (url.pathname === '/api/tts/next' && req.method === 'GET') {
    const deviceToken = process.env.KAEW_DEVICE_TOKEN;
    if (!deviceToken) return send(res, 503, { error: 'เซิร์ฟเวอร์ยังไม่ได้ตั้งค่า KAEW_DEVICE_TOKEN' });
    const bearer = /^Bearer\s+(.+)$/i.exec(req.headers.authorization || '');
    if (!bearer || bearer[1] !== deviceToken) return send(res, 401, { error: 'Bearer token ไม่ถูกต้อง' });
    const item = ttsQueue.shift();
    if (!item) { res.writeHead(204, { 'Cache-Control': 'no-store' }); return res.end(); }
    res.writeHead(200, {
      'Content-Type': 'audio/wav',
      'Content-Length': item.audio.length,
      'Cache-Control': 'no-store',
      'X-TTS-Job-Id': item.id,
      'X-TTS-Voice': item.voice,
      'Access-Control-Allow-Origin': '*',
      'X-Content-Type-Options': 'nosniff',
    });
    return res.end(item.audio);
  }
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
  const path = url.pathname === '/' || url.pathname === '/voice' || url.pathname === '/tts' ? '/index.html' : url.pathname;
  if (path.includes('..')) return send(res, 400, { error: 'Bad path' });
  try {
    const content = await readFile(join(root, path));
    const types = { '.html': 'text/html; charset=utf-8', '.css': 'text/css; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.svg': 'image/svg+xml' };
    send(res, 200, content, types[extname(path)] || 'application/octet-stream');
  } catch { send(res, 404, 'Not found', 'text/plain; charset=utf-8'); }
}).listen(port, '0.0.0.0', () => console.log(`Dashboard listening on ${port}`));
