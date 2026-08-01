# Mezze Edge — Deployment Pack (S1.1)

Repeatable, parameterized deployment of Mezze Edge (Odoo 19 + PostgreSQL + nginx + systemd) onto a clean
supported Linux host. **No developer paths, no hardcoded secrets, no per-customer source edits.**

Software base: `mezze-pilot-rc3` (`8ad8ed9`), module 19.0.1.9.0.
Certified target OS: **Ubuntu Server 22.04 LTS** (x86-64).

## Contents
```
deploy/edge/
├── install.sh            # provision a branch (supports --dry-run)
├── upgrade.sh            # preflight → mandatory backup → -u → validate
├── uninstall.sh          # customer exit: export data first, then remove
├── validate.sh           # run the Edge validator profile
├── backup.sh             # local pg_dump -Fc + filestore + manifest + checksum (WAN not required)
├── restore.sh            # guarded restore (checksum + --yes + stop/restore/start/validate)
├── support-bundle.sh     # redacted diagnostics archive
├── release-identity.sh   # "what build is this branch running?"
├── lib/
│   ├── common.sh         # shared helpers (render, secrets, redact)
│   └── make-cert.sh      # local-CA HTTPS (Option B)
├── templates/            # odoo.conf, systemd unit, nginx, logrotate, backup.env (${VAR} tokens)
├── tests/selftest.sh     # artifact self-tests (no root): syntax, render, unit, cert, redaction, dry-run
└── README.md
```

## Quick start (on a clean Ubuntu 22.04 host, as root)
```bash
# prerequisites: postgresql, nginx, python3-venv, openssl, gettext-base (envsubst)
sudo ./install.sh \
  --hostname mezze.local \
  --db-name restaurant01 \
  --branch-name "Main Branch" \
  --odoo-source  /opt/mezze/odoo \
  --addons-source /opt/mezze/addons
# → provisions user/dirs/venv/deps/role/config/service/nginx/HTTPS/logrotate,
#   installs mezze_bridge (--without-demo=all, R-1 seeds the 101-setting catalog),
#   enables services, runs the Edge validator (must be 0 FAIL).
```
Preview without changing anything: add `--dry-run`.

## Secrets
Generated once at install into `/etc/mezze-edge/{secrets.env,mezze.env}` (`0600`, owned by the service
user). `MEZZE_DB_PASSWORD`, `MEZZE_ADMIN_PASSWD`, `MEZZE_MASTER_KEY` are never committed and never printed
after provisioning. `MEZZE_MASTER_KEY` lives outside PostgreSQL and the repo.

## Backup / restore
```bash
sudo MEZZE_BACKUP_TS=$(date +%Y%m%d-%H%M%S) ./backup.sh restaurant01     # local; off-site optional
sudo ./restore.sh --backup /var/lib/mezze/restaurant01/backups/<stamp> --db restaurant01 --yes
```
Local backup never depends on WAN; off-site upload runs afterward only if enabled and never invalidates a
good local backup.

## Self-tests
```bash
bash tests/selftest.sh   # 21 checks: bash -n, template render, systemd verify, nginx structure, cert chain, redaction, dry-run
```

## Not in this pack (by design)
Physical hardware certification (printer/drawer/tablet/KDS), clean-VM install execution, live systemd/nginx
bring-up, and the 2-hour WAN outage are **S1.2** on-hardware gates. This pack is the engineering that makes
those executable; it does not fake them. See `../addons/mezze_bridge/docs/sell-ready/`.
