# Mezze POS — project brief

For an engineer joining with zero context. Written 2026-09-09 by reading the repository,
its 422 Markdown documents, `git log`, and the surviving Claude Code transcripts.

**Repository:** `/home/mageed/odoo_work_19/mezze` (git remote `git@github.com:MageedGergesA/menes_pos.git`, private)
**Addon:** exactly one — `addons/mezze_bridge`
**Branch read:** `feature/split-bill-v2` @ `f7af9a6` (2026-09-08), 196 commits ahead of `main`, working tree dirty
**Odoo tree it runs against:** `/home/mageed/odoo_work_19/odoo` (Odoo 19.0 Community)

Where a claim below could not be verified from source, it says `UNKNOWN`. Where a repository
document and the code disagree, the code wins and the disagreement is noted.

---

## 1. What this module does, in plain language

Mezze is a restaurant point-of-sale product built on Odoo 19 Community. It is **not** a
skin over Odoo's own POS client. It is an API-first platform: `mezze_bridge` publishes its
own versioned JSON HTTP API under `/mezze/api/v1/`, and its own browser front-ends speak
only that API. They never touch Odoo ORM-RPC or JSON-RPC.

Every write still lands in **native** Odoo records. Orders are created through
`pos.order.sync_from_ui`, so stock moves, pricelists, tax computation, loyalty and the
session-close journal entries are Odoo's, unmodified. There is no custom order model.
`addons/mezze_bridge/README.md` states this contract, and the code holds to it.

What a shift can actually do with it today: open a branch, ring a check with modifiers and
combos, hold and resume it, split it by item, route it to prep stations, show it on a
kitchen board, take cash and manually-recorded card tenders, comp or void with manager
approval, seat a reservation, work a waitlist, take kiosk / QR / storefront orders, run a
drive-thru lane, deliver with cash on delivery, and close the session through Odoo's
accounting.

What it cannot do: run offline, drive any real card terminal or cash machine, receive an
order from any named delivery aggregator, or purchase anything. Those limits are stated in
`addons/mezze_bridge/docs/customer/KNOWN-LIMITATIONS.md` and are honest.

The target market is MENA food and beverage. Arabic and right-to-left are first-class on
the customer-facing pages; the staff surfaces are close but not complete.

---

## 2. Odoo version, dependencies, and how it hooks into `point_of_sale`

### Manifest facts

Source: `addons/mezze_bridge/__manifest__.py`

| Field | Value |
| --- | --- |
| `name` | `Mezze Bridge API` |
| `version` | `19.0.5.5.0` |
| `category` | `Point of Sale` |
| `author` / `website` | Teklines / https://teklines.com |
| `license` | LGPL-3 |
| `application` | `False` |
| `auto_install` | `False` |
| `post_init_hook` | `post_init_generate_token` (defined in `addons/mezze_bridge/__init__.py:11`) |
| `external_dependencies` | Python `cryptography` |

Separately, a product identity string lives at
`addons/mezze_bridge/models/productization.py:24` as `MEZZE_PRODUCT_VERSION = '1.0.0-rc.7'`.
That is the number the running build reports about itself; it is not the manifest version
and the two are deliberately different things.

### `depends`

```
point_of_sale, pos_restaurant, stock, account, bus,
mrp, loyalty, payment_paymob, pos_online_payment, payment_demo
```

Two dependency notes worth knowing. `sms` is used by the campaign code but is **not** in
`depends`; it survives on its own `auto_install`. Egypt e-invoicing reads fields from
`l10n_eg_edi_eta`, which is also not a dependency.

### Where it touches `point_of_sale`

**Python model extensions** (`_inherit`), all in `addons/mezze_bridge/models/`:

| Model extended | File | What it adds |
| --- | --- | --- |
| `pos.order` | `pos_order.py:9` | channel, service mode, parked flag, fire snapshot, split-family columns, `mezze_revision`, public status token, cashier and terminal links |
| `pos.order.line` | `pos_order.py:208` | seat, `mezze_merged_from`, split origin link, refund-ceiling ORM backstop |
| `pos.order.line` | `modifier.py:145` | `mezze_modifier_ids` — the BE-010 structured modifier selection |
| `pos.order` | `mezze_online_payment.py:53` | online payment bridge |
| `pos.config` | `pos_config_policy.py:24` | branch policy flags, e.g. `mezze_servers_off_till` |
| `pos.payment.method` | `payment_platform.py:29`, `payment_reconciliation.py:29`, `mezze_customer_credit.py:32`, `mezze_online_payment.py:185` | device binding, settlement, customer credit, online |
| `pos.payment` | `payment_platform.py:198`, `payment_reconciliation.py:86` | tender key and reconciliation fields |
| `restaurant.table` | `restaurant_table.py:8` | live state overlay |
| `payment.transaction` | `mezze_online_payment.py:162` | POS order linkage |
| `res.partner` | `mezze_customer_credit.py:42` | house-account credit policy |
| `res.users` | `res_users.py:15` | branch scoping |
| `product.template` | `modifier.py:89` | `mezze_modifier_group_ids` |
| `product.tag` | `product_tag.py:19` | `mezze_is_dietary` |
| `ir.http` | `ir_http.py:31` | frontend translation registration + station shift enforcement in `_authenticate_explicit` |
| `ir.config_parameter` | `security_config.py:34` | security posture parameters |

**XML view inheritance** — only five, all narrow:

