const $ = (id) => document.getElementById(id);
const formatTime = (value) => new Date(value).toLocaleString('th-TH', { dateStyle: 'medium', timeStyle: 'medium' });
function drawRows(target, rows, columns) {
  if (!rows.length) { target.innerHTML = `<tr><td colspan="${columns}" class="empty">ยังไม่มีข้อมูลจากเซนเซอร์</td></tr>`; return; }
  target.innerHTML = rows.map((r, i) => `<tr>${columns === 4 ? `<td>${r.sensor}</td><td><b>${Number(r.value).toLocaleString()}</b></td><td>${r.unit}</td><td>${formatTime(r.timestamp)}</td>` : `<td>${rows.length - i}</td><td>${r.sensor}</td><td><b>${Number(r.value).toLocaleString()}</b></td><td>${r.unit}</td><td>${formatTime(r.timestamp)}</td>`}</tr>`).join('');
}
function render({ latest, history = [] }) {
  const count = history.length;
  $('device-count').innerHTML = `${latest ? '1' : '0'} <small>ตัว</small>`;
  $('reading-count').innerHTML = `${count} <small>ครั้ง</small>`;
  if (latest) {
    const value = Number(latest.value).toLocaleString();
    $('dash-value').innerHTML = `${value} <small>${latest.unit}</small>`;
    $('dash-time').textContent = `รับข้อมูล ${formatTime(latest.timestamp)}`;
    $('sensor-value').innerHTML = `${value} <small>${latest.unit}</small>`;
    $('sensor-name').textContent = latest.sensor;
    $('sensor-time').textContent = formatTime(latest.timestamp);
  }
}
async function refresh() { try { const response = await fetch('/api/sensors'); if (response.ok) render(await response.json()); } catch {} }
function navigate(view) {
  const sensor = view === 'sensor';
  $('dashboard-view').classList.toggle('hidden', sensor);
  $('sensor-view').classList.toggle('hidden', !sensor);
  $('crumb').textContent = sensor ? 'Sensor' : 'Dashboard';
  document.querySelectorAll('.nav-link').forEach((link) => link.classList.toggle('active', link.dataset.view === (sensor ? 'sensor' : 'dashboard')));
}
document.querySelectorAll('[data-view]').forEach((link) => link.addEventListener('click', (event) => { event.preventDefault(); navigate(link.dataset.view); history.replaceState(null, '', `#${link.dataset.view}`); }));
document.querySelectorAll('[data-go]').forEach((button) => button.addEventListener('click', () => { navigate(button.dataset.go); history.replaceState(null, '', `#${button.dataset.go}`); }));
navigate(location.hash === '#sensor' ? 'sensor' : 'dashboard'); refresh(); setInterval(refresh, 2000);
