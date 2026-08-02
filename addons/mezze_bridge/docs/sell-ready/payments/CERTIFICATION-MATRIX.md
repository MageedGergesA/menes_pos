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
| L4 Bank / payment QR | SUPPORTED VIA ODOO | depends on scheme | classification surface = later slice; separate from Table-QR |
| L5 Online provider framework | SCAFFOLD + reuse | — | idempotency join + demo-provider tests = later slice |
| L5 Paymob | READY (native, installed) | EXTERNAL TEST: NOT EXECUTED | real Test creds pending |
| L6 Customer account / credit | SUPPORTED VIA ODOO | — | credit-limit policy = later slice |
| L7 Cash machine (Cashdro/Cashmatic/Glory) | SUPPORTED VIA ODOO | PHYSICAL: NOT TESTED | absence never blocks cash |

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

No claim that "every terminal works" or "every provider is certified."
