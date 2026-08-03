# Mezze POS — Editions

Mezze ships in **two editions** built from the **same** `mezze_bridge` codebase.
The edition is detected at runtime from the deployment mode
(`mezze.productization.release_identity().edition`) and reported in `/admin/version`.

## Mezze Cloud

- **What it is:** Mezze-managed hosting of the custom `mezze_bridge` code on our
  infrastructure. This is **NOT** standard Odoo Online / Odoo.sh — Odoo's SaaS does
  not allow arbitrary custom addons, so Mezze Cloud is our own managed deployment
  of the Community stack + `mezze_bridge`.
- **Backups:** managed by Mezze (Cloud-side scheduled `pg_dump` + filestore + offsite).
- **Updates:** rolled out by Mezze on the stable/rc channel.
- **Connectivity:** requires WAN. A WAN outage means the branch is offline.
- **Best for:** single or multi-branch operators who want zero on-site ops.

## Mezze Edge

- **What it is:** a branch-local install of Odoo Community + PostgreSQL +
  `mezze_bridge` on hardware **at the restaurant**, behind an nginx reverse proxy.
- **Offline survival:** the LAN keeps taking orders, firing KDS, and printing
  **through a WAN outage** — the branch does not depend on the internet to sell.
  Online-only features (aggregator callbacks, online customer payment, cross-branch
  reporting) resume when WAN returns.
- **Backups:** local scheduled backups on the box + optional offsite rsync
  (`deploy/edge/backup.sh`); restore via `deploy/edge/restore.sh` (RTO≈14s recorded).
- **Updates:** `deploy/edge/upgrade.sh` (mandatory backup → module `-u` → validate).
- **Certified platform:** Ubuntu Server 24.04 LTS x86-64.
- **Best for:** high-volume or unreliable-connectivity sites that must never stop selling.

## Cloud vs Edge — capability matrix

| Capability | Mezze Cloud | Mezze Edge |
|---|---|---|
| Counter / dine-in / KDS / payments | ✅ | ✅ |
| Customer QR / kiosk / pickup / delivery | ✅ | ✅ (online steps need WAN) |
| **Survives WAN outage (keep selling on LAN)** | ❌ (needs WAN) | ✅ |
| Online customer payment (Paymob etc.) | ✅ (WAN) | ✅ when WAN up |
| Aggregator webhooks (Talabat-style) | ✅ | ✅ when WAN up |
| Cross-branch consolidated reporting | ✅ real-time | ⚠️ per-branch; consolidation when connected |
| Cross-branch customer credit | ✅ | ⚠️ NOT real-time across branches |
| Backups | Managed by Mezze | Local + offsite on the box |
| Updates | Mezze-managed rollout | Operator runs `upgrade.sh` (backup-gated) |
| Physical hardware (printer/drawer/terminal) | PHYSICAL CERT PENDING | PHYSICAL CERT PENDING |
| Host/OS responsibility | Mezze | Operator (Ubuntu 24.04) |

Run `/admin/golive` with the **`edge`** profile on an Edge box (adds host/Postgres/
proxy/WAN checks); use a commercial profile (`counter`/`restaurant`/`delivery`/`full`)
on either edition to check the business format is fully configured.
