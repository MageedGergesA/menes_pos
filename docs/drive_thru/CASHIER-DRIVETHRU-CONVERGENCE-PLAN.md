# Cashier → Drive-Thru convergence plan

The current Drive-Thru Order Taker is rejected as the final order-entry UX. This plan
turns it into **the Mezze Cashier Register in drive-thru mode**, and it is written to be
reviewed before any large edit is made. Nothing in the repository has been changed by
this pass.

Everything below was measured today on the running branch (`d5507b0`, DB `mz_bench61d`,
port 8069), not recalled.

---

## 1. BEFORE — what the screen actually does today

`docs/drive_thru/shots/conv-before-drivethru-order-taker-1920.jpg`

Measured with the New-car panel open, CSS viewport 2494 × 1292:

| | measured | share of canvas |
|---|---|---|
| Lane queue (`#lanes`) | **2054 px** | **82.4 %** |
| Ordering panel (`.sheet`) | 440 px | 17.6 % |
| Catalogue column (`.mz-catalog`) | 399 px | 16.0 % |
| Product grid columns | **2** (`186px 186px`) | — |
| Category navigation | horizontal chips, 399 px wide, 13 chips overflowing sideways | — |
| Category sidebar | **absent** | — |
| Order/cart panel | `#cart`, **0 px tall when empty**, no header, **no totals row anywhere** | — |
| Queue rows on screen | 16, each ~65 px tall with full action sets | — |

So the complaint is confirmed by measurement, item by item:

* the queue consumes 82 % of the width;
* the catalogue is confined to a 399 px drawer;
* the grid is 2 columns where the Register is 11 at the same viewport;
* category navigation is compressed into a scrolling chip strip;
* there is **no cart/order hierarchy at all** — no order header, no line totals, no
  subtotal, no total, only a list of names with steppers;
* ordering is subordinate to lane monitoring, structurally and visually.

## 2. REFERENCE — what the Register actually is

`docs/drive_thru/shots/conv-reference-register-1920.jpg` (`/mezze/pos`, same viewport)

> Correction to the CONV-1 note: the Register **does** render in this database. The
> blank page recorded as an evidence gap was `/mezze/pos?ws=register`, not `/mezze/pos`.
> The side-by-side capture that pass could not produce now exists.

Measured composition at CSS 2494 px — the four panes sum exactly to the viewport:

```
[ rail 68 ][ category sidebar 201 ][ menu 1884 — 11 cols × 156, gap 12 ][ order panel 341 ]
```

| element | measured |
|---|---|
| icon rail `.mz-rail` | 68 px, ≥1280 only |
| category sidebar `.mz-catside` | 201 px (176 flex-basis + 2 × 12 padding + border), ≥1280 only, per-category counts |
| catalogue `.mz-catalog` | search bar 58 px → item-count line → grid |
| card `.mz-tile` | 156 × 247, square media, 12 px gutter |
| order panel `.mz-cart` | **341 px** (`flex:0 0 340px; max-width:44vw`) |
| chip bar `.mz-catbar` | `display:none` at this width — exactly one of sidebar/chips is ever visible |

The order panel, top to bottom: `mz-cart-head` (title + item count) → `mz-otype`
(Dine-in / Takeaway / Delivery) → `mz-custchip` → `mz-cart-lines` → `mz-cart-foot`
(3-column verb grid → subtotal when real → total → Charge).

Each line: `qty× · name · line total` / note sub-line / `[− n +] · unit each · Note · ✕`.

### Architecture

| | Register | Drive-Thru |
|---|---|---|
| Technology | **Owl app** in asset bundle `mezze_bridge.assets_cashier` | **static HTML page**, inline IIFE |
| Entry | `/mezze/pos` → `root.js` (3517 lines), 20 components | `/mezze/drivethru` → `static/drivethru.html` (1364 lines) |
| Product source | `/bootstrap` | `/bootstrap` — same |
| Pricing authority | server | server — same |
| Line identity | `order_store.js`, merges on **product id only** | `lineKey(id, sorted(attribute_value_ids))` |
| Configurator | **none** | the only production one in Mezze |
| Modes | rail destinations | `?mode=order\|payment\|pickup` → `body[data-mode]` |

