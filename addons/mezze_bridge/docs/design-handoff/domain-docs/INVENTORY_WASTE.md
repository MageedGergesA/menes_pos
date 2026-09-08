# Inventory — waste & spoilage

Contract between the prototype (`Mezze POS v3.dc.html`, screen 15 Stock + the Kitchen header
action) and the Odoo 19 implementation. Waste is the first half of Priority 1: plate cost cannot be
trusted while food leaves the building unrecorded.

**The principle:** a waste record is a **stock move**, not a note. If it does not move quantity out
of a real location and post a real cost, it is decoration.

---

## 1. What the design captures

Every write-off carries all of it — the sheet refuses to save without the starred fields.

| Field | Design | Odoo |
| --- | --- | --- |
| Item * | Picked from 15 Stock | `product.product` |
| Quantity * | Keypad, stepper | `stock.move.line.qty_done` |
| Unit | Read from the item (kg / L / pack / bunch / tray) | `uom.uom` — must be the product's UoM or a convertible one |
| Reason * | 8 fixed reasons (below) | Move reference + a `mezze.waste.reason` selection |
| Station * | Grill / Fryer / Cold / Bar / Pastry / Store | Analytic account or `mezze.station` |
| Employee * | Any rostered name; defaults to the signed-in user | `hr.employee` |
| Related order | Optional, from the last few open orders | `pos.order` m2o, nullable |
| Photo | Optional attachment | `ir.attachment` on the move |
| Value | Computed live: `qty × product cost` | `stock.valuation.layer` |
| Approval | Manager PIN over the threshold | `write_uid` + approver field, logged |

**Reasons** (fixed list — do not let branches free-type; the whole point is aggregation):
`Spoiled` · `Dropped` · `Over-prepared` · `Returned` · `Burnt` · `Wrong preparation` ·
`Expired` · `Other`

Each reason carries a **fault class** in the prototype (`supply`, `handling`, `forecast`, `guest`,
`rotation`, `other`). That is what makes the number actionable: 4,000 LE of `Over-prepared` is a
forecasting conversation, the same money in `Dropped` is a training one. Keep the classification
server-side so reporting can group by it.

## 2. Stock move and waste location

- Create a **scrap location** per branch: `Virtual Locations/Mezze Waste/<branch>`, type
  *inventory loss*. Do **not** reuse the generic scrap location across branches — variance has to
  be attributable to a site.
- A waste record posts one `stock.move`: branch stock location → branch waste location, `done`,
  quantity as counted, with the reason on `origin` and the station/employee on the move.
- Never adjust `stock.quant` directly. An inventory adjustment has no reason, no employee and no
  cost history, which is exactly the hole this feature closes.
- `Returned` waste that came back from a guest still moves out of stock — the plate was made. If
  the order is also refunded, that is a separate `pos.order` reversal; do not net them.

## 3. Accounting

- Valuation: the move debits a **waste expense** account and credits inventory, at the product's
  cost method (moving average, per the Odoo product category).
- Waste expense must be its **own account**, not COGS. Rolling waste into COGS makes food cost look
  stable while margin quietly erodes — the reason this gap was raised against Syrve in the first
  place.
- Suggested chart: `5xxx Food waste — spoilage`, `5xxx Food waste — handling`, split by fault class
  if finance wants the granularity; otherwise one account and report by reason.
- Period close: waste posts on the date of the move, inside the POS session's day. It does **not**
  touch the session's cash reconciliation — it is stock, not money in a drawer.

## 4. Permissions

| Role | Can |
| --- | --- |
| Line cook / server | Log waste at their own station, up to the threshold |
| Shift lead | Log at any station, up to the threshold |
| Manager | Any station, any value; approves over-threshold; voids a mistaken record |
| Accountant | Read-only, plus the journal entries |

- Threshold is **per role**, set in Settings; the prototype ships 250 LE and shows the gate in the
  sheet. Over it, the record needs a manager PIN and stores the approver's name on the line.
- Nobody edits a posted waste record. A wrong one is **reversed** by a counter-move with a reason,
  leaving both entries visible. Editing history is how stock ledgers stop being evidence.
- A cook may not approve their own over-threshold waste, even if they hold the PIN — enforce
  `approver_id != employee_id` server-side, not in the UI.

## 5. Cost calculation

- Value at the moment of the move: `qty × cost` where `cost` is the product's current cost, taken
  from the valuation layer rather than recomputed later. Waste valued at today's price for a move
  three weeks old is a reporting bug.
- **Prepared items** are the hard case. Wasting 2 kg of a cooked batch is not 2 kg of raw lamb: it
  is the batch's BoM cost. Two options, and this needs a decision before build:
  1. Waste raw components only — simple, but the line has to know the recipe to log a burnt tray.
  2. Give prepared batches their own storable product with a cost from the BoM — accurate, and it
     is what makes the commissary's own production costing work. **Recommended.**
- Plate cost then reads: theoretical cost from the BoM, actual cost from issues **plus waste**, and
  the gap between them is the number a chef can act on. Without waste in that equation the gap is
  invisible, which is the current state.

## 6. Station and order attribution

- Station is mandatory because waste without a location is unactionable. `Store` covers deliveries
  and dry-goods spoilage that belong to no cooking station.
- The related order is optional and rare — it exists for remakes, returns and burnt plates, where
  one specific ticket caused the loss. When set, it should surface on the order's own audit trail,
  so a manager reviewing a comped order sees the food it cost.
- Report at least: waste by reason, by station, by employee, by item, by day-part. Employee
  reporting is deliberately last and should be framed as coaching, not policing — a branch that
  punishes logging gets under-logging, and then the costing is worthless again.

## 7. Acceptance

Log 1.2 kg of chicken as `Over-prepared` at Grill under a cook's name: branch on-hand falls 1.2 kg,
the waste location rises 1.2 kg, an expense entry of `1.2 × cost` posts to the waste account, and
the line appears in the day's waste history with station, employee and time. Log 2.4 kg of lamb —
over the threshold — and it cannot save without a manager PIN, which is then stored on the record.
Reverse it and both moves remain visible. Plate cost for Mixed Grill moves by exactly the wasted
value, and the theoretical-vs-actual gap closes by the same amount.
