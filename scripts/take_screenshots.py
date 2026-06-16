"""
take_screenshots.py — Capture automatique de toutes les screenshots pour le rapport.
Nécessite : pip install playwright && python -m playwright install chromium
"""

import time
import os
from playwright.sync_api import sync_playwright

OUT = os.path.join(os.path.dirname(__file__), '..', 'rapport', 'screenshots')
os.makedirs(OUT, exist_ok=True)

def save(name):
    return os.path.join(OUT, name)

def wait_and_shot(page, path, wait_ms=2000):
    page.wait_for_timeout(wait_ms)
    page.screenshot(path=path, full_page=False)
    print(f"  [OK] {os.path.basename(path)}")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=['--ignore-certificate-errors'])
    ctx = browser.new_context(
        viewport={'width': 1600, 'height': 900},
        ignore_https_errors=True,
    )
    page = ctx.new_page()

    # ── 1. SecureWatch Dashboard — Tableau de bord ─────────────
    print("\n[1/12] Dashboard overview...")
    page.goto('http://localhost:3000')
    page.wait_for_load_state('networkidle')
    page.wait_for_timeout(5000)   # let charts render + ES data load
    wait_and_shot(page, save('dashboard_overview.png'))

    # ── 2. Flux de Logs ────────────────────────────────────────
    print("[2/12] Dashboard logs...")
    page.click('#nav-logs')
    page.wait_for_timeout(1500)
    # Set filter to WARNING
    page.select_option('#filter-level', 'WARNING')
    page.wait_for_timeout(1000)
    wait_and_shot(page, save('dashboard_logs.png'))

    # ── 3. Alertes ─────────────────────────────────────────────
    print("[3/12] Dashboard alertes...")
    page.click('#nav-alerts')
    page.wait_for_timeout(2000)
    wait_and_shot(page, save('dashboard_alertes.png'))

    # ── 4. État des Services ───────────────────────────────────
    print("[4/12] Dashboard services...")
    page.click('#nav-services')
    page.wait_for_timeout(3000)
    wait_and_shot(page, save('dashboard_services.png'))

    # ── 5. Monitoring — Infrastructure ────────────────────────
    print("[5/12] Dashboard monitoring infra...")
    page.click('#nav-monitoring')
    page.wait_for_timeout(6000)   # charts need time to load from Prometheus
    wait_and_shot(page, save('dashboard_monitoring_infra.png'))

    # ── 6. Monitoring — Sécurité ───────────────────────────────
    print("[6/12] Dashboard monitoring security...")
    page.click('#tab-security')
    page.wait_for_timeout(4000)
    wait_and_shot(page, save('dashboard_monitoring_security.png'))

    # ── 7. Prometheus Targets ─────────────────────────────────
    print("[7/12] Prometheus targets...")
    page.goto('http://localhost:9090/targets')
    page.wait_for_load_state('networkidle')
    page.wait_for_timeout(2000)
    wait_and_shot(page, save('prometheus_targets.png'))

    # ── 8. Prometheus Alerts ──────────────────────────────────
    print("[8/12] Prometheus alerts...")
    page.goto('http://localhost:9090/alerts')
    page.wait_for_load_state('networkidle')
    page.wait_for_timeout(2000)
    # Expand all alert groups
    for btn in page.query_selector_all('button[data-toggle]'):
        try:
            btn.click()
        except Exception:
            pass
    page.wait_for_timeout(1000)
    wait_and_shot(page, save('prometheus_alerts.png'), wait_ms=500)

    # ── 9. Alertmanager ───────────────────────────────────────
    print("[9/12] Alertmanager...")
    page.goto('http://localhost:9093')
    page.wait_for_load_state('networkidle')
    page.wait_for_timeout(3000)
    wait_and_shot(page, save('alertmanager_ui.png'))

    # ── 10. Grafana — Infrastructure ──────────────────────────
    print("[10/12] Grafana infrastructure dashboard...")
    page.goto('http://localhost:3001/dashboards')
    page.wait_for_load_state('networkidle')
    page.wait_for_timeout(2000)
    # Find and click the infrastructure dashboard
    infra_link = page.query_selector('a[href*="Infrastructure"]') or \
                 page.query_selector('a[href*="infrastructure"]')
    if infra_link:
        infra_link.click()
    else:
        # Navigate directly via search
        page.goto('http://localhost:3001/dashboards')
        page.wait_for_timeout(1000)
        links = page.query_selector_all('.dashboard-list-item a, [data-testid="data-testid Dashboard search item"] a')
        for l in links:
            txt = l.inner_text().lower()
            if 'infra' in txt or 'infrastructure' in txt:
                l.click()
                break
    page.wait_for_load_state('networkidle')
    page.wait_for_timeout(5000)
    wait_and_shot(page, save('grafana_infra.png'))

    # ── 11. Grafana — Sécurité ────────────────────────────────
    print("[11/12] Grafana security dashboard...")
    page.goto('http://localhost:3001/dashboards')
    page.wait_for_load_state('networkidle')
    page.wait_for_timeout(2000)
    links = page.query_selector_all('a')
    for l in links:
        try:
            txt = l.inner_text().lower()
            if 'sécu' in txt or 'secur' in txt or 'security' in txt:
                l.click()
                break
        except Exception:
            pass
    page.wait_for_load_state('networkidle')
    page.wait_for_timeout(5000)
    wait_and_shot(page, save('grafana_security.png'))

    # ── 12. Kibana — Discover ─────────────────────────────────
    print("[12/12] Kibana discover...")
    page.goto('http://localhost:5601/app/discover')
    page.wait_for_load_state('networkidle')
    page.wait_for_timeout(5000)
    wait_and_shot(page, save('kibana_discover.png'))

    browser.close()

print(f"\nDone — {len(os.listdir(OUT))} screenshots saved to rapport/screenshots/")
for f in sorted(os.listdir(OUT)):
    size = os.path.getsize(os.path.join(OUT, f)) // 1024
    print(f"  {f}  ({size} KB)")
