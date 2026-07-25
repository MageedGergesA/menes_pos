# Mezze POS — P1 Pilot & Go-Live Readiness — FINAL REPORT

Release candidate: **mezze_bridge 19.0.1.8.0** · commit `ce8dc745eaf6125d3f3e78b9ad7541a6cab10043`
Environment: Odoo 19.0 · PostgreSQL 14.23 · Python 3.10.12 · Linux (Ubuntu 22.04)
Evidence root: `addons/mezze_bridge/docs/go-live/` (this directory)

> Scope discipline: this increment built **no new platform layer** and **redesigned no completed
> workflow**. The only new code is a read-only configuration validator (`mezze.golive.validator`) and
> a narrowly-scoped pilot security hardening of the public status token (hash storage + expiry +
> revocation). Everything else is verification and honest classification of the existing system.

---

## 1. Executive verdict
- **Controlled pilot: GO** — conditional on two on-site verifications (real hardware, real tablet) that cannot be performed in a hardware-less CI host.
- **Unrestricted public launch: NO-GO** — online card payment is unproven/disabled, and hardware/tablet/staff-UAT/service-day acceptance are on-site steps by nature.
- 0 Critical defects, 0 unresolved financial-Major defects, 0 unexplained reconciliation difference.

## 2. Release candidate identity
mezze_bridge **19.0.1.8.0**, commit `ce8dc74`. Modules enabled: point_of_sale, pos_restaurant, stock,
account, bus, mrp, loyalty, payment_paymob + mezze_bridge. Asset & design-token checksums recorded in
`release-manifest.md`. Suggested tag `pilot-rc1` — created by the release owner (agents do not git-write).

## 3. Pilot scope (what the pilot IS)
A single restaurant branch, trusted staff, supervised. Supported: counter sales, dine-in tables,
reservations/walk-ins, waitlist, course hold/fire, KDS, partial/mixed payment, refunds, table transfer,
**safe** merge (blocks orders with payments), QR ordering, pickup (pay-at-counter), pay-on-delivery,
**prepaid** aggregator orders, secure customer order status, manager approvals, branch reports,
offline/reconnect, per-user/device customization, Admin Console governance. Full list: `scope-and-limitations.md`.

## 4. Disabled / deferred for the pilot
**Disabled (must stay OFF):** online **card** payment, **drive-thru**, advanced dispatch, true
**seat-level** line identity, **split-by-seat**, any untested payment provider, any unverified
aggregator, any public cancellation path that violates state policy. These are **not marketed** to
staff or customers. Deferred product capabilities are the post-pilot backlog. See `scope-and-limitations.md`.

## 5. Clean installation
Fresh-install procedure + post-install assertions documented (`installation/installation.md`): module
installed, 101 setting-defs seeded, validator 0-FAIL. The install/upgrade path executes cleanly on every
`-i`/`-u` in CI. A from-empty-DB install on the pilot host is a release-owner step (this build reused the
existing dev DB). **Classification:** procedure documented + exercised; no install-time errors.

## 6. Migration
Scripts `19.0.1.1.0 … 19.0.1.6.0` are idempotent (re-seed/upsert). 1.7.0/1.8.0 add no migration script;
new columns (`mezze_channel`, hashed `mezze_status_token`, `mezze_status_expiry`, `mezze_status_revoked`)
are ORM auto-schema on `-u`, applied cleanly with the suite green post-upgrade. Downgrade = restore a
pre-upgrade `pg_dump` (additive columns, no destructive DDL). Evidence: `migration/migration.md`.

## 7. Production configuration
`mezze.golive.validator.run()` — a read-only validator — returns **0 FAIL**, 4 dev-only WARNINGs
(dev env_profile, dev shared-admin fallback, localhost base_url, api_security=observe). All become PASS
under the production profile checklist. Evidence: `configuration/validator-report.txt`.

## 8. Security gate
0 launch-blocker. Master key from env (never in DB/source); aggregator/webhook secrets AES-GCM encrypted
at rest; shared-admin machine token production-disabled behind scoped emergency break-glass; per-endpoint
rate limits; API replay/nonce protection; audit-append is best-effort + savepoint-isolated so it can never
poison a read-only endpoint's transaction. Evidence: `security/security-gate.md`.