---

## 3. The five reuse questions, answered

**Can the product browser be reused directly? — YES, and it already is.**
CONV-1 moved `.mz-grid` / `.mz-tile*` / `.mz-searchbar` / `.mz-catalog__count` out of the
cashier bundle into `static/design/product-browser.css`; both surfaces link that one file
and render the same markup. The drive-thru's cards are small today **only because the
column is 399 px**, not because the card is different. Widen the column and the same rules
produce the same card. Nothing to do here but give it space.

**Can the category browser be reused directly? — PARTIALLY; the rest must be extracted.**
The drive-thru already uses the Register's `.mz-catbar` chips — which is the Register's own
*narrow-viewport* form. The desktop form the user is asking for, the 176 px `.mz-catside`
sidebar with live per-category counts, is still inside `cashier.css` and therefore
unreachable from any page outside the bundle. → **extract to `static/design/category-nav.css`**
by the CONV-1 method (extract in place, keep bundle order, re-measure the Register).

**Can cart semantics be reused? — The PANEL yes, the STORE no, and this is deliberate.**
`order_store.js` merges lines on product id. Its own comments state that modifiers/notes
make lines "legitimately distinct … and must NOT merge", but nothing implements that,
because the Register has no configurator. The drive-thru's `lineKey(product_id, sorted(avids))`
is **strictly more correct** — importing the Register's store would be a regression that
silently merges a plain burger with a no-onion burger. So: adopt the Register's panel
(markup, hierarchy, geometry, line anatomy, stepper, totals) and **keep the drive-thru's
line identity**. `.mz-cart*` / `.mz-line*` / `.mz-total*` CSS → **extract to
`static/design/order-panel.css`**.

**Can the product configurator be reused? — Nothing to reuse; the direction is reversed.**
The Register has no configurator. The drive-thru's is the only production one. It stays
where it is; feeding it back into the Register is a later pass and is not in scope here.

**Can the pricing summary be reused? — YES, once extracted, and the drive-thru needs it.**
The drive-thru cart shows no money at all today. The server already prices the exact
cart through `/ocb/publish` → `_price_lines()` (the customer board is reading real
subtotal/tax/total from it right now). The order panel will render **that** figure — the
server's, the same one the customer sees — never a client-side sum. `.mz-cart-foot`
`.mz-trow` `.mz-total-*` come across with the panel.

### The one thing that genuinely cannot be shared

**Owl components cannot be imported into a static page.** `ProductGrid` and `Cart` are Owl
classes registered inside `assets_cashier`; consuming them means loading the whole cashier
bundle — the module loader, Owl, all of `@web/core` — into the lane board, which is also
the page an appliance browser loads at a window. So convergence is **one definition of the
canonical thing, consumed by both**, not "mount the Register's components".

Two ways to go further, stated plainly:

| | Option A — extraction (recommended) | Option B — rebuild the board as an Owl app |
|---|---|---|
| Product/category/cart CSS + markup | one shared definition, both surfaces | literally the same components |
| Work | additive; the board keeps its page, its poll, its timers | rewrite of a certified 1364-line surface |
| Blast radius | Order-Taker DOM only | payment, pickup, timers, OCB publish, queue, offline behaviour — all of which this brief says not to change |
| Deployment | unchanged (single self-contained page) | board now depends on the cashier bundle |
| Fidelity achieved | identical geometry, typography, card, chips, sidebar, line anatomy, totals; JS remains separate | identical everything |

Option B is a rewrite, and a rewrite needs both a technical justification and a reason
refactoring is insufficient. Neither holds here: extraction reaches the stated acceptance
criteria (looks and behaves like the Register), and the cost falls entirely on surfaces the
brief protects. **Recommendation: Option A**, with Option B left open as a later platform
decision if the drive-thru ever needs Register features that are pure Owl.

---

## 4. Target layout

