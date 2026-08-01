# Payment security & card-data policy (S2 Slice 2)

- **Card data:** Mezze stores NO PAN / CVV / PIN / track / EMV data. Only native optional fields are reused
  (`card_no` = last-4, `payment_ref_no`, `payment_method_authcode`) — never required, never a card vault.
- **Runtime enforcement before financial effect** — device/reference/duplicate policy raise before any
  pos.payment is created (no partial side effect).
- **Branch crossover prevented** — a device from another branch is rejected (`mezze_branch_id` context check).
- **Authorization** — reconciliation/finalize/difference-approval/external-refund-confirm/duplicate-override
  are manager-gated (a plain cashier cannot self-approve); each is audited (actor + timestamp) via the
  existing audit log.
- Endpoints remain behind the canonical `_authorize` security gate.