- `views/pos_order_views.xml:21,38` extend `point_of_sale.view_pos_pos_form`
- `views/pos_order_views.xml:75` extends `point_of_sale.view_pos_order_tree`
- `views/pos_order_views.xml:90` extends `point_of_sale.view_pos_order_filter`
- `views/modifier_views.xml:74` extends `product.product_template_form_view`

There is **no** override of the native POS client's JavaScript, no patch of a
`point_of_sale` Owl component, and no extension of `point_of_sale.assets_prod`. Mezze's
front-ends are separate applications. This is the single most important architectural fact
for anyone expecting a conventional `pos_*` module.

**The two reused seams**, per `addons/mezze_bridge/README.md`:

- *Read* — a curated `search_read` over the same field lists `pos.load.mixin` uses, returning
  a lean projection rather than the full `load_data` payload.
- *Write* — build the dict `pos.order.sync_from_ui` expects and call it. Idempotency
  piggybacks on the native `pos.order.uuid`.

**Transport**: 227 route decorators across `addons/mezze_bridge/controllers/`, of which 210
use Odoo 19's `type='json2'` bare-REST dispatcher. Auth split: 217 `auth='none'` (token in
the `X-Mezze-Token` header or in the JSON body), 8 `auth='user'`, 2 `auth='public'`.

---

## 3. File map — every file that matters

Paths are relative to `addons/mezze_bridge/` unless stated otherwise.

### Top level

| Path | Role |
| --- | --- |
| `__manifest__.py` | manifest, data list, and the four asset bundles (see §7) |
| `__init__.py` | imports + `post_init_generate_token` |
| `README.md` | API contract and curl walkthrough. **Stale** — documents 4 endpoints; there are 227 |
| `requirements.txt` | Python extras |
| `test_client.html` | dev harness, outside `static/`, served by nothing, referenced by nothing |
| `../../CLAUDE.md` (repo root) | git workflow rules for this project |

### Controllers — `controllers/` (17,445 lines, 227 routes)

| File | Lines | Routes | Role |
| --- | ---: | ---: | --- |
| `main.py` | 11538 | 114 | the bulk of the API: catalogue, orders, fire, tables, promo, loyalty, upsell, reports, and the `/mezze/design/pos` prototype launcher at line 4244 |
| `w1.py` | 706 | 17 | finance, GL, reversals, e-invoice |
| `split_bill.py` | 674 | 6 | Split Bill V2 state and commit |
| `sync.py` | 444 | 4 | edge ⇄ cloud sync server |
| `settings.py` | 444 | 15 | the configuration platform |
| `hardware.py` | 409 | 9 | ESC/POS printing, drawer |
| `station.py` | 404 | 7 | device enrolment, challenge, session |
| `aggregator.py` | 307 | 2 | generic HMAC webhook ingest |
| `checkout.py` | 265 | 5 | public order-status page, renders `mezze_bridge.checkout_status` |
| `drivethru.py` | 235 | 3 | lane board API |
| `cashmachine.py` | 194 | 5 | Glory orchestration |
| `terminal.py` | 193 | 5 | integrated card terminals |
| `payment.py` | 193 | 7 | tender breakdown, online payment |
| `customer.py` | 187 | 5 | guest search, create, credit |
| `cashier.py` | 179 | 1 | serves `/mezze/pos`, renders `mezze_bridge.cashier_page` |
| `tips.py` | 161 | 4 | tip pool endpoints (BE-008) |
| `ocb.py` | 155 | 4 | drive-thru order confirmation board |
| `qr.py` | 126 | 4 | table-QR guest ordering |
| `kds.py` | 113 | 1 | serves `/mezze/kds`, renders `mezze_bridge.kds_page` |
| `productization.py` | 111 | 6 | release identity, support bundle |
| `floor.py` | 110 | 1 | serves `/mezze/floor`, renders `mezze_bridge.floor_page` |
| `register_instance.py` | 107 | 0 | per-client terminal identity helper (the RC6 defect fix) |
| `launcher.py` | 101 | 1 | serves `/mezze/start`, renders `mezze_bridge.launcher_page` |
| `approval.py` | 45 | 0 | HMAC manager-approval helper |
| `edge.py` | 21 | 1 | edge connectivity probe |

### Models — `models/` (58 files, 72 `_name` declarations)

Grouped by what they are for. Every path below is `models/<file>`.

**Order and money.** `pos_order.py`, `cart_pricing.py` (the one canonical pre-fire pricer),
`mezze_payment.py` (dead — never read), `payment_platform.py`, `payment_reconciliation.py`,
`mezze_reversal.py`, `mezze_customer_credit.py`, `mezze_online_payment.py`,
`mezze_payment_qr.py`, `mezze_terminal_txn.py`, `terminal_stripe.py`, `glory_transport.py`,
`mezze_einvoice.py`.

**Kitchen and production.** `kds_ticket.py` (the KDS finite state machine — the
best-engineered component in the module per the feature inventory),
`kitchen_readiness.py` (batched readiness mixin), `ck_request.py` (central kitchen).

**Restaurant floor.** `restaurant_table.py`, `reservation.py`, `waitlist.py`,
`pos_config_policy.py`.

**Channels.** `delivery.py`, `mezze_courier.py`, `drivethru.py`, `ocb.py`, `aggregator.py`,
`campaign.py`, `feedback.py`.

