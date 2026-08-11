# F4–F9 — MEASURED EVIDENCE

All numbers below were measured in a real browser against the running product
(verification server `127.0.0.1:8088`, DB `mezze_ui`, authenticated Odoo session), not
read off the source.

## Method note — how a REAL CSS viewport was obtained (F4)

`resize_window` reports success but the top-level CSS viewport does not change
(`window.innerWidth` stayed **2494** after resizing to 390×844). That is the same blocker
the earlier audits hit and honestly recorded as "Mobile NOT TESTED".

It is closed here with a **same-origin iframe harness**: the surface is loaded into an
iframe of an exact CSS width, and the measurement reads *that browsing context's* own
`window.innerWidth`. Verified genuine:

```
innerWidth: 390   mq(max-width:400px): true   mq(min-width:1024px): false
```

The iframe's `innerWidth` **is** its CSS viewport, and media queries evaluate against it —
this is a real viewport test, not a scaled screenshot.

**What it covers:** CSS viewport width, media queries, layout, wrapping, overflow, element
geometry, computed styles, touch-target sizes in CSS px.
**What it does NOT cover (declared, not hidden):** device pixel ratio, real touch input,
mobile browser chrome / dynamic URL-bar viewport behaviour, and physical device rendering.
Overflow is compared against `documentElement.clientWidth`, which excludes the desktop
scrollbar — the conservative comparison.

## F4 — Responsive matrix

`ovf` = page-level horizontal overflow in px. `small` = interactive controls under 44px high.

| Surface | 360 | 390 | 430 | 768 | 1024 | 1280 | 1440 |
|---|---|---|---|---|---|---|---|
| Register `/mezze/pos` | – | – | – | ovf 0 | ovf 0 | ovf 0 | ovf 0 |
| Floor `/mezze/floor` | – | – | – | ovf 0 | ovf 0 | ovf 0 | ovf 0 |
| KDS `/mezze/kds` | – | – | – | – | ovf 0 | ovf 0 | ovf 0 |
| Shop | ovf 0 | ovf 0 | ovf 0 | ovf 0 | – | – | – |
| QR ordering | ovf 0 | ovf 0 | ovf 0 | ovf 0 | – | – | – |
| Kiosk | – | – | – | ovf 0 | ovf 0 | ovf 0 | – |
| CFD | – | – | – | – | ovf 0 | ovf 0 | – |
| Feedback | ovf 0 | ovf 0 | ovf 0 | ovf 0 | – | – | – |
| Coursing | – | – | – | ovf 0 | ovf 0 | ovf 0 | – |
| Drive-thru | – | – | – | ovf 0 | ovf 0 | ovf 0 | – |
| Onboarding | – | – | – | ovf 0 | ovf 0 | ovf 0 | – |

`–` = not a supported width for that surface (documented minimums below), not an untested gap.

**Supported minimum widths (product decision, unchanged by this program):**
customer surfaces (shop / QR / checkout / feedback) 360px; kiosk 768px (dedicated portrait
terminal); Register / Floor 768px; KDS 1024px (dedicated display); coursing, drive-thru and
onboarding 768px (operator boards, never phone surfaces).

**Page-level horizontal overflow defects: 0.**
Only defect found: drive-thru "+ New car" measured **104×40** → fixed to 44px.

## F5 — Arabic / RTL

Computed font family per surface in full RTL (`document.dir = rtl`):

| Surface | Before | After |
|---|---|---|
| Shop | IBM Plex Sans Arabic | IBM Plex Sans Arabic |
| QR | IBM Plex Sans Arabic (except `.cat` chip = **Arial**) | IBM Plex Sans Arabic |
| Kiosk | **"IBM Plex Arabic" (non-existent family → Latin fallback)** | IBM Plex Sans Arabic |
| Onboarding | **"IBM Plex Arabic" (non-existent family → Latin fallback)** | IBM Plex Sans Arabic |
| Feedback | body ok, but label/`.btn`/`.star`/`.lang` = **Hanken Grotesk / Arial** | IBM Plex Sans Arabic |
| CFD | IBM Plex Sans Arabic | IBM Plex Sans Arabic |
| Register / Floor / KDS | IBM Plex Sans Arabic | IBM Plex Sans Arabic |

