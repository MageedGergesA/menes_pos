# Clean Installation (P1 §5)
**Prerequisites:** Odoo 19.0, PostgreSQL 14, Python 3.10, env var `MEZZE_MASTER_KEY` (base64 of 32 random bytes, NOT in DB or source), the addon on `addons_path`.
**Procedure (fresh DB):**
```
createdb mezze_pilot
MEZZE_MASTER_KEY=... odoo-bin -d mezze_pilot -i mezze_bridge --stop-after-init
```
**Post-install assertions:** module state=installed; `mezze.setting.def` count == 101; validator `run()` returns 0 FAIL.
**Classification:** the fresh-install *procedure* is documented and the install path is exercised on every `-u`/`-i` in CI; a from-empty-DB install on the pilot host is a release-owner step (this build reused the existing dev DB). No install-time errors in the current tree.
