import json, itertools, sys
from playwright.sync_api import sync_playwright
URL = "http://127.0.0.1:8766/index.html"
UPS = ["2","3","4","5","6","7","8","9","10","A"]
def row(s):
    r = s.split(); assert len(r)==10, s; return r

# Independently typed Wizard of Odds total-dependent charts (S17, DAS, LS).
BASE = {
8: {
 "hard": {
  "5–8": row("H H H H H H H H H H"), "9": row("H D D D D H H H H H"), "10": row("D D D D D D D D H H"),
  "11": row("D D D D D D D D D H"), "12": row("H H S S S H H H H H"), "13": row("S S S S S H H H H H"),
  "14": row("S S S S S H H H H H"), "15": row("S S S S S H H H R H"), "16": row("S S S S S H H R R R"),
  "17": row("S S S S S S S S S S"), "18+": row("S S S S S S S S S S")},
 "soft": {
  "A-2": row("H H H D D H H H H H"), "A-3": row("H H H D D H H H H H"), "A-4": row("H H D D D H H H H H"),
  "A-5": row("H H D D D H H H H H"), "A-6": row("H D D D D H H H H H"), "A-7": row("S Ds Ds Ds Ds S S H H H"),
  "A-8": row("S S S S S S S S S S"), "A-9": row("S S S S S S S S S S")},
 "pair": {
  "2-2": row("P P P P P P H H H H"), "3-3": row("P P P P P P H H H H"), "4-4": row("H H H P P H H H H H"),
  "5-5": row("D D D D D D D D H H"), "6-6": row("P P P P P H H H H H"), "7-7": row("P P P P P P H H H H"),
  "8-8": row("P P P P P P P P P P"), "9-9": row("P P P P P S P P S S"), "10-10": row("S S S S S S S S S S"),
  "A-A": row("P P P P P P P P P P")}
},
2: {
 "hard": {
  "5–8": row("H H H H H H H H H H"), "9": row("D D D D D H H H H H"), "10": row("D D D D D D D D H H"),
  "11": row("D D D D D D D D D D"), "12": row("H H S S S H H H H H"), "13": row("S S S S S H H H H H"),
  "14": row("S S S S S H H H H H"), "15": row("S S S S S H H H R H"), "16": row("S S S S S H H H R R"),
  "17": row("S S S S S S S S S S"), "18+": row("S S S S S S S S S S")},
 "soft": {
  "A-2": row("H H H D D H H H H H"), "A-3": row("H H H D D H H H H H"), "A-4": row("H H D D D H H H H H"),
  "A-5": row("H H D D D H H H H H"), "A-6": row("H D D D D H H H H H"), "A-7": row("S Ds Ds Ds Ds S S H H H"),
  "A-8": row("S S S S S S S S S S"), "A-9": row("S S S S S S S S S S")},
 "pair": {
  "2-2": row("P P P P P P H H H H"), "3-3": row("P P P P P P H H H H"), "4-4": row("H H H P P H H H H H"),
  "5-5": row("D D D D D D D D H H"), "6-6": row("P P P P P P H H H H"), "7-7": row("P P P P P P P H H H"),
  "8-8": row("P P P P P P P P P P"), "9-9": row("P P P P P S P P S S"), "10-10": row("S S S S S S S S S S"),
  "A-A": row("P P P P P P P P P P")}
},
1: {
 "hard": {
  "5–7": row("H H H H H H H H H H"), "8": row("H H H D D H H H H H"), "9": row("D D D D D H H H H H"),
  "10": row("D D D D D D D D H H"), "11": row("D D D D D D D D D D"), "12": row("H H S S S H H H H H"),
  "13": row("S S S S S H H H H H"), "14": row("S S S S S H H H H H"), "15": row("S S S S S H H H H H"),
  "16": row("S S S S S H H H R R"), "17": row("S S S S S S S S S S"), "18+": row("S S S S S S S S S S")},
 "soft": {
  "A-2": row("H H D D D H H H H H"), "A-3": row("H H D D D H H H H H"), "A-4": row("H H D D D H H H H H"),
  "A-5": row("H H D D D H H H H H"), "A-6": row("D D D D D H H H H H"), "A-7": row("S Ds Ds Ds Ds S S H H S"),
  "A-8": row("S S S S Ds S S S S S"), "A-9": row("S S S S S S S S S S")},
 "pair": {
  "2-2": row("P P P P P P H H H H"), "3-3": row("P P P P P P P H H H"), "4-4": row("H H P P P H H H H H"),
  "5-5": row("D D D D D D D D H H"), "6-6": row("P P P P P P H H H H"), "7-7": row("P P P P P P P H Rs H"),
  "8-8": row("P P P P P P P P P P"), "9-9": row("P P P P P S P P S S"), "10-10": row("S S S S S S S S S S"),
  "A-A": row("P P P P P P P P P P")}
}}

def fam_of(decks):
    return 1 if decks <= 1 else 2 if decks == 2 else 8

