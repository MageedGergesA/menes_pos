# Mezze POS — Controlled Pilot Release Manifest (RC1)

| Field | Value |
|---|---|
| Release name | **Mezze POS — Controlled Pilot** |
| Candidate number | **RC1** |
| Timestamp (freeze) | 2026-07-25 (EEST) |
| Source branch | `main` |
| Release commit | `277338b87e4ca497754474d39f81f44ae45d2aa7` (release-content commit; the annotated tag is placed on the identity commit that records this line — code/tests/assets are identical between the two) |
| Release tag | `mezze-pilot-rc1` (annotated; created after the identity commit) |
| Odoo version | 19.0 (`v2.0.0-rc1`) |
| Python version | 3.10.12 |
| PostgreSQL version | 14.23 |
| Operating system | Linux 6.8.0-124-generic (Ubuntu 22.04) |
| Module version | mezze_bridge **19.0.1.8.0** |
| Latest migration | `migrations/19.0.1.6.0/` (idempotent); 1.7.0/1.8.0 columns via ORM auto-schema on `-u` |
| Automated test count | **218 tests — 0 failed, 0 error(s), exit code 0** (`release-test.log`) |
| Financial reconciliation | overpaid 0 · orphan 0 · **unexplained difference 0** across 294 genuine orders (`financial-reconciliation/rc1-reconciliation.txt`) |
| Configuration validator (production profile) | **0 FAIL**, 1 env-prerequisite warning — company_timezone unset (`configuration/rc1-production-validation.txt`) |
| Backup / restore | **0 row loss** across 17 critical tables; backup 1.06s · restore 13.35s · 7.6M (`backup-restore/rc1-backup-restore.txt`) |
| Status-token policy | SHA-256 hash storage · 128-bit entropy · 24h expiry · manual revocation (raw never persisted) |

## Enabled feature scope (pilot)
counter POS · dine-in service · reservations · walk-ins & waitlist · table transfer · financially-safe
table merge (blocks orders with payments) · courses & KDS · partial & mixed payment · refunds · QR table
ordering · pickup (pay-at-counter) · pay-on-delivery · approved **prepaid** aggregator ingestion · customer
order status (secure token) · design system · User Settings · Admin Console · operational validation ·
runbooks & go-live evidence.

## Disabled feature scope (must remain off for the pilot)
| Capability | State in code | How access is prevented |
|---|---|---|
| Online card payment | **Absent** — no PSP/redirect route exists | Cannot be reached (no route) |
| Durable seat-level line identity | **Absent** — not modelled | Cannot be reached (no model) |
| True split-by-seat | **Absent** — only split by item/equal/custom | Cannot be reached |
| Drive-thru | **Present** in code (`/drivethru/*` routes + `drivethru.html`) | Routes are `_authorize()`-gated (authenticated terminal only, not public); **not surfaced in pilot navigation**. Operationally disabled by not provisioning a drive-thru client. NOT hard-flag-blocked — see limitation D-1. |
| Advanced driver dispatch | Partial (zone/fee/ETA + accepted/preparing/ready) | Driver assignment is a manual staff procedure (runbook) |
| Unverified payment providers / aggregators | Not provisioned | No secret configured → validator would flag; kept inactive |
| Unsupported public cancellation paths | Not exposed | Before-fire cancel + refund-engine only |

## Frontend asset checksums (sha256, first 16 hex)
| Asset | Checksum |
|---|---|
| static/mezze-design.css | `f58251de4609e018` |
| static/mezze-design.js | `f8be3e117a51d074` |
| static/mezze-customer.css | `aeff6f5efccc3873` |
| static/mezze-customer.js | `87b68b2476c9ca39` |
| static/pos.html | `c0a32ba9dbb87605` |
| **Design-token source** `domain/settings_catalog.py` | `edeea72f0c5a922f` (101-setting source of truth) |

## Known limitations (honest classification)
- **D-1 (drive-thru not hard-blocked):** reachable by an authenticated terminal; mitigated operationally (not surfaced, client not provisioned). Candidate for a scoped RC2 server gate if the pilot owner requires API-level blocking.
- **Hardware / tablet / on-site staff acceptance:** not executable in a hardware-less CI host — see `on-site-acceptance/` (pending real execution; nothing pre-marked Passed).
- **company_timezone** must be set on the pilot host (validator env-prerequisite warning).
- **cryptography** runtime is 3.4.8 (target ≥42) — a deployment-host upgrade task, app runs green.

## Required on-site gates (before first live service)
Real receipt printer · cash drawer (or N/A with reason) · kitchen printer (or N/A) · independent cashier
browser · independent KDS browser · true 1024×768 CSS-viewport tablet · Arabic RTL tablet flow ·
five-client service loop · session close reconciliation · on-site financial sign-off (difference = 0).
Execute the pack in `on-site-acceptance/`. Physical-device acceptance is **NOT** claimed by this manifest.

## Release hygiene
- [x] No real secrets in tree (scan: only install-time random-token generation + fake test fixtures).
- [x] No absolute paths in shipped module code; `tests/concurrency/` (local-path drivers) **excluded** from RC1.
- [x] Root `CLAUDE.md` (dev tooling) **excluded** from RC1.
- [x] `MEZZE_MASTER_KEY` from env only; aggregator/webhook secrets AES-GCM encrypted at rest.
- [x] Database backups kept out of git (scratchpad only).
- [x] `python3 -m compileall` clean; `git diff --check` clean.
- [x] Release commit created (`277338b`); identity commit records the hash; annotated tag `mezze-pilot-rc1` placed on the identity commit.
