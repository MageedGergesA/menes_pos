# S2 — Universal Payments Platform — FINAL CERTIFICATION

Bounded audit after L7 (S2C-7). Scope = ONLY the eight tender layers + the cross-cutting
guarantees already built. **No new functionality is proposed from theoretical gaps.**

Strict vocabulary (never blurred):
- **SOFTWARE CERTIFIED** — code path exists, covered by the CI suite, and browser-accepted with DB proof.
- **SUPPORTED VIA ODOO** — Odoo ships the integration, but Mezze's standalone-cashier adapter is not wired yet.
- **EXTERNAL CERTIFICATION PENDING** — real provider sandbox/live not executed.
- **PHYSICAL CERTIFICATION PENDING** — no hardware tested.
- **NOT SUPPORTED** — not present / not claimed.

## Per-layer verdict

| # | Layer | Verdict | Evidence |
|---|---|---|---|
| L1 | Cash | **SOFTWARE CERTIFIED** | suite + browser: change≠tendered, partial, mixed, rounding |
| L1 | Manual tender (card/wallet/InstaPay/transfer/custom) | **SOFTWARE CERTIFIED** | S2C-2 device/reference/duplicate policy, manager PIN |
| L2 | External terminal (manual confirm) | **SOFTWARE CERTIFIED** · physical device-specific acceptance PENDING | S2C-2; Mezze not electronically integrated (by design) |
| L3 | Integrated-terminal orchestration | **SOFTWARE CERTIFIED** | S2C-3 terminal_service, server-authoritative, one-payment idempotency, force-done, lost-response |
| L3 | Real terminal adapters (Stripe/Adyen/…) | **SUPPORTED VIA ODOO** · standalone adapter PENDING · physical NOT TESTED | tightly coupled to native POS |
| L4 | Bank-App QR | **SOFTWARE CERTIFIED** | S2C-4 native `get_qr_code`, decodable, stale-invalidation, mixed |
| L4 | Egypt / InstaPay QR | **NOT SUPPORTED / NOT CERTIFIED** | no Egyptian payment-QR method in this Odoo source |
| L5 | Online-provider framework | **SOFTWARE CERTIFIED** | S2C-5 native `payment.transaction` authority, exactly-once, pay-before-fire KDS |
| L5 | Odoo Demo provider | **SOFTWARE CERTIFIED (end-to-end)** | success/pending/failure/cancel/duplicate/lost-response → one effect |
| L5 | Paymob | **SOFTWARE PATH CERTIFIED (redirect)** · sandbox NOT EXECUTED · live NOT CERTIFIED | creds unavailable; refund/token/capture NOT claimed |
| L6 | Customer account / credit | **SOFTWARE CERTIFIED** | S2C-6 native receivable, policy gate, deposit/settle, concurrency. Cross-branch Edge credit NOT CLAIMED |
| L7 | Cash-machine orchestration | **SOFTWARE CERTIFIED** | S2C-7 forged-success refused, one-payment, change≠payment, cancel/conn=0, force-done, sim prod-refused |
| L7 | Glory device (`pos_glory_cash`) | **SUPPORTED VIA ODOO** · standalone adapter PENDING · physical NOT TESTED | browser-direct WebSocket welded to native PosStore |
| L7 | Cashdro / Cashmatic | **NOT SUPPORTED (not present in this Odoo 19)** | no addon in `odoo/addons` or `enterprise2/` |

## Cross-cutting

| Aspect | Verdict |
|---|---|
| Partial payment | **SOFTWARE CERTIFIED** (every device layer honours the remaining-balance ceiling) |
| Mixed tender | **SOFTWARE CERTIFIED** (cash+terminal, cash+QR, cash+cash-machine — sum==total, one order) |
| Refund | **SOFTWARE CERTIFIED** (L2 refund engine + ceiling); device-confirmed cash-machine refund = ADAPTER PENDING (not faked) |
| Receipt | **SOFTWARE CERTIFIED** (authoritative breakdown incl device change) |
| Reconciliation | **SOFTWARE CERTIFIED** (provenance: manual / integrated / cash_machine / manual_force_done; recon flag) |
| Arabic | **SOFTWARE CERTIFIED** (native `_t`/`ar.po`; RTL bidi-safe numbers/refs) |
| Security (forged-success, credential non-exposure, route/authz coverage) | **SOFTWARE CERTIFIED** (arbitrary `paid=true` refused; no device credentials in bootstrap/DOM/logs; 100% route-gated) |
| Fresh install | **PASS** (`-i --without-demo=all`, 363 tests 0/0, browser cash-machine success/change) |
| Upgrade | **PASS** (`-u` on an S2C-6 DB, schema migrated, browser smoke of all tenders) |

## S2 readiness

- **Payment SOFTWARE completeness: 100%** — every software gate for L1–L7 + cross-cutting passes.
- **External / device certification (SEPARATE, not part of software completeness):**
  - Integrated terminals — real Stripe/Adyen/… standalone adapter PENDING; physical NOT certified.
  - Bank QR — Egypt/InstaPay NOT certified.
  - Paymob — sandbox/live NOT executed.
  - Customer credit — cross-branch Edge (disconnected DBs) NOT claimed.
  - Cash machines — physical Glory/Cashdro/Cashmatic NOT tested; Glory standalone adapter PENDING; Cashdro/Cashmatic not present in this Odoo.

Physical/provider certification remaining does NOT reduce software completeness. **Do not call physical certification 100%.**

## Not done (deliberately, per spec)
No V1 tag. Payment completion ≠ whole-product completion — Delivery closure, customer-experience closure, onboarding/productization, and physical/pilot work remain.
