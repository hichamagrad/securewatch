"""
take_screenshots_remaining.py — captures the remaining 5 screenshots.
Uses 'load' instead of 'networkidle' for pages with long-polling connections.
"""

import time
import os
from playwright.sync_api import sync_playwright

OUT = os.path.join(os.path.dirname(__file__), '..', 'rapport', 'screenshots')
os.makedirs(OUT, exist_ok=True)

def save(name):
    return os.path.join(OUT, name)

def goto_load(page, url, wait_ms=3000):
    page.goto(url, wait_until='load', timeout=30000)
    page.wait_for_timeout(wait_ms)

def shot(page, path):
    page.screenshot(path=path, full_page=False)
    print(f"  [OK] {os.path.basename(path)}")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=['--ignore-certificate-errors'])
    ctx = browser.new_context(
        viewport={'width': 1600, 'height': 900},
        ignore_https_errors=True,
    )
    page = ctx.new_page()

    # ── 8. Prometheus Alerts ──────────────────────────────────
    print("[8/5] Prometheus alerts...")
    goto_load(page, 'http://localhost:9090/alerts', wait_ms=3000)
    shot(page, save('prometheus_alerts.png'))

    # ── 9. Alertmanager ───────────────────────────────────────
    print("[9/5] Alertmanager...")
    goto_load(page, 'http://localhost:9093', wait_ms=4000)
    shot(page, save('alertmanager_ui.png'))

    # ── 10. Grafana — Infrastructure ──────────────────────────
    print("[10/5] Grafana infrastructure dashboard...")
    # First hit the dashboards list
    goto_load(page, 'http://localhost:3001/dashboards', wait_ms=3000)
    # Find the infrastructure dashboard link
    found = False
    for link in page.query_selector_all('a'):
        try:
            txt = link.inner_text().strip().lower()
            href = link.get_attribute('href') or ''
            if 'infra' in txt or 'infrastructure' in txt:
                link.click()
                found = True
                break
        except Exception:
            pass
    if not found:
        # Try direct UID navigation — Grafana provisioned dashboards
        goto_load(page, 'http://localhost:3001/dashboards', wait_ms=1000)
        # Click first dashboard link
        links = page.query_selector_all('[data-testid*="dashboard"] a, .search-results a, ul li a')
        for l in links:
            href = l.get_attribute('href') or ''
            if '/d/' in href:
                txt = l.inner_text().lower()
                if 'infra' in txt:
                    l.click()
                    found = True
                    break
    page.wait_for_timeout(5000)
    shot(page, save('grafana_infra.png'))

    # ── 11. Grafana — Sécurité ────────────────────────────────
    print("[11/5] Grafana security dashboard...")
    goto_load(page, 'http://localhost:3001/dashboards', wait_ms=2000)
    found = False
    for link in page.query_selector_all('a'):
        try:
            txt = link.inner_text().strip().lower()
            if 'sécu' in txt or 'secur' in txt or 'security' in txt:
                link.click()
                found = True
                break
        except Exception:
            pass
    if not found:
        links = page.query_selector_all('a')
        for l in links:
            href = l.get_attribute('href') or ''
            if '/d/' in href and l.inner_text().strip():
                txt = l.inner_text().lower()
                if 'infra' not in txt:   # pick the other dashboard
                    l.click()
                    found = True
                    break
    page.wait_for_timeout(5000)
    shot(page, save('grafana_security.png'))

    # ── 12. Kibana — Discover ─────────────────────────────────
    print("[12/5] Kibana discover...")
    goto_load(page, 'http://localhost:5601/app/discover', wait_ms=6000)
    shot(page, save('kibana_discover.png'))

    browser.close()

print(f"\nDone — screenshots in rapport/screenshots/")
for f in sorted(os.listdir(OUT)):
    size = os.path.getsize(os.path.join(OUT, f)) // 1024
    print(f"  {f}  ({size} KB)")
