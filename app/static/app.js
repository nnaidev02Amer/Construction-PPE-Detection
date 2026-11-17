/* PPE Safety Monitor dashboard – plain JavaScript, no external libraries */
'use strict';

const API = '/api/v1';
const $ = (id) => document.getElementById(id);
const pad = (n) => String(n).padStart(2, '0');
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) =>
  ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const todayStr = () => { const d = new Date(); return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`; };
const fmtTime = (ts) => (ts ? new Date(ts).toLocaleString() : '—');

/* ── Icons (Lucide-style, inline) ─────────────────────────────────────────── */
const ICONS = {
  'hard-hat': '<path d="M10 10V5a1 1 0 0 1 1-1h2a1 1 0 0 1 1 1v5"/><path d="M14 6a6 6 0 0 1 6 6v3"/><path d="M4 15v-3a6 6 0 0 1 6-6"/><rect x="2" y="15" width="20" height="4" rx="1"/>',
  'layout-dashboard': '<rect width="7" height="9" x="3" y="3" rx="1"/><rect width="7" height="5" x="14" y="3" rx="1"/><rect width="7" height="9" x="14" y="12" rx="1"/><rect width="7" height="5" x="3" y="16" rx="1"/>',
  video: '<path d="m16 13 5.2 3.5a.5.5 0 0 0 .8-.4V7.9a.5.5 0 0 0-.75-.43L16 10.5"/><rect x="2" y="6" width="14" height="12" rx="2"/>',
  'triangle-alert': '<path d="m21.7 18-8-14a2 2 0 0 0-3.5 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.7-3"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
  users: '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.9"/><path d="M16 3.1a4 4 0 0 1 0 7.8"/>',
  chart: '<path d="M3 3v18h18"/><path d="M18 17V9"/><path d="M13 17V5"/><path d="M8 17v-3"/>',
  sliders: '<path d="M21 4h-7"/><path d="M10 4H3"/><path d="M21 12h-9"/><path d="M8 12H3"/><path d="M21 20h-5"/><path d="M12 20H3"/><path d="M14 2v4"/><path d="M8 10v4"/><path d="M16 18v4"/>',
  bell: '<path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.9 1.9 0 0 0 3.4 0"/>',
  play: '<polygon points="6 3 20 12 6 21 6 3"/>',
  square: '<rect width="14" height="14" x="5" y="5" rx="1"/>',
  download: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="m7 10 5 5 5-5"/><path d="M12 15V3"/>',
  printer: '<path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/><path d="M6 9V3h12v6"/><rect x="6" y="14" width="12" height="8" rx="1"/>',
};
function icon(name, cls = '') {
  return `<svg class="icon ${cls}" viewBox="0 0 24 24" aria-hidden="true">${ICONS[name] || ''}</svg>`;
}
document.querySelectorAll('[data-icon]').forEach((el) => { el.innerHTML = icon(el.dataset.icon); });

/* ── Violation types (must match app/core/violation_types.py) ─────────────── */
const TYPES = {
  'NO-Hardhat': { label: 'Missing helmet', cls: 'red', color: '#dc2626' },
  'NO-Safety Vest': { label: 'Missing safety vest', cls: 'orange', color: '#ea580c' },
  COMBINED: { label: 'Helmet + vest missing', cls: 'critical', color: '#a21caf' },
};
const typeInfo = (t) => TYPES[t] || { label: t, cls: 'gray', color: '#64748b' };
const typePill = (t) => `<span class="pill ${typeInfo(t).cls}">${esc(typeInfo(t).label)}${t === 'COMBINED' ? ' – CRITICAL' : ''}</span>`;
const workerLabel = (id) => (id == null ? '—' : `#${id}`);

/* ── Helpers: API, toast, modal ───────────────────────────────────────────── */
async function api(path, opts = {}) {
  const r = await fetch(API + path, opts);
  if (!r.ok) {
    let msg = `Request failed (${r.status})`;
    try {
      const j = await r.json();
      if (typeof j.detail === 'string') msg = j.detail;
      else if (Array.isArray(j.detail)) msg = j.detail.map((d) => (d.msg || '').replace(/^Value error, /, '')).join('; ');
    } catch { /* keep default */ }
    const e = new Error(msg); e.status = r.status; throw e;
  }
  return r.status === 204 ? null : r.json();
}
const post = (p, body) => api(p, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: body ? JSON.stringify(body) : undefined });
const put = (p, body) => api(p, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });

function toast(title, msg, cls = 'info', onClick = null, ms = 6000) {
  const el = document.createElement('div');
  el.className = `toast ${cls}`;
  el.innerHTML = `<div><div class="t">${esc(title)}</div><div class="m">${esc(msg)}</div></div>`;
  el.onclick = () => { el.remove(); if (onClick) onClick(); };
  $('toasts').appendChild(el);
  setTimeout(() => el.remove(), ms);
}
function openModal(title, html) {
  $('modal-title').textContent = title;
  $('modal-body').innerHTML = html;
  $('modal').classList.add('open');
}
const closeModal = () => $('modal').classList.remove('open');
$('modal-close').onclick = closeModal;
$('modal').onclick = (e) => { if (e.target === $('modal')) closeModal(); };

