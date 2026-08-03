# Delivery v1 Audit (S3 §2–§3)

Source-based audit of (a) the EXISTING Mezze delivery/pickup/online-ordering implementation and
(b) NATIVE Odoo 19 restaurant-delivery features, so S3 ADDS only the gaps and reuses what is proven.

## A. Existing Mezze implementation (`mezze_bridge`)

| Capability | Status | Anchor |
|---|---|---|
| Canonical paid `pos.order` per channel | **ALREADY COMPLETE** | `_do_fire` main.py; every channel makes a real order |
| KDS exactly-once fire (pay-before-fire, FOR UPDATE + `mezze_kds_fired`) | **ALREADY COMPLETE** | `models/mezze_online_payment.py` `_mezze_fire_online_kds` |
| S2C-5 online-payment handoff for delivery (validate→draft→native `/pos/pay`) | **ALREADY COMPLETE** | `controllers/checkout.py` `/checkout/online/create|pay`, `_online_delivery_draft` |
| Hashed status token (SHA-256, TTL, revocable) + server-rendered status page | **ALREADY COMPLETE** | `models/pos_order.py` `_mezze_ensure_status_token`; `/checkout/s/<token>` |
| Public status mapping incl `out_for_delivery` | **ALREADY COMPLETE** | `pos_order.py` `mezze_public_status` |
| Delivery fee = real service-product order line (`MEZZE_DELIVERY_FEE`, tax-capable) | **ALREADY COMPLETE** (currently zero-tax) | `main.py` `_delivery_fee_product` |
| `mezze.delivery.zone` (name/branch/fee/min_order/eta_minutes/sequence/active) | **PARTIAL** | `models/delivery.py:14` — missing cod/online-allowed, priority, hours |
| `mezze.delivery` (order link/customer/phone/address-text/fee/zone/rider/state/timestamps) | **PARTIAL** | `models/delivery.py:28` — flat FSM, free-text address, `rider` Char |
| `mezze_channel` durable source (qr/pickup/delivery/drivethru/aggregator/pos) | **PARTIAL** | `pos_order.py` — no first_party-vs-provider split |
| Aggregator ingest (HMAC, idempotency, SKU-map, prepaid normalization) | **ALREADY COMPLETE** | `models/aggregator.py`, `controllers/aggregator.py` |
| Drive-thru (pay-at-window) | **ALREADY COMPLETE** | `models/drivethru.py` |
| 86 (branch-global) revalidated before order/pay | **ALREADY COMPLETE** | `main.py` `_assert_available`; `/menu/eightysix` |
| Customer delivery/pickup SPA + staff dispatch board | **FRONTEND present** (static HTML) | `static/shop.html`, `static/pos.html` `#view-delivery` |
| **COD real collection** | **MISSING** — storefront delivery is booked **fake-prepaid** (`amount_paid=incl`); no unpaid/collect | `main.py` store `/shop/order` delivery |
| **Lifecycle FSM guards + accept/reject + cancellation reasons** | **MISSING** — flat `state`, direct writes, no reason | `/delivery/state` |
| **Courier model + manual assignment** | **MISSING** — `rider` is free text | `mezze.delivery.rider` |
| **Service hours** | **MISSING** — open = session-open only | — |
| **Structured MENA address** | **MISSING** — free-text `address` only | `mezze.delivery.address` |
| **Per-channel product availability** | **MISSING** (global 86 only) — DEFER for v1 | — |
| **Delivery reporting** | **MISSING** | — |
| Automated tests for delivery/zone/dispatch paths | **MISSING** | — |

## B. Native Odoo 19 (reuse decisions)

| Native feature | Verdict | Why |
|---|---|---|
| `pos.preset` delivery/takeaway (`service_at` via `pos_self_order`) | **DEFER** | Mezze uses its own `mezze_channel` + static SPA, not presets/self_order; adopting presets is a large shift for no v1 gain |
| `pos_self_order` online-order flow | **DEFER** | Mezze already has its own storefront + checkout |
| `pos_urban_piper` aggregator (Enterprise OEEL-1) | **COEXIST / DEFER** | Requires UrbanPiper subscription + credentials; Mezze has its own aggregator layer. Documented SUPPORTED VIA ODOO / external cert PENDING. Provider list feeds the MENA matrix |
| Native food-delivery product flag | **DEFER** | Only UrbanPiper's config-scoped m2m; global 86 suffices for v1 |
| Store timings (`pos.preset` `resource.calendar`) | **DEFER heavy calendar; build NARROW** | v1 delivery hours = a small per-branch weekly-window check, not the full slot/capacity calendar |
| `pos.prep` stages (Enterprise) | **COEXIST** | Mezze has its own `mezze.kds.ticket`; kitchen readiness derived from it |
| `delivery.carrier` / shipping (`delivery` module) | **AVOID** | eCommerce shipping-rate architecture, wrong for restaurant food delivery. Only the flat-fee-as-product idea transfers (already done) |
| `pos_online_payment` `/pos/pay/<id>` + `_process_pos_online_payment` | **REUSE** | Delivery online payment rides this verbatim (S2C-5) |

**MENA aggregators named in native `pos_urban_piper`** (for the matrix, all EXTERNAL-CERT PENDING): Careem, Talabat, HungerStation, Mrsool, Jahez, Rafeeq, Ninja, Keeta, NoonFood, EatEasy, Cari, Deliveroo.

## C. S3 build plan (ADD only)
1. **Zone richness** — `cod_allowed`, `online_allowed`, `priority`, delivery hours on `mezze.delivery.zone`; server-authoritative availability (eligible/fee/min/ETA/payment-methods/open).
2. **Real COD** — delivery COD creates an UNPAID canonical order that still fires to KDS (like pickup pay-at-counter), stays `COD_DUE`; a collection action records the real cash `pos.payment` only when collected. **No fake-prepaid.**
3. **Lifecycle FSM** — placed→accepted→preparing→ready→assigned→out_for_delivery→delivered→cancelled, guarded transitions (server authority), accept/reject + cancellation with reason + audit.
4. **Courier + manual dispatch** — `mezze.courier` (name/branch/phone/status/active) + assignment (`courier_id`/assigned_by/assigned_at); manual only (NO optimizer/GPS).
5. **Structured MENA address** — area/street/building/floor/apartment/landmark/phone/notes snapshot (immutable on the order/delivery), composed display text.
6. **Service hours** — narrow per-branch delivery weekly windows; closed → no order.
7. **Reporting** — delivery counts/revenue/AOV/fees/COD-vs-prepaid/cancellations/avg prep+delivery time/by zone/by courier.
8. **Tests + browser + cert matrix.** Reuse everything in the ALREADY-COMPLETE list.
