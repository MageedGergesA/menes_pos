# RC7 — Deployment evidence

## Module upgrade

Run from the detached RC7 worktree against `mezze_pilot_rc7`.

| Check | Result |
|---|---|
| Exit code | **0** |
| `ERROR` lines | 0 |
| `CRITICAL` lines | 0 |
| XML / parse errors | 0 |
| View errors | 0 |
| Asset / bundle errors | 0 |
| i18n errors | 0 (the one i18n line is the INFO "loading translation file … ar.po") |
| Registry errors | 0 (the `odoo.registry` hits are INFO lines) |
| `Traceback (most recent call last)` | **0** |
| WARNINGs | 3 — all `Model attribute '_sql_constraints' is no longer supported` |

The three deprecation warnings are **pre-existing**, not RC7: the RC6 upgrade log
(`mezze-rc6-pilot-runtime/log/upgrade-rc6.log`) contains exactly the same three.

## Data integrity — 27/27 counters identical across the upgrade

companies 1 · active_users 6 · pos_configs 1 · pos_sessions 1 · pos_orders 8 ·
products 17 · products_in_pos 15 · pos_categories 4 · floors 1 · tables 12 ·
payment_methods 2 · taxes 4 · pricelists 0 · partners 10 · attachments 528 ·
attach_with_store_fname 527 · ir_model_data(mezze_bridge) 1164 · ir_config_parameters 24 ·
ir_ui_views(mezze_bridge) 4 · mezze_terminal 11 · mezze_reservation 1 · mezze_waitlist 0 ·
mezze_delivery_zone 0 · mezze_courier 0 · translations_ar 1

Filestore **447 → 447** files. Module version held at `19.0.2.7.0` (no schema or data
migration ships in RC7). **Unexpected data loss: 0.**

## Runtime topology

| | Shadow | Canonical |
|---|---|---|
| HTTP | 8092 | **8090** |
| Gevent | 8093 | **8091** |
| Workers | 4 | 4 |
| DB | `mezze_pilot_rc7` | `mezze_pilot_rc7` |
| `dbfilter` | `^mezze_pilot_rc7$` | `^mezze_pilot_rc7$` |
| `list_db` | False | False |
| data_dir | `~/.local/share/Odoo` | `~/.local/share/Odoo` |
| addons | `…/mezze-rc7-pilot/addons` | `…/mezze-rc7-pilot/addons` |

Shadow ports were proven free before binding. RC6 kept serving `:8090` throughout the
entire shadow validation and was stopped only after every shadow gate passed.
Database listing is not exposed: `/web/database/list` returns `AccessDenied` and the
selector page leaks no database names.

## RC6 security fix (DEFECT-01) — preserved

`api_security` is unset in the database, so the **shipped default `enforce`** applies
(`get_param('mezze_bridge.api_security') or 'enforce'`).

Two fully independent client sessions (separate cookie jars ⇒ separate `mezze_rid`
HttpOnly cookies), tokens taken from the page the server actually rendered and replayed
against the token-gated API. **22/22 checks PASS**, on shadow, after shadow restart, on
canonical, and after canonical restart:

- A boots → A 200; B boots → **A still 200** (the RC5 regression) and B 200
- A distinct `rid` from B
- A reload → A 200 and B 200; B reload → B 200 and A 200
- Register + Floor on one config, both directions, both stay valid
- one profile opening Register then Floor keeps a single stable `rid`
- 25/25 and 25/25 authenticated API calls

**4 distinct worker PIDs** served the 130 logged bootstrap requests — no process-local
identity dependency.

## Restarts

Shadow restart and canonical restart both produced entirely fresh PIDs and preserved:
release identity, database, filestore (447), 4 workers, full isolation suite, and the
restored Register shell.
