import sys
from playwright.sync_api import sync_playwright
URL = "http://127.0.0.1:8766/index.html"
def C(*r): return [{"rank":x,"suit":"♠"} for x in r]
S17={"h17":False,"das":True,"ls":True}; H17={"h17":True,"das":True,"ls":True}
S17NL={"h17":False,"das":True,"ls":False}; H17NL={"h17":True,"das":True,"ls":False}
FULL={"canDouble":True,"canSplit":True,"canSurrender":True}
NOSUR={"canDouble":True,"canSplit":True,"canSurrender":False}
NODBL={"canDouble":False,"canSplit":False,"canSurrender":False}
def ctxf(r): return dict(FULL, canSurrender=r["ls"])
cases = [
 # (name, cards, up, tc, rules, ctx, expected play)
 ("16v9 LS TC-3 surrender", C("10","6"),"9",-3,S17,FULL,"R"),
 ("16v9 LS TC0 surrender",  C("10","6"),"9",0,S17,FULL,"R"),
 ("16v9 LS TC5 surrender",  C("10","6"),"9",5,S17,FULL,"R"),
 ("16v9 LS TC6 surrender",  C("10","6"),"9",6,S17,FULL,"R"),
 ("16v9 noLS TC4 hit",      C("10","6"),"9",4,S17NL,ctxf(S17NL),"H"),
 ("16v9 noLS TC5 stand",    C("10","6"),"9",5,S17NL,ctxf(S17NL),"S"),
 ("16v10 LS TC-5 surrender",C("10","6"),"10",-5,S17,FULL,"R"),
 ("16v10 LS TC5 surrender", C("10","6"),"10",5,S17,FULL,"R"),
 ("16v10 noLS TC-1 hit",    C("10","6"),"10",-1,S17NL,ctxf(S17NL),"H"),
 ("16v10 noLS TC0 stand",   C("10","6"),"10",0,S17NL,ctxf(S17NL),"S"),
 ("3-card 16v10 LS TC-1 hit", C("10","4","2"),"10",-1,S17,NOSUR,"H"),
 ("3-card 16v10 LS TC0 stand",C("10","4","2"),"10",0,S17,NOSUR,"S"),
 ("3-card 16v9 LS TC0 hit",   C("10","4","2"),"9",0,S17,NOSUR,"H"),
 ("15v10 LS TC-1 hit (Fab4)", C("10","5"),"10",-1,S17,FULL,"H"),
 ("15v10 LS TC0 surrender",   C("10","5"),"10",0,S17,FULL,"R"),
 ("15v9 LS TC1 hit",   C("10","5"),"9",1,S17,FULL,"H"),
 ("15v9 LS TC2 surr",  C("10","5"),"9",2,S17,FULL,"R"),
 ("11vA S17 TC0 HIT",  C("6","5"),"A",0,S17,FULL,"H"),
 ("11vA S17 TC-3 HIT", C("6","5"),"A",-3,S17,FULL,"H"),
 ("11vA S17 TC1 double",C("6","5"),"A",1,S17,FULL,"D"),
 ("11vA S17 noDouble TC3 hit",C("6","5"),"A",3,S17,NODBL,"H"),
 ("11vA H17 TC0 double",C("6","5"),"A",0,H17,FULL,"D"),
 ("11vA H17 TC-1 double",C("6","5"),"A",-1,H17,FULL,"D"),
 ("11vA H17 TC-2 hit", C("6","5"),"A",-2,H17,FULL,"H"),
 ("10vA S17 TC3 hit",  C("6","4"),"A",3,S17,FULL,"H"),
 ("10vA S17 TC4 double",C("6","4"),"A",4,S17,FULL,"D"),
 ("10vA H17 TC3 double",C("6","4"),"A",3,H17,FULL,"D"),
 ("10vA H17 TC2 hit",  C("6","4"),"A",2,H17,FULL,"H"),
 ("15vA S17 LS TC0 hit",C("10","5"),"A",0,S17,FULL,"H"),
 ("15vA S17 LS TC1 surrender",C("10","5"),"A",1,S17,FULL,"R"),
 ("15vA H17 LS TC0 surrender",C("10","5"),"A",0,H17,FULL,"R"),
 ("15vA H17 LS TC-2 hit", C("10","5"),"A",-2,H17,FULL,"H"),
 ("17vA H17 LS surrender", C("10","7"),"A",0,H17,FULL,"R"),
 ("17vA H17 noLS stand",   C("10","7"),"A",0,H17NL,ctxf(H17NL),"S"),
 ("17vA S17 LS stand",     C("10","7"),"A",0,S17,FULL,"S"),
 ("8-8vA H17 LS surrender",C("8","8"),"A",0,H17,FULL,"R"),
 ("8-8vA S17 LS split",    C("8","8"),"A",0,S17,FULL,"P"),
 ("A-7 v2 S17 stand",      C("A","7"),"2",0,S17,FULL,"S"),
 ("A-7 v2 H17 double",     C("A","7"),"2",0,H17,FULL,"D"),
 ("A-7 v2 H17 no dbl stand",C("A","7"),"2",0,H17,NODBL,"S"),
 ("A-8 v6 S17 stand",      C("A","8"),"6",0,S17,FULL,"S"),
 ("A-8 v6 H17 double",     C("A","8"),"6",0,H17,FULL,"D"),
 ("soft18 (A,3,4) v3 no-dbl stand", C("A","3","4"),"3",0,S17,NODBL,"S"),
 ("soft18 (A,3,4) v6 no-dbl stand", C("A","3","4"),"6",0,S17,NODBL,"S"),
 ("soft18 (A,3,4) v2 no-dbl stand", C("A","3","4"),"2",0,S17,NODBL,"S"),
 ("soft18 (A,3,4) v9 hit",          C("A","3","4"),"9",0,S17,NODBL,"H"),
 ("A-7 v4 with double",    C("A","7"),"4",0,S17,FULL,"D"),
 ("10-10 v5 TC4 stand",    C("10","10"),"5",4,S17,FULL,"S"),
 ("10-10 v5 TC5 split",    C("10","10"),"5",5,S17,FULL,"P"),
 ("10-10 v6 TC3 stand",    C("10","10"),"6",3,S17,FULL,"S"),
 ("10-10 v6 TC4 split",    C("10","10"),"6",4,S17,FULL,"P"),
 ("K-Q v6 TC9 stand (not a pair)", C("K","Q"),"6",9,S17,FULL,"P") ,
 ("12v3 TC2 stand",  C("10","2"),"3",2,S17,FULL,"S"),
 ("12v3 TC1 hit",    C("10","2"),"3",1,S17,FULL,"H"),
 ("12v2 TC3 stand",  C("10","2"),"2",3,S17,FULL,"S"),
 ("12v4 TC0 stand",  C("10","2"),"4",0,S17,FULL,"S"),
 ("12v4 TC-1 hit",   C("10","2"),"4",-1,S17,FULL,"H"),
 ("13v2 TC-2 hit",   C("10","3"),"2",-2,S17,FULL,"H"),("13v2 TC-1 stand (index -1)", C("10","3"),"2",-1,S17,FULL,"S"),
 ("13v2 TC0 stand",  C("10","3"),"2",0,S17,FULL,"S"),
 ("9v2 TC1 double",  C("5","4"),"2",1,S17,FULL,"D"),
 ("9v7 TC3 double",  C("5","4"),"7",3,S17,FULL,"D"),
 ("10v10 TC4 double",C("6","4"),"10",4,S17,FULL,"D"),
 ("10v10 TC3 hit",   C("6","4"),"10",3,S17,FULL,"H"),
 ("14v10 LS TC (nonsurr) 14 stand?",C("10","4"),"10",0,S17,FULL,"H"),
]
# K-Q is a 10-10 pair (any two ten-value cards). At TC 9 vs 6 the I18 index is split.
cases[[c[0] for c in cases].index("K-Q v6 TC9 stand (not a pair)")] = ("K-Q v6 TC9 split (ten pair)", C("K","Q"),"6",9,S17,FULL,"P")
fail=0
with sync_playwright() as p:
    b = p.chromium.launch(headless=True, executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
    pg = b.new_page(); errs=[]
    pg.on("console", lambda m: errs.append(m.text) if m.type=="error" else None); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(URL, wait_until="networkidle")
    for name,cards,up,tc,rules,ctx,exp in cases:
        r = pg.evaluate("([c,u,tc,ru,cx])=>decide(c,{rank:u,suit:'♦'},tc,ru,cx)", [cards,up,tc,rules,ctx])
        ok = r["play"]==exp
        if not ok: fail+=1
        print(("PASS " if ok else "FAIL "), name, "->", r["play"], ("(expected "+exp+")" if not ok else ""))
    for tc,exp in [(2,False),(3,True),(4,True),(-1,False)]:
        got = pg.evaluate("(t)=>insuranceCorrect(t)", tc)
        ok = got==exp; fail += (not ok); print("PASS " if ok else "FAIL ","insurance TC",tc,"->",got)
    # pair detection
    for a,bb,exp in [("10","K",True),("K","K",True),("J","Q",True),("8","8",True),("10","9",False)]:
        got = pg.evaluate("([a,b])=>handValue([{rank:a,suit:'♠'},{rank:b,suit:'♥'}]).pair",[a,bb])
        ok = got==exp; fail += (not ok); print("PASS " if ok else "FAIL ","pair",a,bb,"->",got)
    print("console errors:", errs)
    b.close()
print("FAILS:", fail)
sys.exit(1 if fail or errs else 0)