const shot = (v, cls = 'thumb') => (v.frame_url
  ? `<img class="${cls}" src="${esc(v.frame_url)}" alt="evidence" loading="lazy" onerror="this.outerHTML='<div class=&quot;no-shot&quot;>unavail-<br>able</div>'" />`
  : '<div class="no-shot">no<br>image</div>');

/* ── Charts (hand-drawn SVG) ──────────────────────────────────────────────── */
function niceMax(m) { if (m <= 5) return 5; const p = 10 ** Math.floor(Math.log10(m)); return Math.ceil(m / p) * p; }

function stackedBars(el, items, colors, names, labelEvery = 1) {
  const W = 600, H = 230, L = 34, B = 26, T = 14, R = 8;
  const totals = items.map((i) => i.parts.reduce((a, b) => a + b, 0));
  const max = niceMax(Math.max(0, ...totals));
  const pw = W - L - R, ph = H - T - B, bw = (pw / items.length) * 0.62;
  let svg = `<svg viewBox="0 0 ${W} ${H}" role="img">`;
  for (let g = 0; g <= 4; g++) {
    const y = T + ph - (ph * g) / 4;
    svg += `<line x1="${L}" x2="${W - R}" y1="${y}" y2="${y}" stroke="#e3e8ef"/><text x="${L - 6}" y="${y + 4}" text-anchor="end">${Math.round((max * g) / 4)}</text>`;
  }
  items.forEach((it, i) => {
    const x = L + (pw / items.length) * i + ((pw / items.length) - bw) / 2;
    let y = T + ph;
    it.parts.forEach((v, k) => {
      const h = (v / max) * ph;
      if (h > 0) { y -= h; svg += `<rect x="${x}" y="${y}" width="${bw}" height="${h}" rx="2" fill="${colors[k]}"><title>${esc(it.label)} – ${esc(names[k])}: ${v}</title></rect>`; }
    });
    if (totals[i] > 0) svg += `<text x="${x + bw / 2}" y="${y - 4}" text-anchor="middle" style="fill:#1b2434;font-weight:600">${totals[i]}</text>`;
    if (i % labelEvery === 0) svg += `<text x="${x + bw / 2}" y="${H - 8}" text-anchor="middle">${esc(it.label)}</text>`;
  });
  svg += '</svg>';
  const legend = names.length > 1
    ? `<div class="chart-legend">${names.map((n, k) => `<span><i style="background:${colors[k]}"></i>${esc(n)}</span>`).join('')}</div>` : '';
  el.innerHTML = svg + legend + (totals.every((t) => t === 0) ? '<p class="help" style="text-align:center">No violations recorded in this period.</p>' : '');
}

function donut(el, slices) {
  const total = slices.reduce((a, s) => a + s.value, 0);
  const R = 42, C = 2 * Math.PI * R;
  let svg = `<svg viewBox="0 0 120 120" style="width:150px;height:150px" role="img"><circle cx="60" cy="60" r="${R}" fill="none" stroke="#eef1f6" stroke-width="16"/>`;
  let off = 0;
  if (total > 0) slices.forEach((s) => {
    const len = (s.value / total) * C;
    if (len > 0) svg += `<circle cx="60" cy="60" r="${R}" fill="none" stroke="${s.color}" stroke-width="16" stroke-dasharray="${len} ${C - len}" stroke-dashoffset="${-off}" transform="rotate(-90 60 60)"><title>${esc(s.label)}: ${s.value}</title></circle>`;
    off += len;
  });
  svg += `<text x="60" y="64" text-anchor="middle" style="font-size:18px;font-weight:700;fill:#1b2434">${total}</text></svg>`;
  el.innerHTML = `<div class="donut-wrap">${svg}<ul>${slices.map((s) => `<li><i style="background:${s.color}"></i>${esc(s.label)}: <b>${s.value}</b>${total ? ` (${Math.round((s.value / total) * 100)}%)` : ''}</li>`).join('')}</ul></div>`
    + (total === 0 ? '<p class="help" style="text-align:center">No violations recorded in this period.</p>' : '');
}
const typeSlices = (d) => Object.keys(TYPES).map((t) => ({ label: TYPES[t].label, value: d[t] || 0, color: TYPES[t].color }));
const TYPE_COLORS = Object.values(TYPES).map((t) => t.color);
const TYPE_NAMES = Object.values(TYPES).map((t) => t.label);

const statCard = (label, value, cls = '', hint = '') =>
  `<div class="card stat ${cls}"><div class="lbl">${esc(label)}</div><div class="val">${esc(value)}</div><div class="hint">${esc(hint)}</div></div>`;
const pct = (v) => (v == null ? '—' : `${v}%`);

/* ── Router ───────────────────────────────────────────────────────────────── */
const PAGES = {
  dashboard: { title: 'Dashboard', sub: 'Today at a glance', load: loadDashboard },
  live: { title: 'Live Monitoring', sub: 'Camera feed with real-time PPE detection', load: loadLive },
  violations: { title: 'Violations', sub: 'Every recorded incident with evidence', load: loadViolations },
  workers: { title: 'Workers', sub: 'Tracking IDs and their violation history', load: loadWorkers },
  reports: { title: 'Reports', sub: 'Daily and monthly safety statistics', load: loadReport },
  settings: { title: 'Settings', sub: 'Detection rules, email and cameras', load: loadSettings },
};
let currentPage = 'dashboard';

