# KDS REUSE DECISION (V2B) — reuse-first audit → verdict

Date 2026-08-06. HEAD `9ab239d`. Audit-only; NO production/test code changed. Options: **A** reuse native
Odoo Preparation Display · **B** thin extension of native · **C** custom Mezze KDS UI.

## Recommendation: **C — CUSTOM MEZZE KDS UI** (on the existing `mezze.kds.ticket` domain)

Chosen NOT because the prototype looks good, but because native reuse is blocked by **two hard gates** —
one legal, one functional — and Mezze already owns a mature, correct KDS data domain.

## The two hard gates against native (A/B)

### Gate 1 — LICENSING (fatal for a Community product)
- Native Preparation Display = **`pos_enterprise`, license `OEEL-1`** (Odoo Enterprise Edition License);
  models `pos.prep.display/order/line/stage/state`; route `/pos_preparation_display/web/`.
- Native customer Order Status Screen = **`pos_order_tracking_display`, `OEEL-1`** too.
- **Mezze is `LGPL-3`, Odoo-Community-based** (`mezze_bridge` license LGPL-3; all deps Community LGPL-3;
  `docs/product/EDITIONS.md` = "Odoo Community"). An LGPL-3 Community product **cannot ship a dependency on
  / integration with OEEL-1 code** — it would force every customer onto an Enterprise subscription and
  contradicts Mezze's clean-room positioning. **A and B are legally unshippable.**

### Gate 2 — HELD COURSES LEAK ON NATIVE (critical restaurant-workflow failure)
- **Native does NOT hide un-fired course items.** `pos.prep.order.process_order` → `_process_preparation_
  changes` loops **every** `order.course_ids` with **no `fired` gate**; the un-fired course renders as a
  full order card with all line items visible, badged **"Pending"** (`order.js:22-25`, `order.xml:11-16`).
  There is no code path that withholds a held course's contents from the kitchen. (Native tests confirm no
  such guarantee.)
- **Mezze hides held courses correctly.** Held courses live as JSON in `ir.config_parameter` and never
  reach the KDS; `/courses/fire` passes ONLY the fired course's lines into `_do_fire`
  (`main.py:2373-2413`), so the kitchen sees each course as a distinct numbered fire and un-fired courses
  never appear. This is exactly Part-23's "a critical restaurant workflow cannot be reliably implemented
  through native extension" — patching native to suppress held content means fighting core.

## Supporting evidence (native vs Mezze)

### Integration seam
- Native prep orders are created by `pos.prep.order.process_order(order_id, options)`, triggered by the
  **native POS `sendOrderInPreparation` client flow**. Mezze's `/mezze/pos` is a **custom Owl cashier**
  that syncs via `/orders/sync` and **never calls `process_order`** — so in restaurant mode a Mezze order
  would **not** appear on the native display without custom glue (verified: mezze_bridge has **zero**
  `pos.prep.*` references). Even licensed, native needs custom integration.

### Arabic / RTL / dark / High-Contrast
- Native prep board: **NOT_FOUND** for RTL/dir/Arabic-specific, dark, prefers-color-scheme, high-contrast
  (relies on global Bootstrap-RTL only). Mezze requires all of these (already delivered on the cashier in V2A).

