# RC7 — Rollback procedure

Everything needed to return to RC6 is preserved. **Nothing was deleted.**

| Asset | Location | State |
|---|---|---|
| RC6 tag | `mezze-v1.0-rc6` → `e85be35c31a3ae285494f68ecc67aaed493fd687` | unmoved |
| RC6 worktree | `/home/mageed/odoo_work_19/mezze-rc6-pilot` | detached at RC6, clean |
| RC6 database | `mezze_pilot_rc6` (65 MB) | **not upgraded**, untouched |
| RC6 filestore | `~/.local/share/Odoo/filestore/mezze_pilot_rc6` | 447 files, untouched |
| RC6 runtime config | `mezze-rc6-pilot-runtime/conf/` | untouched (2 conf files) |
| RC6 evidence | branch `evidence/rc6-pilot` | untouched |
| Pre-RC7 backup | `mezze-rc7-pilot-backups/pre-rc7_…-173401.zip` | sha256 `3f96a20e…` |
| RC5 tag / worktree / DB / backups | as previously preserved | untouched |

## To roll back to RC6

1. Stop the canonical RC7 runtime (match only `odoo-mezze-rc7-pilot`, and exclude your
   own shell PID — a `pgrep -f` pattern that matches the calling shell will kill it):
   ```
   ps -eo pid,cmd | grep -F "odoo-mezze-rc7-pilot" | grep -v grep | awk '$1!=MYPID {print $1}' | xargs -r kill
   ```
2. Wait for `:8090` and `:8091` to be free (`ss -ltn`).
3. Start RC6 again — its config and database are already in place and were never
   modified:
   ```
   bash /home/mageed/odoo_work_19/mezze-rc6-pilot-runtime/start-rc6-pilot.sh
   ```
4. Confirm the runtime reports `product_version 1.0.0-rc.6` and
   `git_commit e85be35c31a3ae285494f68ecc67aaed493fd687`.

Because RC6 runs from its **own** database (`mezze_pilot_rc6`), rollback needs no
restore at all. The pre-RC7 backup exists as a second line of defence only.

## Do not

Do not delete `mezze_pilot_rc6`, its filestore, the RC6 worktree, the RC6 runtime
config, the pre-RC7 backup, or the RC5 assets until the RC7 physical pilot has been
executed and accepted.
