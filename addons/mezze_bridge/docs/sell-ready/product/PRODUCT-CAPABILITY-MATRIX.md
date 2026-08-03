# Mezze POS — Product Capability Matrix (S5)

The single authoritative inventory of what Mezze is and is not. Every capability
carries **exactly one** status — no vague "supported" without qualification.

## Status legend

| Status | Meaning |
|---|---|
| **SOFTWARE CERTIFIED** | Code path exists, CI-tested, browser-accepted with DB proof. Ships and works on the software alone. |
| **SUPPORTED VIA ODOO** | Delivered by reusing native Odoo (accounting, inventory, taxes, journals). Certified as configuration, not custom Mezze code. |
| **EXTERNAL CERT PENDING** | Software path built + tested against a simulator/sandbox; live certification needs a third-party credential/account we do not yet hold. |
| **PHYSICAL CERT PENDING** | Software orchestration certified; physical device certification pending (no hardware on hand). |
| **DEFERRED V2** | Intentionally out of v1 scope. Named, not hidden. |
| **NOT SUPPORTED** | Explicitly not a Mezze capability. Stated so sales cannot imply it. |

### Validator ↔ customer vocabulary mapping

The Go-Live validator (`/admin/golive`) emits the raw token **`NOT TESTED`** for any
fact it cannot confirm from inside software (physical device, host/OS, live external
provider). In these customer-facing matrices that same fact is labelled
**PHYSICAL CERT PENDING** (hardware) or **EXTERNAL CERT PENDING** (third-party
credential). They mean the same thing — "not proven yet" — and `NOT TESTED` is
**never** rendered as PASS/CERTIFIED anywhere.

---

## 1. Point of sale & order taking

| Capability | Status | Evidence / note |
|---|---|---|
| Counter/cash sale, canonical `pos.order` | SOFTWARE CERTIFIED | reuses native POS order + payment |
| Dine-in table service (open/append/bill/pay) | SOFTWARE CERTIFIED | `_do_fire` advisory lock + `fire_uuid` idempotency |
| Two-phone concurrency / double-submit safety | SOFTWARE CERTIFIED | pg advisory lock on `table_id` |
| Server-authoritative pricing/tax/combos | SOFTWARE CERTIFIED | `_build_lines`, `_sanitize_customer_lines` (§63) |
| Modifiers (single-select enforced server-side) | SOFTWARE CERTIFIED | `_validate_modifiers`; explicit min/max beyond single-select = DEFERRED V2 |
| Kitchen display (KDS), fire-once | SOFTWARE CERTIFIED | `_mezze_fire_online_kds` (FOR UPDATE + `mezze_kds_fired`) |
| Reversals / refunds / comps / void / discount | SOFTWARE CERTIFIED | audited, capability-gated, signature-required |
| Stock deduction, accounting postings | SUPPORTED VIA ODOO | native `point_of_sale` + `stock` + `account` |
| True split-by-seat identity | DEFERRED V2 | split-by-amount/line supported; per-seat identity not modelled |

## 2. Payments

| Capability | Status | Evidence / note |
|---|---|---|
| Cash | SOFTWARE CERTIFIED | S2C L1 |
| Manual/external card (record-only) | SOFTWARE CERTIFIED | S2C L2 |
| Integrated card terminal orchestration | SOFTWARE CERTIFIED (software) / PHYSICAL CERT PENDING | S2C-3; real device certification pending |
| Bank-app payment QR | SOFTWARE CERTIFIED / EXTERNAL CERT PENDING | S2C-4; **Egypt/InstaPay QR NOT CERTIFIED** |
| Online customer payment (QR-table / pickup / delivery) | SOFTWARE CERTIFIED | S2C-5, native `pos_online_payment` + `payment.transaction` |
| Paymob online provider | EXTERNAL CERT PENDING | redirect-only; refund/token/capture NOT claimed; sandbox+live NOT certified |
| Customer account / store credit | SOFTWARE CERTIFIED | S2C-6, native `pay_later` receivable |
| Automated cash machine (Glory etc.) | SOFTWARE CERTIFIED (software) / PHYSICAL CERT PENDING | S2C-7; no hardware |
| Stored PAN / CVV / PIN | NOT SUPPORTED | Mezze never stores card data — see privacy doc |

## 3. Customer ordering & self-service

| Capability | Status | Evidence / note |
|---|---|---|
| QR menu (browse real catalog) | SOFTWARE CERTIFIED | `/qr/menu`, `/shop/menu` |
| Table-QR ordering | SOFTWARE CERTIFIED | S4; add-to-existing-table |
| Pickup self-order | SOFTWARE CERTIFIED | S4 |
| Kiosk (pay-at-counter) | SOFTWARE CERTIFIED | S4; native card-terminal kiosk NOT claimed (Adyen/Stripe-only upstream) |
| Kiosk physical hardware | PHYSICAL CERT PENDING | no kiosk device |
| Channel pause/resume + by-channel analytics | SOFTWARE CERTIFIED | `/selforder/*` |
| Arabic / RTL / dark / a11y | SOFTWARE CERTIFIED | bilingual customer surfaces |

## 4. Delivery

| Capability | Status | Evidence / note |
|---|---|---|
| Delivery zones / fees / minimums / ETA | SOFTWARE CERTIFIED | S3 |
| COD (real unpaid → collect) | SOFTWARE CERTIFIED | `/delivery/collect` |
| Manual dispatch + courier assignment | SOFTWARE CERTIFIED | S3 |
| Aggregator channels (Talabat-style webhook) | SOFTWARE CERTIFIED | normalized webhook + outbox delivery |
| Route optimization / live GPS tracking | NOT SUPPORTED | not included in v1 |

## 5. Productization & operations (S5)

| Capability | Status | Evidence / note |
|---|---|---|
| Go-Live readiness validator + commercial profiles | SOFTWARE CERTIFIED | `mezze.golive.validator`, 6 profiles |
| Release identity (version/commit/mode/edition) | SOFTWARE CERTIFIED | `/admin/version` |
| One-click support bundle (secret-redacted) | SOFTWARE CERTIFIED | `/admin/support_bundle`, leakage=0 tested |
| Full-trail audit export | SOFTWARE CERTIFIED | `/admin/audit/export` |
| First-run onboarding (resumable/idempotent) | SOFTWARE CERTIFIED | `mezze.onboarding`, completion derived from validator |
| Staging neutralization | SOFTWARE CERTIFIED | `data/neutralize.sql` + `is_neutralized()` honored |
| Optional demo restaurant (explicit-only) | SOFTWARE CERTIFIED | `demo/` never auto-loaded; validator FAILS demo-in-production |
| Backup / restore (Edge) | SOFTWARE CERTIFIED | `deploy/edge/{backup,restore}.sh`; RTO≈14s recorded |
| Edge installer (Ubuntu 24.04) | SOFTWARE CERTIFIED / clean-host cert on 2 hosts PENDING | `deploy/edge/install.sh` |

## 6. Hardware

See the consolidated `docs/customer/HARDWARE-COMPATIBILITY.md`. All physical
devices (receipt printer, cash drawer, terminal, cash machine, kiosk) are
**PHYSICAL CERT PENDING** until the S6 on-site pilot.
