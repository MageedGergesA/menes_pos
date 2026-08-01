# R-1 — Implementation

## Mechanism (normal Odoo module data loading — no post_init hook)
A manifest-registered data file invokes an idempotent model bootstrap that delegates to the existing
canonical seed. No `post_init_hook` was added — normal `<function>` data-loading safely reaches the seed
service, so the convenience hook was unnecessary (spec §4).

```
data/settings_catalog_bootstrap.xml
   <function model="mezze.setting.def" name="_bootstrap_authoritative_catalog"/>
         │
         ▼
mezze.setting.def._bootstrap_authoritative_catalog()   (models/config_platform.py)
         │  thin adapter, upsert-only
         ▼
mezze.setting.def.seed_catalog(prune=False)
         │  reads the single source of truth
         ▼
domain/settings_catalog.py :: CATALOG_101   (18 working / 76 disabled / 7 hidden)
```

## Files changed (production — narrow)
- `__manifest__.py` — version `19.0.1.8.0 → 19.0.1.9.0`; add `data/settings_catalog_bootstrap.xml`.
- `data/settings_catalog_bootstrap.xml` — NEW; single `<function>` call, no catalog rows duplicated.
- `models/config_platform.py` — `seed_catalog(prune=True)` gains an explicit `prune` flag (default True
  preserves migration behaviour); new thin `_bootstrap_authoritative_catalog()` adapter calls
  `seed_catalog(prune=False)`.
- `models/golive.py` — the `settings_catalog` validator check now derives the expected count from the
  catalog source, verifies key uniqueness + status validity, and FAILs on an empty catalog (was a bare
  WARNING). It no longer merely suppresses.

## Files changed (test/docs)
- `tests/test_settings_catalog_install.py` — NEW: install-provenance + representative-key + idempotency +
  no-prune tests (plain `TransactionCase`, no fixture seeding).
- `tests/common.py` — the ADMIN fixture component now ASSERTS the installed catalog instead of seeding it.
- `tests/test_runtime_designplatform.py` — three setUp `seed_catalog()` calls replaced by an assertion.
- `tests/__init__.py` — register the new test module.
- `docs/testing/r1-settings-bootstrap/` — this evidence pack.

## Single source of truth (§2)
`domain/settings_catalog.py :: CATALOG_101` remains the only catalog definition. Install bootstrap,
migrations, the runtime schema/effective API (`mezze.settings.catalog()/resolve()`), the validator, and
the tests all consume it. No rows duplicated into XML/CSV/JS/fixtures.

## Pruning policy (§7)
- Install / normal data-load → `_bootstrap_authoritative_catalog()` → `seed_catalog(prune=False)`:
  upsert-only, never deletes (cannot destroy an intermediate-migration or third-party key).
- Upgrade migrations → `seed_catalog()` (prune=True): still prune/rename known obsolete Mezze keys — a
  historical transformation migrations own. `migrations/19.0.1.{3,4,6}.0` are unchanged.

## External identities (§8)
`mezze.setting.def` records are created by the `<function>` call (not by XML `<record>` ids), so they carry
no `ir.model.data` external ids — verified 0 on a fresh install. The functional identity is the stable
`key` (unique constraint `mezze_setting_def_key_uniq`). No competing XML-id identity is introduced; nothing
in the codebase references a setting via an external id (all references use the `key`).

## post_init_hook (§4)
NOT used for the catalog. Reason it was unnecessary: the catalog seed has no dependency on records created
after module data-load (it reads only the in-code `CATALOG_101`), so an ordinary manifest `<function>`
data element executes it correctly on both install and update. The existing `post_init_generate_token`
hook (API token) is unchanged and unrelated.