**Menu.** `modifier.py` (BE-010 modifier groups and options), `product_tag.py`.

**People and security.** `mezze_cashier.py`, `attendance.py`, `tip_pool.py`,
`mezze_station.py`, `mezze_station_surface.py`, `mezze_terminal.py`, `res_users.py`,
`emergency_access.py`, `secret_store.py`, `security_config.py`, `rate_limit.py`,
`api_nonce.py`, `mezze_audit_log.py`, `ir_http.py`.

**Platform.** `outbox_event.py` (the transactional outbox), `outbox_consumers.py`,
`mezze_sync_outbox.py` (declared, **zero writers**), `mezze_sync_applied.py`,
`mezze_sync_log.py`, `config_platform.py` (the 7-scope settings platform),
`edge_connectivity.py`, `golive.py`, `onboarding.py`, `productization.py`,
`hardware.py`, `hardware_render.py`, `hw_job.py`, `loyalty_bootstrap.py`.

### Domain layer — `domain/` (pure logic, no ORM models)

`authz.py` (the one authorization gate: 32 capabilities × 16 roles), `route_scope.py`,
`order_fsm.py`, `order_guard.py`, `refund.py`, `discount.py`, `promotion.py`, `reward.py`,
`split_bill.py`, `modifiers.py`, `preparation.py`, `tip_pool.py`, `escpos.py`, `epos.py`,
`glory.py`, `scale.py`, `terminal_adapters.py`, `crypto.py`, `station_crypto.py`,
`signing_policy.py`, `rate_policy.py`, `redaction.py`, `webhook.py`, `outbox.py`,
`settings_catalog.py`, `station_routing.py`, `station_surface.py`, `aggregator_mapping.py`.

### Views — `views/`

| File | Contains |
| --- | --- |
| `cashier_templates.xml` | the three QWeb page shells: `cashier_page`, `kds_page`, `floor_page` |
| `launcher_templates.xml` | `launcher_page` — the branch chooser at `/mezze/start` |
| `checkout_templates.xml` | `checkout_status` — the public order tracker |
| `station_views.xml` | station list/form/search, shifts, enrol wizard, `Mezze Stations` menu |
| `mezze_backend_views.xml` | back-office lists for reservations, waitlist, delivery, zones, couriers, aggregators, campaigns, printers, scales, payment devices, audit log, under a `Mezze` menu root |
| `modifier_views.xml` | modifier group list/form + the `product.template` form extension |
| `pos_order_views.xml` | the four `point_of_sale` view extensions |

### Data, security, migrations

`data/settings_catalog_bootstrap.xml` (seeds the settings catalogue on fresh install — the
R-1 fix), `data/mezze_dietary_tags.xml`, `data/nonce_gc_cron.xml`,
`data/outbox_cron.xml`, `data/station_surface_cron.xml`, `data/neutralize.sql`.
`security/ir.model.access.csv` and `security/mezze_station_security.xml`.
`wizard/station_enrol_wizard.py`.
`migrations/` holds ten post-migration scripts: `19.0.1.1.0`, `1.2.0`, `1.3.0`, `1.4.0`,
`1.6.0`, `2.8.0`, `3.2.0`, `3.3.0`, `3.4.0`, `5.5.0`.

### Front-end — `static/`

**Owl applications** (the production UI):

| Path | Role |
| --- | --- |
| `src/cashier/root.js` (5,977 lines) | the Register. Nineteen child components, workspaces, all order flow |
| `src/cashier/root.xml` (1,307 lines) | template `mezze_bridge.Root` |
| `src/cashier/order_store.js` (1,006 lines) | client cart state, line identity, favourites |
| `src/cashier/api.js` | the transport. Reused verbatim by KDS and Floor |
| `src/cashier/app.js` | mount point |
| `src/cashier/debug.js` | test handle, gated behind Odoo debug mode |
| `src/cashier/cash_machine_service.js`, `terminal_service.js`, `summary_panels.js` | tender services |
| `src/cashier/cashier.css` (1,507 lines) | the Register's own styles |
| `src/cashier/components/*.js|.xml` (21 components) | see §4 |
| `src/kds/root.js`, `store.js`, `app.js`, `components/ticket_card.*`, `kds.css` | the Kitchen Display |
| `src/floor/root.js`, `floor_store.js`, `app.js`, `floor.css` | the Floor / table map |
| `src/shell/rail.js|.xml|.css`, `appearance.js`, `icons.js` | the shared left rail, theme resolver, icon set |

**Shared design layer** — `static/design/`:

| File | Owns |
| --- | --- |
| `foundation.css` | `@font-face` for the four vendored typefaces + the `--mz-` primitive and semantic tokens. No colours |
| `components.css` | the canonical `.mz-btn` family — the single button source |
| `product-browser.css` | the catalogue grid and product card, shared by Register and drive-thru |
| `category-nav.css` | the category sidebar and its ≥1280px contract |
| `order-panel.css` | the 340px order column, line anatomy, totals, 62px primary action |
| `product-config.js` + `product-config.css` | the modifier/combo rules, as a plain script so the static drive-thru page can apply the same ones |
| `customer-config.js` | the customer-facing renderer of the same contract |
| `kiosk-v2.css`, `kiosk-v3.css`, `kiosk-v3-components.css`, `kiosk-v3-screens.css` | kiosk design generations |

