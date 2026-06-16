"""Screenshot the UI for each role to show RBAC visual differences."""
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

OUT = Path("rapport/screenshots/ui_review")
OUT.mkdir(parents=True, exist_ok=True)
URL = "http://localhost:3000"

ACCOUNTS = [
    ("admin",    "Admin@SecureWatch2026!"),
    ("operator", "Operator@PFA2026!"),
    ("user1",    "User1@PFA2026!"),
]

async def login(page, username, password):
    await page.goto(URL, wait_until="domcontentloaded", timeout=15000)
    await page.evaluate("localStorage.clear()")
    await page.reload(wait_until="domcontentloaded")
    await asyncio.sleep(1)
    await page.fill("#login-user", username)
    await page.fill("#login-pass", password)
    await page.click("#login-btn")
    await asyncio.sleep(3)

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        for username, password in ACCOUNTS:
            print(f"  Role: {username}")
            page = await browser.new_page(viewport={"width": 1440, "height": 860})
            await login(page, username, password)
            await page.screenshot(path=str(OUT / f"rbac_{username}_dashboard.png"))
            print(f"    -> rbac_{username}_dashboard.png")
            # Try clicking a restricted nav item
            await page.click("#nav-monitoring", force=True)
            await asyncio.sleep(0.8)
            await page.screenshot(path=str(OUT / f"rbac_{username}_monitoring_attempt.png"))
            print(f"    -> rbac_{username}_monitoring_attempt.png")
            await page.close()
        await browser.close()
        print("Done.")

asyncio.run(run())
