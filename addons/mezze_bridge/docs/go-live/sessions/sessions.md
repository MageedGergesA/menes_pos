# POS Session Opening / Closing (P1 §8)
Session lifecycle is **native Odoo POS** (`pos.session` open → orders → closing control → close),
reused unchanged per project policy (do not rebuild working core).
- **Open:** opening cash control on the native flow.
- **During:** every genuine payment writes a `pos_payment` row (reconciliation proof: 294 genuine orders, 0 diff).
- **Close:** closing control reconciles expected vs counted; a session with orders whose payments are
  unresolved cannot be silently closed — the native closing control surfaces the difference.
- **Mezze guardrails:** mutating session/order routes declare `readonly=False` (else the write aborts on
  Odoo 19's read-only-by-default routing) — this was a confirmed defect fixed and regression-tested.
**Classification:** Pilot supported. Full open→service→Z-close on the pilot host with real cash is an on-site step; the code path and reconciliation are proven.