function show(page) {
  if (!PAGES[page]) page = 'dashboard';
  if (currentPage === 'live' && page !== 'live') detachStream();
  currentPage = page;
  document.querySelectorAll('.page').forEach((p) => p.classList.toggle('active', p.id === `page-${page}`));
  document.querySelectorAll('#nav a').forEach((a) => a.classList.toggle('active', a.dataset.page === page));
  $('page-title').textContent = PAGES[page].title;
  $('page-sub').textContent = PAGES[page].sub;
  $('bell-panel').classList.remove('open');
  PAGES[page].load().catch((e) => toast('Could not load page', e.message, 'red'));
}
document.querySelectorAll('#nav a').forEach((a) => { a.onclick = () => { location.hash = a.dataset.page; }; });
document.querySelectorAll('[data-go]').forEach((a) => { a.onclick = () => { location.hash = a.dataset.go; }; });
window.addEventListener('hashchange', () => show(location.hash.slice(1)));

/* ── Health ───────────────────────────────────────────────────────────────── */
async function pollHealth() {
  try {
    const d = await api('/health');
    $('health-dot').className = `dot ${d.model_loaded ? 'ok' : 'bad'}`;
    $('health-text').textContent = d.model_loaded ? `Online · ${d.cameras_active} camera(s) active` : 'Model not loaded';
  } catch {
    $('health-dot').className = 'dot bad';
    $('health-text').textContent = 'Server offline';
  }
}

/* ── Dashboard ────────────────────────────────────────────────────────────── */
async function loadDashboard() {
  const [o, recent] = await Promise.all([api('/overview'), api('/violations?page_size=8')]);
  const t = o.today;
  $('dash-stats').innerHTML = [
    statCard('Workers detected', t.workers_detected, '', 'today (tracking IDs)'),
    statCard('Compliance', pct(t.compliance_pct), 'green', t.workers_detected ? `${t.compliant_workers} of ${t.workers_detected} workers` : 'no workers tracked today'),
    statCard('Total violations', t.total_incidents, '', 'today'),
    statCard('Helmet violations', t.helmet_violations, 'red', 'today'),
    statCard('Vest violations', t.vest_violations, 'orange', 'today'),
    statCard('Combined violations', t.combined_violations, 'critical', 'helmet + vest, today'),
  ].join('');
  stackedBars($('dash-trend'), o.trend.map((d) => ({ label: d.date.slice(5), parts: [d.helmet, d.vest, d.combined] })), TYPE_COLORS, TYPE_NAMES);
  donut($('dash-donut'), typeSlices(o.distribution));
  $('dash-recent').innerHTML = recent.items.length
    ? recent.items.map((v) => `<tr class="click" data-vid="${v.id}"><td>${shot(v)}</td><td>${esc(fmtTime(v.timestamp))}</td><td>${workerLabel(v.track_id)}</td><td>${typePill(v.violation_type)}</td><td>${esc(v.camera_name || v.camera_id)}</td></tr>`).join('')
    : '<tr><td colspan="5" class="empty">No violations recorded yet.</td></tr>';
  $('dash-cameras').innerHTML = o.cameras.length
    ? o.cameras.map((c) => `<div class="alert-item" style="cursor:default"><div style="flex:1"><b>${esc(c.name)}</b><div class="meta">${esc(c.source_type)}</div></div>${statusPill(c.status)}</div>`).join('')
    : '<div class="empty">No cameras yet. Add one in Settings.</div>';
}
const statusPill = (s) => ({ running: '<span class="pill green">Running</span>', no_signal: '<span class="pill red">No signal</span>' }[s] || '<span class="pill gray">Stopped</span>');
document.addEventListener('click', (e) => {
  const row = e.target.closest('[data-vid]');
  if (row) openViolation(+row.dataset.vid);
  const w = e.target.closest('[data-worker]');
  if (w) { const [c, t, s] = JSON.parse(w.dataset.worker); openWorker(c, t, s); }
});

/* ── Live monitoring ──────────────────────────────────────────────────────── */
let liveCams = [], ws = null, liveCamId = null;

