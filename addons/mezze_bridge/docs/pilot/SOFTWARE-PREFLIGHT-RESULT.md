# CP12 — Software Preflight Result

Executed software go-live gates for the cumulative R2 build. **Physical / external items are
explicitly PENDING — not executed here.** No release tag; nothing committed.

- Build: branch `review/w2`, module **19.0.2.7.0**, HEAD baseline `4abde09`, **dirty/uncommitted**.
- Runtime: Odoo 19.0, Python 3.12, PostgreSQL 14.

| Gate | Method | Result |
|---|---|---|
| Fresh install | `-i mezze_bridge --without-demo=all` on a brand-new DB `mezze_fresh` | **PASS** — Modules loaded; ACLs/assets/crons/data all load; 37/37 tests incl. bootstrap + floor + cashier browser |
| Install-vs-upgrade differential | ran the browser suite on the fresh DB | **PASS** — caught & fixed a fresh-only fixture collision (pos_restaurant auto-seeds a default floor/table 1); fixture now authoritative |
| Upgrade | `-u mezze_bridge` on the seeded DB | **PASS** — exit 0; counts identical (ord=4 pay=3 line=4 res=1 dlv=1 set=101 cron=2); no dup crons/data |
| Production assets | fresh compiled bundles served in tests | **PASS** — Owl templates compile; no 404 bundle (see restore caveat re: filestore) |
| Multi-worker | `--workers=2`, concurrent requests | **PASS** — 2 workers serve concurrent health/status; opaque-token-only enforced cross-worker; 0 crashes; idempotency is DB-backed (unique constraints, no process-local authority) |
| Server restart | seeded shift survived install/upgrade/backup/shell/multi-worker restarts | **PASS** — 4 orders/3 payments/2 drafts/$20 partial/1 reservation persist (PG-backed) |
| Backup | `pg_dump -Fc mezze_fresh` | **PASS** — 7.0 MB, ~1 s, exit 0 |
| Restore (DB only) | `pg_restore` into `mezze_restored` | **DATA PASS / CASHIER FAIL** — all counts match, but cashier unbootable: compiled assets live in the **filestore**, which pg_dump does not include |
| Restore (DB + filestore) | restore DB + copy `<data_dir>/filestore/<DB>` | **PASS** — cashier mounts + completes a cash sale on the restored DB; the 1 ignored `pg_restore` error is a benign cross-version GUC (`transaction_timeout`) |
| Integrity validator | `mezze.golive.validator.integrity()` on restored DB | **PASS** — 11/11 checks (uuid uniqueness, tender-key, one-draft-per-table, table/reservation/waitlist branch bindings, delivery/aggregator wrappers, outbox dead-letters, config/payment present) |
| Integrity detects anomalies | CP12 tests seed anomalies | **PASS** — detects two-drafts-per-table, cross-branch reservation link, orphan delivery |
| Validator valid vs empty | CP12 tests | **PASS** — valid base config passes required checks; a config-less deployment FAILs (never green on empty) |
| Deterministic shift | seeded cash+card+partial | **PASS** — completed gross 126.00 = Cash 84 + Card 42; partial $20 stays open; no unexplained variance |
| Security invariants | EndpointCoverage / RouteScope / P61Structural / Authz | **PASS** — 5/5 |
| Secret scan | repo grep (prod code + static bundles) | **PASS** — no hardcoded secrets; only synthetic keys inside a redaction test |
| Health endpoint | `GET /mezze/api/v1/health` | **PASS** — liveness only `{ok,odoo,module}`, no config/secret; distinct from `/admin/golive` readiness |
| CP1–CP12 regression | full suite + CP12 | **PASS** — 81 tests, 0 failed / 0 errors, HOOT 40 tests / 146 assertions |

## Backup/restore procedure (corrected)
Back up **and restore BOTH**:
1. PostgreSQL: `pg_dump -Fc -d <DB> -f <DB>.dump` → `createdb <NEW>; pg_restore -d <NEW> --no-owner --no-privileges <DB>.dump`
2. Filestore: copy `<data_dir>/filestore/<DB>` → `<data_dir>/filestore/<NEW>`
Then start Odoo on `<NEW>` and run `mezze_preflight.py`. A DB-only restore is **not** sufficient.

## Production flags (must be set for the pilot profile)
`env_profile=production` · `api_security=enforce` (runtime default already enforce) · `shared_token_disabled=true`
· `signing_mode.*=enforce` · `neutralized=false` · `demo_loaded=false` · `MEZZE_MASTER_KEY` set (32-byte base64).
The go-live validator FAILs the production profile if any of these are unsafe.

## Not executed (PENDING PHYSICAL / EXTERNAL)
Receipt printing & Arabic paper appearance, cash drawer kick, payment terminal, KDS hardware, real tablet/phone,
real WAN cut, UPS/power loss, staffed shift, real backup/restore on site, external provider certification.
See `HARDWARE-MATRIX.md` and `PROVIDER-MATRIX.md`.
