"""Full functional audit of SecureWatch dashboard."""
import asyncio, json
from pathlib import Path
from playwright.async_api import async_playwright

OUT = Path("rapport/screenshots/ui_review/audit")
OUT.mkdir(parents=True, exist_ok=True)
URL = "http://localhost:3000"
results = []

def check(name, ok, detail=""):
    status = "PASS" if ok else "FAIL"
    results.append((status, name, detail))
    print(f"  [{status}] {name}" + (f" — {detail}" if detail else ""))

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1440, "height": 860})

        print("\n── Loading app ──────────────────────────")
        await page.goto(URL, wait_until="domcontentloaded", timeout=15000)
        await asyncio.sleep(5)

        # ── 1. Page loads ────────────────────────
        print("\n── 1. Basic load ────────────────────────")
        title = await page.title()
        check("Page title set", "SecureWatch" in title, title)

        es_status = await page.inner_text("#es-status-text")
        check("Elasticsearch connected", "OK" in es_status or "connecté" in es_status.lower(), es_status)

        # ── 2. Clock ticking ─────────────────────
        t1 = await page.inner_text("#live-clock")
        await asyncio.sleep(2)
        t2 = await page.inner_text("#live-clock")
        check("Live clock ticking", t1 != t2, f"{t1} → {t2}")

        # ── 3. Stat cards populated ───────────────
        print("\n── 2. Dashboard stats ───────────────────")
        stat_total = await page.inner_text("#stat-total")
        check("Total events counter populated", stat_total not in ("—", "0", ""), stat_total)

        for sid in ["stat-total", "stat-auth", "stat-forbidden", "stat-errors", "stat-brute"]:
            val = await page.inner_text(f"#{sid}")
            check(f"  {sid} renders", val != "", val)

        # ── 4. Charts rendered ────────────────────
        print("\n── 3. Charts ────────────────────────────")
        timeline_canvas = await page.query_selector("#timelineChart")
        check("Timeline chart canvas exists", timeline_canvas is not None)

        donut_canvas = await page.query_selector("#donutChart")
        check("Donut chart canvas exists", donut_canvas is not None)

        # ── 5. Recent log table ───────────────────
        print("\n── 4. Log table (dashboard) ─────────────")
        rows = await page.query_selector_all("#recent-log-body tr")
        check("Recent logs table has rows", len(rows) > 1, f"{len(rows)} rows")
        first_row = await rows[0].inner_text() if rows else ""
        check("First row not empty", "Chargement" not in first_row, first_row[:60])

        await page.screenshot(path=str(OUT / "01_dashboard.png"))

        # ── 6. Navigation ─────────────────────────
        print("\n── 5. Navigation ────────────────────────")
        for nav_id, section_id, name in [
            ("nav-logs",       "section-logs",       "Flux de Logs"),
            ("nav-alerts",     "section-alerts",     "Alertes"),
            ("nav-services",   "section-services",   "Services"),
            ("nav-monitoring", "section-monitoring", "Monitoring"),
            ("nav-dashboard",  "section-dashboard",  "Dashboard"),
        ]:
            await page.click(f"#{nav_id}")
            await asyncio.sleep(0.5)
            active = await page.get_attribute(f"#{section_id}", "class")
            check(f"Nav {name} activates section", "active" in (active or ""), active)
            nav_active = await page.get_attribute(f"#{nav_id}", "class")
            check(f"  Nav item {name} marked active", "active" in (nav_active or ""), nav_active)

        # ── 7. Full log table ─────────────────────
        print("\n── 6. Flux de Logs ──────────────────────")
        await page.click("#nav-logs")
        await asyncio.sleep(0.6)

        full_rows = await page.query_selector_all("#full-log-body tr")
        check("Full log table has rows", len(full_rows) > 1, f"{len(full_rows)} rows")

        # Level filter
        await page.select_option("#filter-level", "WARNING")
        await asyncio.sleep(0.4)
        filtered = await page.query_selector_all("#full-log-body tr")
        check("Level filter reduces rows", len(filtered) <= len(full_rows), f"{len(filtered)} after filter")

        await page.select_option("#filter-level", "")  # reset

        # Search filter
        await page.fill("#filter-search", "api")
        await asyncio.sleep(0.4)
        searched = await page.query_selector_all("#full-log-body tr")
        check("Search filter works", len(searched) > 0, f"{len(searched)} matching 'api'")
        await page.fill("#filter-search", "")

        await page.screenshot(path=str(OUT / "02_logs.png"))

        # ── 8. Alerts section ─────────────────────
        print("\n── 7. Alertes ───────────────────────────")
        await page.click("#nav-alerts")
        await asyncio.sleep(0.5)
        badge_text = await page.inner_text("#alert-count-badge")
        check("Alert count badge renders", badge_text != "", badge_text)
        nav_badge = await page.inner_text("#alert-badge")
        check("Nav alert badge renders", nav_badge != "", nav_badge)
        await page.screenshot(path=str(OUT / "03_alerts.png"))

        # ── 9. Services section ───────────────────
        print("\n── 8. État des Services ─────────────────")
        await page.click("#nav-services")
        await asyncio.sleep(1.5)
        service_cards = await page.query_selector_all(".service-card")
        check("Service cards rendered", len(service_cards) == 11, f"{len(service_cards)} cards (expect 11)")
        online = await page.query_selector_all(".s-dot--up")
        check("At least 8 services online", len(online) >= 8, f"{len(online)} online")
        arch = await page.query_selector(".architecture-diagram")
        check("Architecture diagram visible", arch is not None)
        await page.screenshot(path=str(OUT / "04_services.png"))

        # ── 10. Monitoring section ────────────────
        print("\n── 9. Monitoring ────────────────────────")
        await page.click("#nav-monitoring")
        await asyncio.sleep(3)  # wait for prometheus data
        cpu_val = await page.inner_text("#prom-cpu-val")
        check("CPU metric loaded", cpu_val not in ("—", ""), cpu_val)
        ram_val = await page.inner_text("#prom-ram-val")
        check("RAM metric loaded", ram_val not in ("—", ""), ram_val)
        await page.screenshot(path=str(OUT / "05_monitoring_infra.png"))

        # Switch to Security tab
        await page.click("#tab-security")
        await asyncio.sleep(1)
        tab_active = await page.get_attribute("#tab-security", "class")
        check("Security tab activates", "active" in (tab_active or ""), tab_active)
        await page.screenshot(path=str(OUT / "06_monitoring_security.png"))

        # ── 11. Theme toggle ──────────────────────
        print("\n── 10. Theme toggle ─────────────────────")
        await page.click("#nav-dashboard")
        await asyncio.sleep(0.3)
        await page.click("#theme-toggle")
        await asyncio.sleep(0.4)
        theme_light = await page.get_attribute("html", "data-theme")
        check("Toggle switches to light", theme_light == "light", theme_light)
        await page.screenshot(path=str(OUT / "07_light_mode.png"))

        await page.click("#theme-toggle")
        await asyncio.sleep(0.4)
        theme_dark = await page.get_attribute("html", "data-theme")
        check("Toggle switches back to dark", theme_dark == "dark", theme_dark)

        # ── 12. "View all" button ─────────────────
        print("\n── 11. View all logs button ─────────────")
        await page.click("#btn-view-all-logs")
        await asyncio.sleep(0.3)
        active_section = await page.get_attribute("#section-logs", "class")
        check("'Voir tout' navigates to logs", "active" in (active_section or ""), active_section)

        # ── 13. Responsive hamburger ──────────────
        print("\n── 12. Responsive hamburger (tablet) ────")
        await page.set_viewport_size({"width": 768, "height": 1024})
        await asyncio.sleep(0.3)
        ham = await page.query_selector("#hamburger")
        ham_visible = await ham.is_visible() if ham else False
        check("Hamburger visible at 768px", ham_visible)

        sidebar_class_before = await page.get_attribute(".sidebar", "class")
        await page.click("#hamburger")
        await asyncio.sleep(0.4)
        sidebar_class_after = await page.get_attribute(".sidebar", "class")
        check("Hamburger opens sidebar", "open" in (sidebar_class_after or ""), sidebar_class_after)

        backdrop = await page.query_selector("#sidebar-backdrop")
        backdrop_visible = await backdrop.is_visible() if backdrop else False
        check("Backdrop visible when sidebar open", backdrop_visible)
        await page.screenshot(path=str(OUT / "08_mobile_sidebar.png"))

        await page.evaluate("document.getElementById('sidebar-backdrop').click()")
        await asyncio.sleep(0.4)
        sidebar_class_closed = await page.get_attribute(".sidebar", "class")
        check("Backdrop click closes sidebar", "open" not in (sidebar_class_closed or ""))

        # ── Summary ───────────────────────────────
        await browser.close()

        passed = sum(1 for r in results if r[0] == "PASS")
        failed = sum(1 for r in results if r[0] == "FAIL")
        print(f"\n{'═'*50}")
        print(f"  TOTAL : {len(results)} checks")
        print(f"  PASS  : {passed}")
        print(f"  FAIL  : {failed}")
        print(f"{'═'*50}")
        if failed:
            print("\nFailed checks:")
            for s, n, d in results:
                if s == "FAIL":
                    print(f"  ✗ {n}" + (f" — {d}" if d else ""))

asyncio.run(run())
