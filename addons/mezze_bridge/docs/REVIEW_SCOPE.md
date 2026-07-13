# Review scope — mezze_bridge (W1 money-path + security)

Adversarial review target: the branch since `7802de9` (initial import). ~8k lines
added. This note ranks where to spend attention and lists intentional scaffolds
so they aren't re-flagged. Prioritize **correctness of money movement, auth, and
concurrency** over style.

## Context in one paragraph
`mezze_bridge` is a custom JSON API (`type='json2'`, `auth='none'`, shared-token)
over Odoo 19 POS, driving two same-origin front-ends (`static/pos.html`,
`static/qr.html`). This session added: an immutable audit trail + cashier PIN
auth, native Paymob delegation (`payment_paymob`), native ETA delegation
(`l10n_eg_edi_eta`), token rotation, and the payment/receipt UX. Sync + payment
external legs are deliberate scaffolds.

## CRITICAL — verify hard

1. **Card completion ordering** — `static/pos.html` `#pay-complete` handler.
   The order is synced/paid for the FULL total (incl. any card tender) via
   `bridgeSyncOrder()` / `bridgeFire()+bridgePay()` **before** `payment/intent`
   opens the Paymob checkout. So the POS marks the sale paid before the card is
   actually authorized/captured. Confirm the intended flow — this looks like
   money can be recorded as collected before it clears. (Card tenders are
   currently gated off unless a provider is enabled, which masks it in the demo.)

2. **API auth surface** — `controllers/main.py::_authenticate`, `sync.py::_auth`,
   `w1.py::_auth`; all endpoints are `auth='none' cors='*' csrf=False`.
   - `sync.py::_env` and `w1.py::_env` run as **SUPERUSER** (documented scaffold)
     — bypasses record rules on payment/einvoice/terminal writes. Must be swapped
     to `_api_env()` (a real POS user) before prod; verify no privilege issue in
     the meantime.
   - Token now strong + launcher `auth='user'`, but the token still travels in
     the `pos.html` URL/query. Assess residual exposure (history, referrer).
   - `cors='*'` on money endpoints: any origin with the token can call them.

3. **Concurrency / fire** — `main.py::_do_fire`, `_reraise_if_retryable`,
   `pg_advisory_xact_lock`. Confirm `SerializationFailure/LockNotAvailable/
   DeadlockDetected` propagate (so `service_model.retrying` re-runs) and are never
   swallowed by the broad `except` (which would poison the txn with
   `InFailedSqlTransaction`). Check the append-semantics + `fire_uuid` idempotency
   under two waiters hitting one table.

4. **Loyalty redeem money integrity** — `main.py::loyalty_redeem` +
   `order_sync` discount path. Points are deducted server-side at redeem time; if
   the order is then abandoned, are points refunded? Verify the earlier
   `line_disc` clobber fix (loop var vs `discount` param) is correct, and that the
   redeemed discount line + tax recompute matches what the customer is charged.

## HIGH

5. **Audit trail reliability** — `models/mezze_audit_log.py::log` swallows ALL
   exceptions (best-effort, to never break a sale). Weigh silent audit loss;
   confirm append-only ACL (write/unlink=0 incl. managers) truly holds and
   `_actor` (`main.py`) can't drop a row on a bad FK.

6. **ETA invoicing path** — `w1.py::einvoice_submit`. `action_pos_order_invoice()`
   on a paid order: journal/partner requirements, error handling, and the
   accounting side-effects of invoicing every order. Confirm the runtime
   `l10n_eg_uuid in _fields` probe is the right optional-dependency guard. Note
   the e-invoice (B2B) vs e-receipt (B2C) gap is a known business decision, not a
   bug — see `docs/ETA.md`.

7. **Payment.transaction creation** — `w1.py::payment_intent`. Reference
   uniqueness (`_compute_reference`), `partner_id` fallback to
   `env.company.partner_id` (sane?), `operation='online_redirect'`, currency.
   Ensure a failed render leaves the tx/`mezze.payment.transaction` in a coherent
   state (it currently returns ok w/ `rendered:false`).

8. **Refund idempotency** — `main.py::order_refund`. Double-refund hazard if
   called twice; confirm the uuid guard prevents it and net stays correct.

9. **Central kitchen stock** — `main.py::ck_produce/ck_dispatch/ck_receive`.
   Real MRP + `stock.quant` moves; check for negative-quant / oversell handling
   and that dispatch is HQ-authoritative.

## MEDIUM

10. **Frontend token/auth** — `pos.html` `w1Call`/`bridgeCall` send the token in
    the body; `finishPin` fallback logs in offline on network error (intended) —
    confirm it can't be abused to bypass a real rejection.
11. **Tender gating** — `pos.html::renderTenders` + `w1.py::payment_methods`:
    a provider in `test` state marks card 'live' — intended for staging, but make
    sure `test` state can't take real money.
12. **Receipt honesty** — `pos.html::etaReceiptInfo`/`openReceipt`: confirm no
    path prints a "cleared" badge or verify-QR unless `l10n_eg_uuid` exists.

## Intentional scaffolds — do NOT flag as bugs
- `controllers/sync.py` push/pull **apply/reconcile is TODO** (transport +
  idempotency are live). See `docs/SYNC.md`.
- `w1.py` einvoice/payment external legs require real creds/EG setup by design;
  they return honest `not-cleared` / `no_provider` until configured.
- `_env()` SUPERUSER in sync.py/w1.py is a flagged scaffold (see CRITICAL #2).
- `mezze.payment.provider` model is partly superseded by native
  `payment.provider`; kept as a POS-side tender-gating/link record.
- Hardcoded tax display (12/14) + some ghost labels (`Table 12`) are known W3
  items; `w1.py::config_tax` is the migration seam.

## Suggested reviewer lenses
correctness (money in/out) · auth/privilege-escalation · idempotency/double-spend
· concurrency/txn-poisoning · silent-failure (audit, best-effort catches) ·
optional-dependency safety (ETA/Paymob absent).
