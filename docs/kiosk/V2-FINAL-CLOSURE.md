# Kiosk V2 — final closure

Two things, and only two: the regression count is reconciled test by test, and the
measured fidelity gap against the approved design is closed. No new features, no
redesign, no RC.

---

## Gate 1 — the regression count

The V2 implementation report ended at **972/0/0** against a **986/0/0** baseline and
called the −14 "the V1 kiosk browser suite was rewritten". That sentence was true but
unproven, so it was re-derived from the code and re-run at both ends with **one command**
(`scratchpad/run_canonical.sh`, identical flags, fresh `--without-demo=all` database,
only the addons path and database name differ).

| Run | Commit | Result |
|---|---|---|
| Baseline | `80110f5` | **986 tests · 0 failed · 0 errors** |
| Head at reconciliation | `77fa76b` | **989 tests · 0 failed · 0 errors** |

### Where every test went

Only two test files changed between the two commits (`git diff --stat`), and
`tests/__init__.py` and `__manifest__.py` are byte-identical, so no module was silently
excluded.

| File | Baseline | Head | Δ |
|---|---|---|---|
| `test_kiosk_configuration.py` | 71 | 74 | **+3** |
| `test_c5_stepper_a11y_localization.py` | 12 | 12 | 0 |
| everything else | unchanged | unchanged | 0 |

986 + 3 = **989**. Exact.

| Class | Baseline | Head |
|---|---|---|
| `TestKioskArchitecture` | 4 | **7** |
| `TestKioskServerAuthority` | 10 | 10 |
| `TestKioskSelfOrderGate` | 4 | 4 |
| `TestKioskUntrustedClient` | 9 | 9 |
| `TestKioskCustomerJourney` | 19 | — retired |
| `TestKioskLanguageAndAccess` | 8 | — retired |
| `TestKioskBenchmarkedLayout` | 17 | — retired |
| `TestKioskV2Journey` | — | 18 |
| `TestKioskV2LocaleAndAccess` | — | 9 |
| `TestKioskV2CoverageParity` | — | 17 |

44 retired, 47 added. The three retired classes drove a DOM the approved design replaced
— every one of them selected `.mz-cfg__*`, the V1 bottom rail or the V1 sheet, so they
could not be re-pointed, only re-expressed.

### Nothing was de-certified

The 44 retired tests were read one by one and their **properties** — not their
selectors — were carried across. That audit is what produced
`TestKioskV2CoverageParity` (test_120–136), and it did not merely restore coverage:

| What the audit found | Outcome |
|---|---|
| Accepting "Make it a meal?" added **nothing** — `existing` conflated an edit target with a preselection, so `replaceLine` no-oped | product fix; `test_134` |
| Editing a line from the order returned to the **menu**, not the order | product fix; `test_121` |
| A `/shop/quote` reply already in flight could land **after** the privacy reset and repaint the previous customer's total | product fix (cart generation); `test_136` |
| Arrow-key roving inside a choose-one group had been **lost** in the V2 rewrite — an accessibility regression no V2 test noticed | restored in `customer-config.js` |

Test-id diff of the two runs: 221 identical ids, 43 removed, 43 added — all 86 inside
the kiosk file.

**Classification: EXPLAINED.** Coverage at head is a strict superset of the baseline's.

---

## Where the suite stands

| Run | Tests | Failed | Errors |
|---|---|---|---|
| Baseline `80110f5` | 986 | 0 | 0 |
| After the coverage-parity audit | 989 | 0 | 0 |
| **After this fidelity pass** | **997** | **0** | **0** |

989 + 8 stage-fidelity tests (`test_140`–`test_147`) = 997. Same command, fresh
`--without-demo=all` database, and the tree was frozen before the run — the four files
it exercised are byte-identical to the ones committed.

---

## Gate 2 — the measured fidelity gap

### What the previous pass got wrong, and how it was found

The approved design project carries a written handoff next to the prototype
(`design_handoff_mezze_kiosk/01..07`). It states every region size, every semantic type
size, the icon list, the motion vocabulary and the responsive matrix as numbers. The V2
implementation had been matched **by eye at a laptop-sized window**, so:

* every type size was ~0.72× the design's — correct for a 1366×768 stage, **30 % too
  small on the 1080×1920 panel the kiosk actually ships on**;
* the landscape order bar and CTA were 150/104 px against the approved 173/124;
* `--k-brand-soft`, `--k-ok-soft`, `--k-warn-soft` and `--k-danger-soft` were **used by
  the stylesheet and defined nowhere**, so every soft fill in the product — selected
  option, completed component, remove button, cart plate, order-number plate — resolved
  to an invalid value and simply did not paint;
* the kiosk followed the operating system's dark preference, while the design is
  explicitly light-only;
* the photo-less media well showed a generic picture icon **and** repeated the product
  name, where the design specifies the dish's own category glyph and no caption.