Four panes, in the Register's own order, with the queue taking the rail's place:

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ DRIVE-THRU · L1 · RED SUV · 01:42 · OCB ● · 5 CARS          [Operations]     │
├──────────┬──────────────┬────────────────────────────────┬───────────────────┤
│ QUEUE    │ CATEGORIES   │ PRODUCTS                       │ CURRENT ORDER     │
│ 180–200  │ 201 (.mz-    │ .mz-catalog + .mz-grid         │ 341 (.mz-cart)    │
│ .qrow    │  catside)    │ canonical .mz-tile cards       │ canonical panel   │
│ compact  │              │                                │ CONFIRM & SEND    │
└──────────┴──────────────┴────────────────────────────────┴───────────────────┘
```

Breakpoints are **the Register's own**, not new ones: the category sidebar appears at
≥1280 and the horizontal chip bar takes over below it, and exactly one of the two is ever
visible.

| viewport | queue | categories | menu column | **product columns** | card | order panel |
|---|---|---|---|---|---|---|
| **1920** | 200 px rail | 201 px sidebar | 1146 px | **6** | 181 px | 341 px |
| **1440** | 180 px rail | 201 px sidebar | 686 px | **4** | 162 px | 341 px |
| **1280** | 180 px rail | 201 px sidebar | 526 px | **3** | 167 px | 341 px |
| **1024** | collapsed to a drawer (toggle in the top bar) | horizontal `.mz-catbar` | 651 px | **4** | 154 px | 341 px |

Columns are computed from the shipped rules — `minmax(154px,1fr)` with a 12 px gap and
16 px grid padding, dropping to `minmax(130px,1fr)` at ≤1100 px — using the same arithmetic
that reproduces the Register's measured 11 columns at 2494 px to within 1.5 px. They will be
re-measured in the browser, not assumed, when the layout lands.

For comparison the Register at the same widths is 7 / 4 / 3 / 4 columns. Same rhythm; the
drive-thru gives up one column at 1920 to keep the queue visible, and is identical from
1440 down.

Priority when space runs out, in order: **the queue narrows, then the queue collapses,
then the category sidebar folds into chips. The product grid and the order panel are never
sacrificed** — the order panel is a fixed 341 px at every width in this table.

## 5. The queue becomes secondary — and Operations gets its own workspace

**Nothing is deleted.** The current full-width board moves, verbatim, to
`/mezze/drivethru?mode=ops` — Lane Monitor / Operations, for the manager, expediter and
lane controller: 10–20 cars, full action sets, Call Forward, intervention.

The Order Taker keeps a compact rail of the same `.qrow` rows — 4–6 visible, lane · vehicle ·
timer · state, **no per-row action buttons** — plus an explicit **Open operations** control.
The active car never leaves the screen: it is in the top bar *and* the order-panel header.

Mode inventory after this pass (one UI never performs six roles):

| mode | surface |
|---|---|
| `?mode=order` *(default)* | **Order Taker — Register in drive-thru mode** |
| `?mode=ops` *(new)* | Operations / Lane Monitor — today's board, unchanged |
| `?mode=payment` | payment window — **untouched** |
| `?mode=pickup` | pickup window — **untouched** |
| `/mezze/kds` | kitchen — **untouched** |
| `/mezze/ocb/<token>` | customer display — **untouched** |

## 6. New Car stops owning the ordering surface

Today `#new` opens one drawer containing lane picker + vehicle field + cart + the whole
172-product catalogue. That is two sequential tasks fused into one narrow column.

Split them:

1. **Identify the car** — a short step: lane `[L1] [L2]`, vehicle (today's capture,
   unchanged), **Start order**.
2. **Take the order** — the step closes and the full four-pane workspace takes over.

The New Car step never contains the catalogue.

## 7. Capability restrictions, and how they are enforced

Kept: products, categories, search, configuration, variants, modifiers, combos (published
today, still not lane-configurable — an existing, recorded limit), quantity, notes,
pricing, total, send to kitchen. Added: vehicle, lane, timer, queue, OCB, drive-thru identity.

