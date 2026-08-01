# Refunds — manual/external provenance (S2 Slice 2)

Every refund routes through the existing Mezze refund ceiling/linkage/idempotency/concurrency engine —
unchanged. For manual/external electronic methods, Mezze records the refund operationally but does NOT
claim the bank/terminal refunded without integration:
- `mezze_external_refund_status`: not_required / pending_external / confirmed_external / failed_external.
- `mezze_confirm_external_refund(reference, …)`: manager action, idempotent, audited, never edits the
  original payment amount. Cash = not_required.
Provider (payment.transaction) refunds use the native mechanism where supported (later slice).
