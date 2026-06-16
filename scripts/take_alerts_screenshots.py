"""Retake prometheus_alerts.png and alertmanager_ui.png while alert is firing."""
import os
from playwright.sync_api import sync_playwright

OUT = os.path.join(os.path.dirname(__file__), '..', 'rapport', 'screenshots')

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=['--ignore-certificate-errors'])
    ctx = browser.new_context(viewport={'width': 1600, 'height': 900}, ignore_https_errors=True)
    page = ctx.new_page()

    # Prometheus alerts — expand all groups so FIRING state is visible
    print("Prometheus alerts...")
    page.goto('http://localhost:9090/alerts', wait_until='load', timeout=20000)
    page.wait_for_timeout(2000)
    # Click all collapsed chevrons to expand
    for btn in page.query_selector_all('button.collapse-button, [data-toggle="collapse"], .accordion-button'):
        try:
            btn.click()
            page.wait_for_timeout(200)
        except Exception:
            pass
    page.wait_for_timeout(1000)
    page.screenshot(path=os.path.join(OUT, 'prometheus_alerts.png'), full_page=False)
    print("  [OK] prometheus_alerts.png")

    # Alertmanager
    print("Alertmanager...")
    page.goto('http://localhost:9093', wait_until='load', timeout=20000)
    page.wait_for_timeout(4000)
    page.screenshot(path=os.path.join(OUT, 'alertmanager_ui.png'), full_page=False)
    print("  [OK] alertmanager_ui.png")

    browser.close()