**Theme registry** — `static/mezze-design.css` (329 lines): the 12-theme × 5-accent token
ramps. **Generated by `static/gen_design.py`. Do not hand-edit.**
`static/mezze-design.js`, `static/mezze-customer.css`, `static/mezze-customer.js`,
`static/mezze-connectivity.js` support the static pages.

**Static HTML pages** — served publicly at `/mezze_bridge/static/*.html`:

| File | Lines | Role |
| --- | ---: | --- |
| `pos.html` | 5,149 | **the design prototype, explicitly non-production.** Route `/mezze/design/pos` |
| `drivethru.html` | 1,848 | the drive-thru board, four modes |
| `kiosk-v3.html` | 1,291 | current kiosk generation |
| `kiosk.html` | 954 | the previously shipped kiosk |
| `shop.html` | 692 | storefront ordering |
| `qr.html` | 499 | table-QR guest ordering |
| `ocb.html` | 367 | drive-thru customer display |
| `kiosk-gallery.html` | 330 | kiosk component gallery |
| `courses.html` | 311 | waiter coursing — **served by no route and in no navigation** |
| `onboarding.html` | 222 | go-live console — **no controller route** |
| `cfd.html` | 219 | customer-facing display |
| `feedback.html` | 135 | guest rating |

**Fonts** — `static/fonts/`: Hanken Grotesk (Latin), IBM Plex Sans Arabic, JetBrains Mono,
and a Material Symbols Rounded subset. All OFL, licence in `static/fonts/OFL.txt`.

**Tests** — `tests/` (179 files, 2,088 test methods, 423 `browser_js` call sites) plus
`static/tests/cashier_logic.test.js` and `static/tests/kds_logic.test.js` (Hoot unit tests).
`tests/common.py` holds the hermetic self-provisioning fixtures and profiles.

### Documentation — 422 Markdown files, 3.1 MB

Read these first, in this order:

1. `docs/MEZZE_POS_FEATURE_INVENTORY.md` — 91 KB, dated 2026-08-21, the single most useful
   document in the repository. Evidence-based, code-over-docs, honest about what is broken.
2. `addons/mezze_bridge/docs/design-gap/GAP_REGISTER.md` — the **current** front of work.
3. `addons/mezze_bridge/docs/design-gap/SURFACE_LEDGER.md` — screen-by-screen: is there a UI,
   is there an engine.
4. `addons/mezze_bridge/docs/RUNBOOK.md` — how to start and test it.
5. `docs/MEZZE_VS_ODOO_POS_PARITY.md` — Mezze against native `point_of_sale` and its 35
   `pos_*` siblings.
6. `addons/mezze_bridge/docs/customer/KNOWN-LIMITATIONS.md` — the honest sales list.

Large clusters you will meet: `docs/design-audit/` (15), `docs/design-consistency/` (25),
`docs/design-truth-audit/` (16), `docs/project-truth-audit/` (13), `docs/design-final/` (12),
`docs/design-handoff/domain-docs/` (29 domain contracts), `docs/sell-ready/**` (~50),
`docs/go-live/**` (~40, mostly empty on-site evidence placeholders), `docs/customer/` (17),
`docs/drive_thru/` (22), `docs/kiosk/` (9).

Strategy and architecture documents — `docs/MEZZE_CONSTITUTION.md`, `docs/RFC-000/001/002`,
`docs/MEZZE_2035_CTO_VISION.md`, `docs/MEZZE_CEO_BUSINESS_PLAN.md`,
`docs/INVESTMENT_DUE_DILIGENCE.md`, `docs/GAPMODEL_VOL1..VOL6` — were written in a single
role-play sequence on 2026-07-22. They are visionary framing, not build instructions. Do not
treat their backlogs as commitments.

---

## 4. Current UI — what renders what, and where the styling lives

### The one fact that governs everything

There are two complete POS front-ends in this repository and only one is production.

| | Production | Not production |
| --- | --- | --- |
| What | 3 Owl apps + the static customer pages | `static/pos.html`, one 5,149-line file |
| Route | `/mezze/pos`, `/mezze/kds`, `/mezze/floor`, `/mezze/drivethru` | `/mezze/design/pos` |
| Self-declared | `views/cashier_templates.xml:4` "production cashier page" | `controllers/main.py:4244` prototype launcher |

`pos.html` is richer, more bilingual and more complete than the shipped Register. Several of
its most visible numbers are hardcoded literals. Never demo from it and never assume a
feature exists because it appears there.

### Rendered pages

| Route | Controller | QWeb template | Mounts |
| --- | --- | --- | --- |
| `/mezze/start` | `controllers/launcher.py:96` | `mezze_bridge.launcher_page` | server-rendered branch chooser |
| `/mezze/pos` | `controllers/cashier.py:174` | `mezze_bridge.cashier_page` | `#mezze-cashier-root` |
| `/mezze/kds` | `controllers/kds.py:109` | `mezze_bridge.kds_page` | `#mezze-kds-root` |
| `/mezze/floor` | `controllers/floor.py:105` | `mezze_bridge.floor_page` | `#mezze-floor-root` |
| `/checkout/s/<token>` | `controllers/checkout.py:244` | `mezze_bridge.checkout_status` | server-rendered |
| `/mezze/drivethru`, `/mezze/cfd`, `/mezze/courses`, `/mezze/ocb/<token>` | `controllers/drivethru.py`, `main.py`, `ocb.py` | none | serve static HTML |

