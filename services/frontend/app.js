/**
 * SecureWatch — Dashboard JavaScript
 * PFA 2025-2026 : Centralisation des Logs pour la Détection d'Incidents de Sécurité
 *
 * Interroge Elasticsearch via /es/ (proxy nginx) pour afficher les logs en temps réel.
 * Détecte : brute force, accès interdits, erreurs système.
 */

const ES_BASE   = '/es';
const PROM_BASE = '/prometheus';
const INDEX      = 'security-logs-*';
const REFRESH_MS = 8000;
const PROM_MS    = 15000;
const PROM_RANGE = 30;   // minutes of history for charts

// ── State ────────────────────────────────────────────────
let allLogs       = [];
let timelineChart = null;
let donutChart    = null;
let refreshTimer  = null;
let promCharts    = {};

// ── Utilitaires ──────────────────────────────────────────
const $ = id => document.getElementById(id);

// Null-safe DOM text setter — avoids TypeError when an element doesn't exist
function setText(id, value) {
  const el = $(id);
  if (el) el.textContent = value;
}

function formatTs(ts) {
  if (!ts) return '—';
  const d = new Date(ts);
  return d.toLocaleTimeString('fr-FR', { hour12: false }) + ' ' +
         d.toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit' });
}

function levelBadge(level) {
  const l = (level || 'INFO').toUpperCase();
  return `<span class="badge badge-${l}">${l}</span>`;
}

function eventTag(type) {
  if (!type) return '';
  return `<span class="event-tag">${type}</span>`;
}

// ── Navigation ────────────────────────────────────────────
let monitoringInitialized = false;

function showSection(name) {
  document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  $(`section-${name}`).classList.add('active');
  $(`nav-${name}`).classList.add('active');
  const titles = {
    dashboard:  'Tableau de bord',
    logs:       'Flux de Logs',
    alerts:     'Alertes de Sécurité',
    services:   'État des Services',
    monitoring: 'Monitoring — Métriques Prometheus'
  };
  $('page-title').textContent = titles[name] || name;

  // Lazy-init: charts need the section visible to measure canvas size
  if (name === 'monitoring') {
    if (!monitoringInitialized) {
      monitoringInitialized = true;
      refreshMonitoring();
      setInterval(refreshMonitoring, PROM_MS);
    } else {
      // Resize charts in case the viewport changed while section was hidden
      Object.values(promCharts).forEach(c => c.resize());
    }
  }
}

// ── Live Clock ────────────────────────────────────────────
function startClock() {
  setInterval(() => {
    $('live-clock').textContent = new Date().toLocaleTimeString('fr-FR', { hour12: false });
  }, 1000);
}

