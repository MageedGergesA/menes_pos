# Pilot Runbooks (P1 §23)

Each runbook: **Symptom · Immediate action · Safe workaround · Prohibited · Verify · Escalate**.

## Card charged but POS response lost
- **Symptom:** payment terminal shows success; POS didn't confirm.
- **Immediate:** re-submit the SAME payment (same order uuid) — the engine is idempotent by order uuid; it returns the existing payment, never a second one.
- **Safe workaround:** verify in the order's payment lines that exactly one payment exists.
- **Prohibited:** manually re-tender a second payment; editing payment lines in the back office.
- **Verify:** order `amount_paid == amount_total`; one payment line; session cash/card unchanged by the retry.
- **Escalate:** if two payment lines appear → engineering (should be impossible; capture order uuid + correlation id).

## Payment terminal unavailable
- **Immediate:** switch tender to cash for that order; note the reason.
- **Prohibited:** marking an order paid without a real tender.
- **Verify:** session cash expected reflects the cash tender.
- **Escalate:** terminal down >30 min → branch admin.

## Refund
- **Immediate:** use the in-app refund (existing refund engine) against the original order; enter reason.
- **Prohibited:** deleting/editing the original order; refunding more than sold (blocked by a model constraint).
- **Verify:** refund line links to the source; cumulative refunded qty ≤ sold.

## Printer / KDS unavailable
- **Immediate:** POS keeps ringing; kitchen tickets queue in the outbox and dispatch on reconnect; use the on-screen bill/KDS as fallback.
- **Prohibited:** closing the session while required outbox events are permanently dead-lettered without acknowledgement.
- **Verify:** on reconnect, queued jobs deliver once (idempotent). Check the outbox view for dead letters.

## Stuck outbox event / failed webhook
- **Immediate:** open the outbox view; inspect event type, business id, attempt count, last error, next retry, correlation id.
- **Safe action:** trigger a **replay** — replay never duplicates the business effect (idempotent consumers).
- **Prohibited:** deleting an event to "clear" it.
- **Escalate:** a poison event that fails after max attempts → engineering with the correlation id.

## Aggregator outage / signature failures
- **Immediate:** signature failures are refused (401) and rate-limited; a burst of failures → verify the shared secret rotation.
- **Verify:** valid callbacks are idempotent (duplicate → one order).

## QR ordering pause
- **Immediate:** disable the channel in the branch config (temporary suspension); QR shows "ordering temporarily paused".
- **Prohibited:** deleting the QR signing key.

## Product 86
- **Immediate:** 86 the item on the KDS/manager view; it propagates to all customer channels; checkout rejects it (`_assert_available`).

## Table / order conflict
- **Immediate:** the newer state wins; a concurrent illegal transition returns 409, no silent overwrite. Reassign via transfer (not merge) if two parties collided.
- **Prohibited:** merging two orders that have payments (blocked, `merge_blocked_payments`).

## Internet outage
- **Immediate:** offline POS keeps ringing sales; they queue and sync to Odoo on reconnect (idempotent by uuid). Card/aggregator/QR require connectivity.

## Restore from backup / Rollback release
- See `../backup-restore/backup-restore.txt` and `../rollback/rollback.md`.

## Escalate to engineering
Trigger: duplicate payment, lost accepted order, duplicate KDS item, permanent outbox stall, or any unexplained financial difference. Provide: order uuid, correlation id, branch, timestamp, worker, and the outbox/audit rows.
