# Mezze POS — Installers (Cloud & Edge)

## Mezze Edge (branch-local, Ubuntu 24.04 LTS x86-64)

The Edge deploy pack lives at `deploy/edge/` (sibling of `addons/`). It is
parameterized, supports a dry run, and never commits or echoes secrets.

| Script | Purpose |
|---|---|
| `install.sh` | provisions venv + Odoo + PostgreSQL role/DB + systemd + nginx + odoo.conf; installs `mezze_bridge` with `--without-demo=all` (factory-empty) |
| `backup.sh` / `restore.sh` | scheduled backups + guarded restore (RTO≈14s recorded) |
| `upgrade.sh` / `uninstall.sh` | backup-gated update / clean removal |
| `validate.sh` | runs the edge-profile go-live validator |
| `support-bundle.sh` / `release-identity.sh` | diagnostics / "what build is this" |
| `lib/common.sh` | `redact()` + `gen_secret()` helpers |
| `templates/` | systemd unit, nginx.conf, odoo.conf, logrotate, backup.env |

**Security guarantees enforced by the pack:**

- `MEZZE_MASTER_KEY` and DB password are generated (`gen_secret`) and written only
  to the environment/config files on the box — never committed, never echoed.
- No `admin/admin`: the admin password is set to a generated value.
- The Odoo database manager is secured (`admin_passwd` set; `list_db` off in prod).
- HTTPS via nginx (`templates/nginx.conf` + `lib/make-cert.sh`); `proxy_mode` on.
- Certified OS pinned: `MEZZE_CERTIFIED_OS_ID=ubuntu`, version `24.04`, `x86_64`.

**Clean-host certification status:** the two-host clean-install certification is
tracked in `docs/sell-ready/edge/certification/s1_1b/RUNBOOK.md` and is marked
**NOT EXECUTED** there — it completes during the S6 pilot. The scripts themselves
are certified via `deploy/edge/tests/selftest.sh`.

## Mezze Cloud (Mezze-managed)

Cloud is a Mezze-managed deployment of the same Community stack + `mezze_bridge`
(not standard Odoo Online — Odoo's SaaS does not permit arbitrary custom addons).
Provisioning, TLS, backups, and updates are operated by Mezze; the customer receives
a URL and an admin login and runs onboarding from the console.

## After install (both editions)

Run onboarding (`/mezze_bridge/static/onboarding.html`), pick the business profile,
and drive `/admin/golive` to green for that profile before go-live.
