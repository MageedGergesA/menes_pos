# Paymob — reuse the native Odoo acquirer (Option A)

We do **not** hand-roll Paymob. Odoo 19 Community ships `payment_paymob`
(LGPL-3) — a full acquirer with auth/order/payment-key, unified checkout, and an
HMAC-SHA512-verified webhook. `mezze_bridge` depends on it and delegates.

## Architecture

```
POS card tender
   │  /mezze/w1/payment/intent {order_uuid, amount, partner_id}
   ▼
mezze_bridge (controllers/w1.py)
   │  finds the enabled payment.provider (code='paymob')
   │  creates a native payment.transaction (operation=online_redirect)
   │  tx._get_processing_values()  → unified-checkout URL + publicKey/clientSecret
   ▼
returns { checkout_url }  → POS opens Paymob checkout
   ▼
Paymob → native webhook  /payment/paymob/webhook   (HMAC verified by Odoo)
   │  payment.transaction -> 'done'
   ▼
POS polls  /mezze/w1/payment/status {reference}  → state 'done' → complete the sale
```

Zero custom crypto: the HMAC calculation, webhook, and refunds all live in the
maintained `payment_paymob` module.

## One-time setup (per merchant)

1. Install: `payment_paymob` installs automatically (it's a dependency now).
2. Odoo → **Accounting → Configuration → Payment Providers → Paymob** → set
   **State = Enabled** (or *Test*), **Account Country = Egypt**, and paste from the
   Paymob dashboard: **API Key**, **Public Key**, **Secret Key**, **HMAC Key**.
3. Activate the card/wallet payment methods you want on the provider.
4. That's it — `/mezze/w1/payment/intent` will now return a real `checkout_url`.

Until a provider is enabled, `payment/intent` returns
`{ok:false, error:'no_paymob_provider'}` — an honest refusal, never a fake charge.

## Endpoints (mezze side)

| Route | Does |
|---|---|
| `/mezze/w1/payment/intent` | create native tx, return checkout URL |
| `/mezze/w1/payment/status` | poll `payment.transaction.state` by reference |

The capture path is the **native** `/payment/paymob/webhook` — nothing to build.

## Frontend wiring (next)

In `static/pos.html` a non-cash tender should call `payment/intent`, open the
returned `checkout_url` (redirect/iframe), then poll `payment/status` until
`done` before completing the sale. Cash stays the one-tap path.

## Card-present (Phase 2)

`payment_paymob` is the **online/redirect** flow (good for QR-order, delivery
prepay, pay-by-link). For fast **card-present** counter tapping, evaluate a POS
terminal integration (`pos_paymob` on the Apps Store / Paymob terminal SDK)
later — a separate bet, not this module.
