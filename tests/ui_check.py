"""Automated UI check with the installed Microsoft Edge (Playwright, channel msedge).

Opens every tab in light and dark theme at desktop and phone size, clicks a counter,
uses the calculator, records console errors, failed requests and horizontal overflow,
and saves screenshots to tests/screens/.
Usage: python ui_check.py [base_url]
"""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8765/"
OUT = Path(__file__).parent / "screens"
OUT.mkdir(exist_ok=True)
problems = []

with sync_playwright() as p:
    browser = p.chromium.launch(channel="msedge", headless=True)
    for vp_name, vp in (("desktop", {"width": 1366, "height": 900}), ("phone", {"width": 390, "height": 844})):
        for theme in ("light", "dark"):
            ctx = browser.new_context(viewport=vp, device_scale_factor=1)
            ctx.add_init_script(f"localStorage.setItem('theme', '{theme}')")
            page = ctx.new_page()
            errors = []
            page.on("console", lambda m, e=errors: e.append(f"console {m.type}: {m.text}") if m.type in ("error", "warning") else None)
            page.on("pageerror", lambda ex, e=errors: e.append(f"pageerror: {ex}"))
            # tiles cancelled by the map when the view jumps are normal (net::ERR_ABORTED); everything else is a problem
            page.on("requestfailed", lambda r, e=errors: None if "ERR_ABORTED" in (r.failure or "") else e.append(f"requestfailed: {r.url} ({r.failure})"))
            page.on("response", lambda r, e=errors: e.append(f"HTTP {r.status}: {r.url}") if r.status >= 400 else None)
            tag = f"{vp_name}_{theme}"
            page.goto(BASE + "#map")
            page.wait_for_function("Number(document.getElementById('map').dataset.markers || 0) > 300", timeout=30000)
            n = page.evaluate("Number(document.getElementById('map').dataset.markers)")
            # click the Mythenquai marker on the canvas at its pixel position
            page.evaluate("""() => { const l = zcw.locations.find(x => x.name === 'Mythenquai' && x.type === 'bike');
                zcw.map.setView([l.lat, l.lon], 17, { animate: false }); }""")
            page.wait_for_timeout(400)
            xy = page.evaluate("""() => { const l = zcw.locations.find(x => x.name === 'Mythenquai' && x.type === 'bike');
                const pt = zcw.map.latLngToContainerPoint([l.lat, l.lon]); const r = document.getElementById('map').getBoundingClientRect();
                return [r.left + pt.x, r.top + pt.y]; }""")
            page.mouse.click(xy[0], xy[1])
            page.wait_for_selector("#panel-detail:not([hidden])")
            page.wait_for_timeout(800)
            rain = page.inner_text("#d-rain")
            if page.inner_text("#d-name") != "Mythenquai":
                problems.append(f"{tag}: canvas click opened {page.inner_text('#d-name')!r} instead of Mythenquai")
            page.screenshot(path=str(OUT / f"{tag}_1_map.png"), full_page=True)
            overflow = {}
            overflow["map"] = page.evaluate("document.documentElement.scrollWidth - window.innerWidth")
            for tab in ("years", "calc", "fc", "about"):
                page.click(f'.tabs [data-tab="{tab}"]')
                page.wait_for_timeout(1500)
                if tab == "calc":
                    page.check('input[name="rain"][value="wet"]')
                    page.fill("#in-temp", "20")
                    page.dispatch_event("#in-temp", "input")
                    page.fill("#in-sun", "8")
                    page.dispatch_event("#in-sun", "input")
                    page.wait_for_timeout(300)
                    early, late = page.inner_text("#o-early"), page.inner_text("#o-late")
                    if (early, late) != ("−33%", "−29%"):
                        problems.append(f"{tag}: calculator wet/20C/8h gives {early}, {late} (expected −33%, −29%)")
                    page.fill("#in-temp", "10")
                    page.dispatch_event("#in-temp", "input")
                    page.fill("#in-sun", "2")
                    page.dispatch_event("#in-sun", "input")
                    page.wait_for_timeout(300)
                page.screenshot(path=str(OUT / f"{tag}_{['years', 'calc', 'fc', 'about'].index(tab) + 2}_{tab}.png"), full_page=True)
                overflow[tab] = page.evaluate("document.documentElement.scrollWidth - window.innerWidth")
            # table toggles on the years tab
            page.click('.tabs [data-tab="years"]')
            page.click('button[data-table="tbl-modes"]')
            rows = page.evaluate("document.querySelectorAll('#tbl-modes tbody tr').length")
            print(f"{tag}: markers {n} | Mythenquai rain {rain} | modes table rows {rows} | horizontal overflow px {overflow}")
            for k, v in overflow.items():
                if v > 0:
                    problems.append(f"{tag}: horizontal overflow {v}px on {k}")
            problems.extend(f"{tag}: {e}" for e in errors)
            ctx.close()
    browser.close()

print("\nPROBLEMS:" if problems else "\nNo problems found.")
for pr in problems:
    print(" -", pr)