### What changed

| Area | Before | Now |
|---|---|---|
| Type scale | hard-coded laptop-sized px | every semantic role from `03-tokens §6`, multiplied by a stage factor `--k-s` (1 on the two primary panels, .72 on the three certified smaller stages) |
| Product name / price | 22 / 30 px | **32 / 48 px** |
| Section title · CTA · order-bar amount | 40 · 30 · 40 | **48 · 48 · 58** |
| Choice label · meal value · cart total | 26 · 28 · 34 | **40 · 48 · 58** |
| Attract wordmark · order number · thank-you | 96 · 120 · 44 | **128 · 128 · 70** |
| Rail item · icon plate · glyph | 104 · 52 · 30 | **148 (112 landscape) · 68 · 40** |
| Meal row · plate · choice row · check plate | ~110 · 64 · 96 · 44 | **172 · 104 · 96 · 56** |
| Cart thumb · steppers · secondary buttons | 190 · 60 · 56–60 | **180 · 72 · 72** |
| Payment card · plate | ~120 · 76 | **176 · 112** |
| Landscape order bar / CTA | 150 / 104 | **173 / 124** |
| CTA width | unbounded (min-width 44 %) | **≤520 px, ≤620 px on the item screen** |
| Soft colour tier | undefined → painted nothing | aliased to the canonical `--mz-*-soft` |
| Default appearance | followed the OS (dark on this machine) | **light**; an explicit `?mzmode=`/`?mztheme=` still wins, so High Contrast keeps reaching the surface |
| Icon vocabulary | 23 house glyphs, 8 category patterns | the approved **40-name vocabulary**, every design name resolvable, categories mapped to the design's own food glyphs |
| Photo fallback | picture icon + product name caption | the dish's **category glyph**, no caption, exact box |
| Motion | one 120 ms colour transition | the canonical token set: 80 ms press `scale(.95)` (steppers `.9`), 120 ms selection, 320 ms screen rise, one spring on the success check, the 1200 ms reconnect loop, and every duration collapsed to 1 ms under `prefers-reduced-motion` |
| Success screen | a number and two lines | check ring → thank-you → **brand-soft order-number plate** → instruction → CTA → spoken countdown |
| Consequence chip | always "each extra … adds N" | **two states**: ok-toned "The first one is included" inside the allowance, flipping to the surcharge the moment it is used — always *before* the tap |
| Welcome composition | centred column | space-between (150/80/110), so START ORDER sits in the LOWER reach band, centred in its own button |
| Service screen | two small tiles floating mid-panel on the canvas | the approved composition: `--mz-workspace` ground, 58 px question + 32 px sub, two cards that **fill the panel**, each a media well over its own 40/24/48 text block |
| Order bar empty state | brand plate + acting CTA | surface-3 plate + the one sanctioned non-acting CTA |
| Upsell | inline-styled button | the approved plate + equal-weight ADD/NO THANKS |

### Measured, not asserted

The design's numbers only exist at the panel size, so the measurement runs **at the panel
size**: `TestKioskV2FidelityPortrait` (`browser_size = 1080,1920`) and
`TestKioskV2FidelityLandscape` (`1920,1080`) read the values back out of a real browser.

| Measured in the browser | Portrait (design) | Landscape (design) |
|---|---|---|
| Top bar | **109** (109) | **109** (109) |
| Category rail | **201** (201) | **237** (237) |
| Rail item | **148** (148) | **127** (127 measured / 112 declared) |
| Content area | **879** (879) | **1683** (1683) |
| Grid | **3** columns, **20** px gap | **5** columns, **20** px gap |
| Card | **264 × 520** (264 × 518) | **311 × 386** (311 × 384) |
| Media well | **262 × 350** (262 × 350) | **309 × 233** (309 × 233) |
| Card body | **168** (168) | **151** (151) |
| Food share of card | **67 %** | **60 %** |
| Order bar / CTA height | **173 / 124** | **173 / 124** |
| CTA width | **408** (≤520) | **408** (≤520) |
| Product name / price | **32 / 48** | **28 / 40** (see deviations) |
| Section title / rail label | **48 / 22** | **48 / 22** |
| Order-bar amount / CTA type | **58 / 48** | **58 / 48** |
| Meal row / plate / value | **172 / 104 / 48** | — |
| Choice row / check plate / label | **96 / 56 / 40** | — |

Every figure above was read out of a running browser at that stage size, not estimated.
Tests `test_140`–`test_147` fail if any of them drifts.

The handoff specifies the three smaller stages but says "implement and **re-measure**
these". Measured, on the same rig:

