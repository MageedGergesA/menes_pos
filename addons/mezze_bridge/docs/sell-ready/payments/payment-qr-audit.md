# S2C-4 — Bank App (Payment) QR Audit (Odoo 19 source)

> Audited against the installed local Odoo 19 source before any code was written
> (S2C-4 priorities 1–2). Every claim cites a file in this tree. Payment QR is kept
> completely separate from **Table QR** (self-order `/qr/menu`, `/qr/bill`,
> `/qr/pay` in `controllers/main.py`) — different feature, different routes.

## 1. Native architecture (as it actually is)

**Generation (server-side, native):**
- `pos.payment.method.get_qr_code(amount, free_communication, structured_communication, currency, debtor_partner)`
  (`point_of_sale/models/pos_payment_method.py:222`) → `journal_id.bank_account_id
  .build_qr_code_base64(...)` → a **base64 PNG data-URI** of the QR.
- The **raw payload** the QR encodes is
  `res.partner.bank._get_qr_code_generation_params(qr_method, …)['value']`
  (`account/models/res_partner_bank.py:195,211`). `build_qr_code_url` returns the
  `/report/barcode/?…` render URL, not the raw string.
- **Requirements** (hard-constrained, `pos_payment_method.py:198`):
  `payment_method_type='qr_code'` **AND** `journal_id.type='bank'` **AND**
  `journal_id.bank_account_id` set **AND** `qr_code_method` set **AND**
  `bank_account_id._get_error_messages_for_qr(...)` clean.

**Confirmation (the trust model):**
- POS shows the QR via `pos_store.showQR(payment)` → `get_qr_code` (server) → a
  **`QRPopup`** dialog whose resolved value is a **boolean the cashier chooses**
  (`payment_screen.js:319-321`: `resp = await showQR(line); isPaymentSuccessful =
  line.handlePaymentResponse(resp)`).
- **There is NO automatic bank/provider webhook.** Native Odoo POS Bank-App-QR is
  **cashier-confirmed / manual** — the cashier visually verifies the customer paid
  and confirms in the popup. This is the same trust class as an L2 external
  terminal (manual confirmation), NOT a provider-verified payment.

Therefore the S2C-4 trust rule resolves to: **preserve Odoo's manual
cashier-confirmation model.** The server owns amount/currency/account/QR payload;
the cashier confirms; the payment provenance is **manual** (bank NOT auto-verified).
A browser `{"paid": true}` never mints a payment on its own — the confirm is an
authenticated cashier action bound to a server-generated QR whose amount must still
equal the order's current remaining (stale QR ⇒ rejected).

## 2. QR-method availability in THIS installed source

`res.partner.bank._get_available_qr_methods()` returns a method only when the
providing module is **installed**. In the Mezze DB (`mezze_test`) **none** are
installed by default — so `payment_method_type` does not even offer `qr_code` until
a QR module is added. Available providers in the tree:

| Method | Module | Standalone? | Currency / account requirement |
|---|---|---|---|
| SEPA Credit Transfer (`sct_qr`) | `account_qr_code_sepa` | **Yes** | EUR + SEPA IBAN + holder name (EPC069-12 payload `BCD\n002\n1\nSCT…`) |
| EMV Merchant-Presented (`emv_qr`) | `account_qr_code_emv` | **No** — needs a country module for merchant-account info + country match | currency in EMV `CURRENCY_MAPPING` |
| Pix (BR) | `l10n_br` | country | BRL |
| PromptPay (TH) | `l10n_th` | country | THB |
| PayNow (SG) | `l10n_sg` | country | SGD |
| VietQR (VN) | `l10n_vn` | country | VND |
| QRIS (ID) | `l10n_id` | country | IDR |
| FPS (HK) | `l10n_hk` | country | HKD |
| KHQR (KH) | `l10n_kh` | country | KHR/USD |
| Swiss QR-bill (CH) | `l10n_ch` | country | CHF/EUR |

**Egypt / InstaPay:** there is **no** bank-app payment-QR method for Egypt in this
source (`l10n_eg_edi_eta` provides an **ETA e-invoicing** QR on `account.move`, NOT
a `res.partner.bank` payment method). Moreover **EGP is not in EMV's
`CURRENCY_MAPPING`** (`account_qr_code_emv/const.py`), so even generic EMV cannot
encode an EGP amount. ⇒ **Egypt / InstaPay QR: NOT CERTIFIED** (and not even
generatable) until proven against compatible Egyptian banking apps with a real
Egyptian QR scheme.

## 3. Mezze design (this slice)

- `mezze_mode='bank_qr'` (auto-classified when `qr_code_method` is set).
- **`mezze.payment.qr`** — a server-side generate/confirm record: `token` (unique),
  order, method, `amount`, `remaining_snapshot`, `reference`, `state`
  (pending/confirmed/cancelled), `pos_payment_id`. The QR **image** and **raw
  payload** come from the native `get_qr_code` / `_get_qr_code_generation_params`
  (Mezze writes no QR-format code).
- **Server-authoritative amount/currency/account** from the order + the method's
  bank account. The browser cannot inflate the amount.
- **Stale invalidation:** confirm requires `current_remaining == remaining_snapshot`
  (any order/remaining change ⇒ `stale_qr`, forcing a regenerate). Overpay rejected.
- **Manual confirmation** (preserves Odoo's model): the cashier confirms receipt;
  provenance `manual` (bank not auto-verified). ONE `pos.payment` per token
  (idempotent via `tender_key=token` + `SELECT … FOR UPDATE` + the existing
  `unique(pos_order_id, mezze_tender_key)` constraint) ⇒ duplicate/concurrent
  confirmation yields exactly one payment. Cancel ⇒ 0 payment, order stays payable.
- Routes `/payment/qr/generate|confirm|cancel|status` (classified in authz +
  route_scope). No Mezze bearer/session token is ever placed in the QR payload —
  the payload is exactly the native bank string (IBAN/amount/currency/reference).

## 4. Decode verification approach

No Python QR decoder (pyzbar/opencv/libzbar) is installed here. The QR image is
proven to encode the native payload two ways: (a) **byte-identical re-encode** — the
endpoint's image equals `image_data_uri(b64(ir.actions.report.barcode(**params)))`
for the native `params` (same encoder, same input ⇒ same bytes); and (b) an
in-browser **jsQR decode** of the displayed `<img>`, asserting the decoded string
equals the native payload (amount/currency/IBAN/reference) and contains **no** Mezze
token. The raw payload is inspected directly for amount/currency/account/reference.
