# TEST TRUTH (forensic — executed evidence only)

Audit date 2026-08-05. HEAD `5ec05b1`. Config: addons-path `odoo/odoo/addons,odoo/addons,mezze/addons`
(clean community path — NO `enterprise2`, which auto-installs the buggy `pos_settle_due`).

## Executed this audit (authoritative)
| Run | Command | Result |
|---|---|---|
| Fresh install | `-i mezze_bridge --without-demo=all --test-enable --test-tags mezze_runtime,mezze_invariants --stop-after-init` | **0 failed, 0 error(s) of 405 tests · INSTALL_EXIT=0** · wall 4:34 · RSS 520MB |
| Upgrade | `-u mezze_bridge …same tags` on the freshly-installed DB | **0 failed, 0 error(s) of 405 tests · UPGRADE_EXIT=0** |
| Settings catalog | materialised on install | **101 defs** (asserted len==101) — **18 working / 76 disabled / 7 hidden** |

**Current suite = 405 Python test methods** (was 403 at rc1/rc3; +2 from the P3B.5 structural test). Every
doc in the repo still says 403 → stale (see STALE-DOCS-AND-CONFLICTS).

## Test LAYERS actually present (nothing else runs)
| Layer | Files | Executed by standard suite? | What it proves |
|---|---|---|---|
| Python invariant (`TransactionCase`) | ~30 | YES (mezze_invariants) | ORM/business-logic + money/FSM/crypto/authz invariants, in-process |
| Server-side HTTP (`HttpCase`) | ~30 | YES (mezze_runtime) | real HTTP POST/GET to `/mezze/api/…` controllers — **no browser/DOM** |
| Python source-grep "structural" | 7 (`test_floor_delivery_status_map`, `test_reservation_settings_status_map`, `test_kds_migration`, `test_p61_structural`, `test_p52_migration`, `test_route_scope`, `test_endpoint_coverage`) | YES (mezze_invariants) | assert **source text** (regex over pos.html/mezze-design.js/controllers) — do NOT render UI |
| HOOT / static JS unit | 1 (`static/tests/cashier_logic.test.js`) | **NO** — wired only into `web.assets_unit_tests`, no runner triggers it here | pure cashier logic (change/idempotency), not rendered UI |
| Authenticated browser (`browser_js`/tours) | **0** | — | **NONE EXIST** — zero `browser_js`/`start_tour`, no `tours/` dir |

## Hard conclusions
- **There is NO executed frontend/browser test anywhere.** All green evidence is server-side Python +
  source-grep. Authenticated-browser evidence = **MISSING** (item N answer). The Owl production cashier
  is **not exercised by any rendering test**.
- Every "browser-verified"/"live-measured" claim in the design docs (incl. this session's P3B passes) is
  **manual, one-off, on the `pos.html` PROTOTYPE**, not reproducible from the suite, and not on the
  production cashier.
- `browser_js` IS available in Odoo 19 (`HttpCase.browser_js`) — the project simply has no such test and
  no fixture wired to add one without code change → audit does not add it.
