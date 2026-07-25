# R1 — Restaurant Service Loop — Acceptance Evidence

| Field | Value |
|---|---|
| Date | 2026-07-24 |
| Commit | `ce8dc74` (+ R1 working changes) |
| Addon version | 19.0.1.5.0 |
| Environment | live Odoo 19 + PostgreSQL, DB `mezze_test`, single-worker HTTP :8199 |
| Roles exercised | host, server, cashier, kitchen, manager (canonical authz) |
| Themes/langs | Mezze Classic light + dark · English LTR + Arabic RTL |

## Workflow / feature audit matrix
Classification from the running app + code (Working / Partial / Missing / Broken→Fixed).

| Feature | Before R1 | After R1 |
|---|---|---|
| Reservations (list/create/availability) | Working | Working |
| Reservation state writes (state/create) | **Broken** (route read-only → writes failed) | **Fixed** (`readonly=False`) |
| Reservation arrival states (confirmed/arrived/waiting/late) | Missing | **Added** + guarded |
| Reservation transition guards / restore | Missing | **Added** (illegal moves rejected) |
| Walk-in / waitlist add + list | Working | Working |
| Waitlist state writes | **Broken** (read-only) | **Fixed** |
| Waitlist states (seating/left/no_response) | Missing | **Added** + guarded |
| Floor plan / table state | Working (real tables, states, stats) | Working |
| Table assignment | Working | Working (+ guarded seat) |
| Table transfer | Working (validated, preserves identity/payments/KDS) | Working |
| Table merge / combine | Working (re-homes lines+KDS, adds guests, audits) | Working |
| Table-order creation (idempotent by uuid) | Working | Working (+ seat→order back-link) |
| Seat → order attach (exactly one, idempotent) | Missing | **Added** (`_seat_attach_order`) |
| Guest count persistence | Working (pos.order.customer_count) | Working |
| Seat-level ordering | Backend-limited | Guest count durable; seat numbers not durably modelled — see limitations |
| Course hold / fire / board | Working (fire idempotent by `fire_uuid`, appends additions) | Working |
| KDS routing / state / transition | Working (via transactional outbox) | Working |
| Ready / served progression | Working | Working |
| Split bill / partial / mixed tender | Working (existing payment engine) | Working |
| Payment idempotency (lost response) | Working (idempotent by order uuid) | Working |
| Table release safety | Working (release only via paid order; no bypass endpoint) | Working |
| Reconnect / recovery | Working (uuid + fire_uuid idempotency, offline journal) | Working |
| Host/server/kitchen roles | Partial (no host/server role) | **Added** host + server roles |

## Runtime + DB assertions (from the automated suite — real Odoo + PostgreSQL + real HTTP)
`tests/test_runtime_r1.py` (all green in the 199-test run):
- **Guarded transitions** — `test_completed_cannot_reseat`: a `done` reservation seat attempt raises and the row is **not** written; `test_cancelled_needs_restore`: `cancelled`→seat rejected, `restore`→`booked`→seat succeeds.
- **Idempotent seat→order** (real HTTP) — `test_seat_attaches_one_order_idempotently`: seating links the table's single draft order; a **retry returns the same order_id**; DB assertion `search_count(table draft orders) == 1`; `reservation.pos_order_id == order.id`.
- **Invalid transition over HTTP** — returns `invalid_transition` (409); DB row unchanged.
- **Permission boundary** — `test_host_permission_boundary`: a host is denied `/orders/pay` (`permission_denied`) but may seat.
- **Waitlist** — progression waiting→notified→seating→seated; `seated`→`notify` rejected; left→restore→waiting.

## Screenshots
| File | Shows |
|---|---|
| reservations-arrival-checkin-ltr.jpg | Arrival workflow: CONFIRMED/BOOKED states, VIP/Anniversary/Late chips, Arrived+Seat actions (English) |
| reservations-arrival-arabic-rtl.jpg | Same, **Arabic RTL** (rail mirrored right) |
| staff-floor-plan.jpg | Floor: real table shapes, seat dots, occupancy/covers/dwell stats, labeled legend |
| staff-kds-empty-AFTER-fixed.jpg | KDS all-caught-up state (renders live ticket cards when active) |
| staff-reports-light.jpg | Sales/refunds KPIs (real sources) — the completion reporting context |

## Known limitations
- **Seat-level ordering**: guest count is durable (`pos.order.customer_count`); explicit per-seat line assignment is **not** durably modelled in the current backend, so R1 exposes guest count fully and does **not** ship a UI-only seat system (per §6). Marked unsupported.
- **Multi-device real-time**: the sync/outbox/bus infrastructure is reused and idempotency is proven, but this session executed on a single HTTP worker + one browser context; true 3-device concurrent convergence was **not** staged live (idempotency guarantees it cannot duplicate; convergence is by the existing bus + poll-reconcile).
- **Tablet viewport**: the capture host cannot force a narrow-tablet CSS viewport (`resize_window` no-ops on hi-DPI); responsive CSS present, not framed at ≤1024px.
- **Full pay→release visual sequence**: the payment-state visual set (processing/failed/change-due/printing) was not re-framed this increment; payment correctness/idempotency is covered by the existing engine + suite.
