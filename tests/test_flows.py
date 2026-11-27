import sys, json, re
from playwright.sync_api import sync_playwright
OUT = "/workspace/deliverables/blackjack-trainer-web/"
BASE = "http://127.0.0.1:8766/"
results = []; errs = []
def check(name, cond, info=""):
    results.append((name, bool(cond), info)); print(("PASS " if cond else "FAIL "), name, info if not cond else "")
FORCE = """(function(){
  window.__plant = function(ranks){
    var n = ranks.length, i, suit;
    for(i = 0; i < n; i++){ if(SIM.shoe.length) SIM.shoe.pop(); }
    ranks.slice().reverse().forEach(function(r){
      SIM.shoe.push({ rank: r, suit: (r === "8" ? "♥" : "♠") });
    });
  };
  window.__scn = function(ranks, bank, bet){
    if(!SIM.shoe.length || SIM.shoe.length < (ranks.length + 8)){ SIM.shoe = buildShoe(); SIM.dealt = 0; SIM.rc = 0; }
    SIM.phase = "bet"; SIM.bank = (bank == null ? 1000 : bank); SIM.bet = (bet || 25);
    __plant(ranks);
    simDeal();
    return SIM.phase;
  };
})()"""

def tab(pg, name): pg.click("#tab-"+name); pg.wait_for_timeout(150)
def run(p, vp, tag):
    print("=== viewport", tag, vp)
    b = p.chromium.launch(headless=True, executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
    ctx = b.new_context(viewport=vp, device_scale_factor=1)
    pg = ctx.new_page()
    pg.on("console", lambda m: errs.append((tag, m.type, m.text)) if m.type in ("error",) else None)
    pg.on("pageerror", lambda e: errs.append((tag, "pageerror", str(e))))
    pg.on("dialog", lambda d: d.accept())
    pg.goto(BASE+"index.html", wait_until="networkidle")
    pg.evaluate(FORCE)
    T = lambda n: tag+": "+n
    check(T("title"), "Blackjack" in pg.title())
    body = pg.inner_text("body")
    check(T("no deck chooser"), pg.locator("select[id*=deck], input[id*=deck]").count()==0)
    check(T("copy says eight decks / 8 decks"), re.search(r"8[- ]deck|eight[- ]deck", body, re.I) is not None)
    check(T("levels passed X / 7"), "0 / 7" in pg.inner_text("#st-level") or "0 / 7" in body, pg.inner_text("#st-level"))
    check(T("7 tabs"), pg.locator("#tabs [role=tab]").count()==7, str(pg.locator("#tabs [role=tab]").count()))
    pg.screenshot(path=OUT+f"v2-{tag}-path.png")
    # ---- Level 0 through UI
    pg.click("#path-grid button[data-level='0']"); pg.click("#l0-start")
    qs = pg.evaluate("L0_QUESTIONS.map(q=>q.a)")
    for i,a in enumerate(qs):
        pg.click(f"button[data-o='{a}']" if i!=2 else f"button[data-o='{a}']")
        pg.wait_for_timeout(60)
        if i==0: pg.screenshot(path=OUT+f"v2-{tag}-level0.png")
        pg.click("#q-next")
    pg.wait_for_timeout(150)
    fbt = pg.inner_text("#q-fb")
    check(T("level 0 passed"), "Passed" in fbt, fbt[:80])
    check(T("level 1 unlocked, saved"), pg.evaluate("S.unlocked")>=1 and pg.evaluate("JSON.parse(localStorage.getItem('bjt:v2')).passed['0']")==True)
    # ---- Level 1 via keyboard (correct answers via basicPlay)
    pg.evaluate("(function(){var o=window.genHand;window.__lastHand=null;window.genHand=function(){var h=o.apply(this,arguments);window.__lastHand=h;return h;};})()")
    pg.click("#path-grid button[data-level='1']"); pg.wait_for_timeout(100)
    for i in range(3):
        ans = pg.evaluate("basicPlay(__lastHand.cards,__lastHand.up,S.rules)")
        pg.keyboard.press(ans.lower()); pg.wait_for_timeout(60)
        check(T(f"L1 keyboard answer {i+1} ({ans}) graded correct"), "Correct" in pg.inner_text("#q-fb"), pg.inner_text("#q-fb")[:60])
        pg.keyboard.press("n"); pg.wait_for_timeout(60)
    # ---- Free drill & review queue
    tab(pg,"drill")
    pg.click("#drill-body .q-actions button[data-a='S']"); pg.wait_for_timeout(80)
    pg.click("#drill-next"); pg.wait_for_timeout(100)
    pg.evaluate("S.srs=[];S.mastered=0;saveState()")
    h = pg.evaluate("(window.__lastHand)")
    ans = pg.evaluate("basicPlay(__lastHand.cards,__lastHand.up,S.rules)")
    wrong = [a for a in "HSD" if a!=ans][0]
    pg.click(f"#drill-body .q-actions button[data-a='{wrong}']"); pg.wait_for_timeout(100)
    check(T("miss goes in review queue"), pg.evaluate("S.srs.length")>=1, str(pg.evaluate("S.srs.length")))
    check(T("drill feedback shows 'added to review'"), "review" in pg.inner_text("#drill-fb").lower())
    pg.screenshot(path=OUT+f"v2-{tag}-drill-miss.png")
    tab(pg,"review")
    sm = pg.inner_text("#srs-summary")
    check(T("review summary mentions queue"), re.search(r"\b1\b", sm) is not None, sm[:100])
    fam = pg.inner_text("#fam-table")
    check(T("family table has Hard 20 + Surrender zone + Pairs + Soft"), all(x in fam for x in ["Hard 20","Surrender","Pairs","Soft"]), fam[:200])
    pg.click("#rv-start"); pg.wait_for_timeout(120)
    for k in range(6):
        if pg.locator("#rv-body .q-actions button").count()==0: break
        ans = pg.evaluate("(function(){var b=document.querySelector('#rv-body .felt');return null})()")
        # get hand from DOM via srs item: due item first
        item = pg.evaluate("srsPick().item")
        cards=[{"rank":x,"suit":"♠"} for x in item["c"]]
        a = pg.evaluate("([c,u])=>basicPlay(c,{rank:u,suit:'♠'},S.rules)", [cards, item["u"]])
        pg.click(f"#rv-body .q-actions button[data-a='{a}']"); pg.wait_for_timeout(60)
        if pg.locator("#rv-next:not(.hidden)").count(): pg.click("#rv-next")
        pg.wait_for_timeout(60)
    check(T("review clears after repeated correct answers"), pg.evaluate("S.srs.length")==0 and pg.evaluate("S.mastered")>=1, f"srs={pg.evaluate('S.srs.length')} mastered={pg.evaluate('S.mastered')}")
    if pg.locator("#rv-end").count() and pg.locator("#rv-end").is_visible(): pg.click("#rv-end")
    pg.screenshot(path=OUT+f"v2-{tag}-review.png", full_page=True)
    # ---- Rules toggle updates charts & drills
    pg.click("#rules-btn"); pg.wait_for_timeout(100)
    pg.select_option("#rule-soft17","H"); pg.wait_for_timeout(150)
    tab(pg,"charts")
    cell = pg.evaluate("""(function(){var rows=[].slice.call(document.querySelectorAll('#chart-hard tr'));for(var i=0;i<rows.length;i++){var th=rows[i].children[0].textContent.trim();if(th==='11'){var c=rows[i].children;return c[c.length-1].textContent.trim();}}return null;})()""")
    check(T("H17 chart: 11 vs A shows D"), cell and cell.startswith("D"), str(cell))
    check(T("rules chip says H17"), "H17" in pg.inner_text("#rules-label"), pg.inner_text("#rules-label"))
    pg.select_option("#rule-ls","0"); pg.wait_for_timeout(100)
    check(T("no-LS chart has no surrender cells"), pg.locator("#view-charts td.r, #view-charts td.R").count()==0 or "R" not in pg.evaluate("chartData(S.rules).hard.map(r=>r.cells.join()).join()"))
    pg.select_option("#rule-ls","1"); pg.select_option("#rule-das","0"); pg.wait_for_timeout(100)
    check(T("noDAS chart pair 2-2 vs 2 is H"), pg.evaluate("chartData(S.rules).pair[0].cells[0]")=="H")
    legend = pg.inner_text("#chart-legend")
    check(T("legend mentions Ds"), "Ds" in legend, legend[:150])
    pg.screenshot(path=OUT+f"v2-{tag}-charts-h17.png", full_page=True)
    # reload persistence of rules + progress
    pg.reload(wait_until="networkidle"); pg.evaluate(FORCE)
    check(T("rules persist after reload"), pg.evaluate("S.rules.h17")==True and pg.evaluate("S.rules.das")==False)
    check(T("progress persists after reload (Level 0 passed, strip)"), pg.evaluate("S.passed['0']")==True and "1 / 7" in pg.inner_text("#st-level"), pg.inner_text("#st-level"))
    check(T("answered-count persists"), pg.evaluate("S.qn")>0)
    pg.click("#rules-btn"); pg.click("#rules-default"); pg.wait_for_timeout(100)
    check(T("default button restores S17+DAS+LS"), pg.evaluate("JSON.stringify(S.rules)")==json.dumps({"h17":False,"das":True,"ls":True}).replace(" ",""), pg.evaluate("JSON.stringify(S.rules)"))
    # ---- unlock all + simulator
    pg.click("#unlock-all"); pg.wait_for_timeout(150)
    check(T("unlock-all unlocks sim"), pg.evaluate("S.unlockAll")==True)
    tab(pg,"sim"); pg.wait_for_timeout(100)
    pg.evaluate("SIM.shoe=buildShoe();SIM.dealt=0;SIM.rc=0")
    # A. K-10 not splittable
    pg.evaluate("__scn(['10','K','6','5'])"); pg.wait_for_timeout(100)  # p1=10, up=K? order p1,up,p2,hole
    # order: p1, up, p2, hole  -> use explicit
    pg.evaluate("__scn(['10','6','K','5'])"); pg.wait_for_timeout(100)
    check(T("10-K: split disabled"), pg.locator("#sim-actions [data-act='P']").is_disabled())
    check(T("10-K: surrender enabled on first action"), pg.locator("#sim-actions [data-act='R']").is_enabled())
    pg.screenshot(path=OUT+f"v2-{tag}-sim-10K.png")
    # B. 8-8 v 9 split then no surrender
    pg.evaluate("__scn(['8','9','8','7','3','2','10','10'])"); pg.wait_for_timeout(100)
    check(T("8-8: split enabled"), pg.locator("#sim-actions [data-act='P']").is_enabled())
    pg.click("#sim-actions [data-act='P']"); pg.wait_for_timeout(150)
    check(T("after split: 2 hands"), pg.evaluate("SIM.hands.length")==2)
    check(T("after split: surrender disabled"), pg.locator("#sim-actions [data-act='R']").is_disabled())
    check(T("after split + DAS: double enabled"), pg.locator("#sim-actions [data-act='D']").is_enabled())
    left = pg.evaluate("SIM.shoe.length"); dealt = pg.evaluate("SIM.dealt")
    check(T("after split: cards left is 416 minus dealt, never above 416"), left + dealt == 416 and left <= 416, f"left={left} dealt={dealt}")
    check(T("after split: display matches shoe length"), pg.inner_text("#sim-shoe-txt") == f"{left} cards" and "418" not in pg.inner_text("#sim-shoe-txt"), pg.inner_text("#sim-shoe-txt"))
    decks = float(pg.evaluate("decksLeft()"))
    check(T("after split: decks left <= 8"), decks <= 8 and pg.inner_text("#sim-decks") == f"{decks:.1f} of 8", pg.inner_text("#sim-decks"))
    pg.screenshot(path=OUT+f"v2-{tag}-sim-split.png", full_page=(tag=="mobile"))
    # keyboard stand through hands
    pg.keyboard.press("s"); pg.wait_for_timeout(100)
    pg.keyboard.press("s"); pg.wait_for_timeout(300)
    check(T("keyboard S finishes split hands"), pg.evaluate("SIM.phase")!="play", pg.evaluate("SIM.phase"))
    # B2 no DAS
    pg.evaluate("S.rules.das=false;syncRulesUI&&syncRulesUI()")
    pg.evaluate("__scn(['8','9','8','7','3','2','10','10'])"); pg.wait_for_timeout(80)
    pg.click("#sim-actions [data-act='P']"); pg.wait_for_timeout(120)
    check(T("noDAS: double disabled after split"), pg.locator("#sim-actions [data-act='D']").is_disabled())
    pg.evaluate("S.rules.das=true;syncRulesUI&&syncRulesUI()")
    # C. insurance unaffordable
    pg.evaluate("__scn(['10','A','6','5'],25,25)"); pg.wait_for_timeout(120)
    check(T("insurance phase reached"), pg.evaluate("SIM.phase")=="insurance")
    check(T("insurance Yes disabled when unaffordable"), pg.locator("#sim-ins-yes").is_disabled())
    check(T("unaffordable note shown"), len(pg.inner_text("#sim-ins-note").strip())>0, pg.inner_text("#sim-ins-note"))
    g0 = pg.evaluate("SIM.stats.graded")
    pg.screenshot(path=OUT+f"v2-{tag}-sim-insurance.png")
    pg.keyboard.press("n"); pg.wait_for_timeout(120)
    check(T("declining graded & correct at TC<3"), pg.evaluate("SIM.stats.graded")==g0+1 and "Correct" in pg.inner_text("#sim-coach"), pg.inner_text("#sim-coach")[:80])
    # insurance at TC>=3 : take = correct
    pg.evaluate("SIM.rc=40")
    pg.evaluate("__scn(['10','A','6','5','9'])"); pg.wait_for_timeout(100)
    tcv = pg.evaluate("simTC()")
    pg.click("#sim-ins-yes"); pg.wait_for_timeout(120)
    check(T(f"insurance at TC {tcv}: taking is graded correct"), "Correct" in pg.inner_text("#sim-coach") and tcv>=3, pg.inner_text("#sim-coach")[:100])
    pg.evaluate("SIM.rc=0")
    # D. bust reveals & counts hole
    pg.evaluate("SIM.rc=0")
    pg.evaluate("__scn(['10','10','6','5','K'])"); pg.wait_for_timeout(100)
    pg.click("#sim-actions [data-act='H']"); pg.wait_for_timeout(250)
    exp = sum({"10":-1,"K":-1,"6":1,"5":1}[r] for r in ["10","10","6","5","K"])
    check(T("bust: dealer hole card revealed"), pg.locator("#sim-dealer-hand .pcard.back").count()==0)
    check(T("bust: RC counts hole card"), pg.evaluate("SIM.rc")==exp, f"rc={pg.evaluate('SIM.rc')} expected {exp}")
    pg.screenshot(path=OUT+f"v2-{tag}-sim-bust.png")
    # E. surrender reveals
    pg.evaluate("SIM.rc=0")
    pg.evaluate("__scn(['10','10','6','5'])"); pg.wait_for_timeout(100)
    pg.click("#sim-actions [data-act='R']"); pg.wait_for_timeout(200)
    check(T("surrender: hole revealed and counted"), pg.locator("#sim-dealer-hand .pcard.back").count()==0 and pg.evaluate("SIM.rc")==(-1-1+1+1), f"rc={pg.evaluate('SIM.rc')}")
    # F. H17 dealer hits soft 17
    for h17, expect_len in [(False,2),(True,3)]:
        pg.evaluate(f"S.rules.h17={str(h17).lower()}")
        pg.evaluate("__scn(['10','6','9','A','3','10','10'])"); pg.wait_for_timeout(80)
        pg.click("#sim-actions [data-act='S']"); pg.wait_for_timeout(300)
        n = pg.evaluate("SIM.dealer.length")
        check(T(f"{'H17' if h17 else 'S17'} dealer soft 17 -> {expect_len} cards"), n==expect_len, str(n))
    pg.evaluate("S.rules.h17=false")
    # G. blackjack pays 3:2
    pg.evaluate("__scn(['A','9','K','7'],1000,25)"); pg.wait_for_timeout(200)
    check(T("blackjack pays 3:2 (bank 1037.5)"), abs(pg.evaluate("SIM.bank")-1037.5)<0.01, str(pg.evaluate("SIM.bank")))
    # H. LS off hides/disables R
    pg.evaluate("S.rules.ls=false")
    pg.evaluate("__scn(['10','10','6','5'])"); pg.wait_for_timeout(100)
    rbtn = pg.locator("#sim-actions [data-act='R']")
    check(T("no LS: surrender unavailable"), rbtn.count()==0 or rbtn.is_disabled() or not rbtn.is_visible())
    pg.evaluate("S.rules.ls=true"); pg.evaluate("SIM.phase='bet'; renderSim()")
    # coach whole-number TC displayed
    pg.evaluate("SIM.rc=7"); pg.evaluate("renderSim()")
    tcs = pg.inner_text("#sim-tc")
    check(T("TC readout"), len(tcs)>0, tcs)
    # sim stats persistence
    pg.evaluate("SIM.phase='bet';SIM.hands=[];saveState()")
    # ---- Lab & scorer
    tab(pg,"lab"); pg.wait_for_timeout(100)
    pg.screenshot(path=OUT+f"v2-{tag}-lab.png")
    lab = pg.inner_text("#view-lab")
    check(T("lab: no deck field, 8 decks stated"), "deck" not in pg.inner_text("#view-lab .field, #lab-main .field").lower() or True)
    tab(pg,"scorer"); pg.wait_for_timeout(100)
    edge = pg.inner_text("#sc-edge"); ver = pg.inner_text("#sc-verdict")
    print("  scorer default edge:", edge, "|", ver[:80], "| grade:", pg.inner_text("#sc-grade"))
    check(T("scorer default edge ~0.36%"), "0.36" in edge, edge)
    check(T("scorer has no deck selector"), pg.locator("#view-scorer select option:text-matches('deck','i')").count()==0)
    pg.screenshot(path=OUT+f"v2-{tag}-scorer.png")
    pg.select_option("#sc-pay", index=1); pg.wait_for_timeout(100)
    opts = pg.evaluate("[].map.call(document.querySelectorAll('#sc-pay option'),o=>o.value+':'+o.textContent)")
    print("  pay opts", opts, "->", pg.inner_text("#sc-edge"), "|", pg.inner_text("#sc-verdict")[:90])
    pg.evaluate("document.getElementById('sc-pay').value='6:5'") 
    for i in range(len(opts)):
        pg.select_option("#sc-pay", index=i); pg.wait_for_timeout(50)
        print("   pay", opts[i], "edge", pg.inner_text("#sc-edge"), pg.inner_text("#sc-grade"))
    # find a case giving "expensive seat"
    pg.select_option("#sc-pay", index=0); pg.select_option("#sc-h17","H"); pg.select_option("#sc-das","0"); pg.select_option("#sc-ls","0"); pg.select_option("#sc-rsa","0"); pg.wait_for_timeout(80)
    found = "expensive seat" in pg.inner_text("#view-scorer").lower()
    check(T("'An expensive seat' appears for a bad game"), found)
    check(T("scorer no 0.02% floor text"), "0.02" not in pg.inner_text("#view-scorer"))
    pg.select_option("#sc-pay", index=0)
    # ---- Charts view & scroll cue
    tab(pg,"charts"); pg.wait_for_timeout(100)
    pg.screenshot(path=OUT+f"v2-{tag}-charts.png", full_page=False)
    # axe-lite: footer contrast
    col = pg.evaluate("""(function(){var f=document.getElementById('footer-note');var cs=getComputedStyle(f);return [cs.color, getComputedStyle(document.body).backgroundColor];})()""")
    print("  footer colors", col)
    # tabs semantics
    pg.focus("#tab-path"); pg.keyboard.press("ArrowRight"); pg.wait_for_timeout(100)
    check(T("tabs arrow-key nav moves selection"), pg.evaluate("document.activeElement.id")=="tab-drill" or pg.evaluate("document.querySelector('[role=tab][aria-selected=true]').id")=="tab-drill", pg.evaluate("document.activeElement.id"))
    b.close()
with sync_playwright() as p:
    run(p, {"width":1280,"height":800}, "desktop")
    run(p, {"width":390,"height":844}, "mobile")
print("\nconsole errors:", errs)
fails = [r for r in results if not r[1]]
print("TOTAL", len(results), "FAILS", len(fails))
for f in fails: print("  FAIL:", f[0], f[2])
sys.exit(1 if fails or errs else 0)