def reference(decks, h17, das, ls):
    fam = fam_of(decks)
    g = json.loads(json.dumps(BASE[fam]))
    A = 9
    if h17:
        g["hard"]["11"][A] = "D"
        if ls:
            g["hard"]["15"][A] = "R"
            g["hard"]["17"][A] = "Rs"
            if fam != 1:
                g["pair"]["8-8"][A] = "Rp"
            else:
                g["pair"]["7-7"][A] = "R"
                g["pair"]["9-9"][A] = "P"
        elif fam == 1:
            g["pair"]["9-9"][A] = "P" if das else "S"
        if fam == 1:
            g["soft"]["A-7"][0] = "S"          # 1D H17: stand (not double) vs 2
            g["soft"]["A-7"][A] = "H"
        else:
            g["soft"]["A-7"][0] = "Ds"
            g["soft"]["A-8"][4] = "Ds"
            if fam == 2:
                g["soft"]["A-3"][2] = "D"      # 2D H17: A,3 vs 4 doubles
    if not ls:
        for k in g:
            for lab, cells in g[k].items():
                g[k][lab] = [{"R":"H","Rs":"S","Rp":"P"}.get(c,c) for c in cells]
    if not das:
        if fam == 1:
            g["pair"]["2-2"][0] = "H"
            g["pair"]["3-3"][0] = "H"; g["pair"]["3-3"][1] = "H"; g["pair"]["3-3"][6] = "H"
            g["pair"]["4-4"][2] = "H"; g["pair"]["4-4"][3] = "D"; g["pair"]["4-4"][4] = "D"
            g["pair"]["6-6"][5] = "H"
            g["pair"]["7-7"][6] = "H"
            if h17: g["pair"]["9-9"][A] = "S"
        elif fam == 2:
            for c in (0,1): g["pair"]["2-2"][c] = "H"; g["pair"]["3-3"][c] = "H"
            for c in (3,4): g["pair"]["4-4"][c] = "H"
            g["pair"]["6-6"][5] = "H"
            g["pair"]["7-7"][6] = "H"
        else:
            for c in (0,1): g["pair"]["2-2"][c] = "H"; g["pair"]["3-3"][c] = "H"
            for c in (3,4): g["pair"]["4-4"][c] = "H"
            g["pair"]["6-6"][0] = "H"
    return g

def val(r):
    if r=="A": return 11
    if r in ("10","J","Q","K"): return 10
    return int(r)

def hard_lab(t, fam):
    if fam == 1:
        if t <= 7: return "5–7"
        if t == 8: return "8"
    else:
        if t <= 8: return "5–8"
    if t >= 18: return "18+"
    return str(t)

bad = []; total_cells = 0; total_hands = 0
with sync_playwright() as p:
    b = p.chromium.launch(headless=True, executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
    pg = b.new_page(); errs=[]
    pg.on("console", lambda m: errs.append(m.text) if m.type=="error" else None); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(URL, wait_until="networkidle")
    for decks, h17, das, ls in itertools.product([1,2,4,6,8],[False,True],[True,False],[True,False]):
        rules = {"decks":decks,"h17":h17,"das":das,"ls":ls}
        fam = fam_of(decks)
        ref = reference(decks,h17,das,ls)
        got = pg.evaluate("(r)=>chartData(r)", rules)
        for kind in ("hard","soft","pair"):
            labs = [r["label"] for r in got[kind]]
            if labs != list(ref[kind].keys()):
                bad.append((rules, kind, "labels", labs, list(ref[kind].keys())))
            for r in got[kind]:
                if r["label"] not in ref[kind]:
                    bad.append((rules, kind, "extra-row", r["label"])); continue
                for i,(g,e) in enumerate(zip(r["cells"], ref[kind][r["label"]])):
                    total_cells += 1
                    if g != e: bad.append((rules, kind, r["label"], UPS[i], "app", g, "ref", e))
        hands = pg.evaluate("""(r)=>{var o=[];var R=["A","2","3","4","5","6","7","8","9","10","J","Q","K"];
          R.forEach(function(a){R.forEach(function(b){R.forEach(function(u){
            o.push([a,b,u,stratCode([{rank:a,suit:"♠"},{rank:b,suit:"♥"}],{rank:u,suit:"♦"},r,true)]);});});});return o;}""", rules)
        for a,bb,u,code in hands:
            total_hands += 1
            uv = val(u); col = 9 if uv==11 else uv-2
            if a==bb:
                lab = "A-A" if a=="A" else ("10-10" if val(a)==10 else f"{a}-{a}"); kind="pair"
            elif a=="A" or bb=="A":
                other = bb if a=="A" else a
                if val(other)==10: continue
                lab = f"A-{other}"; kind="soft"
            else:
                t = val(a)+val(bb); kind="hard"; lab = hard_lab(t, fam)
            exp = ref[kind][lab][col]
            if code != exp: bad.append((rules,"hand",a,bb,"vs",u,"app",code,"ref",exp))
    b.close()

print("cells", total_cells, "hands", total_hands, "combos", 5*8)
print("console errors:", errs)
if bad:
    print("MISMATCHES:", len(bad))
    for row in bad[:40]: print(" ", row)
    sys.exit(1)
print("MISMATCHES: 0")
