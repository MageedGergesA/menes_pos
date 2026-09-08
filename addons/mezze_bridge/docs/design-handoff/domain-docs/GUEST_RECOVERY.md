# Guest recovery

Contract between the prototype (`Mezze POS v3.dc.html` — the **Make it right** sheet) and the Odoo 19
implementation. It joins six things that already existed and never spoke to each other: **Guests ·
Orders · Comp · Refund · Loyalty · Exceptions**.

**The principle:** a complaint is not a note, and a remedy is not a discount. A recovery is **one
record** that names what went wrong, which order and item it happened to, what was done about it, what
that cost the branch, and who signed for it. Every one of those facts already existed in the app —
in five different places, with nothing joining them.

The broken chain the audit found: a complaint was logged as free text on the guest record and died
there. The comp that settled it lived on a check. The refund lived on an order. The goodwill points
lived on a loyalty balance. The exception report counted the comp but knew nothing about the
complaint. **Nobody could answer "what did making that right cost us?"** — the most useful question in
service recovery, and the only one none of the five places could answer alone.

---

## 1. The chain

```
complaint (guest record, or straight from an order)
   │
   ├─ reason ........... what went wrong, and whose it is  (kitchen / service / billing / supply)
   ├─ affected .......... which order, which item, how many
   ├─ remedy ............ Remake · Comp · Refund · Voucher · Loyalty points · Apology only
   ├─ cost .............. computed BEFORE it is committed, from one function
   └─ approval .......... over the threshold, or an allergen, a manager signs
        │
        └─→ ONE recovery record, and it writes through to:
              the guest record   (the complaint, now with its remedy and cost)
              the order          (comp / refund / remake against the line)
              the loyalty ledger (goodwill points, as an adjust row with a reason)
              gift cards         (a voucher, as a real card and a real liability)
              Exceptions         (the event, with cost and approver, under the right person)
```

Nothing is offered that the record cannot carry. If a remedy cannot be executed, the recovery says so
rather than pretending.

## 2. Complaint reasons

The reason carries the **fault owner**, because a recovery that names no owner teaches the branch
nothing, and a suggested remedy, because at the table there are thirty seconds to decide.

| Reason | Owner | Suggests |
| --- | --- | --- |
| Wrong item served | kitchen | Remake |
| Late — long wait | service | Comp |
| Cold food | service | Remake |
| Quality below standard | kitchen | Remake |
| **Allergen mishandled** | kitchen | Refund — **always a manager**, whatever it costs |
| Service — staff attitude | service | Voucher |
| Billing error | billing | Refund |
| Missing item | service | Refund |

Allergen is not a service complaint. It is an incident: senior approval regardless of value, and it
belongs in the same report as voids and comps, not in a comment field.

## 3. The six remedies

| Remedy | Moves | Needs |
| --- | --- | --- |
| **Remake** | the kitchen makes it again; the guest still pays. The branch eats the ingredients twice | the item |
| **Comp** | the line keeps its full price and an offsetting comp line is written — gross sales unchanged, **stock still consumed** (`docs/COMP_ACCOUNTING.md`) | the item |
| **Refund** | back to the original tender (`docs/PAYMENT_VALUE_ENGINE.md` §3). Revenue reversed *and* the food is gone | a settled line |
| **Voucher** | a real gift card: a liability now, a cost when redeemed, breakage if it never is | an amount |
| **Loyalty points** | a goodwill `adjust` row on the loyalty ledger, with the reason on it (`docs/LOYALTY_ENGINE.md`) | a guest |
| **Apology only** | no money moves — and it is still recorded, because a pattern of apologies is a pattern | nothing |

## 4. Recovery cost — one computation

The number the branch has never had. Three components, **added, never netted**:

| Component | Meaning |
| --- | --- |
| **Revenue given up** | price × qty the branch will not keep (comp, refund) |
| **Food consumed** | recipe cost of the plate that was made and cannot be sold (remake, comp, refund of served food) |
| **Liability issued** | face value of a voucher, or the cash value of goodwill points |

```
Remake         food only        — revenue is still collected
Comp           revenue + food   — the classic double cost, and why comp is not a discount
Refund         revenue + food   — worst case: the money goes back and the food is gone
Voucher        liability        — deferred: a cost on the day it is redeemed
Points         liability        — points ÷ 10 = LE, from the loyalty rate
Apology        nothing          — a real zero, recorded as a real event
```

`rcQuote()` computes it and **the preview and the posted record are the same call** — the figure a
manager approves is the figure that lands in Exceptions. Food cost comes from the same `compCostOf()`
the comp and refire flows use, so one plate cannot be valued two ways.

## 5. Approval

- Over `RC_LIMIT` (300 LE of total recovery cost) → a manager PIN.
- Allergen mishandled → a manager PIN **always**, at any value.
- The approver's name is on the record, and the record is not editable afterwards; a correction is a
  new linked recovery.

## 6. What it writes