// ── Elasticsearch ─────────────────────────────────────────
async function fetchLogs(size = 500) {
  const body = {
    query: {
      bool: {
        must: [
          { range: { '@timestamp': { gte: 'now-24h' } } }
        ],
        must_not: [
          { terms: { 'event_type.keyword': ['health_check', 'service_start'] } }
        ]
      }
    },
    sort: [{ '@timestamp': { order: 'desc' } }],
    size
  };

  try {
    const res = await fetch(`${ES_BASE}/${INDEX}/_search`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    return (data.hits?.hits || []).map(h => h._source);
  } catch (e) {
    return null;
  }
}

async function checkES() {
  try {
    const res = await fetch(`${ES_BASE}/_cluster/health`);
    const ok  = res.ok;
    $('es-dot').className  = 'status-dot ' + (ok ? 'connected' : 'error');
    $('es-status-text').textContent = ok ? 'Elasticsearch OK' : 'ES Non connecté';
    return ok;
  } catch {
    $('es-dot').className  = 'status-dot error';
    $('es-status-text').textContent = 'ES Non connecté';
    return false;
  }
}

// ── Stats ─────────────────────────────────────────────────
function updateStats(logs) {
  const total    = logs.length;
  const authFail = logs.filter(l => l.event_type === 'auth_failure').length;
  const forbidden= logs.filter(l => l.event_type === 'forbidden_access' || l.status === 403).length;
  const errors   = logs.filter(l => l.level === 'ERROR' || l.status === 500).length;
  const brute    = logs.filter(l => l.event_type === 'brute_force').length;

  $('stat-total').textContent     = total.toLocaleString();
  $('stat-auth').textContent      = authFail.toLocaleString();
  $('stat-forbidden').textContent = forbidden.toLocaleString();
  $('stat-errors').textContent    = errors.toLocaleString();
  $('stat-brute').textContent     = brute.toLocaleString();

  // Alert badge
  const alertCount = brute + (authFail >= 5 ? 1 : 0) + (forbidden >= 10 ? 1 : 0);
  $('alert-badge').textContent    = alertCount;
  $('alert-count-badge').textContent = `${alertCount} alerte${alertCount !== 1 ? 's' : ''}`;
}

// ── Charts ────────────────────────────────────────────────
function buildTimeline(logs) {
  // Bucket by hour for the last 12 hours
  const now = Date.now();
  const buckets = Array.from({ length: 12 }, (_, i) => {
    const start = now - (11 - i) * 3600000;
    const end   = start + 3600000;
    const label = new Date(start).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });
    return { label, start, end, total: 0, warn: 0, err: 0 };
  });

  logs.forEach(l => {
    const t = new Date(l.timestamp).getTime();
    const b = buckets.find(b => t >= b.start && t < b.end);
    if (!b) return;
    b.total++;
    if (l.level === 'WARNING') b.warn++;
    if (l.level === 'ERROR' || l.level === 'CRITICAL') b.err++;
  });

  const labels  = buckets.map(b => b.label);
  const totals  = buckets.map(b => b.total);
  const warns   = buckets.map(b => b.warn);
  const errs    = buckets.map(b => b.err);

  if (timelineChart) {
    timelineChart.data.labels           = labels;
    timelineChart.data.datasets[0].data = totals;
    timelineChart.data.datasets[1].data = warns;
    timelineChart.data.datasets[2].data = errs;
    timelineChart.update('none');
    return;
  }

  const ctx = $('timelineChart').getContext('2d');
  timelineChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [
        {
          label: 'Total',
          data: totals,
          borderColor: '#00d4ff',
          backgroundColor: 'rgba(0,212,255,0.08)',
          fill: true,
          tension: 0.4,
          pointRadius: 3,
          borderWidth: 2
        },
        {
          label: 'WARNING',
          data: warns,
          borderColor: '#ff9f43',
          backgroundColor: 'transparent',
          tension: 0.4,
          pointRadius: 2,
          borderWidth: 1.5,
          borderDash: [4, 3]
        },
        {
          label: 'ERROR/CRITICAL',
          data: errs,
          borderColor: '#ff4757',
          backgroundColor: 'transparent',
          tension: 0.4,
          pointRadius: 2,
          borderWidth: 1.5,
          borderDash: [4, 3]
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { labels: { color: '#7a8aac', font: { size: 11 }, boxWidth: 12 } }
      },
      scales: {
        x: { ticks: { color: '#7a8aac', font: { size: 10 } }, grid: { color: 'rgba(255,255,255,0.04)' } },
        y: { ticks: { color: '#7a8aac', font: { size: 10 } }, grid: { color: 'rgba(255,255,255,0.04)' }, beginAtZero: true }
      }
    }
  });
}

