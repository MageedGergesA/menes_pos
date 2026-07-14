# Review scope — mezze_bridge (full product: W1 + W2 + 2C)

Adversarial review target: the whole `mezze_bridge` addon (baseline = the empty
`Initial commit`; ~9.7k lines). Covers W1 (money-legal), W2 (chain-trust), and
2C (reporting / GL bridge / aggregators). This note ranks where to spend
attention and lists intentional scaffolds so they aren't re-flagged. Prioritize
**correctness of money movement, auth, and concurrency** over style. The
money-path writes to scrutinize hardest: `main.py` (order_sync/pay/refund/fire,
loyalty), `w1.py` (payment/einvoice/approve), and `aggregator.py` (webhooks).

## Context in one paragraph
`mezze_bridge` is a custom JSON API (`type='json2'`, `auth='none'`, shared-token)
over Odoo 19 POS, driving two same-origin front-ends (`static/pos.html`,
`static/qr.html`). This session added: an immutable audit trail + cashier PIN
auth, native Paymob delegation (`payment_paymob`), native ETA delegation
(`l10n_eg_edi_eta`), token rotation, and the payment/receipt UX. Sync + payment
external legs are deliberate scaffolds.

## CRITICAL — verify hard

1. **Card completion ordering** — `static/pos.html` `#pay-complete` + `cardCharge()`.
   ADDRESSED: the flow now authorizes/captures a live card tender FIRST
   (`cardCharge()` → `payment/intent` → poll `payment/status` until `done`) and
   only finalizes the order (`bridgeSyncOrder`/`bridgePay`) if capture succeeds;
   otherwise it aborts and leaves the pay modal open. The captured-but-
   finalize-fails gap is CLOSED: if the order can't be recorded after capture (or
   a charge we couldn't confirm may have settled), `#pay-complete` calls
   `/payment/void`, which writes a CRITICAL `payment.reversal` audit row and
   either auto-refunds (when `provider.support_refund != 'none'`) or flags for
   manual reversal (Paymob today has no auto-refund via Odoo). STILL VERIFY: the
   90s poll timeout + `done/authorized` success mapping vs Paymob's real webhook
   states; partial/mixed cash+card recording (Odoo still records one payment
   method for the full total); and that `flagged_manual` alerts reach staff
   (currently a toast + audit row) reliably enough to guarantee the manual
   reversal actually happens.

2. **API auth surface** — `controllers/main.py::_authenticate`, `sync.py::_auth`,
   `w1.py::_auth`; all endpoints are `auth='none' cors='*' csrf=False`.
   - `sync.py::_env` / `w1.py::_env` now bind to the configured API user (W2 2A#2
     — no longer SUPERUSER); verify that user has (only) the rights it needs.
     Token is strong + `/mezze/pos` launcher is `auth='user'` (W1) — token no
     longer in source or served to anonymous.
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

## W2 additions — review these too

W2-1. **Approval gate — FIXED** — `order_refund` no longer trusts a client id.
   `/w1/approve` (PIN-verified) mints an HMAC-signed, short-lived (120s),
   action-bound token (`controllers/approval.py`); `order_refund` verifies it and
   records the token-derived approver. Verified: no token / forged token → 403,
   valid token → refund. STILL VERIFY: the secret source (`database.secret`), TTL
   suitability, and single-use (a token can currently be replayed within its 120s
   window — consider a nonce/jti if replay matters).
W2-2. **`order_exchange`** (`main.py`) — internal `self.order_refund()` +
   `self.order_sync()`. Check: partial failure (refund ok, sale fails → orphan
   refund, no compensation); idempotency of the `-ret`/`-new` uuids on retry;
   net-cash = new_incl − return_incl.
W2-3. **Refund tax fix** (`main.py::order_refund`) — now applies the PRODUCT's
   taxes via the fiscal position and refunds tax-inclusive. Verify: it uses
   current product taxes, not the ORIGINAL line's taxes (a rate change since the
   sale would refund at the new rate); negative-qty `compute_all` signs; and it
   matches what was actually charged.