## 9. Status-token lifecycle (P1 hardening)
Public customer status tokens: 128-bit entropy (`os.urandom(16).hex()`), **SHA-256 hash stored** (raw
returned once, never persisted), **24h expiry** (`status_token_ttl_hours`), **manual revocation**.
Resolver rejects len<24, hash-mismatch, revoked, or expired. Regression-tested (hash≠raw, expiry set,
idempotent issue, revoke→unresolvable). Evidence: `tests/test_runtime_o1.py`, `tests/test_runtime_p1.py`.

## 10. Financial reconciliation
Live DB assertions: over-paid orders = **0**, orphan payments = **0**, and **0** amount_paid-vs-payment-line
difference across **294 genuine payment-engine orders**. Honest note: 89 test-fixture orders carry
`amount_paid` with **zero** `pos_payment` rows — these are programmatic test creations, not payment-engine
transactions (a real tender always writes a payment row); excluding them, every genuine paid order
reconciles exactly. Refund invariant: model constraint caps cumulative refund ≤ sold on every path.
Evidence: `financial-reconciliation/reconciliation.txt`.

## 11. Session opening / closing
Native Odoo POS session lifecycle reused unchanged. Opening/closing cash control intact; a session with
unresolved payments cannot be silently closed. Mezze mutating session/order routes declare `readonly=False`
(the Odoo-19 read-only-default defect, previously fixed and regression-tested). Evidence: `sessions/sessions.md`.

## 12. Hardware acceptance — **on-site**
No physical hardware in the build host. Hardware jobs queue through the outbox and dispatch idempotently;
printer/KDS-unavailable is queue-and-reconnect. Real receipt/kitchen print, drawer kick, and terminal tender
**must be exercised on the pilot hardware before first service**. Evidence: `hardware/hardware.md`.

## 13. Multi-device acceptance
Separate cashier + KDS + manager clients PROVEN via live **2-worker** execution (3 worker children) driving
concurrent HTTP clients with DB assertions; seat/fire/pay/merge/aggregator each resolve to exactly one
logical operation (idempotent); role boundaries enforced. Evidence: `device-acceptance/device-acceptance.md`,
`tests/concurrency/`.

## 14. Tablet acceptance — **on-site**
Physical tablet viewport (1024×768, 100%/120%, Arabic RTL) is **not forceable** in the hi-DPI CI host
(`resize_window` no-ops; frames stuck ~1568px). Responsive CSS + RTL present. **Must be re-verified on the
pilot tablet before launch.** Evidence: `device-acceptance/device-acceptance.md`.

## 15. Restaurant workflow acceptance
Arrival → seat (idempotent) → course hold/fire → KDS prep → tender → transfer/safe-merge → close: proven by
the mezze_runtime suite + multi-worker concurrency. Host/server/cashier/kitchen/manager role loop enforced.

## 16. Omnichannel acceptance
QR (signed, pausable, 86-aware), pickup (pay-at-counter + secure status), delivery (zone/fee/ETA +
pay-on-delivery; manual driver dispatch), aggregator (HMAC-signed, 401 on bad sig, rate-limited, idempotent
— duplicate callback → one order). Online card checkout & drive-thru disabled. Evidence: `omnichannel/omnichannel.md`.

## 17. Cancellation / refund acceptance
Before-fire cancel + refund-engine path proven; refund constraint blocks refunding more than sold on every
path; duplicate refund blocked; paid cancellation flows through the refund engine (no order deletion/edit).
Fired/preparing cancels require a staff/manager decision (runbook — Pilot supported with manual procedure).

## 18. Canonical menu contract
Single canonical order/product engine; 86 an item on KDS/manager view propagates to all customer channels
and checkout rejects it (`_assert_available`). 101-setting authoritative catalog (`settings_catalog.py`,
checksum in manifest) is the single source of truth for configurable behavior.

