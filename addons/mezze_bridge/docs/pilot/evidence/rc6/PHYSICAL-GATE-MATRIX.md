# RC6 PILOT — PHYSICAL GATE MATRIX

Build: `mezze-v1.0-rc6` / `e85be35c31a3ae285494f68ecc67aaed493fd687`

**Total 21 · Passed 0 · Failed 0 · Pending 21.**

**No gate below was executed.** RC6 corrects software defects; it does not advance physical
evidence. Software concurrency proofs do **not** count as physical hardware gates, and no
RC5 result was carried forward — there was none to carry.

| # | Gate | Status | Blocked by |
|---|---|---|---|
| 1 | Counter sale → physical receipt | PENDING | printer MISSING |
| 2 | Arabic physical receipt | PENDING | printer MISSING |
| 3 | Cash drawer opens from a real transaction | PENDING | drawer + printer MISSING |
| 4 | KDS ticket on a separate physical KDS device | PENDING | device MISSING |
| 5 | KDS ready/served lifecycle from that device | PENDING | device MISSING |
| 6 | Table service from a staff tablet | PENDING | tablet MISSING |
| 7 | Reservation / waitlist from a staff device | PENDING | tablet MISSING |
| 8 | QR order from a separate customer phone | PENDING | phone MISSING · plain-HTTP secure-context caveat |
| 9 | Customer responsive / touch workflow | PENDING | phone MISSING |
| 10 | Real payment-terminal interaction | PENDING | terminal + provider NOT CONFIGURED |
| 11 | Split / mixed tender on the terminal | PENDING | as above |
| 12 | Refund / reversal on the terminal | PENDING | as above + authorisation |
| 13 | Real WAN outage | PENDING | procedure only |
| 14 | Recovery after WAN returns | PENDING | procedure only |
| 15 | Application restart during active pilot data | PENDING | needs a live shift |
| 16 | Device reconnect | PENDING | devices MISSING |
| 17 | Physical power / UPS recovery | PENDING | UPS MISSING |
| 18 | Cash-count reconciliation | PENDING | drawer MISSING |
| 19 | Staffed shift execution | PENDING | not scheduled |
| 20 | Pre-shift full DB+filestore backup | PENDING | must be taken immediately before the shift |
| 21 | Post-shift restore proof | PENDING | follows gate 20 |

## What RC6 *did* change for gate 6

Gate 6 (staff tablet) previously carried a known software blocker: DEFECT-01 meant a second
device on the same POS config would knock the first offline. **That blocker is now removed
and proven removed on the deployed runtime.** The gate itself is still PENDING — it needs a
tablet — but it will no longer fail for that reason.

## Not gate 15

A clean restart was proved twice during this redeployment (shadow and canonical). That is
**not** gate 15, which requires a restart while real orders are open on real devices
mid-shift.
