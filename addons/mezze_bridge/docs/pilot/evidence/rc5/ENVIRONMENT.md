# RC5 PILOT — ENVIRONMENT

| | |
|---|---|
| OS / kernel | Ubuntu 22.04.5 LTS / 6.8.0-136-generic |
| CPU | 12 cores |
| RAM | 15 GiB total; **~3.9 GiB available** at sizing time |
| Disk | 234 G on `/dev/nvme0n1p2`, **92 % used, 19 G free** |
| Python | 3.12.13 (`/home/mageed/odoo_work_19/venv_19`) |
| Odoo | Server 19.0 |
| PostgreSQL | server cluster **14** on port 5432 (client binaries 18.4) |
| Nginx | 1.18.0 installed; **not** fronting the pilot |
| Chrome | 151.0.7922.75 |
| Network | `wlo1 192.168.8.181/24`, gateway `192.168.8.1` |

## Paths

```
pilot code      /home/mageed/odoo_work_19/mezze-rc5-pilot            (detached @ mezze-v1.0-rc5)
pilot config    /home/mageed/odoo_work_19/mezze-rc5-pilot-runtime/conf/odoo-mezze-rc5-pilot.conf
pilot logs      /home/mageed/odoo_work_19/mezze-rc5-pilot-runtime/log/pilot.log
start script    /home/mageed/odoo_work_19/mezze-rc5-pilot-runtime/start-pilot.sh
backups         /home/mageed/odoo_work_19/mezze-rc5-pilot-backups/
data_dir        /home/mageed/.local/share/Odoo
filestore       /home/mageed/.local/share/Odoo/filestore/mezze_pilot_rc5   (17 MB, 430 files)
```

`data_dir` is shared with the other local instances **by design** — the filestore is
per-database, so there is no cross-contamination, and the pilot's filestore is its own
directory.

## Secrets

Not reproduced in this evidence package. Stored with `0600` permissions:

```
conf/.masterkey               MEZZE_MASTER_KEY for the pilot runtime
conf/.pilot_credentials.json  role -> password for the 6 pilot logins
```

`db_password`, `admin_passwd`, the Mezze API token and all user passwords are deliberately
absent from every document here.

## Deployment style

This host runs Odoo instances as **user-space background processes**, not systemd units —
`systemctl list-units | grep odoo` returns nothing, and the pre-existing instances on
8071/8077/8728 follow the same pattern. The pilot therefore uses a dedicated config plus
`start-pilot.sh`, matching the established local pattern. **No systemd unit was created**
and no existing service was modified.

## Not touched

* `mezze_dev` (8071) and its database — read-only source, still running
* `bft_ui` (8077), `mho` (8728) — untouched
* test/verification ports 8074 and 8088 — deliberately not reused
* the development checkout `/home/mageed/odoo_work_19/mezze` — never switched
