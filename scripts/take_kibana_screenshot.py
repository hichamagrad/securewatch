"""Retake kibana_discover.png — creates data view via API then screenshots Discover."""
import os, requests
from playwright.sync_api import sync_playwright

OUT = os.path.join(os.path.dirname(__file__), '..', 'rapport', 'screenshots')

# ── 1. Create data view via Kibana API ───────────────────────
print("Creating data view via API...")
try:
    r = requests.post(
        'http://localhost:5601/api/data_views/data_view',
        headers={'kbn-xsrf': 'true', 'Content-Type': 'application/json'},
        json={
            "data_view": {
                "title": "security-logs-*",
                "name": "security-logs-*",
                "timeFieldName": "@timestamp"
            }
        },
        timeout=10
    )
    print(f"  API response: {r.status_code} — {r.text[:120]}")
except Exception as e:
    print(f"  (API call: {e})")

# ── 2. Screenshot Discover ───────────────────────────────────
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=['--ignore-certificate-errors'])
    ctx = browser.new_context(viewport={'width': 1600, 'height': 900}, ignore_https_errors=True)
    page = ctx.new_page()

    print("Loading Kibana Discover...")
    page.goto('http://localhost:5601/app/discover', wait_until='load', timeout=60000)
    page.wait_for_timeout(10000)

    # Dismiss any modal/tour
    for sel in [
        'button[data-test-subj="skipWelcomeScreen"]',
        'button:has-text("Skip")',
        'button:has-text("Dismiss")',
        'button:has-text("Maybe later")',
        'button:has-text("No thanks")',
        '[data-test-subj="guided-onboarding--skip-button"]',
    ]:
        try:
            el = page.query_selector(sel)
            if el and el.is_visible():
                el.click()
                page.wait_for_timeout(500)
        except Exception:
            pass

    page.wait_for_timeout(3000)
    page.screenshot(path=os.path.join(OUT, 'kibana_discover.png'), full_page=False)
    print("  [OK] kibana_discover.png")
    browser.close()
