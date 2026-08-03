# S2C-5 — Online Customer Payment Audit (Odoo 19 source)

> Audited against the installed local source before any code was written. Every
> claim cites a file. Overriding conclusion: **Odoo already owns the entire online
> customer-payment engine** (`pos_online_payment` + the `payment` framework +
> provider addons). Mezze must NOT build a second one — it wires its customer
> channels to the native flow and adds pay-before-fire KDS timing + revalidation +
> a customer status surface.

## 1. Native online-payment bridge — `pos_online_payment` (ODOO CORE)

`addons/pos_online_payment` (depends `point_of_sale`, `account_payment`) is the
native POS ↔ `payment.transaction` bridge:

- **Public, tokenized pay page**: `GET /pos/pay/<int:pos_order_id>?access_token=…`
  (`controllers/payment_portal.py:81`, `auth='public'`) — renders
  `pos_online_payment.pay` with the order total + the allowed providers.
  `_check_order_access(pos_order_id, access_token)` (`:14`) authorizes via the
  order's **native `access_token`** (pos.order inherits `portal.mixin`,
  `point_of_sale/models/pos_order.py:27`, `_ensure_access_token()` at `:1197`).
- **Transaction route**: `POST /pos/pay/transaction/<id>` (`:161`, jsonrpc, public)
  creates the `payment.transaction` with `custom_create_values={'pos_order_id': …}`.
  It is **server-authoritative**: amount = `_get_amount_to_pay(order)` and a client
  amount that differs raises *"The amount to pay has changed"* (`:220`); currency is
  forced to `order.currency_id` and the client currency is ignored (`:213`);
  tokenization is refused for the public user (`:198`).
- **Provider discovery**: `_get_allowed_providers_sudo` = providers compatible for
  (company, partner, amount, currency) ∩ the method's `online_payment_provider_ids`
  (`:51`, `pos_payment_method.py:30`). Customer never picks a hardcoded brand.
- **Exactly-once finalization**: `payment.transaction._post_process` →
  `_process_pos_online_payment` (`pos_online_payment/models/payment_transaction.py`).
  For a tx in `authorized|done` whose `payment_id.pos_order_id` is not yet set, it
  creates the account.payment, `order.add_payment({…, online_account_payment_id: …})`,
  and `_process_saved_order` when fully paid. The `not tx.payment_id.pos_order_id`
  guard + the account.payment↔pos.payment link make **duplicate / concurrent / lost
  -response** callbacks converge to ONE pos.payment natively. It then bus-notifies
  `ONLINE_PAYMENTS_NOTIFICATION`.
- **online-payment method**: `pos.payment.method.is_online_payment` +
  `online_payment_provider_ids` (`pos_payment_method.py:11,12`);
  `_get_or_create_online_payment_method(company, config)` (`:110`).

## 2. `payment.transaction` = the authority (ODOO CORE)

`addons/payment/models/payment_transaction.py`: `state` selection
(`draft/pending/authorized/done/cancel/error`), `_process` (`:737`),
`_search_by_reference` (`:757`), `_apply_updates` (`:852`), `_set_pending/_set_done/
_set_canceled/_set_error` (`:909-979`). Providers drive these; controllers never set
`state='done'` directly. **Mezze reuses this as the sole financial authority for
online payments and creates NO second transaction engine.** (`mezze.payment.transaction`
in `models/mezze_payment.py` is dormant TODO scaffolding — it stays for possible
channel linkage only and is NOT a financial authority.)

## 3. Demo provider — `payment_demo` (ODOO CORE, used first)

`direct` (inline) flow with an explicit **outcome chooser**: the pay form has a
`simulated_payment_state` `<select>` (done / pending / cancel / error)
(`views/payment_demo_templates.xml:205`); the JS posts to the jsonrpc route
`/payment/demo/simulate_payment` (`controllers/main.py:8`, public) →
`_process('demo', data)` → `_apply_updates` maps state → `_set_pending/_set_done/
_set_canceled/_set_error` (`models/payment_transaction.py:122`). No banking
credentials needed. Feature flags: refund `partial`, tokenization `True`, manual
capture `partial`, express `True`. Mezze proves the whole flow on Demo first.

## 4. Paymob provider — `payment_paymob` (PAYMOB NATIVE) — capabilities ACTUALLY found

