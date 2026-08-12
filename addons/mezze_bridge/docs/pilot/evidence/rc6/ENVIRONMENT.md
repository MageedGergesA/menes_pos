# RC6 PILOT — ENVIRONMENT

| | |
|---|---|
| OS / kernel | Ubuntu 22.04.5 LTS / 6.8.0-136-generic |
| CPU / RAM | 12 cores / 15 GiB |
| Python | 3.12.13 (`/home/mageed/odoo_work_19/venv_19`) |
| Odoo | 19.0 |
| PostgreSQL | server cluster 14 on 5432 |
| Network | `wlo1 192.168.8.181/24`, gateway `192.168.8.1` |

## Paths

```
pilot code      /home/mageed/odoo_work_19/mezze-rc6-pilot              (detached @ mezze-v1.0-rc6)
canonical conf  .../mezze-rc6-pilot-runtime/conf/odoo-mezze-rc6-pilot.conf
shadow conf     .../mezze-rc6-pilot-runtime/conf/odoo-mezze-rc6-shadow.conf   (validation only)
start script    .../mezze-rc6-pilot-runtime/start-rc6-pilot.sh
logs            .../mezze-rc6-pilot-runtime/log/pilot.log
database        mezze_pilot_rc6
filestore       /home/mageed/.local/share/Odoo/filestore/mezze_pilot_rc6   (18 MB, 446 files)
backups         /home/mageed/odoo_work_19/mezze-rc5-pilot-backups/
```

## Ports

| Port | Owner | Note |
|---|---|---|
| **8090** | **RC6 canonical pilot HTTP** | taken over from RC5 after it was stopped and the port verified free |
| **8091** | **RC6 canonical gevent / websocket** | |
| 8092 / 8093 | RC6 shadow (validation) | stopped after cutover |
| 8071 / 8077 / others | pre-existing unrelated instances | **never touched** |

## Process model

4 workers + 2 cron threads (8 processes observed), matching the pilot architecture so the
real websocket/longpolling path is exercised. Memory limits 700 MiB soft / 960 MiB hard,
CPU 120 s, real 240 s.

## Secrets

Not reproduced here. `0600`:

```
mezze-rc6-pilot-runtime/conf/.masterkey
mezze-rc6-pilot-runtime/conf/.pilot_credentials.json
```

No bearer token, DB password, master key or user password appears in any document in this
directory.

## Untouched

RC5 worktree · RC5 database · RC5 config · the development checkout · the pre-existing
Odoo instances on 8071/8077 and the `atmta_*` / `mho_*` databases.
