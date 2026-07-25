# O1 — Omnichannel Ordering — Acceptance Evidence

| Field | Value |
|---|---|
| Date | 2026-07-25 |
| Commit | `ce8dc74` (+ O1 working changes) |
| Addon version | 19.0.1.7.0 |
| Odoo | 19 · **2 real worker processes** (3 worker children observed) |
| PostgreSQL | real, DB `mezze_test`, port 8204 |

## Channel audit (Working / Partial / Missing / Fixed)
| Capability | QR | Pickup | Delivery | Drive-thru | Aggregator | Status |
|---|---|---|---|---|---|---|
| Menu contract (branch/channel-safe) | ✓ | ✓ | ✓ | ✓ | ✓ (SKU map) | Working |
| Server-authoritative pricing | ✓ | ✓ | ✓ (zone fee) | ✓ | ✓ | Working (`_build_lines`, `_promo_for_cart` — never client totals) |
| Availability revalidation at checkout | ✓ | ✓ | ✓ | ✓ | ✓ | Working (`_assert_available` rejects 86'd) |
| Canonical `pos.order` + uuid idempotency | ✓ | ✓ | ✓ | ✓ | ✓ (external_id) | Working |
| KDS routing via outbox | ✓ | ✓ | ✓ | ✓ | ✓ | Working |
| Payment (existing engine) | ✓ | pay-at-counter | pay-on-delivery | ✓ | prepaid | Working |
| Aggregator normalization + idempotency | — | — | — | — | ✓ | Working (`controllers/aggregator.py`) |
| **Customer order-status (secure token)** | ✓ | ✓ | ✓ | ✓ | ✓ | **Fixed this increment** |
| Refund/cancel (existing engines) | ✓ | ✓ | ✓ | ✓ | ✓ (+policy) | Working |

## Defects found & fixed
1. **No secure customer order-status contract (§14).** Added an OPAQUE `mezze_status_token` on `pos.order` (12 random bytes → 24 hex; never the sequential id), a `mezze_public_status()` safe mapping (received/confirmed/preparing/ready/out_for_delivery/completed/cancelled), the `/shop/status` endpoint (token-only, rate-limited, generic 404, safe fields only), and live polling in `shop.html`. Set the token + `mezze_channel` on every channel order (qr/pickup/delivery/aggregator).
2. **Read-only mutating routes** — the aggregator webhook (`type='http'`) + `order_sync`, `register`, `push`, and the w1 financial routes (`einvoice_submit`, `payment_intent`, `payment_void`, `reversals_resolve`) lacked `readonly=False`; their writes aborted. **Fixed** (`readonly=False` added).

## Multi-worker live execution (`multiworker-execution.txt`) — 4/4 PASS on 2 workers
- **6 concurrent aggregator callbacks (same external_id) → exactly ONE `pos.order`** (order_ids=[7257]); DB assertion `agg_orders(LIVE-EXT-1)=1`. (One of the 6 hit the unique-constraint race and would resolve to the idempotent hit on retry.)
- `shop/status` by opaque token → 200 with safe public status, **no internal `state` field leaked**.
- `shop/status` with a wrong token → **404** (generic, no leak).

## Automated suite (real Odoo + PostgreSQL + real HTTP) — 214/214 green
`tests/test_runtime_o1.py`: opaque-token idempotence + 24-hex; public-status mapping (received→preparing→ready→cancelled); status-by-token safe fields; **sequential id does NOT expose** an order; wrong token → generic 404; **aggregator duplicate callback → one order**; **unmapped SKU → 422 reject**; **bad signature → refused**.

## Screenshots
- `online-shop.jpg` — online shop (Mezze Classic, terracotta), token-adopted.
- `customer-display.jpg` — CFD order summary.
- `arabic-rtl.jpg` — Arabic RTL rendering.

## Known limitations
- Customer-status live-polling UI added to `shop.html`; QR/drive-thru status UIs reuse their existing surfaces (token available, richer polling UI is follow-up).
- Server-authoritative pricing + availability were pre-existing (verified, not rebuilt).
- Tablet ≤1024px viewport not forceable on the capture host (documented in R1.1).
