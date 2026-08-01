# R-1 — Root cause: settings catalog absent on fresh install

## Symptom
```
fresh empty DB → -i mezze_bridge --without-demo=all → mezze.setting.def count = 0
```
But `-u mezze_bridge` yields the full 101-setting catalog.

## Authoritative catalog (source of truth)
`domain/settings_catalog.py :: CATALOG_101` — 101 eight-tuples. Verified status split:
- total **101**, working **18**, disabled **76**, hidden **7** (counted from source, not hardcoded).

`models/config_platform.py` imports it and exposes `mezze.setting.def.seed_catalog()` — an idempotent
upsert-by-key (+ prune of non-catalog keys) that materialises the 101 rows.

## Why `-i` produced 0 rows
A fresh install runs only:
1. manifest `data` files — `security/ir.model.access.csv`, `data/nonce_gc_cron.xml`,
   `data/outbox_cron.xml`. **None seeds the catalog.**
2. `post_init_hook = post_init_generate_token` (`__init__.py`) — sets the API token only.

`seed_catalog()` is **never** invoked on install.

## Why `-u` produced 101 rows
Upgrade runs the migration scripts, three of which call `seed_catalog()`:
- `migrations/19.0.1.3.0/post-migration.py` → `seed_catalog()`
- `migrations/19.0.1.4.0/post-migration.py` → `seed_catalog()`
- `migrations/19.0.1.6.0/post-migration.py` → `seed_catalog()` + `MIGRATION_MAP` rename of override rows

So the catalog was, until now, a side effect of historical migrations — never part of install.

## Fix (narrow, install-only)
Add a manifest-loaded data file that invokes a thin idempotent bootstrap adapter over the existing
`seed_catalog()`, so a fresh install materialises the current authoritative catalog immediately. Migrations
remain responsible for historical transformations (renames, override migration). See `implementation.md`.
