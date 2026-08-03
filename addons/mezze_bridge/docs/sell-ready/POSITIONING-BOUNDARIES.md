# Mezze POS — Positioning & Boundaries

Sales-safe positioning for Mezze. Use this to describe the product accurately and to
stay inside the lines on licensing and partner claims.

## What Mezze IS

- A **restaurant operating system** for MENA F&B, built on **Odoo 19.0 Community** (the
  `mezze_bridge` addon): counter, dine-in table service, kitchen display, first-party
  delivery, and customer self-ordering (QR menu, table-QR, pickup, kiosk).
- **Bilingual EN/AR, RTL-aware** across customer surfaces.
- Shipped in **two editions** from one codebase — **Mezze Cloud** (Mezze-managed
  hosting of the custom code) and **Mezze Edge** (branch-local, survives a WAN outage
  on the LAN).
- **Honest by design:** every capability carries one status word; go-live readiness is
  validated by software, not self-declared.

## What Mezze is NOT

- **Not standard Odoo Online / Odoo.sh.** Mezze Cloud is our own managed deployment;
  Odoo's SaaS does not allow arbitrary custom addons.
- **Not a payment processor or bank.** Every tender converges on Odoo's native
  payment/accounting layer; Mezze never stores PAN/CVV/PIN.
- **Not a courier/logistics platform.** Delivery is manual dispatch — no route
  optimisation, no live GPS (v1).
- **Not certified on Odoo 20.** Certified on Odoo 19.0 Community only.
- **Not an official Odoo partner offering.** Do **not** claim Odoo partnership or
  certification; Mezze is an independent addon built on Community.

## Licensing & dependency truth

- **License:** LGPL-3.
- **Depends on** these Odoo 19 Community modules: `point_of_sale`, `pos_restaurant`,
  `stock`, `account`, `bus`, `mrp`, `loyalty`, `payment_paymob`,
  `pos_online_payment`, `payment_demo`.
- Built on Community — no Enterprise dependency implied, and **no official Odoo partner
  claim**.

## Commercial feature matrix (sales-safe)

Status words: **SOFTWARE CERTIFIED** · **SUPPORTED VIA ODOO** · **EXTERNAL CERT
PENDING** · **PHYSICAL CERT PENDING** · **DEFERRED V2** · **NOT SUPPORTED**.

| Capability | Status |
|---|---|
| Counter / cash sale | SOFTWARE CERTIFIED |
| Dine-in table service, fire-by-course, transfer/merge | SOFTWARE CERTIFIED |
| Kitchen display (fire-once) | SOFTWARE CERTIFIED |
| Refund / void / comp / discount (manager-gated, audited) | SOFTWARE CERTIFIED |
| Stock deduction & accounting postings | SUPPORTED VIA ODOO |
| Split by amount / line + mixed tenders | SOFTWARE CERTIFIED |
| Split by **seat identity** | DEFERRED V2 |
| Cash payment | SOFTWARE CERTIFIED |
| Manual card (reference only) | SOFTWARE CERTIFIED |
| Integrated card terminal | SOFTWARE CERTIFIED (software) / PHYSICAL CERT PENDING |
| Bank-app QR (Egypt/InstaPay NOT certified) | SOFTWARE CERTIFIED / EXTERNAL CERT PENDING |
| Online payment (native path) | SOFTWARE CERTIFIED |
| Paymob online (redirect-only; no refund/token/capture) | EXTERNAL CERT PENDING |
| Customer account / store credit | SOFTWARE CERTIFIED |
| Automated cash machine (Glory) | SOFTWARE CERTIFIED (software) / PHYSICAL CERT PENDING |
| Stored PAN / CVV / PIN | NOT SUPPORTED |
| QR menu / table-QR / pickup / kiosk (pay-at-counter) | SOFTWARE CERTIFIED |
| Kiosk physical hardware | PHYSICAL CERT PENDING |
| Channel pause/resume + by-channel analytics | SOFTWARE CERTIFIED |
| Delivery zones / fees / COD / manual dispatch | SOFTWARE CERTIFIED |
| Aggregator channels (Talabat-style webhook) | SOFTWARE CERTIFIED (specific aggregator: EXTERNAL CERT PENDING) |
| Route optimisation / live GPS | NOT SUPPORTED |
| Go-live validator + commercial profiles | SOFTWARE CERTIFIED |
| Support bundle (redacted) / audit export | SOFTWARE CERTIFIED |
| Backup/restore (Edge) | SOFTWARE CERTIFIED |
| Arabic / RTL / a11y | SOFTWARE CERTIFIED |
| Odoo 20 | NOT claimed |

This mirrors `docs/sell-ready/product/PRODUCT-CAPABILITY-MATRIX.md` — that file is the
authoritative source; keep this in sync with it.
