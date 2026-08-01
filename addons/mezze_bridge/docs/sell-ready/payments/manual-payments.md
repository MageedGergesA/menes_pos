# Manual & external-terminal payments (S2 Slice 2)

Cashier flow for non-integrated tenders (cash, manual card, wallet, bank transfer, InstaPay, custom):
`select method → amount → device (if required) → reference/approval (if policy) → explicit confirm →
canonical pos.payment`. No second financial engine — reuses `add_payment` + the money invariants.

## Runtime policy (enforced BEFORE any financial effect, `pos.payment.method.mezze_validate_payment`)
- **device_policy** disabled/optional/required — REQUIRED with no compatible/active/same-branch device → error, no payment.
- **reference_policy** disabled/optional/required — REQUIRED with no `payment_ref_no` → error, no payment.
- **duplicate_policy** allow/warn/manager_approval/block over the configured `reference_scope`
  (device+ref / method+ref / branch+ref) — BLOCK errors; MANAGER_APPROVAL returns 409 `needs_manager`
  until an authorized override (`allow_duplicate`); WARN surfaces duplicates to the UI.
- Provenance: `mezze_confirmation_source = manual` (never "provider confirmed"). Approval code reuses the
  native `payment_method_authcode`; reference reuses native `payment_ref_no`; last-4 reuses native `card_no`.
  **No PAN/CVV/PIN/track fields.**

Wired into `POST /mezze/api/v1/orders/pay` (`device_id`, `payment_ref`, `approval_code`, `allow_duplicate`).
Software-tested; physical terminal + browser UX acceptance = later.