**RTL detail checks (Register, live):**
- logical spacing / mirrored layout — PASS (brand right, cart left, nav mirrored)
- amount + currency placement — PASS (`30.00 $`, digits LTR, currency trails in RTL)
- numeric input direction — PASS (payment reference / PIN / amount fields carry `dir="ltr"`)
- phone/email — PASS (`unicode-bidi:isolate` on phone cells)
- quantity stepper — PASS: the track mirrors with the layout and the **+/- glyphs are NOT
  mirrored**, so business meaning is preserved
- back / forward arrows — **was FAIL**: U+2190/U+2192 have `Bidi_Mirrored=No`, so "back"
  kept pointing physically left. Now mirrored via `.mz-dirglyph` (verified computed
  `matrix(-1, 0, 0, 1, 0, 0)`); the payment screen renders "Back to order →" in RTL.
- keyboard shortcut legend — **was FAIL** (trailing neutrals reordered), now isolated LTR
- filter strip scrolling — PASS (`overflow-x:auto`, 0 page overflow at every width)
- mixed Arabic + English — PASS (bidi isolation on data-bearing cells)

**Not fixed, reported:** Arabic *translation coverage* of the Owl staff apps is
**52/201 strings = 26%**. See `F5-ARABIC-COVERAGE-GAP.md`.

## F6 — Accessibility

Measured on Register (menu), Register (payment), Register (cash tender), Floor, KDS:

| Check | Result |
|---|---|
| Interactive controls with no accessible name | **0** |
| Form controls with no programmatic label | **0** |
| Positive `tabindex` (order smells) | **0** |
| Dialog focus transfer | PASS — opening "Assign table" moves focus inside the dialog |
| Dialog `role` | PASS — 11/11 production dialogs |
| Dialog accessible name | PASS — 11/11 (`aria-label` / `aria-labelledby`) |
| Dialog `aria-modal` | **was 5/11** → now **11/11** (6 cashier dialogs were missing it) |
| Smallest frequent touch target | **36px** — canonical `.mz-btn--sm` ("Add customer"), a deliberate secondary/inline variant. All primary, money, nav, category, stepper, table, reservation and KDS actions are ≥44px. |
| Colour-only critical states | **0** — status carries text + `data-state`; not-tested is dashed; reserved tables are dashed + labelled; selection adds weight/ring |

**Real screen-reader walkthrough: NOT TESTED** (no screen reader in this environment).
Reported separately from the semantic audit above, which is browser-measured.

## F7 — Themes / contrast

Measured on the live payment screen (the highest-stakes surface) in all four theme states.
Ratios are computed from resolved `getComputedStyle` colours, including `color-mix()`.

| Pair | classic/light | lounge/dark | HC light | HC dark |
|---|---|---|---|---|
| Total amount (24px/800) | 15.31 | 12.96 | 21.00 | 19.80 |
| Payment title (22px/700) | 15.09 | 15.48 | 21.00 | 21.00 |
| Payment method tile (16px/700) | 15.31 | 12.96 | 21.00 | 19.80 |
| Back link (13px/600) | 5.18 | 6.67 | 13.58 | 13.48 |
| Nav — idle (14px/600) | 10.09 | 9.69 | 18.10 | 16.91 |
| Nav — current (14px/800) | **5.09** | 6.08 | **5.09** | 6.08 |
| "Add customer" (13px/700) | 9.37 | 8.69 | 16.45 | 15.74 |
| User label (16px/600) | 10.09 | 9.69 | 18.10 | 16.91 |
| Connectivity status (11px/700) | 5.61 | 6.47 | 6.32 | 6.84 |

