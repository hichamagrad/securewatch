"""
generate_missing_screenshots.py
Generates the 4 missing rapport screenshots:
  - gateway_rate_limit.png   (terminal output, Phase 1)
  - rate_limit_terminal.png  (terminal output, Phase 2)
  - architecture_diagram.png (SVG rendered via Playwright)
  - flux_donnees.png         (SVG rendered via Playwright)
"""

import os, subprocess, sys, textwrap
from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import sync_playwright

OUT = os.path.join(os.path.dirname(__file__), '..', 'rapport', 'screenshots')
os.makedirs(OUT, exist_ok=True)

# ── 1. Run rate-limit scenario and capture output ─────────────────────────────
print("[1/4] Running rate-limit scenario...")
result = subprocess.run(
    [sys.executable, os.path.join(os.path.dirname(__file__), 'generate_attacks.py'),
     '--scenario', 'rate-limit', '--delay', '0.04'],
    capture_output=True, text=True, timeout=120,
    cwd=os.path.dirname(os.path.dirname(__file__))
)
raw = result.stdout + (result.stderr if result.stderr else '')
lines = raw.splitlines()
print(f"  captured {len(lines)} lines of output")

# ── 2. Render terminal lines as PNG ──────────────────────────────────────────

BG        = (13, 17, 23)        # dark background
FG        = (201, 209, 217)     # default text
GREEN     = (63, 185, 80)
RED       = (248, 81, 73)
YELLOW    = (210, 153, 34)
CYAN      = (121, 192, 255)
MAGENTA   = (188, 140, 255)

FONT_SIZE = 15
PAD_X, PAD_Y = 24, 20
LINE_H    = FONT_SIZE + 5