async function loadLive() {
  api('/settings').then((s) => { $('conf-chip').textContent = `people ≥ ${Number(s.detection_confidence).toFixed(2)} · helmet/vest ≥ ${Number(s.ppe_item_confidence).toFixed(2)}`; }).catch(() => {});
  await refreshLiveCameras();
  if (liveCamId && liveCams.find((c) => c.id === liveCamId && c.is_running)) attachStream(liveCamId);
  else {
    const running = liveCams.find((c) => c.is_running);
    if (running) { $('live-camera').value = running.id; attachStream(running.id); }
  }
  renderLiveButtons();
}
async function refreshLiveCameras() {
  liveCams = await api('/cameras');
  const sel = $('live-camera');
  const keep = sel.value;
  sel.innerHTML = liveCams.length
    ? liveCams.map((c) => `<option value="${c.id}">${esc(c.name)} (${esc(c.source_type)})</option>`).join('')
    : '<option value="">No cameras – add one in Settings</option>';
  if (keep && liveCams.find((c) => c.id === +keep)) sel.value = keep;
  renderLiveButtons();
}
function selectedLiveCam() { return liveCams.find((c) => c.id === +$('live-camera').value); }
function renderLiveButtons() {
  const cam = selectedLiveCam();
  $('live-start').disabled = !cam || cam.is_running;
  $('live-stop').disabled = !cam || !cam.is_running;
  setStatus(cam ? cam.status : 'stopped');
}
function setStatus(s) {
  const chip = $('live-status');
  chip.className = `status-chip ${s}`;
  chip.lastElementChild.textContent = { running: 'Detecting', no_signal: 'No signal – camera disconnected?', stopped: 'Stopped' }[s] || s;
}
function attachStream(id) {
  detachStream();
  liveCamId = id;
  $('live-img').src = `${API}/stream/${id}?t=${Date.now()}`;
  $('live-img').style.display = 'block';
  $('live-ph').style.display = 'none';
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  ws = new WebSocket(`${proto}://${location.host}${API}/ws/${id}`);
  ws.onmessage = (ev) => {
    let d; try { d = JSON.parse(ev.data); } catch { return; }
    if (d.ping) return;
    if (d.signal === false) setStatus('no_signal');
    else if (d.signal === true) setStatus('running');
    renderLiveCounts(d);
  };
}
function detachStream() {
  if (ws) { ws.onclose = null; ws.close(); ws = null; }
  $('live-img').removeAttribute('src');
  $('live-img').style.display = 'none';
  $('live-ph').style.display = '';
  $('live-counts').innerHTML = '';
  $('live-workers').innerHTML = '<tr><td colspan="4" class="empty">No workers in view</td></tr>';
}
$('live-img').onerror = () => { if (currentPage === 'live' && $('live-img').getAttribute('src')) { setStatus('stopped'); } };
function renderLiveCounts(d) {
  const tile = (l, v, c = '') => `<div class="card stat ${c}" style="padding:10px 12px"><div class="lbl">${l}</div><div class="val" style="font-size:22px">${v ?? '—'}</div></div>`;
  $('live-counts').innerHTML = tile('In view', d.person_count) + tile('Compliant', d.compliant_count, 'green') + tile('No helmet', d.helmet_missing_count, 'red')
    + tile('No vest', d.vest_missing_count, 'orange') + tile('Critical', d.combined_missing_count, 'critical') + tile('Tracked total', d.unique_person_count);
  const ps = d.persons || [];
  const yes = '<span class="pill green">OK</span>', no = (c) => `<span class="pill ${c}">Missing</span>`;
  $('live-workers').innerHTML = ps.length
    ? ps.map((p) => `<tr><td><b>#${p.track_id}</b></td><td>${p.has_hardhat ? yes : no('red')}</td><td>${p.has_vest ? yes : no('orange')}</td><td>${Math.round((p.confidence || 0) * 100)}%</td></tr>`).join('')
    : '<tr><td colspan="4" class="empty">No workers in view</td></tr>';
}
$('live-camera').onchange = async () => { await refreshLiveCameras(); const c = selectedLiveCam(); if (c && c.is_running) attachStream(c.id); else detachStream(); };
$('live-start').onclick = async () => {
  const cam = selectedLiveCam(); if (!cam) return;
  $('live-start').disabled = true;
  try { await post(`/cameras/${cam.id}/start`); await refreshLiveCameras(); attachStream(cam.id); toast('Camera started', cam.name, 'ok', null, 3000); }
  catch (e) { toast('Could not start camera', e.message, 'red', null, 9000); await refreshLiveCameras(); }
};
$('live-stop').onclick = async () => {
  const cam = selectedLiveCam(); if (!cam) return;
  try { await post(`/cameras/${cam.id}/stop`); detachStream(); await refreshLiveCameras(); toast('Camera stopped', cam.name, 'info', null, 3000); }
  catch (e) { toast('Could not stop camera', e.message, 'red'); }
};

/* ── Real-time notifications (Server-Sent Events) ─────────────────────────── */
let unread = 0; const notes = [];
function alertItem(v) {
  const t = typeInfo(v.violation_type);
  return `<div class="alert-item ${t.cls}" data-vid="${v.id}">${shot(v)}<div style="flex:1">
    <div><b>Worker ${workerLabel(v.track_id)}</b> – ${typePill(v.violation_type)}</div>
    <div class="meta">${esc(v.camera_name || 'Camera ' + v.camera_id)} · ${esc(fmtTime(v.timestamp))}</div></div></div>`;
}
function renderBell() {
  $('bell-count').style.display = unread ? 'block' : 'none';
  $('bell-count').textContent = unread > 99 ? '99+' : unread;
  $('nav-count').style.display = unread ? 'inline-block' : 'none';
  $('nav-count').textContent = unread;
  $('bell-list').innerHTML = notes.length ? notes.map(alertItem).join('') : '<div class="empty">No new violations since you opened this page.</div>';
}
function onViolation(v) {
  unread += 1; notes.unshift(v); notes.length = Math.min(notes.length, 30);
  renderBell();
  const feed = $('live-alerts');
  if (feed.querySelector('.empty')) feed.innerHTML = '';
  feed.insertAdjacentHTML('afterbegin', alertItem(v));
  while (feed.children.length > 20) feed.lastElementChild.remove();
  const info = typeInfo(v.violation_type);
  toast(`${v.violation_type === 'COMBINED' ? 'CRITICAL – ' : ''}${info.label}`, `Worker ${workerLabel(v.track_id)} · ${v.camera_name || 'Camera ' + v.camera_id}`, info.cls, () => openViolation(v.id), 8000);
  if (['dashboard', 'violations', 'workers', 'reports'].includes(currentPage)) scheduleRefresh();
}
let refreshT = null;
function scheduleRefresh() { clearTimeout(refreshT); refreshT = setTimeout(() => PAGES[currentPage].load().catch(() => {}), 600); }
function startEvents() {
  const es = new EventSource(`${API}/events`);   // the browser reconnects by itself
  es.addEventListener('violation', (e) => { try { onViolation(JSON.parse(e.data)); } catch { /* ignore */ } });
}
$('bell').onclick = () => $('bell-panel').classList.toggle('open');
$('bell-clear').onclick = () => { unread = 0; notes.length = 0; renderBell(); };

