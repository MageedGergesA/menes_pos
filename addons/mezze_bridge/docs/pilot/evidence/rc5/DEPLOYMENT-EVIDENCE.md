# RC5 PHYSICAL-PILOT DEPLOYMENT EVIDENCE

Deployment of the immutable release candidate for physical-pilot execution.
**Preparation only — no physical gate was executed.**

| | |
|---|---|
| Tag | `mezze-v1.0-rc5` |
| Tag object | `60932a4c46f8ec7f9a33af3ad4b74f1dba79267a` |
| Peeled commit | `4b0feb1e4794134d57466bc17e6dc2ea5f4080b6` |
| Module | `mezze_bridge` |
| Module version (from `ir.module.module`) | **`19.0.2.7.0`** |
| Prepared | 2026-08-11 |

Local and remote tag refs were both re-verified before deployment and agree exactly.
RC4 (`cad16ae…`) was confirmed unmoved on both.

---

## 1. Immutable code checkout

A **detached** worktree was created from the tag — the development checkout was never
switched, and nothing was committed into the pilot tree.

```
/home/mageed/odoo_work_19/mezze-rc5-pilot
  HEAD                4b0feb1e4794134d57466bc17e6dc2ea5f4080b6
  git describe        mezze-v1.0-rc5   (exact match)
  git status          clean  (0 entries)
  git diff / --cached  0 / 0
```

## 2. Runtime identity — the hard gate

The runtime does **not** merely echo a configured string. `mezze_bridge.build_commit` is
**UNSET** in the pilot database, so `release_identity()` fell through to running
`git rev-parse HEAD` against the module tree it was actually imported from:

```json
{"product": "Mezze POS", "product_version": "1.0.0-rc.1", "edition": "Mezze Cloud",
 "deployment_mode": "cloud", "module": "mezze_bridge", "module_version": "19.0.2.7.0",
 "odoo_version": "19.0", "odoo_series": "19.0",
 "git_commit": "4b0feb1e4794134d57466bc17e6dc2ea5f4080b6",
 "release_channel": "rc", "build": "n/a", "neutralized": false,
 "env_profile": "development"}
```

Independently corroborated:

| Evidence | Value |
|---|---|
| `sys.modules['odoo.addons.mezze_bridge'].__file__` | `/home/mageed/odoo_work_19/mezze-rc5-pilot/addons/mezze_bridge/__init__.py` |
| `.pyc` written into the pilot worktree | 78 files, newest **21:44** (worktree created 21:37) |
| `.pyc` touched in the development checkout during the window | **0** |
| Module version in DB | `19.0.2.7.0` |

**Runtime identity: PASS.** Code path, git commit, exact tag and module version all agree.

## 3. Host

| | |
|---|---|
| OS / kernel | Ubuntu 22.04.5 LTS / 6.8.0-136-generic |
| CPU / RAM | 12 cores / 15 GiB total, **~3.9 GiB free at sizing time** |
| Disk | 234 G, **92 % used, 19 G free** |
| Python | 3.12.13 |
| Odoo | 19.0 |
| PostgreSQL | server cluster 14 on 5432 (client 18.4) |
| Nginx | 1.18.0 present, **not** proxying the pilot |

## 4. Ports

Live listeners were inspected before choosing; nothing was assumed free.

| Port | Owner | Action |
|---|---|---|
| 8071 | pre-existing `mezze_dev` | left running, untouched |
| 8077 | pre-existing `bft_ui` | untouched |
| 8728 | pre-existing `mho` | untouched |
| 8074 / 8088 | regression / browser-verification ports | deliberately **not** reused |
| **8090** | **pilot HTTP** | selected, verified free |
| **8091** | **pilot gevent / websocket** | selected, verified free |

## 5. Pilot database

| | |
|---|---|
| Source | `mezze_dev` (developer instance, module **19.0.2.2.0**) — used **read-only** |
| Why | the only hand-configured single-company restaurant (1 POS config, 1 floor, 12 tables, 15 POS products, 4 categories); cloning it exercises a genuine multi-version upgrade |
| Pilot DB | **`mezze_pilot_rc5`** (name was free; nothing overwritten) |
| Provenance | restored **from the backup**, not copied from the live source |
| Filestore | `/home/mageed/.local/share/Odoo/filestore/mezze_pilot_rc5` — 17 MB, **430 files** |

