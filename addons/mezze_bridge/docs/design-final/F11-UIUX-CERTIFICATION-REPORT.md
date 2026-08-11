# MEZZE — FINAL UI/UX CERTIFICATION REPORT

**Branch:** `design/v1-uiux-completion`
**Start Commit:** `2a8fcb6`
**Final Commit:** `3f70465`
**Program:** F1–F11 Final UI/UX Convergence & Certification
**Evidence:** `F1-PRODUCTION-SURFACE-INVENTORY.md`, `F2-NAVIGATION-ROLE-IA-AUDIT.md`,
`F4-F9-EVIDENCE.md`, `F5-ARABIC-COVERAGE-GAP.md`

P3A COMPLETE · P3B COMPLETE · P3C COMPLETE · P3D COMPLETE · P3E COMPLETE
P3F COMPLETE · P3G COMPLETE · P3H COMPLETE · P3I COMPLETE

---

## PRODUCTION SURFACES

**Total:** 17 production UI surfaces (11 staff incl. 3 in-app workspaces + dialogs, 6 customer),
rendered by 12 documents (3 Owl apps + 1 QWeb page + 8 static HTML).
**Browser observed:** 12 / 12 documents.
**Unobserved:** 0.
`/mezze/design/pos` is **NOT PRODUCTION** (visual reference prototype) and is excluded from
every score below.

---

## NAVIGATION / IA

**Roles audited:** cashier, host, waiter/server, kitchen, manager, customer.

**Navigation systems:** 2 drifted per-app copies → **1 canonical family** in
`design/components.css` (shell + nav). The app shell had drifted across 6 of 8 classes
between the two staff workspaces (topbar `rgb(42,37,29)` vs `rgb(51,45,35)`, padding 12/20
vs 8/16, logo 20px vs 18px), so Floor↔Register visibly jumped. One source now.

**Destination set:** Floor exposed 2, Register exposed 4 → **both expose the same 4**
(Floor · Register · Orders · Reservations) in the same order, with Orders/Reservations
reached by a `?view=` deep link handled once after a successful boot.

**Dead Destinations:** 0
**Unauthorized Destinations Exposed:** 0
**Prototype-only Destinations Exposed:** 0

**KDS is deliberately excluded from workspace navigation** — kitchen staff get no financial
nav clutter, and KDS runs on a dedicated always-on display, not a device that roams between
workspaces. Recorded as a product decision, not a defect.

**No role-based nav filtering was introduced.** Every production page is `auth='user'` with
no group gate; the only role distinction that exists is Odoo's native
`point_of_sale.group_pos_user` / `group_pos_manager`. Hiding items would have *replaced*
access rules rather than reflected them.

**Navigation Verdict: PASS**

---

## RESPONSIVE MATRIX

Real CSS viewports (same-origin iframe harness; `window.innerWidth` reports the target and
media queries evaluate against it — `resize_window` does **not** change the top-level
viewport in this environment and was not used). See `F4-F9-EVIDENCE.md` §method.

| Width | Result |
|---|---|
| 360 | PASS — shop, QR, feedback (3/3 applicable) |
| 390 | PASS — shop, QR, feedback (3/3) |
| 430 | PASS — shop, QR, feedback (3/3) |
| 768 | PASS — Register, Floor, shop, QR, feedback, kiosk, courses, drive-thru, onboarding (9/9) |
| 1024 | PASS — Register, Floor, KDS, kiosk, CFD, courses, drive-thru, onboarding (8/8) |
| 1280 | PASS — Register, Floor, KDS, kiosk, CFD, courses, drive-thru, onboarding (8/8) |
| 1440 | PASS — Register, Floor, KDS (3/3) |

**Required Applicable Viewports Tested: 37 / 37** (+24 bilingual cases added by FINAL-C4:
courses / drive-thru × EN / AR × 360 · 390 · 430 · 768 · 1024 · 1280)
**Page-Level Horizontal Overflow Defects: 0**
Touch defects found and fixed: drive-thru "+ New car" 104×40 (F6); the drive-thru lane-card
`.act` family — `39×40`, `39×40`, `41×42` and the dismiss control at **27×40** — plus the
courses header control at 41×41 (FINAL-C4). All ≥44px.

