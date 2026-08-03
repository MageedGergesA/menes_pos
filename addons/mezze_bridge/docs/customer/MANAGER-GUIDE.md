# Mezze POS — Manager Guide

For the shift/branch manager: watching performance, closing the money, and approving
the exceptions.

## By-channel analytics

- See performance broken down by channel (counter, dine-in, table-QR, pickup, kiosk,
  delivery, aggregator): orders, revenue, average order value, payment mix,
  cancellations, and top items.
- Use it to spot a slow channel, a spike in cancellations, or a payment mix that
  looks wrong.

## Reconciliation

- **Cash:** each cashier session records opening float, movements, and a counted
  close; Mezze reports expected vs counted with the variance.
- **Card / online:** integrated-terminal and online-payment tenders are matched to
  their Odoo payment records. The go-live validator surfaces online transactions
  that completed but did not link to a POS payment so you can chase them — nothing is
  auto-resolved behind your back.
- **COD:** delivery COD stays unpaid until the courier's collection is recorded, then
  reconciles as cash.

## Approvals

- Refunds, voids, comps, and discounts require a **manager PIN** and are audited with
  a signature (who approved, what, how much). Approve deliberately — the audit trail
  is the record.

## Credit approvals

- Charging to a customer's store account (pay-later) can require **manager approval**,
  depending on the method's credit policy.
- The company's credit-limit checking should be **on** so limits are enforced; if it
  is off, limits are not applied (the go-live check warns you).
- **Edge note:** cross-branch customer credit is **NOT real-time** — a customer's
  balance updated at one branch is not instantly visible at another until branches
  reconcile. Manage credit per branch or on Cloud for real-time cross-branch.

## Pulling a support bundle

If something needs Mezze support, pull a redacted support bundle
(`POST /mezze/api/v1/admin/support_bundle`) — it contains no secrets and no PII.
See `TROUBLESHOOTING.md` and `PRIVACY-DATA.md`.
