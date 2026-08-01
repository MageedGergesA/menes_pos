# R-1 — Fresh-Install Settings Catalog Bootstrap — FINAL REPORT

## 1. Executive verdict
**R-1 RESOLVED.** A bare `-i mezze_bridge --without-demo=all` now materialises the authoritative
101-setting catalog (18 working / 76 disabled / 7 hidden) from module installation — no upgrade, no tests,
no fixtures required. Change is a narrow production installation fix; RC1/RC2 unchanged; hermetic suite
229/229 green on two fresh DBs, after upgrade, on the canonical DB, and from a clean worktree.

## 2. Root cause
Fresh `-i` runs only the manifest `data` files + `post_init_generate_token` (API token); none seeded the
catalog. `seed_catalog()` was invoked exclusively by upgrade migrations
(`migrations/19.0.1.{3,4,6}.0`), so a fresh install had `mezze.setting.def` = 0. Details:
`root-cause.md`, `install-call-graph.md`.

## 3. Previous installation path
`-i` → schema → data(access CSV, 2 crons) → post_init(token) → **catalog EMPTY**. Catalog appeared only via
`-u` migrations.

## 4. New installation path
`-i` → schema → data(... + `data/settings_catalog_bootstrap.xml` →
`mezze.setting.def._bootstrap_authoritative_catalog()` → `seed_catalog(prune=False)` →
`domain/settings_catalog.py::CATALOG_101`) → post_init(token) → **catalog = 101**. Re-affirmed on every `-u`.

## 5. Files changed
Production: `__manifest__.py` (data file + version 1.8.0→1.9.0), `data/settings_catalog_bootstrap.xml` (new),
`models/config_platform.py` (prune flag + bootstrap adapter), `models/golive.py` (validator check).
Test/docs: `tests/test_settings_catalog_install.py` (new), `tests/common.py`,
`tests/test_runtime_designplatform.py`, `tests/__init__.py`, this evidence pack. No other production files.

## 6. Catalog bootstrap mechanism
Manifest `<function model="mezze.setting.def" name="_bootstrap_authoritative_catalog"/>` → idempotent thin
adapter → `seed_catalog(prune=False)`. Normal Odoo module-data loading; **no post_init hook** (unnecessary —
see §11 confirmations). `implementation.md`.

## 7. Canonical source-of-truth preservation
Single definition remains `domain/settings_catalog.py::CATALOG_101`, consumed by install/migrations/runtime
API/validator/tests. No rows duplicated into XML/CSV/JS/fixtures.

## 8. Install-only result
`-i mezze_bridge --without-demo=all --stop-after-init` (NO tests), DB `mezze_r1_install`: exit 0,
101 setting defs, 0 config-values, 0 ir.model.data external ids for setting defs (created by function, not
XML records), no demo. `install-only.txt`.

## 9. Exact setting counts
**total 101 · Working 18 · Disabled 76 · Hidden 7** · distinct keys 101 (unique). Representative keys
verified: app_mode/app_theme/app_density/ws_panel_side/gr_cols/cd_img/ac_dir = working; pf_virtual/ad_debug
= hidden.

## 10. Settings API result
On the fresh-install DB, `mezze.settings.catalog()` = 101 entries; `resolve(ctx)` returns
`{effective(101), provenance, locks, overrides}` with `app_mode='system'` (correct default). No test-side
seeding. `settings-api.txt`.

## 11. Admin Console result
Admin Console reads the same installed catalog; template/assignment/lock/bounded-policy/provenance flows
verified via `TestAdminHumanPrincipals`/`TestSettingsHttp`/`TestCascade` (28/28 focused run). Disabled
settings stay read-only, hidden not presented, terminal principals denied. `admin-console.txt`.

## 12. Validator result
Fresh-install `settings_catalog` check = **PASS** ("101/101 setting defs, keys unique, status valid"),
was WARNING pre-R-1. Now derives the expected count from the catalog and FAILs on an empty catalog rather
than suppressing. `validator.txt`.