**Responsive Verdict: PASS** — with the declared limit that this proves CSS-viewport
behaviour, not device pixel ratio or physical touch hardware.

---

## ARABIC / RTL

**Production Surfaces Tested: 11 / 11**

**Arabic Font: PASS** — every surface computes `IBM Plex Sans Arabic`. Two surfaces
(kiosk, onboarding) were requesting the **non-existent** family `'IBM Plex Arabic'` and
silently falling back to a Latin face; three further fallbacks (canonical field labels,
the legacy customer `.btn`, page-local `<button>`s) were found and fixed.

**RTL Layout: PASS** — mirrored shell, logical spacing, amount/currency placement, LTR
isolation on reference/PIN/amount inputs and phone cells.

**Mixed Bidi: PASS** — the cashier keyboard legend was reordering in RTL; now isolated.

**Directional Icons: PASS** — `U+2190/U+2192` are not Unicode-mirrored, so back arrows
pointed the wrong way in RTL; now mirrored via `.mz-dirglyph`, applied **only** to glyphs
whose meaning genuinely reverses. Quantity `+/-` and currency are deliberately not mirrored.

**Arabic Verdict: PASS** *(was CONDITIONAL at first certification)*.

At first certification the Owl staff UI measured 26 % translated and an Arabic cashier saw a
mixed interface. **FINAL-C2 closed this.** Re-auditing HEAD showed the true denominator is
**367** strings (the first count scanned templates only and missed `_t()` in JS):
**108 → 364 translated = 100 % of translatable strings**, with **3 kept in Latin by design**
(`Mezze`, `QR`, `VIP`). Terminology is governed by `ARABIC-TERMINOLOGY-GLOSSARY.md`;
`Register` is now **نقطة البيع** (the selling workspace) and الكاشير is reserved for the
cashier *person*. 0 placeholder mismatches, 0 unexplained terminology conflicts, and 0
unexplained English UI copy on any of the seven staff surfaces, verified in the browser.
Detail: `FINAL-C2-ARABIC-TRANSLATION-CLOSURE.md`.

**FINAL-C4** then closed the last gap on this axis: `courses.html` (the waiter's meal-coursing
board) and `drivethru.html` (the operator lane board) shipped English-only. Both are now
bilingual on the localisation contract `onboarding.html` already used — **51 / 51 keys paired,
0 orphans, 0 undefined references** — proven in the browser at 24 responsive cases and 16
theme cases, including runtime-translated JS strings and localised accessible names.
Detail: `FINAL-C4-OPERATOR-BOARD-LOCALIZATION.md`.

**FINAL-C5.1** closed the storefront's document-semantics gap: `shop.html` re-declares
`dir` alongside `lang` on a live language switch, so declared and painted direction now
agree in every state (verified EN→AR→EN→AR, 4/4, with price strings byte-identical — no
bidi reordering). Detail: `FINAL-C5.1-SEMANTICS-MOTION-EVIDENCE.md`.

**Human native-speaker wording review: NOT PERFORMED** — this remains an open condition.

---

## ACCESSIBILITY

**Keyboard: PASS** — all interactive controls reachable, 0 positive `tabindex`, no traps
observed; the Floor workspace had **no `:focus-visible` rule at all** and now inherits the
canonical one.
**Focus: PASS** — visible ring on every surface; opening a dialog transfers focus inside it
(verified live on "Assign table").
**Dialogs: PASS** — 11 / 11 production dialogs carry `role="dialog"` + an accessible name +
`aria-modal="true"` (6 cashier dialogs were missing `aria-modal`).
**Forms: PASS** — 0 controls without a programmatic label.
**Status/Alerts: PASS** — canonical `.mz-status` / `.mz-alert`; `role=status` / `role=alert`
+ `aria-live` on loading and error states; `aria-busy` on loading.
**ARIA: PASS** — `aria-pressed` on filters/segments, `aria-current="page"` on navigation
(never `role=tab`), no status wearing `aria-pressed`.
**Screen-Reader Semantic Audit: PASS** (browser-measured structure).
**Real Screen-Reader Walkthrough: NOT TESTED** — no screen reader available in this
environment. Reported separately, never merged into the semantic result.

