# R1.1 — Real-Device, Multi-Client & Checkout Acceptance — Evidence

| Field | Value |
|---|---|
| Date | 2026-07-24 |
| Commit | `ce8dc74` (+ R1.1 working changes) |
| Addon version | 19.0.1.6.0 |
| Odoo | 19 · **2 real worker processes** (`--workers=2`, 3 worker children observed) |
| PostgreSQL | real, DB `mezze_test`, port 8203 |
| Transport | real HTTP over the worker pool |

## Environment / device matrix
| Client | Kind | Role | Viewport | Lang | Theme |
|---|---|---|---|---|---|
| Multi-worker HTTP client | real HTTP (urllib), pooled across 2 workers | host / kitchen / manager | — | EN | — |
| Reservation arrival (browser) | Chrome tab | manager | ~1568px* | EN + **AR RTL** | Classic light |
| Floor plan (browser) | Chrome tab | manager | ~1568px* | EN | Classic light |

\* **Tablet limitation (honest):** `resize_window` does not change the rendered CSS viewport on this hi-DPI capture host — frames stay ~1568px. A true 1024×768 tablet frame could **not** be forced. The responsive layer (`@media ≤1040px`, logical/RTL props) is present in source but not rendered at ≤1024px this session.

## Multi-worker live execution (`multiworker-execution.txt`)
Against **2 real workers** — **6/6 PASS**:
- `seat_attaches_order` — seating attaches **exactly one** order (order_id matched the seeded draft).
- `seat_retry_same_order` — retry across the pool returns the **same** order (idempotent).
- `concurrent_seat_no_crash` — 4 parallel seat requests across workers, deterministic.
- `kds_transition_write_works` — **status 200** (kitchen role) — proves the read-only defect fix on real workers.
- `merge_safe_unpaid_over_workers` — table merge succeeds on real workers.
- `host_denied_payment` — role boundary enforced (host → `permission_denied`).
- **DB assertion:** `draft_orders_on_tables = 1` after merge (unique order identity).

## Automated suite (real Odoo + PostgreSQL + real HTTP HttpCase) — 206/206 green
`tests/test_runtime_r1.py` adds: reservation lifecycle guards, idempotent seat→order, host permission boundary, **merge blocked when an order has a payment** (payment + order untouched), **merge safe when both unpaid**, **kitchen cannot pay**, **cashier cannot modify KDS prep**. Payment/order/fire idempotency proven by the wider suite.

## Screenshots
- `reservation-arrival-ltr.jpg` / `reservation-arrival-rtl.jpg` — arrival check-in (CONFIRMED/VIP/Late chips, Arrived+Seat), English + **Arabic RTL**.
- `floor-plan.jpg` — real table geometry + labeled legend.

## Defects found & fixed (this acceptance session)
1. **Read-only mutating endpoints** — `courses/fire`, `courses/hold`, `tables/transfer`, `tables/merge`, `kds/transition`, `sessions/close`, `orders/exchange` + 21 others lacked `readonly=False`; their writes aborted the transaction (complex handlers with `SELECT FOR UPDATE`/savepoints defeated Odoo's readonly-retry). **Fixed** (`readonly=False` on 28 mutating routes).
2. **Table-merge financial safety (§8)** — merge re-homed lines then `unlink()`ed the source **without moving payments**, silently destroying payment records. **Fixed** — merge now blocks (`merge_blocked_payments`, 409, audited) when either order has payments/reversals unless an explicit `combine_confirm`.

## Known limitations
- Tablet 1024×768 viewport not forceable on the capture host (above).
- The three clients were a real HTTP client (pooled across 2 workers) + browser tabs, not three separate physical devices; bus real-time convergence relies on the existing bus + poll-reconcile (idempotency proves no duplication).
- Full payment-state visual sequence (processing/failed/change-due/printing) not re-framed; payment correctness/idempotency covered by the existing engine + suite.
