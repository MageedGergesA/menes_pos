# R-1 — Install / upgrade call graph

## BEFORE (defective on fresh install)
```
-i mezze_bridge --without-demo=all
  ├─ create schema (models)
  ├─ load manifest data:
  │     security/ir.model.access.csv
  │     data/nonce_gc_cron.xml
  │     data/outbox_cron.xml          ← NO catalog seed
  └─ post_init_hook: post_init_generate_token   ← API token only
  ⇒ mezze.setting.def = 0                         ← DEFECT (R-1)

-u mezze_bridge
  ├─ pre-migrations
  ├─ load manifest data (same as above)
  └─ post-migrations:
        19.0.1.3.0 → seed_catalog()
        19.0.1.4.0 → seed_catalog()
        19.0.1.6.0 → seed_catalog() + MIGRATION_MAP rename
  ⇒ mezze.setting.def = 101                        ← only via migration
```

## AFTER (catalog part of install; migrations still own history)
```
-i mezze_bridge --without-demo=all
  ├─ create schema
  ├─ load manifest data:
  │     security/ir.model.access.csv
  │     data/nonce_gc_cron.xml
  │     data/outbox_cron.xml
  │     data/settings_catalog_bootstrap.xml
  │        └─ <function model="mezze.setting.def"
  │                     name="_bootstrap_authoritative_catalog"/>
  │              └─ seed_catalog(prune=False)   ← upsert 101, no destructive prune
  │                    └─ domain/settings_catalog.py :: CATALOG_101
  └─ post_init_hook: post_init_generate_token
  ⇒ mezze.setting.def = 101 (18 working / 76 disabled / 7 hidden)   ← FIXED

-u mezze_bridge
  ├─ pre-migrations
  ├─ load manifest data (incl. bootstrap → upsert, no prune)   ← idempotent, no dupes
  └─ post-migrations:
        19.0.1.x → seed_catalog(prune=True) + renames   ← history unchanged
  ⇒ mezze.setting.def = 101, overrides/templates/assignments preserved
```

## Single source of truth
`domain/settings_catalog.py :: CATALOG_101` is consumed by: the install bootstrap, migrations, the runtime
schema/effective API, the validator, and the tests. No catalog rows are duplicated into XML/CSV/JS/fixtures.

## Pruning policy (§7)
- **Bootstrap (install/normal data load):** `seed_catalog(prune=False)` — upsert only, never deletes.
- **Migration (upgrade):** `seed_catalog()` (prune=True default) — still prunes/renames known obsolete
  Mezze keys, because that is a historical transformation migrations own.