Each of the three Owl page templates in `views/cashier_templates.xml` is a **full HTML
document** written in QWeb, not a fragment. It sets `lang`/`dir` from the user, stamps
`data-appearance="mezze"`, `data-mz-theme`, `data-mz-mode`, `data-mz-accent` on `<html>`,
seeds `var odoo = {debug: …}` before the module loader, runs an inline pre-paint theme
resolver, then calls `t-call-assets` twice — once with `t-js="false"` in `<head>` and once
with `t-css="false"` at the end of `<body>`. The boot payload is a
`<script type="application/json" id="mezze-boot">` element.

### Register component tree

`static/src/cashier/root.js:57-58`: template `mezze_bridge.Root`, children —

`ProductGrid`, `Cart`, `PaymentScreen`, `Receipt`, `CashMachine`, `Workspace`,
`SettingsPanel`, `WorkspaceRail`, `ManagerGate`, `DeliveryForm`, `ProductConfig`,
`SessionClose`, `TipPool`, `SplitBill`, `RefundScreen`, `EnterCodeScreen`, `Numpad`,
`CoursesScreen`, `ProductInfoScreen`.

Each has a paired `.js` and `.xml` in `static/src/cashier/components/`. The largest are
`payment_screen.xml` (440 lines), `cart.xml` (363), `split_bill.xml` (254),
`session_close.xml` (190).

`WorkspaceRail` lives in `static/src/shell/rail.xml` and is shared with KDS and Floor.
KDS renders `mezze_bridge.KdsRoot` with one child, `mezze_bridge.KdsTicketCard`.
Floor renders `mezze_bridge.FloorRoot` with no child components.

### Where styling lives — the cascade order

For the Owl apps the order is fixed by the bundle definition in `__manifest__.py` and it
matters:

1. `static/design/foundation.css` — fonts and non-colour tokens
2. `static/design/components.css` — `.mz-btn`
3. `static/design/product-browser.css`, `category-nav.css`, `order-panel.css`,
   `product-config.css` (cashier bundle only)
4. `static/mezze-design.css` — the theme and accent colour registry
5. `static/src/shell/**` then `static/src/cashier/**` (or `kds/**`, `floor/**`)

The shared files are loaded **before** the app's own CSS deliberately, so every later
cashier rule still wins as it did before extraction. Do not reorder them.

For the static HTML pages the same foundation arrives as a plain
`<link rel="stylesheet" href="design/foundation.css">` in `<head>`.
`addons/mezze_bridge/docs/design-consistency/ASSET-FOUNDATION-MAP.md` is the authority on
this split.

### Design authority

The primary visual authority is the frozen Claude Design prototype, now vendored in the repo
at `addons/mezze_bridge/docs/design-handoff/Mezze POS v3.dc.html` (39,526 lines, committed
2026-09-08 in `3334a34`) with 29 domain contracts beside it in
`docs/design-handoff/domain-docs/`. Tokens are in
`docs/design-handoff/ui-design/MEZZE_DESIGN_TOKENS.json` (untracked at time of writing).

An earlier authority — `~/Downloads/Mezze POS Visual Redesign/export`, 40 HTML spec files —
governs the colour system, typefaces and geometry and is cited throughout
`docs/design-consistency/`. It is **outside the repository**. Treat
`docs/DESIGN_SYSTEM.md` as a downstream translation; it carries its own authority-correction
banner.

---

## 5. Timeline of significant changes

384 commits, first on 2026-07-12, latest `f7af9a6` on 2026-09-08. Twelve tags:
`sprint-1-design-foundation`, `v2.0.0-rc1`, `mezze-pilot-rc1..rc3`, `mezze-v1.0-rc1..rc7`.

**Phase 1 — bridge and core loop (2026-07-10 → 07-16).** The JSON API, split-bill flow,
floor, refund, KDS state machine and waiter push wired to Odoo. Architecture settled early:
own API, native writes.

**Phase 2 — design system migration P1→P7 (2026-07-17 → 07-22).** Colour, typography, icons,
surface, motion, spacing, component library, each flag-gated under
`[data-appearance="mezze"]` with amber remaining the default. Records in
`docs/P1_MEZZE_COLOR_SYSTEM.md` through `docs/P7_VISUAL_CONVERGENCE_RELEASE.md`. Closed and
frozen, then followed by "Experience 3.0" phases 1–6
(`docs/EXP3_PHASE1_APP_SHELL.md`…`EXP3_PHASE6_LIVEOPS_AND_FINAL.md`).

**Phase 3 — the strategy interlude (2026-07-22).** One day of role-play prompts produced the
Constitution, RFC-000/001/002, the CTO vision, the CEO plan, the red-team memo, the
due-diligence report and the six-volume gap model. Large, ambitious, and almost entirely
uncoupled from the code that followed.

**Phase 4 — engineering hardening (2026-07-23 → 07-25).** Payment correctness, refund
ceilings in integer minor units, the lifecycle finite state machine, the transactional
outbox and dispatcher, the authorization gate, object scope, secret closure, multi-worker
proof. Ends at `mezze-pilot-rc1`.

**Phase 5 — test hermeticity and fresh-install correctness (2026-07-25 → 08-01).** RC2-D2
made the suite self-provisioning so it passes on `--without-demo=all`; R-1 fixed the settings
catalogue being empty on a fresh install. `mezze-pilot-rc2`, `rc3`.

