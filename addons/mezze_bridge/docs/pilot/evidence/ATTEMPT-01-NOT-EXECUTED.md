# Physical Pilot Attempt 01 — NOT EXECUTED

> This record documents a physical-pilot **attempt** against RC4 that could **not** be
> executed because no field environment, hardware, staff, or provider was available.
> The blank templates in this directory remain unfilled and reusable for the real
> on-site pilot. **No physical PASS is claimed. No field evidence is fabricated.**

## 1. RC identity (VERIFIED — software)
- Release Candidate: **mezze-v1.0-rc4**
- Certified commit: **cad16ae3b46de2d0e6c85210656c0d90bc87c023**
- Module: **mezze_bridge 19.0.2.7.0**
- Freeze check: `git rev-parse HEAD` == RC; `git describe --tags --exact-match` == `mezze-v1.0-rc4`; tag peeled `^{}` == RC; working tree clean; `origin/review/w2` == RC; `main` untouched (`a0a5d8f`).

## 2. Software preflight (PASS — software, not field evidence)
- `docs/pilot/mezze_preflight.py` → `PREFLIGHT_RESULT: GO`
- Data integrity: **11/11 PASS** (0 fail)
- Go-live config required checks: **0 fail** (dev-profile WARNINGs only)
- Frozen regression reference: **81 tests, 0 failed, 0 errors**; HOOT **40 tests / 146 assertions**
- `/admin/version` identity (release_identity code path): git_commit == `cad16ae…`, module_version `19.0.2.7.0`

## 3. Environment (as attempted)
- **Headless developer workstation only — NOT a branch/site deployment.**
- Odoo 19 dev instance; PostgreSQL 14; Python 3.12.
- No pilot branch, no store network, no physical pilot infrastructure.

## 4. Hardware status
| Device | Status |
|---|---|
| Receipt printer | PENDING PHYSICAL |
| Cash drawer | PENDING PHYSICAL |
| KDS display | PENDING PHYSICAL |
| Tablet | PENDING PHYSICAL |
| Customer phone | PENDING PHYSICAL |
| Payment terminal | EXTERNAL CERTIFICATION PENDING / PENDING PHYSICAL |
| Router / WAN control | PENDING PHYSICAL |
| UPS / power | PENDING PHYSICAL |

## 5. Staff
- None available for physical execution.
- No cashier / server / host / kitchen / manager field operators.
- No physical cash count performed.

## 6. Providers
- No provider environment or credentials supplied.
- Payment terminal / provider certification pending.
- Aggregator / provider certification pending where applicable.
- E-invoice provider pending where applicable.

## 7. Pilot execution
- Field orders executed: **0**
- Real shift duration: **N/A**
- Physical cash difference: **N/A**
- Physical gates passed: **0**
- Physical gates failed: **0**
- Physical gates not executed: **all applicable gates**

## 8. Defects
- **No physical defects observed because the physical pilot was not executed.**
- Separately, the software preflight has **0 unresolved Critical software defects** (software evidence only, not a field-quality claim).

## Pilot gate table
| Gate | Evidence | Status |
|---|---|---|
| RC identity | git HEAD/tag/peeled == cad16ae, tree clean | VERIFIED SOFTWARE |
| Software preflight | `mezze_preflight.py` GO | PASS SOFTWARE |
| Security / integrity | validator 11/11 + frozen suites 81/0/0, HOOT 40/146 | PASS SOFTWARE |
| Cashier physical operation | no field workstation/staff | NOT EXECUTED — PENDING PHYSICAL |
| Floor / table service | no field operation | NOT EXECUTED — PENDING PHYSICAL |
| KDS physical display | no device | NOT EXECUTED — PENDING PHYSICAL |
| Reservation / waitlist live | no staff/site | NOT EXECUTED — PENDING PHYSICAL |
| Transfer / merge live | no staff/site | NOT EXECUTED — PENDING PHYSICAL |
| Partial / mixed tender | no real cash/terminal | NOT EXECUTED — PENDING PHYSICAL |
| QR table ordering | no customer phone/site QR | NOT EXECUTED — PENDING PHYSICAL |
| Pickup / delivery | no customer field device/site | NOT EXECUTED — PENDING PHYSICAL |
| Customer status | no customer device | NOT EXECUTED — PENDING PHYSICAL |
| Receipt printer | no printer | NOT EXECUTED — PENDING PHYSICAL |
| Arabic printed receipt | no printer | NOT EXECUTED — PENDING PHYSICAL |
| Cash drawer | no drawer | NOT EXECUTED — PENDING PHYSICAL |
| Payment terminal | no hardware/provider environment | EXTERNAL CERTIFICATION PENDING |
| WAN outage | no branch network | NOT EXECUTED — PENDING PHYSICAL |
| Device reconnect | no physical device/site | NOT EXECUTED — PENDING PHYSICAL |
| KDS restart | no device | NOT EXECUTED — PENDING PHYSICAL |
| Server restart (on-site) | no site window | NOT EXECUTED — PENDING PHYSICAL |
| UPS / power | no UPS | NOT EXECUTED — PENDING PHYSICAL |
| Site backup / restore | DB+filestore procedure proven in CP12 software; no site storage | NOT EXECUTED — PENDING PHYSICAL |
| Shift close | no shift/staff | NOT EXECUTED — PENDING PHYSICAL |
| Cash reconciliation | no physical cash | NOT EXECUTED — PENDING PHYSICAL |

## Final evidence verdict
- **PHYSICAL PILOT: NOT EXECUTED** (not PASS / not PASS WITH CONDITIONS / not FAIL — no physical pilot took place).
- **SOFTWARE PREFLIGHT: GO FOR PHYSICAL PILOT.**
- **COMMERCIAL CERTIFICATION: NOT GRANTED.**
- **FINAL COMMERCIAL RELEASE: NOT CREATED.**

## Next action (requires a human field team)
Deploy `mezze-v1.0-rc4` to a real branch; use real target hardware and real staff roles;
execute `docs/pilot/CP12-PILOT-RUNBOOK.md`; capture photos / receipts / device info / network
timing; perform actual cash reconciliation; execute **DB + filestore** backup/restore; supply
provider evidence where commercially required. Only those real observations convert the pending
gates into PASS/FAIL and fill the blank templates in this directory.
