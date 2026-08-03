# Mezze POS — Privacy & Data

What Mezze stores, what it deliberately does not, and how support access is kept
clean. Written for owners and their data-protection reviewers.

## What Mezze does NOT store

- **No card data — ever.** Mezze never stores the full card number (PAN), CVV, or PIN.
  For manual card tenders it keeps only a **reference/approval code and the last 4
  digits**. Integrated terminals and online providers handle the card on their side;
  Mezze reads only the result.

## Where customer data lives

- **Customer PII** (name, phone, delivery address, reservation details) is stored on
  the **Odoo partner** record — the standard, access-controlled customer model. It is
  used to fulfil orders (delivery, pickup status, account/credit) and nothing beyond
  that.
- **Orders and accounting** are native Odoo records with normal access control and
  audit.

## Support bundles are safe to share

- A support bundle (`POST /mezze/api/v1/admin/support_bundle`) is **secret-redacted
  and PII-redacted before it leaves the site** — the redaction is done in the model,
  not the network layer, and leakage has been tested to **zero**.
- It contains configuration/diagnostic metadata to help Mezze support — **no card
  data, no customer PII, no secrets** (keys, tokens, passwords are never included).

## Audit log

- Sensitive actions (refunds, voids, comps, discounts, credit approvals, config
  changes, break-glass access) write an immutable audit line: who, what, when,
  terminal, amount, and a **redacted** detail.
- The audit **export** (`/admin/audit/export`) returns audit **metadata only** — never
  order contents or customer PII — and detail fields are redaction-filtered.
- **Retention:** audit lines are retained as immutable business records for compliance
  and reconciliation; set and document your retention period per local law (e.g.
  Egypt/KSA tax record-keeping) with your implementation partner.

## Access control

- Human admin access is role-scoped (org_admin / store_manager / role_manager /
  auditor); auditors are read-only. See `ADMIN-GUIDE.md`.
- Public customer status links use short-lived, revocable tokens (a default TTL,
  typically 24h) — they expose only that customer's own order status, never internals.

## Your responsibilities

- Keep secrets out of git and in the environment (see `SECURITY-BASELINE.md`).
- Serve over HTTPS.
- Define and honour a data-retention and consent policy appropriate to your
  jurisdiction; Mezze provides the controls, you set the policy.
