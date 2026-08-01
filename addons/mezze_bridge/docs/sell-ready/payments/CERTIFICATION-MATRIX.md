# Mezze Payments — Certification Matrix (S2 §56)

Strict distinction: **SOFTWARE** = code path exists + tested in CI; **CERTIFIED** = verified on the real
device/provider (later commercial certification). Never blur them.

| Tender | Software | Device/Provider | Notes |
|---|---|---|---|
| L1 Cash | CERTIFIED (suite) | N/A | change≠tendered, partial, mixed, rounding — existing invariants |
| L1 Manual tender (card/wallet/InstaPay/transfer) | Backend PASS · Cashier UX NOT EXECUTED (browser) | N/A (external confirm) | runtime policy + contract endpoints done; POS-shell UI browser-acceptance pending |
| L2 External terminal (manual confirm) | Backend PASS · Cashier UX NOT EXECUTED (browser) | MANUAL COMPATIBILITY / PHYSICAL PENDING | runtime enforcement + reconciliation + contract endpoints done; cashier dialog/receipt browser-acceptance pending |
| L3 Odoo integrated terminal (Stripe/Adyen/…) | SUPPORTED VIA ODOO | NOT TESTED | state-normalization/force-done wrapper = later slice; no hardware cert |
| L4 Bank / payment QR | SUPPORTED VIA ODOO | depends on scheme | classification surface = later slice; separate from Table-QR |
| L5 Online provider framework | SCAFFOLD + reuse | — | idempotency join + demo-provider tests = later slice |
| L5 Paymob | READY (native, installed) | EXTERNAL TEST: NOT EXECUTED | real Test creds pending |
| L6 Customer account / credit | SUPPORTED VIA ODOO | — | credit-limit policy = later slice |
| L7 Cash machine (Cashdro/Cashmatic/Glory) | SUPPORTED VIA ODOO | PHYSICAL: NOT TESTED | absence never blocks cash |

No claim that "every terminal works" or "every provider is certified."