**Smallest Frequent Touch Target: 36px** — the canonical `.mz-btn--sm` secondary/inline
variant ("Add customer"). Every primary, money, navigation, category, stepper, table,
reservation and KDS action measures **≥44px**. Two sub-44 defects were found and fixed
(payment "Back to order" 99×29, drive-thru "+ New car" 104×40).

**Color-Only Critical States: 0** — status carries text + `data-state`; not-tested is dashed;
reserved tables are dashed **and** labelled; selection adds weight and an inset ring;
connectivity carries a text label.

**Accessible Names: PASS** *(closed by FINAL-C5)*. The quantity steppers are icon controls
(`−` / `+`), so an `aria-label` carries their action name — and on `shop.html`, `qr.html`
and `kiosk.html` that label was hardcoded English on an otherwise Arabic page. All **9**
sites (across several dynamic generation paths, not one literal per file) now build the
name from each page's dictionary, reusing the pair C4 shipped on the operator boards.
Verified by DOM **and** by the computed accessibility tree over CDP
(`Accessibility.queryAXTree`, `role=button`): 0 wrong-language AX names, 0 empty AX names,
0 stale names across live EN→AR→EN switches. A pre-existing kiosk bug was found in the
process — the review sheet was never re-rendered on a language switch, so the order lines
kept the previous language. Detail:
`FINAL-C5-CUSTOMER-STEPPER-A11Y-LOCALIZATION.md`.

**Computed browser accessibility-name verification: PASS.**
**Real screen-reader walkthrough: NOT TESTED** — the AX tree is what the browser exposes to
assistive technology; it is not a screen reader, and no such claim is made.

**Reduced Motion: PASS** *(runtime-verified by FINAL-C5.1, previously "not exercised")*.
CDP media emulation drives `prefers-reduced-motion`; both states are proved with
`matchMedia` before measurement. Under `reduce`: **0 continuous animations survive** across
storefront, kiosk and KDS (every rendered element swept, not a known-class list); the
spinner stops but keeps a visible static arc; the KDS LATE meaning survives on border and
text; dialogs, toasts, chips and nav transitions are neutralised. No CSS was needed.

**Accessibility Verdict: CONDITIONAL** — structural/browser accessibility is proven,
including computed accessible names and runtime-verified reduced motion; the real
screen-reader walkthrough is not.

---

## THEMES

**Light: PASS** · **Dark: PASS** · **Mezze High Contrast: PASS on 11 of 11 surfaces**
*(9/11 at first certification; closed to 11/11 by FINAL-C1 — see `FINAL-C1-HIGH-CONTRAST-CLOSURE.md`)*

Measured on the live payment screen in all four theme states — **0 pairs below WCAG AA**.
Before this program the workspace navigation measured **1.19 / 1.37 / 1.02** against AA's
4.5 (the UA `buttonface` background leaking through a `<button>` nav item under themed
text). Fixed.

**forced-colors: PASS** *(was NOT SUPPORTED)* · **prefers-contrast: PASS** *(was NOT SUPPORTED)*
— closed by **FINAL-C3**. The user agent's palette owns colour (`forced-color-adjust` stays
`auto`; **0** opt-outs product-wide); only meaning the forced palette erases is restored —
selection via `Highlight`/`HighlightText`, focus via `CanvasText` outlines, and real borders
where an edge was previously only a shadow. `prefers-contrast` has three distinct branches
(`more` strengthens separation, `less` only removes decorative depth, the unqualified branch
never changes contrast because it also reaches `less` users), each verified with CDP media
emulation and `matchMedia`. Neither is the same thing as Mezze's own High-Contrast theme,
which is unchanged and still 11/11. Detail: `FINAL-C3-CONTRAST-PREFERENCES-CLOSURE.md`.

**Lowest Important Measured Contrast: 5.09:1** — current navigation item, 14px/800, light
themes (AA requires 4.5).