/* ── Violation detail ─────────────────────────────────────────────────────── */
async function openViolation(id) {
  try {
    const v = await api(`/violations/${id}`);
    const email = v.alerts.filter((a) => a.handler_type === 'email').pop();
    const emailTxt = !email ? 'No email sent (disabled, not configured, or switched off for this type)'
      : email.success ? 'Email sent' : `Email failed: ${esc(email.error_msg || 'unknown error')}`;
    const img = v.frame_url
      ? `<img class="detail-img" src="${esc(v.frame_url)}" alt="Evidence screenshot" onerror="this.outerHTML='<div class=&quot;empty detail-img&quot;>Screenshot file is no longer available.</div>'" />`
      : '<div class="empty detail-img">No screenshot available for this violation.</div>';
    const worker = v.track_id != null
      ? `<a data-worker='${JSON.stringify([v.camera_id, v.track_id, v.session_id])}' style="cursor:pointer">Worker #${v.track_id} – history</a>` : '—';
    openModal(`Violation #${v.id}`, `<div class="detail-grid"><div>${img}</div><dl class="kv">
      <dt>Type</dt><dd>${typePill(v.violation_type)}</dd>
      <dt>Missing PPE</dt><dd>${esc(v.missing_items.join(' + ') || '—')}</dd>
      <dt>Worker</dt><dd>${worker}</dd>
      <dt>Camera</dt><dd>${esc(v.camera_name || v.camera_id)}</dd>
      <dt>Detected</dt><dd>${esc(fmtTime(v.timestamp))}</dd>
      <dt>Confidence</dt><dd>${Math.round(v.confidence * 100)}%</dd>
      <dt>Session</dt><dd>${esc(v.session_id || 'n/a (older record)')}</dd>
      <dt>Email</dt><dd>${emailTxt}</dd></dl></div>
      <p class="help">Worker # is a tracking ID within one camera session – not an identity.</p>`);
    unread = Math.max(0, unread - notes.filter((n) => n.id === id).length);
    const i = notes.findIndex((n) => n.id === id); if (i >= 0) notes.splice(i, 1);
    renderBell();
  } catch (e) { toast('Could not open violation', e.message, 'red'); }
}

/* ── Violations page ──────────────────────────────────────────────────────── */
const vState = { page: 1, size: 15, total: 0 };
function vParams(paged) {
  const p = new URLSearchParams();
  if ($('v-search').value.trim()) p.set('search', $('v-search').value.trim());
  if ($('v-type').value) p.set('violation_type', $('v-type').value);
  if ($('v-camera').value) p.set('camera_id', $('v-camera').value);
  if ($('v-from').value) p.set('from', `${$('v-from').value}T00:00:00`);
  if ($('v-to').value) p.set('to', `${$('v-to').value}T23:59:59`);
  if (paged) { p.set('page', vState.page); p.set('page_size', vState.size); }
  return p;
}
async function fillCameraSelect(sel) {
  const cams = await api('/cameras');
  const keep = sel.value;
  sel.innerHTML = '<option value="">All cameras</option>' + cams.map((c) => `<option value="${c.id}">${esc(c.name)}</option>`).join('');
  sel.value = keep;
}
async function loadViolations() {
  await fillCameraSelect($('v-camera'));
  const d = await api(`/violations?${vParams(true)}`);
  vState.total = d.total;
  $('v-body').innerHTML = d.items.length ? d.items.map((v) => `<tr class="click" data-vid="${v.id}">
      <td>#${v.id}</td><td>${shot(v)}</td><td>${esc(fmtTime(v.timestamp))}</td><td>${workerLabel(v.track_id)}</td>
      <td>${typePill(v.violation_type)}</td><td>${esc(v.camera_name || v.camera_id)}</td><td>${Math.round(v.confidence * 100)}%</td></tr>`).join('')
    : '<tr><td colspan="7" class="empty">No violations match these filters.</td></tr>';
  const pages = Math.max(1, Math.ceil(d.total / vState.size));
  $('v-info').textContent = `${d.total} violation(s) · page ${d.page} of ${pages}`;
  $('v-prev').disabled = d.page <= 1; $('v-next').disabled = d.page >= pages;
  const q = vParams(false).toString();
  $('v-export').href = `${API}/violations/export${q ? '?' + q : ''}`;
}
let vTimer = null;
const vReload = () => { vState.page = 1; loadViolations().catch((e) => toast('Error', e.message, 'red')); };
$('v-search').oninput = () => { clearTimeout(vTimer); vTimer = setTimeout(vReload, 300); };
['v-type', 'v-camera', 'v-from', 'v-to'].forEach((id) => { $(id).onchange = vReload; });
$('v-reset').onclick = () => { ['v-search', 'v-type', 'v-camera', 'v-from', 'v-to'].forEach((id) => { $(id).value = ''; }); vReload(); };
$('v-prev').onclick = () => { vState.page -= 1; loadViolations(); };
$('v-next').onclick = () => { vState.page += 1; loadViolations(); };

