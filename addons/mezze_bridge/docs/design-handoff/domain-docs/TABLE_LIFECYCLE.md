# Table lifecycle

Contract between the prototype (`Mezze POS v3.dc.html` — 02 Floor) and the Odoo 19 implementation.

**The break:** a settled check sent the table straight back to *Available*. Nobody had cleared it. The
host saw a free table, walked a party to it, and found the last party's plates on it. The floor's own
state machine was lying about the only thing it exists to tell you.

```
before   seated → ordered → bill → PAID ─────────────────→ Available
after    seated → ordered → bill → PAID → Needs clearing → Ready
                                              │
                                              busser assigned · time waiting · turn time
```

---

## 1. The states

| State | Means | Seatable |
| --- | --- | --- |
| `free` — **Ready** | cleared, reset, checked | **yes** |
| `seated` | party sat, nothing ordered | no |
| `ordered` | in service | no |
| `bill` | bill asked for | no |
| `dirty` — **Needs clearing** | check settled, table not yet bussed | **no** |

`Needs clearing` is a real service state, not a cosmetic flag: the arrival queue's *Ready to seat*
reads it (`docs/ARRIVAL_QUEUE.md` §1), so a table that has not been cleared cannot be offered to a
guest by anything in the app.

## 2. One transition into clearing

Every path that settles a check goes through **`flToClearing(id)`** — the floor's own stage advance
*and* the handheld's capture. That one function is where the two numbers are captured, because a
transition written in two places is a turn time recorded twice and agreeing never.

| Captured | From |
| --- | --- |
| **Turn time** | how long the party had the table: the elapsed clock at the moment of settlement |
| **Time waiting** | how long it has sat needing clearing: from the moment of that transition |

## 3. What the floor gains

- **Clear table** — one action, on the table's own inspector. It records who cleared it, how long it
  waited and the turn it closes, then sets the table to *Ready*.
- **Assigned busser** — from the people actually clocked in. An unassigned dirty table is visible as
  unassigned; assignment is what makes "why is table 12 still dirty?" answerable.
- **Time waiting** — live, on the table and in the queue header, with the longest wait called out.
- **Turn time** — per table as it closes, and as a rolling average (`flTurnAvg()`) across the shift.
  This is the number a quoted wait should be built from.

Every clear writes a row to `flTurns`: table, turn, wait, who, when. Averages derive from it — there
is no stored average to drift.

## 4. Odoo mapping

| Design | Odoo 19 |
| --- | --- |
| Table state | `restaurant.table` + a POS-side state (Odoo has no bussing state — this is the extension) |
| Clear action | state write, with employee |
| Busser | `hr.employee` assignment on the table |
| Turn time | derived from order open/close timestamps on `pos.order` |
| Turn/clear averages | reporting over those rows, per zone and per shift |

Odoo's restaurant module treats a table as occupied or not. Bussing is the state it lacks, and it is
the state that decides whether the host is telling the truth.

## 5. Gaps

1. **No cleaning SLA.** A table waiting longer than a target should escalate to a manager; the wait is
   measured, the threshold is not set.
2. **Turn average is shift-wide** — it should be per zone and per party size before it can drive a
   quote.
3. **No pre-bussing signal.** A table at `bill` is about to need clearing; the busser could be walking
   over already.
4. **Clear does not check the deposit or the check** — settlement guards live on the check, and a
   table can be cleared while an unpaid balance sits on it if the settle path was skipped.

## 6. Acceptance

Settle a check: the table reads **Needs clearing**, not Available, and the arrival queue stops
offering it. Its inspector shows the turn time it just closed, a live *waiting to be cleared* clock,
and an unassigned busser. Assign a busser from the on-shift list: it reads their name. Tap **Clear
table**: the table becomes **Ready**, the wait and the turn are written to `flTurns`, and the queue's
*Ready to seat* rows recompute — a waiting party of 2 becomes seatable the moment a 2-top is cleared,
and not before.
