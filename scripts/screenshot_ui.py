"""Take screenshots of the SecureWatch dashboard for UI review."""
import asyncio
import time
from pathlib import Path
from playwright.async_api import async_playwright

OUT = Path("rapport/screenshots/ui_review")
OUT.mkdir(parents=True, exist_ok=True)

URL = "http://localhost:3000"

NAV_ITEMS = [
    ("dashboard",   "#nav-dashboard",   "01_dashboard.png"),
    ("logs",        "#nav-logs",        "02_logs.png"),
    ("alerts",      "#nav-alerts",      "03_alerts.png"),
    ("services",    "#nav-services",    "04_services.png"),
    ("monitoring",  "#nav-monitoring",  "05_monitoring.png"),
]

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1440, "height": 860})

        print(f"Loading {URL} ...")
        await page.goto(URL, wait_until="domcontentloaded", timeout=15000)
        await asyncio.sleep(5)  # let charts render and ES data load

        for name, nav_sel, fname in NAV_ITEMS:
            print(f"  Screenshotting: {name}")
            await page.click(nav_sel)
            await asyncio.sleep(1.5)
            path = OUT / fname
            await page.screenshot(path=str(path), full_page=False)
            print(f"    -> {path}")

        # Monitoring infra tab
        await page.click("#nav-monitoring")
        await asyncio.sleep(2)
        await page.click("#tab-infra")
        await asyncio.sleep(1.5)
        await page.screenshot(path=str(OUT / "06_monitoring_infra.png"))
        print(f"    -> {OUT}/06_monitoring_infra.png")

        # Monitoring security tab
        await page.click("#tab-security")
        await asyncio.sleep(1.5)
        await page.screenshot(path=str(OUT / "07_monitoring_security.png"))
        print(f"    -> {OUT}/07_monitoring_security.png")

        await browser.close()
        print("\nDone. Screenshots saved to:", OUT)

asyncio.run(run())
