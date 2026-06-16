"""Screenshot login screen and post-login dashboard."""
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

OUT = Path("rapport/screenshots/ui_review")
OUT.mkdir(parents=True, exist_ok=True)
URL = "http://localhost:3000"

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        # ── 1. Login screen (no JWT) ──
        page = await browser.new_page(viewport={"width": 1440, "height": 860})
        await page.goto(URL, wait_until="domcontentloaded", timeout=15000)
        await page.evaluate("localStorage.clear()")
        await asyncio.sleep(1.5)
        await page.screenshot(path=str(OUT / "auth_login_screen.png"))
        print("  -> login screen")

        # ── 2. Wrong credentials ──
        await page.fill("#login-user", "admin")
        await page.fill("#login-pass", "wrongpassword")
        await page.click("#login-btn")
        await asyncio.sleep(1)
        await page.screenshot(path=str(OUT / "auth_login_error.png"))
        print("  -> login error")

        # ── 3. Quick-fill demo button ──
        await page.click(".login-account-btn[data-user='admin']")
        await asyncio.sleep(0.3)
        await page.screenshot(path=str(OUT / "auth_login_prefilled.png"))
        print("  -> prefilled form")

        # ── 4. Successful login ──
        await page.click("#login-btn")
        await asyncio.sleep(4)
        await page.screenshot(path=str(OUT / "auth_dashboard_logged_in.png"))
        print("  -> logged in dashboard")

        # ── 5. Light mode logged in ──
        await page.click("#theme-toggle")
        await asyncio.sleep(0.5)
        await page.screenshot(path=str(OUT / "auth_light_logged_in.png"))
        print("  -> light mode logged in")

        await browser.close()
        print("Done.")

asyncio.run(run())
