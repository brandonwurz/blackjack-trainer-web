# Blackjack Trainer v2 (index.html)
Original kept as original.html (not part of the repo).
- 8 decks everywhere (shoe 416 cards, true count over decks remaining of 8, scorer/lab defaults, copy). No deck selector.
- Rules toggle: S17/H17, DAS, late surrender. Default S17+DAS+LS. Charts, drills, coach, index plays follow it.
- Fixed: hard 11 vs A is HIT in 8-deck S17 (original doubled it); H17 doubles it.
- 16v9 surrenders at every count in LS games; no-LS uses stand at +5; 3-card 16v10 uses stand at 0.
- Soft 18 vs 3-6 stands when you cannot double; legend uses Ds, Rs, Rp.
- Progress saved in localStorage (key bjt:v2).
- Simulator: split equal ranks only, no surrender after split, insurance blocked if unaffordable, graded vs +3, hole card revealed and counted on bust/surrender.
- Missed-hand spaced-repetition review + accuracy by family (pairs, soft, hard 5-11, 12-16, 17-19, hard 20, surrender zone).
- Keyboard: H/S/D/P/R, N next, Y/N insurance, 1-5 chips, Enter, arrow keys on tabs.
- PWA: manifest, icons, service worker (offline), install button. System fonts (no Google Fonts).
- Coach true count whole-number; mobile tabs + chart scroll cue; copy nits; footer AA contrast.

## Shoe-count fix
The 418-cards / 8.1-decks reading in v2-hero-desktop-simulator-split.png was from the screenshot/test helper pushing scripted cards onto a full 416-card shoe (424 − 4 dealt − 2 split draws = 418; decks left then added the face-down hole card, (418+1)/52 = 8.1). Production play never grew the shoe. The helper now replaces the upcoming cards so the shoe stays 416. The display, true-count divisor, and cut-card check all use the real undealt shoe length (cards left = 416 − dealt; decks left never includes the hole card and never exceeds 8).

# v3 — counting drills, index trainer, speed run
Always 8 decks; the S17/H17, DAS and late-surrender toggle drives everything. Three new tabs (10 tabs total). All progress is saved in localStorage (key bjt:v2, new sections cnt / idx / spd; old saves load fine).

## Count Drills (tab "Count Drills")
- **Running count of a dealt sequence** at six selectable speeds (a card every 2 s, 1.5 s, 1 s, 0.7 s, 0.5 s, 0.35 s) and 10 / 20 / 30 / 52 cards. Enter the count with +/- (or the keyboard). The cards are listed with their Hi-Lo values afterwards.
- **Deck countdown against the clock:** a real shuffled 52-card deck, flip 1, 2 or 3 cards at a time (button, Space or right arrow). Clock starts on the first card; a clean deck ends on 0 and saves your best time per flip size.
- **Running to true count out of 8 decks:** given the running count plus either decks left or cards dealt (of 416), enter the rounded true count. Questions never land on an exact half; the explanation shows the division.
- **Accuracy tracking:** overall and per speed, clean-deck rate and best times, true-count accuracy per mode, and the fastest speed at which you counted 20+ cards cleanly. Stop button / Esc ends any drill.

## Index Trainer (tab "Index Trainer")
- Flashcards: dealer card, your hand and the whole-number true count; answer H/S/D/P/R (or take/decline insurance). Illustrious 18 (incl. insurance at +3) plus the Fab 4 surrenders.
- **Rules-aware:** S17 vs H17 (11 vs A: +1 / -1, 10 vs A: +4 / +3, 15 vs A: +1 / -1), late surrender on/off. With surrender offered, 16 vs 9/10 and 15 vs 10 stand indices are drilled on three-card hands (surrender is a first-two-cards option) and the Fab 4 appear; with no surrender the stand indices are drilled on two-card hands and the Fab 4 are not shown. DAS does not move any of these indices.
- **Spaced repetition on misses:** a missed card (index + true count) comes back after 2, then 5, 12, 30, 80 cards and leaves after five right in a row. "My missed cards only" mode. The queue is saved and is rule-aware (cards for another ruleset stay hidden until the rules match).
- Your index list table for the active rules, and accuracy by index.

## Speed Run (tab "Speed Run")
- Timed basic-strategy rounds: 30 s, 60 s or 2 min, graded on the active rules, with a per-decision speed target (3.0 / 2.0 / 1.5 / 1.0 s) and a live per-decision bar that turns red past the target.
- Score = +10 per right play, +5 more inside the target, -5 per miss. Result screen: score, hands, accuracy, average decision time, how many decisions beat the target.
- Saved on this device: best score, best accuracy (10+ hands), fastest average decision (10+ hands at 90%+), last 10 runs. Misses join the normal missed-hand review queue. Leaving the tab, cancelling or changing the rules cancels a run without saving it.

## Other
- Keyboard: H/S/D/P/R and Y/N in the new drills, N or Enter for next, Space / right arrow to flip a deck, + / - / arrows to set a count, Esc to stop.
- PWA: service worker cache bumped to bjt-v3-1 so installed copies update. Every manifest / service-worker / icon path is relative (start_url "./index.html", scope "./"), so it works under the /blackjack-trainer-web/ GitHub Pages subpath; tests/test_pwa_paths.py checks this locally under a subpath and against the live URL.
- Contrast: kbd hints on green buttons, locked cards and dark-mode buttons fixed to WCAG AA; axe reports zero A/AA violations on all 10 tabs in light and dark.

## Tests (tests/)
test_strategy.py, test_decide.py, test_shoe_invariant.py, test_flows.py, test_levels_pwa.py (axe, offline), test_features.py (new: index values vs an independently typed 6-8 deck reference for all 8 rule combos, 24,000 engine checks, count / index / speed flows at 390x844 and 1280x800 with a controlled clock), test_pwa_paths.py (new).
