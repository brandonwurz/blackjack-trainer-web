"""Assert the simulator shoe never exceeds 416 cards and stays in sync with cards dealt."""
import sys
from playwright.sync_api import sync_playwright

URL = "http://127.0.0.1:8766/index.html"
SCRIPT = r"""
() => {
  function fail(msg, extra){ return { ok:false, msg: msg, extra: extra || null }; }
  function snapshot(){
    var onTable = (SIM.dealer ? SIM.dealer.length : 0);
    (SIM.hands || []).forEach(function(h){ onTable += h.cards.length; });
    return {
      left: SIM.shoe.length, dealt: SIM.dealt, phase: SIM.phase,
      decks: decksLeft(), shown: document.getElementById("sim-shoe-txt").textContent,
      decksShown: document.getElementById("sim-decks").textContent, onTable: onTable, rc: SIM.rc
    };
  }
  function check(tag){
    var s = snapshot();
    if (s.left + s.dealt !== SHOE_SIZE)
      return fail(tag + ": cards left (" + s.left + ") + dealt (" + s.dealt + ") = " + (s.left + s.dealt) + ", expected " + SHOE_SIZE, s);
    if (s.left > SHOE_SIZE) return fail(tag + ": cards left " + s.left + " > 416", s);
    if (s.dealt < 0) return fail(tag + ": dealt negative", s);
    if (s.decks > 8 + 1e-12) return fail(tag + ": decks left " + s.decks + " > 8", s);
    var expectTxt = s.left + " cards";
    if (s.shown !== expectTxt) return fail(tag + ": display '" + s.shown + "' != '" + expectTxt + "'", s);
    var expectDecks = s.decks.toFixed(1) + " of 8";
    if (s.decksShown !== expectDecks) return fail(tag + ": decks display '" + s.decksShown + "' != '" + expectDecks + "'", s);
    return null;
  }

  S.unlockAll = true; S.rules = { h17:false, das:true, ls:true };
  if (!SIM) initSim();
  SIM.shoe = buildShoe(); SIM.dealt = 0; SIM.rc = 0; SIM.phase = "bet";
  SIM.bank = 5000; SIM.bet = 0; SIM.hands = []; SIM.dealer = [];
  renderSim();
  var err = check("fresh shoe"); if (err) return err;
  if (SIM.shoe.length !== 416) return fail("fresh shoe is " + SIM.shoe.length + " cards, expected 416");

  function plant(ranks){
    var n = ranks.length, i;
    for (i = 0; i < n; i++){ if (SIM.shoe.length) SIM.shoe.pop(); }
    ranks.slice().reverse().forEach(function(r){ SIM.shoe.push({ rank:r, suit:"♠" }); });
  }
  function forceDeal(ranks, bank, bet){
    if (SIM.phase !== "bet") { /* shouldn't start mid-hand */ }
    if (SIM.shoe.length < ranks.length + 16 || SIM.dealt >= CUT_CARDS - 16){
      SIM.shoe = buildShoe(); SIM.dealt = 0; SIM.rc = 0;
    }
    SIM.phase = "bet";
    SIM.bank = (bank == null ? Math.max(SIM.bank, 1000) : bank);
    SIM.bet = bet || 25;
    plant(ranks);
    var before = SIM.shoe.length;
    simDeal();
    return before;
  }
  function playOut(prefer){
    if (SIM.phase === "insurance"){
      var take = prefer === "ins-yes" && SIM.bank >= Math.floor((SIM.hands[0] ? SIM.hands[0].bet : 25) / 2);
      simInsurance(!!take);
    }
    var guard = 0;
    while (SIM.phase === "play" && guard++ < 30){
      var h = SIM.hands[SIM.active], ctx = simCtx(h);
      var act;
      if (prefer === "split" && ctx.canSplit) act = "P";
      else if (prefer === "surrender" && ctx.canSurrender) act = "R";
      else if (prefer === "bust" && ctx.canSurrender) act = "H"; // 16v10: hitting can bust
      else if (prefer === "bust") act = "H";
      else {
        var d = decide(h.cards, SIM.dealer[0], simTC(), S.rules, ctx);
        act = d.play;
        if (act === "D" && !ctx.canDouble) act = "H";
        if (act === "P" && !ctx.canSplit) act = "H";
        if (act === "R" && !ctx.canSurrender) act = "H";
      }
      simAct(act);
    }
    if (SIM.phase === "play") return fail("hand did not finish", snapshot());
    return check("after hand " + prefer);
  }

  var counts = { rounds:0, splits:0, surrenders:0, insurance:0, busts:0 };
  function tally(){
    counts.rounds++;
    (SIM.hands || []).forEach(function(h){
      if (h.fromSplit) counts.splits = counts.splits; // counted below
      if (h.result && /Surrendered/.test(h.result)) counts.surrenders++;
      if (h.result === "Bust") counts.busts++;
    });
    if (SIM.hands && SIM.hands.length > 1) counts.splits++;
    if (SIM.insNote) counts.insurance++;
  }

  var scripted = [
    { name:"split 8s", ranks:["8","9","8","7","3","2","10","10"], prefer:"split" },
    { name:"surrender 16v10", ranks:["10","10","6","5"], prefer:"surrender" },
    { name:"insurance ace", ranks:["10","A","6","5","9"], prefer:"ins-yes" },
    { name:"bust 16v10", ranks:["10","10","6","5","K"], prefer:"bust" },
    { name:"split aces", ranks:["A","6","A","9","10","5"], prefer:"split" },
    { name:"BJ vs 9", ranks:["A","9","K","7"], prefer:"basic" },
    { name:"double 11", ranks:["5","6","6","9","10"], prefer:"basic" }
  ];
  var i, j;
  for (i = 0; i < 8; i++){
    for (j = 0; j < scripted.length; j++){
      var sc = scripted[j];
      forceDeal(sc.ranks);
      err = check("dealt " + sc.name + " #" + i); if (err) return err;
      err = playOut(sc.prefer); if (err) return err;
      tally();
      err = check("settled " + sc.name + " #" + i); if (err) return err;
    }
  }

  // Random rounds until we have 200+ completed hands/rounds
  var kinds = ["basic","split","surrender","bust","ins-yes"];
  var spun = 0;
  while (counts.rounds < 220 && spun < 400){
    spun++;
    if (SIM.bank < 200) SIM.bank += 1000;
    var prefer = kinds[spun % kinds.length];
    if (prefer === "split") forceDeal(["8","9","8","7", "4","5","2","3","10","6"]);
    else if (prefer === "surrender") forceDeal(["10","9","6","5"]);
    else if (prefer === "ins-yes") forceDeal(["10","A","7","8","2"]);
    else if (prefer === "bust") forceDeal(["10","10","6","4","K","Q"]);
    else {
      if (SIM.shoe.length < 60 || SIM.dealt >= CUT_CARDS){ SIM.shoe = buildShoe(); SIM.dealt = 0; SIM.rc = 0; }
      SIM.phase = "bet"; SIM.bet = 25; simDeal();
    }
    err = check("random deal " + spun); if (err) return err;
    err = playOut(prefer); if (err) return err;
    tally();
    err = check("random settled " + spun); if (err) return err;
  }

  if (counts.rounds < 200) return fail("only played " + counts.rounds + " rounds");
  if (counts.splits < 10) return fail("too few splits: " + counts.splits, counts);
  if (counts.surrenders < 10) return fail("too few surrenders: " + counts.surrenders, counts);
  if (counts.insurance < 10) return fail("too few insurance: " + counts.insurance, counts);
  if (counts.busts < 10) return fail("too few busts: " + counts.busts, counts);
  return { ok:true, counts:counts, final: snapshot() };
}
"""

def main():
    errs = []
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True, executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
        pg = b.new_page()
        pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto(URL, wait_until="networkidle")
        pg.evaluate("S.unlockAll=true; renderPath(); refreshStrip();")
        pg.click("#tab-sim")
        pg.wait_for_timeout(100)
        result = pg.evaluate(SCRIPT)
        b.close()
    print(result)
    if errs:
        print("console errors:", errs)
    if not result or not result.get("ok"):
        print("FAIL", result)
        sys.exit(1)
    print("PASS 200+ shoe invariant:", result["counts"], "final", result["final"])
    sys.exit(0)

if __name__ == "__main__":
    main()
