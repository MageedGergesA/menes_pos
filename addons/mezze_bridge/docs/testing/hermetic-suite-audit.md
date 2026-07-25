# Mezze test-suite hermeticity audit (RC2 / D-2)

Every test class, its base + fixture profile, and the ambient assumption removed. The suite now
provisions its own deterministic environment on a fresh `--without-demo=all` database.

## Removed ambient-discovery assumptions (root causes of D-2)
| Pattern (removed) | Where it failed on a clean DB | Replacement |
|---|---|---|
| `env['pos.config'].search([], limit=1)` | no config exists → `UserError: assign a PoS` | `self.pos_config` (fixture) |
| `env['pos.config'].search([], limit=2)` | ≤1 config → isolation tests aliased cfg1==cfg2 | `self.pos_config` + `self.make_second_pos_config()` |
| `env['pos.session'].search([('state','=','opened')], limit=1)` | reused a FOREIGN config's session → `ValidationError: another session already open` | `self.open_test_session()` (config-scoped) |
| `env['product.product'].search([...available_in_pos...], limit=1)` | no products on clean DB | `self.product` / `self.products` (fixture menu) |
| `c.payment_method_ids[:1]` on an ambient config | no payment methods | fixture config's methods / `self.cash_payment_method` |
| ambient restaurant tables | none on clean DB | `self.tables` / `self.floor` (RESTAURANT profile) |
| ambient aggregator channel | none on clean DB | `self.aggregator` (OMNICHANNEL) or a per-test channel with a test-only secret |

Stable Odoo core XML IDs still used (guaranteed by installed deps): `base.group_user`,
`base.user_admin`, `point_of_sale.group_pos_manager/group_pos_user`, currencies. **No demo XML IDs.**
Accounting (journals + accounts) comes from `AccountTestInvoicingCommon` (chart via
`try_loading(install_demo=False)`) — the canonical, dependency-guaranteed hermetic path.

## Base classes (tests/common.py)
- `MezzeTransactionCase` — light `TransactionCase` (no chart) — CORE / pure-domain.
- `MezzePosCase` — `AccountTestInvoicingCommon` + fixtures — POS/restaurant/omnichannel model tests.
- `MezzeHttpCase` — `AccountTestInvoicingCommon` + `HttpCase` + fixtures — real HTTP/controller tests.

## Per-class inventory (migrated files)
| File | Class | Base | Profile |
|---|---|---|---|
| test_runtime_o1 | TestPublicStatus | MezzePosCase | POS |
| test_runtime_o1 | TestShopStatusHttp | MezzeHttpCase | POS |
| test_runtime_o1 | TestAggregatorIdempotent | MezzeHttpCase | OMNICHANNEL |
| test_runtime_p1 | TestGoLiveValidator | MezzePosCase | POS |
| test_runtime_p1 | TestStatusTokenLifecycle | MezzePosCase | POS |
| test_runtime_refund | TestRefundLinkageRuntime / TestRefundModelConstraint | MezzePosCase | POS |
| test_runtime_guard | TestGuardRuntime | MezzePosCase | POS |
| test_runtime_guard | TestGuardHttp | MezzeHttpCase | POS |
| test_http_adoption | TestHttpAdoption | MezzeHttpCase | POS |
| test_runtime_objectscope | TestObjectScope | MezzeHttpCase | POS (2 configs) |
| test_runtime_adoption | TestOutboxAdoption | MezzePosCase | POS |
| test_runtime_emergency | TestEmergencyModel | MezzePosCase | POS |
| test_runtime_emergency | TestEmergencyHttp | MezzeHttpCase | POS (2 configs) |
| test_runtime_secrets | TestSecretEncryption | MezzePosCase | POS (own test-secret aggregator) |
| test_runtime_r1 | TestReservationLifecycle / TestWaitlistLifecycle | MezzePosCase | RESTAURANT |
| test_runtime_r1 | TestSeatOrderIdempotent / TestR11Acceptance | MezzeHttpCase | RESTAURANT |
| test_runtime_p61 | TestP61Model | MezzePosCase | POS |
| test_runtime_p61 | TestP61Http | MezzeHttpCase | POS (2 configs) |
| test_runtime_designplatform | TestCascade / TestDesignStructural | MezzeTransactionCase | CORE |
| test_runtime_designplatform | TestSettingsHttp / TestAdminHumanPrincipals | MezzeHttpCase | POS |
| test_runtime_security | TestSecurityRuntime / TestSecurityMultiCompany | MezzeHttpCase | POS (2 configs / Company B inline) |
| test_runtime_security | TestNonceGc | MezzeTransactionCase | CORE |
| test_runtime_p52 | TestP52Runtime | MezzePosCase | POS (own test-secret aggregator, 2 configs) |
| test_clean_database_bootstrap | TestCleanDatabaseBootstrap | MezzePosCase | FULL |
| test_fixture_isolation | TestNoArbitraryDiscovery | MezzeTransactionCase | CORE |
| test_fixture_isolation | TestFixtureIsolation | MezzePosCase | POS |

## Pure-domain files (unchanged — no POS/session/config/product dependency)
test_money_invariants, test_order_fsm, test_order_guard, test_guard_wiring, test_promotion,
test_rollback, test_refund_ceiling, test_authz, test_endpoint_coverage, test_outbox_policy,
test_runtime_outbox, test_runtime_outbox_concurrency, test_kds_migration, test_webhook_policy,
test_p52_migration, test_security_rollout, test_runtime_rollout, test_signing_policy,
test_runtime_p61 (structural part in test_p61_structural), test_crypto, test_route_scope,
test_runtime_ratelimit — these test `domain/` pure functions or module structure and require no ambient data.

## Accounting strategy (§4)
Chosen approach: **reuse `AccountTestInvoicingCommon`** (option 1 — minimal chart-template setup in the
fixture) rather than hand-rolling accounts. It is dependency-guaranteed, loads NO demo
(`install_demo=False`), and yields `company_data` with cash/bank/sale journals + receivable/revenue/
expense accounts. Payment methods, POS config, products, pricelist, taxes are layered on top by
`tests/factories.py`. CORE/pure-domain tests skip the chart entirely (performance).
