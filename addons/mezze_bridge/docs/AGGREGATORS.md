# Delivery aggregators (Talabat / Jahez / …)

## Principle: an aggregator order is a prepaid delivery
Odoo Community has no MENA-aggregator connector, so this is a real build — but a
thin one. A webhook order becomes the SAME artifact the on-premise delivery path
already produces: a paid `pos.order` (aggregator = prepaid tender) + KDS tickets
+ a `mezze.delivery` record. Ingestion reuses `_build_lines` / `_make_station_
tickets` / `_ensure_open_session` / `_audit`; it doesn't re-implement order
creation.

## Data model (`models/aggregator.py`)
- **`mezze.aggregator`** — one channel per (aggregator, branch): `code` (URL
  slug), `config_id`, `payment_method_id` (prepaid tender), `secret` (HMAC),
  `auto_accept`, `commission_pct`. Unique (code, config_id).
- **`mezze.aggregator.product.map`** — `external_sku` → `product_id` per channel.
  Unique (aggregator, sku).
- **`mezze.aggregator.order`** — one ingested order: unique (aggregator,
  external_id) = idempotency; links pos_order/delivery; `state`
  received/rejected/cancelled; gross/commission/net_payout; `raw_payload`.

## Webhook — `POST /mezze/aggregator/<code>/webhook`
`type='http'`, `auth='none'` (signed, not token). Normalised body:
```json
{"external_id":"TLB-5001","event":"order.new",
 "config_id":1,
 "customer":{"name":"…","phone":"…","address":"…"},
 "items":[{"sku":"ESP","qty":2,"price":30.0,"note":"…"}],
 "totals":{"gross":120.0}}
```

### Security (money path — gated hard)
1. **Signature** — `X-Mezze-Signature: hex(hmac_sha256(channel.secret, raw_body))`.
   Constant-time compare. Unsigned / wrong / secret-unset → 401 / 503. Verified
   over the RAW bytes (why the route is `type='http'`, not `json2`).
2. **Idempotency** — a repeat (aggregator, external_id) returns the first result;
   never a second `pos.order`.
3. **Fail loud on unmapped SKU** — if ANY item's sku isn't mapped, the whole
   order is REJECTED (`state=rejected`, `unmapped_skus` recorded, audit
   `aggregator.reject`, HTTP 422). We never silently drop a line or guess a
   product — that would corrupt the bill and stock.

### order.new flow
resolve channel (by code, disambiguate by `config_id` when a code spans branches)
→ verify sig → idempotency check → map all SKUs → `_build_lines` (server-side
tax) → paid `pos.order` via `sync_from_ui` on the channel's prepaid tender →
fire tickets (`auto_accept` gates the broadcast) → `mezze.delivery` (preparing)
→ `mezze.aggregator.order` (gross/commission/payout) → audit `aggregator.order`.

### order.cancel flow
Flags the `mezze.aggregator.order` cancelled + delivery failed + audit
`aggregator.cancel` (warning). It does **not** auto-void the paid, possibly-
cooking `pos.order` — refund/void of a prepaid order is a staff decision routed
through the existing refund / reversal-queue path. Idempotent.

## Staff endpoint — `POST /mezze/aggregator/orders`
Shared-token auth. Returns ingested orders (state, who, tracking, gross/
commission/payout) + the branch's channels. Backs the manager view (frontend
TODO — mirrors the Reports/GL pattern).

## Commission
`commission = gross × commission_pct`; `net_payout = gross − commission`. Purely
informational for payout reconciliation — it does NOT change what the customer
paid or the `pos.order` total. A GL commission-expense line is a later item
(the GL bridge already surfaces the gross takings).

## Scaffolds — honest, not faked
- **Per-aggregator adapters** — the webhook accepts the NORMALISED body above.
  Each real aggregator (Talabat, Jahez, HungerStation, Deliveroo) has its own
  payload shape + signature scheme; a thin shim normalises theirs to this once
  their partner API spec + credentials are provisioned.
- **Status-push OUT** (`_notify`) — telling the aggregator accepted/ready/
  dispatched needs each aggregator's live API. Currently logs the intent and
  returns `False` rather than pretending to have called — same honesty stance as
  the ETA/PSP external legs.

## Validation (2026-07-13, live demo, curl + DB)
Seeded a `talabat` channel (config 1, secret, 20% commission) + ESP/FLW/CRO map.
Proven: signed new order → paid balanced `pos.order` #199 (121.30 = 95 × 1.12 ×
1.14, taxes correct) + 2 station tickets (Barista/Pastry) + delivery + agg order
(gross 120 / commission 24 / payout 96); idempotent replay (no dup); bad
signature → 401; unmapped SKU → 422 + rejected record; cancel → flagged +
delivery failed + audit; cancel again → idempotent; staff list returns all.
