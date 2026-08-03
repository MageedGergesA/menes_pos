# Mezze Payments — Certification Matrix (S2 §56)

Strict distinction: **SOFTWARE** = code path exists + tested in CI; **CERTIFIED** = verified on the real
device/provider (later commercial certification). Never blur them.

| Tender | Software | Device/Provider | Notes |
|---|---|---|---|
| L1 Cash | CERTIFIED (suite + real browser) | N/A | change≠tendered, partial, mixed, rounding — browser-accepted S2C-1/S2C-2 |
| L1 Manual electronic tender (card/wallet/InstaPay/transfer/custom) | **CERTIFIED (software: suite + real browser)** | N/A (external confirm) | S2C-2: config-driven method buttons, reusable manual-tender dialog, device/reference/duplicate policy, partial + mixed, manager-PIN approval — browser-accepted + DB-proven |
| L2 External terminal (manual confirmation) | **CERTIFIED (software: suite + real browser)** | **COMPATIBLE VIA MANUAL CONFIRMATION · PHYSICAL DEVICE-SPECIFIC ACCEPTANCE: PENDING** | S2C-2: device selector (/payment/devices), "Confirm only after the external terminal shows APPROVED" notice, manual provenance persisted. Mezze is NOT electronically integrated with the terminal — no hardware/API integration claimed |
| L3 Integrated terminal platform (Mezze orchestration) | **CERTIFIED (software: suite + real browser)** | N/A (orchestration layer) | S2C-3: one terminal_service, normalized states, server-authoritative outcome, one-txn→one-payment idempotency, lost-response recovery, manager-gated Force Done (provenance `manual_force_done` + recon flag), mixed integrated+cash — browser-accepted with the TEST simulator + DB-proven. Mezze reimplements NO provider protocol |
| L3 Odoo integrated terminal (Stripe/Adyen/Razorpay/Mercado Pago/Viva/QFPay/Pine Labs) | **SUPPORTED VIA ODOO** | **MEZZE STANDALONE CASHIER INTEGRATION: PENDING · PHYSICAL DEVICE CERTIFICATION: NOT TESTED** | S2C-3 audit: native adapters are tightly coupled to the native POS store (category C), so they are not yet wired to the standalone cashier; no protocol copied, no hardware cert. See `integrated-terminal-audit.md` |
| L4 Bank App (Payment) QR platform | **CERTIFIED (software: suite + real browser)** | scheme-specific (see matrix) | S2C-4: native `get_qr_code` generator reused (Mezze writes no QR format), server-authoritative amount/currency/account, machine-decodable QR (browser jsQR decode == native payload), stale-QR invalidation, cancel=0, duplicate/concurrent confirm=1, mixed cash+QR, manual cashier confirmation (Odoo's own model — no auto bank webhook), receipt/recon/report. **Separate from Table QR.** |
| L4 Egypt / InstaPay QR | **NOT SUPPORTED / NOT CERTIFIED** | N/A | No Egyptian bank-app payment-QR method exists in this Odoo source (l10n_eg is ETA e-invoicing QR, not a `res.partner.bank` payment method); EGP is not even in EMV's currency map. Requires a real Egyptian QR scheme + compatible banking-app testing |
| L5 Online provider framework | **CERTIFIED (software: suite + real browser)** | N/A | S2C-5: reuses Odoo `pos_online_payment` + `payment.transaction` as the sole authority (no second engine); channel→draft→native `/pos/pay/<id>?access_token`; server-authoritative amount/currency; 86/zone revalidation pre-order; exactly-once tx→pos.payment finalization (native) + pay-before-fire KDS once; tokenized customer status (return-not-authority). Customer channels: QR-table / pickup / delivery |
| L5 Odoo Demo provider | **END-TO-END CERTIFIED** | N/A | success / pending→done / failure / cancel + duplicate/concurrent/lost-response finalization → ONE effect — suite + real customer browser |
| L5 Paymob | **SOFTWARE PATH CERTIFIED (redirect)** | **SANDBOX: NOT EXECUTED (creds unavailable) · LIVE: NOT CERTIFIED** | native redirect + HMAC webhook reused (Mezze adds no HMAC/parser); wired through the same provider/transaction path as Demo |
| L5 Paymob refund | **NOT SUPPORTED VIA ODOO** | — | source confirms `support_refund='none'`; provider money refund is EXTERNAL / MANUAL — Mezze's POS refund engine still applies |
| L5 Paymob tokenization / manual capture / express checkout | **NOT CLAIMED / NOT SUPPORTED** | — | source confirms unset; saved-card / auth-capture / Apple&Google-Pay gateways skipped in Paymob sync |
| L6 Customer account / credit | **CERTIFIED (software: suite + real browser)** | N/A (native receivable) | S2C-6: reuses Odoo native `partner.credit`/`credit_limit` (no second ledger); configurable policy (warn/manager-approval/hard-block), row-locked server-authoritative projected exposure incl open-session pay_later, deposit/settlement via native inbound `account.payment`, customer selector + safe summary, cashier can never self-approve. Cross-branch credit on disconnected Edge DBs: **NOT CLAIMED**. See `customer-credit-audit.md` |
| L7 Cash-machine orchestration (Mezze) | **CERTIFIED (software: suite + real browser)** | N/A (orchestration layer) | S2C-7: same server-authoritative spine as L3 (kind='cash_machine'), server-decided outcome, forged-success refused, one-txn→one-payment idempotency + concurrency lock, inserted≠payment when change returned (pos.payment ≤ due), cancel/connection-failure=0-delta, uncertain→manager Force Done, TEST-only simulator (prod-refused). No device protocol written. Browser-accepted + DB-proven |
| L7 Glory cash machine (`pos_glory_cash`) | **SUPPORTED VIA ODOO** | **MEZZE STANDALONE ADAPTER: PENDING · PHYSICAL: NOT TESTED** | Only native cash machine present in this Odoo 19; browser-direct WebSocket welded to native PosStore (like L3), so not yet wired to the standalone cashier; no protocol copied. Refund = manager-only cash dispense natively → standalone adapter PENDING. Cash-count supported natively. See `cash-machine-audit.md` |
| L7 Cashdro / Cashmatic | **NOT PRESENT IN THIS ODOO 19** | — | No `pos_cashdro` / `pos_cashmatic` addon in `odoo/addons` or `enterprise2/`; not faked |

## Localization (cashier payment UI)

| Aspect | Status |
|---|---|
| RTL layout | **PASS** (real browser — mirrored via logical CSS, dark+RTL, no clipping) |
| Cashier payment i18n (Arabic) | **PASS** — all S2C cashier chrome translated via Odoo's native translation system (`i18n/ar.po`, `_t`/`translateFn`, `ir.http` frontend exposure). No custom dictionary |
| Arabic real browser | **PASS** — shell, Manual Card, duplicate WARN, manager approval, mixed tender, receipt, dark+RTL browser-verified with a real `ar_001` session; fresh-install + upgrade Arabic verified |
| Numbers / references / order refs | bidi-safe (LTR-isolated): `EGP 500.00`, `TERM-CARD-1`, `260-1-000317`, `••••9911` render correctly in RTL |
| Intentionally not translated | configured payment-method names, device codes, product names, externally-entered references/order numbers (business/technical data) |

## Integrated-terminal provider matrix (this installed Odoo 19 source)

Recorded from the LOCAL source, not documentation. See `integrated-terminal-audit.md`.

| Provider | Module | Installed | Odoo support | Mezze software bridge | Physical cert |
|---|---|---|---|---|---|
| Adyen | `pos_adyen` | available | YES (server-mediated) | orchestration ready · standalone wiring PENDING | NOT TESTED |
| Stripe | `pos_stripe` | available | YES (server-mediated) | orchestration ready · standalone wiring PENDING | NOT TESTED |
| Razorpay | `pos_razorpay` | available | YES | orchestration ready · standalone wiring PENDING | NOT TESTED |
| Mercado Pago | `pos_mercado_pago` | available | YES (server-mediated) | orchestration ready · standalone wiring PENDING | NOT TESTED |
| Viva.com | `pos_viva_com` | available | YES (server-mediated) | orchestration ready · standalone wiring PENDING | NOT TESTED |
| QFPay | `pos_qfpay` | available | YES (server-mediated) | orchestration ready · standalone wiring PENDING | NOT TESTED |
| Pine Labs | `pos_pine_labs` | available | YES | orchestration ready · standalone wiring PENDING | NOT TESTED |
| Ingenico / SIX / Worldline / Mollie / DPO / Tyro | — | NOT PRESENT | — | — | — |
| **TEST simulator** | `mezze_bridge` | built-in | N/A | **CERTIFIED (test-only; never selectable in production)** | N/A |

S2C-3 closes SOFTWARE integrated-terminal support (Mezze orchestration + simulator).
It does NOT certify any physical reader or provider merchant account.

## Bank-app (payment) QR method matrix

QR support activates only when a QR-method module is installed AND a method is
configured with a bank journal + bank account + `qr_code_method`. Recorded from
local source. See `payment-qr-audit.md`.

| Scheme | Module | Standalone | Mezze software | App-tested |
|---|---|---|---|---|
| SEPA Credit Transfer (`sct_qr`) | `account_qr_code_sepa` | YES (EUR + IBAN) | **CERTIFIED** (native generate + orchestration, browser-decoded) | banking-app scan NOT tested |
| EMV Merchant-Presented (`emv_qr`) | `account_qr_code_emv` | needs a country module | orchestration ready | NOT tested |
| Pix / PromptPay / PayNow / VietQR / QRIS / FPS / KHQR / Swiss QR-bill | l10n_br/th/sg/vn/id/hk/kh/ch | country | orchestration ready · install country module | NOT tested |
| **Egypt / InstaPay** | — | **NONE** | **NOT SUPPORTED** | **NOT CERTIFIED** |

The Mezze QR orchestration (generate/confirm/cancel/stale/idempotent/mixed) is
scheme-agnostic and software-certified; per-scheme banking-app compatibility (does
a real bank app scan+pay this QR) is a separate acceptance and is NOT claimed.

No claim that "every terminal works" or "every provider is certified."
