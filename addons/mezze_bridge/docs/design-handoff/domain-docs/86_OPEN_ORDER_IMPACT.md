# 86 → open-order impact

Contract between the prototype (`Mezze POS v3.dc.html` — the **86 impact** sheet) and the Odoo 19
implementation.

**The principle:** 86 is not a menu flag. It is an **incident**. The moment a dish runs out, the
branch has two problems, and the flag only solves one of them:

1. *Nobody else may order it* — availability. Solved today.
2. *The orders that already contain it will not be delivered* — impact. **This was the break.**

The workflow audit named it: marking Grilled Salmon 86 disabled future sales and told nobody about
the four open orders already carrying it. Those guests find out when a runner arrives without their
food, or worse, when nothing arrives at all. Every minute between the 86 and the conversation makes
the recovery more expensive — a substitution offered at minute one is service; the same offer at
minute twenty is a complaint.

So: **86 opens the impact sheet, and the flag is a side effect of it.**

---

## 1. What 86 does now

```
manager marks Grilled Salmon 86
        │
        ├─→ availability off, every channel, immediately   (the old behaviour, unchanged)
        │
        └─→ IMPACT SHEET, opened not offered
              scans every system of record for unserved lines of that dish
              lists each affected order with its stage, guest and value
              per order: Substitute · Refund · Contact guest · Keep · Comp replacement
              stays open — with an unresolved count in the top bar — until every line is answered
```

A 86 with unresolved lines is **not finished**, and the app says so from wherever you are.

## 2. What gets scanned

An order this scan misses is an order nobody is told about, so the sources are a **registry**, not a
list of ad-hoc lookups, and the sheet **names what it scanned**.

| Source | Held as | Stage read from |
| --- | --- | --- |
| Register checks | `state.checks[key].lines` | line `status`: NEW → *not fired*, FIRED/PREPARING → *with the kitchen*, SERVED, PAID |
| Handheld checks | `hhSent()` + `hhDraft` | draft → *not fired*, sent → *with the kitchen*, `hhServed` → *served*, `hhPaid` → *paid* |
| Drive-thru | `state.dt[].items` | `pos: order` → *not fired*, else *with the kitchen*; `paid` → *paid* |
| Order board (delivery, takeaway, catering) | `boardData().lines` | `state`/`paid` |
| Channel feed (Talabat, Elmenus, app, QR) | `CH_FEED[].items` | *not accepted yet* — refuse the line before it becomes an order |
| Kiosk and QR carts | `ksDraft`, `qrDraft` | *guest is still building it* — the tile turns unavailable under their hand, so the sheet says who is mid-order |

**The KDS is deliberately not a source.** Its tickets mirror the orders above; scanning it too would
double-count the same food. What the KDS gets instead is the 86 banner and the substitutions as
ticket amendments.

## 3. The five actions

Which are offered depends on the stage — the honest set, not all five everywhere.

| Action | Offered when | Does |
| --- | --- | --- |
| **Substitute** | not fired, with the kitchen | swap to an available dish; the price delta is shown and applied (cheaper → refund the difference, dearer → the guest agrees or it is comped) |
| **Contact guest** | any stage with a phone | call or message from the order's own contact record; the attempt is logged with who tried and when |
| **Keep** | not fired, with the kitchen | honour this one from remaining stock — an explicit decision with a name on it, and a running count of portions committed |
| **Comp replacement** | with the kitchen, served, paid | substitute *and* comp it, per `docs/COMP_ACCOUNTING.md`: full price line plus an offsetting comp, stock stays consumed |
| **Refund** | served, paid | back to the original tender, per `docs/PAYMENT_VALUE_ENGINE.md` §3 |

Rules that hold:

- **One resolution per line, and it is recorded.** Action, detail, who, when. A second tap on a
  resolved line does not re-resolve it.
- **Substitutions come from the same category, available now, closest in price** — a suggestion list,
  not a free-text field, because a substitution nobody can cook is a second 86.
- **Keep is not "ignore".** It commits a portion, and the sheet counts how many have been committed,
  so a manager cannot honour six orders out of two portions of stock without seeing it.
- **Contact does not resolve the line.** Reaching the guest is a step, not an outcome; the line stays
  open until a decision is recorded.

## 4. Why the dish went 86

The reason is required, because the reason decides what else has to happen: *sold out* implies a
stock count, *quality* implies a waste record, *equipment down* implies more than one dish and a
maintenance job.

`Sold out · Quality — batch rejected · Equipment down · Supplier failure · Prep not ready`

## 5. Coming back on

Un-86 is not the end of the incident either. If lines are still unresolved when the dish comes back,
the sheet stays reachable and the count stays in the top bar — the guests waiting on those four
orders do not stop waiting because the kitchen found more.

## 6. Odoo mapping

| Design | Odoo 19 |
| --- | --- |
| 86 flag | POS availability on `product.product` (never archive — that loses history) |
| Impact scan | query unserved `pos.order.line` / delivery lines by product, per session |
| Substitute | line replacement on the order, with the price difference as its own line |
| Comp replacement | comp line pattern from `docs/COMP_ACCOUNTING.md` |
| Refund | refund order linked to the original, original tender |
| Contact attempt | `mail.message` on the order / partner |
| 86 incident + reason | custom model, per branch per session, with resolution lines |
| Channel push-out | aggregator availability API per channel |

The incident is the model worth adding: an availability flag with no incident record cannot tell you,
next month, that Grilled Salmon went 86 nine times and cost 4,300 LE in comps.

## 7. Gaps

1. **Substitution rewrites the register check, not the other surfaces' orders.** On checks the line is
   actually swapped; elsewhere the resolution is recorded as the instruction and the surface's own
   order is not yet edited.
2. ~~Refund and comp record the decision and the amount, but do not post~~ — **closed, Pass 18B.**
   Comp posts to `compLog`, the same ledger the handheld comp flow writes and Plate cost already
   reads. Refund calls the canonical `ordRefundCommit()` — the same poster the Orders refund sheet and
   Guest Recovery's Refund remedy use — so a 86-impact refund reverses the proportional loyalty earn
   and posts a House-account credit note exactly as an Orders-initiated refund would.
3. **No stock link.** *Sold out* should offer to open a count on the ingredient that ran out, and
   *quality* a waste record.
4. **No forecast.** The sheet answers "who is affected"; it does not answer "how many portions are
   left", which is what decides Keep. Par levels are in Stock; the join is not built.
5. **Aggregator push-out is optimistic** — the channel screen shows the item as pushed out with no
   acknowledgement from the platform.

## 8. Acceptance

Mark a dish 86 with a reason. The sheet opens immediately, names every source it scanned, and lists
each affected order with its stage, guest, quantity and value — the register check that has not fired,
the handheld table whose lines are with the kitchen, the paid drive-thru car, the delivery order on
the board, the aggregator order not yet accepted, and the kiosk cart being built right now. Each row
offers only the actions its stage allows. Substitute a not-fired register line: the line changes on
the check, the price delta is stated, and the row reads resolved with the manager's name. Keep two
orders: the sheet says two portions committed. Leave one unresolved and navigate away: the top bar
carries the count, and tapping it reopens the sheet. Resolve the last line: the incident closes and
the chip disappears.