**Phase 6 — sell-ready S1→S6 (2026-08-01 → 08-05).** Edge edition, the universal payments
platform in seven slices (S2C-1 through S2C-7, which is where the Owl cashier at `/mezze/pos`
was born), delivery v1, customer ordering and self-service, productization and onboarding,
then the physical-pilot pack. `mezze-v1.0-rc1`.

**Phase 7 — truth audits (2026-08-05 → 08-06).** `docs/project-truth-audit/` and
`docs/design-truth-audit/` were written to replace self-reported completion claims with
forensic reads of git, code and runtime. They corrected several earlier design result
documents.

**Phase 8 — pilot RCs (2026-08-11 → 08-12).** Final UI/UX certification F1–F11, then RC5,
RC6 (fixing a multi-Register token-eviction defect) and RC7 (Register fidelity restored from
34 to 85 out of 100 against the design export). All physical gates remain unexecuted.

**Phase 9 — drive-thru and convergence (2026-08-14 → 08-18).** DT-UX3 through DT-QA7 built
the lane, payment window, pickup handoff gate and vehicle finite state machine. Then the user
rejected the order-taker UI outright — "the current Drive-Thru Order Taker UI is not the
product I want" — and the CONV series rebuilt it as the Register in drive-thru mode. This is
where `design/product-browser.css`, `category-nav.css`, `order-panel.css` and
`product-config.js` were **extracted out of** `cashier.css` so two surfaces could share one
definition. Kiosk V2 landed in the same window. Mezze Station (a Windows client) began as
WS-0/WS-1 and lives in a separate repository at `/home/mageed/odoo_work_19/mezze-station`.

**Phase 10 — Split Bill V2 and the Odoo parity campaign (2026-08-19 → 08-26).** Split Bill V2
with durable family columns on `pos.order`, row locks and optimistic revisions. Then a long
campaign driven by `docs/MEZZE_VS_ODOO_POS_PARITY.md`, closing gaps against native POS until
Mezze matched or exceeded it. Branch currency, kiosk internationalisation, discount survival
through sync, browser-test stability (one browser per test) all landed here.

**Phase 11 — the design-gap campaign (2026-09-06 → today).** The current work. The frozen
prototype is being closed screen by screen against
`addons/mezze_bridge/docs/design-gap/GAP_REGISTER.md`. Landed so far: tip pooling
(BE-008, models plus a Register screen), structured modifier groups (BE-010, migrating off
product attributes, migration `19.0.5.5.0`), the locked rail, the stale-write revision guard
extended from one route to seven, the conflict banner, the guest panel, open-checks strip,
dietary filter, merged-line badge, and phone-number masking on the till.

**In flight, uncommitted right now** (18 modified files, 5 untracked): Screen 02, the Floor.
The map gains pan and zoom, tap-to-select instead of tap-to-navigate, a counting legend and a
320px side panel. Alongside it, an overlay z-index ordering fix so the manager-approval
prompt can never be covered by the modal that summoned it, and a screenshot capture harness
(`tests/test_zz_visual_capture.py`, tagged `mezze_capture`, excluded from the default run)
for pixel diffing against the prototype.

### Recurring themes across the past sessions

- **Prototype versus product.** The single most repeated friction. The user repeatedly asked
  why `/mezze/pos` did not look like `/mezze_bridge/static/pos.html`, and on 2026-09-08 asked
  outright whether the project should be restarted from scratch.
- **Screens exist, engines exist, they are not connected.** Recurs in every audit.
- **Browser tests are the flaky part.** A long thread of commits moved the suite to one
  browser per test and added launch retries.
- **Verification discipline.** Repeated instruction not to write another RFC, roadmap or
  audit but to change running code. Also a standing rule that any recommendation to rewrite a
  module must carry a technical justification and a reason refactoring is insufficient.
- **Negative controls.** The Screen 01 revision-guard work caught a vacuously passing test —
  it lived in a profile whose `floor_ids` was empty, so it skipped, and a skip read as a pass.

### Note on Step 4 of the request

The transcript directory named in the task, `~/.claude/projects/-home-mageed-odoo-work-19-mezze/`,
**does not exist**. The Mezze history is not lost — it is in
`~/.claude/projects/-home-mageed-odoo-work-19-odoo/`, because these sessions ran with the
working directory set to the Odoo tree rather than the Mezze repository. The two substantial
files are `c373d9b5-27fd-416d-91f0-ce34bcf14d42.jsonl` (207 MB, from 2026-07-09) and
`8eef5a4b-cd91-4876-a1b8-b30ff0e82f97.jsonl` (212 MB, from 2026-08-11), plus
`0a870232-…jsonl` and `2fa1eaf8-…jsonl` for the last three days. §5 is drawn from those.

---

## 6. Known issues, open TODOs, and what was rolled back

### Verified-current issues

- **`main.py` is 11,538 lines and holds 114 routes.** It is the module's centre of gravity
  and its largest single risk.
- **Two of three enforcement layers ship in observe mode.** Request signing and the
  order-lifecycle guard audit but do not block. Worse, three sources disagree on the shipped
  posture: `controllers/main.py:544` documents "default observe", `main.py:555` codes
  `or 'enforce'`, `models/golive.py:95` codes `or 'observe'`. Resolve this before trusting
  any security claim.
- **`README.md` in the addon is stale.** It documents four endpoints; there are 227.
- **`main` is 196 commits behind `feature/split-bill-v2`,** while `CLAUDE.md` states main is
  the source of truth. The rule and the repository disagree. Ask before merging.