## 13. First fresh DB result
`mezze_r1_b`: `-i --without-demo=all --test-tags /mezze_bridge`: exit 0, **0 failed / 0 error of 229**.
Post-run catalog 101/101 (no duplicate defs from fixtures). `first-fresh-db.txt`.

## 14. Second fresh DB result
`mezze_r1_c` (independent): exit 0, **0 failed / 0 error of 229**; catalog 101/101. Deterministic.
`second-fresh-db.txt`.

## 15. Upgrade result
`mezze_r1_upg` (clone of canonical + 4 seeded overrides free/bounded/locked + 4 templates), `-u`: 101 defs,
unique keys, overrides/templates/policies preserved, version → 19.0.1.9.0, 0 fatal. `upgrade.txt`.

## 16. Double-upgrade idempotency
Two consecutive `-u`: both exit 0; final state stable — 101 defs, 101 distinct, 4 overrides, 4 templates,
policy split unchanged. No duplicate defs, no drift. `double-upgrade.txt`.

## 17. Existing preference preservation
After upgrade: user override (app_mode/user), device override (app_density/device), org lock
(app_theme/organization), branch bounded (gr_cols/branch) all intact; templates intact.

## 18. Migration compatibility
Migration/structural tests green (TestKdsMigration, TestP52Migration, TestP61Structural, TestCascade) — the
install bootstrap does not interfere with MIGRATION_MAP / gridCols split / fallback logic. Fresh installs do
not run historical transformations; upgrades still do. `migration-compatibility.txt`.

## 19. Fixture-system adjustment
The D-2 ADMIN fixture component and three design-platform setUps no longer seed the catalog — they ASSERT
the module installed it. A new plain-`TransactionCase` test (`test_settings_catalog_install.py`) proves
install-provenance without any fixture. No environmental coupling reintroduced.

## 20. Canonical DB result
`mezze_test`: full suite exit 0, **0 failed / 0 error of 229**; catalog used, not reseeded. `canonical-db.txt`.

## 21. Clean-worktree result
Worktree at `bfd2f4c`: install-only → 101/18/76/7; full suite (DB `mezze_rc3_suite`) → **process exit 0, 0 failed / 0 error of 229 tests**, 128.2s, 151068 queries, final catalog 101/101. `clean-worktree.txt`.

## 22. Automated tests
**229 total** (225 D-2 + 4 new R-1: install-provenance ×2, bootstrap-idempotent, no-prune). Exit code 0.

## 23. Production diff boundary
Only manifest, one bootstrap XML, config_platform (seed service + adapter), golive (validator). Zero
controllers/payment/refund/POS/restaurant/KDS/auth/security/omnichannel/static/migrations changed.

## 24. Performance impact
The `<function>` bootstrap adds one idempotent upsert of ≤101 rows at install/upgrade time (negligible).
Suite duration unchanged in character (~99–130s / DB, chart-per-POS-class dominates, as in D-2); +4 tests.

## 25. Evidence
`docs/testing/r1-settings-bootstrap/`: root-cause, install-call-graph, implementation, install-only,
first/second-fresh-db, upgrade, double-upgrade, canonical-db, settings-api, admin-console, validator,
migration-compatibility, clean-worktree, final-report.

## 26. Commit
`bfd2f4c` — "fix: seed settings catalog on fresh install".

## 27. RC3 tag
`mezze-pilot-rc3` (annotated) → the release identity commit (implementation `bfd2f4c` + docs commit). RC1 `634d17e` and RC2 `13276b9` unchanged.

## 28. Remaining gaps
None for R-1. (Pre-existing, out of scope: D-1 drive-thru hard-gate; on-site hardware/tablet acceptance.)

## 29. Final go/no-go verdict
**GO — R-1 RESOLVED.** Every gate executed and passed: install-only (101/18/76/7), first & second fresh-DB suites (229/0/0), upgrade + double-upgrade (idempotent, preferences/templates/policies preserved), canonical DB (229/0/0), settings/admin + migration focused (28/0/0), clean-worktree install-only (101/18/76/7) and full suite (229/0/0). Validator settings_catalog=PASS. Production diff limited to the install/catalog/validator/version path. RC1/RC2 immutable. RC3 tags the tested code.