# Try to load a monospace font; fall back to default
def load_font(size):
    candidates = [
        "C:/Windows/Fonts/consola.ttf",
        "C:/Windows/Fonts/cour.ttf",
        "C:/Windows/Fonts/lucon.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()

font      = load_font(FONT_SIZE)
font_bold = load_font(FONT_SIZE)   # same size, bold not critical here

def line_color(text):
    t = text.upper()
    if 'RATE LIMITED' in t:   return RED
    if '429' in t:             return RED
    if 'PHASE' in t:           return MAGENTA
    if 'SCENARIO' in t:        return CYAN
    if '200' in t:             return GREEN
    if '401' in t or '403' in t: return YELLOW
    if 'OK' in t and '[OK]' in t: return GREEN
    if 'VERIFICATION' in t or '==' in t: return CYAN
    return FG

def render_terminal(lines_subset, path, title=None):
    w = 1200
    total_lines = len(lines_subset) + (2 if title else 0)
    h = PAD_Y * 2 + total_lines * LINE_H + 10
    img = Image.new('RGB', (w, h), BG)
    draw = ImageDraw.Draw(img)

    # Title bar
    draw.rectangle([0, 0, w, 30], fill=(31, 36, 43))
    bar_text = title or "PowerShell  —  SecureWatch Attack Simulator"
    draw.text((12, 7), bar_text, fill=FG, font=font)
    # Traffic lights
    for xi, col in [(w-60, (255,95,86)), (w-40, (255,189,46)), (w-20, (40,200,64))]:
        draw.ellipse([xi-6, 11, xi+6, 23], fill=col)

    y = 38
    for line in lines_subset:
        col = line_color(line)
        # Wrap long lines
        max_chars = (w - PAD_X * 2) // (FONT_SIZE // 2 + 1)
        if len(line) > max_chars:
            line = line[:max_chars - 3] + '...'
        draw.text((PAD_X, y), line, fill=col, font=font)
        y += LINE_H

    img.save(path, 'PNG')
    print(f"  [OK] {os.path.basename(path)}  ({os.path.getsize(path)//1024} KB)")

# Split output: Phase 1 = up to Phase 2 line, Phase 2 = rest
phase2_idx = next((i for i, l in enumerate(lines) if 'Phase 2' in l), len(lines)//2)

phase1_lines = lines[:phase2_idx + 1]   # include the Phase 2 header so context is clear
phase2_lines = lines[phase2_idx:]        # Phase 2 onwards

# gateway_rate_limit.png — show Phase 1 (first 50 lines)
render_terminal(
    phase1_lines[:55],
    os.path.join(OUT, 'gateway_rate_limit.png'),
    title="PowerShell  —  python generate_attacks.py --scenario rate-limit"
)

# rate_limit_terminal.png — Phase 2 onwards
render_terminal(
    phase2_lines[:40],
    os.path.join(OUT, 'rate_limit_terminal.png'),
    title="PowerShell  —  Phase 2: auth/login rate limiting (5 req/min)"
)

# ── 3 & 4. Architecture + Data-flow diagrams via Playwright SVG ──────────────

ARCH_HTML = """<!DOCTYPE html><html><head><meta charset="utf-8">
<style>
  body { margin:0; background:#0d1117; font-family: 'Segoe UI', sans-serif; }
  svg { display:block; }
  text { font-family: 'Segoe UI', sans-serif; }
</style></head><body>
<svg width="1400" height="860" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <marker id="arr" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
      <path d="M0,0 L0,6 L8,3 z" fill="#58a6ff"/>
    </marker>
    <marker id="arr2" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
      <path d="M0,0 L0,6 L8,3 z" fill="#3fb950"/>
    </marker>
    <marker id="arr3" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
      <path d="M0,0 L0,6 L8,3 z" fill="#d29922"/>
    </marker>
    <filter id="glow">
      <feGaussianBlur stdDeviation="2" result="coloredBlur"/>
      <feMerge><feMergeNode in="coloredBlur"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
  </defs>

  <!-- Title -->
  <text x="700" y="38" text-anchor="middle" fill="#e6edf3" font-size="22" font-weight="bold">Architecture SecureWatch — PFA 2025-2026</text>

  <!-- ── Zone: Internet / Client ─────────────────────── -->
  <rect x="20" y="60" width="180" height="70" rx="10" fill="#161b22" stroke="#30363d" stroke-width="1.5"/>
  <text x="110" y="91" text-anchor="middle" fill="#8b949e" font-size="11">INTERNET</text>
  <text x="110" y="112" text-anchor="middle" fill="#c9d1d9" font-size="14">🌐 Client / Browser</text>

  <!-- ── Zone: Gateway ───────────────────────────────── -->
  <rect x="255" y="55" width="200" height="80" rx="10" fill="#1c2128" stroke="#58a6ff" stroke-width="2"/>
  <text x="355" y="80" text-anchor="middle" fill="#58a6ff" font-size="12" font-weight="bold">API GATEWAY</text>
  <text x="355" y="100" text-anchor="middle" fill="#c9d1d9" font-size="13">Nginx Reverse Proxy</text>
  <text x="355" y="118" text-anchor="middle" fill="#8b949e" font-size="11">:8443 HTTPS · :8080 HTTP</text>

  <!-- Client → Gateway -->
  <line x1="200" y1="95" x2="253" y2="95" stroke="#58a6ff" stroke-width="1.8" marker-end="url(#arr)"/>
  <text x="226" y="88" text-anchor="middle" fill="#8b949e" font-size="10">HTTPS</text>

  <!-- ── Zone: Services ──────────────────────────────── -->
  <!-- Auth Service -->
  <rect x="520" y="40" width="170" height="70" rx="10" fill="#1c2128" stroke="#3fb950" stroke-width="2"/>
  <text x="605" y="65" text-anchor="middle" fill="#3fb950" font-size="12" font-weight="bold">auth-service</text>
  <text x="605" y="83" text-anchor="middle" fill="#c9d1d9" font-size="12">Flask :5001</text>
  <text x="605" y="100" text-anchor="middle" fill="#8b949e" font-size="10">JWT · Login · Register</text>

  <!-- API Service -->
  <rect x="520" y="130" width="170" height="70" rx="10" fill="#1c2128" stroke="#3fb950" stroke-width="2"/>
  <text x="605" y="155" text-anchor="middle" fill="#3fb950" font-size="12" font-weight="bold">api-service</text>
  <text x="605" y="173" text-anchor="middle" fill="#c9d1d9" font-size="12">Flask :5002</text>
  <text x="605" y="190" text-anchor="middle" fill="#8b949e" font-size="10">Data · Upload · Protected</text>

  <!-- Frontend -->
  <rect x="520" y="220" width="170" height="70" rx="10" fill="#1c2128" stroke="#3fb950" stroke-width="2"/>
  <text x="605" y="245" text-anchor="middle" fill="#3fb950" font-size="12" font-weight="bold">frontend</text>
  <text x="605" y="263" text-anchor="middle" fill="#c9d1d9" font-size="12">Nginx :3000</text>
  <text x="605" y="280" text-anchor="middle" fill="#8b949e" font-size="10">Dashboard SPA</text>

  <!-- Gateway → Services -->
  <line x1="455" y1="80" x2="518" y2="78" stroke="#58a6ff" stroke-width="1.5" marker-end="url(#arr)"/>
  <line x1="455" y1="95" x2="518" y2="165" stroke="#58a6ff" stroke-width="1.5" marker-end="url(#arr)"/>
  <line x1="455" y1="110" x2="518" y2="255" stroke="#58a6ff" stroke-width="1.5" marker-end="url(#arr)"/>

  <!-- ── Zone: ELK Stack ─────────────────────────────── -->
  <rect x="22" y="380" width="620" height="230" rx="12" fill="#161b22" stroke="#d29922" stroke-width="1.5" stroke-dasharray="6,3"/>
  <text x="332" y="404" text-anchor="middle" fill="#d29922" font-size="13" font-weight="bold">ELK STACK — Log Management</text>

  <!-- Filebeat -->
  <rect x="40" y="415" width="140" height="65" rx="8" fill="#1c2128" stroke="#d29922" stroke-width="1.5"/>
  <text x="110" y="440" text-anchor="middle" fill="#d29922" font-size="12" font-weight="bold">Filebeat</text>
  <text x="110" y="458" text-anchor="middle" fill="#c9d1d9" font-size="11">Log Shipper</text>
  <text x="110" y="474" text-anchor="middle" fill="#8b949e" font-size="10">/logs/*.log</text>

  <!-- Logstash -->
  <rect x="220" y="415" width="140" height="65" rx="8" fill="#1c2128" stroke="#d29922" stroke-width="1.5"/>
  <text x="290" y="440" text-anchor="middle" fill="#d29922" font-size="12" font-weight="bold">Logstash</text>
  <text x="290" y="458" text-anchor="middle" fill="#c9d1d9" font-size="11">Parse &amp; Enrich</text>
  <text x="290" y="474" text-anchor="middle" fill="#8b949e" font-size="10">:5044 Beats input</text>

  <!-- Elasticsearch -->
  <rect x="400" y="415" width="140" height="65" rx="8" fill="#1c2128" stroke="#d29922" stroke-width="1.5"/>
  <text x="470" y="440" text-anchor="middle" fill="#d29922" font-size="12" font-weight="bold">Elasticsearch</text>
  <text x="470" y="458" text-anchor="middle" fill="#c9d1d9" font-size="11">Index &amp; Store</text>
  <text x="470" y="474" text-anchor="middle" fill="#8b949e" font-size="10">security-logs-*</text>

  <!-- Kibana -->
  <rect x="220" y="510" width="140" height="65" rx="8" fill="#1c2128" stroke="#d29922" stroke-width="1.5"/>
  <text x="290" y="535" text-anchor="middle" fill="#d29922" font-size="12" font-weight="bold">Kibana</text>
  <text x="290" y="553" text-anchor="middle" fill="#c9d1d9" font-size="11">Visualize &amp; Search</text>
  <text x="290" y="569" text-anchor="middle" fill="#8b949e" font-size="10">:5601</text>

  <!-- ELK arrows -->
  <line x1="180" y1="447" x2="218" y2="447" stroke="#d29922" stroke-width="1.5" marker-end="url(#arr3)"/>
  <line x1="360" y1="447" x2="398" y2="447" stroke="#d29922" stroke-width="1.5" marker-end="url(#arr3)"/>
  <line x1="470" y1="480" x2="470" y2="510" stroke="#d29922" stroke-width="1.5"/>
  <line x1="470" y1="510" x2="330" y2="510" stroke="#d29922" stroke-width="1.5" marker-end="url(#arr3)"/>

  <!-- ── Zone: Monitoring ────────────────────────────── -->
  <rect x="700" y="380" width="680" height="230" rx="12" fill="#161b22" stroke="#bc8cff" stroke-width="1.5" stroke-dasharray="6,3"/>
  <text x="1040" y="404" text-anchor="middle" fill="#bc8cff" font-size="13" font-weight="bold">MONITORING STACK</text>

  <!-- Prometheus -->
  <rect x="720" y="415" width="150" height="65" rx="8" fill="#1c2128" stroke="#bc8cff" stroke-width="1.5"/>
  <text x="795" y="440" text-anchor="middle" fill="#bc8cff" font-size="12" font-weight="bold">Prometheus</text>
  <text x="795" y="458" text-anchor="middle" fill="#c9d1d9" font-size="11">Metrics Scraping</text>
  <text x="795" y="474" text-anchor="middle" fill="#8b949e" font-size="10">:9090</text>

  <!-- Alertmanager -->
  <rect x="910" y="415" width="150" height="65" rx="8" fill="#1c2128" stroke="#bc8cff" stroke-width="1.5"/>
  <text x="985" y="440" text-anchor="middle" fill="#bc8cff" font-size="12" font-weight="bold">Alertmanager</text>
  <text x="985" y="458" text-anchor="middle" fill="#c9d1d9" font-size="11">Alert Routing</text>
  <text x="985" y="474" text-anchor="middle" fill="#8b949e" font-size="10">:9093</text>

  <!-- Grafana -->
  <rect x="1100" y="415" width="150" height="65" rx="8" fill="#1c2128" stroke="#bc8cff" stroke-width="1.5"/>
  <text x="1175" y="440" text-anchor="middle" fill="#bc8cff" font-size="12" font-weight="bold">Grafana</text>
  <text x="1175" y="458" text-anchor="middle" fill="#c9d1d9" font-size="11">Dashboards</text>
  <text x="1175" y="474" text-anchor="middle" fill="#8b949e" font-size="10">:3001</text>

  <!-- Node Exporter -->
  <rect x="720" y="510" width="150" height="65" rx="8" fill="#1c2128" stroke="#bc8cff" stroke-width="1.5"/>
  <text x="795" y="535" text-anchor="middle" fill="#bc8cff" font-size="12" font-weight="bold">Node Exporter</text>
  <text x="795" y="553" text-anchor="middle" fill="#c9d1d9" font-size="11">Host Metrics</text>
  <text x="795" y="569" text-anchor="middle" fill="#8b949e" font-size="10">:9100</text>

  <!-- Monitoring arrows -->
  <line x1="870" y1="447" x2="908" y2="447" stroke="#bc8cff" stroke-width="1.5" marker-end="url(#arr)"/>
  <line x1="1060" y1="447" x2="1098" y2="447" stroke="#bc8cff" stroke-width="1.5" marker-end="url(#arr)"/>
  <line x1="795" y1="508" x2="795" y2="482" stroke="#bc8cff" stroke-width="1.5" marker-end="url(#arr)"/>
  <text x="810" y="499" fill="#8b949e" font-size="10">scrape</text>

  <!-- ── Services → ELK (log shipping) ──────────────── -->
  <line x1="605" y1="310" x2="605" y2="380" stroke="#d29922" stroke-width="1.5" stroke-dasharray="4,3"/>
  <line x1="605" y1="380" x2="180" y2="430" stroke="#d29922" stroke-width="1.5" stroke-dasharray="4,3" marker-end="url(#arr3)"/>
  <text x="450" y="370" fill="#d29922" font-size="10">logs → Filebeat</text>

  <!-- Services → Prometheus (metrics) -->
  <line x1="690" y1="165" x2="760" y2="415" stroke="#bc8cff" stroke-width="1.5" stroke-dasharray="4,3" marker-end="url(#arr)"/>
  <text x="760" y="310" fill="#bc8cff" font-size="10">metrics :8000</text>

  <!-- ── Networks legend ─────────────────────────────── -->
  <rect x="20" y="660" width="1360" height="90" rx="8" fill="#161b22" stroke="#30363d" stroke-width="1"/>
  <text x="700" y="682" text-anchor="middle" fill="#8b949e" font-size="12" font-weight="bold">RÉSEAUX DOCKER</text>

  <rect x="40" y="695" width="14" height="14" fill="#58a6ff"/>
  <text x="60" y="707" fill="#c9d1d9" font-size="11">gateway-net  (Nginx ↔ auth/api/frontend)</text>

  <rect x="360" y="695" width="14" height="14" fill="#d29922"/>
  <text x="380" y="707" fill="#c9d1d9" font-size="11">elk-net  (Filebeat → Logstash → Elasticsearch → Kibana)</text>

  <rect x="730" y="695" width="14" height="14" fill="#bc8cff"/>
  <text x="750" y="707" fill="#c9d1d9" font-size="11">monitoring-net  (Prometheus → Alertmanager → Grafana)</text>

  <text x="40" y="738" fill="#8b949e" font-size="10">13 conteneurs Docker · 3 réseaux isolés · Tout trafic passe par le gateway Nginx (CSP, rate-limit, CORS)</text>
</svg>
</body></html>"""

FLUX_HTML = """<!DOCTYPE html><html><head><meta charset="utf-8">
<style>
  body { margin:0; background:#0d1117; font-family: 'Segoe UI', sans-serif; }
  svg { display:block; }
  text { font-family: 'Segoe UI', sans-serif; }
</style></head><body>
<svg width="1400" height="760" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <marker id="arr" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto">
      <path d="M0,0 L0,6 L9,3 z" fill="#58a6ff"/>
    </marker>
    <marker id="arrg" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto">
      <path d="M0,0 L0,6 L9,3 z" fill="#3fb950"/>
    </marker>
    <marker id="arry" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto">
      <path d="M0,0 L0,6 L9,3 z" fill="#d29922"/>
    </marker>
    <marker id="arrp" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto">
      <path d="M0,0 L0,6 L9,3 z" fill="#bc8cff"/>
    </marker>
    <marker id="arrr" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto">
      <path d="M0,0 L0,6 L9,3 z" fill="#f85149"/>
    </marker>
  </defs>

  <!-- Title -->
  <text x="700" y="40" text-anchor="middle" fill="#e6edf3" font-size="22" font-weight="bold">Flux de Données — SecureWatch PFA 2025-2026</text>

  <!-- ════════════════════════════════════════════
       ROW 1 : LOG FLOW
  ═════════════════════════════════════════════ -->
  <text x="700" y="80" text-anchor="middle" fill="#d29922" font-size="13" font-weight="bold">── FLUX DE LOGS ─────────────────────────────────────────────────────────────────</text>

  <!-- Services box -->
  <rect x="30" y="95" width="150" height="100" rx="8" fill="#1c2128" stroke="#3fb950" stroke-width="2"/>
  <text x="105" y="120" text-anchor="middle" fill="#3fb950" font-size="13" font-weight="bold">Services</text>
  <text x="105" y="140" text-anchor="middle" fill="#8b949e" font-size="10">auth-service</text>
  <text x="105" y="155" text-anchor="middle" fill="#8b949e" font-size="10">api-service</text>
  <text x="105" y="170" text-anchor="middle" fill="#8b949e" font-size="10">nginx gateway</text>
  <text x="105" y="185" text-anchor="middle" fill="#8b949e" font-size="10">/logs/*.log</text>

  <!-- Filebeat -->
  <rect x="240" y="110" width="130" height="70" rx="8" fill="#1c2128" stroke="#d29922" stroke-width="1.5"/>
  <text x="305" y="135" text-anchor="middle" fill="#d29922" font-size="12" font-weight="bold">Filebeat</text>
  <text x="305" y="155" text-anchor="middle" fill="#c9d1d9" font-size="11">tail logs</text>
  <text x="305" y="171" text-anchor="middle" fill="#8b949e" font-size="10">→ Beats protocol</text>

  <!-- Logstash -->
  <rect x="430" y="110" width="140" height="70" rx="8" fill="#1c2128" stroke="#d29922" stroke-width="1.5"/>
  <text x="500" y="135" text-anchor="middle" fill="#d29922" font-size="12" font-weight="bold">Logstash</text>
  <text x="500" y="153" text-anchor="middle" fill="#c9d1d9" font-size="11">Parse JSON</text>
  <text x="500" y="170" text-anchor="middle" fill="#8b949e" font-size="10">Grok · GeoIP · Mutate</text>

  <!-- Elasticsearch -->
  <rect x="630" y="110" width="150" height="70" rx="8" fill="#1c2128" stroke="#d29922" stroke-width="1.5"/>
  <text x="705" y="135" text-anchor="middle" fill="#d29922" font-size="12" font-weight="bold">Elasticsearch</text>
  <text x="705" y="153" text-anchor="middle" fill="#c9d1d9" font-size="11">Index: security-logs-*</text>
  <text x="705" y="170" text-anchor="middle" fill="#8b949e" font-size="10">Full-text search</text>

  <!-- Kibana -->
  <rect x="850" y="110" width="130" height="70" rx="8" fill="#1c2128" stroke="#d29922" stroke-width="1.5"/>
  <text x="915" y="135" text-anchor="middle" fill="#d29922" font-size="12" font-weight="bold">Kibana</text>
  <text x="915" y="153" text-anchor="middle" fill="#c9d1d9" font-size="11">Discover</text>
  <text x="915" y="170" text-anchor="middle" fill="#8b949e" font-size="10">Visualize :5601</text>

  <!-- Dashboard (reads ES too) -->
  <rect x="1060" y="110" width="150" height="70" rx="8" fill="#1c2128" stroke="#58a6ff" stroke-width="1.5"/>
  <text x="1135" y="135" text-anchor="middle" fill="#58a6ff" font-size="12" font-weight="bold">Dashboard</text>
  <text x="1135" y="153" text-anchor="middle" fill="#c9d1d9" font-size="11">SecureWatch SPA</text>
  <text x="1135" y="170" text-anchor="middle" fill="#8b949e" font-size="10">Logs · Alertes :3000</text>

  <!-- Log flow arrows -->
  <line x1="180" y1="145" x2="238" y2="145" stroke="#d29922" stroke-width="2" marker-end="url(#arry)"/>
  <line x1="370" y1="145" x2="428" y2="145" stroke="#d29922" stroke-width="2" marker-end="url(#arry)"/>
  <line x1="570" y1="145" x2="628" y2="145" stroke="#d29922" stroke-width="2" marker-end="url(#arry)"/>
  <line x1="780" y1="145" x2="848" y2="145" stroke="#d29922" stroke-width="2" marker-end="url(#arry)"/>
  <line x1="780" y1="155" x2="1060" y2="155" stroke="#58a6ff" stroke-width="1.5" stroke-dasharray="4,3" marker-end="url(#arr)"/>

  <text x="209" y="140" text-anchor="middle" fill="#8b949e" font-size="9">tail</text>
  <text x="399" y="140" text-anchor="middle" fill="#8b949e" font-size="9">:5044</text>
  <text x="599" y="140" text-anchor="middle" fill="#8b949e" font-size="9">REST</text>
  <text x="814" y="140" text-anchor="middle" fill="#8b949e" font-size="9">query</text>

  <!-- ════════════════════════════════════════════
       ROW 2 : METRICS FLOW
  ═════════════════════════════════════════════ -->
  <text x="700" y="235" text-anchor="middle" fill="#bc8cff" font-size="13" font-weight="bold">── FLUX DE MÉTRIQUES ────────────────────────────────────────────────────────────</text>

  <!-- Exporters -->
  <rect x="30" y="250" width="150" height="120" rx="8" fill="#1c2128" stroke="#bc8cff" stroke-width="2"/>
  <text x="105" y="275" text-anchor="middle" fill="#bc8cff" font-size="13" font-weight="bold">Exporteurs</text>
  <text x="105" y="295" text-anchor="middle" fill="#8b949e" font-size="10">node-exporter :9100</text>
  <text x="105" y="312" text-anchor="middle" fill="#8b949e" font-size="10">auth-service :8000</text>
  <text x="105" y="329" text-anchor="middle" fill="#8b949e" font-size="10">api-service  :8000</text>
  <text x="105" y="346" text-anchor="middle" fill="#8b949e" font-size="10">elasticsearch :9200</text>
  <text x="105" y="363" text-anchor="middle" fill="#8b949e" font-size="10">nginx :9113</text>

  <!-- Prometheus -->
  <rect x="250" y="270" width="150" height="80" rx="8" fill="#1c2128" stroke="#bc8cff" stroke-width="1.5"/>
  <text x="325" y="298" text-anchor="middle" fill="#bc8cff" font-size="12" font-weight="bold">Prometheus</text>
  <text x="325" y="316" text-anchor="middle" fill="#c9d1d9" font-size="11">Scrape every 15s</text>
  <text x="325" y="334" text-anchor="middle" fill="#8b949e" font-size="10">TSDB :9090</text>

  <!-- Alert rules -->
  <rect x="470" y="270" width="150" height="80" rx="8" fill="#1c2128" stroke="#f85149" stroke-width="1.5"/>
  <text x="545" y="298" text-anchor="middle" fill="#f85149" font-size="12" font-weight="bold">Règles d'alerte</text>
  <text x="545" y="316" text-anchor="middle" fill="#c9d1d9" font-size="11">BruteForceDetected</text>
  <text x="545" y="334" text-anchor="middle" fill="#8b949e" font-size="10">HighErrorRate …</text>

  <!-- Alertmanager -->
  <rect x="690" y="270" width="150" height="80" rx="8" fill="#1c2128" stroke="#f85149" stroke-width="1.5"/>
  <text x="765" y="298" text-anchor="middle" fill="#f85149" font-size="12" font-weight="bold">Alertmanager</text>
  <text x="765" y="316" text-anchor="middle" fill="#c9d1d9" font-size="11">Route · Group</text>
  <text x="765" y="334" text-anchor="middle" fill="#8b949e" font-size="10">:9093</text>

  <!-- Grafana -->
  <rect x="910" y="270" width="150" height="80" rx="8" fill="#1c2128" stroke="#bc8cff" stroke-width="1.5"/>
  <text x="985" y="298" text-anchor="middle" fill="#bc8cff" font-size="12" font-weight="bold">Grafana</text>
  <text x="985" y="316" text-anchor="middle" fill="#c9d1d9" font-size="11">Infrastructure</text>
  <text x="985" y="334" text-anchor="middle" fill="#8b949e" font-size="10">Sécurité :3001</text>

  <!-- Dashboard reads Prometheus too -->
  <rect x="1130" y="270" width="150" height="80" rx="8" fill="#1c2128" stroke="#58a6ff" stroke-width="1.5"/>
  <text x="1205" y="298" text-anchor="middle" fill="#58a6ff" font-size="12" font-weight="bold">Dashboard</text>
  <text x="1205" y="316" text-anchor="middle" fill="#c9d1d9" font-size="11">Monitoring tab</text>
  <text x="1205" y="334" text-anchor="middle" fill="#8b949e" font-size="10">/api/v1/query</text>

  <!-- Metrics arrows -->
  <line x1="180" y1="310" x2="248" y2="310" stroke="#bc8cff" stroke-width="2" marker-end="url(#arrp)"/>
  <line x1="400" y1="310" x2="468" y2="310" stroke="#bc8cff" stroke-width="2" marker-end="url(#arrp)"/>
  <line x1="620" y1="310" x2="688" y2="310" stroke="#f85149" stroke-width="2" marker-end="url(#arrr)"/>
  <line x1="840" y1="310" x2="908" y2="310" stroke="#bc8cff" stroke-width="2" marker-end="url(#arrp)"/>
  <line x1="840" y1="320" x2="1130" y2="320" stroke="#58a6ff" stroke-width="1.5" stroke-dasharray="4,3" marker-end="url(#arr)"/>

  <text x="214" y="305" text-anchor="middle" fill="#8b949e" font-size="9">scrape</text>
  <text x="434" y="305" text-anchor="middle" fill="#8b949e" font-size="9">eval</text>
  <text x="654" y="305" text-anchor="middle" fill="#8b949e" font-size="9">fire</text>
  <text x="874" y="305" text-anchor="middle" fill="#8b949e" font-size="9">query</text>

  <!-- ════════════════════════════════════════════
       ROW 3 : REQUEST FLOW
  ═════════════════════════════════════════════ -->
  <text x="700" y="415" text-anchor="middle" fill="#58a6ff" font-size="13" font-weight="bold">── FLUX DE REQUÊTES (HTTP) ──────────────────────────────────────────────────────</text>

  <rect x="30" y="430" width="130" height="70" rx="8" fill="#1c2128" stroke="#58a6ff" stroke-width="2"/>
  <text x="95" y="456" text-anchor="middle" fill="#58a6ff" font-size="13" font-weight="bold">Client</text>
  <text x="95" y="474" text-anchor="middle" fill="#c9d1d9" font-size="11">Browser / curl</text>
  <text x="95" y="490" text-anchor="middle" fill="#8b949e" font-size="10">HTTPS :8443</text>

  <rect x="220" y="425" width="220" height="80" rx="8" fill="#1c2128" stroke="#58a6ff" stroke-width="2"/>
  <text x="330" y="450" text-anchor="middle" fill="#58a6ff" font-size="12" font-weight="bold">Nginx Gateway</text>
  <text x="330" y="468" text-anchor="middle" fill="#c9d1d9" font-size="11">Rate-limit · CSP · CORS</text>
  <text x="330" y="485" text-anchor="middle" fill="#8b949e" font-size="10">JWT verify · Allowlist routes</text>
  <text x="330" y="500" text-anchor="middle" fill="#8b949e" font-size="10">X-Real-IP injection</text>

  <rect x="500" y="430" width="130" height="70" rx="8" fill="#1c2128" stroke="#3fb950" stroke-width="1.5"/>
  <text x="565" y="455" text-anchor="middle" fill="#3fb950" font-size="12" font-weight="bold">auth-service</text>
  <text x="565" y="473" text-anchor="middle" fill="#c9d1d9" font-size="11">Login · JWT sign</text>
  <text x="565" y="489" text-anchor="middle" fill="#8b949e" font-size="10">:5001</text>

  <rect x="690" y="430" width="130" height="70" rx="8" fill="#1c2128" stroke="#3fb950" stroke-width="1.5"/>
  <text x="755" y="455" text-anchor="middle" fill="#3fb950" font-size="12" font-weight="bold">api-service</text>
  <text x="755" y="473" text-anchor="middle" fill="#c9d1d9" font-size="11">Data · Protected</text>
  <text x="755" y="489" text-anchor="middle" fill="#8b949e" font-size="10">:5002</text>

  <rect x="880" y="430" width="150" height="70" rx="8" fill="#1c2128" stroke="#3fb950" stroke-width="1.5"/>
  <text x="955" y="455" text-anchor="middle" fill="#3fb950" font-size="12" font-weight="bold">frontend / SPA</text>
  <text x="955" y="473" text-anchor="middle" fill="#c9d1d9" font-size="11">Dashboard UI</text>
  <text x="955" y="489" text-anchor="middle" fill="#8b949e" font-size="10">Nginx :3000</text>

  <!-- Request arrows -->
  <line x1="160" y1="465" x2="218" y2="465" stroke="#58a6ff" stroke-width="2" marker-end="url(#arr)"/>
  <line x1="440" y1="455" x2="498" y2="455" stroke="#3fb950" stroke-width="1.5" marker-end="url(#arrg)"/>
  <line x1="440" y1="470" x2="688" y2="470" stroke="#3fb950" stroke-width="1.5" marker-end="url(#arrg)"/>
  <line x1="440" y1="485" x2="878" y2="485" stroke="#3fb950" stroke-width="1.5" marker-end="url(#arrg)"/>
  <text x="469" y="452" fill="#8b949e" font-size="9">/auth/*</text>
  <text x="469" y="468" fill="#8b949e" font-size="9">/api/*</text>
  <text x="469" y="483" fill="#8b949e" font-size="9">/</text>

  <!-- Rate limit return 429 -->
  <line x1="330" y1="425" x2="155" y2="445" stroke="#f85149" stroke-width="1.5" stroke-dasharray="4,2" marker-end="url(#arrr)"/>
  <text x="240" y="415" text-anchor="middle" fill="#f85149" font-size="10">429 Rate Limited</text>

  <!-- ════════════════════════════════════════════
       LEGEND
  ═════════════════════════════════════════════ -->
  <rect x="20" y="570" width="1360" height="130" rx="8" fill="#161b22" stroke="#30363d" stroke-width="1"/>
  <text x="700" y="596" text-anchor="middle" fill="#8b949e" font-size="12" font-weight="bold">LÉGENDE</text>

  <line x1="40" y1="620" x2="100" y2="620" stroke="#d29922" stroke-width="2.5" marker-end="url(#arry)"/>
  <text x="108" y="625" fill="#c9d1d9" font-size="12">Flux de logs (Filebeat → Logstash → Elasticsearch)</text>

  <line x1="40" y1="648" x2="100" y2="648" stroke="#bc8cff" stroke-width="2.5" marker-end="url(#arrp)"/>
  <text x="108" y="653" fill="#c9d1d9" font-size="12">Flux de métriques (scrape Prometheus)</text>

  <line x1="460" y1="620" x2="520" y2="620" stroke="#3fb950" stroke-width="2.5" marker-end="url(#arrg)"/>
  <text x="528" y="625" fill="#c9d1d9" font-size="12">Requêtes proxifiées (Nginx → Services)</text>

  <line x1="460" y1="648" x2="520" y2="648" stroke="#f85149" stroke-width="2" stroke-dasharray="4,2" marker-end="url(#arrr)"/>
  <text x="528" y="653" fill="#c9d1d9" font-size="12">Alertes / blocages (429, firing)</text>

  <line x1="880" y1="620" x2="940" y2="620" stroke="#58a6ff" stroke-width="2" stroke-dasharray="4,3" marker-end="url(#arr)"/>
  <text x="948" y="625" fill="#c9d1d9" font-size="12">Lecture directe (Dashboard → ES / Prometheus)</text>

  <text x="40" y="688" fill="#8b949e" font-size="10">Toutes les requêtes externes traversent le gateway Nginx — aucun service backend n'est exposé directement sur l'hôte.</text>
</svg>
</body></html>"""

# Write HTML files to temp locations
import tempfile

arch_html_path = os.path.join(OUT, '_arch_tmp.html')
flux_html_path = os.path.join(OUT, '_flux_tmp.html')
with open(arch_html_path, 'w', encoding='utf-8') as f:
    f.write(ARCH_HTML)
with open(flux_html_path, 'w', encoding='utf-8') as f:
    f.write(FLUX_HTML)

print("[3/4] Rendering architecture_diagram.png...")
print("[4/4] Rendering flux_donnees.png...")

with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True)
    ctx = browser.new_context(viewport={'width': 1400, 'height': 870})
    page = ctx.new_page()

    page.goto('file:///' + arch_html_path.replace('\\', '/'), wait_until='load')
    page.wait_for_timeout(500)
    page.screenshot(path=os.path.join(OUT, 'architecture_diagram.png'), full_page=False)
    print(f"  [OK] architecture_diagram.png  ({os.path.getsize(os.path.join(OUT, 'architecture_diagram.png'))//1024} KB)")

    page.set_viewport_size({'width': 1400, 'height': 770})
    page.goto('file:///' + flux_html_path.replace('\\', '/'), wait_until='load')
    page.wait_for_timeout(500)
    page.screenshot(path=os.path.join(OUT, 'flux_donnees.png'), full_page=False)
    print(f"  [OK] flux_donnees.png  ({os.path.getsize(os.path.join(OUT, 'flux_donnees.png'))//1024} KB)")

    browser.close()

# Clean up temp HTML
os.remove(arch_html_path)
os.remove(flux_html_path)

print("\n=== All 4 missing screenshots generated ===")
for name in ['gateway_rate_limit.png','rate_limit_terminal.png','architecture_diagram.png','flux_donnees.png']:
    p = os.path.join(OUT, name)
    size = os.path.getsize(p)//1024 if os.path.exists(p) else 0
    status = "OK" if size > 10 else "SMALL - may need check"
    print(f"  {status:6s}  {name}  ({size} KB)")
