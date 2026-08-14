# KDS × Drive-Thru — gap audit (DT-UX5 preparation, **no implementation**)

Audited on `feature/drive-thru-enterprise-ux` at `88597e6` + DT-UX3.
Nothing in this document has been implemented.

## 1. How is source/channel represented?

`pos.order.mezze_channel` (Char) — documented values `qr | pickup | delivery |
drivethru | aggregator | kiosk | pos`. `mezze.kds.ticket._payload()` already sends
it to the board:

```python
channel = order.mezze_channel or ('dine_in' if self.table_label else 'counter')
```

So the KDS payload **already carries a channel field** and the board can already
distinguish a drive-thru ticket in principle.

**But — measured gap:** `/drivethru/create` does **not** stamp `mezze_channel`. It
fires the order through the shared `_do_fire` path with no table, so the ticket
falls through to `'counter'`. A drive-thru ticket is therefore
**indistinguishable from a counter ticket today**, even though the field exists.
This is the single highest-value fix and it is one assignment.

## 2. Can KDS resolve `mezze.drivethru` from `pos.order`?

Yes, but only by searching: `mezze.drivethru.pos_order_id` is a `Many2one` with an
index, and there is **no inverse field** on `pos.order`. A ticket can find its car
with one indexed search; it cannot traverse a relation.

## 3. What is already in the ticket payload?

`id, order_id, uuid, tracking, channel, station, state, course, table_label,
server_name, guests, fired_at` + lines. Timestamps for every state
(`fired_at → accepted_at → preparing_at → ready_at → served_at`).

**Absent:** `lane`, `vehicle`, and the drive-thru elapsed clock (`placed_at`).

## 4. Minimal addition to expose lane / vehicle / drive-thru identity

Two changes, no duplicated truth:

1. **Stamp the channel at creation** — `drivethru_create` sets
   `mezze_channel = 'drivethru'` on the order. One line; makes every existing
   consumer (KDS badge, reporting, analytics by channel) correct at once.
2. **Add a narrow drive-thru block to `_payload()`**, resolved only when the
   channel says drive-thru:

   ```
   'drivethru': {'lane': …, 'vehicle': …, 'placed_at': …}   # or absent
   ```

   Read from `mezze.drivethru`, not copied onto the ticket — the car record stays
   the single source of truth, and a ticket that outlives its car degrades to
   absent rather than to a stale label.

**Explicitly not proposed:** denormalising `lane`/`vehicle` onto
`mezze.kds.ticket`. It would duplicate order truth, and the brief forbids exactly
that.

## 5. Sorting

`mezze.kds.ticket._order` and the board's sort were **not changed** and must not be
changed casually: drive-thru queue order and kitchen priority are different
concepts. If DT-UX5 wants the kitchen to see lane sequence, it should be shown as
information on the ticket, not by silently reordering the kitchen's work.

## 6. Was any of this needed for the handoff gate?

**No.** `_kitchen_ready()` already derives readiness from the order's KDS tickets,
so the DT-UX3 safety gate needed no KDS change at all.


---

# DT-UX5 outcome (this document's gaps, closed)

| Gap recorded above | Status |
|---|---|
| `/drivethru/create` never stamps `mezze_channel` | **CLOSED** — stamps `'drivethru'` on the order |
| ticket payload lacks lane / vehicle / clock basis | **CLOSED** — `drivethru{id, lane, vehicle, state, placed_at}`, present only on drive-thru tickets |
| resolution would be N+1 | **CLOSED** — one `_drivethru_map()` per recordset, passed through context; rendering 14 tickets performs **0** extra car lookups |
| denormalising lane/vehicle onto the ticket | **NOT DONE, deliberately** — read from the car relation, so identity cannot go stale and pre-stamp orders still resolve |
| KDS sorting | **UNCHANGED, deliberately** — see below |

## Car-order sorting — NOT AUTHORITATIVE

The brief asked whether Mezze can express true physical car sequence. Measured
answer: **it cannot, and DT-UX5 did not pretend otherwise.**

What exists:

| Fact | What it can express |
|---|---|
| `placed_at` | when the order was taken — **age**, not position |
| `lane` | which lane, not position within it |
| `state` incl. `at_window` | that a car reached the window — the ONLY authoritative physical fact |
| `window_at` | when it reached the window |
| creation sequence | arrival order *per lane*, assuming nobody leaves or is parked |

What does **not** exist: any position index, any pull-forward/park concept, and
any merge rule between lanes. Two lanes merging at one window is a physical
reality the data cannot describe.

So the three concepts are kept separate rather than collapsed onto one field:

- **Kitchen priority** — existing KDS order, deliberately unchanged. Drive-thru
  work is not reordered ahead of other channels.
- **Physical car order** — expressed only where it is real: `at_window` (the car
  is here) drives Payment and Pickup selection. Elsewhere it is **NOT
  REPRESENTABLE**.
- **Elapsed urgency** — `placed_at`, shown as the queue's sort and the timer.

**CAR-ORDER SORTING NOT YET AUTHORITATIVE** is recorded as a capability gap. A
truthful label beats a false sequence: sorting the kitchen by "car order" derived
from age would tell cooks a car is ahead when the product cannot know that.

Closing it properly needs a business decision first (does the branch park cars?
how do two lanes merge?), then a position field — not a heuristic.