function buildDonut(logs) {
  const types = {
    'Auth Failure':  logs.filter(l => l.event_type === 'auth_failure').length,
    'Forbidden':     logs.filter(l => l.event_type === 'forbidden_access').length,
    'Brute Force':   logs.filter(l => l.event_type === 'brute_force').length,
    'Server Error':  logs.filter(l => l.event_type === 'server_error').length,
    'API Access':    logs.filter(l => l.event_type === 'api_access').length,
    'Autres':        logs.filter(l => !l.event_type).length,
  };

  const labels = Object.keys(types).filter(k => types[k] > 0);
  const data   = labels.map(k => types[k]);
  const colors = ['#ff9f43','#ff4757','#ff6b7a','#ffd32a','#2ed573','#7a8aac'];

  if (donutChart) {
    donutChart.data.labels           = labels;
    donutChart.data.datasets[0].data = data;
    donutChart.update('none');
    return;
  }

  const ctx = $('donutChart').getContext('2d');
  donutChart = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels,
      datasets: [{ data, backgroundColor: colors, borderColor: '#05091a', borderWidth: 3, hoverOffset: 6 }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: '68%',
      plugins: {
        legend: {
          position: 'bottom',
          labels: { color: '#7a8aac', font: { size: 10 }, padding: 12, boxWidth: 10 }
        }
      }
    }
  });
}

// ── Log Tables ────────────────────────────────────────────
function renderRecentLogs(logs) {
  const tbody = $('recent-log-body');
  const recent = logs.slice(0, 20);

  if (!recent.length) {
    tbody.innerHTML = `<tr><td colspan="5" class="log-empty">Aucun log disponible — démarrez les services Docker</td></tr>`;
    return;
  }

  tbody.innerHTML = recent.map(l => `
    <tr>
      <td>${formatTs(l.timestamp)}</td>
      <td>${levelBadge(l.level)}</td>
      <td>${l.service || '—'}</td>
      <td title="${(l.message || '').replace(/"/g, '&quot;')}">${l.message || '—'}</td>
      <td>${l.ip || '—'}</td>
    </tr>
  `).join('');
}

let filteredLogs = [];
function renderFullLogs(logs) {
  filteredLogs = logs;
  applyFilters();
}

function applyFilters() {
  const levelF   = $('filter-level').value.toUpperCase();
  const serviceF = $('filter-service').value.toLowerCase();
  const searchF  = $('filter-search').value.toLowerCase();

  const filtered = filteredLogs.filter(l => {
    if (levelF   && (l.level  || '').toUpperCase()  !== levelF)   return false;
    if (serviceF && (l.service|| '').toLowerCase() !== serviceF) return false;
    if (searchF  && !(l.message||'').toLowerCase().includes(searchF)) return false;
    return true;
  });

  const tbody = $('full-log-body');
  if (!filtered.length) {
    tbody.innerHTML = `<tr><td colspan="6" class="log-empty">Aucun résultat pour ces filtres</td></tr>`;
    return;
  }

  tbody.innerHTML = filtered.slice(0, 200).map(l => `
    <tr>
      <td>${formatTs(l.timestamp)}</td>
      <td>${levelBadge(l.level)}</td>
      <td>${l.service || '—'}</td>
      <td title="${(l.message||'').replace(/"/g,'&quot;')}">${l.message || '—'}</td>
      <td>${l.ip || '—'}</td>
      <td>${eventTag(l.event_type)}</td>
    </tr>
  `).join('');
}

