# DESIGN-P1 — Accessibility & Contrast Parity — Result

Scope: **accessibility & contrast parity only** (focus, dialog semantics, accessible
names, status announcements, color-only state, meaningful contrast, high-frequency
touch, reduced motion, RTL/dark a11y). **No** shared tokens, component library, nav
restructure, customer shell, theme/font/spacing/radius migration, or visual redesign.

Release baseline: audit commit `94c2160`; certified RC `mezze-v1.0-rc1` (`ad32f3e`)
**never moved**. Standard: WCAG 2.2 **AA** baseline; **44×44 CSS px** is Mezze's
internal *operational touch* target for frequent controls (not claimed as a WCAG AA
requirement).

## Measure-first findings (why the scope is what it is)

**Contrast — measured, mostly PASSES; not changed.** Computed WCAG ratios for the
muted-text tiers on the four priority surfaces:

| Pair | Ratio | Verdict |
|---|---:|---|
| onboarding/kiosk DARK `--mut #b7a9c2` on `--card #211a26` | 7.63:1 | PASS |
| onboarding/kiosk LIGHT `--mut #6b5c76` on `#fff` | 6.14:1 | PASS |
| onboarding/kiosk LIGHT `--mut #6b5c76` on `--bg #faf7fb` | 5.78:1 | PASS |
| qr LIGHT `--ink2 #6b6259` on `#fff` | 5.97:1 | PASS |
| shop LIGHT `--ink2 #6e6152` on `#fff` | 6.01:1 | PASS |
| shop DARK `--ink2 #c6b6a2` on `--card #211a13` | 8.69:1 | PASS |

→ The audit's contrast worry was `--ink-3` (3.76:1) **in the DS/`pos.html`**, already
documented + restricted to ≥14px/bold there. The customer/kiosk/onboarding muted tiers
**already pass AA** — **no token darkened** (measure-first prevented an invented change).

**Touch — measured, mostly PASSES; one real fix.**

| Control | Screen | Before W×H | High-frequency? | Action |
|---|---|---|---|---|
| `.step button` (qty ±) | shop | 44×44 | yes | already OK — no change |
| `.cat` (category chip) | qr | min-h 44 | yes | already OK — no change |
| `.stepper button` (qty ±) | qr | 44×44 | yes | already OK — no change |
| `.add` (add-to-cart) | shop | **40×40** | yes | **→ 44×44** |
| `.thumb .half` (½&½ badge) | shop | 26×26 | no (indicator) | no change |
| `.cartbar .cc` (count bubble) | shop | 27×27 | no (counter) | no change |

## Patch manifest (exact, evidence-backed)

| # | Surface | Category | Change |
|---|---|---|---|
| P1-1 | onboarding.html | focus | Add `:focus-visible` ring (accent, offset), light+dark |
| P1-2 | onboarding.html | names/labels | `aria-label` on theme (◐) button; `aria-label` on token input + profile `<select>` |
| P1-3 | onboarding.html | status | `aria-live="polite"` on `#err`; `role="status"` on the overall verdict/complete region |
| P1-4 | onboarding.html | reduced-motion | Add `prefers-reduced-motion` block |
| P1-5 | kiosk.html | focus | Add `:focus-visible` ring, light+dark |
| P1-6 | kiosk.html | reduced-motion | Add `prefers-reduced-motion` block |
| P1-7 | kiosk.html | dialog | `role="dialog" aria-modal="true"` + `aria-label` on the modifier/cart sheet |
| P1-8 | kiosk.html | names | `aria-label` on lang + theme icon buttons |
| P1-9 | shop.html | dialog | `role="dialog" aria-modal="true"` + labelled title on the 3 `.sheet` dialogs |
| P1-10 | shop.html | touch | `.add` 40→44 (no overlap; density preserved) |
| P1-11 | shop.html | status | `aria-live="polite"` for cart/checkout status region |
| P1-12 | shop.html | names | `aria-label` on `.add` / cart / icon buttons |
| P1-13 | qr.html | dialog | `role="dialog" aria-modal="true"` + labelled title on the sheets |
| P1-14 | qr.html | status | `aria-live="polite"` for order/bill status region |
| P1-15 | qr.html | names | `aria-label` on icon buttons |
| P1-16 | all four | focus-not-obscured | ensure ring not hidden under sticky bars (offset/scroll-margin) |

Cashier (`pos.html`) + KDS: **regression-tested only, no visual change** (already meet
the contract). No business/financial logic touched anywhere.

## Results

Browser-verified on a running server (`read_page` accessible DOM + console) — EN and
AR. Screenshots were unavailable (tooling), so per the guardrail this is
**Semantic accessibility smoke: PASS**, not screen-reader certification.