### Comparison matrix (▲ = better / ✓ = present / ✗ = absent)
| Capability | Mezze KDS (`mezze.kds.ticket`) | Native (`pos.prep.*`, OEEL-1) | Decision |
|---|---|---|---|
| Kitchen ticket / lines | ✓ own model | ✓ | tie |
| Table / guests / server | ✓ snapshot | ✓ | tie |
| Order source / channel | ✓ on pos.order | preset only, no type filter | Mezze ▲ |
| Dine-in/pickup/delivery/QR/aggregator | ✓ all feed KDS | display has no order-type facet | Mezze ▲ |
| **Courses: hold / fire course N** | ✓ | ✓ (tagging) | tie |
| **Held course hidden until fired** | **✓** | **✗ (leaks as "Pending")** | **Mezze ▲ (hard gate)** |
| Addition after fire | ✓ delta ticket, idempotent | ✓ delta prep.order | tie |
| Cancel after fire → kitchen | KDS-screen only; **no order-void cascade (gap)** | cancel-as-qty (no cancelled state) | both partial |
| Ready / served | ✓ (fired→…→served) | ✓ stages | tie |
| Late / alert timer | derived from timestamps | ✓ per-stage `alert_timer` | Native ▲ |
| Item-level completion | **✗ (station-level only)** | ✓ per-line `todo` | Native ▲ |
| Priority / rush | ✗ | ✗ | tie |
| Allergy / structured | free-text `note` only | note only | tie |
| Multiple stations / routing | ✓ `station` per product | ✓ category/config routing | tie |
| Recall / reopen | ✓ `action_recall` | ✓ recall stack | tie |
| Realtime | ✓ `bus.bus` + transactional outbox + poll | ✓ `bus.bus` | tie |
| **LAN / WAN-independent** | **✓ local server→client** | ✓ bus (local) | tie |
| Multi-worker / reconnect | ✓ row-locked + poll reconcile | ✓ RPC re-fetch on reconnect | tie |
| Arabic / RTL / dark / HC | ✓ (reuse cashier V2A contract) | ✗ NOT_FOUND | Mezze ▲ |
| Customer Order Status Screen | ✓ own `/checkout/s/<token>` (LGPL-3) | ✓ but OEEL-1 | Mezze ▲ (license) |
| **Licence for a Community product** | **✓ LGPL-3** | **✗ OEEL-1** | **Mezze ▲ (hard gate)** |

## Decision scorecard (0–100 weighted)
| Category (weight) | A native | B extend | C custom |
|---|---|---|---|
| restaurant functional fit (25) | 18 | 18 | 23 |
| course/addition/cancel (15) | 7 | 9 | 12 |
| realtime/reliability (15) | 13 | 13 | 14 |
| Edge/offline fit (10) | 8 | 8 | 10 |
| UX/design fit (10) | 4 | 6 | 9 |
| Arabic/RTL (5) | 1 | 3 | 4 |
| testability (5) | 2 | 3 | 5 |
| implementation effort (5) | 4 | 3 | 3 |
| maintenance burden (5) | 2 | 2 | 4 |
| Odoo upgrade resilience (5) | 4 | 3 | 4 |
| **weighted total** | **≈63** | **≈68** | **≈88** |
| **HARD-GATE overlay** | **DISQUALIFIED** (OEEL-1 + held-course leak) | **DISQUALIFIED** (OEEL-1; patch-core to hide held) | **VIABLE** |

A/B are disqualified by the licensing gate regardless of points; C is the only license-clean, functionally-
complete option.

## Dispositions
- **State authority = MEZZE.** `mezze.kds.ticket` is already the sole authority; native isn't even fed →
  no two-state-machine conflict exists today, and the custom UI keeps Mezze authoritative.
- **`mezze.kds.ticket` + `/kds/state` + `/kds/transition` = KEEP** (they are the authority; the custom UI
  consumes them). Do NOT delete/adapt in V2B.
- **Order Status Screen = REJECT native** (OEEL-1); Mezze's own `/checkout/s/<token>` status page (LGPL-3)
  is the authority — already implemented.
- **Native = reference only** — its stage/timer/recall/cancel-qty patterns are a good design reference for
  the custom UI, consumed as ideas, not code.

## Gaps to fix WHEN the custom KDS UI is built (not in V2B)
1. **Order-void → KDS-cancel cascade** — voiding/refunding a pos.order currently leaves its fired tickets
   live on the board (Mezze KDS finding). Add a cascade or a clear-on-void.
2. **Item-level completion + priority + structured allergens** — Mezze KDS is station-level only; decide
   whether the product needs per-dish bump / rush / allergen fields.
3. **Late/alert timer** — Mezze derives wait time but has no per-stage alert threshold; add one for parity.

## KDS readiness (do NOT inflate before implementation)
Software: model+API mature (~70%); **production UI = 0% (does not exist)**. Decision made; implementation
is the NEXT phase. Cloud/Edge KDS readiness unchanged by V2B (no code shipped).

## Next phase
**V2C — Build the Mezze KDS production UI** (Owl, on the V2A cashier foundation: shared theme/RTL/dark/HC +
authenticated `browser_js` regression), consuming `/kds/state` + `/kds/transition`, authority =
`mezze.kds.ticket`. Reuse-first WITHIN Mezze's own stack (the cashier's proven Owl/theme/test harness), not
the Enterprise display.
