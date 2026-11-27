"""PWA path / subpath / offline test. usage: test_pwa_paths.py BASE_URL (must end with /)"""
import sys, re, json, urllib.request, urllib.parse
from playwright.sync_api import sync_playwright
BASE = sys.argv[1]; OUT = sys.argv[2] if len(sys.argv) > 2 else None
res = []; errs = []
def check(n, c, i=""): res.append((n, bool(c))); print(("PASS " if c else "FAIL "), n, ("" if c else i))
def get(path):
    with urllib.request.urlopen(urllib.parse.urljoin(BASE, path), timeout=30) as r: return r.status, r.read().decode("utf-8", "replace") if not path.endswith(".png") else r.read()
st, idx = get("index.html"); st2, man = get("manifest.webmanifest"); st3, sw = get("sw.js")
check("index/manifest/sw all 200", st == st2 == st3 == 200)
check("index.html has no root-absolute href/src", not re.search(r'(?:href|src)="/(?!/)', idx))
m = json.loads(man)
check("manifest start_url, scope, id are relative", all(not str(m[k]).startswith(("/", "http")) for k in ("start_url", "scope", "id")), json.dumps({k: m[k] for k in ("start_url", "scope", "id")}))
check("manifest icon paths are relative", all(not i["src"].startswith(("/", "http")) for i in m["icons"]), str([i["src"] for i in m["icons"]]))
check("sw.js has no root-absolute asset paths", not re.search(r'["\']/(?!/)[A-Za-z]', sw.split("self.addEventListener")[0]), sw[:300])
for i in m["icons"]:
    s, body = get(i["src"]); check(f"icon {i['src']} loads ({i['sizes']})", s == 200 and len(body) > 100)
check("sw cache name is v4", 'bjt-v4' in sw, re.findall(r'var CACHE = "[^"]+"', sw)[0] if 'CACHE' in sw else "")
with sync_playwright() as p:
    b = p.chromium.launch(headless=True, executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
    ctx = b.new_context(viewport={"width": 1280, "height": 800}); pg = ctx.new_page()
    pg.on("console", lambda m_: errs.append(m_.text) if m_.type == "error" else None); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(BASE + "index.html", wait_until="networkidle")
    check("page loads, title ok, 10 tabs", "Blackjack" in pg.title() and pg.locator("#tabs [role=tab]").count() == 10)
    scope = pg.evaluate("navigator.serviceWorker.ready.then(r=>r.scope)")
    check(f"service worker registered with scope = {BASE}", scope == BASE, scope)
    pg.reload(wait_until="networkidle"); pg.wait_for_timeout(600)
    check("page is controlled by the SW after reload", pg.evaluate("!!navigator.serviceWorker.controller"))
    keys = pg.evaluate("caches.keys()")
    check("cache bjt-v4-2 present (old caches gone)", keys == ["bjt-v4-2"], str(keys))
    cached = pg.evaluate("caches.open('bjt-v4-2').then(c=>c.keys()).then(k=>k.map(r=>new URL(r.url).pathname))")
    base_path = urllib.parse.urlparse(BASE).path
    check("every precached URL is inside the app path", all(c.startswith(base_path) for c in cached) and len(cached) >= 8, str(cached))
    mf = pg.evaluate("(function(){var l=document.querySelector('link[rel=manifest]');return l.href;})()")
    check("manifest link resolves under the app path", mf == BASE + "manifest.webmanifest", mf)
    start = pg.evaluate("fetch('manifest.webmanifest').then(r=>r.json()).then(j=>new URL(j.start_url, document.baseURI+'../'.slice(3)).href)")
    check("start_url resolves inside scope", start.startswith(BASE), start)
    # open a new-feature view to prove it renders from cache offline
    ctx.set_offline(True)
    pg.reload(wait_until="domcontentloaded"); pg.wait_for_timeout(500)
    check("offline reload works", "Blackjack" in pg.title() and pg.locator("#tabs [role=tab]").count() == 10)
    pg.click("#tab-index"); pg.wait_for_timeout(100)
    check("offline: Index Trainer renders a card", pg.locator("#index-stage .pcard").count() >= 3)
    pg.click("#tab-count"); pg.click("#cd-modes button[data-cmode=conv]"); pg.click("#cd-start")
    check("offline: Count Drill runs", pg.locator("#cd-q-rc").count() == 1)
    pg.click("#tab-speed"); pg.click("#sp-start"); pg.wait_for_timeout(300)
    check("offline: Speed Run starts", pg.locator("#sp-body .q-actions button").count() >= 4)
    pg.click("#sp-cancel")
    icons = [pg.evaluate(f"fetch('{u}').then(r=>r.status)") for u in ["icon-192.png", "icon-512.png", "apple-touch-icon.png", "manifest.webmanifest"]]
    check("icons + manifest served offline", icons == [200] * 4, str(icons))
    if OUT: pg.screenshot(path=OUT)
    b.close()
print("console/page errors:", errs)
f = [r for r in res if not r[1]]; print("TOTAL", len(res), "FAILS", len(f)); sys.exit(1 if f or errs else 0)
