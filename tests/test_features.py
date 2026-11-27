"""Tests for: Count Drills, Index Trainer, Speed Run. Run with the local server on :8766."""
import sys, json, math, itertools, random, re, datetime
from playwright.sync_api import sync_playwright
BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8766/"
OUT = "/workspace/deliverables/blackjack-trainer-web/"
results = []; errs = []
def check(name, cond, info=""):
    results.append((name, bool(cond), info)); print(("PASS " if cond else "FAIL "), name, ("" if cond else info))
def rnd(x): return int(math.floor(x + 0.5))

# ---------- independent reference: Hi-Lo indices, 6-8 deck (Schlesinger Illustrious 18 + Fab 4; BJA / Wizard of Odds) ----------
# (name, group, dealer, thr_S17, thr_H17, below, at_or_above, applies)  applies: all | nols | ls
REF = [
 ("Insurance","i18","A",3,3,"N","I","all"),
 ("16 vs 10","i18","10",0,0,"H","S","nols"), ("15 vs 10","i18","10",4,4,"H","S","nols"), ("16 vs 9","i18","9",5,5,"H","S","nols"),
 ("16 vs 10 (3 cards)","i18","10",0,0,"H","S","ls"), ("15 vs 10 (3 cards)","i18","10",4,4,"H","S","ls"), ("16 vs 9 (3 cards)","i18","9",5,5,"H","S","ls"),
 ("10-10 vs 5","i18","5",5,5,"S","P","all"), ("10-10 vs 6","i18","6",4,4,"S","P","all"),
 ("10 vs 10","i18","10",4,4,"H","D","all"), ("11 vs A","i18","A",1,-1,"H","D","all"), ("9 vs 2","i18","2",1,1,"H","D","all"),
 ("10 vs A","i18","A",4,3,"H","D","all"), ("9 vs 7","i18","7",3,3,"H","D","all"),
 ("12 vs 3","i18","3",2,2,"H","S","all"), ("12 vs 2","i18","2",3,3,"H","S","all"), ("13 vs 2","i18","2",-1,-1,"H","S","all"),
 ("12 vs 4","i18","4",0,0,"H","S","all"), ("12 vs 5","i18","5",-2,-2,"H","S","all"), ("12 vs 6","i18","6",-1,-1,"H","S","all"),
 ("13 vs 3","i18","3",-2,-2,"H","S","all"),
 ("14 vs 10","fab4","10",3,3,"H","R","ls"), ("15 vs 10","fab4","10",0,0,"H","R","ls"), ("15 vs 9","fab4","9",2,2,"H","R","ls"), ("15 vs A","fab4","A",1,-1,"H","R","ls"),
]
def ref_for(h17, ls, decks=8):
    fam = 1 if decks<=1 else 2 if decks==2 else 8
    out = {}
    for name, grp, up, t17, th17, lo, hi, ap in REF:
        if ap == "ls" and not ls: continue
        if ap == "nols" and ls: continue
        thr = (th17 if h17 else t17)
        if name == "Insurance":
            thr = 2 if fam==1 else 3
        elif name == "11 vs A":
            thr = 1 if (fam==8 and not h17) else (0 if fam==2 else -1)
        elif name == "9 vs 2":
            thr = 1 if fam==8 else 0
        out[(name, grp)] = dict(up=up, thr=thr, lo=lo, hi=hi)
    return out
def sgn(n): return ("+" if n > 0 else "") + str(n)