- **No client-side offline capability.** Zero IndexedDB, zero service worker, zero queue.
  `mezze.sync.outbox` is declared with **zero writers**. The prototype's "works fully
  offline" banner is a false claim.
- **Realtime is polling.** KDS polls every 4 s, Floor refetches every 30 s, the Register
  subscribes to nothing.
- **Prep-station routing is a hardcoded English keyword matcher** with six fixed stations and
  no configuration surface. A hard blocker for an Arabic menu.
- **No real payment device has ever been exercised.** Card terminals and cash machines both
  resolve to a `test: simulatorAdapter` registry. The server refuses real providers rather
  than faking them, which is the right behaviour.
- **No aggregator vendor protocol exists.** What ships is a hardened generic HMAC webhook for
  a payload format Mezze invented.
- **Paymob transactions are orphaned** — no `pos_order_id`, so they never become a
  `pos.payment`.
- **Physical certification has not started.** Every directory under
  `docs/go-live/on-site-acceptance/` and `docs/sell-ready/edge/certification/` is a
  placeholder reading "NOT EXECUTED".
- **Unreachable screens:** `static/onboarding.html` has no controller route and needs the
  shared admin token that production disables; `static/courses.html` is served by no route;
  `static/cfd.html` is only pushed to by the prototype; `test_client.html` is dead.

### Issues the August inventory named that now appear closed — re-verify before quoting

`docs/MEZZE_POS_FEATURE_INVENTORY.md` closes by naming three defects that corrupt real
orders. Reading the code at `f7af9a6`, all three look addressed, but I did not run the tests:

- *Fire double-appends the cart* — `controllers/main.py:3084` now implements
  `_fire_order_delta` and `main.py:3290` takes a `reconcile` argument.
- *Line notes never persisted* — `main.py:1639-1640` writes `customer_note` on the line.
- *Recall strips line configuration* — `tests/test_draft_recovery.py` was added in `f7af9a6`.

Likewise, the inventory says refunds have no production UI; there is now a `RefundScreen`
component in the Register. And it says only four models have a backend view; there are now
back-office lists for twelve. **The inventory is dated 2026-08-21 and the module has moved
from 19.0.3.1.0 to 19.0.5.5.0 since. Trust it for architecture and judgement, verify it for
status.**

### Rolled back, rejected or abandoned

- **The drive-thru order taker, first version.** Rejected outright by the user on 2026-08-15
  for putting a 16-car monitoring board across 82% of the canvas. Replaced by the CONV series,
  which made the order taker the Register in drive-thru mode. Recorded in
  `docs/drive_thru/CASHIER-DRIVETHRU-CONVERGENCE-PLAN.md`.
- **Kiosk V1** — `docs/kiosk/KIOSK-EXPERIENCE.md` and
  `docs/kiosk/PRODUCT-CONFIGURATION.md` both carry a "SUPERSEDED by Kiosk V2" banner.
  `static/kiosk.html` still ships beside `static/kiosk-v3.html`.
- **A raw NUL byte as the line-key separator** — reverted to an escape in `3b071cf`.
- **Native Odoo `pos_self_order`** — audited and rejected; the native kiosk is Adyen and
  Stripe-terminal only. See `docs/sell-ready/customer-ordering/odoo-self-order-audit.md`.
- **Native Enterprise `pos.prep.*` for KDS** — audited and rejected in favour of
  `mezze.kds.ticket`. See `docs/project-truth-audit/KDS-REUSE-DECISION.md`.
- **The earlier design audit's premises** — `docs/design-consistency/PRECEDENCE-AND-CORRECTIONS.md`
  formally corrects `docs/design-audit/`, which had treated `docs/DESIGN_SYSTEM.md` and
  `pos.html` as authoritative.
- **Dead code, still present:** `models/mezze_payment.py` (`mezze.payment.provider` and
  `mezze.payment.transaction`, never read), `mezze.sync.outbox` / `.cursor` (zero writers),
  the `/orders/kds` route, the floor `bill` state, and the cart subtotal row in
  `components/cart.js` which reads a getter `OrderStore` does not define.

### TODO markers

Seven in the whole module. Zero FIXME, XXX or HACK. All seven are external-integration seams
(Egypt ETA, payment service providers, aggregator adapters).

### Open decisions someone must make

1. Merge `feature/split-bill-v2` into `main`, or redefine which branch is the trunk.
2. Resolve the observe-versus-enforce contradiction across the three files named above.
3. Whether `foundation.css` stays separate from `mezze-design.css` or is folded in
   (`docs/design-consistency/ASSET-FOUNDATION-MAP.md`, "Open architectural decision").
4. Masked versus full guest phone number on the till — ours masks, the frozen design shows
   it in full. A divergence from a frozen design needs a ruling, not a silent preference.
5. The 929 pixel literals in consumer CSS that are off the attested spacing scale
   (`docs/design-consistency/DESIGN-P3-TOKEN-LAYER-AUDIT.md`, untracked).

---

## 7. Constraints someone must know before changing the UI

### 1. Know which front-end you are editing

Three Owl apps under `static/src/`, one prototype at `static/pos.html`, and eight static
customer pages. Changing `pos.html` changes nothing a customer will ever run. Changing
`static/src/cashier/**` changes the till.