| Audit issue | Before | Fix | Evidence | Status | Remaining debt |
|---|---|---|---|---|---|
| onboarding: no keyboard focus | 0 `:focus` rules | Added `:focus-visible` ring (accent, offset, scroll-margin) light+dark | CSS present; served | **FIXED** | shares accent token w/ others → DESIGN-P2 |
| onboarding: unnamed input/select/theme | 0 `aria-label` | `aria-label` on token input, profile select, theme, lang | `read_page`: "Admin token", "Business profile", "Toggle light or dark theme", "Switch language" | **FIXED** | — |
| onboarding: async results silent | no live region | `aria-live` on `#err` (alert) + `#overall` (status) | served attrs | **FIXED** | — |
| onboarding: no reduced-motion | none | added `prefers-reduced-motion` block | served | **FIXED** | — |
| kiosk: no keyboard focus | 0 `:focus` | `:focus-visible` ring light+dark | served | **FIXED** | — |
| kiosk: cart sheet not a dialog | plain div | `role=dialog aria-modal aria-labelledby` + `role=alert` on error | `read_page`: `dialog "طلبك"` + `alert` | **FIXED** | JS focus-trap not added (native dialog semantics only) — DESIGN-P2 |
| kiosk: no reduced-motion | none | added block | served | **FIXED** | — |
| shop: 3 sheets not dialogs | plain divs | `role=dialog aria-modal aria-labelledby` on ov-opt/cart/co | `read_page`: 3 `dialog` w/ headings + "Close" | **FIXED** | focus-trap = DESIGN-P2 |
| shop: `.add` 40×40 (frequent touch) | 40×40 | → 44×44 | CSS `width:44px;height:44px` served | **FIXED** | — |
| shop: zone/payment status silent | no live region | `role=status`/`role=alert`+`aria-live` on co-zinfo/co-zerr/co-pmsg | `read_page`: `status` + `alert` | **FIXED** | — |
| qr: 3 sheets not dialogs + unlabelled close | plain divs, close `✕` no name | `role=dialog aria-modal aria-labelledby` + `aria-label="Close"` | `read_page`: 3 `dialog` + "Close" | **FIXED** | focus-trap = DESIGN-P2 |
| qr: toast silent | no live region | `role=status aria-live` on `#toast` | `read_page`: `status` | **FIXED** | — |
| qr: cart-line stepper unnamed | `<button>–/+</button>` | `aria-label="less"/"more"` | served | **FIXED** | — |
| Contrast (customer/kiosk muted) | 5.6–8.7:1 measured | **none — already passes AA** | measured (see table) | **NO CHANGE NEEDED** | `--ink-3` 3.76:1 in `pos.html` (documented/restricted) tracked, not touched |
| shop/qr focus + reduced-motion | already present | verified, not modified | grep | **ALREADY OK** | — |

**Cashier (`pos.html`) + KDS:** no visual change; regression-tested only.
**Backend / business / financial behavior:** **unchanged** (all edits are HTML
attributes, CSS focus/motion, one radius-preserving 40→44px, and aria-labels in JS
template strings — no order/payment/delivery logic).

## Re-score (evidence-affected dimensions only)

| Dimension | Before | After | Basis |
|---|---:|---:|---|
| Accessibility Baseline | 58% | **72%** | focus on the 2 zero-focus surfaces; dialog semantics on 7 sheets; live regions on 6 status/error nodes; accessible names on the worst surface; reduced-motion parity |
| Touch | (n/a scalar) | ↑ | shop `.add` 40→44; other frequent controls already 44 |
| Arabic / RTL | 65% | **68%** | AR verified on kiosk+shop with new semantics; no new RTL defects (logical-property RTL migration deferred to DESIGN-P2) |
| Dark mode | ~63% | **65%** | focus rings verified usable in dark; no dark regressions; kiosk/onboarding dark completeness still DESIGN-P2/P6 |
| Onboarding/Go-Live screen | 56 | **66** | from worst-a11y to labelled + focus-visible + live status |
| Kiosk screen | 69 | **73** | dialog + focus + reduced-motion |
| Customer shop | 60 | **65** | dialogs + status + 44px touch |
| Table QR | 60 | **65** | dialogs + labelled close + status |
| **Overall design readiness** | 68% | **~72%** | accessibility floor raised on the four weak surfaces; token/component consolidation (the big lift) remains DESIGN-P2+ |

Scores reflect **only** what was measured/changed. No token/component/nav/theme work
was done, so those dimensions are unchanged by design.

## Remaining debt (explicitly deferred, not hidden)

- JS **focus-trap** + focus-return for custom sheets (native `role=dialog` added; full
  trap belongs with the shared modal component in **DESIGN-P2**).
- **Shared token layer** (3 vocabularies, triplicated accent) — **DESIGN-P2**.
- Logical-property **RTL migration** of physical `left/right` spacing — later increment.
- `pos.html` `--ink-3` 3.76:1 (documented/restricted) — revisit with the token layer.