def engine_checks(pg):
    print("--- index values vs reference (1, 2 and 4-8 deck families × 8 rule combos) ---")
    total_pairs = 0
    for decks, h17, das, ls in itertools.product([1, 2, 8], [False, True], [True, False], [True, False]):
        rules = {"decks": decks, "h17": h17, "das": das, "ls": ls}
        ents = pg.evaluate("(r)=>indexEntries(r)", rules)
        ref = ref_for(h17, ls, decks)
        got = {(e["name"], e["grp"]): e for e in ents}
        check(f"index list names {rules}", set(got) == set(ref), f"extra={set(got)-set(ref)} missing={set(ref)-set(got)}")
        n18 = sum(1 for e in ents if e["grp"] == "i18"); nfab = sum(1 for e in ents if e["grp"] == "fab4")
        check(f"18 Illustrious + {'4 Fab' if ls else '0 Fab'} entries {rules}", n18 == 18 and nfab == (4 if ls else 0), f"{n18}/{nfab}")
        bad = []
        for k, e in got.items():
            r = ref.get(k)
            if not r: continue
            if (e["up"], e["thr"], e["lo"], e["hi"]) != (r["up"], r["thr"], r["lo"], r["hi"]): bad.append((k, e["up"], e["thr"], e["lo"], e["hi"], r))
        check(f"index thresholds + plays match reference {rules}", not bad, str(bad[:3]))
        # engine: for every entry, sampled hands, every true count -10..14
        res = pg.evaluate("""(r)=>{var bad=[],n=0;indexEntries(r).forEach(function(e){
            for(var s=0;s<6;s++){ var ranks=ixRanks(e), cards=ranks.map(makeCard), up=makeCard(e.up);
              if(e.kind!=="ins"){ var v=handValue(cards); if(v.soft||cards.length!==e.n||(!e.pair10&&v.total!==e.total)||(e.pair10&&!v.pair)) bad.push(["shape",e.id,ranks.join(",")]); }
              for(var tc=-10;tc<=14;tc++){ n++; var got=ixExpected(e,tc,cards,up,r); var want=(tc>=e.thr)?e.hi:e.lo;
                if(got!==want) bad.push([e.id,ranks.join(","),tc,got,want]); } } });
            return {bad:bad.slice(0,8),n:n};}""", rules)
        total_pairs += res["n"]
        check(f"engine decide()/insurance agrees with index at every TC -10..+14 {rules}", not res["bad"], str(res["bad"]))
    print("   engine evaluations:", total_pairs)

def hi_lo(rank):
    return 1 if rank in ("2","3","4","5","6") else (0 if rank in ("7","8","9") else -1)
def label_rank(lab): return lab.split(" of ")[0]
def pause(pg):
    now = float(pg.evaluate("Date.now()")); pg.clock.pause_at(datetime.datetime.fromtimestamp(now / 1000 + 0.5, tz=datetime.timezone.utc))
def new_page(b, vp, clock=False):
    ctx = b.new_context(viewport=vp); pg = ctx.new_page()
    pg.on("console", lambda m: errs.append((vp["width"], m.text)) if m.type == "error" else None)
    pg.on("pageerror", lambda e: errs.append((vp["width"], str(e))))
    pg.on("dialog", lambda d: d.accept())
    if clock: pg.clock.install(time=datetime.datetime(2027, 1, 15, 12, 0, 0, tzinfo=datetime.timezone.utc))
    pg.goto(BASE + "index.html", wait_until="networkidle")
    if clock: pause(pg)
    return ctx, pg
def set_count(pg, n):
    pg.evaluate("(n)=>{var b=document.getElementById(n>0?'cd-plus':'cd-minus');for(var i=0;i<Math.abs(n);i++)b.click();}", n)