### 2. Asset bundles are custom and deliberately minimal

`__manifest__.py` declares four bundles: `mezze_bridge.assets_cashier`,
`mezze_bridge.assets_kds`, `mezze_bridge.assets_floor`, and the standard
`web.assets_unit_tests`. There is no contribution to `web.assets_backend`,
`web.assets_frontend` or `point_of_sale.assets_prod`.

Each app bundle contains only `web/static/src/module_loader.js`, Luxon, Owl, `env.js`,
`session.js`, `@web/core` JS and XML, with `emoji_data.js` removed. **The core components'
SCSS is deliberately excluded** because it assumes the full backend variable chain
(`$o-datetime-picker-width` and friends). Each app ships plain CSS instead. Do not add SCSS
to these bundles and do not add a `@web` import that drags the missing chain back in.

A new CSS or JS file under `static/src/cashier/`, `kds/` or `floor/` is picked up by the
existing `**/*` glob. A new file under `static/design/` must be added to each bundle
explicitly, in the right position.

### 3. Load order inside the bundle is load-bearing

Shared design files come **before** the app's own CSS so app rules keep winning. The manifest
comments say so at each entry. Reordering them will silently change specificity outcomes
across the whole Register.

### 4. `static/mezze-design.css` is generated

Header line 1: "GENERATED by gen_design.py. Do not hand-edit." Edit `static/gen_design.py`
and regenerate. This file owns the entire colour and theme registry.

### 5. The theme contract is a set of HTML attributes, not a class

Every surface resolves appearance the same way, before first paint, from
`?mzmode=` / `?mztheme=` / `?mzaccent=` then `localStorage['mzSettings.v1']` then
`prefers-color-scheme`, and stamps `data-theme`, `data-mz-mode`, `data-mz-theme`,
`data-mz-accent` on `<html>`. The colour ramps in `mezze-design.css` are keyed on
`:root[data-appearance="mezze"][data-mz-theme="…"]`. A rule that does not sit under that
selector chain will not theme. The inline resolver is duplicated verbatim in all three page
templates in `views/cashier_templates.xml`; change one and change all three.

### 6. The QWeb page templates are whole documents

`cashier_page`, `kds_page` and `floor_page` emit `<!DOCTYPE html>` through an escaped entity
and render their own `<html>`, `<head>` and `<body>`. They do not inherit `web.layout`. Two
`t-call-assets` calls per page: CSS in the head, JS at the end of the body. Keep that split.

### 7. Odoo 19 specifics this module already navigated

- `type='json'` is a deprecated alias for `type='jsonrpc'`. This module uses the newer
  `type='json2'` for bare-REST JSON, which **requires** `Content-Type: application/json`.
- The framework hard-codes the CORS preflight `Access-Control-Allow-Headers` and does not
  include `X-Mezze-Token`, so every token-authenticated route also accepts the token in the
  JSON body or query string. Do not "clean this up".
- No `name_get`, no `attrs=`, no `groups_id`. Security uses `group_id` references in
  `security/ir.model.access.csv`.
- Frontend translations only reach the browser because `models/ir_http.py` adds
  `mezze_bridge` to `_get_translation_frontend_modules_name`.

### 8. Right-to-left is a real requirement

`i18n/ar.po` carries 884 message ids. The page templates set `dir="rtl"` for Arabic. Use CSS
logical properties (`margin-inline-start`, not `margin-left`). Phone numbers are forced to
left-to-right inside right-to-left rows. New user-facing strings need Arabic in the same
commit — the recent register commits all do this.

### 9. Assets are cached; the browser will lie to you

Restart Odoo with `--dev=assets` when editing bundle JS or CSS, then hard-reload
(Ctrl+Shift+R). Without it you will debug a stale bundle. The Owl debug handle used by the
browser tests only exists under `?debug=1`.

### 10. Tests are hermetic — keep them that way

The suite self-provisions its fixtures via `tests/common.py` and passes on a clean
`--without-demo=all` database. Do not add a test that depends on demo data. Run with
`--log-level=test`; at `warn` the "Modules loaded" and "0 failed, 0 error(s)" lines are
suppressed and a clean run looks like a crash.

There are 423 `browser_js` call sites. The established pattern is one browser per test —
loop-driven multi-launch tests were converted for exactly this reason. A test that skips
reads as a pass, so verify a new guard by negative control: remove the guard and watch the
named test go red.

### 11. UI fidelity is governed, not free

The standing instruction on this project, given verbatim on 2026-09-08: never redesign, never
"improve" spacing, typography, colour, density, radius or component proportions, and never
substitute generic Odoo UI where a Mezze reference exists. The reference is
`addons/mezze_bridge/docs/design-handoff/Mezze POS v3.dc.html`. Divergences from it are
recorded as decisions in `docs/design-gap/GAP_REGISTER.md`, not made silently.

### 12. Before building anything from the gap register

Its own closing instruction: read that row's domain doc in full, re-verify anything marked
`UNVERIFIED` against the contract, and check `FEATURE_MATRIX.md` and `PROJECT-STATE.md`
first so you do not re-verify what is already certified.

### 13. Git rules for this repository

From `CLAUDE.md`: `main` is the source of truth; `review/full` is disposable and
force-pushing it is expected; never force-push `main`, release branches or production
branches. Note the conflict flagged in §6 — the actual work is on
`feature/split-bill-v2`, 196 commits ahead of `main`.
