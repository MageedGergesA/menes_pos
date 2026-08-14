# Drive-Thru — Current State Audit

**Base branch:** `feature/drive-thru-enterprise-ux` from `cc5a2cd`
(contains `mezze-v1.0-rc7` = `de27828` plus this session's work).
**Method:** repository inventory + live measurement against `mezze_fid` on :8210.
Nothing below is assumed; every claim was read from source or measured in Chrome.

---

## 0. The finding that shaped the plan

**At RC7 the drive-thru board has no Odoo route.** `static/drivethru.html` exists and
speaks to real endpoints, but nothing serves it, and its only way to authenticate was
`?token=` in the query string. It became reachable at `/mezze/drivethru` in commit
`ae23b04` and correctly themed in `cc5a2cd`. Phase 1 of the brief (open the current UI
in Chrome) is therefore only possible on this base — from `de27828` there is nothing
to open.

---

## 1. Backend — richer than the UI suggests

### Model `mezze.drivethru` (`models/drivethru.py`)

| Field | Type | Note |
|---|---|---|
| `pos_order_id` | m2o pos.order, required, cascade | a car IS a real order |
| `config_id` | related, stored | branch |
| `lane` | Integer, indexed, default 1 | **multi-lane is already modelled** |
| `vehicle` | Char | free text ("Red Corolla / plate") |
| `state` | Selection | `preparing → ready → at_window → collected`, plus `cancelled` |
| `partner_id` / `customer_name` | m2o / Char | optional identity |
| `note` | Char | |
| `placed_at` | Datetime, indexed | **server clock — timer authority** |
| `ready_at`, `window_at`, `collected_at` | Datetime | stage timestamps already captured |

Ordering is `lane asc, placed_at asc, id asc` — FIFO position per lane is derived, not stored.

**Derived truth already available:**
- `_kitchen_ready()` — every KDS ticket for the order is `ready`/`served`
- `_paid()` — `pos.order` state or `amount_paid >= amount_total`
- `_who()` — customer name, else partner, else vehicle

### Endpoints (`controllers/main.py`)

| Endpoint | Capability | Purpose |
|---|---|---|
| `drivethru/create` | ORDERS_WRITE | add a car; fires the order to the kitchen as a **draft** |
| `drivethru/board` | KITCHEN_READ | lanes + cars |
| `drivethru/stage` | ORDERS_WRITE | `ready` / `window` / `pay` / `collected` / `cancel` |

`/drivethru/board` per-car payload — this is the key discovery:

```
id, lane, position, vehicle, who, state,
order_id, tracking, total, items[],
kitchen_ready, paid,          <-- the three status tracks, server-truthful
placed_at, minutes, ready_at
```

**All three journeys the brief asks for are already backed by server truth.**
Vehicle stage = `state`; kitchen = `kitchen_ready` (from KDS tickets); payment = `paid`.
No status track has to be faked, and no schema change is needed to display them.

---

## 2. Existing screen

`static/drivethru.html` — a prototype page, now served and themed:

- flat topbar (brand, branch, live chip, `ع`, **+ New car**) — matches the Register since `cc5a2cd`
- lane heading (`Lane 1`, `N cars`) + a card list; empty state "No cars in this lane"
- a **New car** sheet: Lane 1 / Lane 2 chips, a free-text Vehicle input, a menu grid, **Send to kitchen**

It is **not** an Owl app: no shared shell, no rail, no component library. It talks to the
API with its own `fetch` helper.

---

## 3. Measured gaps (against the brief)

| # | Gap | Evidence |
|---|---|---|
| G1 | **No persistent queue.** One lane's cars listed; no cross-lane operational queue | `#lanes` renders per-lane blocks only |
| G2 | **Timer is present but tiny and coarse.** `0m` in the smallest type on the card, minutes only — not MM:SS, not scannable | measured 1440x900 |
| G3 | **No speed-of-service strip.** No count / avg / longest / target | absent |
| G5 | **No Order Taker cockpit.** The menu lives in a modal sheet, so taking an order hides the lane | `#menu` inside `.sheet` |
| G6 | **No Payment Window or Pickup screens.** `stage` supports `window`/`pay`/`collected`; no UI reaches them | endpoint vs UI |
| G7 | **Handoff guards payment but NOT kitchen.** `collected` returns 409 `unpaid`, but nothing blocks handing off food still being cooked | `drivethru_stage` |
| G8 | **Vehicle identity is one free-text field.** No fast colour/type entry; keyboard required | `<input>` in the sheet |
| G9 | **KDS shows no drive-thru identity.** Channel exists on the order; the ticket does not surface lane/vehicle | `kds_ticket.py` |
| G10 | **No role/workstation context.** Every terminal opens the same board | single route, no mode |
| G11 | **No OCB / confirmation surface.** | absent |
| G12 | **Lane kanban, not a queue.** Two side-by-side lane columns; no cross-lane ordering by urgency, and the brief explicitly rules out kanban columns | measured |
| G13 | **Page scrolls at 1280 and 1024.** The whole canvas scrolls, not a pane | `scrollHeight > innerHeight` at both |
| G14 | **Product codes leak into the board.** `display_name` prints `[GIFTCARD] Gift Card` | measured |

### Corrections to my first pass (measured, not assumed)

Two claims I wrote before opening the page were **wrong**, and the baseline
screenshot disproves them:

- ~~Kitchen and payment state invisible~~ — **both are rendered**, as `READY` and
  `PAID` / `PAYMENT DUE` badges on every card.
- ~~No stage-specific CTA~~ — the CTA **already changes by stage**: `Take payment ·
  USD 30` when unpaid, `Collected ✓` when paid, plus `Call forward`.

Vehicle identity is also already prominent (large caps, above the order number).
The board is a good deal further along than the brief's "current" description
assumes, and the work is therefore convergence and density, not invention.

---

## 4. What must NOT regress

- `mezze.drivethru` state machine and its timestamps
- the `unpaid` handoff guard (409)
- per-instance terminal identity (RC6 token-eviction fix) — the lane mints
  `drivethru-<config>` with `role='terminal'`
- `api_security=enforce`, capability gating on all three endpoints
- the theme contract added in `cc5a2cd` (server-stamped `data-mz-source`)

---

## 5. Timer authority

**SERVER.** `placed_at` is a server datetime and `minutes` is computed server-side.
The board polls, so elapsed time can be rendered client-side from `placed_at` without
inventing a second clock — the browser formats, the server decides.