W2-4. **Split multi-payment** (`main.py::order_sync`) — builds one `pos.payment`
   per tender, last absorbs rounding. Verify the sum equals `total_incl` exactly
   and zero-amount tenders are filtered.
W2-5. **Reversal resolve** (`w1.py::reversals_resolve`) — any pos_user can mark a
   reversal resolved; consider requiring manager role.

## 2C additions — reporting, GL bridge, aggregators

2C-1. **Reporting** (`w1.py::reports_summary` / `reports_refunds_csv`) — READ-ONLY.
   Refund-by-reason + cashier leaderboard come from `mezze.audit.log`; sales from
   `pos.order`. No money movement. Check: range defaulting, that the CSV escapes
   fields, and that reason/cashier totals can't be forged (they read the immutable
   audit trail, not client input). Frontend = Reports view in `pos.html`.

2C-2. **GL bridge** (`w1.py::gl_sessions` / `gl_summary` / `gl_export.csv`,
   `_gl_moves`) — READ-ONLY reconciliation over NATIVE journal entries; it never
   creates/posts an `account.move`. `_gl_moves` = session close moves ∪
   invoiced-order moves (Odoo keeps them disjoint → no double-count). Verify: the
   union really is disjoint on your data; the range basis (sessions by `start_at`,
   documented in `docs/GL.md`); and that `gl_summary`'s trial balance matches the
   session move's own balance. Frontend = Books · GL sub-tab.

2C-3. **Aggregator webhooks** (`controllers/aggregator.py`, `models/aggregator.py`)
   — the ONLY new money-path write; scrutinize like W1/W2:
   - **Signature** — HMAC-SHA256 over the RAW body (`type='http'`),
     `hmac.compare_digest`. Confirm the raw bytes are what's signed (not a
     re-serialised dict), and secret-unset → 503 (never open).
   - **Idempotency** — unique `(aggregator, external_id)` + the `_find` early
     return. Two concurrent identical webhooks: does the unique constraint (not
     just the check) prevent a double order? (No advisory lock here, unlike fire.)
   - **Fail-loud** — an unmapped SKU rejects the WHOLE order (422); confirm no
     partial paid order is ever created when some items map and some don't.
   - **Order creation** — mirrors `delivery_create` (paid order on the prepaid
     tender via `sync_from_ui`, `_build_lines` server-side tax). Verify the total
     the customer paid the aggregator (`gross`) vs the Odoo order total can
     diverge (aggregator markup) — is booking Odoo's computed `incl` (not gross)
     correct, and is the commission/payout purely informational?
   - **Cancel** — flags cancelled + delivery failed but does NOT void the paid,
     possibly-cooking order (documented staff decision). Confirm that's intended
     and money isn't silently stranded.
   Frontend = Delivery → Delivery apps sub-tab (read-only oversight).

## Intentional scaffolds — do NOT flag as bugs
- `controllers/sync.py` push/pull **apply/reconcile is TODO** (transport +
  idempotency are live). See `docs/SYNC.md`.
- `aggregator.py` per-aggregator payload/signature **adapters** + the
  **status-push-OUT** leg (`_notify`) are scaffolds pending real Talabat/Jahez
  partner API creds — the webhook accepts a NORMALISED contract. See
  `docs/AGGREGATORS.md`.
- `w1.py` einvoice/payment external legs require real creds/EG setup by design;
  they return honest `not-cleared` / `no_provider` until configured.
- (`_env()` SUPERUSER was fixed in W2 2A#2 — now the API user.)
- `mezze.payment.provider` model is partly superseded by native
  `payment.provider`; kept as a POS-side tender-gating/link record.
- Hardcoded tax display (12/14) + some ghost labels (`Table 12`) are known W3
  items; `w1.py::config_tax` is the migration seam.

## Suggested reviewer lenses
correctness (money in/out) · auth/privilege-escalation · idempotency/double-spend
· concurrency/txn-poisoning · silent-failure (audit, best-effort catches) ·
optional-dependency safety (ETA/Paymob absent).
