# Mezze Payments — Certification Matrix (S2 §56)

Strict distinction: **SOFTWARE** = code path exists + tested in CI; **CERTIFIED** = verified on the real
device/provider (later commercial certification). Never blur them.

| Tender | Software | Device/Provider | Notes |
|---|---|---|---|
| L1 Cash | CERTIFIED (suite + real browser) | N/A | change≠tendered, partial, mixed, rounding — browser-accepted S2C-1/S2C-2 |
| L1 Manual electronic tender (card/wallet/InstaPay/transfer/custom) | **CERTIFIED (software: suite + real browser)** | N/A (external confirm) | S2C-2: config-driven method buttons, reusable manual-tender dialog, device/reference/duplicate policy, partial + mixed, manager-PIN approval — browser-accepted + DB-proven |
| L2 External terminal (manual confirmation) | **CERTIFIED (software: suite + real browser)** | **COMPATIBLE VIA MANUAL CONFIRMATION · PHYSICAL DEVICE-SPECIFIC ACCEPTANCE: PENDING** | S2C-2: device selector (/payment/devices), "Confirm only after the external terminal shows APPROVED" notice, manual provenance persisted. Mezze is NOT electronically integrated with the terminal — no hardware/API integration claimed |
| L3 Odoo integrated terminal (Stripe/Adyen/…) | SUPPORTED VIA ODOO | NOT TESTED | state-normalization/force-done wrapper = later slice; no hardware cert |
| L4 Bank / payment QR | SUPPORTED VIA ODOO | depends on scheme | classification surface = later slice; separate from Table-QR |
| L5 Online provider framework | SCAFFOLD + reuse | — | idempotency join + demo-provider tests = later slice |
| L5 Paymob | READY (native, installed) | EXTERNAL TEST: NOT EXECUTED | real Test creds pending |
| L6 Customer account / credit | SUPPORTED VIA ODOO | — | credit-limit policy = later slice |
| L7 Cash machine (Cashdro/Cashmatic/Glory) | SUPPORTED VIA ODOO | PHYSICAL: NOT TESTED | absence never blocks cash |

No claim that "every terminal works" or "every provider is certified."