**Themes Verdict: PASS** *(was CONDITIONAL at first certification)*.

At first certification `kiosk.html` and `onboarding.html` were off the theme registry:
they shipped their own local light/dark palettes, and forcing `data-mz-theme=highcontrast`
changed **nothing** on them (measured: background unchanged, while `shop.html` correctly
went to pure black). **FINAL-C1 closed this.** Both surfaces now load the canonical registry
and consume its semantic tokens; High Contrast is measurably active on both (kiosk and
onboarding HC canvas `rgb(0,0,0)` / `rgb(255,255,255)` with pure-white / pure-black borders),
Light and Dark remain distinct, and no page-specific High-Contrast CSS was introduced.
Detail: `FINAL-C1-HIGH-CONTRAST-CLOSURE.md`.

---

## MOTION

**Reduced Motion: PASS** — **0 continuous animations remain** under
`prefers-reduced-motion: reduce`.

P3H had only *slowed* the spinner to 2400ms, which is still continuous rotation. Per the F8
instruction this was re-evaluated: both `.mz-spinner` and `.mz-kds-spinner` now **stop** and
render a static but unmistakable loading arc — the indication is never removed, and every
loading state also carries its own text plus `aria-busy`. The KDS spinner previously had no
reduced-motion branch of its own at all.

**Continuous Motion Remaining: 0.** No decorative infinite pulse; spring behaviour stays
confined to the established payment-completion moment.

Verified from the **served** stylesheet via CSSOM. The environment reports
`prefers-reduced-motion: no-preference` and offers no emulation, so the **runtime toggle
itself was not exercised** — declared, not implied.

**Motion Verdict: PASS**

---

## DESIGN SYSTEM

| Family | Systems |
|---|---|
| Buttons | 1 canonical |
| Status | 1 canonical |
| Badge | 1 canonical |
| Alerts | 1 canonical |
| Inputs | 1 canonical |
| Quantity | 1 canonical |
| Dialogs | 1 canonical |
| Cards | 1 canonical foundation |
| List Rows | 1 canonical foundation |
| Empty/Loading | 1 canonical foundation |
| Filters/Segmented | 1 canonical foundation |
| **Navigation** | **1 canonical (was 2 drifted copies — new in F3)** |

**Unexplained Production Component Systems: 0**
**Unexplained Hardcoded Palettes: 0**
Residual page-local vocabularies (kiosk `.svcbtn`, qr `.cartbtn`/`.x`, shop/courses/drivethru
`.sx`/`.x`, feedback/courses/drivethru `.btn`/`.ghost`/`.act`, drivethru `.newbtn`) are
enumerated with rationale in `F4-F9-EVIDENCE.md` §F9 — explained, not unexplained.

**Typography:** Hanken Grotesk (Latin) / IBM Plex Sans Arabic (Arabic) / JetBrains Mono +
`tabular-nums` for money — measured across all 11 surfaces, **zero** Arial / system-ui /
Roboto / misspelled-family leakage.

**Design System Coherence: 96 %**

---

## PRODUCT UX SCORES

| Dimension | Score | Verdict |
|---|---|---|
| Design System Coherence | 96 | PASS |
| Cross-Screen Consistency | 94 | PASS |
| Cashier UX | 92 | PASS |
| KDS UX | 93 | PASS |
| Floor UX | 90 | PASS |
| Orders UX | 90 | PASS |
| Reservations / Waitlist UX | 89 | PASS |
| Customer Ordering UX | 88 | PASS |
| Operator boards (Coursing / Drive-thru) | 92 | PASS *(FINAL-C4: bilingual + touch)* |
| Navigation / IA | 90 | PASS |
| Arabic / RTL | 97 | PASS *(72 → 93 C2 → 96 C4 → 97 C5: the last English-only accessible names)* |
| Accessibility | 93 | CONDITIONAL *(85 → 91 C3 → 93 C5: every stepper accessible name now follows the UI language, verified in the computed AX tree; remains CONDITIONAL only for the untested real screen-reader walkthrough)* |
| Responsive / Mobile | 92 | PASS |
| Light Theme | 95 | PASS |
| Dark Theme | 95 | PASS |
| High Contrast | 96 | PASS *(82 → 94 C1 → 96 C3: + forced-colors / prefers-contrast)* |
| Touch | 93 | PASS *(92 → 93, FINAL-C4 lane-card actions)* |
| Keyboard | 88 | PASS |
| Motion | 90 | PASS |
| Error / Recovery UX | 88 | PASS |

