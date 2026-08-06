# SCREEN-BY-SCREEN DESIGN COMPLIANCE (production only; prototype excluded)

Scale: PASS / PARTIAL / FAIL / N/A / NOT-OBSERVED. "Browser" = executed authenticated browser evidence at HEAD 96a72e1.

Dimensions: Typo · Color · Space · Radius · Elev · Icon · Buttons · Status · Inputs · Dialogs · Cards · Tabs/Nav · Hierarchy · Density · Touch · AR/RTL · Dark · HC · Responsive · A11y · RestaurantUX.

## `/mezze/pos` — Owl Cashier (PRODUCTION-STAFF · browser-verified)
| Typo | Color | Space | Radius | Icon | Buttons | Status | Inputs | Dialogs | Cards | Touch | AR/RTL | Dark | HC | RestUX |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| PARTIAL (no `--mz-font-num` for amounts) | PASS | **FAIL** (0 primitives / 267 raw px) | PARTIAL (local `--radius`) | PARTIAL (SVG not Material Symbols; labeled) | PARTIAL (dup `.mz-btn` base) | PASS | FAIL (bespoke `.mz-input`) | FAIL (bespoke `.mz-modal`) | FAIL (bespoke `.mz-tile/.mz-line`) | **PARTIAL** (qty 36px, cat ~38px) | PASS (logical props, isolate) | PASS | PASS | PASS (payment mirror, idempotency, mixed tender) |

**Match ≈ 68%.** P0: none. P1: raw-px spacing/radius; qty+cat touch <44px; amounts not tabular-mono. P2: dup button base; bespoke inputs/dialog/card (P3C–G).

## `/mezze/kds` — Owl KDS (PRODUCTION-STAFF · browser-verified) — REFERENCE
| Typo | Color | Space | Radius | Icon | Buttons | Status | Touch | AR/RTL | Dark | HC | RestUX |
|---|---|---|---|---|---|---|---|---|---|---|---|
| PASS (incl. `--mz-font-num`) | PASS (0 raw hex) | PASS (32 primitives) | PASS (`--mz-radius-*`) | PARTIAL (SVG) | PASS (`--touch`) | PASS | PASS (≥48px) | PASS (logical, LTR timer) | PASS | PASS | PASS (aging color+timer+position, allergen-as-note, cancel-shown) |

**Match ≈ 90%.** P0/P1: none. P2: inline SVG vs Material Symbols; item-level completion deferred (documented).

## `/checkout/s/<token>` — Checkout Status hub (PRODUCTION-CUSTOMER · NOT browser-observed)
Server-rendered QWeb, native i18n/RTL, mobile. Typo/Color/AR: NOT-OBSERVED (no browser run); source shows native Odoo i18n. **Match: NOT-OBSERVED.**

## Customer static — bridged (shop, qr, cfd, feedback, drivethru, courses) — NOT browser-observed
Registry bridged (data-appearance + mezze-customer.css → terracotta/real fonts/dark/HC at runtime). Buttons: shop/qr adopt `.mz-btn`; **drivethru/feedback/courses keep legacy gradient `.btn`** (color-flattened only). Status: **drivethru/onboarding color-only dots/badges**. **Match ≈ 55% (source-inferred; not browser-verified).**

## `kiosk.html` (PRODUCTION-CUSTOMER) & `onboarding.html` (ADMIN) — OFF-REGISTRY
No `data-appearance`; own lavender `:root[data-mz-mode]` palette; **no theme registry, no HC**; **misspelled `'IBM Plex Arabic'` → Arabic falls back to system**. Typo FAIL(AR)/Color FAIL(off-brand lavender)/Dark PARTIAL(self-rolled)/HC FAIL. **Match ≈ 35%.**

## `pos.html` prototype — EXCLUDED from production scoring
Uses `.mz-btn`×59, `.mz-status`×50, own @font-face + registry. Reference for intended design ONLY.

## Summary
| Screen | Production? | Browser | Match % | P0 | P1 | P2 |
|---|---|---|---|---|---|---|
| /mezze/kds | YES | YES | ~90% | 0 | 0 | 2 |
| /mezze/pos | YES | YES | ~68% | 0 | 3 | 3 |
| shop / qr | YES-cust | NO | ~60% | 0 | 1 | 2 |
| cfd / feedback / drivethru / courses | YES | NO | ~52% | 0 | 2 | 2 |
| /checkout/s hub | YES-cust | NO | NOT-OBSERVED | ? | ? | ? |
| kiosk | YES-cust | NO | ~35% | 1 (AR broken) | 2 | 1 |
| onboarding | ADMIN | NO | ~35% | 0 | 2 | 1 |
