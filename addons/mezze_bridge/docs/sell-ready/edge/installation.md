# Mezze Edge — Deployment & Installer (S1 §2–3)

**Approach:** reuse the project's existing technology (Odoo 19 + PostgreSQL + a plain systemd service +
nginx reverse proxy on a supported Linux host). **No Docker/Kubernetes/Ansible** introduced for v1.

## Supported baseline OS (v1 certified target)
**Ubuntu Server 24.04 LTS (Noble Numbat) x86-64** is the certified v1 target — Odoo 19's current Ubuntu
package target and a longer-lived production baseline than 22.04. Ubuntu 26.04 is NOT part of this phase;
other distros are UNTESTED until certified. The installer's `check_platform` enforces this (override:
`--allow-unsupported-os`, engineering only).

## Python policy
Odoo 19 requires **Python ≥ 3.10**; use the interpreter Ubuntu 24.04 provides (Python 3.12) — do not pin
3.10 or downgrade the system Python. The installer creates a venv from the host `python3`.

## PostgreSQL policy
Odoo 19 supports **PostgreSQL ≥ 13**; the Ubuntu 24.04 repository version (PostgreSQL 16) is the normal
certified install. Do not require exactly 14 — Mezze has no proven 14-only dependency. Record the exact
installed version during certification.

## What the deployment must provision (§2)
PostgreSQL · Odoo 19 · Mezze required addons + `mezze_bridge` · Python deps · a dedicated DB role · a
dedicated `odoo` service account · filestore dir · Odoo config · systemd unit(s) · worker + gevent/websocket
config · nginx reverse proxy + HTTPS · logs + logrotate · backup dir + restore tools · health check ·
production profile · the branch database.

## Installer contract (§3)
A repository-controlled installer (`mezze-edge install`, to be built as a parameterized shell script under
`deploy/edge/` — NOT yet implemented) accepting: `DB_NAME`, `BRANCH_NAME`, `HOSTNAME`, `LOCAL_DOMAIN`,
`ODOO_USER`, `ODOO_PORT`, `GEVENT_PORT`, `WORKERS`, `PG_*` connection, `BACKUP_PATH`, `CERT_PATH`,
`ADDONS_PATH`. Requirements:
- **Idempotent** where practical; a repeated run/validation must not destroy data.
- **No developer absolute paths** (no `/home/mageed/...`), no test credentials, no source-tree secrets.
- Secrets (DB password, `MEZZE_MASTER_KEY`) supplied via environment or a `0600` config file, never
  hardcoded and never committed.
- `MEZZE_MASTER_KEY` generated once per branch at install (base64 of 32 random bytes) and stored outside
  PostgreSQL and outside the repo.
- No manual source edits per customer.

## Reference config skeleton (parameterized — illustrative)
```ini
[options]
addons_path = ${ADDONS_PATH}
data_dir    = /var/lib/mezze/${DB_NAME}/filestore
db_host     = 127.0.0.1
db_user     = ${PG_USER}
db_password = ${PG_PASSWORD}      ; from env / 0600 file, never committed
http_port   = ${ODOO_PORT}
gevent_port = ${GEVENT_PORT}
workers     = ${WORKERS}
proxy_mode  = True
list_db     = False
log_level   = warn
logfile     = /var/log/mezze/${DB_NAME}.log
```
Post-install: `-i mezze_bridge --without-demo=all` (R-1 seeds the 101-setting catalog automatically), set
`mezze_bridge.env_profile=production`, run the Go-Live/Edge validator (must be 0 FAIL).

## Status
Documented approach only. The installer script, systemd units, nginx/HTTPS templates, and logrotate policy
are **not yet built** (see readiness-matrix.md). The clean-install test (§28) and upgrade test (§29) are
**NOT EXECUTED** — they require a clean supported host/VM and, for full certification, real branch hardware.