**Overall UI/UX Product Readiness: 90 %**

---

## REGRESSION

| Run | Result |
|---|---|
| **Baseline `2a8fcb6`, fresh install, full module** | **515 tests · 1 failed · 0 errors** |
| **HEAD `3f70465`, fresh install, full module** | **521 tests · 1 failed · 0 errors** |
| **HEAD upgrade over a baseline-installed DB, full module** | **521 tests · 1 failed · 0 errors** |

**Frontend:** TestCashierBrowser **16** · TestFloorRegister **26** (was 23) ·
TestReservationsWaitlist **33** (was 30) · TestKdsBrowser **11**
**HOOT:** cashier **40 tests / 146 assertions** · KDS **30 tests / 91 assertions**
**Invariants:** EndpointCoverage 1/0 · RouteScope 1/0 · P61Structural 1/0 · Authz 2/0 ·
CashierHoot 1/0 — **all green**
**Known RateLimit Flake:** `TestRateLimit.test_atomic_under_real_concurrency` — **present
and identical on the pristine baseline**, unchanged in character
**New Failures: 0**
**Tests added: +6** (test_24, test_25, test_26, test_63, test_64, test_65)
**Tests weakened: 0.** `test_60`'s P3H spinner assertion was made **stricter** (animation
must stop **and** keep a visible static cue), per the F8 instruction to re-evaluate it.
**Business Behavior Changed: NO** — no order, payment, KDS, reservation/waitlist, delivery,
pricing, tax, security, branch/company-scope or route behaviour was touched.

> Method note: an early run against a long-lived reused database showed 2 unrelated failures
> (`test_22`, `test_cp11_...`) with `cannot execute UPDATE in a read-only transaction`. Both
> reproduce **identically on the pristine baseline** and vanish on a clean install — they are
> stale-DB artifacts, not regressions. All figures above therefore use the project's own
> clean-install convention.

---

## FINAL VERDICT

# UI/UX CERTIFIED WITH CONDITIONS

The design system is coherent and singly-sourced, navigation is converged and role-appropriate,
every applicable viewport is clean, Arabic/RTL *renders* correctly product-wide, contrast passes
AA in all four theme states, and there are no new regressions.

### Blocking Issues

**NONE.**

At first certification there was one, for an Arabic-market RC: the Owl staff UI was 26 %
translated. **FINAL-C2 closed it** — 100 % of translatable staff strings now carry Arabic,
governed by an approved glossary and enforced by contract tests. What remains is a
native-speaker *read-through* of the delivered wording, which is a review task and is listed
below as a condition, not a product gap.

### Non-Blocking Conditions

1. **Real screen-reader walkthrough: NOT TESTED** — no screen reader in this environment.
   Structural/browser accessibility is proven.
2. **Physical device testing: NOT TESTED** — the responsive matrix proves CSS-viewport
   behaviour, not device pixel ratio or touch hardware.
3. ~~**`prefers-reduced-motion` runtime toggle not exercised**~~ — **CLOSED by FINAL-C5.1.**
   The claim that no emulation was available was **wrong**: the CDP path C3 established for
   `forced-colors` drives `prefers-reduced-motion` too. Both states are now proved with
   `matchMedia` before anything is measured, and the reduced behaviour is read from
   *computed* styles: **0 continuous animations survive `reduce`** (verified by sweeping
   every rendered element on storefront, kiosk and KDS — not by listing known classes),
   the loading cue is never removed, and the KDS LATE meaning survives without motion.
   **No CSS was needed** — every rule was already correct and is now runtime-verified.
   Detail: `FINAL-C5.1-SEMANTICS-MOTION-EVIDENCE.md`.