| Target | Written |
| --- | --- |
| Guest record | the complaint entry, its remedy, cost and reference — and the originating complaint is closed by the recovery, not by hand |
| Loyalty ledger | `adjust` row, reason `Service recovery`, for a points remedy |
| Gift cards | a real card number and balance for a voucher remedy |
| Exceptions | one event under the fault owner's name, carrying the recovery cost and the approver |
| Recovery ledger | the record itself: `rcLog`, append-only |

## 7. Odoo mapping

| Design | Odoo 19 |
| --- | --- |
| Recovery record | custom model, linked to `res.partner` + `pos.order` |
| Complaint | `mail.message` / CRM-style log on the partner, closed by the recovery |
| Comp | comp line pattern on the order |
| Refund | refund order, original tender |
| Voucher | `loyalty.card` (gift-card programme) |
| Points | `loyalty.history` adjust entry |
| Exceptions | POS exception reporting, filtered on the recovery model |
| Cost | recipe BoM cost of the affected product |

The model worth adding is the recovery itself. Without it, the same six facts stay in six places and
the branch cannot cost its own goodwill.

## 8. What the prototype does

- `RC_REASONS` / `RC_REMEDIES` — reason with owner and suggested remedy; remedy with what it needs.
- `rcQuote(draft)` — the one cost function: revenue, food, liability, total, and a line-by-line
  explanation shown in the sheet before anything is committed.
- `rcCreate()` — validates, demands the PIN where required, executes what it can (points via
  `loyAdjust`, voucher via `gcIssue`), writes the recovery row, the guest complaint entry and the
  Exceptions event, and closes the originating complaint.
- **Make it right** opens from a guest record, from an open complaint on that record, and from an
  order — prefilled with whatever context it was opened from.
- The Exceptions screen merges recovery events into the person's event list, so a comp that settled a
  complaint reads as a recovery with a cost, not as an unexplained comp.

## 9. Gaps

1. ~~Comp, refund and remake record the decision and the cost; they do not yet post~~ — **closed,
   Pass 18B.** Comp and Remake now write to the SAME ledgers the handheld's own comp/refire flows
   write to (`compLog` / `rfLog`) — tagged with the recovery's own reference (`rc`) — so Plate cost's
   existing Comps and Refires panels pick them up with no new cost ledger. Refund calls the one
   canonical poster, `ordRefundCommit()`, shared with the Orders refund sheet and the 86-impact sheet
   — it reverses the proportional loyalty earn (`docs/LOYALTY_ENGINE.md` §9) and posts a House-account
   credit note when that was the original tender.
2. **No item picker for orders opened from the board** — the sheet takes the order's own lines, but a
   recovery against a specific modifier or a half-eaten plate is coarser than reality.
3. **Recovery cost now reads INTO Plate cost** rather than sitting beside it — Comp/Remake post to
   the ledgers Plate cost already aggregates, so goodwill is visible as a cost of doing business
   without a separate P&L line to keep in sync.
4. ~~Substitution pricing policy~~ — **frozen, Pass 18C. MEZZE POLICY (not native Odoo):** the guest
   never pays more because of a restaurant-caused recovery substitution —
   `charge = min(original configured price, replacement configured price)`. A cheaper replacement
   passes its saving to the guest; a dearer one is absorbed by the branch. This lives in the
   86-impact sheet today (`e86Resolve`, the only place Substitute is offered — Guest Recovery's own
   remedy set is Remake/Comp/Refund/Voucher/Points/Apology and was not extended with a duplicate
   Substitute remedy). Customer price and food cost are tracked separately: swapping the check line
   never invents a "sum of both dishes' cost" — if the original was already **with the kitchen**
   when substituted, that prep's real cost posts once to `rfLog` (the same ledger a remake writes,
   category `REFIRE_REMAKE`/`RECOVERY_SUBSTITUTION`); if it was never fired, only the replacement's
   normal cost exists. **Open**: this does not yet re-ticket the KDS with the replacement — the
   check line changes, but no amendment ticket fires. That is real kitchen-flow work, not a pricing
   or costing gap, and is flagged for the next pass rather than built here.
4. **No follow-up.** A recovery should be able to schedule a call-back and mark whether the guest
   returned — that is the only measure of whether the recovery worked.

## 10. Acceptance

Open **Make it right** from a guest with an open complaint: the reason is prefilled from the
complaint, the guest's last order and its lines are offered, and the suggested remedy is preselected.
Pick Comp on a 320 LE Mixed Grill: the cost panel reads revenue 320.00 + food 118.60 = **438.60**,
and states that stock stays consumed. Switch to Remake: revenue 0, food 118.60. Switch to Voucher
200: liability 200.00, with the note that it costs the branch on redemption. Switch to Apology only:
0.00, and the record is still written. Any recovery over 300 LE, and any allergen complaint at any
value, refuses without a manager PIN. Confirm: the guest record shows the complaint closed with its
remedy and cost, the loyalty ledger carries the points row if points were given, a voucher appears as
a real card, and the Exceptions screen shows the event under the fault owner with the same cost figure
the manager approved.
