# Mezze Customer Ordering & Self-Service — Certification Matrix (S4 §91)

**SOFTWARE CERTIFIED** = code path exists + CI-tested + browser-accepted with DB proof.
**PHYSICAL / EXTERNAL PENDING** = requires hardware / provider credentials not present. Never blurred.

| Capability | Status | Notes |
|---|---|---|
| QR Menu (browse real catalog, categories, product, options) | **SOFTWARE CERTIFIED** | `/qr/menu`, `/shop/menu`; server catalog, no mocks |
| Table-QR Ordering (place → append to the table's open draft → bill → pay/pay-online) | **SOFTWARE CERTIFIED** | `/qr/order` reuses `_do_fire`; add-more-later; KDS exactly once |
| Two-phone concurrency / double-submit / lost-response | **SOFTWARE CERTIFIED** | pg advisory lock on `table_id` + `fire_uuid` idempotency |
| Table identity security (bearer token, validated; can't tamper `table_id`) | **SOFTWARE CERTIFIED** | `restaurant.table.mezze_qr_token` (rotation = documented future hardening) |
| Table QR ≠ Payment QR | **SOFTWARE CERTIFIED** | `/qr/*` (order) vs `/payment/qr/*` (bank) — separate models/routes |
| Pickup self-order | **SOFTWARE CERTIFIED** | menu→pickup→pay-at-counter→canonical order→KDS→status |
| **Kiosk software** (start/home, service mode, cart, pay-at-counter, completion, inactivity reset, privacy clear) | **SOFTWARE CERTIFIED** | `static/kiosk.html` + `/shop/order` fulfillment=kiosk; UNPAID pay-at-counter (never faked) |
| Kiosk cash | **NOT FAKED** | no "customer selected cash → pretend collected"; pay-at-counter = PAYMENT_DUE only |
| Kiosk **physical hardware** | **NOT TESTED** | no kiosk device available |
| Kiosk **integrated card terminal** | **NOT CERTIFIED** | native Odoo kiosk = Adyen/Stripe-terminal-only; Mezze kiosk v1 = pay-at-counter; terminal path = S2C-3 software / physical PENDING |
| Server-authoritative pricing / tax | **SOFTWARE CERTIFIED** | `_build_lines`; §63 — client price/discount stripped for customer channels (`_sanitize_customer_lines`) |
| Modifiers (single-select ≤1 enforced server-side; multi optional) | **SOFTWARE CERTIFIED** | `_validate_modifiers`; injection-proof `_line_attr_values`. Explicit min/max beyond single-select = DEFERRED (not natively modeled) |
| Combos / half-&-half (one-per-group, server-repriced) | **SOFTWARE CERTIFIED (server + storefront)** | `_resolve_combo`; table-QR combo picker UI = minor parity item (server + shop.html support it) |
| Product 86 (branch-global, revalidated at checkout, bus push) | **SOFTWARE CERTIFIED** | blocks all self-order channels incl kiosk |
| Channel pause / resume + governance | **SOFTWARE CERTIFIED** | `/selforder/pause`; paused ⇒ 409, table-QR won't auto-open a session |
| Self-order health / status | **SOFTWARE CERTIFIED** | `/selforder/status` (public, no internals leaked) |
| Customer status / tracking (secure hashed token) | **SOFTWARE CERTIFIED** | one shared O1 token contract across qr/pickup/kiosk/delivery |
| By-channel analytics | **SOFTWARE CERTIFIED** | `/selforder/report` — orders/revenue/AOV/payment-mix/cancellations/top-items |
| Arabic / RTL / mobile / dark / a11y | **SOFTWARE CERTIFIED** | native i18n + kiosk bilingual EN/AR, large touch targets |
| Per-channel product availability | **DEFERRED** | branch-global 86 + `available_in_pos` suffice for v1 (documented) |

## Odoo native coexistence
Native `pos_self_order` (Community OWL app) is **NOT the production customer frontend** — Mezze's
storefront + table-QR + kiosk is the ONE customer-ordering product (native self-order left OFF to
avoid two competing products). **Native kiosk payment = Adyen/Stripe-terminal-only**; Mezze does NOT
inherit broader kiosk payment — kiosk v1 pays at the counter. See `odoo-self-order-audit.md`.