4. ~~**High Contrast absent on `kiosk.html` + `onboarding.html`**~~ — **CLOSED by FINAL-C1.**
   Both are on the canonical registry; High Contrast is measurably active on both.
5. ~~**`forced-colors` / `prefers-contrast`: NOT SUPPORTED**~~ — **CLOSED by FINAL-C3.**
   Both are supported and browser-verified under CDP media emulation; 0 forced-color opt-outs.
6. ~~**`courses.html` and `drivethru.html` ship English-only**~~ — **CLOSED by FINAL-C4.**
   Both boards are now bilingual on the localisation contract `onboarding.html` already
   used (page-local `T={en,ar}` + `data-t` hooks + the shared `mezze_shop_lang` key) — no
   sixth mechanism. 51/51 keys paired, 0 orphans, 0 undefined references; 24 responsive
   cases and 16 theme cases clean. C4 also fixed 4 pre-existing sub-44px controls on the
   drive-thru lane card (worst: the dismiss control at 27×40).
   Note for the record: these are **operator** boards, and "courses" means **meal
   courses** (hold & fire to the kitchen), not training courses.
7. ~~**Arabic customer stepper accessible names incomplete on shop / QR / kiosk**~~ —
   opened by FINAL-C4, **CLOSED by FINAL-C5.** All **9** hardcoded accessible-name sites
   (shop 2, QR 5, kiosk 2 — several dynamic generation paths, not one literal per file)
   now build their name from each page's existing `T={en,ar}` dictionary, reusing the
   exact pair C4 shipped on the operator boards. Verified on real interacted-with
   steppers in both languages by DOM **and** by the computed accessibility tree
   (`Accessibility.queryAXTree`, `role=button`), with 0 wrong-language AX names and 0
   stale names across live EN→AR→EN switches. Glyphs, layout, touch size, keyboard
   semantics and quantity behaviour unchanged.
   Detail: `FINAL-C5-CUSTOMER-STEPPER-A11Y-LOCALIZATION.md`.
   *Separate finding recorded there and NOT fixed:* `shop.html`'s runtime language switch
   updates `lang` but not the `dir` attribute (fresh AR loads are correct, and the visible
   direction is correct via `body.rtl`) — left alone because changing it could shift
   layout, which C5 was forbidden to do.
8. **Human native-speaker wording review: NOT PERFORMED** — every Arabic string delivered by
   FINAL-C2 was written and cross-checked against the glossary, with automated semantic and
   consistency gates, but no native speaker has read it. No native certification is claimed.

### Recommended Release Action

*Recommendation only — the release decision is yours.*

1. ~~Commission the native-speaker Arabic pass over the 144 listed strings.~~ **Superseded by
   FINAL-C2**, which translated all of them. What is still worth doing is a native-speaker
   **read-through** of the delivered wording (a review, not a translation project) — the
   glossary makes it a short pass.
2. ~~Close condition 4 (kiosk + onboarding onto the theme registry)~~ — **done (FINAL-C1)**.
3. Then consider an RC. Conditions 4, 5, 6 and 7 are now closed
   (FINAL-C1 / C3 / C4 / C5), and condition 3 by FINAL-C5.1. **Every remaining condition
   (1, 2, 8) needs a human or a physical device, not a code change** — a real
   screen-reader walkthrough, physical device validation, and a native-speaker
   read-through of the Arabic wording. **No software-verifiable UI/UX condition remains
   open.** A release note can carry all three.

   FINAL-C5.1 also closed the one observation C5 had left open: `shop.html`'s runtime
   language switch now declares `dir` alongside `lang`. The risk C5 cited (newly
   activating `[dir="rtl"]` rules) did not apply once the mechanism was understood — a
   fresh `?lang=ar` load already renders with `dir="rtl"`, so the switched state now
   simply matches a configuration the product was already shipping.

**RC4:** UNCHANGED (`cad16ae`)
**review/w2:** UNCHANGED (`11afb86`)
**main:** UNCHANGED (`a0a5d8f`)

No RC5 created. No merge performed. No tag moved. No release made.
