"""Screenshot both dark and light themes for review."""
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

OUT = Path("rapport/screenshots/ui_review")
OUT.mkdir(parents=True, exist_ok=True)
URL = "http://localhost:3000"

async def shot(page, name):
    await asyncio.sleep(1.2)
    await page.screenshot(path=str(OUT / name))
    print(f"  -> {OUT / name}")

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1440, "height": 860})

        # ── Dark mode ──
        print("Dark mode...")
        await page.goto(URL, wait_until="domcontentloaded", timeout=15000)
        # Ensure dark theme
        await page.evaluate("document.documentElement.setAttribute('data-theme','dark')")
        await asyncio.sleep(3)
        await shot(page, "theme_dark_dashboard.png")
        await page.click("#nav-logs");   await shot(page, "theme_dark_logs.png")
        await page.click("#nav-services"); await shot(page, "theme_dark_services.png")
        await page.click("#nav-monitoring"); await asyncio.sleep(2)
        await shot(page, "theme_dark_monitoring.png")

        # ── Light mode ──
        print("Light mode...")
        await page.click("#nav-dashboard")
        await page.evaluate("document.documentElement.setAttribute('data-theme','light')")
        await asyncio.sleep(2)
        await shot(page, "theme_light_dashboard.png")
        await page.click("#nav-logs");   await shot(page, "theme_light_logs.png")
        await page.click("#nav-services"); await shot(page, "theme_light_services.png")
        await page.click("#nav-monitoring"); await asyncio.sleep(2)
        await shot(page, "theme_light_monitoring.png")

        await browser.close()
        print("Done.")

asyncio.run(run())
