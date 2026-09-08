# Delivery engine

The dispatch board Mezze already had is at market parity: orders arrive, a rider is assigned, the row
turns *With rider*. Everything that happens **after** that — the part where the food, the money and
the promise actually live — was outside the system. This document is that part: the rider's own
device, the route, the proof, the failures, the cash, and what the guest is told while it happens.

**The principle:** delivery is not a status on an order. It is a *run* — one rider, several drops,
one cash bag, one settlement — and every screen reads the same run. The rider app is a client of the
order board, not a second system with its own orders.

**Built:** screen 34 Rider (two tabs — **Rider app** and **Settlement**) in `Mezze POS v3.dc.html`.

---

## 1. The run

A run is what a rider leaves the branch with.

| Part | Rule |
| --- | --- |
| **Stops** | one per order, sequenced; a rider can add a *ready* order to an open run before leaving |
| **Sequence** | distance order by default, editable — the rider knows the street better than the router |
| **State per stop** | `enroute → arrived → delivered` or `enroute → arrived → failed`, never skipped |
| **Cash bag** | the sum of what the rider has actually collected, per stop, visible at all times |
| **Close** | a run closes only when every stop is delivered or failed *and* the bag is handed over |
| **Who owns state** | the rider app owns per-stop state; the dispatch board keeps the order *with rider* until the run is **settled**, because that is the moment the branch holds both the proof and the money |

**Multi-drop is the normal case, not an optimisation.** Two drops in the same zone leave together or
the second one is late by construction. The app therefore shows the whole run, with each stop's own
promise, rather than one order at a time.

## 2. GPS, route and estimated arrival

- **The rider's position is the only live input.** Everything else — ETA, "on the way", the guest's
  tracking page — is derived from it, so there is one truth and no fake progress bar.
- **ETA per stop** = travel time from the current point through the remaining sequence
  (distance × pace) + a fixed handover per stop. It is recomputed as the run moves.
- **The promise is not the ETA.** The promise was made when the order was accepted; the ETA is what
  is actually going to happen. When the ETA passes the promise, the stop turns late *before* the
  guest calls, and dispatch sees the same thing the rider does.
- **The guest sees the rider's ETA**, not an average — the number on the tracking page is the number
  on the rider's screen.

## 3. Proof of delivery

One of three, chosen by what the order needs rather than by rider preference:

| Proof | When it is required |
| --- | --- |
| **Photo at the door** | the default; timestamped and stamped with the GPS point |
| **Four-digit code** | when the order was prepaid — a link, a card, points; the code is the receipt |
| **Signature** | corporate drops where a reception signs for a floor |

Proof is attached to the order, not to the rider's phone: it survives the shift, and a chargeback
argument is settled from the order, not from a photo roll.

## 4. Failed delivery

A failure is a decision with two consequences — one for the food, one for the money — and the app
makes both explicit rather than leaving a rider to improvise.

| Reason | The food | The money |
| --- | --- | --- |
| No answer after three calls | returns to the branch, held 30 minutes | nothing collected; order held, then written off |
| Address does not exist | returns to the branch | nothing collected; the address is flagged on the guest record |
| Guest refused it | waste, with a reason | refund if prepaid, and a recovery on the guest record |
| Cannot reach the door | returns to the branch | nothing collected; dispatch re-books |

Every failure writes the reason, the GPS point and the time. **A failed drop is not a deleted
order** — it stays on the board with its reason, which is how the branch learns that one building
fails twice a week.

## 5. Cash collection

- **Cash on delivery is a tender captured away from the till,** so the rider's bag is a drawer that
  walks. It is counted at hand-over like any drawer, against what the orders say it should be.
- The rider collects **the board total** — items plus the delivery fee, VAT included — never a number
  recomputed on the phone.
- Change carried out and change given back are the rider's float, declared at the start of the run.
- A prepaid stop shows **nothing to collect**, in words, so a rider cannot ask twice.

## 6. Rider settlement

At hand-over, per rider, for the run:

| Line | Where it comes from |
| --- | --- |
| Drops delivered / failed | the run |
| Cash expected | the sum of unpaid stops delivered |
| Cash counted | typed at hand-over by the cashier, not by the rider |
| Variance | counted − expected; over and short are both exceptions with a reason |
| Card at the door | settled by the terminal, informational here |
| Rider payout | per drop + per km — a **cost**, kept apart from the delivery fee |
| Sign-off | the cashier signs; it posts to the session and shows on Reconcile |

**The delivery fee is revenue, the rider payout is a cost, and they are not the same number.** A
25 LE fee against a 12 LE + distance payout is the margin on the drop; conflating them is how
delivery looks profitable when it is not.

## 7. Customer tracking

The guest sees the run, one stage behind the kitchen and one stage ahead of the door:

`accepted → preparing → ready → rider on the way → delivered`

- Every stage comes from a real event — the KDS bump, the pickup scan, the rider's position, the
  proof of delivery. No stage is on a timer.
- The **rider's name and the live ETA** appear at *rider on the way*; the phone number is masked.
- A failed delivery tells the guest what happens next, in words, on the same page.

## 8. Odoo mapping

| Design | Odoo 19 |
| --- | --- |
| Run | a delivery batch (`stock.picking.batch`-shaped) per rider per shift |
| Stop | the `pos.order` / `sale.order` and its delivery address |
| Rider | `hr.employee` with a rider role; attendance for the shift |
| GPS point | a position log on the run, written by the rider app |
| Proof of delivery | attachment + `pos.order` field (photo, OTP verified, signature) |
| Failure reason | a reason model on the stop, plus a stock move back to the branch or to waste |
| Cash collected | POS payment of type *Cash* captured on the rider's session |
| Hand-over | a cash-in from the rider's bag to the branch drawer, on the session |
| Rider payout | employee expense / payout line per run |
| Tracking page | Website portal on the order, reading the run's state |

## 9. Gaps

1. **Position is simulated.** The rider dot advances on the session clock, not on a real GPS feed;
   the app is shaped for one (a position log per run) but there is nothing writing to it.
2. **The route is not routed.** Sequence is distance order, not a road network — a real router
   (OSRM or the map provider) belongs behind the same interface.
3. **Aggregator drops.** Talabat and Elmenus riders are not ours; those stops appear on the board but
   the run, the proof and the cash are theirs. The design treats them as read-only.
4. **Zone-level distance.** Kilometres come from the zone, not from the address pin — the same map-pin
   gap as `ONLINE_ORDERING.md` §6.
5. **No rider chat.** Dispatch and rider talk by phone today; a message thread on the run is the
   obvious next surface.

## 10. Acceptance

Open the rider app on a rider who is out with two drops, add a third *ready* order to the run before
leaving, and watch the sequence, each stop's own promise and a live ETA per stop. Arrive at the first
stop, take a photo as proof, and see the stop close with nothing to collect because it was prepaid.
Arrive at the second, collect the board total in cash, and watch the bag grow by exactly that number.
Fail the third for *no answer after three calls* and see both consequences stated — food back to the
branch, nothing collected, reason and time on the order. Switch to Settlement, count the bag, and
watch expected, counted and variance reconcile, with the rider payout shown as a cost beside the fee
as revenue. Sign it off, and see the tracking card show the guest exactly what the rider's screen
said.
