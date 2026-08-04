# P3-BUSINESS-STATE-MAP (DESIGN-P3B)

Business states → canonical semantic variant. Same meaning → same semantics everywhere (item 8);
size/scale may differ (KDS large, admin compact). Derived from source + business meaning.

## Go-Live (onboarding) ✅ migrated
| State | Semantic |
|---|---|
| PASS | success |
| WARNING | warning |
| FAIL | danger |
| NOT TESTED | **not-tested** (dashed — never resembles pass/fail) |
| N/A | neutral |

## Payment (checkout / cashier) — ✅ checkout migrated (`.pay-msg`)
| State | Semantic | Trust note (item 17) |
|---|---|---|
| Ready to pay | info | — |
| Confirming | info/active | — |
| Pending / processing | warning | not yet settled |
| Paid / successful | success | provider-confirmed |
| Failed | danger | not charged |
| Canceled | warning | not charged |
| Partially paid | warning | distinct from paid |
| Manual confirmation | warning | must NOT look identical to provider-confirmed (paid=success) |
| Refunded | neutral/info | — |
| Refund pending/manual | warning | — |

## Store / Customer (shop/qr/cfd) — ✅ store open/closed migrated
| State | Semantic |
|---|---|
| Open | success | 
| Closed | danger |
| Preparing your order | active |
| Ready for pickup | success |
| On the way / out for delivery | active |
| Completed | success |
| Cancelled | danger |

## Order / KDS (pending migration — pos prototype + cashier)
| State | Semantic |
|---|---|
| Draft / New | neutral |
| Sent / Fired | info |
| Accepted | warning→info |
| Preparing | active |
| Ready | success |
| Served / Completed | neutral (done) or success |
| Late / Urgent | warning (escalates to danger) |
| Cancelled | danger |

## Table / Floor (pending)
Available→success · Occupied→info · Reserved→warning · Needs attention→warning · Partially paid→warning · Bill requested→info.

## Reservation / Waitlist (pending)
Booked→info · Arrived→active · Waiting→warning · Seated→success · Cancelled→danger · No-show→danger/neutral.

## Delivery (pending)
New→neutral · Accepted→info · Preparing→active · Ready→success · Assigned→info · Out for delivery→active · Delivered→success · Cancelled→danger · Delayed→warning.

## Connectivity (pending — preserve 3-signal architecture, item 22)
Local Online→success · Local Unavailable→danger · Internet Online→success · Internet Offline→danger ·
Internet Unknown→not-tested/neutral · External Online→success · External Degraded→warning ·
External Paused→paused · External N/A→neutral. **Do NOT collapse the three signals into one "Offline".**

## Admin / Settings (pending — item 40)
Working→success · Disabled→neutral · Hidden→neutral · Inherited→info · Locked→warning ·
Published→success · Archived→neutral. Disabled / Locked / Unavailable must not look identical.

> No FSM / business behaviour changes — this is state PRESENTATION mapping only.
