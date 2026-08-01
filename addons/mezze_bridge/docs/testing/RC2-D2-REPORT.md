# RC2-D2 — Hermetic Self-Provisioning Test Base — FINAL REPORT

## 1. Executive verdict
D-2 is **RESOLVED**. The complete Mezze suite now provisions its own deterministic environment and passes
on a freshly created, empty, `--without-demo=all` database — no canonical pilot DB, no demo data, no manual
POS/session/product/payment provisioning. **Fresh-install non-negotiable command: exit 0, `0 failed,
0 error(s) of 225 tests`.** The change is test-only; no production behaviour changed. RC1 (`mezze-pilot-rc1`
→ `634d17e`) is untouched.

## 2. Root-cause inventory
The suite assumed ambient data that a fresh install does not create:
- `pos.config.search([], limit=1)` → no config → `UserError: assign a PoS`.
- `pos.config.search([], limit=2)` → isolation tests aliased one config to itself.
- `pos.session.search([('state','=','opened')], limit=1)` → reused a FOREIGN config's session →
  `ValidationError: another session already open`.
- `product.product.search([...available_in_pos...])` → no products on a clean DB.
- ambient payment methods / restaurant tables / aggregator channels → none on a clean DB.
- (revealed) the 101-setting catalog is seeded by MIGRATIONS, not by a fresh `-i` install — see §35.

## 3. Test files audited
All 36 `tests/test_*.py`. 15 needed migration (POS/session/config/product dependency); the rest are pure
`domain/` or structural tests needing no ambient data. Full per-class inventory in `hermetic-suite-audit.md`.

## 4. Assumptions removed
Every `search([], limit=1/2)` fixture selection, every global opened-session search, and every ambient
product/payment/table/aggregator lookup — replaced by explicit fixtures. A guard test
(`TestNoArbitraryDiscovery`) fails the build if any forbidden pattern returns.

## 5. Files changed
Modified (test-only): 15 test files + `tests/__init__.py`. New: `tests/common.py`, `tests/factories.py`,
`tests/profiles.py`, `tests/test_clean_database_bootstrap.py`, `tests/test_fixture_isolation.py`,
`tests/run_clean_database_suite.sh`, `docs/testing/hermetic-suite-audit.md`, this report.
**No production Python/controllers/models/views/security/data/migrations/static changed.**

## 6. Fixture architecture
`MezzeFixtureMixin` provisions per `fixture_profile`, binds explicit aliases, asserts integrity. Three
bases: `MezzeTransactionCase` (light, no chart — CORE/domain), `MezzePosCase`
(`AccountTestInvoicingCommon` + fixtures), `MezzeHttpCase` (`AccountTestInvoicingCommon` + `HttpCase`).

## 7. Fixture profiles
CORE, POS, PAYMENTS, RESTAURANT, KDS, OMNICHANNEL, ADMIN_GOVERNANCE, FULL — each a minimal component set;
a class pays only for what it declares.

## 8. Accounting provisioning
Reuses `AccountTestInvoicingCommon` (chart via `try_loading(install_demo=False)`) → `company_data`
journals (cash/bank/sale) + accounts (receivable/revenue/expense). No country chart forced; no demo.

## 9. POS configuration provisioning
`factories.make_pos_config` — fixture-owned config, explicit company, sale journal, payment methods,
pricelist. `make_second_pos_config` builds an independent config with its OWN cash/bank journals + methods
(cash methods cannot be shared, nor share a journal).

## 10. Payment-method provisioning
Cash + card(bank) + split-capable credit, wired to the supplied journals/accounts, explicitly assigned to
the config. Second configs get uniquely-labelled methods on fresh journals.

## 11. Menu/product provisioning
Deterministic 5-product menu (plain/taxed/modifiable/kitchen/86-item), `available_in_pos`, POS category,
a basic sale tax. Tests reference `self.product`/`self.products`, never a name search.

## 12. Restaurant provisioning
Restaurant-enabled config + 1 floor + 3 tables (`self.floor`, `self.tables`); reservation/waitlist created
against fixture tables.

## 13. KDS provisioning
`mezze.kds.ticket` created against fixture order/config/session (station, fire_uuid, course).

## 14. User/role provisioning
Deterministic host/server/cashier/kitchen/manager/admin/auditor users — unique logins, test passwords,
fixture company, POS groups. API user (`base.user_admin`) granted membership in the fixture company.

## 15. Omnichannel provisioning
`self.aggregator` (code `mezzeats`, test secret, product-map SKU `MZ-SKU-1`). HMAC-exact tests keep their
own known-secret channel (test-only secret, never production).

## 16. Settings/admin provisioning
The 101-setting catalog is seeded by the fixture (`seed_catalog()`) for ADMIN/FULL profiles and by the
settings/admin test classes' setUp — because a fresh install does not seed it (§35).

## 17. Session lifecycle fix
`open_test_session/get_test_session/close_test_session/assert_no_foreign_session/
create_order_in_test_session` — all operate ONLY on the fixture config; never select or close a foreign
session. Kills the "another session already open" class at the source.

## 18. Test classes migrated
15 files / ~30 classes (see `hermetic-suite-audit.md` for the per-class base + profile table).

## 19. Test-order coupling removed
No `test_NN_*` ordinal chains introduced; each method is independent (class fixtures in setUpClass,
per-method savepoints). Verified by running representative classes in isolation (§26).

## 20. Clean bootstrap test
`test_clean_database_bootstrap.py::TestCleanDatabaseBootstrap` (FULL) — company/users/config/payment/menu,
open session, order → payment → completed, reservation seating, KDS fire, pickup status token, 101-setting
catalog, go-live validator — all from fixtures, no canonical record.