## 19. Performance
Pilot-relevant risk is correctness under contention, which holds: live 2-worker traffic sustains
seat/fire/pay/merge/aggregator with zero double-effects; per-endpoint rate limits prevent starvation;
outbox enqueue ~1.6ms/dispatch ~2.3ms per event (batch 200). A formal p95/throughput load-test is a
pre-public-launch task, not pre-pilot (a single branch's peak is within the proven envelope). Evidence: `performance/performance.md`.

## 20. Failure recovery
Lost payment response → same-uuid resubmit returns the existing payment (never a second); worker kill →
queued work re-delivers once; poison outbox event → dead-letter + replay (never duplicates); duplicate
aggregator callback → one order; illegal concurrent transition → 409 (no silent overwrite). Evidence:
`failure-recovery/failure-recovery.md`, `tests/concurrency/*_evidence.txt`.

## 21. Outbox / dead-letter operations
Outbox view exposes event type, business id, attempt count, last error, next retry, correlation id.
Replay is idempotent; deletion prohibited; poison events dead-letter after max attempts and are flagged by
the validator. Runbook: `runbooks/runbooks.md` (stuck event / failed webhook).

## 22. Monitoring & alerts
Validator + dead-letter count + outbox visibility + security-event aggregation (replay/signature-failure
counters). What to watch and thresholds: `monitoring/monitoring.md`. Support/manager visibility is via the
outbox view + audit log + Admin Console (no separate console built — reuses existing surfaces).

## 23. Logging & traceability
Every business event carries a correlation id; the audit log records security-relevant events
(best-effort, savepoint-isolated). Escalation payload (order uuid, correlation id, branch, timestamp,
worker, outbox/audit rows) defined in the runbooks.

## 24. Backup & restore
Real `pg_dump -Fc` → `pg_restore --no-owner` into a clean DB, **exact row-count match (0 data loss)**,
measured **RTO ~14s** at pilot data scale. Evidence: `backup-restore/backup-restore.txt`.

## 25. Rollback
Restore-based rollback exercised (the backup/restore run is the rollback drill). Release rollback = redeploy
prior tag + restore pre-upgrade dump; additive schema means no destructive downgrade. Evidence: `rollback/rollback.md`.

## 26. Support visibility
Support/manager sees live state through the outbox view, audit log, and Admin Console governance surfaces —
existing surfaces, no new console. Runbooks give the symptom→action→verify→escalate path per incident class.

## 27. Runbooks
11 incident runbooks (card-charged-response-lost, terminal down, refund, printer/KDS down, stuck outbox,
aggregator outage, QR pause, product-86, order conflict, internet outage, restore/rollback), each with
Symptom · Immediate · Safe workaround · Prohibited · Verify · Escalate. Evidence: `runbooks/runbooks.md`.

## 28. Staff UAT
Representative now: every role's permission boundary enforced + regression-tested. On-site: trained staff run
a real service day following the runbooks (intrinsically not a CI artifact). Evidence: `staff-uat/staff-uat.md`.

## 29. Training
Role-scoped quick guides (host/server, cashier, kitchen, manager, all-staff) cross-referenced to runbooks.
Evidence: `training/training.md`.

## 30. Pilot data readiness
Menu/products, POS config, payment methods (cash/card journals), settings catalog (101) seeded and validated
(validator payment_methods/journals/pos_config_present = PASS). Secrets sourced from env / encrypted at rest.

## 31. Pilot-day simulation
Full transaction mix simulated as automated scenarios (cash/card/mixed/partial/change/failed/refund/
partial-refund/duplicate-refund-blocked/cancel-before-fire/paid-cancel/aggregator-prepaid/pay-on-delivery/QR)
plus concurrent multi-worker traffic — all green. The live wall-clock service day is the pilot's first day.
Evidence: `pilot-simulation/pilot-simulation.md`.

## 32. Defects found (this increment)
1. Public status token stored raw, without expiry/revocation — a pilot-relevant information-exposure risk.
2. Report/evidence honesty: the reconciliation query surfaced 89 amount_paid-vs-payment mismatches that had to be explained rather than glossed.
(No new Critical/financial-Major defects surfaced. The Odoo-19 read-only-route class was already fixed in prior increments.)

## 33. Defects fixed
1. Status token → SHA-256 hash storage, 128-bit entropy, 24h expiry, manual revocation, hardened resolver + controller length/hash/revoke/expiry checks; regression tests added.
2. Reconciliation classified honestly: 0 difference on 294 genuine payment-engine orders; the 89 are documented test fixtures without payment rows (not a financial defect).

## 34. Remaining blockers
- Pilot: **none** that are code blockers. Two on-site prerequisites gate first service: real hardware, real tablet.
- Public launch: online card-payment journey unproven/disabled; formal load test; full on-site staff UAT + service-day; physical hardware/tablet sign-off.

## 35. Evidence directory
`docs/go-live/` with subdirs: installation, migration, configuration, security, financial-reconciliation,
sessions, hardware, device-acceptance, omnichannel, performance, failure-recovery, monitoring, backup-restore,
rollback, runbooks, staff-uat, training, pilot-simulation — plus release-manifest.md, scope-and-limitations.md,
launch-checklist.md, final-verdict.md, and this report. Evidence persisted in-repo (not only /tmp).

## 36. Automated regression tests
Suite: mezze_invariants + mezze_runtime, run on live Odoo 19 + PostgreSQL (`--test-enable --stop-after-init`).
**Result: `0 failed, 0 error(s) of 218 tests` — exit code 0, 17.7s, 20,726 queries** (live run, `--log-level=test`).
Deliberate negative-path noise (duplicate-nonce replay rejection, best-effort audit-append failing soft on
read-only routes) is expected ERROR-log output and does not fail any test — the authoritative result line is
`odoo.tests.result: 0 failed, 0 error(s) of 218 tests`.

## 37. Launch checklist
Mandatory-pass / conditional / must-disable matrix in `launch-checklist.md`. All mandatory code gates PASS;
the two ⚠ mandatory gates (real printing, real tablet) are on-site verifications; disabled-list enforced.

## 38. Final go / no-go verdict
- **Controlled pilot: GO**, conditioned on completing real-hardware and real-tablet verification before first service, with the disabled-capabilities list enforced.
- **Unrestricted public launch: NO-GO.** Full statement: `final-verdict.md`.

---

## Explicit confirmations
- [x] No new platform layer built; no completed workflow redesigned; no major new feature added (only a read-only validator + a scoped status-token security fix).
- [x] MEZZE_MASTER_KEY sourced from the environment — never in PostgreSQL, never in source control, never printed in reports/tests/logs.
- [x] Aggregator/webhook secrets encrypted at rest (AES-GCM envelope); no real secret value displayed anywhere.
- [x] No fabricated data, metrics, or trust signals; the 89-order reconciliation anomaly is disclosed and explained, not hidden.
- [x] Every known limitation classified as exactly one of: Pilot supported / Pilot supported with manual procedure / Disabled for pilot / Hidden from users / Launch blocker (`scope-and-limitations.md`).
- [x] Unsupported behavior (online card, drive-thru, seat-level split, driver dispatch) is disabled and NOT marketed to staff or customers.
- [x] Financial integrity verified on the live DB: 0 over-paid, 0 orphan payments, 0 genuine reconciliation difference (294 orders).
- [x] Public status tokens are hash-stored, expiring, and revocable (no raw token persisted).
- [x] Backup/restore proven with zero data loss and a measured RTO (~14s); rollback is restore-based and exercised.
- [x] Failure-recovery, idempotency, and multi-worker correctness proven by the concurrency suite.
- [x] Evidence stored under `docs/go-live/` in the repository (not only in /tmp).
- [x] Agents performed no git staging/commit/push/tag — those remain the release owner's actions.
- [x] A test suite alone was NOT treated as sufficient: live DB assertions, a real backup/restore, a config validator, multi-worker runs, and honest on-site classifications back this verdict.
- [x] **Is the branch approved for a controlled restaurant pilot?** — **YES**, conditioned on real-hardware and real-tablet on-site verification and enforcement of the disabled-capability list.
- [x] **Is the branch approved for unrestricted public launch?** — **NO.**
