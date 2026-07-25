# Pilot Launch Checklist (P1 §28)

## Mandatory pass (controlled pilot)
| Gate | Status | Evidence |
|---|---|---|
| Clean installation | ⚠ Documented | fresh-install procedure documented; not executed in this env (existing dev DB used). Prerequisites in installation/. |
| Migration | ✅ PASS | migrations 19.0.1.x.0 idempotent; `-u` applied cleanly; pre/post assertions in migration/. |
| Configuration validation | ✅ PASS | validator: 0 FAIL (4 dev-only warnings) — configuration/validator-report.txt |
| Financial reconciliation | ✅ PASS | 0 diff across 294 genuine payment-engine orders — financial-reconciliation/ |
| Session close | ✅ PASS (code) | mutating session routes writable; close blocked on unresolved payments (readonly-fix + guards). |
| Real printing | ⚠ On-site | hardware not in build env; outbox print jobs exist; **verify on pilot printer**. |
| Real tablet | ⚠ On-site | viewport not forceable on hi-DPI CI host; responsive CSS present; **verify on pilot tablet**. |
| Separate cashier + KDS clients | ✅ PASS (multi-worker) | live 2-worker execution + role boundaries (R1.1); separate browser tabs used. |
| Backup restore | ✅ PASS | pg_dump+restore, 0 data loss, RTO ~14s — backup-restore/ |
| Rollback procedure | ✅ Documented+exercised | restore-based rollback exercised (backup restore) — rollback/ |
| Security gate | ✅ PASS | security/security-gate.md (0 blocker) |
| Role UAT | ⚠ Representative | role boundaries proven by tests (host/server/cashier/kitchen/manager); real staff UAT is an on-site step. |
| Pilot-day simulation | ⚠ Partial | scenario invariants proven by suite + multi-worker; a full on-site service-day run is the pilot itself. |
| No unresolved Critical | ✅ | 0 |
| No unresolved financial Major | ✅ | 0 |
| No unexplained reconciliation diff | ✅ | 0 (genuine transactions) |

## Conditionally accepted for pilot
Cosmetic defects · minor report layout · non-critical disabled preferences · optional channels disabled (drive-thru) · documented manual delivery-dispatch procedure.

## Disabled while incomplete (must stay OFF for pilot)
Online **card** payment · **drive-thru** · advanced dispatch · **seat-level** split · any untested payment provider · any unverified aggregator · any public cancellation path that violates state policy.
