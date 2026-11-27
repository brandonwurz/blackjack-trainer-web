# Blackjack Trainer v2 (index.html)
Original kept untouched as original.html. Not pushed or deployed.
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
