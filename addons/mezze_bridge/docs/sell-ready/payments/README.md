# Mezze Universal Payments Platform

One platform, one set of money invariants. Mezze does NOT reimplement bank protocols or run seven
payment engines — every tender converges on Odoo's `pos.payment` / `pos.order` and Mezze's existing
money/refund/idempotency/concurrency invariants. Levels:

- **L1 Cash / manual tender** — native `pos.payment.method` (cash) + Mezze mode/policy metadata.
- **L2 External terminal (manually confirmed)** — Mezze reference/approval policy + device registry;
  reuses native `payment_ref_no` / `payment_method_authcode` / `card_no` (last-4). No PAN/CVV/PIN/track.
- **L3 Odoo integrated terminals** — reuse native `use_payment_terminal` (Stripe/Adyen/…): SUPPORTED VIA ODOO.
- **L4 Bank / payment QR** — reuse native `qr_code_method`; kept strictly separate from Table-QR ordering.
- **L5 Online providers** — reuse `payment.provider` / `payment.transaction`; Paymob native (installed).
- **L6 Customer account / credit** — reuse native `type=pay_later` + receivable.
- **L7 Cash machines** — SUPPORTED VIA ODOO (Cashdro/Cashmatic/Glory); physical device NOT TESTED.

See `payment-capability-audit.md` for the grounded classification and `CERTIFICATION-MATRIX.md` for the
strict supported-vs-certified split.

## Status (staged build)
- **Slice 1 (this increment) — DONE:** payment-method Mezze modes + policy metadata, `mezze.payment.device`
  registry, external-reference policy (required/optional/disabled) enforced on the native field, and
  duplicate-reference detection (configurable scope). 13 tests green; full suite green; Edge self-tests 25/25.
- **Remaining slices (NOT yet built):** L3 terminal state-normalization + force-done policy wrapper; L4
  static/dynamic QR classification surface; L5 online idempotency join + demo-provider tests + server-
  authoritative recompute; L6 credit-limit policy; reconciliation model; cashier/device/customer UX +
  receipt breakdown; payment validator checks + payment health; remaining L1–L7 + refund + reconciliation
  + multi-worker tests; per-level docs.

S2 is therefore **NOT product-complete yet** — this is the foundational slice. Nothing about specific
terminals/providers is claimed "certified"; Paymob external Test is NOT EXECUTED.