/* ── Workers page ─────────────────────────────────────────────────────────── */
async function loadWorkers() {
  await fillCameraSelect($('w-camera'));
  const p = new URLSearchParams();
  if ($('w-search').value.trim()) p.set('search', $('w-search').value.trim());
  if ($('w-camera').value) p.set('camera_id', $('w-camera').value);
  if ($('w-from').value) p.set('from', `${$('w-from').value}T00:00:00`);
  if ($('w-to').value) p.set('to', `${$('w-to').value}T23:59:59`);
  if ($('w-only').checked) p.set('only_with_violations', 'true');
  const ws_ = await api(`/workers?${p}`);
  $('w-body').innerHTML = ws_.length ? ws_.map((w) => `<tr class="click" data-worker='${JSON.stringify([w.camera_id, w.track_id, w.session_id])}'>
      <td><b>#${w.track_id}</b></td><td>${esc(w.camera_name)}</td><td>${esc(w.session_id || 'n/a')}</td>
      <td>${w.total_violations ? `<b>${w.total_violations}</b>` : '<span class="pill green">0</span>'}</td>
      <td class="t-red">${w.helmet_violations}</td><td class="t-orange">${w.vest_violations}</td><td class="t-critical">${w.combined_violations}</td>
      <td>${esc(fmtTime(w.last_violation))}</td></tr>`).join('')
    : '<tr><td colspan="8" class="empty">No workers tracked yet. Start a camera and stand in front of it.</td></tr>';
}
let wTimer = null;
$('w-search').oninput = () => { clearTimeout(wTimer); wTimer = setTimeout(() => loadWorkers().catch(() => {}), 300); };
['w-camera', 'w-from', 'w-to', 'w-only'].forEach((id) => { $(id).onchange = () => loadWorkers().catch(() => {}); });

