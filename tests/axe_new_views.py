from playwright.sync_api import sync_playwright
from axe_playwright_python.sync_playwright import Axe
with sync_playwright() as p:
    b=p.chromium.launch(headless=True,executable_path="/usr/bin/google-chrome",args=["--no-sandbox"])
    for scheme,vp in [("light",{"width":1280,"height":800}),("light",{"width":390,"height":844}),("dark",{"width":1280,"height":800})]:
        pg=b.new_context(viewport=vp,color_scheme=scheme).new_page(); pg.goto("http://127.0.0.1:8766/index.html",wait_until="networkidle")
        for v in ["speed","count","index"]:
            pg.click("#tab-"+v)
            if v=="count": pg.click("#cd-modes button[data-cmode=conv]"); pg.click("#cd-start")
            if v=="speed": pg.click("#sp-start"); pg.wait_for_timeout(150)
            r=Axe().run(pg,options={"runOnly":{"type":"tag","values":["wcag2a","wcag2aa"]}}).response["violations"]
            for x in r:
                for n in x["nodes"]: print(scheme,vp["width"],v,x["id"],n["target"],(n["any"][0]["message"])[:150] if n.get("any") else n.get("failureSummary","")[:150])
    b.close()
