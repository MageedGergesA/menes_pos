# 04 — Component Inventory & Duplication

Components are largely **re-implemented per file** because each `static/*.html` is a
self-contained shell. The Owl cashier (`static/src/cashier/components/*`) is the one
place with true reusable components.

## Reusable-component matrix (where implemented / consistency)

| Component | `pos.html` | Owl cashier | `shop` | `qr` | `kiosk` | Consistency |
|---|---|---|---|---|---|---|
| Button (primary) | `.btn`,`.primary` | component CSS | `.btn` | `.btn` | `.startbtn/.svcbtn/.addbtn/.review` | **DUPLICATED** (many class names) |
| Icon button | many (some unnamed) | — | few | few | few | drift + a11y gap (unnamed) |
| Input / select | DS input (h44, focus ring) | `manual_tender` inputs | own | own | own | drift |
| Search | `#search` | `product_grid` | `.search` | — | — | drift |
| Category chip / tab | `.cat`/segmented | tabs | `.cat` | `.cat` | `.cat` | similar but per-file |
| Status badge / pill | `.badge` (DS, +label) | status chips | `.pill`/`.tag` | `.tag` | `.tag` | **DUPLICATED** |
| Card | DS `.card` (stripe) | component | `.card` | `.card` | `.card` | drift (radius/padding differ) |
| Product tile | `.card`/tile | `product_grid` tile | menu card | menu card | `.card` big | **DUPLICATED** |
| Cart line | `.cartrow` | `cart.xml` | cart row | cart row | `.crow` | **DUPLICATED** |
| Payment-method selector | `pay*` family | `payment_screen` | online only | pay/online | pay-at-counter | drift |
| Quantity stepper | `less/more` | `cart` +/- | qty | qty | qty | **DUPLICATED** |
| Modal / sheet | 35 blocks, `role=dialog`×3 | dialogs | `.sheet`×3 | `.sheet`×3 | `.sheet`×1 | **DUPLICATED** (headers differ; only pos marks `role=dialog`) |
| Toast | `aria-live`×2 | — | none | none | none | present only in pos |
| Empty state | some | some | minimal | minimal | minimal | inconsistent |
| Skeleton / loading | partial | spinner | spinner | spinner | spinner | inconsistent |
| KPI tile | DS KPI | — | — | — | — | pos only |
| Order card / table card / KDS ticket | pos | — | — | — | — | pos only |
| Go-Live check row / step | — | — | — | — | — | `onboarding.html` (own) |

## Duplication report (concrete)

1. **Primary-action button** exists as `.btn`, `.primary` (pos), `.addbtn`,
   `.svcbtn`, `.startbtn`, `.review` (kiosk), and the `.pay*` family (pos payment) —
   at least **4 distinct implementations** of "the button the user taps to proceed".
2. **Status pill** as `.badge` (pos, DS), `.pill`/`.tag` (shop), `.tag`
   (qr/kiosk/onboarding) — ~3 implementations; only the pos one guarantees a text
   label (status-not-color-alone).
3. **Bottom sheet / modal** as `.modal`/`.overlay` (pos, `role=dialog`), `.sheet`
   (shop/qr/kiosk) — different header conventions; **only `pos.html` sets
   `role=dialog`/`aria-modal`**.
4. **Quantity control** re-implemented in pos, Owl cart, shop, qr, kiosk (`.crow`).
5. **Cart line** re-implemented per surface (`.cartrow` vs `.crow` vs shop rows).

## Component states (present ✓ / missing ✗)

| State | pos.html | shop/qr/kiosk | onboarding.html |
|---|---|---|---|
| default / selected | ✓ | ✓ | ✓ |
| hover | ✓ | ✓ | partial |
| **focus-visible** | ✓ (12 rules, ring) | shop✓/qr✓/**kiosk ✗** | **✗ (0 rules)** |
| pressed (touch feedback) | ✓ (`scale(.97)`) | partial | ✗ |
| disabled | ✓ | partial | partial |
| loading | ✓ | spinner | ✗ |
| error / success | ✓ (`aria-live`) | color only | inline text |

**Key state gaps:** `kiosk.html` and `onboarding.html` have **no `:focus` styling**;
`onboarding.html` (S5 admin console) has no press/loading/aria states — the weakest
surface for interaction feedback and keyboard a11y.

## Consolidation opportunity (report only — do NOT refactor now)

One shared component layer (button, badge, card, input, sheet/modal, qty stepper,
status pill) imported by every `static/*.html` would remove ~5 duplicate button
implementations, ~3 badge implementations, and unify modal semantics + focus states.
This is the single highest-leverage structural change (see `FINAL-DESIGN-ROADMAP.md`
P1).
