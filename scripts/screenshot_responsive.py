"""Screenshot at multiple viewport sizes to verify responsive layout."""
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

OUT = Path("rapport/screenshots/ui_review/responsive")
OUT.mkdir(parents=True, exist_ok=True)
URL = "http://localhost:3000"

VIEWPORTS = [
    ("desktop_1440",  1440, 860),
    ("tablet_1024",   1024, 768),
    ("mobile_390",     390, 844),
]

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        for name, w, h in VIEWPORTS:
            print(f"  {name} ({w}x{h})")
            page = await browser.new_page(viewport={"width": w, "height": h})
            await page.goto(URL, wait_until="domcontentloaded", timeout=15000)
            await asyncio.sleep(3)

            # Dashboard (sidebar closed)
            await page.screenshot(path=str(OUT / f"{name}_dashboard.png"))
            print(f"    -> dashboard")

            # On mobile/tablet: open sidebar
            if w <= 1024:
                ham = page.locator('#hamburger')
                await ham.click()
                await asyncio.sleep(0.6)
                await page.screenshot(path=str(OUT / f"{name}_sidebar_open.png"))
                print(f"    -> sidebar_open")
                # Navigate via JS to avoid click issues
                await page.evaluate("document.getElementById('sidebar-backdrop').click()")
                await asyncio.sleep(0.4)

            # Navigate to services via JS (works whether sidebar is open or not)
            await page.evaluate("document.getElementById('nav-services').click()")
            await asyncio.sleep(1)
            await page.screenshot(path=str(OUT / f"{name}_services.png"))
            print(f"    -> services")

            await page.close()

        await browser.close()
        print(f"\nAll done — {OUT}")

asyncio.run(run())