| Capability | Truth (from source) |
|---|---|
| Flow | **Redirect** (unified checkout); `redirect_form` (`data/payment_provider_data.xml:6`), `_get_specific_rendering_values` builds a Paymob intention (`models/payment_transaction.py:42`) |
| Notification / HMAC | Native `POST /payment/paymob/webhook` + `GET /payment/paymob/return` (`controllers/main.py:24,37`), verified by `_verify_signature` → `_compute_signature` (SHA-512 HMAC, `hmac.compare_digest`) (`main.py:90,111`). **Mezze reuses this; adds no HMAC verifier.** |
| Refund | **NOT supported** — no `_send_refund_request`, `support_refund` stays base default `'none'` (`payment/models/payment_provider.py:268`) |
| Partial refund | **NOT supported** |
| Tokenization | **NOT supported** (`support_tokenization` unset; saved-card gateways skipped in sync, `payment_provider.py:169`) |
| Manual capture | **NOT supported** (auth/capture gateways skipped in sync) |
| Express checkout | **NOT supported** (Apple/Google Pay gateways skipped, `payment_provider.py:162`) |
| Countries / currencies | EG→EGP, AE→AED, OM→OMR, SA→SAR, PK→PKR (`const.py:5`); country field domain-restricted (`payment_provider.py:30`) |
| Credential fields | `paymob_account_country_id`, `paymob_public_key`, `paymob_secret_key` (group_system), `paymob_hmac_key`, `paymob_api_key` (`payment_provider.py:24-50`) |

**v1 product policy** (matches spec §3): Paymob Online / Redirect / Test = SUPPORTED;
Tokenization / Manual Capture / Native Refund / Express Checkout = **NOT CLAIMED**
(source confirms unsupported). Paymob refund of a paid order ⇒ **EXTERNAL / MANUAL
PROVIDER ACTION** (Mezze's product/accounting refund engine still applies to the POS
side).

## 5. Existing Mezze channels (MEZZE EXISTING)

All create real **draft `pos.order`s** and mint a secure **`mezze_status_token`**
(SHA-256 hash, TTL, rate-limited public `shop_status`, opaque-token-only,
`models/pos_order.py:42-99`, `controllers/main.py:2828`):

- **Table QR**: `qr_order` → `_do_fire` draft (`main.py:2414`); `qr_bill` mints status
  token + `mezze_channel='qr'` (`:2484`).
- **Pickup**: `shop_order` pickup → `_do_fire` draft + `mezze_channel='pickup'` (`:2804`).
- **Delivery**: `shop_order` delivery — zone **min-order + fee** enforced server-side
  (`:2750-2766`, `models/delivery.py:14`); today creates a **paid** pay-on-delivery
  order.

**KDS today fires on CREATE** (`_do_fire` → `_make_station_tickets` → `_publish_kds`,
`main.py:1701,263`), decoupled from payment. For L5 pay-before-fire, online orders
must be created **deferred** (no fire) and fire **once** on authoritative payment.

## 6. Mezze bridge required (MEZZE BRIDGE REQUIRED)

1. `depends += pos_online_payment, payment_demo`; provision an `is_online_payment`
   method + Demo provider on the config.
2. Online-checkout path: create the channel draft order **without firing** (server-
   authoritative pricing + 86/zone revalidation), then hand the customer to the
   NATIVE `/pos/pay/<id>?access_token` page. No card fields, no Mezze payment engine.
3. `payment.transaction._process_pos_online_payment` extension: after the native
   finalization, **fire KDS exactly once** for the paid online order (guarded flag)
   and expose customer status. Nothing fires on pending/failed/canceled.
4. Tokenized customer status (`/checkout/status`) over the existing status-token +
   the authoritative `payment.transaction` / `pos.order` state (return-not-authority).
5. Reconciliation detectors (tx-done-no-payment, paid-no-tx, amount/currency
   mismatch, orphan tx, manual-refund-required) + go-live validator + admin surface.

## 7. External certification (EXTERNAL CERTIFICATION / NOT SUPPORTED)

- Paymob **sandbox/live** external journey — only if configured credentials already
  exist; otherwise NOT EXECUTED (does not block software completion).
- Paymob **refund / tokenization / manual capture / express** — NOT SUPPORTED (source).
