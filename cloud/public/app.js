const $ = (id) => document.getElementById(id);
const formatTime = (value) => new Date(value).toLocaleString('th-TH', { dateStyle: 'medium', timeStyle: 'medium' });
function renderTranscripts(items = []) {
  $('voice-count').textContent = String(items.length);
  if (items.length === 0) {
    const empty = document.createElement('div');
    empty.className = 'voice-empty';
    const icon = document.createElement('span'); icon.className = 'empty-wave'; icon.textContent = '〰';
    const title = document.createElement('b'); title.textContent = 'ยังไม่มีข้อความถอดเสียง';
    const hint = document.createElement('span'); hint.textContent = 'เมื่อ Gateway ส่งเสียงมา ข้อความจะแสดงที่นี่';
    empty.append(icon, title, hint);
    $('transcript-list').replaceChildren(empty);
    return;
  }
  const cards = items.map((item) => {
    const card = document.createElement('article');
    card.className = 'transcript-card';
    const message = document.createElement('p');
    message.className = 'transcript-text';
    message.textContent = item.text;
    const meta = document.createElement('div');
    meta.className = 'transcript-meta';
    const mark = document.createElement('span');
    mark.className = 'transcript-mark';
    mark.textContent = '◖';
    const label = document.createElement('span');
    label.textContent = formatTime(item.timestamp);
    meta.append(mark, label);
    card.append(message, meta);
    return card;
  });
  $('transcript-list').replaceChildren(...cards);
}
async function loadTranscripts() {
  try {
    const response = await fetch('/api/voice');
    if (!response.ok) throw new Error('เชื่อมต่อไม่ได้');
    const data = await response.json();
    renderTranscripts(data.history || []);
    $('voice-status').querySelector('span').textContent = data.history?.length ? 'รับข้อความจาก Gateway แล้ว' : 'รอรับเสียงจาก Gateway';
  } catch { $('voice-status').querySelector('span').textContent = 'เชื่อมต่อไม่ได้'; }
}
if (location.pathname === '/voice') {
  loadTranscripts();
  setInterval(loadTranscripts, 2000);
}
function drawRows(target, rows, columns) {
  if (!rows.length) { target.innerHTML = `<tr><td colspan="${columns}" class="empty">ยังไม่มีข้อมูลจากเซนเซอร์</td></tr>`; return; }
  target.innerHTML = rows.map((r, i) => `<tr>${columns === 4 ? `<td>${r.sensor}</td><td><b>${Number(r.value).toLocaleString()}</b></td><td>${r.unit}</td><td>${formatTime(r.timestamp)}</td>` : `<td>${rows.length - i}</td><td>${r.sensor}</td><td><b>${Number(r.value).toLocaleString()}</b></td><td>${r.unit}</td><td>${formatTime(r.timestamp)}</td>`}</tr>`).join('');
}
function showWeight(id, value, unit) {
  const label = document.createElement('small');
  label.textContent = unit;
  $(id).replaceChildren(`${value} `, label);
}

const sensorCards = {
  hx711: { value: 'hx711-value', name: 'hx711-name', time: 'hx711-time', unit: 'g', match: /hx711|weight|load.?cell/i },
  tds: { value: 'tds-value', name: 'tds-name', time: 'tds-time', unit: 'ADC', match: /tds/i },
  temp: { value: 'temp-value', name: 'temp-name', time: 'temp-time', unit: '°C', match: /temp|thermo/i },
  water: { value: 'water-value', name: 'water-name', time: 'water-time', match: /water.?level|water|level|float.?switch/i },
};

function identifySensor(reading) {
  const name = String(reading.sensor || '').trim();
  const unit = String(reading.unit || '').trim().toLowerCase();
  for (const [key, card] of Object.entries(sensorCards)) {
    if (card.match.test(name) || (key === 'tds' && unit === 'ppm') || (key === 'temp' && ['°c', 'c', '℃'].includes(unit))) return key;
  }
  return null;
}

function updateSensorCard(key, reading) {
  const card = sensorCards[key];
  if (key === 'water') {
    const value = reading.value;
    const hasWater = value === true || value === 1 || /^(1|true|yes|มีน้ำ|น้ำมี|wet|water)$/i.test(String(value).trim());
    const noWater = value === false || value === 0 || /^(0|false|no|ไม่มีน้ำ|แห้ง|dry|empty)$/i.test(String(value).trim());
    const display = $(card.value);
    display.textContent = hasWater ? 'มีน้ำ' : noWater ? 'ไม่มีน้ำ' : 'ไม่ทราบสถานะ';
    display.classList.toggle('has-water', hasWater);
    display.classList.toggle('no-water', noWater);
    display.classList.toggle('unknown', !hasWater && !noWater);
    $(card.name).textContent = reading.sensor || 'Water Level';
    $(card.time).textContent = formatTime(reading.timestamp);
    return;
  }
  const unit = reading.unit || card.unit;
  showWeight(card.value, Number(reading.value).toLocaleString(), unit);
  $(card.name).textContent = reading.sensor || key.toUpperCase();
  $(card.time).textContent = formatTime(reading.timestamp);
}

function render({ latest, latestBySensor = {}, count }) {
  $('device-count').innerHTML = `${latest ? '1' : '0'} <small>ตัว</small>`;
  $('reading-count').innerHTML = `${count} <small>ครั้ง</small>`;
  if (latest) {
    const value = Number(latest.value).toLocaleString();
    showWeight('dash-value', value, latest.unit);
    $('dash-time').textContent = `รับข้อมูล ${formatTime(latest.timestamp)}`;
  }
  for (const reading of [...Object.values(latestBySensor), latest].filter(Boolean)) {
    const key = identifySensor(reading);
    if (key) updateSensorCard(key, reading);
  }
}
const sensorEvents = new EventSource('/api/sensors/events');
sensorEvents.onmessage = ({ data }) => render(JSON.parse(data));
sensorEvents.onopen = () => { $('sensor-status').textContent = 'เชื่อมต่อแล้ว'; };
sensorEvents.onerror = () => { $('sensor-status').textContent = 'กำลังเชื่อมต่อใหม่'; };
function navigate(view) {
  const current = ['dashboard', 'sensor', 'voice'].includes(view) ? view : 'dashboard';
  for (const page of ['dashboard', 'sensor', 'voice']) $(`${page}-view`).classList.toggle('hidden', current !== page);
  $('crumb').textContent = current[0].toUpperCase() + current.slice(1);
  document.querySelectorAll('.nav-link').forEach((link) => link.classList.toggle('active', link.dataset.view === current));
}
document.querySelectorAll('[data-view]').forEach((link) => link.addEventListener('click', (event) => { event.preventDefault(); navigate(link.dataset.view); history.replaceState(null, '', link.dataset.view === 'voice' ? '/voice' : `/#${link.dataset.view}`); }));
document.querySelectorAll('[data-go]').forEach((button) => button.addEventListener('click', () => { navigate(button.dataset.go); history.replaceState(null, '', `/#${button.dataset.go}`); }));
navigate(location.pathname === '/voice' ? 'voice' : location.hash.slice(1));
window.addEventListener('popstate', () => navigate(location.pathname === '/voice' ? 'voice' : location.hash.slice(1)));
