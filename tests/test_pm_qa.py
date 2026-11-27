"""PM Bot QA items 2, 5, 6, 12 (and a few related checks). Server on :8766."""
import sys, math
from playwright.sync_api import sync_playwright
BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8766/"
results, errs = [], []
def check(name, cond, info=""):
    results.append((name, bool(cond), str(info)))
    print(("PASS " if cond else "FAIL "), name, ("" if cond else info))

def run(pg):
    # 2) Bankroll Lab TC frequencies: 8D 75% ~8.8% at TC>=+3, not 28%
    freq = pg.evaluate("()=>tcFreqAtLeast(3, {decks:8,h17:false,das:true,ls:true})")
    check("lab 8-deck 75% P(TC>=+3) is about 9%, not 28%", 0.07 <= freq <= 0.11, f"got {freq}")
    table = pg.evaluate("""()=>{
      if(typeof showView==='function') showView('lab');
      var rows=[...document.querySelectorAll('#lab-ramp-table tr')].slice(1);
      return rows.map(r=>({tc:r.children[0].textContent.trim(), pct:r.children[3].textContent.trim()}));
    }""")
    hi = 0
    for row in table:
        tc = int(row["tc"].replace("+",""))
        pct = float(row["pct"].replace("%",""))
        if tc >= 3: hi += pct
    check("lab ramp table TC>=+3 sums to about 9%", 7 <= hi <= 11, f"sum={hi} rows={table}")

    # 5) insurance is half the bet including $12.50; even money is 1:1 on the full bet
    amt = pg.evaluate("insuranceAmt(25)")
    check("insurance on a $25 bet is $12.50 (not floored to $12)", amt == 12.5, amt)
    ev = pg.evaluate("""()=>{
      S.unlockAll = true; S.unlocked = 6; showView('sim');
      SIM.bank = 1000; SIM.bet = 25; SIM.phase = 'bet'; SIM.dealt = 0; SIM.rc = 0;
      SIM.shoe = buildShoe();
      function C(r){ return {rank:r, suit:'♠'}; }
      // deal order pop: p1, up, p2, hole
      SIM.shoe.push(C('6'), C('10'), C('A'), C('A')); // wait, push adds at end, last is first pop
      // last push is first pop: need p1=A, up=A, p2=10, hole=6
      // so push hole, p2, up, p1
      SIM.shoe = buildShoe();
      SIM.shoe.push(C('6'));  // hole
      SIM.shoe.push(C('10')); // p2
      SIM.shoe.push(C('A'));  // up
      SIM.shoe.push(C('A'));  // p1
      simDeal();
      var btn = document.getElementById('sim-ins-yes').textContent;
      var before = {phase:SIM.phase, bank:SIM.bank, btn:btn, bj:handValue(SIM.hands[0].cards).blackjack};
      simInsurance(true);
      return {before:before, bank:SIM.bank, result:SIM.hands[0].result, insBet:SIM.insBet, msg:document.getElementById('sim-message').textContent, note:SIM.insNote};
    }""")
    check("even money offered when player has blackjack vs ace", ev["before"]["bj"] and ev["before"]["phase"]=="insurance", ev["before"])
    check("even money button names the full $25 bet at 1:1", "25" in ev["before"]["btn"] and "1:1" in ev["before"]["btn"], ev["before"]["btn"])
    check("even money pays 1:1: bank goes 1000 → 1025", ev["bank"] == 1025, ev)
    check("even money is not a half-bet insurance side bet", ev["insBet"] == 0, ev)
    check("even money result says 1:1", "Even money" in ev["result"] and "1:1" in ev["result"], ev["result"])

    ins = pg.evaluate("""()=>{
      SIM.bank = 1000; SIM.bet = 25; SIM.phase = 'bet'; SIM.dealt = 0; SIM.rc = 0;
      function C(r){ return {rank:r, suit:'♠'}; }
      SIM.shoe = buildShoe();
      SIM.shoe.push(C('9'));  // hole, not a ten, dealer has no BJ
      SIM.shoe.push(C('7'));  // p2
      SIM.shoe.push(C('A'));  // up
      SIM.shoe.push(C('9'));  // p1  — hard 16, not BJ
      simDeal();
      var btn = document.getElementById('sim-ins-yes').textContent;
      var can = !document.getElementById('sim-ins-yes').disabled;
      simInsurance(true);
      return {btn:btn, can:can, insBet:SIM.insBet, bank:SIM.bank, phase:SIM.phase};
    }""")
    check("insurance button shows $12.50 on a $25 bet", "$12.50" in ins["btn"], ins)
    check("insurance side bet is exactly $12.50", ins["insBet"] == 12.5, ins)
    check("insurance deducts $12.50 after the $25 bet (bank 962.50)", abs(ins["bank"] - 962.5) < 0.01, ins)

    # 6) missed cards come back in I18-only and in a Free Drill focus mode
    ix = pg.evaluate("""()=>{
      var e = indexEntries().find(function(x){ return x.pair10 && x.up==='5'; });
      S.idx.qn = 10;
      S.idx.srs = [{k:e.id+'@6', id:e.id, tc:6, box:0, due:0, miss:1}];
      document.getElementById('ix-mode').value = 'i18';
      var orig = Math.random; Math.random = function(){ return 0; };
      var hits = 0, n = 12, first = null;
      for(var i=0;i<n;i++){
        var p = ixPick();
        if(!first) first = {srs:!!p.srs, id:p.entry && p.entry.id, name:p.entry && p.entry.name};
        if(p.srs && p.entry && p.entry.id === e.id) hits++;
      }
      Math.random = orig;
      return {hits:hits, n:n, id:e.id, first:first};
    }""")
    check("I18-only mode re-serves a due missed card", ix["hits"] == ix["n"], ix)

    drill = pg.evaluate("""()=>{
      var h = {cards:[makeCard('8'), makeCard('8')], up:makeCard('5')};
      S.qn = 20; S.srs = [];
      recordAnswer(h, false);
      S.srs[0].due = S.qn; // due now (normal gap is 2 questions)
      var orig = Math.random; Math.random = function(){ return 0; };
      var due = srsDueForFocus('pair');
      var dueHard = srsDueForFocus('hard');
      Math.random = orig;
      return {due:due.length, key:due[0] && due[0].k, dueHard:dueHard.length, queue:S.srs.map(function(x){return x.k;})};
    }""")
    check("Free Drill pair focus keeps a missed pair in the review queue", drill["due"] >= 1 and "pair 8s" in (drill["key"] or ""), drill)
    check("a missed pair is not injected into the hard-hands focus", drill["dueHard"] == 0, drill)

    # also: i18 miss should not leak into fab4-only if it's an i18 card
    leak = pg.evaluate("""()=>{
      var e = indexEntries().find(function(x){ return x.grp==='i18' && x.pair10; });
      S.idx.srs = [{k:e.id+'@6', id:e.id, tc:6, box:0, due:0, miss:1}];
      document.getElementById('ix-mode').value = 'fab4';
      var orig = Math.random; Math.random = function(){ return 0; };
      var p = ixPick();
      Math.random = orig;
      return {gotI18: !!(p.entry && p.entry.id===e.id), grp: p.entry && p.entry.grp, empty:!!p.empty};
    }""")
    check("Fab 4 mode does not serve an I18 missed card", leak["gotI18"] is False, leak)

    # 12) 10-J is a 10-10 pair for splitting and indices, trainer and sim
    pair = pg.evaluate("""()=>{
      var cards = [makeCard('10'), makeCard('J')], up = makeCard('5');
      var v = handValue(cards);
      var d5 = decide(cards, up, 5, {decks:8,h17:false,das:true,ls:true}, {canSplit:true,canDouble:true,canSurrender:true});
      var d4 = decide(cards, up, 4, {decks:8,h17:false,das:true,ls:true}, {canSplit:true,canDouble:true,canSurrender:true});
      var ranks = ixRanks(indexEntries().find(function(x){ return x.pair10 && x.up==='5'; }));
      var bothTens = ranks.every(function(r){ return rankVal(r)===10; });
      return {pair:v.pair, at5:d5.play, at4:d4.play, bothTens:bothTens, ranks:ranks};
    }""")
    check("10+J is a pair", pair["pair"] is True, pair)
    check("10+J vs 5 at TC +5 is a split (I18 10-10)", pair["at5"] == "P", pair)
    check("10+J vs 5 at TC +4 stands (below the index)", pair["at4"] == "S", pair)
    check("index trainer 10-10 deals two ten-value cards", pair["bothTens"] is True, pair)

    can = pg.evaluate("""()=>{
      S.unlockAll = true; showView('sim');
      SIM.bank = 1000; SIM.bet = 25; SIM.phase = 'bet'; SIM.dealt = 0; SIM.rc = 0;
      function C(r){ return {rank:r, suit:'♠'}; }
      SIM.shoe = buildShoe();
      SIM.shoe.push(C('9'));  // hole
      SIM.shoe.push(C('J'));  // p2
      SIM.shoe.push(C('5'));  // up
      SIM.shoe.push(C('10')); // p1
      simDeal();
      var ctx = simCtx(SIM.hands[0]);
      return {pair:handValue(SIM.hands[0].cards).pair, canSplit:ctx.canSplit, ranks:[SIM.hands[0].cards[0].rank, SIM.hands[0].cards[1].rank], up:SIM.dealer[0].rank, phase:SIM.phase};
    }""")
    check("simulator treats 10+J as a splittable pair", can["pair"] and can["canSplit"] and can["phase"]=="play", can)

    # related: fmtSecs 2 decimals, go-to-level, storage banner presence
    check("fmtSecs shows 0.35 s with two decimals", pg.evaluate("fmtSecs(350)") == "0.35 s", pg.evaluate("fmtSecs(350)"))
    goto = pg.evaluate("""()=>{
      S.unlockAll = false; S.unlocked = 0; showView('path');
      document.querySelector('[data-goto-level=\"3\"]').click();
      var title0 = (document.querySelector('#stage h3')||{}).textContent || '';
      S.unlocked = 3;
      document.querySelector('[data-goto-level=\"3\"]').click();
      var title3 = (document.querySelector('#stage h3')||{}).textContent || '';
      return {title0:title0, title3:title3};
    }""")
    check("Go to Level 3 does not start Level 0 when Level 3 is still locked", "Level 0" not in goto["title0"], goto)
    check("Go to Level 3 starts Level 3 once it is unlocked", "Level 3" in goto["title3"], goto)

with sync_playwright() as p:
    b = p.chromium.launch(headless=True, executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
    ctx = b.new_context(viewport={"width":1280,"height":800})
    pg = ctx.new_page()
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.on("console", lambda m: errs.append(m.text) if m.type=="error" else None)
    pg.goto(BASE, wait_until="domcontentloaded")
    pg.wait_for_timeout(200)
    run(pg)
    ctx.close(); b.close()

print("\nconsole/page errors:", errs)
fails = [r for r in results if not r[1]]
print("TOTAL", len(results), "FAILS", len(fails))
for f in fails: print("  FAIL:", f[0], f[2][:400])
sys.exit(1 if fails or errs else 0)