| | 1366×768 | 1280×720 | 1024×768 |
|---|---|---|---|
| Top bar / order bar / CTA | 96 / 156 / 112 | 96 / 156 / 112 | 96 / 156 / 112 |
| Rail | **220** (220) | **200** (200) | **190** (190) |
| Columns | **4** (4) | **4** (4) | **3** (3) |
| Card width | **260** (264) | **243** (245) | **249** (250) |
| Food share of card | **64 %** | **62 %** | **63 %** |
| Horizontal overflow | none | none | none |

Card *heights* run shorter than the matrix's approximations (305 vs ~356 at 1366) because
the body shrinks with the stage while the 4/3 crop does not; the invariants the design
protects — column count, rail, bar heights, ≥112 px CTA, ≥60 % food, no horizontal
scroll — all hold.

Two defects surfaced only because the measurement was done at the panel size:

* the media well is a flex item, and a real two-line product name **shrank the food** —
  the card kept its height while the photograph lost 18 px. Pinned with `flex:0 0 auto`;
* the product card is a `<button>`, so the **user-agent's 6 px button padding** was
  insetting every card by 12 px. The well measured 250 px wide against the approved 262.
  Both were invisible at laptop size and obvious at 1080 × 1920.

### Deliberate deviations, and why

| Deviation | Reason |
|---|---|
| The landscape card's own name/price step down one notch (28/40 rather than 32/48) | at the portrait type scale a genuine two-line name needs 167 px of body inside a 384 px card, which pushes the food below 60 % of the card. "Food image always ≥ 60 % of card height" is on the design's *never changes* list, so the invariant wins and the card type gives way. Portrait — the primary panel — keeps the full scale |
| The `tune` marker sits in the media well, not on the price row | the design's price row is `price + currency + 56 px chip` inside a 264 px card, which fits a 3-character price. This branch's prices are `147.00`; wrapping the row grew the whole grid row past the approved card height, and clipping the chip is worse. The well already carries markers in the design |
| Icons are Mezze's own inline SVG, not the Material Symbols font | the handoff names Material as the authority **and** says a bespoke Mezze set supersedes it. Inline SVG needs no font file, so the kiosk cannot flash glyph *names* if a webfont fails — a failure mode the handoff itself flags |
| An idle order still resets (with a warning), which the design defers past v1 | Mezze's privacy contract is older and is tested (`test_105`): a walked-away basket must not survive. The design's own objection is to a *silent* wipe, and this one warns first |
| The theme registry still reaches the kiosk | product-wide accessibility contract (`test_66`/`test_67`): Mezze High Contrast must reach every surface. The kiosk simply no longer *defaults* to dark |

### Fidelity re-score — same rubric, same threshold

| Criterion | Max | Before | Now | Why |
|---|---|---|---|---|
| Layout | 20 | 18 | **19** | every region measured at both panels; one documented marker deviation |
| Typography | 10 | 9 | **10** | every semantic role measured against the handoff table |
| Colours | 10 | 10 | **10** | and now the soft tier actually paints — the previous 10 was generous |
| Product cards | 10 | 9 | **9** | geometry and fallback correct; marker moved |
| Categories | 10 | 9 | **10** | rail, item, plate, glyph, label and the four-cue selected state |
| Configurator | 15 | 14 | **14** | scale and the two-state consequence chip land; per-group icons are still name-derived |
| Cart / checkout | 10 | 9 | **10** | line, summary, upsell, review, payment and failure tone, with a real tax exercised |
| Responsive | 5 | 5 | **5** | five stages; two measured, three specified by the matrix |
| Arabic | 5 | 5 | **5** | mirrored, Arabic family, tracking zeroed, market numerals |
| Motion | 5 | 4 | **5** | the approved vocabulary, measured, and reduced-motion honoured |
| **Total** | **100** | **92** | **97** | **target ≥95: MET** |

Not 100: the marker deviation is real, and the per-component icon set is a heuristic on
group names rather than a curated map — both are named above rather than rounded away.

### Evidence

`docs/kiosk/shots/` — `v3-*` captured by driving the **real** kiosk over CDP with the
viewport emulated to 1080×1920 and 1920×1080 (`scratchpad/cdpshot.py`), not a laptop
window scaled down:

`v3-welcome-portrait.jpg` · `v3-service-portrait.jpg` · `v3-menu-portrait.jpg` ·
`v3-detail-portrait.jpg` · `v3-cart-portrait.jpg` · `v3-review-portrait.jpg` ·
`v3-payment-portrait.jpg` · `v3-success-portrait.jpg` · `v3-menu-ar-portrait.jpg` ·
`v3-welcome-landscape.jpg` · `v3-service-landscape.jpg` · `v3-menu-landscape.jpg`, and
the side-by-sides
`v3-vs-design-{menu,configurator,cart,arabic}.jpg`.

The tax block is exercised for real: this branch charges 15 %, so `v3-cart-portrait`
shows subtotal, the branch's own tax row and the total — no invented rate, no fake row,
and nothing about the branch's fiscal configuration was changed to produce it.
