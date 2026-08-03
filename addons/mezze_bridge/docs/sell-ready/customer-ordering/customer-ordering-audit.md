# Customer-Ordering Audit (S4 §2)

Source-based audit of the EXISTING Mezze customer-facing ordering so S4 ADDS only the gaps and
reuses the certified S3 storefront / table-QR / catalog / payment / status. Anchors are file:line.

## Already COMPLETE — REUSE, do NOT rebuild

| Capability | Status | Anchor |
|---|---|---|
| Off-premise storefront (menu/search/cards/cart/checkout, pickup+delivery, promo, EN/AR, dark) | **COMPLETE** | `static/shop.html` |
| Table-QR customer menu | **COMPLETE** | `static/qr.html`; `/qr/menu` `main.py:2458` |
| Table-QR **ordering** (place → append to the table's open draft → bill → pay/pay-online) | **COMPLETE** | `/qr/order` `main.py:2495`, `_do_fire` append `main.py:1782`, `/qr/bill` `:2577`, `/qr/pay` `:2601`, `/checkout/table/pay_online` `checkout.py:179` |
| Add-items-to-existing-table (only new lines fire) | **COMPLETE** | `_do_fire` FSM + append |
| Two-phone concurrency / double-submit / lost-response | **COMPLETE (strong)** | `_do_fire` pg advisory lock on table_id `main.py:1751` + `fire_uuid` idempotency `:1757` |
| Server-authoritative pricing/tax, injection-proof | **COMPLETE** | `_build_lines` `main.py:1425`, `_line_attr_values` filters to the product's template `:1353` |
| Combos (one-per-group, reprice to the cent) | **COMPLETE (server)** | `_resolve_combo` `main.py:1529`, `_combo_child_vals` `:1488` |
| Modifiers (single/multi, real `price_extra`) | **PARTIAL** | `_product_modifiers` `main.py:1388` — **no required/min/max/default** |
| Product 86 (branch-global, revalidated at checkout, bus push) | **COMPLETE** | `_assert_available` `main.py:3911`, `/menu/eightysix`, `_revalidate_available` `checkout.py:37,151` |
| Pickup self-order (menu→pickup→cart→pay-at-counter→canonical order→KDS→status) | **COMPLETE** | `/shop/order` pickup `main.py:2914` |
| Hashed status token + status page (reused all channels) | **COMPLETE** | `pos_order.py:23`, `/checkout/s/<token>` |
| Table identity (per-table bearer token, validated — can't tamper table_id) | **COMPLETE (static bearer)** | `restaurant.table.mezze_qr_token` `models/restaurant_table.py:15`; `_qr_resolve` `main.py:2373` |
| Table QR ≠ Payment QR (separate routes/models) | **COMPLETE** | `/qr/*` (order) vs `/payment/qr/*` (bank) |
| Online payment reuse (S2C-5 `payment.transaction`, exactly-once KDS) | **COMPLETE** | `mezze_online_payment.py:76` |

## MISSING — what S4 ADDS

1. **KIOSK mode — MISSING entirely** (biggest build): no self-service full-screen mode, start/home, eat-in/takeaway, inactivity reset + privacy clear, completion+reset, large touch. `grep kiosk` = 0 hits.
2. **Modifier required / min / max / default** — server does not model or enforce them (only single vs multi + `price_extra`).
3. **Pause/resume + channel admin config** — no per-branch enable/pause of QR / pickup / kiosk, no pay-policy/language/service-location settings; storefront open/closed is implicit (session-open only).
4. **Self-order / by-channel analytics** — `mezze_channel` stored but never reported; `_branch_stats` is branch-only.
5. **Table-QR "closed"/pause gate** — `/qr/*` AUTO-OPENS a pos.session on a customer scan (`_ensure_open_session` `main.py:739`); no closed/paused gate (unlike the shop path which returns `store_closed`).
6. **qr.html combo & half-&-half customer UX** — server + shop.html support them; qr.html renders modifiers only. (frontend-only)
7. **Per-channel availability** — 86/menu are branch-global; no per-channel (QR/pickup/delivery/kiosk). **DEFER for v1** (global 86 + `available_in_pos` suffice; documented).
8. **QR table token is a static bearer** (never rotated). **DEFER** — validated + adequate; rotation is a hardening nice-to-have.

## S4 build plan (ADD only)
- **Kiosk**: a new `static/kiosk.html` kiosk MODE reusing the SAME `/shop/*` catalog + a kiosk order path that creates an UNPAID pay-at-counter canonical order (like pickup), eat-in/takeaway service mode, `mezze_channel='kiosk'`, returns a pickup number; client inactivity reset + completion reset + privacy clear. **No faked cash** (pay-at-counter = PAYMENT_DUE).
- **Pause/resume**: per-branch self-order pause flag; gate `/qr/menu|order`, `/shop/order`, kiosk; staff toggle; `/selforder/status` health.
- **Modifier min/max/required**: model on the modifier payload + validate server-side at order (reject invalid selections; browser can't bypass).
- **Self-order analytics**: `/selforder/report` grouped by `mezze_channel`.
- **qr.html combo/half UX** (frontend). Validator + tests + browser.
