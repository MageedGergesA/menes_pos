# Mezze Delivery v1 — Certification Matrix (S3 §102)

Strict distinction: **SOFTWARE CERTIFIED** = code path exists + CI-tested + browser-accepted with DB
proof. **SUPPORTED VIA ODOO** = Odoo ships it but Mezze's standalone adapter/credentials are pending.
**EXTERNAL CERTIFICATION PENDING** = real provider account/credentials not executed. Never blurred.

## First-party delivery

| Capability | Status | Notes |
|---|---|---|
| First-party customer delivery ordering | **SOFTWARE CERTIFIED** | storefront → canonical `pos.order` → KDS-once → status token |
| Pickup | **SOFTWARE CERTIFIED** | pay-at-counter, no fee, unaffected by delivery (regression-tested) |
| Structured MENA address | **SOFTWARE CERTIFIED** | area/street/building/floor/apartment/landmark, immutable snapshot on the order |
| Server-authoritative zone/fee/minimum/ETA | **SOFTWARE CERTIFIED** | `/delivery/availability`; browser cannot inject fee/min/zone |
| Out-of-zone / below-minimum / closed-hours | **SOFTWARE CERTIFIED** | refused → 0 order, 0 payment |
| Delivery hours | **SOFTWARE CERTIFIED** | narrow per-zone weekly windows; closed ⇒ no order |
| Delivery fee (real order line, tax-capable) | **SOFTWARE CERTIFIED** | `MEZZE_DELIVERY_FEE` service product; total/receipt/accounting agree |
| **COD (real, unpaid until collection)** | **SOFTWARE CERTIFIED** | order is NEVER faked paid at checkout; fires KDS; `COD_DUE` until `/delivery/collect` records the one cash `pos.payment` (idempotent) |
| Online delivery payment | **SOFTWARE CERTIFIED** | reuses S2C-5 `payment.transaction` + native `/pos/pay`; zone/fee validated before any transaction |
| Canonical POS order + KDS exactly-once | **SOFTWARE CERTIFIED** | `_do_fire` / `_mezze_fire_online_kds`, FOR UPDATE + `mezze_kds_fired` |
| Lifecycle FSM (placed→accepted→preparing→ready→assigned→out_for_delivery→delivered / cancelled / rejected) | **SOFTWARE CERTIFIED** | server-authoritative guarded transitions; illegal jumps refused |
| Accept / reject + cancellation reasons | **SOFTWARE CERTIFIED** | reason required; cancel-after-fire needs a manager (§44) |
| Manual dispatch + courier assignment | **SOFTWARE CERTIFIED** | `mezze.courier`; manual only — **NO route optimisation / GPS / fleet** |
| Customer tracking (secure token) | **SOFTWARE CERTIFIED** | hashed SHA-256 token, TTL, revocable; server-rendered status page |
| Staff delivery dashboard | **SOFTWARE CERTIFIED** | dispatch board with lifecycle + assign + COD collect |
| Delivery reporting | **SOFTWARE CERTIFIED** | counts / revenue / AOV / fees / COD-vs-prepaid / cancellations / avg prep+delivery / by zone + courier |
| Arabic / RTL / mobile / dark | **SOFTWARE CERTIFIED** | native `_t`/`ir.translation`; browser-verified |
| Idempotency / concurrency / KDS-once | **SOFTWARE CERTIFIED** | client uuid + COD-collect FOR UPDATE + unique tender key |

## Aggregators (external)

| Provider | Status | Notes |
|---|---|---|
| Mezze aggregator ingest layer | **SOFTWARE CERTIFIED** | HMAC, idempotency, SKU-map, prepaid normalization → same canonical lifecycle/KDS |
| UrbanPiper (native `pos_urban_piper`, Enterprise) | **SUPPORTED VIA ODOO / EXTERNAL CERTIFICATION PENDING** | requires Odoo Enterprise + UrbanPiper subscription + credentials; not wired to Mezze first-party channel |
| Talabat, Careem, Mrsool, HungerStation, Jahez, NoonFood, Deliveroo, Rafeeq, Ninja, Keeta, EatEasy, Cari (MENA, via UrbanPiper) | **EXTERNAL CERTIFICATION PENDING** | named in native `pos_urban_piper` data; none Mezze-certified (no credentials/live tests) |

## Explicitly NOT built (out of S3 scope)
Route optimization · automatic driver optimization · multi-stop planning · live GPS tracking ·
driver payroll · fleet management · delivery marketplace · own Talabat/Careem protocols ·
courier bidding · advanced dispatch engine. These may become later premium features.
