# RC6 PILOT — ROLLBACK TO RC5

RC5 is preserved intact. **Nothing was deleted during the RC6 cutover** — the RC5 tag,
worktree, database, backup and evidence all still exist, and RC5's database was never
upgraded in place.

**This procedure is documented, not performed.** Do not roll back unless RC6 shows a
genuine problem the operator decides to retreat from.

## What is preserved

| Artifact | Location | State |
|---|---|---|
| RC5 tag | `mezze-v1.0-rc5` → `4b0feb1e4794134d57466bc17e6dc2ea5f4080b6` | immutable, unmoved |
| RC5 worktree | `/home/mageed/odoo_work_19/mezze-rc5-pilot` | detached at RC5, clean |
| RC5 config | `mezze-rc5-pilot-runtime/conf/odoo-mezze-rc5-pilot.conf` | never edited |
| RC5 start script | `mezze-rc5-pilot-runtime/start-pilot.sh` | intact |
| RC5 database | `mezze_pilot_rc5` | **module 19.0.2.7.0, 2 terminals — not upgraded** |
| RC5 filestore | `filestore/mezze_pilot_rc5` | intact |
| RC5 pre-cutover backup | `mezze_pilot_rc5_PRE-RC6-CUTOVER_20260812-102327.zip` (SHA-256 `e04c53d5…`) | retained |
| RC5 evidence | `docs/pilot/evidence/rc5/` | unaltered |

## Procedure

```bash
# 1. stop the canonical RC6 pilot (and only it)
kill "$(ps -eo pid,cmd | grep -F 'odoo-mezze-rc6-pilot.conf' | grep -v grep | awk 'NR==1{print $1}')"
until ! ss -ltn | grep -q ':8090 '; do sleep 1; done

# 2. confirm the canonical ports are free
ss -ltn | grep -E ':(8090|8091) '     # expect no output

# 3. start RC5 again — its config and database are untouched
nohup bash /home/mageed/odoo_work_19/mezze-rc5-pilot-runtime/start-pilot.sh \
      > /home/mageed/odoo_work_19/mezze-rc5-pilot-runtime/log/stdout.log 2>&1 &

# 4. verify you are back on RC5
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8090/web/login     # expect 200
git -C /home/mageed/odoo_work_19/mezze-rc5-pilot describe --tags --exact-match HEAD
#   expect: mezze-v1.0-rc5
#   and release_identity() should report git_commit 4b0feb1e…  (product_version will
#   read the stale 1.0.0-rc.1 — that is RC5 DEFECT-02, expected on a rollback)
```

Rolling back restores **RC5 behaviour, including DEFECT-01**: two Register clients on one
POS config will evict each other again. Accept that consciously.

## If instead the RC6 database must be discarded but RC6 code kept

Restore the pre-cutover artifact into a fresh database and re-upgrade with RC6 code:

```bash
odoo-bin db -c <rc6 conf> --db_host=/var/run/postgresql -r odoo -w odoo \
        load mezze_pilot_rc6_retry \
        /home/mageed/odoo_work_19/mezze-rc5-pilot-backups/mezze_pilot_rc5_PRE-RC6-CUTOVER_20260812-102327.zip
odoo-bin -c <rc6 conf> -d mezze_pilot_rc6_retry -u mezze_bridge --stop-after-init
```

Never restore over a live database, and never `--no-filestore`.

## Retention

Keep every artifact above **until RC6 pilot preparation is formally accepted** by the
operator. Only then consider reclaiming the RC5 database and worktree — and even then, keep
the backup and the evidence directories.
