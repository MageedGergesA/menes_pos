# Mezze Edge v1.0 — Readiness Matrix (S1 §1)

Software base: `mezze-pilot-rc3` (`8ad8ed9`), module 19.0.1.9.0. Classification of each Edge concern as of
this engineering-preparation pass. **Ready** = proven/self-contained in RC3; **Partially ready** = exists
but needs deployment packaging or on-hardware verification; **Missing** = deployment artifact not yet built;
**Deferred** = out of Edge v1 scope; **N/A**.

| # | Concern | Status | Notes |
|---|---------|--------|-------|
| 1 | Odoo service | Partially ready | Runs; needs a packaged systemd unit + service account (see installation.md). |
| 2 | PostgreSQL | Partially ready | Works (14.23 tested); needs Edge provisioning script + local role/password policy. |
| 3 | Reverse proxy | Missing | No proxy config shipped; nginx template + `proxy_mode` needed for HTTPS/websocket (HTTPS.md). |
| 4 | Websocket / gevent routing | Partially ready | Odoo bus needs gevent port proxied; config documented, proxy artifact pending. |
| 5 | HTTPS | Missing | No cert strategy shipped; local-CA / internal cert approach to be packaged (HTTPS.md). |
| 6 | Workers | Partially ready | `--workers` configurable; Edge default worker/cron policy to be fixed in the unit file. |
| 7 | Cron | Ready | Mezze crons (outbox, nonce-gc) install with the module. |
| 8 | Filestore | Partially ready | Standard Odoo `data_dir`; Edge path + permissions to be set by installer. |
| 9 | Backup | Partially ready | `pg_dump -Fc` proven (RC1). Local+offsite two-tier Edge script pending (backup.md). |
| 10 | Restore | Ready | `pg_restore` proven with 0 row loss (RC1); re-verify on Edge hardware. |
| 11 | Local DNS / LAN discovery | Missing | Static IP + local hostname strategy to document; no Internet DNS dependency for LAN. |
| 12 | Printer integration | Partially ready | Outbox hardware-job path exists in code; **no printer certified** (needs real ESC/POS). |
| 13 | Cash drawer | Partially ready | Kick-on-authorized-cash logic exists; **no drawer certified** (needs real device). |
| 14 | KDS | Ready (logic) | KDS model + UI proven in suite; on-device certification pending. |
| 15 | Waiter tablet | Partially ready | Responsive/RTL UI present; **1024×768 physical tablet not certified**. |
| 16 | Cashier | Ready (logic) | Payment/session flows proven in suite; hardware-station cert pending. |
| 17 | Customer display | Ready (logic) | `cfd.html` served; on-device cert pending. |
| 18 | Barcode scanner | Untested | HID-keyboard scanners generally work; not certified. |
| 19 | Session recovery | Ready | Native POS session lifecycle; close blocks on unresolved payments. |
| 20 | WAN-loss behavior | Partially ready | Local-authoritative DB design holds; explicit WAN status model not yet built (§8). |
| 21 | Restart behavior | Missing | systemd auto-start ordering (PG→Odoo→proxy) to be packaged + tested. |
| 22 | Shutdown behavior | Missing | Clean-shutdown policy to document (UPS.md). |
| 23 | Power-loss recovery | Partially ready | PostgreSQL is crash-safe; whole-stack recovery not yet tested on Edge hardware. |
| 24 | Monitoring | Missing | Health endpoint exists (`/mezze/api/v1/health`); Edge monitoring/alerts pending. |
| 25 | Log rotation | Missing | logrotate policy to ship with the installer. |
| 26 | Disk monitoring | Missing | Edge disk check to add to the validator (§25). |
| 27 | Clock sync | Missing | NTP/chrony requirement to document + validate. |
| 28 | Configuration validation | Ready | `mezze.golive.validator` (16 checks) exists; Edge profile to extend (§25). |
| 29 | Local admin access | Ready | Odoo backend + Admin Console; human-principal auth. |
| 30 | Installer | Missing | No `mezze-edge install` yet; approach documented (installation.md). |
| 31 | Upgrade process | Partially ready | `-u` idempotent + migrations proven; Edge upgrade+rollback runbook pending (upgrades.md). |
| 32 | Uninstall / data-export | Partially ready | `pg_dump` export works; documented uninstall flow pending. |

## Summary
- **Software/logic layer:** largely **Ready** (RC3: 229 tests green, fresh-install catalog, reconciliation 0, backup/restore proven).
- **Deployment/packaging layer:** mostly **Missing/Partially ready** — installer, reverse proxy, HTTPS, systemd auto-start, log rotation, monitoring, WAN status model are the engineering build-out for Edge v1.
- **Physical/hardware layer:** **NOT certified** — no printer/drawer/tablet/KDS device on this host; all hardware gates are on-hardware steps (see certification-report.md).