The source database and its filestore were never modified.

## 6. Isolation

| Control | Setting |
|---|---|
| `db_name` | `mezze_pilot_rc5` |
| `dbfilter` | `^mezze_pilot_rc5$` |
| `list_db` | `False` |
| Database names leaked at `/web/database/selector` | **0** (other local DBs invisible) |

## 7. Process model

Sized from **memory**, not a CPU formula: 12 cores were available but only ~3.9 GiB RAM
was free, so a `(cores*2)+1` worker count would have been reckless.

| | |
|---|---|
| workers | **4** |
| max_cron_threads | 2 |
| limit_memory_soft / hard | 700 MiB / 960 MiB |
| limit_time_cpu / real | 120 s / 240 s |
| processes observed | 10 |

Multi-worker was chosen deliberately so the pilot exercises the real
websocket/longpolling path (gevent 8091) that a single-process run would not.

## 8. Upgrade

```
-d mezze_pilot_rc5 -u mezze_bridge --stop-after-init
UPGRADE_EXIT = 0
```

| Error class | Count |
|---|---|
| ERROR / CRITICAL | **0** |
| Tracebacks | **0** |
| XML / view parse | **0** |
| Asset | **0** |
| i18n | **0** |
| Missing external IDs | **0** |
| Registry failures | **0** |

### Data integrity, before vs after

17 counters compared. **Business data: identical.**

```
companies 1 · users 1 · pos_config 1 · products_pos 15 · product_templates 17
pos_category 4 · floors 1 · tables 12 · payment_methods 2 · taxes 4
pricelists 0 · partners 5 · attachments 501 · attach_stored 500 · mezze_tables 44
```

Two deltas, both expected and explained:

| Delta | Explanation |
|---|---|
| `module_version` 19.0.2.2.0 → **19.0.2.7.0** | the upgrade under test |
| `mezze_xmlids` 1163 → **1164** | one new field definition, `ir.model.fields: field_pos_order__mezze_parked` — a schema addition introduced between 2.2.0 and 2.7.0, not a data change |

**Unexpected data loss: 0.**

## 9. Runtime

| Check | Result |
|---|---|
| Start | **PASS** — HTTP 200 on 8090, gevent listening on 8091 |
| Clean restart | **PASS** — same commit, same module path, same DB, same filestore (430 files), same ports; 0 tracebacks, no restart loop |
| Static customer surfaces (shop, QR, kiosk, courses, drive-thru, feedback, CFD, onboarding) | **200** (8/8) |
| Staff routes anonymous | **303 → login** (correct gating) |
| Cashier / Floor / KDS boot payload | `ok: true`, mount node present (3/3) |
| Live API after boot | `bootstrap` 200, `floors` 200, `kds/state` 200 |
| Workspace endpoints | `orders/list` 200, `reservations/list` 200, `waitlist/list` 200 |
| Cashier rendered in a real browser | **PASS** — real pilot data (Arabic Coffee, Fattoush, Hummus Beiruti, Mixed Grill, Shish Tawook…), branch "Mezze Dev", 4 nav destinations, 12 tiles, phase `menu` |
| Reservations workspace rendered | **PASS** — day segmented control, Reservations/Waitlist toggle, "+ New reservation" |

Two corrections to my own method, recorded so the evidence is not misread:

1. A DOM probe initially reported the Cashier as "not booted" while it was in fact fully
   rendered — the documented rAF freeze in a background tab. A screenshot flushed
   rendering and the app was there. **Screenshot before believing a negative DOM probe.**
2. An early `kds/board` 404 was **my wrong endpoint name**; the real route is `kds/state`,
   which returns 200. Not a defect.

Floor and KDS were confirmed by boot payload + live API, **not** by visual browser render —
the browser extension disconnected before that step. Stated rather than implied.

## 10. Backup

See `BACKUP-RESTORE-EVIDENCE.md`. Summary: full DB **+ filestore** zip, restore proved on a
throwaway database, **500/500 attachments resolved on disk**, verification copy destroyed,
backup retained.