// ── Alerts ────────────────────────────────────────────────
function detectAlerts(logs) {
  const alerts = [];
  const seenBruteIPs = new Set();

  // Brute force — détection directe via event_type=brute_force (chaque event = attaque confirmée)
  logs.filter(l => l.event_type === 'brute_force').forEach(l => {
    const ip = (l.ip || 'unknown').split(',')[0].trim();
    if (!seenBruteIPs.has(ip)) {
      seenBruteIPs.add(ip);
      const attempts = l.failed_attempts || '?';
      alerts.push({
        type: 'BRUTE FORCE',
        severity: 'critical',
        title: `Attaque Brute Force détectée`,
        desc: `IP ${ip} a déclenché une alerte brute force (${attempts} tentatives détectées)`,
        meta: `IP: ${ip} · Tentatives: ${attempts}`
      });
    }
  });

  // Brute force secondaire — agrégation des auth_failure par IP (seuil 5)
  const ipFails = {};
  logs.filter(l => l.event_type === 'auth_failure').forEach(l => {
    const ip = (l.ip || 'unknown').split(',')[0].trim();
    ipFails[ip] = (ipFails[ip] || 0) + 1;
  });
  Object.entries(ipFails).forEach(([ip, count]) => {
    if (count >= 5 && !seenBruteIPs.has(ip)) {
      seenBruteIPs.add(ip);
      alerts.push({
        type: 'BRUTE FORCE',
        severity: 'critical',
        title: `Attaque Brute Force détectée`,
        desc: `IP ${ip} a échoué ${count} tentatives d'authentification en 24h`,
        meta: `IP: ${ip} · Échecs: ${count}`
      });
    }
  });

  // Accès interdits répétés par IP (seuil 5)
  const ipForbidden = {};
  logs.filter(l => l.event_type === 'forbidden_access').forEach(l => {
    const ip = (l.ip || 'unknown').split(',')[0].trim();
    ipForbidden[ip] = (ipForbidden[ip] || 0) + 1;
  });
  Object.entries(ipForbidden).forEach(([ip, count]) => {
    if (count >= 5) {
      alerts.push({
        type: 'ACCÈS INTERDIT',
        severity: 'high',
        title: `Tentatives d'accès non autorisées répétées`,
        desc: `IP ${ip} a tenté ${count} accès interdits en 24h`,
        meta: `IP: ${ip} · Tentatives 403: ${count}`
      });
    }
  });

  // Erreurs système répétées par service (seuil 5)
  const svcErrors = {};
  logs.filter(l => l.level === 'ERROR' || l.status === 500).forEach(l => {
    const s = l.service || 'unknown';
    svcErrors[s] = (svcErrors[s] || 0) + 1;
  });
  Object.entries(svcErrors).forEach(([svc, count]) => {
    if (count >= 5) {
      alerts.push({
        type: 'ERREURS SYSTÈME',
        severity: 'medium',
        title: `Erreurs système répétées sur ${svc}`,
        desc: `${svc} a généré ${count} erreurs (500) en 24h — instabilité possible`,
        meta: `Service: ${svc} · Erreurs 500: ${count}`
      });
    }
  });

  renderAlerts(alerts);
}