**Pairs below WCAG AA (4.5:1): 0. Lowest important measured contrast: 5.09:1** (current
navigation item, light themes).

Navigation before F3, same measurement: **1.19 / 1.37 / 1.02** — the UA `buttonface`
defect. Fixed.

- `forced-colors`: browser supports the query; the **product declares 0 rules** → NOT SUPPORTED.
- `prefers-contrast`: browser supports the query; the **product declares 0 rules** → NOT SUPPORTED.
- Mezze's own High-Contrast theme is a separate, working feature and must not be confused
  with either.

## F8 — Motion

Every animation in production CSS, and its reduced-motion answer:

| Animation | Default | Under `prefers-reduced-motion: reduce` |
|---|---|---|
| `.mz-spinner` | 0.8s linear infinite | **was 2400ms (still spinning)** → now `animation:none` + static brand arc |
| `.mz-kds-spinner` | 900ms linear infinite | **was 2400ms; no branch of its own** → now `animation:none` + static arc |
| `.mz-status--active .mz-status__dot` | 1.4s pulse infinite | `animation:none` |
| `.mz-kds-card--late .mz-kds-timer` | 1.4s pulse infinite | `animation:none` |
| `.mz-dialog__panel` / `.mz-modal` | 140ms enter | `animation:none` |
| `.mz-undo-toast` | 180ms enter | `animation:none` |
| `.mz-btn` / stepper / chips / nav | short transitions | `transition:none` |
| motion duration tokens | — | `--mz-dur-*: .001ms` |

**Continuous motion remaining under reduce: 0.** No decorative infinite pulse; spring
behaviour remains confined to the established payment-completion moment.

Verified from the *served* stylesheet via CSSOM (rule present and correctly scoped). The
environment reports `prefers-reduced-motion: no-preference` and offers no emulation, so the
**runtime toggle itself was not exercised** — declared, not implied.

## F9 — Cross-screen convergence

**Typography** — computed family of every visible element, all 8 static production surfaces
plus the 3 Owl apps: **Hanken Grotesk** (Latin) / **IBM Plex Sans Arabic** (Arabic) only.
**Zero** Arial, system-ui, Roboto or misspelled-family leakage.
**Numerics:** `.mz-tile-price` computes **JetBrains Mono + `font-variant-numeric: tabular-nums`**
— the old "cashier money not tabular-mono" gap is closed.

**Canonical components render identically across every surface:**
`.mz-btn` radius 11px / weight 700 / ≥44px · `.mz-input` 11px · `.mz-status` pill 999px ·
`.mz-alert` 8px.

**Component systems:** Button 1 · Status 1 · Badge 1 · Alert 1 · Input 1 · Quantity 1 ·
Dialog 1 · Card 1 · List-row 1 · Empty/Loading 1 · Filter/Segmented 1 · **Navigation 1 (new
in F3 — previously 2 drifted copies)**.

**Explained residual vocabularies (not unexplained duplication):**

| Surface | Classes | Why it stays |
|---|---|---|
| kiosk | `.svcbtn` | eat-in/takeaway service-mode selector; deliberately branded large-touch, kept by P3I |
| qr | `.cartbtn`, `.x` | page-local cart bar + sheet close on a phone-only surface |
| shop, courses, drivethru | `.sx`, `.x` | dialog/sheet close glyph buttons |
| feedback, courses, drivethru | `.btn`, `.ghost`, `.act` | legacy customer `.btn` bridge (documented since P3A); now inherits the correct font and meets 44px |
| drivethru | `.newbtn` | lane-board action; touch fixed here |

**Unexplained production component systems: 0. Unexplained hardcoded palettes: 0** — every
raw hex remaining in production CSS is a page-local palette *definition* that the
`--mz-` bridge maps onto the canonical brand, or a QR quiet-zone plate.