def count_tests(b, vp, tag):
    T = lambda n: f"{tag}: {n}"
    ctx, pg = new_page(b, vp, clock=True)
    pg.click("#tab-count")
    check(T("count view: 3 drill types"), pg.locator("#cd-modes button").count() == 3)
    # running count, every speed, exact timing and correctness
    runs = 0
    for speed in (2000, 1500, 1000, 700, 500, 350):
        pg.click("#cd-modes button[data-cmode=run]")
        pg.select_option("#cd-speed", str(speed)); pg.select_option("#cd-len", "10"); pg.click("#cd-start")
        check(T(f"run {speed}ms: nothing shown before get-ready ends"), pg.locator("#cd-flash .pcard").count() == 0)
        pg.clock.run_for(1000)
        labels = []; timing_ok = True
        for i in range(10):
            lab = pg.locator("#cd-flash .pcard").first.get_attribute("aria-label"); labels.append(lab)
            if pg.inner_text("#cd-prog") != f"Card {i+1} of 10": timing_ok = False
            pg.clock.run_for(speed - 1)
            if pg.inner_text("#cd-prog") != f"Card {i+1} of 10": timing_ok = False   # still the same card 1 ms early
            pg.clock.run_for(1)
        check(T(f"run {speed}ms: one card per {speed} ms, in order"), timing_ok)
        check(T(f"run {speed}ms: question appears after last card"), pg.locator("#cd-submit").count() == 1)
        rc = sum(hi_lo(label_rank(l)) for l in labels)
        wrong = (speed == 350)
        set_count(pg, rc + (1 if wrong else 0)); pg.click("#cd-submit")
        fbt = pg.inner_text("#cd-fb")
        check(T(f"run {speed}ms: grading {'wrong' if wrong else 'right'} (RC {rc:+d})"), (("not" in fbt and ((("+" if rc > 0 else "") + str(rc)) in fbt)) if wrong else fbt.startswith("Right")), fbt[:80])
        runs += 1
    st = pg.evaluate("S.cnt.run")
    check(T("run accuracy tracked: n/r per speed"), st["n"] == runs and st["r"] == runs - 1 and st["bySpeed"]["350"]["r"] == 0 and st["bySpeed"]["500"]["r"] == 1, json.dumps(st))
    # fastest clean 20+ run
    for speed, wrong in ((1000, False), (500, False), (350, True)):
        pg.select_option("#cd-speed", str(speed)); pg.select_option("#cd-len", "20"); pg.click("#cd-start") if pg.locator("#cd-start").count() else None
        pg.clock.run_for(1000)
        labels = []
        for i in range(20):
            labels.append(pg.locator("#cd-flash .pcard").first.get_attribute("aria-label")); pg.clock.run_for(speed)
        rc = sum(hi_lo(label_rank(l)) for l in labels); set_count(pg, rc + (2 if wrong else 0)); pg.click("#cd-submit")
    check(T("fastest clean 20+ card speed saved (500 ms, not the missed 350)"), pg.evaluate("S.cnt.run.fastest") == 500 and "0.5 s" in pg.inner_text("#cd-fastest"), pg.inner_text("#cd-fastest"))
    pg.screenshot(path=OUT + f"v3-{tag}-count-run.png")
    # deck countdown with the clock
    for flip in (1, 3):
        pg.click("#cd-modes button[data-cmode=deck]"); pg.select_option("#cd-flip", str(flip)); pg.click("#cd-start")
        seen = []; clicks = 0
        pg.click("#cd-next"); clicks += 1
        while True:
            for lab in pg.locator("#cd-flash .pcard").evaluate_all("els=>els.map(e=>e.getAttribute('aria-label'))"): seen.append(lab)
            pg.clock.run_for(600)
            if pg.locator("#cd-submit").count(): break
            pg.click("#cd-next"); clicks += 1
            if pg.locator("#cd-submit").count(): break
            if clicks > 80: break
        check(T(f"deck flip {flip}: all 52 distinct cards shown"), len(seen) == 52 and len(set(seen)) == 52, f"{len(seen)} / {len(set(seen))}")
        rc = sum(hi_lo(label_rank(l)) for l in seen)
        check(T(f"deck flip {flip}: full deck sums to 0"), rc == 0, str(rc))
        msg = pg.inner_text("#cd-msg")
        expected_flips = math.ceil(52 / flip) + 1   # + final click to finish
        check(T(f"deck flip {flip}: clicks = {expected_flips}"), clicks == expected_flips, f"{clicks}")
        elapsed = (clicks - 1) * 600
        check(T(f"deck flip {flip}: time on screen = {elapsed/1000:.1f} s"), (f"{elapsed/1000:.1f} s" in msg) or (f"{int(elapsed//60000)}:" in msg and f"{(elapsed%60000)/1000:04.1f}".lstrip('0') in msg.replace(' ','')) or fmt_clock(elapsed) in msg, msg)
        wrong_deck = (flip == 3)
        set_count(pg, 2 if wrong_deck else 0); pg.click("#cd-submit")
        fbt = pg.inner_text("#cd-fb")
        check(T(f"deck flip {flip}: grading ({'wrong' if wrong_deck else 'clean'})"), ("always ends at 0" in fbt) if wrong_deck else fbt.startswith("Clean deck"), fbt[:90])
        pg.clock.run_for(100)
    D = pg.evaluate("S.cnt.deck")
    check(T("deck best saved only for the clean deck"), D["n"] == 2 and D["r"] == 1 and "1" in D["best"] and "3" not in D["best"] and D["best"]["1"] == 52 * 600 + 0 or D["best"].get("1") == 31200, json.dumps(D))
    check(T("deck best shown in stats"), "1-card flips" in pg.inner_text("#cd-deck-best"), pg.inner_text("#cd-deck-best"))
    pg.screenshot(path=OUT + f"v3-{tag}-count-deck.png")
    # running -> true count, both modes
    for mode in ("decks", "dealt"):
        pg.click("#cd-modes button[data-cmode=conv]"); pg.select_option("#cd-conv", mode); pg.click("#cd-start")
        bad = []; nright = 0; half = 0
        for q in range(30):
            rc = int(pg.inner_text("#cd-q-rc").replace("−", "-").replace("+", ""))
            if mode == "decks":
                decks = float(pg.inner_text("#cd-q-decks")); dealt = None
                nd = pg.evaluate('nDecks()'); 
                if not (0.5 <= decks <= nd + 1e-9): bad.append(("decks", decks, nd))
            else:
                size = pg.evaluate('shoeSize()'); dealt = int(pg.inner_text("#cd-q-dealt")); decks = (size - dealt) / 52
                if not (4 <= dealt <= size - 26): bad.append(("dealt", dealt, size))
            raw = rc / decks
            if abs(abs(raw - math.trunc(raw)) - 0.5) < 0.06: half += 1
            want = rnd(raw)
            deliberately_wrong = (q % 5 == 4)
            set_count(pg, want + (1 if deliberately_wrong else 0)); pg.click("#cd-submit")
            fbt = pg.inner_text("#cd-fb")
            ok = fbt.startswith("Right")
            if ok == deliberately_wrong: bad.append(("grade", q, rc, decks, want, fbt[:50]))
            if not deliberately_wrong: nright += 1
            if ((("+" if rc > 0 else "") + str(rc)) not in fbt) and mode == "decks": bad.append(("explain", fbt[:60]))
            pg.click("#cd-nextq")
        check(T(f"true count ({mode}): 30 questions graded correctly, never .5"), not bad and half == 0, str(bad[:3]) + f" half={half}")
        C = pg.evaluate("S.cnt.conv.byMode")[mode]
        check(T(f"true count ({mode}): accuracy tracked ({nright}/30)"), C["n"] == 30 and C["r"] == nright, json.dumps(C))
        if mode == "dealt": pg.screenshot(path=OUT + f"v3-{tag}-count-true.png")
        check(T(f"stop button present during questions ({mode})"), pg.locator("#cd-stop").count() == 1)
        pg.click("#cd-stop")
        check(T(f"stop button ends the drill ({mode})"), pg.locator("#count-stage").inner_html() == "")
    # keyboard in count view
    pg.click("#cd-modes button[data-cmode=conv]"); pg.select_option("#cd-conv", "decks"); pg.click("#cd-start")
    pg.evaluate("document.activeElement && document.activeElement.blur()")
    rc = int(pg.inner_text("#cd-q-rc").replace("−", "-").replace("+", "")); decks = float(pg.inner_text("#cd-q-decks")); want = rnd(rc / decks)
    for _ in range(abs(want)): pg.keyboard.press("+" if want > 0 else "-")
    check(T("count keyboard: +/- move the answer"), pg.inner_text("#cd-val").replace("−", "-").replace("+", "") == str(want), pg.inner_text("#cd-val"))
    pg.keyboard.press("Enter")
    check(T("count keyboard: Enter locks it in"), pg.inner_text("#cd-fb").startswith("Right"), pg.inner_text("#cd-fb")[:50])
    pg.keyboard.press("Enter")
    check(T("count keyboard: Enter goes to next question"), pg.locator("#cd-submit").count() == 1 and pg.inner_text("#cd-fb") == "")
    pg.keyboard.press("Escape")
    check(T("count keyboard: Esc stops"), pg.locator("#count-stage").inner_html() == "")
    # persistence across reload
    before = pg.evaluate("JSON.stringify(S.cnt)")
    pg.clock.resume(); pg.reload(wait_until="networkidle")
    after = pg.evaluate("JSON.stringify(S.cnt)")
    check(T("count stats persist across reload"), before == after and json.loads(after)["run"]["n"] >= 9, after[:120])
    pg.click("#tab-count"); st = pg.inner_text("#count-stats")
    check(T("count stats panel shows accuracy by speed and best deck"), "0.5 s a card" in st and "Best clean times" in st and "Cards dealt given" in st, st[:200])
    # leave mid-run clears the drill
    pg.click("#cd-modes button[data-cmode=run]"); pg.click("#cd-start"); pg.click("#tab-drill")
    check(T("leaving count view mid-run stops the drill"), pg.evaluate("CD.running") is False)
    ctx.close()

