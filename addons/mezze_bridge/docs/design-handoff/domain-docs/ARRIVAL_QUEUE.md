# Arrival queue

Contract between the prototype (`Mezze POS v3.dc.html` — the **Arrival queue** panel inside 02 Floor)
and the Odoo 19 implementation.

**The principle:** a booking, a walk-in on the waitlist and a party already sitting down are **the same
event at different stages**. The host was reading three lists to answer one question — *who is next?*
— and no list knew about the other two. So there is one queue, derived from all three sources, and it
lives **inside Floor**, next to the tables it is about. No new module: a host who has to switch
screens to decide where a party goes will guess instead.

---

## 1. The six stages

Derived, never stored — `aqStage(row)` reads the source's own state plus the clock plus the floor:

| Stage | Means | From |
| --- | --- | --- |
| **Arriving** | booked within the next 20 minutes, not here yet | booking |
| **Waiting** | here and unseated — a booking marked *arrived*, or a walk-in on the list | booking · walk-in |
| **Late** | more than 10 minutes past the booked time, still not here | booking |
| **Ready to seat** | waiting **and** a clean table of the right size exists right now | booking · walk-in |
| **Seated** | at a table | booking · walk-in |
| **No-show** | given up on, or walked off the list | booking · walk-in |

Two of those are the point of the whole exercise:

- **Ready to seat is a computed answer, not a wish.** It requires a table at `Ready` — not one that is
  still `Needs clearing` (`docs/TABLE_LIFECYCLE.md`). A queue that says "ready" while the table is
  covered in plates is how a party gets walked to a dirty table.
- **Late is not No-show.** Late is a prompt to call; no-show is a decision, taken by a person, after
  `AQ_NOSHOW` (25 min) — and the queue asks rather than deciding on its own, because releasing a
  table is a commercial choice.

## 2. What the host can do from the row

| Action | On | Does |
| --- | --- | --- |
| **Seat now** | any waiting party | takes the smallest clean table that fits — least waste, not first found — seats them, and clears them from the queue |
| **Mark arrived** | a booking | *Arriving* / *Late* → *Waiting*, so the wait clock starts from when they actually got here |
| **+5 min** | a walk-in | extends the quote, on the record, so quoted-versus-actual stays honest |
| **No-show** | a late booking | releases the table it was holding, and logs who decided |
| **Add walk-in** | — | party size in one tap; they enter the queue as *Waiting* |

Every action writes back to the source it came from — bookings to `bkStatus`, walk-ins to the
waitlist, seating through the floor's own `flSeat` — so the queue never becomes a fourth place where
arrival state lives.

## 3. Sorting and counts

Stage first (Ready to seat, then Late, then Waiting longest, then Arriving), then time waited
descending. The chips carry live counts, and a party over its quoted wait is marked — the number the
host is judged on is *quoted versus actual*, so it is on screen rather than in a report.

Bookings further out than the horizon are counted (`N more tonight`) but not listed: a queue that
shows the 21:30 table at 18:00 is a diary, not a queue.

## 4. Odoo mapping

| Design | Odoo 19 |
| --- | --- |
| Booking | `restaurant.booking`-style model (custom in 19), partner-linked |
| Walk-in | the same model with no advance time — a walk-in **is** a booking made at the door |
| Waitlist quote | field on the record, plus quoted-vs-actual for reporting |
| Seating | `restaurant.table` assignment, the same call the floor uses |
| No-show | state on the record, with the decider |

Modelling a walk-in as a booking made at the door is what lets one queue exist at all.

## 5. Gaps

1. **No SMS.** "Your table is ready" belongs on the Ready-to-seat action; the channel exists in
   Marketing but is not wired here.
2. **Quote is manual.** A real quote comes from turn time and the number of parties ahead —
   `flTurnAvg()` now exists (`docs/TABLE_LIFECYCLE.md`), so the estimate is computable and not yet
   computed.
3. **One floor.** The queue reads every zone; a branch that wants "bar only" needs a zone filter.
4. **No party-size splitting** (a 6 into two 3s), which real hosts do at the door.

## 6. Acceptance

The panel lists bookings, walk-ins and seated parties as one queue with the six stage chips and live
counts. A booking 14 minutes past its time reads **Late**, not No-show, and offers a call. Marking it
arrived moves it to **Waiting** and starts its wait clock. A party of 2 with a clean 2-top free reads
**Ready to seat**; mark that table *Needs clearing* and the same row falls back to **Waiting** in the
same breath. Seat now takes the smallest table that fits, seats the party, and the row moves to
**Seated**. A walk-in over its quote is marked. Nothing in the panel is a second copy of arrival
state — every action writes back to bookings, the waitlist or the floor.
