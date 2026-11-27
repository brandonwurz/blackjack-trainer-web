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

def tab(pg, name):
    pg.evaluate("""(n)=>{
      var p=document.getElementById('rules-panel');
      if(p) p.setAttribute('hidden','');
      var b=document.getElementById('rules-btn');
      if(b) b.setAttribute('aria-expanded','false');
      showView(n);
    }""", name)
    pg.wait_for_timeout(150)
def set_rule(pg, field, value):
    pg.evaluate("""([f,v])=>{ var el=document.getElementById(f); el.value=v; el.dispatchEvent(new Event('change',{bubbles:true})); }""", [field, value])
    pg.wait_for_timeout(80)
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
    check(T("default is 8 decks"), "8D" in pg.inner_text("#rules-label") or "8 deck" in body.lower(), pg.inner_text("#rules-label"))
    check(T("deck count options 1/2/4/6/8"), pg.evaluate('()=>[...document.querySelectorAll("#rule-decks option")].map(o=>o.value)' )==["1","2","4","6","8"])
    check(T("levels passed X / 7"), "0 / 7" in pg.inner_text("#st-level") or "0 / 7" in body, pg.inner_text("#st-level"))
    check(T("10 tabs"), pg.locator("#tabs [role=tab]").count()==10, str(pg.locator("#tabs [role=tab]").count()))
    pg.screenshot(path=OUT+f"v2-{tag}-path.png")
    # ---- Level 0 through UI
    pg.click("#path-grid button[data-level='0']"); pg.click("#l0-start")
    for i in range(8):
        pg.evaluate("""()=>{
          var q = document.querySelector("#q-body p").textContent;
          var Q = L0_QUESTIONS.find(function(x){ return x.q === q; });
          var want = Q.opts[Q.a];
          Array.prototype.forEach.call(document.querySelectorAll("#q-body button[data-o]"), function(b){
            var c = b.cloneNode(true);
            Array.prototype.forEach.call(c.querySelectorAll("kbd"), function(k){ k.remove(); });
            if(c.textContent.trim() === want) b.click();
          });
        }""")
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
    set_rule(pg, "rule-soft17", "H")
    tab(pg,"charts")
    cell = pg.evaluate("""(function(){var rows=[].slice.call(document.querySelectorAll('#chart-hard tr'));for(var i=0;i<rows.length;i++){var th=rows[i].children[0].textContent.trim();if(th==='11'){var c=rows[i].children;return c[c.length-1].textContent.trim();}}return null;})()""")
    check(T("H17 chart: 11 vs A shows D"), cell and cell.startswith("D"), str(cell))
    check(T("rules chip says H17"), "H17" in pg.inner_text("#rules-label"), pg.inner_text("#rules-label"))
    set_rule(pg, "rule-ls", "0")
    check(T("no-LS chart has no surrender cells"), pg.locator("#view-charts td.r, #view-charts td.R").count()==0 or "R" not in pg.evaluate("chartData(S.rules).hard.map(r=>r.cells.join()).join()"))
    set_rule(pg, "rule-ls", "1"); set_rule(pg, "rule-das", "0")
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
    check(T("default button restores 8D+S17+DAS+LS"), pg.evaluate("S.rules.decks")==8 and pg.evaluate("S.rules.h17")==False and pg.evaluate("S.rules.das")==True and pg.evaluate("S.rules.ls")==True, pg.evaluate("JSON.stringify(S.rules)"))
    # ---- unlock all + simulator
    pg.click("#unlock-all"); pg.wait_for_timeout(150)
    check(T("unlock-all unlocks sim"), pg.evaluate("S.unlockAll")==True)
    tab(pg,"sim"); pg.wait_for_timeout(100)
    pg.evaluate("SIM.shoe=buildShoe();SIM.dealt=0;SIM.rc=0")
    # A. K-10 not splittable
    pg.evaluate("__scn(['10','K','6','5'])"); pg.wait_for_timeout(100)  # p1=10, up=K? order p1,up,p2,hole
    # order: p1, up, p2, hole  -> use explicit
    pg.evaluate("__scn(['10','6','K','5'])"); pg.wait_for_timeout(100)
    check(T("10-K: split enabled (any two ten-value cards)"), pg.locator("#sim-actions [data-act='P']").is_enabled())
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
    size = pg.evaluate("shoeSize()"); check(T("after split: cards left is shoe size minus dealt"), left + dealt == size and left <= size, f"left={left} dealt={dealt} size={size}")
    check(T("after split: display matches shoe length"), pg.inner_text("#sim-shoe-txt") == f"{left} cards" and "418" not in pg.inner_text("#sim-shoe-txt"), pg.inner_text("#sim-shoe-txt"))
    decks = float(pg.evaluate("decksLeft()"))
    nd = pg.evaluate("nDecks()"); check(T("after split: decks left display"), decks <= nd and pg.inner_text("#sim-decks") == f"{decks:.1f} of {nd}", pg.inner_text("#sim-decks"))
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
    check(T("lab has no separate decks select (uses Rules)"), pg.locator("#lab-main #sc-decks, #lab-main #rule-decks").count()==0)
    tab(pg,"scorer"); pg.wait_for_timeout(100)
    edge = pg.inner_text("#sc-edge"); ver = pg.inner_text("#sc-verdict")
    print("  scorer default edge:", edge, "|", ver[:80], "| grade:", pg.inner_text("#sc-grade"))
    check(T("scorer default edge ~0.35% (8D S17 DAS LS)"), "0.35" in edge, edge)
    check(T("scorer has a decks selector"), pg.locator("#sc-decks").count()==1)
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

    # ---- Deck count setting + forced split + design QA
    pg.evaluate("S.rules = {decks:8,h17:false,das:true,ls:true}; onRulesChanged();")
    pg.evaluate("document.getElementById('rules-panel').removeAttribute('hidden'); document.getElementById('rules-btn').setAttribute('aria-expanded','true');")
    check(T("rules panel has a decks select"), pg.locator("#rule-decks").count()==1)
    pg.select_option("#rule-decks", "1")
    pg.wait_for_timeout(80)
    check(T("switching to 1 deck updates the rules label"), "1D" in pg.inner_text("#rules-label"), pg.inner_text("#rules-label"))
    check(T("1-deck shoe is 52 cards"), pg.evaluate("shoeSize()")==52 and pg.evaluate("SIM.shoe.length")==52, str(pg.evaluate("({sz:shoeSize(),n:SIM.shoe.length})")))
    tab(pg,"charts"); pg.wait_for_timeout(80)
    eleven_a = pg.evaluate("chartData(S.rules).hard.filter(r=>r.label==='11')[0].cells[9]")
    check(T("1-deck S17: 11 vs A is a double"), eleven_a=="D", eleven_a)
    set_rule(pg, "rule-decks", "8")
    eleven_a8 = pg.evaluate("chartData(S.rules).hard.filter(r=>r.label==='11')[0].cells[9]")
    check(T("8-deck S17: 11 vs A is a hit"), eleven_a8=="H", eleven_a8)
    # close rules if open
    pg.evaluate("document.getElementById('rules-panel').setAttribute('hidden',''); document.getElementById('rules-btn').setAttribute('aria-expanded','false');")

    # Forced split in the simulator
    tab(pg,"sim"); pg.wait_for_timeout(80)
    pg.evaluate("""() => {
      S.unlockAll = true; refreshStrip();
      SIM.phase = "bet"; SIM.bank = 2000; SIM.bet = 25; SIM.hands = []; SIM.dealer = [];
      if (SIM.shoe.length < 20) { SIM.shoe = buildShoe(); SIM.dealt = 0; SIM.rc = 0; }
      var ranks = ["8","9","8","6","3","2","10","5"];
      for (var i=0;i<ranks.length;i++) SIM.shoe.pop();
      ranks.slice().reverse().forEach(function(r){ SIM.shoe.push({rank:r,suit:"♠"}); });
      simDeal();
    }""")
    pg.wait_for_timeout(80)
    check(T("forced split: 8-8 dealt, Split enabled"), pg.locator("#sim-actions [data-act='P']").is_enabled())
    check(T("forced split: Hit and Stand are visible after Deal"), pg.locator("#sim-actions [data-act='H']").is_visible() and pg.locator("#sim-actions [data-act='S']").is_visible())
    pg.click("#sim-actions [data-act='P']")
    pg.wait_for_timeout(80)
    check(T("forced split: two hands after Split"), pg.evaluate("SIM.hands.length")==2, str(pg.evaluate("SIM.hands.length")))

    # Level result: retry button + progress bar reflects the score
    pg.evaluate("()=>{ S.unlockAll=true; showView('path'); startLevel(0); finishLevel(LEVELS[0], 1, 8, 7); }")
    pg.wait_for_timeout(80)
    check(T("failed level shows a Try again button"), pg.locator("#q-retry").count()==1 and pg.locator("#q-retry").is_visible())
    bar = pg.evaluate("""()=>{var el=document.getElementById('q-bar'); var w=el ? el.style.width : ''; return {w:w, fail: !!(el && el.classList.contains('fail'))};}""")
    width = float(str(bar.get("w","0")).replace("%","") or 0)
    check(T("failed level bar is ~1/8, not full green"), 10 <= width <= 20 and bar.get("fail"), str(bar))

    # Install panel: hidden in standalone, only on the path tab otherwise
    tab(pg,"path"); pg.wait_for_timeout(50)
    check(T("install panel is on the Level Path tab"), pg.locator("#install-panel").count()==1 and pg.locator("#install-panel").is_visible())
    tab(pg,"drill"); pg.wait_for_timeout(50)
    hidden_elsewhere = pg.evaluate("document.getElementById('install-panel').hidden===true")
    check(T("install panel is hidden on other tabs"), hidden_elsewhere)
    tab(pg,"path")
    pg.evaluate("()=>{ window.__realSA = isStandalone; isStandalone = function(){ return true; }; syncInstallPanel(); }")
    check(T("install panel hides when running installed/standalone"), pg.evaluate("document.getElementById('install-panel').hidden===true"))
    pg.evaluate("()=>{ isStandalone = window.__realSA; syncInstallPanel(); }")

    # Light-mode feedback: picked and correct stay opaque
    tab(pg,"drill"); pg.wait_for_timeout(80)
    pg.evaluate("""()=>{
      var btns=document.querySelectorAll('#view-drill .q-actions button');
      if(btns[0]) btns[0].click();
    }""")
    pg.wait_for_timeout(80)
    opac = pg.evaluate("""()=>{
      var btns=[...document.querySelectorAll('#view-drill .q-actions button')];
      return btns.map(b=>({cls:b.className, op:getComputedStyle(b).opacity, dis:b.disabled}));
    }""")
    marked=[o for o in opac if "picked-right" in o["cls"] or "picked-wrong" in o["cls"]]
    others=[o for o in opac if "picked-right" not in o["cls"] and "picked-wrong" not in o["cls"]]
    check(T("drill feedback: picked/correct buttons stay fully opaque"), marked and all(abs(float(o["op"])-1)<0.05 for o in marked), str(opac))
    check(T("drill feedback: unchosen buttons are faded"), not others or all(float(o["op"])<0.9 for o in others), str(opac))

    # Desktop tabs: Game Scorer and Strategy Charts are not clipped
    if tag=="desktop":
        boxes = pg.evaluate("""()=>[...document.querySelectorAll('#tabs [role=tab]')].map(b=>{
          var r=b.getBoundingClientRect(); return {id:b.id, right:r.right, bottom:r.bottom, top:r.top};
        })""")
        vw = pg.evaluate("window.innerWidth")
        clipped=[b for b in boxes if b["right"]>vw+1]
        check(T("desktop tab bar does not clip the last tabs"), not clipped, str(clipped))
        check(T("desktop tabs include Scorer and Charts in the wrapped bar"), any(b["id"]=="tab-scorer" and b["top"]>=0 for b in boxes) and any(b["id"]=="tab-charts" for b in boxes))
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