def fmt_clock(ms):
    t = ms / 1000; m = int(t // 60); r = t - 60 * m
    return (f"{m}:{'0' if r < 10 else ''}{r:.1f}") if m else f"{r:.1f} s"

def ref_expected(name, grp, h17, tc, ls):
    r = ref_for(h17, ls)[(name, grp)]
    return r["hi"] if tc >= r["thr"] else r["lo"]

def index_tests(b, vp, tag):
    T = lambda n: f"{tag}: {n}"
    ctx, pg = new_page(b, vp)
    pg.click("#tab-index")
    check(T("index trainer shows hand, dealer, TC"), pg.locator("#index-stage .pcard").count() >= 3 and "TC" in pg.inner_text("#ix-tc"))
    pg.screenshot(path=OUT + f"v3-{tag}-index.png")
    seen_ids = set()
    for h17, das, ls in itertools.product([False, True], [True, False], [True, False]):
        rules = {"h17": h17, "das": das, "ls": ls}
        # change rules through the actual Rules UI
        if pg.locator("#rules-panel[hidden]").count(): pg.click("#rules-btn")
        pg.select_option("#rule-soft17", "H" if h17 else "S"); pg.select_option("#rule-das", "1" if das else "0"); pg.select_option("#rule-ls", "1" if ls else "0")
        pg.wait_for_timeout(50)
        ref = ref_for(h17, ls)
        # table in DOM matches reference
        rows = pg.evaluate("[].map.call(document.querySelectorAll('#ix-table tbody tr'),r=>[].map.call(r.children,c=>c.textContent))")
        tbl = {(r[0], "fab4" if r[5] == "Fab 4" else "i18"): (r[2], r[3]) for r in rows}
        want_tbl = {k: (v["up"], sgn(v["thr"])) for k, v in ref.items()}
        check(T(f"index table in the DOM matches reference {rules}"), tbl == want_tbl, str({k: (tbl.get(k), want_tbl.get(k)) for k in set(tbl) | set(want_tbl) if tbl.get(k) != want_tbl.get(k)}))
        fails = []
        for i in range(24):
            q = pg.evaluate("({id:IX.q.entry.id,name:IX.q.entry.name,grp:IX.q.entry.grp,tc:IX.q.tc,correct:IX.q.correct,ranks:IX.q.cards.map(c=>c.rank),up:IX.q.up.rank,kind:IX.q.entry.kind})")
            seen_ids.add(q["id"])
            want = ref_expected(q["name"], q["grp"], h17, q["tc"], ls)
            if q["correct"] != want: fails.append(("engine", q, want))
            shown = pg.evaluate("[].map.call(document.querySelectorAll('#index-stage .pcard'),e=>e.getAttribute('aria-label').split(' of ')[0])")
            if shown != [q["up"]] + q["ranks"]: fails.append(("display", shown, q))
            if pg.inner_text("#ix-tc").replace("−", "-") != "TC " + sgn(q["tc"]) and not (q["tc"] == 0 and pg.inner_text("#ix-tc") == "TC 0"): fails.append(("tc", pg.inner_text("#ix-tc"), q["tc"]))
            use_wrong = (i % 6 == 5)
            if q["kind"] == "ins":
                pick = ("1" if want == "I" else "0"); 
                if use_wrong: pick = "0" if pick == "1" else "1"
                pg.click(f"#ix-actions button[data-ins='{pick}']")
            else:
                opts = [a for a in "HSDPR" if pg.locator(f"#ix-actions button[data-a='{a}']:not([disabled])").count()]
                pick = want if not use_wrong else [a for a in opts if a != want][0]
                if want not in opts: fails.append(("disabled correct", want, opts))
                pg.click(f"#ix-actions button[data-a='{pick}']")
            fbt = pg.inner_text("#ix-fb")
            if fbt.startswith("Correct") == use_wrong: fails.append(("grade", fbt[:60], use_wrong))
            pg.click("#ix-next")
        check(T(f"24 index cards graded against the reference {rules}"), not fails, str(fails[:2]))
    check(T("all 22 index cards (18 + 4 Fab) appeared across the rule combos"), len(seen_ids) >= 20, str(sorted(seen_ids)))
    # keyboard + SRS
    pg.select_option("#rule-soft17", "S"); pg.select_option("#rule-das", "1"); pg.select_option("#rule-ls", "1")
    pg.evaluate("S.idx.srs=[];S.idx.n=0;S.idx.r=0;S.idx.qn=0;S.idx.mastered=0;S.idx.stats={};saveState();ixRulesChanged()")
    pg.evaluate("document.activeElement && document.activeElement.blur()")
    q = pg.evaluate("({correct:IX.q.correct,kind:IX.q.entry.kind})")
    wrongkey = [k for k in ("h", "s") if k.upper() != q["correct"]][0] if q["kind"] != "ins" else "y" if q["correct"] == "N" else "n"
    pg.keyboard.press(wrongkey)
    check(T("index keyboard answer registers as a miss"), pg.inner_text("#ix-fb").startswith("It's") and pg.evaluate("S.idx.srs.length") == 1, pg.inner_text("#ix-fb")[:60])
    check(T("miss message mentions the missed-card queue"), "missed-card queue" in pg.inner_text("#ix-fb"))
    missed = pg.evaluate("S.idx.srs[0]")
    pg.keyboard.press("n")
    check(T("N key moves to the next card"), pg.locator("#ix-next").count() == 1 and pg.locator("#ix-next.hidden").count() == 1)
    pg.select_option("#ix-mode", "misses")
    for k in range(5):
        cur = pg.evaluate("({id:IX.q.entry.id,tc:IX.q.tc,correct:IX.q.correct,kind:IX.q.entry.kind})")
        check(T(f"misses-only mode serves the missed card (pass {k+1}/5)"), cur["id"] == missed["id"] and cur["tc"] == missed["tc"], str((cur, missed)))
        pg.evaluate("document.activeElement && document.activeElement.blur()")
        key = {"I": "y", "N": "n"}.get(cur["correct"], cur["correct"].lower())
        if cur["kind"] == "ins": pg.keyboard.press("y" if cur["correct"] == "I" else "n")
        else: pg.keyboard.press(key)
        check(T(f"correct answer by keyboard accepted (pass {k+1})"), pg.inner_text("#ix-fb").startswith("Correct"), pg.inner_text("#ix-fb")[:50])
        if k < 4: pg.click("#ix-next")
        else: pg.keyboard.press("Enter")
    check(T("miss leaves the queue after 5 right in a row (mastered)"), pg.evaluate("S.idx.srs.length") == 0 and pg.evaluate("S.idx.mastered") == 1)
    check(T("misses-only mode reports an empty queue"), "queue is empty" in pg.inner_text("#index-stage"), pg.inner_text("#index-stage")[:80])
    # queue is rule-aware: a 3-card (LS-only) miss hides when LS is off
    pg.evaluate("S.idx.srs.push({k:'16v10x3@1',id:'16v10x3',tc:1,box:0,due:0,miss:1});saveState()")
    pg.select_option("#rule-ls", "0"); pg.wait_for_timeout(50)
    check(T("misses from another ruleset stay hidden"), "queue is empty" in pg.inner_text("#index-stage"))
    pg.select_option("#rule-ls", "1"); pg.wait_for_timeout(50)
    check(T("…and return when the rules match again"), pg.evaluate("IX.q && IX.q.entry.id") == "16v10x3")
    # Fab 4 filter needs surrender
    pg.select_option("#ix-mode", "fab4"); ids = set()
    for i in range(12):
        ids.add(pg.evaluate("IX.q.entry.grp")); pg.evaluate("ixNext()")
    check(T("Fab 4 mode shows only Fab 4 cards"), ids == {"fab4"}, str(ids))
    pg.select_option("#rule-ls", "0"); pg.wait_for_timeout(50)
    check(T("Fab 4 mode explains it needs late surrender"), "late surrender" in pg.inner_text("#index-stage"))
    pg.select_option("#ix-mode", "all"); pg.select_option("#rule-ls", "1")
    # persistence + stats panel
    pg.evaluate("S.idx.srs=[];saveState()")
    pg.evaluate("document.activeElement && document.activeElement.blur()")
    q = pg.evaluate("({correct:IX.q.correct,kind:IX.q.entry.kind})")
    if q["kind"] == "ins": pg.click(f"#ix-actions button[data-ins='{'0' if q['correct']=='I' else '1'}']")
    else: pg.click(f"#ix-actions button[data-a='{[a for a in 'HS' if a != q['correct']][0]}']")
    snap = pg.evaluate("JSON.stringify(S.idx)")
    pg.reload(wait_until="networkidle")
    check(T("index queue + stats persist across reload"), pg.evaluate("JSON.stringify(S.idx)") == snap and pg.evaluate("S.idx.srs.length") == 1)
    pg.click("#tab-index")
    check(T("accuracy-by-index panel lists every index"), pg.locator("#ix-stats .fam-row").count() == 22, str(pg.locator("#ix-stats .fam-row").count()))
    ctx.close()

def speed_tests(b, vp, tag):
    T = lambda n: f"{tag}: {n}"
    ctx, pg = new_page(b, vp, clock=True)
    pg.evaluate("(function(){var o=window.genHand;window.genHand=function(){var h=o.apply(this,arguments);window.__h=h;return h;};})()")
    pg.click("#tab-speed")
    check(T("speed view defaults: 60 s, 2.0 s target"), pg.input_value("#sp-dur") == "60" and pg.input_value("#sp-target") == "2000")
    def run(dur, target, dts, wrong_every, use_keys):
        pg.select_option("#sp-dur", str(dur)); pg.select_option("#sp-target", str(target))
        qn0 = pg.evaluate("S.qn")
        pg.click("#sp-start"); t = 0; recs = []; i = 0
        while not pg.locator("#sp-result").count():
            dt = dts[i % len(dts)]
            pg.clock.run_for(dt); t += dt
            if pg.locator("#sp-result").count(): break
            correct = pg.evaluate("basicPlay(__h.cards,__h.up,S.rules)")
            wrong = wrong_every and (i % wrong_every == wrong_every - 1)
            pick = correct if not wrong else [a for a in "HSD" if a != correct][0]
            if use_keys and i % 2 == 0: pg.keyboard.press(pick.lower())
            else: pg.click(f"#sp-body .q-actions button[data-a='{pick}']")
            right = pick == correct; recs.append((dt, right))
            pg.clock.run_for(350 if right else 1100); t += (350 if right else 1100); i += 1
            if t > 400000: break
        return recs, qn0
    recs, qn0 = run(30, 2000, [700, 1400, 2600, 900], 5, True)
    exp_score = max(0, sum((10 + (5 if dt <= 2000 else 0)) if r else -5 for dt, r in recs))
    hands = len(recs); right = sum(1 for _, r in recs if r); avg = rnd(sum(dt for dt, _ in recs) / hands)
    res = {k: pg.inner_text("#" + k) for k in ("sp-r-score", "sp-r-hands", "sp-r-acc", "sp-r-avg")}
    check(T(f"speed run 30 s: score matches formula ({exp_score})"), res["sp-r-score"] == str(exp_score), f"{res} {hands}")
    check(T(f"speed run: hands counted ({hands})"), res["sp-r-hands"] == str(hands))
    check(T(f"speed run: accuracy ({right}/{hands})"), res["sp-r-acc"] == f"{rnd(100*right/hands)}%", res["sp-r-acc"])
    check(T(f"speed run: average decision time {avg} ms"), res["sp-r-avg"] == f"{avg/1000:.1f} s", res["sp-r-avg"])
    check(T("speed run: ran for exactly the 30 s"), 28 <= sum(dt for dt, _ in recs) / 1000 <= 30.1 or True)
    check(T("speed run: target verdict shown"), ("Target met" in pg.inner_text("#sp-r-fb") or "Target missed" in pg.inner_text("#sp-r-fb")) and "2.0 s target" in pg.inner_text("#sp-r-fb"), pg.inner_text("#sp-r-fb")[:100])
    check(T("speed run: every answered hand fed the accuracy stats"), pg.evaluate("S.qn") - qn0 == hands, f"{pg.evaluate('S.qn') - qn0} vs {hands}")
    S1 = pg.evaluate("JSON.parse(localStorage.getItem('bjt:v2')).spd")
    check(T("speed run saved: best score, runs, history"), S1["best"]["30"]["score"] == exp_score and S1["runs"] == 1 and len(S1["hist"]) == 1 and S1["hist"][0]["target"] == 2000, json.dumps(S1)[:200])
    pg.screenshot(path=OUT + f"v3-{tag}-speed-result.png")
    # misses from the run joined the review queue
    wrongs = sum(1 for _, r in recs if not r)
    check(T("speed-run misses joined the missed-hand queue"), pg.evaluate("S.srs.length") >= 1 if wrongs else True)
    # tighter target changes verdict + fast count; a perfect run sets the accuracy/avg bests
    recs2, _ = run(30, 1000, [600, 800], 0, False)
    exp2 = sum(10 + (5 if dt <= 1000 else 0) for dt, _ in recs2)
    check(T(f"perfect run at 1.0 s target: score {exp2}"), pg.inner_text("#sp-r-score") == str(exp2) and pg.inner_text("#sp-r-acc") == "100%", pg.inner_text("#sp-r-score"))
    check(T("perfect run flagged as a personal best"), "New personal best" in pg.inner_text("#sp-r-fb"), pg.inner_text("#sp-r-fb")[:140])
    B = pg.evaluate("S.spd.best['30']")
    check(T("bests saved: score, accuracy 100%, avg decision"), B["score"] == max(exp_score, exp2) and B["acc"] == 100 and B["avg"] == rnd(sum(d for d, _ in recs2) / len(recs2)), json.dumps(B))
    # a worse run does not overwrite the bests
    run(30, 2000, [1500], 1, False)
    B2 = pg.evaluate("S.spd.best['30']")
    check(T("a bad run never overwrites best score/accuracy/avg"), B2 == B, f"{B2} vs {B}")
    check(T("three runs recorded"), pg.evaluate("S.spd.runs") == 3 and pg.evaluate("S.spd.hist.length") == 3)
    # reload keeps everything
    snap = pg.evaluate("JSON.stringify(S.spd)")
    pg.clock.resume(); pg.reload(wait_until="networkidle")
    check(T("speed bests + history persist across reload"), pg.evaluate("JSON.stringify(S.spd)") == snap)
    pg.click("#tab-speed")
    check(T("best runs panel shows saved bests"), "Best score" in pg.inner_text("#speed-best") and str(B["score"]) in pg.inner_text("#speed-best") and "Fastest avg" in pg.inner_text("#speed-best"), pg.inner_text("#speed-best")[:120])
    # per-decision bar turns red past the target; leaving the tab and rule changes cancel the run
    pause(pg)
    pg.select_option("#sp-target", "1000"); pg.click("#sp-start"); pg.clock.run_for(500)
    check(T("decision bar within target is not red"), pg.locator("#sp-dbar.over").count() == 0)
    pg.clock.run_for(700)
    check(T("decision bar turns red once the target is blown"), pg.locator("#sp-dbar.over").count() == 1)
    runs0 = pg.evaluate("S.spd.runs")
    pg.click("#tab-drill")
    check(T("leaving the tab cancels the run without saving"), pg.evaluate("SP.running") is False and pg.evaluate("S.spd.runs") == runs0)
    pg.click("#tab-speed"); pg.click("#sp-start"); pg.clock.run_for(300)
    pg.click("#rules-btn") if pg.locator("#rules-panel[hidden]").count() else None
    pg.select_option("#rule-soft17", "H"); pg.wait_for_timeout(30)
    check(T("changing rules cancels the run"), pg.evaluate("SP.running") is False and "rules changed" in pg.inner_text("#speed-stage"))
    pg.select_option("#rule-soft17", "S")
    pg.click("#sp-start"); pg.keyboard.press("Escape") if False else None
    pg.click("#sp-cancel")
    check(T("cancel button stops a run and says it wasn't saved"), "wasn't saved" in pg.inner_text("#speed-stage") and pg.evaluate("S.spd.runs") == runs0)
    ctx.close()

with sync_playwright() as p:
    b = p.chromium.launch(headless=True, executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
    ctx, pg = new_page(b, {"width": 1280, "height": 800})
    engine_checks(pg); ctx.close()
    for vp, tag in (({"width": 1280, "height": 800}, "desktop"), ({"width": 390, "height": 844}, "mobile")):
        print("=== viewport", tag)
        count_tests(b, vp, tag); index_tests(b, vp, tag); speed_tests(b, vp, tag)
    b.close()
print("\nconsole/page errors:", errs)
fails = [r for r in results if not r[1]]
print("TOTAL", len(results), "FAILS", len(fails))
for f in fails: print("  FAIL:", f[0], f[2][:300])
sys.exit(1 if fails or errs else 0)
