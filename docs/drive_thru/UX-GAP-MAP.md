# Drive-Thru — Current → Target

Every row was measured on `/mezze/drivethru` at 1440×900 with **8 cars across 2
lanes**, not with two fixtures. Rows marked *already there* exist today and are
kept — they are listed so the plan is not mistaken for a rewrite.

| # | Current (measured) | Target | Why it matters in a rush |
|---|---|---|---|
| 1 | Two lane **columns** side by side | One compact **vertical queue**, cross-lane, ordered by urgency, lane shown as a marker | At 8 cars the columns still read; at 15 they do not, and columns hide *who is worst* |
| 2 | Elapsed = `0m`, smallest type on the card | `01:42` as one of the strongest values, MM:SS, tabular | The timer is the operational signal; minutes-only cannot show a car sliding past target |
| 3 | No operations strip | Count / avg / longest / target, compact, no charts | "How is the lane doing?" has no answer today |
| 4 | Menu opens in a modal sheet, covering the lane | Three-zone cockpit: queue │ menu │ active order — queue stays visible while ordering | Taking an order currently blinds the operator to the lane |
| 5 | Vehicle = one free-text input, keyboard required | Colour + type chips, two taps, free text still available | Keyboard entry at a speaker box is the slowest possible path |
| 6 | One board for every role | Order Taker / Payment / Pickup modes on one shared queue | A payment window should not open into order taking |
| 7 | Handoff blocked on **unpaid** only (409) | Blocked on unpaid **or** kitchen not ready, with the exact reason | Handing out food that is still cooking is the expensive error |
| 8 | KDS ticket shows no lane/vehicle | `DRIVE-THRU · L1 · RED SUV · #DT-184` on the ticket | The kitchen cannot match a bag to a car |
| 9 | Page scrolls at 1280 and 1024 | Panes scroll, canvas does not | Losing the queue off-screen defeats the purpose |
| 10 | `[GIFTCARD] Gift Card` | Product name only | Internal codes are noise at a window |
| — | Vehicle identity prominent *(already there)* | keep | |
| — | `READY` / `PAID` badges *(already there)* | keep, tighten to three named tracks | |
| — | Stage-specific CTA *(already there)* | keep, extend per role | |
| — | Arabic/RTL working *(already there)* | keep, verify each pass | |

## Not invented

The brief lists gaps that do **not** exist here and are deliberately absent from
this map: "one active order only" (the board is already multi-car), "generic
checkout" (the CTA is already stage-specific), and "order ID only" (vehicle is
already the headline). Building against those would have been rework.

## Sequencing

**DT-UX1** shell + operations strip + persistent queue.
**DT-UX2** Order Taker convergence (queue stays live while ordering).
Then review, before Payment / Pickup / KDS / OCB.
