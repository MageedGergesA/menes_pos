# RC7 — Register deployment verification

Real headless Chrome against the **deployed** runtime with **real pilot data**, at
1440×900, Light, EN, dpr 1. Tab / Shift+Tab / Enter / Space were driven as **trusted**
CDP input events, because synthetic `KeyboardEvent`s can neither move focus nor fire a
button's default action. Identical results on shadow `:8092` and canonical `:8090`.

## Geometry

| Element | Expected | Measured |
|---|---|---|
| Icon rail | ~75px | **75 × 852** |
| Category sidebar | ~185px | **185 × 852** |
| Order panel | ~381px | **381 × 852** |
| Product card | 145 × 229 | **145 × 229** |
| Media | 143 × 143 | **143 × 143** |
| Columns @1440 | 5 | **5** |
| Gap | 11px | **11px** |
| Product name | 13.5px / 600 | **13.5px / 600** |
| Total | 24px / 800 | **24px / 800** |
| Charge | 52px / r16 | **348 × 52, radius 16px** |
| Quick-add visible | 27 × 27 | **27 × 27** |
| Quick-add hit target | ≥44 × 44 | **44 × 44** |

## Real data truth — no fake data was added

The pilot catalogue contains **12 menu products, none of which carry an image**. The
only imaged product template is *Gift Card*, a loyalty utility product with no POS
category, which `_menu_domain` deliberately excludes from the menu.

Consequence, and it is correct behaviour rather than a defect:
**0 real images rendered · 0 broken images · 12 clean initials placeholders · grid
layout holds · no image requests issued.**

## Category navigation

Vertical sidebar at ≥1280px with real categories and real counts —
`All items 12 · Cold Mezze 3 · Drinks 4 · Grills 3 · Manakish 2` (3+4+3+2 = 12, self
consistent). Exactly one category control is pressed. Selecting a category filters the
grid (12 → 2). **Exactly one category navigation system is visible at every width** —
never both, never zero.

## Navigation rail — no dead destinations

Five real destinations, all 46px tall, each with an icon:

| Item | Kind | Verified |
|---|---|---|
| Register | in-app, `aria-current="page"` | active phase |
| Floor | link `/mezze/floor?config_id=1` | navigates (title "Mezze Floor") |
| Orders | in-app phase switch | phase → `orders`, `aria-current` moves |
| Reservations | in-app phase switch | phase → `reservations`, `aria-current` moves |
| Kitchen | link `/mezze/kds?config_id=1` | real route |

Orders and Reservations carry no `href` because they are **in-app phase switches**
(`openOrders()` / `openHost()`), not dead links — both were clicked and both changed
phase.

## Navigation is never lost across phases

| Phase | Surface | Destinations | `aria-current` |
|---|---|---|---|
| menu | rail | 5 | Register |
| orders | horizontal nav | 4 | Orders |
| reservations | horizontal nav | 4 | Reservations |
| **payment** | horizontal nav | 4 | Register |
| back to menu | rail | 5 | Register |

**Always exactly one navigation surface. Never zero, never two.** This is the defect
found during the restoration (hiding the horizontal nav had left Payment with none).

## Quick-add

| Check | Result |
|---|---|
| Mouse click | 1 line, qty 1 — exactly +1 |
| Tab sequence | card0 main → card0 quick-add → card1 main → card1 quick-add |
| Shift+Tab | exact reverse |
| Enter | qty → 1 (+1) |
| Space | qty → 2 (+1) |
| AX role / name (EN) | `button` / `Add Arabic Coffee to order` |
| AX role / name (AR) | `button` / `إضافة Arabic Coffee إلى الطلب` |
| Disabled products | 0 in this catalogue (nothing 86'd); native `disabled` mirrors main |

## Arabic / RTL

`dir=rtl`, `lang=ar_001`. Icon rail mirrors to the right (x=1365), order panel to the
left (x=0), category sidebar mirrors. Quick-add sits **12px from the inline-end** (now
the left edge) and the **`+` glyph does not mirror** (`transform: none`). Rail labels
are Arabic (نقطة البيع / الصالة / الطلبات / الحجوزات / المطبخ), sidebar label الفئات,
"All items" → كل الأصناف. Category *names* remain English because they are database
data. 0 horizontal overflow, 0 sub-44px controls, 5 columns.

## Responsive

| Width | Navigation | Categories | Columns | Overflow | <44px |
|---|---|---|---|---|---|
| 768 | horizontal nav | chip bar | 3 | 0 | 0 |
| 1024 | horizontal nav | chip bar | 4 | 0 | 0 |
| 1280 | **icon rail** | **sidebar** | 4 | 0 | 0 |
| 1440 | icon rail | sidebar | 5 | 0 | 0 |
| 1920 | icon rail | sidebar | 8 | 0 | 0 |

The 1280px threshold behaves exactly as designed, and all 12 quick-adds render at every
width.

## Accessibility smoke

| Mode | Quick-add | Hit | Nav / Cat | Overflow | <44px |
|---|---|---|---|---|---|
| light | visible | 44×44 | 1 / 1 | 0 | 0 |
| dark | visible | 44×44 | 1 / 1 | 0 | 0 |
| forced-colors | visible, **1px system border** | 44×44 | 1 / 1 | 0 | 0 |
| prefers-contrast: more | visible | 44×44 | 1 / 1 | 0 | 0 |
| prefers-reduced-motion | visible, no long animation | 44×44 | 1 / 1 | 0 | 0 |

## Fidelity

Implementation fidelity remains the certified **85/100 — substantially restored**. It
was **not** rescored against pilot data: missing catalogue photography is a property of
the pilot database, not of the implementation.