function renderAlerts(alerts) {
  const container = $('alerts-container');
  const iconMap = {
    critical: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>`,
    high:     `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="4.93" y1="4.93" x2="19.07" y2="19.07"/></svg>`,
    medium:   `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/></svg>`
  };

  if (!alerts.length) {
    container.innerHTML = `<div class="alert-empty">
      <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10z"/><path d="M12 8v4"/><path d="M12 16h.01"/></svg>
      <p>Aucune alerte active détectée pour les dernières 24h.</p>
    </div>`;
    return;
  }

  container.innerHTML = alerts.map(a => `
    <div class="alert-card alert-card--${a.severity}">
      <div class="alert-icon alert-icon--${a.severity}">${iconMap[a.severity]}</div>
      <div class="alert-body">
        <div class="alert-title">
          <span class="badge badge-${a.severity === 'critical' ? 'CRITICAL' : a.severity === 'high' ? 'ERROR' : 'WARNING'}">${a.type}</span>
          &nbsp;${a.title}
        </div>
        <div class="alert-desc">${a.desc}</div>
        <div class="alert-meta">${a.meta}</div>
      </div>
    </div>
  `).join('');
}

// ── Services Status ───────────────────────────────────────
const SERVICES = [
  { name: 'Elasticsearch',  check: `${ES_BASE}/_cluster/health`,  port: '9200', role: 'Stockage & indexation des logs' },
  { name: 'Kibana',         check: '/kibana-health',              port: '5601', role: 'Visualisation ELK' },
  { name: 'Logstash',       check: '/logstash-health',            port: '5044', role: 'Pipeline de traitement des logs' },
  { name: 'Filebeat',       check: null,                          port: '—',    role: 'Collecte des fichiers de logs' },
  { name: 'Auth Service',   check: '/auth-health',                port: '—',    role: 'Authentification (interne via gateway)' },
  { name: 'API Service',    check: '/api-health',                 port: '—',    role: 'API principale (interne via gateway)' },
  { name: 'API Gateway',    check: '/gateway-health',             port: '8080', role: 'Point d\'entrée unique — rate limiting' },
  { name: 'Prometheus',     check: '/prometheus/-/healthy',       port: '9090', role: 'Collecte des métriques temps réel' },
  { name: 'Grafana',        check: '/grafana-health',             port: '3001', role: 'Dashboards de visualisation' },
  { name: 'Node Exporter',  check: '/node-exporter-health',       port: '9100', role: 'Métriques système hôte (CPU, RAM)' },
  { name: 'Nginx Exporter', check: '/nginx-exporter-health',      port: '9113', role: 'Métriques gateway Nginx' },
];

async function pingService(url) {
  if (!url) return null;
  try {
    const res = await fetch(url, { signal: AbortSignal.timeout(3000) });
    return res.ok;
  } catch {
    return false;
  }
}

async function updateServicesStatus(logs) {
  const grid = $('services-grid');

  // Count events per service from logs
  const evtCount = {};
  logs.forEach(l => {
    if (l.service) evtCount[l.service] = (evtCount[l.service] || 0) + 1;
  });

  // Probe all checkable services in parallel
  const statuses = await Promise.all(SERVICES.map(svc => pingService(svc.check)));

  grid.innerHTML = SERVICES.map((svc, i) => {
    const up    = statuses[i];
    const count = evtCount[svc.name.toLowerCase().replace(' ', '-')] || '—';
    const dotClass    = up === null ? 's-dot--unknown' : up ? 's-dot--up' : 's-dot--down';
    const statusLabel = up === null ? 'Non sondé' : up ? 'En ligne' : 'Hors ligne';

    return `<div class="service-card">
      <div class="service-header">
        <span class="service-name">${svc.name}</span>
        <div class="service-status">
          <div class="s-dot ${dotClass}"></div>
          <span>${statusLabel}</span>
        </div>
      </div>
      <div class="service-url">Port : ${svc.port}</div>
      <div class="service-events">Rôle : ${svc.role}</div>
      <div class="service-events">Événements 24h : ${count}</div>
    </div>`;
  }).join('');
}

// ── Main Refresh Loop ─────────────────────────────────────
async function refresh() {
  const ok = await checkES();

  if (!ok) {
    // Show demo data when ES not available
    loadDemoData();
    return;
  }

  const logs = await fetchLogs(1000);
  if (!logs) { loadDemoData(); return; }

  allLogs = logs;
  updateStats(logs);
  buildTimeline(logs);
  buildDonut(logs);
  renderRecentLogs(logs);
  renderFullLogs(logs);
  detectAlerts(logs);
  updateServicesStatus(logs);
}

// ── Demo Data (quand ES n'est pas encore démarré) ─────────
function loadDemoData() {
  const now = Date.now();
  const demo = [];
  const services = ['auth-service', 'api-service'];
  const types = [
    { level: 'INFO',     event: 'auth_success',    msg: 'Authentication successful for user admin', ip: '172.18.0.1' },
    { level: 'WARNING',  event: 'auth_failure',     msg: 'Authentication failed for user admin', ip: '10.0.0.5' },
    { level: 'WARNING',  event: 'forbidden_access', msg: '403 Forbidden — Access to /api/admin denied', ip: '192.168.1.42' },
    { level: 'ERROR',    event: 'server_error',     msg: '500 Internal Server Error on /api/data', ip: '172.18.0.3' },
    { level: 'CRITICAL', event: 'brute_force',      msg: 'BRUTE FORCE ATTACK detected from IP 10.0.0.5', ip: '10.0.0.5' },
    { level: 'INFO',     event: 'api_access',       msg: 'GET /api/users — 200 OK', ip: '172.18.0.1' },
  ];

  for (let i = 0; i < 80; i++) {
    const t = types[Math.floor(Math.random() * types.length)];
    demo.push({
      timestamp: new Date(now - Math.random() * 86400000).toISOString(),
      level: t.level, event_type: t.event, message: t.msg,
      service: services[Math.floor(Math.random() * services.length)],
      ip: t.ip, status: t.level === 'ERROR' ? 500 : t.event === 'forbidden_access' ? 403 : 200
    });
  }
  demo.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
  allLogs = demo;

  updateStats(demo);
  buildTimeline(demo);
  buildDonut(demo);
  renderRecentLogs(demo);
  renderFullLogs(demo);
  detectAlerts(demo);
  updateServicesStatus(demo);
}

// ── Monitoring Tab Switcher ───────────────────────────────
function switchMonTab(tab) {
  document.querySelectorAll('.mon-tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.mon-panels').forEach(p => p.classList.remove('active'));
  $(`tab-${tab}`).classList.add('active');
  $(`panels-${tab}`).classList.add('active');
}

// ── Prometheus Helpers ────────────────────────────────────
async function fetchPromRange(query) {
  const end   = Math.floor(Date.now() / 1000);
  const start = end - PROM_RANGE * 60;
  try {
    const url = `${PROM_BASE}/api/v1/query_range?` + new URLSearchParams({
      query, start, end, step: '30s'
    });
    const res = await fetch(url);
    if (!res.ok) return null;
    const json = await res.json();
    return json.data?.result || null;
  } catch { return null; }
}

async function fetchPromInstant(query) {
  try {
    const url = `${PROM_BASE}/api/v1/query?query=${encodeURIComponent(query)}`;
    const res = await fetch(url);
    if (!res.ok) return null;
    const json = await res.json();
    const result = json.data?.result;
    if (!result?.length) return null;
    return parseFloat(result[0].value[1]);
  } catch { return null; }
}

function rangeToPoints(result) {
  if (!result?.length) return { labels: [], data: [] };
  const values = result[0].values || [];
  return {
    labels: values.map(([ts]) =>
      new Date(ts * 1000).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })
    ),
    data: values.map(([, v]) => Math.max(0, parseFloat(v) || 0))
  };
}

function upsertChart(id, labels, datasets, yOpts = {}) {
  const ctx = document.getElementById(id);
  if (!ctx) return;

  const commonLine = (color, fill = false) => ({
    borderColor: color,
    backgroundColor: fill ? color.replace(')', ', 0.1)').replace('rgb', 'rgba') : 'transparent',
    fill,
    tension: 0.4,
    pointRadius: 0,
    borderWidth: 2
  });

  if (promCharts[id]) {
    promCharts[id].data.labels = labels;
    datasets.forEach((ds, i) => {
      if (promCharts[id].data.datasets[i])
        promCharts[id].data.datasets[i].data = ds.data;
    });
    promCharts[id].update('none');
    return;
  }

  promCharts[id] = new Chart(ctx, {
    type: 'line',
    data: { labels, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      plugins: { legend: { display: false }, tooltip: { mode: 'index', intersect: false } },
      scales: {
        x: {
          ticks: { color: '#7a8aac', font: { size: 9 }, maxTicksLimit: 7, maxRotation: 0 },
          grid:  { color: 'rgba(255,255,255,0.04)' }
        },
        y: {
          ticks: { color: '#7a8aac', font: { size: 9 } },
          grid:  { color: 'rgba(255,255,255,0.04)' },
          beginAtZero: true,
          ...yOpts
        }
      }
    }
  });
}

// ── Monitoring Refresh — Infrastructure ───────────────────
async function refreshInfra() {
  const [cpuRange, ramRange, authRpsRange, apiRpsRange,
         cpuNow, ramUsed, ramFree, authTotal, apiTotal] = await Promise.all([
    fetchPromRange('(1 - avg(rate(node_cpu_seconds_total{mode="idle"}[1m]))) * 100'),
    fetchPromRange('(node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes) / 1024 / 1024 / 1024'),
    fetchPromRange('sum(rate(flask_http_request_total{service="auth-service"}[1m]))'),
    fetchPromRange('sum(rate(flask_http_request_total{service="api-service"}[1m]))'),
    fetchPromInstant('(1 - avg(rate(node_cpu_seconds_total{mode="idle"}[1m]))) * 100'),
    fetchPromInstant('(node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes) / 1024 / 1024 / 1024'),
    fetchPromInstant('node_memory_MemAvailable_bytes / 1024 / 1024 / 1024'),
    fetchPromInstant('sum(flask_http_request_total{service="auth-service"})'),
    fetchPromInstant('sum(flask_http_request_total{service="api-service"})')
  ]);

  // CPU chart
  if (cpuRange) {
    const { labels, data } = rangeToPoints(cpuRange);
    upsertChart('chart-cpu', labels, [{
      label: 'CPU %', data,
      borderColor: '#00d4ff', backgroundColor: 'rgba(0,212,255,0.08)',
      fill: true, tension: 0.4, pointRadius: 0, borderWidth: 2
    }], { max: 100, ticks: { callback: v => v + '%', color: '#7a8aac', font: { size: 9 } } });
  }
  const cpuStr = cpuNow !== null ? cpuNow.toFixed(1) + '%' : '—';
  setText('prom-cpu-val', cpuStr);
  setText('prom-cpu-chart-val', cpuStr);

  // RAM chart
  if (ramRange) {
    const { labels, data } = rangeToPoints(ramRange);
    upsertChart('chart-ram', labels, [{
      label: 'RAM GB', data,
      borderColor: '#2ed573', backgroundColor: 'rgba(46,213,115,0.08)',
      fill: true, tension: 0.4, pointRadius: 0, borderWidth: 2
    }]);
  }
  const ramStr = ramUsed !== null ? ramUsed.toFixed(1) + ' GB' : '—';
  setText('prom-ram-val',      ramStr);
  setText('prom-ram-chart-val', ramStr);
  setText('prom-ram-free', ramFree !== null ? ramFree.toFixed(1) + ' GB libre' : '— libre');

  // HTTP req/s multi-series chart
  const authPts = rangeToPoints(authRpsRange);
  const apiPts  = rangeToPoints(apiRpsRange);
  const rpsLabels = authPts.labels.length >= apiPts.labels.length ? authPts.labels : apiPts.labels;
  upsertChart('chart-rps', rpsLabels, [
    {
      label: 'auth-service', data: authPts.data,
      borderColor: '#00d4ff', backgroundColor: 'transparent',
      fill: false, tension: 0.4, pointRadius: 0, borderWidth: 2
    },
    {
      label: 'api-service', data: apiPts.data,
      borderColor: '#2ed573', backgroundColor: 'transparent',
      fill: false, tension: 0.4, pointRadius: 0, borderWidth: 2
    }
  ]);

  setText('prom-auth-total', authTotal !== null ? Math.round(authTotal).toLocaleString() : '—');
  setText('prom-api-total',  apiTotal  !== null ? Math.round(apiTotal).toLocaleString()  : '—');
}

// ── 429 depuis Elasticsearch (gateway nginx, jamais vu par Flask) ──
async function fetchES429Total() {
  try {
    const body = {
      query: { bool: { must: [
        { term: { status: 429 } },
        { range: { '@timestamp': { gte: 'now-24h' } } }
      ]}},
      size: 0
    };
    const res = await fetch(`${ES_BASE}/${INDEX}/_search`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });
    const data = await res.json();
    return data.hits?.total?.value ?? null;
  } catch { return null; }
}

async function fetchES429Range() {
  try {
    const now = new Date();
    const start = new Date(now - PROM_RANGE * 60 * 1000);
    const body = {
      query: { bool: { must: [
        { term: { status: 429 } },
        { range: { '@timestamp': { gte: start.toISOString(), lte: now.toISOString() } } }
      ]}},
      size: 0,
      aggs: { per_minute: { date_histogram: { field: '@timestamp', fixed_interval: '1m' } } }
    };
    const res = await fetch(`${ES_BASE}/${INDEX}/_search`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });
    const data = await res.json();
    const buckets = data.aggregations?.per_minute?.buckets || [];
    return {
      labels: buckets.map(b => new Date(b.key).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })),
      data:   buckets.map(b => b.doc_count)
    };
  } catch { return { labels: [], data: [] }; }
}

// ── Monitoring Refresh — Security ─────────────────────────
async function refreshSecurity() {
  const [authFailRange, f403Range,
         bruteTotal, total403, total500,
         total429, ratePts] = await Promise.all([
    fetchPromRange('sum(increase(auth_failures_total[1m]))'),
    fetchPromRange('sum(increase(flask_http_request_total{status="403"}[1m]))'),
    fetchPromInstant('sum(brute_force_total)'),
    fetchPromInstant('sum(flask_http_request_total{status="403"})'),
    fetchPromInstant('sum(flask_http_request_total{status="500"})'),
    fetchES429Total(),
    fetchES429Range()
  ]);

  // Auth failures chart
  const authFailPts = rangeToPoints(authFailRange);
  upsertChart('chart-auth-fail', authFailPts.labels, [{
    label: 'Auth Failures', data: authFailPts.data,
    borderColor: '#ff9f43', backgroundColor: 'rgba(255,159,67,0.1)',
    fill: true, tension: 0.4, pointRadius: 0, borderWidth: 2
  }]);
  const lastAuth = authFailPts.data.at(-1) ?? null;
  setText('prom-auth-fail-val', lastAuth !== null ? lastAuth.toFixed(1) + '/min' : '—');

  // 429 rate-limit chart (source: Elasticsearch gateway logs)
  upsertChart('chart-429', ratePts.labels, [{
    label: '429 Rate Limited', data: ratePts.data,
    borderColor: '#ff4757', backgroundColor: 'rgba(255,71,87,0.1)',
    fill: true, tension: 0.4, pointRadius: 0, borderWidth: 2
  }]);
  const last429 = ratePts.data.length ? ratePts.data.at(-1) : null;
  setText('prom-429-val', last429 !== null ? last429 + '/min' : '—');

  // Security combo: 403 + auth failures
  const f403Pts = rangeToPoints(f403Range);
  const comboLabels = f403Pts.labels.length >= authFailPts.labels.length
    ? f403Pts.labels : authFailPts.labels;
  upsertChart('chart-security-combo', comboLabels, [
    {
      label: '403', data: f403Pts.data,
      borderColor: '#ff4757', backgroundColor: 'transparent',
      fill: false, tension: 0.4, pointRadius: 0, borderWidth: 2
    },
    {
      label: 'Auth Failures', data: authFailPts.data,
      borderColor: '#ff9f43', backgroundColor: 'transparent',
      fill: false, tension: 0.4, pointRadius: 0, borderWidth: 2
    }
  ]);

  setText('prom-brute-total', bruteTotal !== null ? Math.round(bruteTotal) : '—');
  setText('prom-403-total',   total403   !== null ? Math.round(total403)   : '—');
  setText('prom-500-total',   total500   !== null ? Math.round(total500)   : '—');
  setText('prom-429-total',   total429   !== null ? total429 : '—');
}

async function refreshMonitoring() {
  await Promise.all([refreshInfra(), refreshSecurity()]);
  const now = new Date().toLocaleTimeString('fr-FR', { hour12: false });
  $('prom-last-update').textContent = `Mis à jour : ${now}`;
}

// ── Init ──────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  startClock();
  refresh();
  refreshTimer = setInterval(refresh, REFRESH_MS);
  // Monitoring charts are lazy-initialized on first visit (see showSection)
});
