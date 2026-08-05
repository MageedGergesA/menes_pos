# CAPABILITY MATRIX (forensic — from code; implementation ≠ certification)

Audit 2026-08-05, HEAD `5ec05b1`. Architecture = **managed custom-code Odoo deployment** (custom Python
controllers/models + `external_dependencies: cryptography` → **cannot** be Odoo Online SaaS; needs Odoo.sh /
self-hosted Cloud / on-prem Edge).

## Core POS + operations — all IMPLEMENTED
counter sale (`/orders/sync` main.py:953), dine-in/table service, floors (`/floors`), guest count, transfer
(`/tables/transfer`), merge (`/tables/merge`), courses (`/courses/board|hold|fire`), hold/fire
(`/orders/fire`, FSM-guarded), KDS (`/orders/kds`,`/kds/transition`), ready/served (BDS), partial payment,
mixed tender, refund (`/orders/refund` + integer ceiling `domain/refund.py`), session close. Reservations,
waitlist, QR self-order, shop off-premise, pickup, delivery (+ real COD), aggregator ingest (HMAC webhook),
drive-thru — all IMPLEMENTED. No whole capability is missing.

## Payments (implementation ≠ external/physical certification)
| Tender | Implemented | Cashier UI | Backend test | External/physical cert |
|---|---|---|---|---|
| Cash | Y (native cash mode) | Y | Y (mixed_tender, money_invariants) | n/a |
| Manual Card | Y (`manual` class) | Y (ManualTender) | Y (payment_platform/contract) | n/a |
| Wallet | PARTIAL — provider registry exists but driver is **TODO stub** (`mezze_payment.py:37`) | via ManualTender | indirect | none |
| Bank Transfer | Y (reference tender) | Y | Y | n/a |
| External Terminal (manual) | Y (`external_terminal`, ref-policy) | Y | Y (reconciliation/contract) | device `certification_status=not_tested`; "never implies hardware cert" |
| Integrated Terminal | SUPPORTED not CERTIFIED — orchestration only; **real providers refused ("integration PENDING — no fake success")** | Y | Y (**TEST simulator** only, gated) | **physical device cert PENDING** (golive.py) |
| Bank App QR | Y (manual, cashier-confirmed) | Y | Y (payment_qr) | **Egypt/InstaPay NOT certified** (golive.py:199) |
| Online Payment | Y — reuses native `pos_online_payment` | Y (customer checkout) | Y — **Demo provider exactly-once** | live PSP not run |
| Paymob | WIRED not EXECUTED — hard dep `payment_paymob`, delegated to native `payment.transaction` | via checkout | **none Paymob-specific** | **no sandbox/live run anywhere** |
| Customer Account (pay_later) | Y — native `partner.credit`/`account.payment`, "no second ledger" | Y | Y (customer_credit) | n/a |
| Customer Credit Governance | Y — odoo_warning / manager_approval / hard_block | Y | Y | n/a |
| Cash Machine | SUPPORTED not CERTIFIED — Glory-only orchestration; **real device refused ("adapter PENDING")** | Y | Y (**simulator** only) | **physical cert PENDING** |
| Mixed Tender | Y | Y | Y | n/a |
| Refund | Y (integer ceiling, manager-gated) | Y | Y (refund_ceiling, invariants) | n/a |
| Reconciliation | Y (manager-approval finalize) | report | Y | n/a |

**SUPPORTED vs READY vs CERTIFIED:** cash/manual/mixed/partial/refund/online(Demo)/customer-account are
implemented + server-tested. Integrated terminal / cash machine / bank-QR are **software-orchestration only**
(real hardware/bank confirmation refused in code — never faked). Paymob is a wired dependency with **no
executed sandbox/live transaction**. Wallet acquirer driver is a TODO stub.

## Security / integrity (implemented + tested unless noted)
One gate `_security_gate` default **enforce** (main.py:544). auth gate, branch/company scope, route-scope
classification (A–E), endpoint coverage (no ungated route, test_endpoint_coverage), HMAC signing
(off/observe/enforce; machine principals forced enforce), nonce/replay (durable single-use), idempotency
(per-tender key + FOR UPDATE), transactional outbox, payment duplicate protection, refund ceiling, secret +
support-bundle redaction (leakage=0), AES-256-GCM secret-at-rest (crypto), rate limiting, append-only audit.
All have tests. **Gap (honest, self-documented):** object-level scope is gate-WIRED only for the
`OBJECT_SCOPED` subset (pay/refund/comp/fire/print/drawer/session-close); other Category-A routes are
authn+capability gated but not yet object-scoped ("wiring pending", route_scope.py:149).

## Notable code-vs-doc conflicts
1. `mezze.payment.transaction` markets Paymob/Fawry/HyperPay/mada/Geidea but the driver is `(TODO)`; the
   live online path actually runs through the separate native `pos_online_payment` bridge. Two overlapping
   payment abstractions; the acquirer-registry one is unwired.
2. Two cashier front-ends: Owl app (shipped) + `pos.html` prototype (unreferenced by manifest bundle).
3. `route_scope.ROUTE_SCOPE` has duplicate keys (harmless; values agree) despite "classified once" claim.