Not exposed: floor plan, tables, dine-in, reservations, waitlist, generic park, back-office
reports, refund administration, other service modes, admin/settings.

**Enforcement is structural, not CSS.** The lane board's only write path is
`/drivethru/create`; there is no table, reservation, park or refund endpoint reachable from
it, and the page is `auth='user'` scoped to a drive-thru config. Concretely, when the
canonical order panel is adopted the Register's verb grid is **not** carried over — no
Assign table, no Park order, no Split, no Fire, no order-type chips. The panel renders only
the verbs the drive-thru actually has. Nothing is hidden that a request could still reach.

"Customer, if appropriate" is **not** in this plan: the drive-thru has no customer endpoint
today, and adding one is a feature, not a convergence. Recorded as out of scope, not done.

## 8. Test blast radius, stated before the edit

31 UX tests, 17 customization tests, 32 OCB tests. Of the UX suite, 16 load the order-mode
URL and lean on `.qrow` (21 references) and `.qtime` (10).

| tests | expectation |
|---|---|
| `test_02`–`test_05` (queue order, timer prominence, elapsed arithmetic, tick, colour-independent late) | **survive**: the compact rail keeps `.qrow`/`.qtime` markup |
| `test_21`, `test_22`, `test_23` (row action buttons, call forward) | **re-point to `?mode=ops`** — the buttons move there with the board |
| `test_01` (ops strip metrics) | re-point or re-scope; the metrics also live in the new top bar |
| `test_06`, `test_24`–`test_26` (ordering, configurator, touch floor) | **stay**, selectors updated as the sheet becomes the workspace |
| payment (9), pickup (3), unknown-mode fallback (1) | **untouched** |

Re-pointing a certified test is a change to certified work, so it is listed here for
approval rather than done quietly. No assertion is weakened: the same behaviour is asserted
against the surface that now owns it. New tests cover the new layout, the four-pane
geometry at each breakpoint, the totals, and the ops/order split.

## 9. DECISION-1 — needs your call before implementation

The target sketch shows `#DT-184` in the order-panel header while the order is being taken.
Today no car and no order exist until **Send to kitchen**; the drive-thru number and the
timer both begin at that moment.

* **(a) Local draft (default if you say nothing).** Header reads `L1 · NEW CAR · draft`;
  the number appears after Send. No server behaviour changes, no test moves.
* **(b) Create on Start order.** The header shows a real `#DT-…` while ordering — and the
  car enters the queue, and the timer starts, when it *arrives* rather than when the order
  is sent. Arguably the truer drive-thru measurement, but it changes queue membership, ops
  metrics and timer semantics, all of which are certified.

I will build (a) unless you choose (b).

## 10. Phasing — reviewable steps, not one rewrite

| pass | scope | gate |
|---|---|---|
| **CONV-2a** | extract `.mz-catside` and `.mz-cart*`/`.mz-line*`/`.mz-total*` into shared design files; **Register re-measured, must be unchanged to the pixel** | full suite + Register browser suite |
| ↳ *done* | category sidebar extracted to `static/design/category-nav.css`; Register 0px delta at 1920/1440/1280/1024, LTR + RTL. See `CONV-2A-SHARED-FOUNDATION.md`. The **order panel did not move**: its rules are scattered across five regions of `cashier.css`, so it takes its own pass — folded into **CONV-2c**, with the `[data-mz-panel="left"]` ordering family travelling with it | — |
| **CONV-2b** | Order Taker shell: four panes, queue demoted to a rail, top bar with active car; Operations split to `?mode=ops` | new layout tests + re-pointed tests |
| **CONV-2c** | canonical order panel with server totals and CONFIRM & SEND; New Car reduced to an onboarding step | money parity vs `/ocb/publish` |
| **CONV-2d** | responsive 1920/1440/1280/1024, RTL, focus order, touch floor; side-by-side capture against the Register | measured captures at each width |

Not in this plan and not to be touched: Payment, Pickup, KDS, OCB, the Operations board's
own behaviour, RC7, and the known debts listed in the brief.
