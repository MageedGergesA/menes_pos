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
