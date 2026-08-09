# CP12 — External Provider Matrix

`CERTIFIED` requires real external/provider evidence already present — never inferred from a mock.

| Provider / integration | Software status | External certification | Notes |
|---|---|---|---|
| Paymob (online, Egypt) | SOFTWARE READY (native pos_online_payment bridge; refund NOT claimed) | EXTERNAL CERTIFICATION PENDING | Live keys + provider sign-off required |
| Demo online provider | SOFTWARE READY (used for tests) | N/A | Test provider only |
| Integrated payment terminal (S2C-3) | SOFTWARE READY (orchestration + idempotency) | EXTERNAL CERTIFICATION PENDING | Per-device/provider cert |
| Bank-app QR (S2C-4) | SOFTWARE READY | EXTERNAL CERTIFICATION PENDING | Not certified for InstaPay etc. |
| Aggregators (Talabat/Jahez/Careem…) | SOFTWARE READY (generic HMAC intake, SKU map, idempotent) | EXTERNAL CERTIFICATION PENDING | Provider protocol/cert is separate work |
| Cash machine / recycler (S2C-7) | SOFTWARE READY (Glory orchestration) | EXTERNAL CERTIFICATION PENDING | Device cert pending |
| SMS / WhatsApp / email | via outbox (best-effort, non-blocking) | EXTERNAL CERTIFICATION PENDING | Not required for order commit |
| Fiscal / e-invoice (ETA/ZATCA) | SOFTWARE READY (einvoice model) | EXTERNAL CERTIFICATION PENDING | Country cert + token/device separate |
