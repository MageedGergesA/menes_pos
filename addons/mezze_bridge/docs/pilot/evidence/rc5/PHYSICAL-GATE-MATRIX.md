# RC5 PILOT — PHYSICAL GATE MATRIX

Build: `mezze-v1.0-rc5` / `4b0feb1e4794134d57466bc17e6dc2ea5f4080b6`

**Total gates: 21. Passed: 0. Failed: 0. Pending: 21.**

**No gate below was executed.** Preparation is not execution, and a discovered device is
not a passed device. Every row starts PENDING and only a human with the physical hardware
may change one.

| # | Gate | Status | Hardware required | Blocked by |
|---|---|---|---|---|
| 1 | Counter sale → physical receipt | PENDING | receipt printer | printer MISSING |
| 2 | Arabic physical receipt | PENDING | receipt printer w/ Arabic capability | printer MISSING |
| 3 | Cash drawer opens from a real transaction | PENDING | drawer + printer kick | both MISSING |
| 4 | KDS order appears on a separate physical KDS device | PENDING | second display/tablet | device MISSING |
| 5 | KDS ready/served lifecycle from the real device | PENDING | KDS device | device MISSING |
| 6 | Table service from a staff tablet | PENDING | staff tablet | tablet MISSING · see DEFECT-01 |
| 7 | Reservation / waitlist from a staff device | PENDING | staff tablet | tablet MISSING |
| 8 | QR order from a separate customer phone | PENDING | customer phone | phone MISSING · HTTP-camera caveat |
| 9 | Customer responsive / touch workflow | PENDING | customer phone | phone MISSING |
| 10 | Real payment-terminal interaction | PENDING | terminal + provider account | NOT CONFIGURED |
| 11 | Split / mixed tender on the terminal | PENDING | terminal | NOT CONFIGURED |
| 12 | Refund / reversal on the terminal | PENDING | terminal + authorisation | NOT CONFIGURED |
| 13 | Real WAN outage | PENDING | router/uplink access | procedure only |
| 14 | Recovery after WAN returns | PENDING | as above | procedure only |
| 15 | Application restart during active pilot data | PENDING | live shift data | needs a shift |
| 16 | Device reconnect | PENDING | ≥1 real device | devices MISSING |
| 17 | Physical power / UPS recovery | PENDING | UPS | UPS MISSING |
| 18 | Cash-count reconciliation | PENDING | cash + drawer | drawer MISSING |
| 19 | Staffed shift execution | PENDING | staff + devices | not scheduled |
| 20 | Pre-shift full DB+filestore backup | PENDING | — | must be taken immediately before the shift |
| 21 | Post-shift restore proof | PENDING | — | follows gate 20 |

Gates 20 and 21 are the only two that need no restaurant hardware, and both are still
PENDING **by definition**: the backup already taken covers the pre-deployment state, not
the pre-shift state. Taking gate 20's backup early would make it worthless.

## What "restart during active pilot data" (15) means here

A clean restart was already proved during deployment — same commit, same database, same
filestore, no asset regression. That is **not** gate 15. Gate 15 requires a restart while
real orders are open on real devices mid-shift, and remains PENDING.

## Note on gate 6

`DEFECT-01` (see `DEFECTS.md`) is directly relevant: two Register sessions on the same POS
config invalidate each other's API token. Plan gate 6 with that in mind, or the failure
will be misattributed to the tablet.
