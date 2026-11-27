import sys, re, random
from playwright.sync_api import sync_playwright
from axe_playwright_python.sync_playwright import Axe
OUT="/workspace/deliverables/blackjack-trainer-web/"; BASE="http://127.0.0.1:8766/"
errs=[]; res=[]
def check(n,c,i=""): res.append((n,bool(c))); print("PASS " if c else "FAIL ", n, i if not c else "")
with sync_playwright() as p:
    b=p.chromium.launch(headless=True,executable_path="/usr/bin/google-chrome",args=["--no-sandbox"])
    for tag,vp in [("desktop",{"width":1280,"height":800}),("mobile",{"width":390,"height":844})]:
        ctx=b.new_context(viewport=vp); pg=ctx.new_page()
        pg.on("console", lambda m,t=tag: errs.append((t,m.text)) if m.type=="error" else None)
        pg.on("pageerror", lambda e,t=tag: errs.append((t,str(e))))
        pg.on("dialog", lambda d: d.accept())
        pg.goto(BASE+"index.html",wait_until="networkidle")
        pg.evaluate("S.unlockAll=true;renderPath();refreshStrip()")
        # smoke every level 1..6: click through with correct BS answers where possible, random otherwise
        pg.evaluate("(function(){var o=window.genHand;window.genHand=function(){var h=o.apply(this,arguments);window.__lastHand=h;return h;};})()")
        for lv in range(1,7):
            pg.click("#tab-path"); pg.click(f"#path-grid button[data-level='{lv}']"); pg.wait_for_timeout(100)
            steps=0; finished=False
            while steps<120:
                steps+=1
                txt=pg.inner_text("#q-fb") if pg.locator("#q-fb").count() else ""
                if "Passed" in txt or "Not yet" in txt or "Path complete" in txt: finished=True; break
                nxt=pg.locator("#q-next:not(.hidden)")
                if nxt.count() and nxt.is_enabled(): nxt.click(); pg.wait_for_timeout(20); continue
                btns=pg.locator("#q-body .q-actions button:not([disabled])")
                if btns.count() and lv in (1,2,3):
                    a=pg.evaluate("basicPlay(__lastHand.cards,__lastHand.up,S.rules)")
                    loc=pg.locator(f"#q-body .q-actions button[data-a='{a}']")
                    if loc.count(): loc.first.click(); pg.wait_for_timeout(20); continue
                if pg.locator("#rc-submit").count() and pg.locator("#rc-submit").is_enabled():
                    pg.click("#rc-submit"); pg.wait_for_timeout(20); continue
                cand=pg.locator("#q-body button:not([disabled])")
                if cand.count(): cand.nth(random.randrange(cand.count())).click(timeout=2000); pg.wait_for_timeout(20); continue
                pg.wait_for_timeout(40)
            check(f"{tag}: level {lv} runs to a result", finished, f"steps={steps} text={pg.inner_text('#q-fb')[:60]}")
            if lv in (1,6) and tag=="mobile": pg.screenshot(path=OUT+f"v2-{tag}-level{lv}-result.png")
        # chart scroll cue at 320
        pg.set_viewport_size({"width":320,"height":700}); pg.click("#tab-charts"); pg.wait_for_timeout(150)
        info=pg.evaluate("""(function(){var w=document.querySelector('#chart-hard').parentElement;var c=[].slice.call(document.querySelectorAll('.chart-wrap, .table-scroll, .scroll-x'));return {cls:w.className, sw:w.scrollWidth, cw:w.clientWidth, hint:document.getElementById('chart-hint').textContent, hintVisible:getComputedStyle(document.getElementById('chart-hint')).display};})()""")
        print("  chart scroller:", info)
        check(f"{tag}: chart hint visible at 320 when scrollable", info["sw"]<=info["cw"] or info["hintVisible"]!="none")
        pg.screenshot(path=OUT+f"v2-{tag}-charts-320.png")
        pg.set_viewport_size(vp)
        # axe on key views (AA + best practice)
        axe=Axe()
        for view in ["path","drill","speed","count","index","review","charts","scorer","lab","sim"]:
            pg.click("#tab-"+view); pg.wait_for_timeout(120)
            if view == "count":
                pg.click("#cd-modes button[data-cmode=conv]"); pg.click("#cd-start"); pg.wait_for_timeout(80)
            if view == "speed":
                pg.click("#sp-start"); pg.wait_for_timeout(150)
            r=axe.run(pg, options={"runOnly":{"type":"tag","values":["wcag2a","wcag2aa","wcag21aa"]}})
            v=r.response["violations"]
            print(f"  axe {tag}/{view}: {len(v)} violations", [(x['id'],len(x['nodes'])) for x in v])
            for x in v[:4]:
                for n in x["nodes"][:2]: print("     ", x["id"], n["target"], (n.get("any") or [{}])[0].get("message","")[:120])
            check(f"{tag}: axe {view} zero WCAG2A/AA violations", len(v)==0)
        # dark mode contrast
        pg2=ctx.new_page(); 
        ctx.close()
    # dark scheme axe + offline PWA
    ctx=b.new_context(viewport={"width":1280,"height":800}, color_scheme="dark"); pg=ctx.new_page()
    pg.on("pageerror", lambda e: errs.append(("dark",str(e))))
    pg.goto(BASE+"index.html",wait_until="networkidle")
    axe=Axe()
    for view in ["path","charts","scorer","speed","count","index"]:
        pg.click("#tab-"+view); pg.wait_for_timeout(100)
        if view == "count":
            pg.click("#cd-modes button[data-cmode=conv]"); pg.click("#cd-start"); pg.wait_for_timeout(80)
        v=axe.run(pg, options={"runOnly":{"type":"tag","values":["wcag2a","wcag2aa"]}}).response["violations"]
        print(f"  axe dark/{view}:", [(x['id'],len(x['nodes'])) for x in v]); check(f"dark: axe {view} clean", len(v)==0)
    pg.screenshot(path=OUT+"v2-desktop-dark.png")
    ctx.close()
    ctx=b.new_context(viewport={"width":1280,"height":800}); pg=ctx.new_page()
    pg.on("pageerror", lambda e: errs.append(("offline",str(e))))
    pg.goto(BASE+"index.html",wait_until="networkidle")
    ready=pg.evaluate("navigator.serviceWorker.ready.then(r=>!!r.active)")
    check("service worker registered and active", ready)
    pg.reload(wait_until="networkidle"); pg.wait_for_timeout(500)
    man=pg.evaluate("fetch('manifest.webmanifest').then(r=>r.json()).then(j=>j.name+'|'+j.icons.length)")
    check("manifest served", "Blackjack" in man, man)
    pg.evaluate("S.passed['0']=true;S.unlocked=1;saveState()")
    ctx.set_offline(True)
    pg.reload(wait_until="domcontentloaded"); pg.wait_for_timeout(400)
    check("offline reload works (cached shell)", "Blackjack" in pg.title() and pg.locator("#tabs [role=tab]").count()==10)
    check("offline: progress still there", pg.evaluate("S.passed['0']")==True)
    pg.click("#tab-charts"); check("offline: charts render", pg.locator("#chart-hard tr").count()>5)
    pg.screenshot(path=OUT+"v2-desktop-offline.png")
    icons=[pg.evaluate(f"fetch('{u}').then(r=>r.status)") for u in ["icon-192.png","icon-512.png","apple-touch-icon.png"]]
    check("icons load offline from cache", icons==[200,200,200], str(icons))
    b.close()
print("console/page errors:", errs)
f=[r for r in res if not r[1]]; print("TOTAL",len(res),"FAILS",len(f)); [print(" FAIL",x[0]) for x in f]
