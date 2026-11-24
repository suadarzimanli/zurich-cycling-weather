"""Performance check: records main-thread freezes (long tasks over 50 ms) during typical use.

Runs in the installed Microsoft Edge with the CPU slowed down 4x (a typical laptop or phone).
Usage: python perf_check.py [base_url] [cpu_slowdown]
"""
import sys
import time

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8765/"
SLOW = float(sys.argv[2]) if len(sys.argv) > 2 else 4

INIT = """
window.__long = [];
new PerformanceObserver((list) => { for (const e of list.getEntries()) window.__long.push(e.duration); })
  .observe({ type: 'longtask', buffered: true });
"""


def report(page, label, t0):
    d = page.evaluate("window.__long.splice(0)")
    tot = sum(d)
    print(f"{label:38s} wall {time.time() - t0:5.1f}s | freezes {len(d):3d} | longest {max(d) if d else 0:6.0f} ms | total blocked {tot:6.0f} ms")
    return tot


with sync_playwright() as p:
    browser = p.chromium.launch(channel="msedge", headless=True)
    ctx = browser.new_context(viewport={"width": 1366, "height": 900})
    page = ctx.new_page()
    page.add_init_script(INIT)
    cdp = ctx.new_cdp_session(page)
    cdp.send("Emulation.setCPUThrottlingRate", {"rate": SLOW})
    t0 = time.time()
    page.goto(BASE + "#map")
    page.wait_for_function("Number(document.getElementById('map').dataset.markers || 0) > 300", timeout=60000)
    page.wait_for_timeout(1500)
    report(page, "load map", t0)

    t0 = time.time()
    box = page.locator("#map").bounding_box()
    cx, cy = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
    for _ in range(3):
        page.mouse.move(cx, cy)
        page.mouse.wheel(0, -300)
        page.wait_for_timeout(500)
    for _ in range(3):
        page.mouse.wheel(0, 300)
        page.wait_for_timeout(500)
    report(page, "zoom in and out (6 steps)", t0)

    t0 = time.time()
    for dx in (200, -300, 150):
        page.mouse.move(cx, cy)
        page.mouse.down()
        page.mouse.move(cx + dx, cy + dx / 3, steps=12)
        page.mouse.up()
        page.wait_for_timeout(300)
    report(page, "pan the map (3 drags)", t0)

    t0 = time.time()
    for name in ("Mythenquai", "Langstrasse (Fahrbahn Nord)", "Hardbrücke Süd (Seite HB)"):
        page.select_option("#loc-select", label=name)
        page.wait_for_timeout(700)
    report(page, "click 3 counters", t0)

    t0 = time.time()
    page.click('[data-range="all"]')
    page.wait_for_timeout(800)
    cb = page.locator("#c-series").bounding_box()
    for i in range(30):
        page.mouse.move(cb["x"] + 20 + i * (cb["width"] - 40) / 30, cb["y"] + cb["height"] / 2)
    page.wait_for_timeout(300)
    report(page, "all years + hover along chart", t0)

    t0 = time.time()
    page.click('.tabs [data-tab="years"]')
    page.wait_for_timeout(1500)
    report(page, "open 'Rain over the years'", t0)

    t0 = time.time()
    page.click('.tabs [data-tab="calc"]')
    page.wait_for_timeout(800)
    sb = page.locator("#in-temp").bounding_box()
    page.mouse.move(sb["x"] + 5, sb["y"] + sb["height"] / 2)
    page.mouse.down()
    page.mouse.move(sb["x"] + sb["width"] - 5, sb["y"] + sb["height"] / 2, steps=40)
    page.mouse.up()
    page.wait_for_timeout(300)
    report(page, "drag temperature slider", t0)

    t0 = time.time()
    page.click('.tabs [data-tab="fc"]')
    page.wait_for_timeout(1500)
    report(page, "open 'Forecasting'", t0)

    t0 = time.time()
    page.click('.tabs [data-tab="map"]')
    page.wait_for_timeout(500)
    page.click("#themeBtn")
    page.wait_for_timeout(1500)
    report(page, "switch theme on map", t0)
    browser.close()