async function openWorker(cam, track, session) {
  try {
    const q = new URLSearchParams({ camera_id: cam, track_id: track });
    if (session) q.set('session_id', session);
    const h = await api(`/workers/history?${q}`);
    openModal(`Worker #${h.track_id} · ${h.camera_name}`, `
      <p class="help" style="margin-top:0">Tracking ID within camera session ${esc(h.session_id || '(older record)')} – not a permanent identity.</p>
      <div class="grid" style="grid-template-columns:repeat(4,1fr);margin-bottom:14px">
        ${statCard('Total', h.total_violations)}${statCard('Helmet', h.helmet_violations, 'red')}
        ${statCard('Vest', h.vest_violations, 'orange')}${statCard('Combined', h.combined_violations, 'critical')}</div>
      <div class="table-wrap"><table><thead><tr><th>ID</th><th>Evidence</th><th>Time</th><th>Type</th><th>Conf.</th></tr></thead><tbody>
      ${h.violations.length ? h.violations.map((v) => `<tr class="click" data-vid="${v.id}"><td>#${v.id}</td><td>${shot(v)}</td><td>${esc(fmtTime(v.timestamp))}</td><td>${typePill(v.violation_type)}</td><td>${Math.round(v.confidence * 100)}%</td></tr>`).join('')
        : '<tr><td colspan="5" class="empty">No violations recorded for this worker.</td></tr>'}</tbody></table></div>`);
  } catch (e) { toast('Could not load worker', e.message, 'red'); }
}

/* ── Reports ──────────────────────────────────────────────────────────────── */
let rMode = 'daily';
$('r-day').value = todayStr();
$('r-month').value = todayStr().slice(0, 7);
document.querySelectorAll('#r-tabs button').forEach((b) => {
  b.onclick = () => {
    rMode = b.dataset.mode;
    document.querySelectorAll('#r-tabs button').forEach((x) => x.classList.toggle('on', x === b));
    $('r-day-wrap').style.display = rMode === 'daily' ? '' : 'none';
    $('r-month-wrap').style.display = rMode === 'monthly' ? '' : 'none';
    loadReport().catch((e) => toast('Report error', e.message, 'red'));
  };
});
$('r-day').onchange = $('r-month').onchange = () => loadReport().catch((e) => toast('Report error', e.message, 'red'));
async function loadReport() {
  let r;
  if (rMode === 'daily') {
    const day = $('r-day').value || todayStr();
    r = await api(`/reports/daily?date=${day}`);
    $('r-title').textContent = `Daily safety report – ${day}`;
    $('r-stats').innerHTML = [
      statCard('Workers detected', r.workers_detected, '', 'tracking IDs'),
      statCard('Compliant workers', r.compliant_workers, 'green', 'no incident recorded'),
      statCard('Compliance', pct(r.compliance_pct), 'green', r.workers_detected ? '' : 'no workers tracked'),
      statCard('Helmet violations', r.helmet_violations, 'red'), statCard('Vest violations', r.vest_violations, 'orange'),
      statCard('Combined violations', r.combined_violations, 'critical'), statCard('Total incidents', r.total_incidents),
    ].join('');
    $('r-chart-title').textContent = 'Incidents by hour of day';
    stackedBars($('r-chart'), r.by_hour.map((n, h) => ({ label: pad(h), parts: [n] })), ['#2563eb'], ['Incidents'], 2);
    donut($('r-donut'), typeSlices({ 'NO-Hardhat': r.helmet_violations, 'NO-Safety Vest': r.vest_violations, COMBINED: r.combined_violations }));
    $('r-csv').onclick = () => { location.href = `${API}/reports/daily/export?date=${day}`; };
  } else {
    const month = $('r-month').value || todayStr().slice(0, 7);
    r = await api(`/reports/monthly?month=${month}`);
    $('r-title').textContent = `Monthly safety report – ${month}`;
    $('r-stats').innerHTML = [
      statCard('Total violations', r.total_violations), statCard('Helmet violations', r.by_type['NO-Hardhat'], 'red'),
      statCard('Vest violations', r.by_type['NO-Safety Vest'], 'orange'), statCard('Combined violations', r.by_type.COMBINED, 'critical'),
      statCard('Most frequent', r.most_frequent_type ? typeInfo(r.most_frequent_type).label : 'none recorded'),
      statCard('Workers detected', r.workers_detected, '', 'tracking IDs'), statCard('Compliance', pct(r.compliance_pct), 'green', r.workers_detected ? '' : 'no workers tracked'),
    ].join('');
    $('r-chart-title').textContent = 'Daily violation trend';
    stackedBars($('r-chart'), r.daily.map((d) => ({ label: d.date.slice(8), parts: [d.helmet, d.vest, d.combined] })), TYPE_COLORS, TYPE_NAMES, 2);
    donut($('r-donut'), typeSlices(r.by_type));
    $('r-csv').onclick = () => { location.href = `${API}/reports/monthly/export?month=${month}`; };
  }
  $('r-cameras').innerHTML = r.by_camera.length
    ? r.by_camera.map((c) => `<tr><td>${esc(c.camera_name)}</td><td class="t-red">${c.helmet}</td><td class="t-orange">${c.vest}</td><td class="t-critical">${c.combined}</td><td><b>${c.total}</b></td></tr>`).join('')
    : '<tr><td colspan="5" class="empty">No incidents in this period.</td></tr>';
  $('r-note').textContent = r.note;
}
$('r-print').onclick = () => window.print();

/* ── Settings ─────────────────────────────────────────────────────────────── */
async function loadSettings() {
  const s = await api('/settings');
  $('s-conf').value = s.detection_confidence;
  $('s-ppeconf').value = s.ppe_item_confidence;
  $('s-persist').value = s.violation_persist_seconds;
  $('s-cooldown').value = s.alert_cooldown_seconds;
  $('s-email-on').checked = s.email_enabled;
  $('s-host').value = s.smtp_host; $('s-port').value = s.smtp_port;
  $('s-sender').value = s.sender_email; $('s-receiver').value = s.receiver_email;
  $('s-password').value = '';
  $('s-pw-help').textContent = s.email_password_set
    ? 'A password is saved (it is never shown). Leave blank to keep it. For Gmail use an App Password.'
    : 'No password saved yet. For Gmail create an App Password (your normal password will not work).';
  $('s-n-helmet').checked = s.email_notify_helmet; $('s-n-vest').checked = s.email_notify_vest; $('s-n-combined').checked = s.email_notify_combined;
  $('s-email-state').textContent = !s.email_enabled ? 'disabled' : s.email_configured ? 'ready' : 'not configured';
  $('s-email-state').className = `pill ${s.email_enabled && s.email_configured ? 'green' : 'gray'}`;
  await loadCamTable();
}
async function saveSettings() {
  const body = {
    detection_confidence: parseFloat($('s-conf').value), ppe_item_confidence: parseFloat($('s-ppeconf').value), violation_persist_seconds: parseFloat($('s-persist').value),
    alert_cooldown_seconds: parseInt($('s-cooldown').value, 10), email_enabled: $('s-email-on').checked,
    smtp_host: $('s-host').value.trim(), smtp_port: parseInt($('s-port').value, 10),
    sender_email: $('s-sender').value.trim(), receiver_email: $('s-receiver').value.trim(),
    email_notify_helmet: $('s-n-helmet').checked, email_notify_vest: $('s-n-vest').checked, email_notify_combined: $('s-n-combined').checked,
  };
  if ($('s-password').value) body.email_password = $('s-password').value;
  Object.keys(body).forEach((k) => { if (typeof body[k] === 'number' && Number.isNaN(body[k])) delete body[k]; });
  await put('/settings', body);
  await loadSettings();
}
$('s-save').onclick = async () => {
  try { await saveSettings(); $('s-msg').textContent = 'Saved. Thresholds apply immediately to running cameras.'; toast('Settings saved', '', 'ok', null, 2500); }
  catch (e) { $('s-msg').textContent = ''; toast('Could not save settings', e.message, 'red'); }
};
$('s-test').onclick = async () => {
  $('s-test').disabled = true; $('s-msg').textContent = 'Sending test email…';
  try {
    await saveSettings();
    const r = await post('/settings/test-email');
    $('s-msg').textContent = r.message;
    toast(r.ok ? 'Test email sent' : 'Test email failed', r.message, r.ok ? 'ok' : 'red', null, 9000);
  } catch (e) { $('s-msg').textContent = e.message; toast('Test email failed', e.message, 'red'); }
  $('s-test').disabled = false;
};

const SOURCE_HINTS = {
  webcam: ['0', 'Device number: 0 = built-in laptop webcam, 1 = a second camera.'],
  rtsp: ['rtsp://user:password@192.168.1.100:554/stream', 'RTSP URL of an IP/CCTV camera (the exact path depends on the brand).'],
  file: ['C:\\videos\\site.mp4', 'Full path to a video file on this computer. It loops while the camera is running.'],
};
function updateHint() { const [ph, help] = SOURCE_HINTS[$('cam-type').value]; $('cam-uri').placeholder = ph; $('cam-help').textContent = help; }
$('cam-type').onchange = updateHint; updateHint();
$('cam-form').onsubmit = async (e) => {
  e.preventDefault();
  try {
    await post('/cameras', { name: $('cam-name').value.trim(), source_type: $('cam-type').value, source_uri: $('cam-uri').value.trim() });
    e.target.reset(); updateHint(); await loadCamTable(); toast('Camera added', '', 'ok', null, 2500);
  } catch (err) { toast('Could not add camera', err.message, 'red', null, 9000); }
};
async function loadCamTable() {
  const cams = await api('/cameras');
  $('cam-body').innerHTML = cams.length ? cams.map((c) => `<tr><td>${c.id}</td><td>${esc(c.name)}</td><td>${esc(c.source_type)}</td>
    <td style="max-width:260px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(c.source_uri)}</td><td>${statusPill(c.status)}</td>
    <td style="white-space:nowrap"><button class="btn-sm" data-edit="${c.id}">Edit</button> <button class="btn-sm" data-del="${c.id}">Delete</button></td></tr>`).join('')
    : '<tr><td colspan="6" class="empty">No cameras yet.</td></tr>';
  $('cam-body').querySelectorAll('[data-edit]').forEach((b) => { b.onclick = () => editCamera(cams.find((c) => c.id === +b.dataset.edit)); });
  $('cam-body').querySelectorAll('[data-del]').forEach((b) => { b.onclick = () => deleteCamera(cams.find((c) => c.id === +b.dataset.del)); });
}
function editCamera(c) {
  $('ce-id').value = c.id; $('ce-name').value = c.name; $('ce-uri').value = c.source_uri;
  $('ce-uri').disabled = c.is_running;
  $('ce-help').textContent = c.is_running ? 'Stop the camera (Live Monitoring) to change its source.' : SOURCE_HINTS[c.source_type][1];
  $('cam-modal').classList.add('open');
}
$('cam-modal-close').onclick = () => $('cam-modal').classList.remove('open');
$('ce-save').onclick = async () => {
  const body = { name: $('ce-name').value.trim() };
  if (!$('ce-uri').disabled) body.source_uri = $('ce-uri').value.trim();
  try { await put(`/cameras/${$('ce-id').value}`, body); $('cam-modal').classList.remove('open'); await loadCamTable(); toast('Camera updated', '', 'ok', null, 2500); }
  catch (e) { toast('Could not update camera', e.message, 'red', null, 9000); }
};
async function deleteCamera(c) {
  if (!confirm(`Delete camera "${c.name}"?`)) return;
  try { await api(`/cameras/${c.id}`, { method: 'DELETE' }); }
  catch (e) {
    if (e.status !== 409) return toast('Could not delete camera', e.message, 'red');
    if (!confirm(`${e.message}\n\nDelete the camera AND all of its recorded violations? This cannot be undone.`)) return;
    try { await api(`/cameras/${c.id}?delete_history=true`, { method: 'DELETE' }); }
    catch (e2) { return toast('Could not delete camera', e2.message, 'red'); }
  }
  await loadCamTable(); toast('Camera deleted', c.name, 'info', null, 3000);
}

/* ── Start-up ─────────────────────────────────────────────────────────────── */
pollHealth(); setInterval(pollHealth, 5000);
setInterval(() => {
  if (document.hidden) return;
  if (currentPage === 'live') refreshLiveCameras().catch(() => {});
  else if (['dashboard', 'violations', 'workers'].includes(currentPage) && !$('modal').classList.contains('open')) PAGES[currentPage].load().catch(() => {});
}, 8000);
startEvents(); renderBell();
show(location.hash.slice(1) || 'dashboard');
