# POS settlement reconciliation (S2 Slice 2)

Operational settlement reconciliation (NOT accounting journal reconciliation). Models:
`mezze.payment.reconciliation` (per session/branch) + `.line` (per method/device).

- **Expected** amounts are DERIVED from finalized payments (`build_for_session`), grouped by method(+device),
  gross or `settlement_basis=net`. **Never hand-edited.**
- **Settlement input** (`record_settlement`): actual count/settlement amount + reference + source
  (cash_count / manual_terminal_settlement / bank_transfer_confirmation / provider_import / automated_provider)
  + operator. Never edits `pos.payment`.
- **Status** per line: MATCHED / OVER / SHORT / MISSING_SETTLEMENT / UNRECONCILED (currency precision).
- **Finalize** (`finalize`): idempotent + row-locked (concurrent finalize → one authoritative result);
  manager approval required when any line difference exceeds the method `reconciliation_tolerance`; audited.
- Cash uses expected-vs-counted; native Odoo cash control remains authoritative for cash accounting.
- A difference is STORED and acknowledged — never zeroed by editing payments.

Session-close: reconciliation status is exposed for the close flow; Odoo's session close is not reimplemented.
