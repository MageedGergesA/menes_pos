# Cashier payment experience (S2 Slice 2B)

## Backend contract — DONE & green
The cashier UI + receipt consume a stable, authenticated, branch-scoped, secret-free contract
(`controllers/payment.py`, 8 contract tests):
- `POST /payment/devices` — valid devices for branch + method (active, compatible).
- `POST /payment/breakdown` — per-tender breakdown for screen/receipt: configured method name (never the
  engine mode), device, amount, **masked** reference (`••••8421`), confirmation source, external-refund
  status. Verified to contain no PAN/CVV/PIN/secret/`mezze_mode`/`external_terminal`.
- `POST /reconciliation/summary` — per method/device: expected (derived), settlement, difference, status.
- `POST /reconciliation/settlement` — record settlement/count (expected stays read-only).
- `POST /reconciliation/finalize` — 409 `needs_manager_approval` over tolerance; manager approval finalizes.
- `POST /payment/external_refund/confirm` — manager confirms external refund (idempotent, audited).
- `POST /payment/report` — manager totals by method / device + refunds.

## Browser cashier UX — NOT EXECUTED (honest)
The actual POS-shell rendering (payment dialog fields, external-terminal confirmation copy, device selector,
duplicate WARN/manager modal, mixed-tender/partial display, receipt payment breakdown, Arabic RTL receipt,
session-close reconciliation panel, manager reporting view, admin device surface) is **not built/verified
this increment** — there is no in-repo browser/JS acceptance harness on this host. These are frontend
acceptance items (like the on-site/hardware gates) and are honestly reported NOT EXECUTED. The backend
contract above is what makes them a thin, low-risk build once a browser acceptance environment is available.

## Status language (Part 42)
- Manual Card / External-terminal — **Backend: PASS · Cashier UX: NOT EXECUTED (browser)**.
- External terminal physical certification — **PENDING** (S1.2 / device-specific).
Software completion ≠ device certification.