## 21. Fixture-isolation tests
`test_fixture_isolation.py` — no-arbitrary-discovery guard, second-config independence, two-config session
isolation, payment-method company scoping, role distinctness, no-demo-XML-id.

## 22. Hermetic runner
`tests/run_clean_database_suite.sh` — env-driven (no absolute paths), unique temp DB, `-i --without-demo=all
--test-tags /mezze_bridge`, PIPESTATUS capture, masks the master key, drops the DB unless `KEEP_TEST_DB=1`,
non-zero on any failure.

## 23. First fresh-database result
`mezze_fresh_a`, `-i mezze_bridge --without-demo=all --test-tags /mezze_bridge`: **exit 0, 0 failed,
0 error(s) of 225 tests** (128.6s incl. install).

## 24. Second fresh-database result
`mezze_fresh_b`, independent empty DB, same fresh-install command: **exit 0, 0 failed, 0 error(s) of
225 tests**. Proves run A left no leaked state that a second clean run depended on.

## 25. Upgrade result
`mezze_upg`: fresh `-i --without-demo=all`, then `-u mezze_bridge --test-enable --test-tags /mezze_bridge`:
**exit 0, 0 failed, 0 error(s) of 225 tests**. The suite passes after a module upgrade.

## 26. Individual-class results
Each representative class run ALONE (`--test-tags :Class`) — proves no inter-class / test-order coupling.
All green: TestRefundLinkageRuntime (8), TestP52Runtime (18), TestReservationLifecycle (6),
TestSeatOrderIdempotent (3), TestSettingsHttp (5), TestAdminHumanPrincipals (5), TestShopStatusHttp (3),
TestAggregatorIdempotent (3), TestStatusTokenLifecycle (2), TestGoLiveValidator (2),
TestCleanDatabaseBootstrap (1), TestFixtureIsolation (5) — **0 failed / 0 error(s)** in every case.

## 27. Canonical-database result
`mezze_test` (the RC1 canonical provisioned DB), `--test-enable --test-tags /mezze_bridge`: **exit 0,
0 failed, 0 error(s) of 225 tests**. The migrated suite uses its own fixture-owned records; no ambient
POS/session record was required or modified. Previous behaviour preserved (218 originals still green +7 new).

## 28. Clean-worktree result
`git worktree add /tmp/mezze-rc2 13276b9` (RC2 commit), fresh `-i mezze_bridge --without-demo=all
--test-tags /mezze_bridge` from the worktree: **exit 0, 0 failed, 0 error(s) of 225 tests** (124.2s incl.
install). The RC2 commit is self-contained — the excluded `tests/concurrency/` + `CLAUDE.md` are absent and
nothing is missing; no uncommitted file is required.

## 29. Test count
Previous: 218 retained. New: +7 (1 bootstrap + 1 no-discovery guard + 5 fixture-isolation). **Total 225.**

## 30. Test exit code
Fresh clean database: **0**.

## 31. Runtime and query comparison
- RC1 canonical suite: 218 tests, ~17.9s.
- RC2 clean-DB suite: 225 tests, ~86–99s run (128.6s incl. fresh install), ~153k queries.
- RC2 canonical suite (`mezze_test`): 225 tests, ~90s (chart-per-class dominates; ambient data unused).
The increase is `AccountTestInvoicingCommon` loading a chart template once per POS test class (~20 classes)
— the correctness cost of hermetic accounting. Pure-domain classes stay on the light base (no chart).
Not an extreme/pathological slowdown; acceptable for a self-provisioning suite.

## 32. Production-code diff assertion
`git diff HEAD` touches only `tests/` + `docs/testing/`. Zero production Python, controllers, models,
views, security, data, static, or migration files changed. Fixtures never run outside test mode.

## 33. RC2 commit
`13276b94590435604454635d8fa4f7e7e0d90a91` — "test: make Mezze suite self-provisioning". Test-only;
`git diff --cached --check` clean; concurrency/report/production excluded.

## 34. RC2 tag
Annotated `mezze-pilot-rc2` → `13276b9`. **`mezze-pilot-rc1` (634d17e) is UNCHANGED** (verified). Not pushed
(branch/tag push remains the repository owner's action).

## 35. Remaining concrete gaps (separately-reported runtime finding — NOT part of D-2)
**FINDING R-1 (install completeness):** the 101-setting authoritative catalog (`mezze.setting.def`) is
seeded only by migration scripts (`migrations/19.0.1.{3,4,6}.0/post-migration.py`), NOT by the module's
`post_init` hook. A fresh `-i mezze_bridge` therefore has 0 setting defs until an upgrade or an explicit
`seed_catalog()` runs; the go-live validator reports `settings_catalog` as WARNING on a fresh install.
This is a runtime/install-completeness gap, reported separately per the increment rules and NOT fixed here
(the tests seed the catalog themselves). Recommended fix (separate change): call `seed_catalog()` from the
`post_init` hook so a fresh install is catalog-complete.

## 36. Final go/no-go verdict
**GO — D-2 is fully resolved.** Every Definition-of-Done gate is met: 218 previous tests retained (+7 new =
225); a blank no-demo database needs no manual business provisioning; the full suite passes on the first
clean DB, a second independent clean DB, after upgrade, per-class in isolation, on the canonical DB, and from
a clean RC2 worktree; no arbitrary POS/session/product/payment discovery remains; no test-order coupling; no
demo data required; no production behaviour changed; RC1 unchanged; RC2 tagged only after all gates passed.
One item is carried forward as a SEPARATE runtime finding (R-1, §35), not part of D-2.
