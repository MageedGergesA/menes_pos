# Mezze POS — Complete Feature Inventory (Evidence-Based Audit)

**Target:** `addons/mezze_bridge` @ `feature/split-bill-v2` (working tree, 33 uncommitted files)
**Module version:** `19.0.3.1.0` · product identity `1.0.0-rc.7` · latest tag `mezze-v1.0-rc7`
**Audited:** 2026-08-21 · **Method:** read-only source tracing, 9 parallel subsystem sweeps, claims re-verified at source by the coordinator
**Rule applied throughout:** where documentation and code disagree, **code wins**. Nothing is counted as a feature on the strength of its name.

---

## THE ONE FACT THAT GOVERNS EVERY ROW BELOW

There are **two** complete POS front-ends in this repository, and only one is production.

| | Production | Not production |
|---|---|---|
| **What** | 3 standalone Owl apps + 8 static customer pages | `static/pos.html` — one 5,016-line file |
| **Route** | `/mezze/pos`, `/mezze/kds`, `/mezze/floor`, `/mezze/drivethru` | `/mezze/design/pos` |
| **Self-declared** | `views/cashier_templates.xml:4` "production cashier page" | `controllers/main.py:2899` **"DESIGN PROTOTYPE launcher (non-production)"** |

`pos.html` is the largest, richest, most bilingual, most feature-complete file in the repo. It contains 11 workspace views, a guided tour, a 384-key bilingual string table, and screens for refunds, GL, reversals, marketing, time clock, waste, gift cards, loyalty redemption, quick keys, central kitchen and HQ roll-up — **none of which exist in the production cashier.** Several of its most visible numbers are fabricated client-side (§M).

**45% of the API surface (89 of 197 routes) has no production front-end caller.** Read every "UI?" column against that.

---

## A. EXECUTIVE SUMMARY — what Mezze POS is today

1. **It is an API-first restaurant platform, not an Odoo module with screens.** 197 HTTP routes, 56 own models — and exactly **4 models with any Odoo backend view**, under **one** menu tree (`Mezze Stations` → Enrol / Stations / Shifts). Reservations, waitlist, delivery, couriers, aggregators, campaigns, feedback, KDS tickets, the audit log and the whole config platform have **zero** back-office UI.
2. **The money spine is genuinely production-grade.** Every tender path converges on one `pos.payment` write guarded by a server-authoritative amount, `SELECT … FOR UPDATE`, and a DB-level `unique(pos_order_id, mezze_tender_key)`. There is no second money engine and no browser path that can fake a payment.
3. **It reuses Odoo rather than reimplementing it.** Stock deduction, pricelists, tax `compute_all`, loyalty, `pos_online_payment`, `sync_from_ui` — all native. The manifest's reuse claim is accurate.
4. **Split Bill V2 is better than native Odoo's.** Durable family columns on `pos.order` (native keeps it in browser `uiState`), row locks, optimistic revisions, combo atomicity, fired-KDS redistribution. 66 tests.
5. **The KDS state machine is the best-engineered component** — forward-only with legal skips, row-locked, idempotent, terminal-absorbing, browser-proven under concurrent bumps.
6. **Drive-thru is the strongest complete feature.** 4-station board, formally specified vehicle FSM with a closed terminal region, PostgreSQL-sequence merge ordering, two-window topology, and a 3-condition handoff gate enforced server-side at mutation time.
7. **Security architecture is unusually serious for an Odoo addon:** one canonical gate, 32 capabilities × 16 roles, ECDSA P-256 station identity with honest TPM/DPAPI/software levels, HMAC request signing, replay nonces, an atomic multi-worker rate limiter, AES-256-GCM envelope encryption, real SSRF defence, and a durable audit that survives read-only transactions.
8. **…but two of its three enforcement layers ship in `observe` mode.** Request signing defaults to OBSERVE; the order-lifecycle FSM guard defaults to observe. Both audit; neither blocks.
9. **It is NOT offline-capable.** Zero `indexedDB`, zero service workers, zero queue. A network failure loses the tender outright. The prototype's login screen advertises "Works fully offline"; that claim is false for every shipped surface.
10. **Realtime is polling.** No production surface opens a WebSocket. KDS polls every 4s, Floor refetches every 30s, and the **Register subscribes to nothing at all**.
11. **The floor plan is read-only.** Mezze renders native geometry and overlays live state; it cannot create, move, resize or rotate a table. All authoring is native Odoo backend.
12. **Prep-station routing is a hardcoded English keyword matcher** with six fixed stations and no configuration surface — a hard blocker for an Arabic menu.
13. **There is no aggregator integration with any named vendor.** What exists is a hardened generic webhook for a payload format Mezze invented.
14. **There is no real payment device.** Card terminals and cash machines both resolve to `REGISTRY = { test: simulatorAdapter }`; real providers are refused server-side rather than faked.
15. **Purchasing is entirely absent** — `purchase` is not a dependency and appears nowhere.
16. **Localization is excellent at the presentation layer and absent at the system layer.** `ar.po` is 542/542 complete, customer pages are 100% bilingual, RTL is 92.8% logical-property — but 1 file imports `_()`, 53 API error messages are English-only, and `EGP` is hardcoded 67 times outside the prototype.
17. **The "101-setting configuration platform" has 18 working settings**, all appearance/accessibility. Not one governs business behaviour.
18. **The honesty discipline is real and rare.** Split-by-seat returns `seat_reason: 'no_seat_model'`. The kiosk offers one payment option because Mezze drives no kiosk terminal. The go-live validator FAILs a production config wired to a simulator and marks physical checks NOT TESTED, a status no profile can upgrade.
19. **1,200 tests, structurally serious — but 41% run with authorization switched to `observe`**, and the one class that runs the shipped posture is 13/15 red.
20. **Physical certification has not started.** Every on-site acceptance directory is an empty placeholder.

---

## B. MASTER FEATURE MATRIX

Status: ✅ Production-ready · 🟢 Implemented · 🟡 Partial · 🟠 UI-only / no production UI · 🔵 Prototype · ⚪ Planned · 🔴 Broken/dead
Surface: **Owl** = production cashier · **proto** = `pos.html` (non-production) · **DT** = drive-thru · **cust** = shop/kiosk/qr

### 1. POS / Order Entry

| Feature | Sub-feature | Status | Frontend | Backend | Notes |
|---|---|---|---|---|---|
| Cart | New order / clear | ✅ | `root.js:3860` | `/orders/sync` `main.py:1015` | client uuid, server idempotent |
| Cart | Add product | ✅ | `order_store.js:223` | `main.py:1163` | server re-prices; client price untrusted |
| Cart | Line identity = product+modifiers+note+combo | ✅ | `order_store.js:201` → `product-config.js:307` | `main.py:1147` | NUL-separated key; correct merge |
| Cart | Quantity +/− | 🟢 | `cart.xml:104` | `main.py:1136` | integer only |
| Cart | Direct qty entry | ⚪ | — | — | `settings_catalog.py:56` disabled |
| Cart | Remove + 6s Undo | ✅ | `order_store.js:301,333` | client-only | `test_cashier_browser` test_10 |
| Cart | **Weighted / scale products** | 🔴 | — | 0 hits for `to_weight` | `_loadOrderLines` `Math.round(l.qty)` destroys fractions |
| Cart | **Subtotal breakdown row** | 🔴 dead | `cart.js:167` reads `order.subtotal` | — | `OrderStore` has no such getter → row can never render |
| Browse | Product grid, image-led | ✅ | `product_grid.js:38` | `main.py:958` | letter-tile fallback, no fake photos |
| Browse | Category sidebar + real counts | ✅ | `root.xml:221` | `main.py:945` | shared sheet, tested |
| Browse | Text search | ✅ | `order_store.js:437` | client-side | name substring, whole catalogue |
| Browse | Keyboard `/`, ↑↓, Enter-add | ✅ | `root.js:928-985` | — | never confirms a tender/refund/void |
| Browse | Favourites (device-local) | 🟢 | `order_store.js:104` | localStorage only | explicitly no server persistence |
| Browse | **Quick keys** | 🟠 | proto only (`pos.html:2324`) | `/menu/quickkeys` full API | Owl receives `quick_keys` in bootstrap and **discards it**; 0 tests |
| Browse | **Barcode / SKU scan** | 🟠 | proto only | bootstrap returns `barcode` | Owl drops `barcode`/`default_code` at map time |
| Browse | 86 / sold-out per branch | ✅ | `product_grid.js:22` | `/menu/eightysix`, `_assert_available` | per-`pos.config` id set, not a global flag |
| Browse | 86 live push to other tills | 🟡 | no bus subscriber in Owl | `bus._sendone('mezze_menu_86')` | only proto listens |
| Config | Shared modifier rules engine | ✅ | `design/product-config.js` (366 L, frozen global) | `_product_modifiers`, `_validate_modifiers` | one definition, Owl **and** DT; structurally enforced |
| Config | Configurator panel | ✅ | `components/product_config.js` | `main.py:1123` | required group named in the warning |
| Config | Price preview == charged price | ✅ | `order_store.js:171` | `main.py:1141` | documented fix |
| Config | Over-selection guard | ✅ | `product-config.js:156` | `main.py:1677` raises | tested |
| Config | Cross-product value injection blocked | ✅ | — | `main.py:1147`, `cart_pricing.py:97` | tested |
| Config | **Combos / meal deals** | ✅ | `product-config.js:68` | `_product_combos`, `_combo_child_vals` | real `product.combo`, Odoo's own proration |
| Config | **Half & half** | 🟠 | proto/shop only | `_halfhalf_apply` | eligibility = category name contains `"pizza"` |
| Config | Cooking preference / doneness | ⚪ | — | — | only as a generic attribute |
| Config | Allergens / dietary | 🟠 | kiosk shows `product.tag` | — | no allergen model; marketing copy, not compliance |
| Notes | Line note UI | 🟢 | `root.js:2921` | — | 200-char clamp |
| Notes | **Note persisted on the line** | 🔴 | — | `line_vals` has no `customer_note` | typed, shown, sent — then dropped |
| Notes | Note reaches kitchen ticket | 🟡 | — | `_line_note` `main.py:1534` | returns modifiers **OR** free text, never both |
| Notes | Order-level / kitchen note | ⚪ | — | — | |
| Discount | Per-line % | 🟠 | no UI anywhere | `main.py:1137,1156` | route accepts it; nothing sends it |
| Discount | Open price / manual override | 🟠 | proto sends list base only | `main.py:1133` | Owl never emits `price_unit` |
| Discount | **Order-level discount** | 🔴 fake | `pos.html:2601` hardcoded 10% | not sent | changes the screen, not the bill |
| Discount | **Comp (complimentary)** | 🟡 | `root.js:2674` | `/orders/comp`, approval ON by default | **button hidden by default** (see §M) |
| Discount | Comped line struck-through | ✅ | `cart.js:105` | `/orders/get` returns `discount` | survives reload |
| Promo | Auto-promotions | 🟡 | `shop.html:483` **customer only** | `_promo_for_cart`, `_promo_apply_to_order` | **never applied on `/orders/sync` or `/orders/pay`** — the till gets no promos |
| Promo | Typed promo code / coupon | 🟡 | customer only | `_promo_resolve_code` | single-use consumption works |
| Promo | `/promo/apply` from the till | 🔴 | no caller | needs `ORDERS_DISCOUNT`, which `terminal` lacks | would 403 anyway |
| Promo | Buy-X-get-Y | ⚪ | — | in `PROMO_TYPES`, returns `0.0` | listed as supported, never applies |
| Promo | Free-product reward | ⚪ | — | `main.py:5948` admits it | |
| Promo | `discount_mode='per_point'` | 🔴 | — | falls through to `0.0` | silently zero |
| Lifecycle | Park / hold | ✅ | `root.js:1359` | `/orders/park` → `mezze_parked` | never pays/cancels/unlinks |
| Lifecycle | Park (prototype) | 🔴 fake | `pos.html:2676` | no call | toast + cart wipe |
| Lifecycle | Orders workspace Open/Parked/Completed | ✅ | `root.js:1206` | `/orders/list`, branch-scoped | tested |
| Lifecycle | **Recall a draft** | 🔴 fidelity | `root.js:1160` | `/orders/get` `main.py:2596` | payload omits `attribute_value_ids`, `note`, combo → resume rebuilds **bare** lines, next sync **destroys** them server-side |
| Lifecycle | Completed = read-only | ✅ | `root.js:1410` | park refuses non-draft | tested |
| Lifecycle | Duplicate / reorder | ⚪ | — | — | |
| Lifecycle | **Fire to kitchen** | 🔴 bug | `root.js:2772-2778` | `_do_fire` appends `main.py:2168` | `_ensurePersisted()` writes the whole cart, then `/orders/fire` sends the **same whole cart**, which APPENDS → doubled lines and total. Route docstring says send the delta; the prototype does, the production app doesn't |
| Lifecycle | Fire idempotency / delta contract | ✅ (contract) | proto obeys it | `fire_uuid` sha1, advisory lock | backend sound, canonical client misuses it |
| Lifecycle | Void | 🟡 | `root.js:2700` | `/orders/void` cancels tickets + order + releases table | hidden by default; draft-only |
| Lifecycle | Manager gate (code+PIN+reason) | ✅ | `manager_gate.js` | `_verify_inline_approver` | pre-mint bug documented & fixed |
| Lifecycle | **Refund** | 🟠 | **proto only** | `/orders/refund` — minor-unit ceilings, advisory lock, ORM backstop | best-engineered code in the module; **no production UI** |
| Lifecycle | **Refund tender selection** | 🔴 bug | — | `main.py:4538` `pm = config.payment_method_ids[:1]` | every refund books to the config's **first** method; no override parameter |
| Lifecycle | Exchange | 🟠 | no caller anywhere | `/orders/exchange` | thin composition, no tests |
| Lifecycle | Split bill (by items) | ✅ | `split_bill.js` | `/split/commit` | 66 tests |
| Order type | Dine-in / Takeaway / Delivery chips | 🟢 | `root.js:2803` | `mezze_service_mode` | Selection is **only** `eat_in`/`takeaway` |
| Order type | Service mode persisted at charge | 🟡 | `root.js:2333,2647` send no `service_mode` | `main.py:1247` | pick Takeaway on a fresh cart → stored with no mode |
| Order type | Table locks the type | 🟡 | client-side rule only | server does not enforce | |
| Order type | **Curbside** | ⚪ | — | — | zero occurrences |
| Upsell | AI upsell | 🟠 | proto + QR only | `/ai/upsell` real confidence+lift miner | ⚠️ unbounded `search()` over all paid orders, O(n·k²) per request |
| Customer | Search / create / attach | ✅ | `root.js:2979,703` | `controllers/customer.py` | 8 tests |
| Customer | **Search leaks non-customers** | 🔴 bug | — | `customer.py:30-33` | `customer_rank>0` is **replaced** by the query domain, not extended |
| Customer | Customer-account (credit) sale | ✅ | `root.js:3053` | `_mezze_credit_gate` | 3 policies, `FOR UPDATE`, tested |

### 2. Restaurant Service · Tables · Floor Plan

| Feature | Sub-feature | Status | Frontend | Backend | Realtime | Notes |
|---|---|---|---|---|---|---|
| Floor | Multi-floor tabs | 🟢 | `floor/root.xml:61` | `/floors` | 30s poll | branch-scoped |
| Floor | Render position/size/shape/seats | 🟢 | `floor/root.js:171-193` | `main.py:4844` | — | round vs rounded-rect only; seat dots capped at 12 |
| Floor | **Floor creation** | 🔴 delegated | — | **no `restaurant.floor` write in the addon** | — | native Odoo backend only |
| Floor | **Table create / drag / resize / rotate** | 🔴 absent | click handler only | only write is `mezze_qr_token` | — | no pointer/drag/transform code exists |
| Floor | **Zoom / pan** | ⚪ | `overflow:auto` | — | — | browser scrollbars |
| Floor | State colours, non-colour-safe | ✅ | `floor_store.js:38` | `main.py:4847` | 30s | + `forced-colors`, `prefers-contrast` |
| Floor | Occupied / free / reserved | 🟢 | `root.xml:104-118` | `main.py:4854-4874` | 30s | multi-draft tables OR-ed and summed |
| Floor | **"Bill requested" state** | 🔴 dead | legend + CSS + mapping all ship | `/floors` emits only available/occupied/reserved | — | UI advertises a state the server cannot produce |
| Floor | Order total / guests / dwell / server | 🟢 | `root.xml:104-117` | `main.py:4857` | 30s | `server` is `user_id.name` — usually the service account |
| Floor | Table timer | 🟡 | no client tick | `minutes` from `date_order` | 30s | moves only on refresh (DT ticks 1s) |
| Floor | Responsive / touch | 🟡 | 44px floor met | — | — | **`floor.css` has no width media query at all** |
| Table | Open table → Register | ✅ | `floor/root.js:204` | `_resolve_table_context` | — | validates active + floor∈config |
| Table | Resume authoritative order | ✅ | `root.js:1105` | earliest draft, `limit=1` | — | tested |
| Table | Assign table to counter order | ✅ | `root.js:2081` | `/orders/assign_table` | — | advisory lock; refuses occupied/reserved/cross-branch |
| Table | **Transfer** | ✅ | `root.js:2189` | `/tables/transfer` | — | ordered advisory locks, re-labels KDS tickets, audited |
| Table | **Merge** | ✅ | `root.js:2225` | `/tables/merge` | — | re-homes lines+tickets, sums covers, rebuilds fired snapshot |
| Table | Merge financial safety gate | ✅ | server-authoritative | 409 `merge_blocked_payments` | — | refuses if either side has payments/reversals |
| Table | Set guest count | ✅ | `cart.xml:44` | `/orders/set_guests` | — | clamped ≥1 |
| Table | Release on payment | 🟢 | — | full settlement only | — | 8 tests incl. no-bypass |
| Table | **Waiter assignment / transfer** | ⚪ | — | `server_name` is a Char | — | no waiter model, no assignment endpoint |
| Table | **Seat numbers** | ⚪ declared | split modes list | `'seat': False, 'seat_reason': 'no_seat_model'` | — | honestly refused, tested |
| Table | Multiple orders per table | 🟡 | Register resumes earliest only | floor aggregates all | — | split children legitimately create N drafts |
| Courses | Hold / fire / board | 🟢 | `courses.html` | `/courses/*` | 2.5s poll | fired state derived from ticket states |
| Courses | **Held-course storage** | 🟡 | — | `ir.config_parameter` key per table | — | no model, no session scope, **no expiry** — survives payment and session close |
| Courses | **UI reachability** | 🔴 | `courses.html` served by **no route** | — | — | absent from launcher, rail and station roles; bearer token in the URL |
| Courses | Course grouping in order panel | ⚪ | — | catalog `disabled` | — | |

### 3. Drive-Thru

| Feature | Status | Evidence | Notes |
|---|---|---|---|
| Page route + auth + token mint | ✅ | `drivethru.py:113-159` | branch-scoped terminal, `Cache-Control: no-store` |
| Server-side theme stamping | ✅ | `drivethru.py:69-111` | panel width matches the Register |
| 4 stations (order/ops/payment/pickup) | ✅ | `drivethru.html:740`; `mezze_station.py:57-60` | client routing, crumbs, RTL-mirrored |
| Order taker reusing the Register verbatim | ✅ | CONV-1/2a/2b/3 bundles | certified by `test_drivethru_order_taker` |
| Server-priced totals | ✅ | `/drivethru/quote` → `mezze.cart.pricing` | no tax row invented for a tax-free branch |
| **Vehicle stage FSM** | ✅ | `drivethru.py:33-71` explicit `LEGAL_TRANSITIONS` | terminal region closed; back door in `write()` also closed; 18 tests |
| Lane + service sequences | ✅ | real PG `nextval` + `FOR UPDATE` | idempotent call-forward, gaps intentional |
| Server-authoritative clock | ✅ | `drivethru.html:800`; board returns `now` | a skewed till clock cannot misreport speed |
| **Handoff gate (3 conditions)** | ✅ | `main.py:7484-7516` | paid → kitchen-ready → at-window, all 409, evaluated at mutation |
| Payment at the window | ✅ | `action='pay'` | real branch tenders |
| Auto-advance preparing→ready | 🟢 | board writes on read | batched: 36 cars = 1 KDS query |
| **Lane count** | 🟡 | `drivethru.html:1239` hardcodes `[1,2]` | a 3-lane branch is unreachable from the UI |
| **Two-window topology** | 🔴 deadlocked | no client sends `action:'pickup'`; `main.py:7443` is a dead ternary | with `topology='two_window'` **no car can be handed off from the UI** |
| `holding` / pull-forward | ⚪ | model + endpoint, no UI | self-declared out of phase |
| Customer order board (OCB) | 🟢 | `ocb.py`, `static/ocb.html` | token-scoped public appliance, 0.5s poll, rate-limited |
| Topology & SLA target config | 🟡 | `ir.config_parameter` only | **not in the settings catalog**, no admin UI |

### 4. Self-Service · QR · Online

| Feature | Status | Evidence | Notes |
|---|---|---|---|
| Per-table QR token | ✅ | `restaurant_table.py:15-22` | `secrets.token_urlsafe(12)`, lazy mint |
| QR credential scope | ✅ | `_qr_resolve` `main.py:2868` | `(table_id, qr)` pair only; cannot reach another table |
| QR menu / order / bill | 🟢 | `main.py:2953-3100` | shared `_do_fire`, `_sanitize_customer_lines`, pause checked before session open |
| QR pay-at-table | 🟢 | `/qr/pay`; `/checkout/table/pay_online` | tip + settle in one savepoint |
| **QR cart totals** | 🔴 | `qr.html:269` `svc=sub*0.12, vat=(sub+svc)*0.14`, `'EGP'` hardcoded | `/shop/quote` exists and is never called |
| QR self-order product gate | 🟡 | `_SELFORDER_CHANNELS_GATED = ('kiosk',)` | `self_order_available` ignored for QR and shop |
| Kiosk config / menu / quote / order | ✅ | `main.py:3263-3612` | server re-validates every line; nothing invented |
| Kiosk privacy/idle reset, bilingual, images | ✅ | `kiosk.html:807-831` | tested |
| **Kiosk page routing** | 🟡 | no route — raw static file | the only station surface that isn't a controller |
| Shop pickup / delivery / COD / prepaid | ✅ | `main.py:3485-3630` | real UNPAID order for COD, never faked paid |
| **Shop cart totals** | 🔴 | `shop.html:475` same hardcoded 12%+14% | server then charges a different number |
| Price-tampering guard | ✅ | `_sanitize_customer_lines` whitelist | a public client cannot express a price |
| Public status page + tokens | ✅ | `pos_order.py:122-191` | SHA-256 stored, raw returned once, TTL + revoke, rate-limited, generic 404 |
| Self-order pause/resume, status, report | ✅/🟡 | `/selforder/*` | report has no UI |

### 5. Payments

| Feature | Status | Evidence | Notes |
|---|---|---|---|
| Cash tender + quick-cash | 🟢 | `payment_screen.js:245` | currency-agnostic, derived from the bill |
| Partial payment | ✅ | `main.py:2489` | leaves the order draft |
| Mixed / multiple tenders | ✅ | one `pos.payment` per tender | `action_pos_order_paid()` only at remaining≤eps |
| Per-tender idempotency | ✅ | `unique(pos_order_id, mezze_tender_key)` | safe double-click/retry |
| **Overtender** | 🔴 | server returns `error: 'overpay'` | UI clamps to remaining before sending |
| **Change** | 🟡 UI-only | `amount_return` **never written** | structurally always 0.00 — overpay is rejected |
| Manual / external-terminal tender | 🟢 | `manual_tender.js` | honest label: "does not verify it with the bank" |
| Reference + device + duplicate policy | ✅ | `payment_reconciliation.py:47-82` | allow/warn/manager/block, ORM constraint backstop |
| Manager PIN approval (non-self-approvable) | ✅ | role rank `<2` → `insufficient_role` | reused across terminal/cashmachine |
| **Cash rounding** | ⚪ | zero occurrences of `account.cash.rounding` | not implemented |
| Money precision | ✅ | `currency.decimal_places` + eps everywhere; refunds in integer minor units | property + golden tests |
| Split by item | ✅ | `/split/commit` | `FOR UPDATE`, revision check, combo atomicity, fired-KDS transfer |
| **Split evenly** | 🟠 | `even_amounts()` is pure and unit-tested | **no endpoint calls it**; UI says so |
| Split by seat | ⚪ | honestly refused with a reason | tested |
| Recombine / family / state | 🟢 | `split_bill.py:379-499` | refuses a paid child |
| **Integrated card terminal** | 🟢 orchestration / 🔴 no vendor | `terminal_service.js:80` `REGISTRY = { test: simulatorAdapter }` | 10 states, force-done, recon flag, 18 tests — and **zero real acquirers**; server refuses rather than fakes |
| Force Done (manager override) | ✅ | own provenance + `mezze_recon_flag` | never conflated with a provider confirmation |
| Uncertain/timeout never auto-retried | ✅ | `UNCERTAIN_STATES` | tested |
| Simulator production guard | ✅ | 403 unless flag; go-live FAILs it | |
| Online payments (native reuse) | ✅ | `checkout.py:175` → native `/pos/pay` | Mezze writes no card fields, never sets `tx.state` |
| `payment_demo` end-to-end | ✅ | 5 tests | |
| **Paymob** | 🟡 orphan | `w1.py:153-217` creates a real `payment.transaction` | tx carries **no `pos_order_id`** → can never become a `pos.payment` |
| Pay-before-fire (KDS on paid only) | ✅ | `mezze_online_payment.py:164` | row lock + fired flag; idempotent |
| Bank-app QR | 🟢 | native `get_qr_code` payload | confirmation is a cashier button; provenance `'manual'` |
| Egypt / InstaPay QR | ⚪ | go-live WARNs it is NOT certified | |
| **Cash machines** | 🟢 orchestration / ⚪ no device | `cash_machine_service.js:85` same simulator-only registry | Glory = `device_integration_pending`; Cashdro/Cashmatic exist only in a docstring |
| Inserted-vs-payment semantics | ✅ | payment = net; inserted/change display-only | tested |
| Customer credit / house account | ✅ | native `partner.credit`, no second ledger | 3 policies, deposit + FIFO settle, concurrency test |
| Gift cards — issue / balance / sale | 🟢 backend / 🟠 no Owl UI | real `loyalty.card` | selling a gift card from the Owl register issues **no card** (paid-sync branch only) |
| Gift card as a tender | 🟡 | proto only | server-validated `min(req, balance, total)`; not in `SUPPORTED_TENDER_MODES` |
| Loyalty points earning | 🟢 | wired into 4 money paths | real `loyalty.history` |
| **Loyalty program provisioning** | 🔴 | `_loyalty_program()` only **searches** for `'Mezze Rewards'` | nothing ever creates it → inert on a fresh install |
| **Loyalty redemption is client-trusted** | 🔴 | `main.py:2433` grafts `price_unit = -discount` | no check that a reward exists or the card was debited; bypasses the `LOYALTY_ADJUST` capability |
| Refund ceilings | ✅ | `domain/refund.py` + ORM `@api.constrains` backstop | closes the bypass for core POS UI and direct `sync_from_ui` too |
| Reversal queue / external refund confirm | 🟡 | backend only | delegates to the native provider's refund |
| Reconciliation (summary/settlement/finalize) | 🟢 backend / 🟠 no UI | `FOR UPDATE`, idempotent, tolerance gate | `unique(session_id)` |

### 6. Checkout · Receipts · Printing · Hardware

| Feature | Status | Evidence | Notes |
|---|---|---|---|
| On-screen receipt | 🟢 | `receipt.js/xml` | server line items preferred; per-rate tax; fully translated |
| ESC/POS network print | 🟢 **real** | `domain/escpos.py` + raw TCP :9100 | the only wire protocol Mezze implements itself |
| **Arabic / bilingual printed receipt** | 🔴 | `escpos.py:46` `s.encode('cp437','replace')` | Arabic prints as `?????`; every printed label is a hardcoded English literal, not `_()`-wrapped |
| **QR / barcode on printed receipt** | ⚪ | no `GS ( k` anywhere | ZATCA/ETA signed QR cannot be printed; ETA UUID prints as plain text |
| **VAT / tax-registration line on paper** | ⚪ | not in `receipt_ticket` | also absent: company address, cashier name, per-rate tax split, change, tip, logo |
| Browser-print fallback | 🟢 | `receipt.js:67` | gives Save-as-PDF when no printer |
| Reprint an older receipt | 🟡 | endpoint supports it | no UI reaches it |
| Refund receipt | 🟡 | generic ticket with negative lines | no credit-note layout |
| Kitchen ticket + per-station printer routing | 🟢 | `_pick_printer(station=)` | **no modifiers/notes on the printed ticket** |
| **Auto-print kitchen ticket on fire** | 🔴 | only `purpose='receipt'` is ever published | kitchen printing is pull-only |
| Print idempotency ledger | ✅ | `mezze.hw.job` unique key, savepoint-safe | re-renders from the authoritative order |
| Cash drawer | 🟢 real (`ESC p`) | auto-kick config-gated, default OFF | **no call in the production cashier**; stale-drawer expiry guard |
| Barcode scanner | 🟠 | keyboard-HID passthrough, no code | catalog entry marked `disabled` |
| Customer display — CFD | 🟡 legacy | pushed **only** from `pos.html` | production Owl drives no customer display |
| Customer display — OCB | 🟢 | DB-backed, server-priced, token-scoped | the real one — drive-thru only |
| Scales / NFC / pole display / IoT Box | ⚪ | zero references | `hardware.py:4` — Community has no IoT Box, so hardware is server-driven |
| E-invoice — Egypt ETA | 🟡 | `w1.py` reads native `l10n_eg_*` fields | `l10n_eg_edi_eta` is **not a manifest dependency**; probed defensively; needs a USB token |
| E-invoice — KSA ZATCA | ⚪ | a Selection value only | no signing, no UBL, no Fatoora |
| Public checkout status page | 🟢 | `/checkout/s/<token>` | server-rendered, RTL-aware, rate-limited |

### 7. KDS / Kitchen

| Feature | Status | Evidence | Notes |
|---|---|---|---|
| Ticket FSM (fired→accepted→preparing→ready→served, +cancel) | ✅ | `kds_ticket.py:23-126` | forward-only with skips, row-locked `FOR UPDATE`, terminal-absorbing, idempotent |
| Grain | — | one ticket = one station's slice of one fire | ticket-level, never item-level |
| Idempotent fire (`fire_uuid`) | ✅ | `main.py:2119` + advisory lock per table | replay returns existing tickets |
| Owl KDS board | ✅ | `static/src/kds/*` | own bundle; pure logic module with 20 Hoot tests + 11 browser tests |
| Bump (single next action) | ✅ | `store.js:36` `NEXT_ACTION` | one advance button per card |
| Recall (one step back) | ✅ flow / 🔴 correctness | `kds_ticket.py:114-126` | writes only `state` — **never clears the stamp being left**, so `ready_at` survives a recall and corrupts prep-time analytics; **no terminal guard**, so `served` can be recalled |
| **Cancel from the board** | 🔴 absent | no cancel button in `ticket_card.xml` | backend supports it; the cook cannot cancel |
| Live timer, late/overdue alert | 🟢 | `store.js:129-145` | `kds_late_minutes` is a **global** ICP, not branch-scoped, not in the settings catalog |
| Colour/state indicators, non-colour cues | ✅ | canonical `.mz-status--*` + text chips + strikethrough | `forced-colors` outlines |
| Cancelled shown, not removed | ✅ | full-width `CANCELLED — do not make` banner | production is safer than the prototype, which filters them out |
| **Sound / audio alert** | 🔴 | zero `Audio`/`beep`/`vibrate` | a busy kitchen gets no audible cue |
| **Priority / rush** | ⚪ by decision | documented out of v1 | |
| **Item-level bump** | ⚪ by decision | needs a `pos.order.line ↔ kds.line` link that doesn't exist | |
| Keyboard shortcuts / bump-all | 🔴 | zero `keydown` in `static/src/kds/` | touch-only, one ticket at a time |
| Station pin filter | 🟢 | chips derived from labels on the board | emergent, not configured |
| Reconnect re-seed | ✅ | re-reads authoritative state | no duplicates/stale/resurrected-cancels |
| **Prep-station routing** | 🟡 hardcoded | `main.py:2039-2057` | 6 English keyword stations, no config table; **Arabic names match nothing**; "Watermelon Salad" → Bar |
| Void cascade to kitchen | ✅ | `cancel_for_order` row-locked, spares `served` | 4 tests |
| Kitchen readiness mixin | ✅ | one `_read_group`, not stored, not sudoed | 36 cars = 1 query |
| Prep-time / per-station analytics | 🟢 backend / 🟠 no production UI | `/manager/dashboard` | |
| **Expo screen / packing screen** | 🔴 | zero occurrences of `expo`/`packing`/`bagging` | do not exist |
| Pickup board | 🟡 | proto board; Register shows a count only | derived from beverage tickets |
| **Realtime transport** | 🟡 | `kds/root.js:17` `POLL_MS = 4000` | **no WebSocket in any Owl app**; the only socket is in the prototype |
| Waiter "ready" bell + 86 broadcast | 🔴 no consumer | events published; Floor and Cashier poll no bus | server-side feature, zero delivery |
| `/orders/kds` (legacy) | 🔴 dead | zero consumers, zero tests | superseded by `/kds/state` |

### 8. Central Kitchen / Production

| Feature | Status | Evidence | Notes |
|---|---|---|---|
| `mezze.ck.request` lifecycle | 🟡 | 36-line model | thin tracker over real Odoo objects; `cancelled` unreachable |
| `/ck/produce` → real MO | 🟢 | `mrp.production` create→confirm→`button_mark_done()` | justifies the `mrp` dependency |
| `/ck/dispatch` → real picking | 🟢 | `stock.picking` + `button_validate()` | genuine inter-branch stock movement |
| `/ck/receive` | 🟡 | flips a state | stock already landed on dispatch |
| **Tests** | 🔴 | **0** references to any `/ck/*` route in `tests/` | the whole MO/picking path is unexercised |
| **Seed data** | 🔴 | products found by `default_code LIKE 'CK\_%'` | nothing ever creates one → inert on a fresh DB |
| Production UI | 🟠 | Owl workspace is read-only; only the prototype can drive it | |
| Branch scoping | 🔴 | classified `E` (scope-free); `branch_id` from the request body | a till at branch A can dispatch to branch B |
| `button_validate()` return discarded | 🔴 | `main.py:7781` | a backorder wizard leaves the picking unvalidated while the request flips to `dispatched` |
| Locations matched by name | 🟡 | `'Branch/%s' % config.name`, no `company_id` filter | renaming a config orphans its stock |

### 9. Reservations · Waitlist

| Feature | Status | Evidence | Notes |
|---|---|---|---|
| Reservation FSM (9 states) | ✅ | `reservation.py:16-31` | single source of legal transitions |
| List (day/upcoming/search) | 🟢 | `/reservations/list` | branch-scoped, limit 200 |
| Availability | 🟡 | `_res_conflict` half-open interval overlap | per-table only; no covers pacing, no turn-time, no table combining |
| **Double-booking hole** | 🔴 bug | domain is `state in ('booked','seated')` | omits `confirmed`, `arrived`, `late`, `waiting` — pressing **Confirm** releases the table hold, on the floor board and the walk-in guard too |
| Availability scan cost | 🟡 | unbounded search per table, filtered in Python | 40 tables × full history per keystroke |
| Create / party size / table assign | 🟢 | cross-branch refused, 409 on clash | |
| **Booking edit (date/time)** | ⚪ | only `guests` and `table_id` are mutable | changing a time = cancel + rebook |
| Calendar view | ⚪ | list only | |
| **Guest confirmation (SMS/email)** | ⚪ | no `mail.mail`/`sms.sms` in the reservation path | |
| Cancellation / no-show + restore | 🟢 | terminals restore to `booked` | |
| Auto no-show / late sweep | ⚪ | no cron | `late` is manual; a display-only flag |
| **Reservation → POS handoff** | ✅ | `_seat_attach_order` + back-link | idempotent from both directions; propagates covers + partner |
| Waitlist FSM (7 states) | ✅ | `waitlist.py:16-27` | includes a `seating` hold against double-seating |
| Add / list / quote | 🟢 | `/waitlist/*` | |
| Wait-time estimator | 🟡 | `10 + waiting*12 (+10 if full)`, capped 120 | **party size is accepted and never used**; no historical turn-time |
| **Guest notification** | 🔴 name-only | `'notify': 'notified'` writes a state and nothing else | no SMS, no push, no pager |
| Check-in / seating | 🟢 | same idempotent attach | |
| **Preferences (area, high chair, accessible, VIP)** | 🟡 dead | fields declared | `/waitlist/add` has no parameter for any of them |

### 10. Delivery · Aggregators

| Feature | Status | Evidence | Notes |
|---|---|---|---|
| Zone model | 🟢 | `delivery.py:50-68` | **no geography at all** — no lat/lng, polygon, radius or postcode; the customer picks the zone from a `<select>` |
| Zone validation | ✅ | `main.py:3505-3521` | exists/active/this-branch → COD allowed → open → above minimum |
| Fee | 🟢 | flat `zone.fee`, untaxed line on an auto-created service product | client `fee` is overwritten server-side |
| **ETA** | 🟡 | static `zone.eta_minutes` (default 45) | never computed — no kitchen load, queue, courier, distance or historical feedback, even though `/delivery/report` measures real prep and delivery minutes |
| Opening hours | 🟡 | `hours_json` per weekday | naive UTC (a Cairo branch is evaluated in UTC); malformed JSON **fails open** |
| `/delivery/availability` | ✅ | public, server-authoritative, leak-tested | production Owl form obeys it |
| `/delivery/create` (staff) | 🟢 | zone fee re-resolved, minimum enforced, kitchen fired | |
| **COD** | ✅ | real unpaid `pos.order`, `amount_paid: 0.0` | `/delivery/collect` row-locks, idempotent on `cod-<id>`, one payment; test collects ×3 → 1 payment |
| **`payment_mode` mislabelled** | 🔴 bug | 3 of 4 creation paths omit it → defaults `'cod'` | prepaid and online deliveries are recorded as COD; `cod_uncollected` counts them as uncollected cash forever |
| Lifecycle FSM + manager gate on late cancel | ✅ | `_LEGAL` + `_transition()`, rank<manager can never authorise | |
| **`/delivery/state` + `/collect` skip object-scope** | 🔴 authz | bare `self._authorize()` with no `target=` | classified Category A; a branch-B principal can transition a branch-A delivery by id |
| Couriers | 🟡 | 33-line model, 3 states | no UI calls `/delivery/couriers`; no branch check |
| **Dispatch board** | 🟠 | proto only | production Delivery workspace is a **read-only generic list** — no assign, no collect |
| `/delivery/report` | 🟡 | real KPIs, tested | **no caller** |
| Customer tracking "out for delivery" | 🔴 dead | `pos_order.py:178` tests `state in ('dispatched','out')` | neither is a real state (`out_for_delivery` is) |
| Maps / navigation / geocoding | ⚪ | zero hits for lat/lng/geo/polygon/postcode/maps/waze | |
| **Aggregator vendors** | ⚪ **none** | Mrsool/Careem/Deliveroo/UrbanPiper/Deliverect/Zomato = **0 occurrences**; Talabat/Jahez/HungerStation appear only in 2 docstrings, 1 help string and test AAD literals | |
| Generic aggregator webhook | ✅ | raw-byte HMAC + `compare_digest`, AES-GCM envelope secret, idempotent on `(agg, external_id)`, unmapped-SKU rejects the whole order | production-quality delivery machinery, **no vendor semantics** |
| Outbound status webhook | ✅ | SSRF pre-check + post-DNS IP re-check, no redirects, TLS dead-letter | posts Mezze's own JSON shape to one admin-set URL |
| **`aggregator/orders` capability** | 🔴 | endpoint id resolves to `"orders"`, not a registry key → `cap = None` | no capability required; any till principal can read commission and payout figures |
| Aggregator configuration | 🔴 | no view for `mezze.aggregator` or `.product.map` | every channel and SKU row is an `odoo-bin shell` script |

### 11. Products · Menu · Pricing · Inventory · Purchasing

| Feature | Status | Evidence | Notes |
|---|---|---|---|
| Catalog bootstrap | ✅ | `/bootstrap` real `search_read` | no fixtures |
| Branch-aware product domain | ✅ | `_menu_domain` mirrors native `_load_pos_data_domain` | fixed a real "26 items in Odoo, whole catalogue in Mezze" bug |
| Variants | 🟡 | surface as independent tiles | no variant selector, no template grouping |
| Menu images (staff + customer) | 🟢 | native `/web/image` + token-gated `/shop/image` | |
| Daypart menus / scheduling / happy hour | ⚪ | zero hits | nearest is native pricelist date rules — **day granularity only** |
| Nutritional data | ⚪ | — | |
| Native pricelist engine reused | ✅ | `_get_product_price` + `compute_all` only | no custom price engine |
| `mezze.cart.pricing` (pre-fire pricer) | ✅ | batched by distinct qty; PTAV/combo validated before pricing | refuses to invent a tax row |
| Branch prices | 🟢 | `config.pricelist_id` everywhere | |
| **Customer-specific pricing** | 🔴 | `property_product_pricelist` = **0 occurrences** | a B2B partner is charged branch list price; partner *is* used for fiscal position, so tax is customer-aware and price is not |
| Sales stock deduction | ✅ delegated | native `action_pos_order_paid` → `_create_order_picking` | Mezze writes no `stock.move` on any sales path |
| Recipes / BoM cost | 🟢 | `_recipe_cost`, one-level explosion | |
| Theoretical vs actual consumption | 🟢 | variance, variance %, food-cost % per product | genuinely restaurant-grade; **one BoM level only** |
| Ingredient burn-rate / stock-out projection | 🟢 | from real velocity ÷ `qty_available` | no production UI |
| Waste / spoilage | 🟢 backend / 🟠 proto UI | real `stock.scrap` + `do_scrap()` in a savepoint, native reason tags, money impact | careful env/valuation handling |
| Inter-branch transfer | 🟢 | real internal `stock.picking`, validated | |
| **Lots / serials** | 🔴 | `'pack_lot_ids': []` on every path | a lot-tracked product produces a picking with no lot |
| Expiry / removal dates | ⚪ | only a waste *reason* string | |
| UoM conversion | 🟡 | passed through for scrap, displayed | order lines carry no `product_uom_id` |
| Reorder rules / orderpoints | ⚪ | zero hits | |
| Inventory adjustment UI | 🔴 | only via the offline-sync outbox, which has no client | |
| **PURCHASING (all of it)** | ⚪ **ABSENT** | `purchase` not in `depends`; 0 hits for `purchase.order`/`seller_ids`/`supplier_rank` | no vendors, POs, approvals, receiving, returns, supplier pricing or reorder automation |

### 12. Multi-branch · Configuration Platform

| Feature | Status | Evidence | Notes |
|---|---|---|---|
| Branch = `pos.config` | — | `main.py:7520`; `pos.config` is **not** extended | no branch model, no company-per-branch requirement |
| Branch resolution is token-authoritative | ✅ | `_resolve_config` `main.py:766-797` | a scoped principal naming another branch is **ignored and logged**; docstring names the two bugs it fixed |
| Branch chooser `/mezze/start` | ✅ | reads with the **user's own env** so record rules filter for free | a station never sees a chooser |
| Branch-specific menus / prices | 🟢 | `limit_categories` + pricelist | |
| Branch-specific inventory | 🟡 | only via CK `Branch/<name>` locations | ordinary POS stock is per-warehouse → two branches in one company share stock |
| `/branches`, `/hq/summary` | 🟡 | full per-branch KPIs + chain totals | bare `search([])` — **not scoped** despite Category-B classification |
| Cross-branch order isolation | ✅ | `_mezze_scope_domain` fails **closed** | correct pattern — applied to 9 routes, missing from ~15 |
| Settings catalog | 🟢 | **101 settings: 18 working, 76 disabled, 7 hidden**, 13 sections | every disabled entry carries a real reason; enforced server-side, not just documented |
| Working settings scope | 🟡 | all 18 are appearance/a11y | **not one business setting** |
| Scope cascade (7 scopes) | ✅ | platform→org→brand→branch→role→user→device | full provenance per key |
| Locks (free/bounded/locked) | 🟡 | `locked` correctly blocks lower scopes | **`bounded` is advisory only** — `is_valid()` never checks `bounded_options` |
| **`brand` scope** | 🔴 dead | `settings.py:55` hardcodes `'brand_id': None` | a brand lock writes a row, audits it, and is never read |
| **`device` scope** | 🔴 | `save_user` always writes `scope='user'` | the two scopes never see each other's rows |
| Templates + publish/version/assign | 🟡 | model + lifecycle complete; resolver honours published only | **no API can add a template line** → templates can only ever be empty |
| Admin console (11 endpoints) | 🟠 | 0 callers in `static/`, no backend view | reachable only by curl |
| Config audit trail | ✅ | actor/scope/key/old/new per operation | |

### 13. Reporting · Live Ops

| Report / endpoint | Metrics exposed | UI? | Status |
|---|---|---|---|
| `/ops/summary` | `net_sales, tx, avg_ticket, margin, theoretical_cost, top_products[], hourly[], foodcost[]{theoretical,actual,variance,variance_pct,foodcost_pct}, burnrate[]{on_hand,used_today,rate_per_hr,hours_to_out}` | proto only; **Owl panel renders blank** | 🟡 |
| `/manager/dashboard` | `sales{net,tx,avg_ticket,margin}`, `service{open_tabs,open_amount,occupied,total_tables,oldest_tab_min}`, `kitchen{open_tickets,ready_waiting,avg_prep_sec,oldest_open_min,sla_minutes,sla_breaches,stations[]}`, `servers[]`, `alerts[]` | proto only; Owl blank | 🟡 |
| `/hq/summary` | `total{net_sales,tx,open_tabs,active_deliveries,open_tickets,occupied,total_tables,branches,open_branches,avg_ticket}` + per-branch rows | proto only; Owl blank | 🟡 |
| `/w1/reports/summary` | `sales{count,total,avg_ticket}`, `refunds{count,total,by_reason{}}`, `reversals{open,resolved}`, `by_cashier{}` | proto only | 🟢 |
| `/w1/reports/refunds.csv` | `datetime,reference,amount,reason_code,cashier,approver_cashier_id` | proto only | 🟢 |
| `/w1/gl/summary` | `sessions{count,posted_moves,draft_moves}`, `accounts[]{code,name,type,debit,credit,balance}`, `totals{debit,credit,balanced}`, `tax{}` | proto only | 🟢 |
| `/w1/gl/sessions` | per session: `orders,total,move,move_state,gl_balance,**cash_diff**,unposted,unbalanced,cash_flag` | proto only | 🟢 |
| `/w1/gl/export.csv` | `date,entry,journal,account_code,account_name,partner,label,debit,credit,tax` | proto only | 🟢 |
| `/delivery/report` | `total, delivered, revenue, fees, aov, cod, prepaid_or_online, cod_uncollected, cancellations, cancel_reasons{}, avg_prep_minutes, avg_delivery_minutes, by_zone{}, by_courier{}` | **none** | 🟡 |
| `/selforder/report` | `total, revenue, aov, by_channel{}, paid, payment_due, cancellations, top_items[]` | **none** | 🟡 |
| `/feedback/list` | `count, avg, distribution{1..5}, items[]` | proto only | 🟡 |
| `/waste/list` | `total_cost, today_cost, reasons[], items[]` | proto only | 🟡 |
| `/clock/list` | `on_clock, hours_total, staff[]{hours_today}` | proto only | 🟡 (not branch-scoped) |
| `/payment/report` | `by_method{}, by_device{}, refunds, payment_count` | **none** | 🔴 no capability check |
| `/reconciliation/summary` | `state, overall_status, total_difference, lines[]{expected,settlement,difference,status}` | **none** | 🔴 no capability check |
| `/marketing/segments` | `counts{all,loyalty,recent}, whatsapp_ready` | proto only | 🟠 |
| Odoo backend pivot/graph/report | **none** — 0 `<pivot>`, 0 `<graph>`, 0 `ir.actions.report` | — | ⚪ |
| **Native POS Analysis by cashier/terminal** | ✅ | `pos_order_views.xml:96-106` adds group-bys | real orders → Odoo's own pivot works for free |
| Void report | ⚪ | `order.void` is audited; **no report reads it** | |
| Discount report | ⚪ | **no `discount.override` event is ever written** | comps are audited; plain discounts are not |
| Security-denial metrics | 🔵 | `security_metrics()` exists, **no endpoint** | |
| Data-integrity validator (12 checks) | 🔵 | `golive.integrity()`, **no HTTP endpoint** | |

**Live-ops latency, measured:** write → outbox consumer **sub-second** (post-commit hook) · consumer → `bus_bus` immediate · `bus_bus` → **KDS 0–4s** · → **Floor 0–30s** (and only via a full refetch, not the bus) · → **Cashier never** · post-commit failure → cron recovery ≤60s.

### 14. Employees · Security · Sessions

| Feature | Status | Evidence | Notes |
|---|---|---|---|
| Cashier identity, 8 roles | ✅ | `mezze_cashier.py:29-35` | |
| PIN storage | ✅ | PBKDF2-SHA256 ×100 000 + per-record salt | plaintext never stored |
| PIN throttle + timing equalisation | ✅ | `_dummy_pin_work` for unknown codes; fails **closed** | counts only failures, with the reasoning written down |
| Clock in/out | 🟡 | proto only | **uses raw `check_pin`, bypassing the throttle** |
| **Cashier backend UI** | 🔴 | no view for `mezze.cashier` | PINs must be set via ORM/shell |
| Station shift (device + PIN → Odoo session) | ✅ | least-privilege service identity, path-confined, revocable | the only real staff backend UI |
| Capability model | ✅ | 32 capabilities × 16 roles, least-privilege | |
| **`ALL_CAPABILITIES` omits `orders.split*`** | 🔴 bug | verified by executing `authz.py`: `can('cashier','orders.split') → False` | `administrator` cannot call `/split/commit` or `/split/recombine` |
| Single canonical gate | ✅ | `_security_gate`, structurally tested | no per-endpoint auth logic |
| **6 routes bypass capability checking** | 🔴 | `payment/report`, `reconciliation/summary`, `payment/breakdown`, `payment/devices`, `edge/status`, `aggregator/orders` | 4 are financial reads; the structural test's regex can't span a decorator ending in a trailing comment, so it reports 100% |
| Object scope wired | 🟡 | 13 of 63 Category-A routes | includes money routes: `orders/exchange`, `payment/void`, `reversals/resolve`, `loyalty/redeem`, `delivery/state`, `delivery/collect`, `kds/transition` |
| Branch scope on collections | 🟡 | 9 routes use the (correct, fail-closed) helper; ~15 don't | and the module ships **zero `ir.rule` records** |
| HMAC signing + nonce replay | 🟡 | canonical string binds version/kid/principal/method/path/body-hash/ts/nonce; duplicate-header smuggling rejected; nonce burned only after a valid signature | **defaults to OBSERVE** |
| Rate limiter | ✅ | PG `INSERT … ON CONFLICT … RETURNING` on an independent connection | atomic across worker processes; FAIL_CLOSED; **6 endpoints only** |
| Envelope encryption | ✅ | AES-256-GCM, `MEZZE_MASTER_KEY`, AAD-bound | migrations fail closed rather than store plaintext |
| SSRF defence | ✅ | blocks IMDS/loopback/private by name + post-DNS re-check | |
| Redaction | ✅ | structural patterns, PEM blocks, Luhn PANs, CVV-near-label, emails, key-based JSON | idempotent, never raises |
| Durable security audit | ✅ | independent self-committing cursor | survives Odoo 19 readonly `auth='none'` transactions; presence booleans only |
| Audit trail UI | 🔴 | ~80 event types, append-only, **no backend view** | an auditor with an Odoo login has no screen |
| Manager elevation | 🟡 | approver must genuinely hold the capability; both identities audited | **OFF by default** (`allow_manager_elevation = '0'`) |
| Break-glass emergency access | 🟡 | ≤1h, scoped, capability-narrowed, audited | no UI; `_cron_expire` never scheduled |
| Security-config weakening guard | ✅ | 12 guarded keys; production raises `UserError` before the write | strengthening always allowed |
| FSM guard (13-state RFC-001) | 🟡 | pure, property-tested | **defaults to observe** |
| **Gate fails open on exception** | 🟠 | outer `except Exception: return None` | not mode-scoped — fails open in `enforce` too |
| Session close preview | ✅ | payments by method, cash opening/taken/expected | blocks on open orders, server-computed |
| Session close | 🟢 | delegates to native `action_pos_session_closing_control()` | **writes no audit row** |
| **Counted cash / discrepancy / over-short** | 🔴 absent | the endpoint accepts no counted amount | `cash_register_difference` is only ever **read**, in `/w1/gl/sessions` |
| Cash in / cash out / drawer moves | ⚪ | no endpoint, no model | |
| X report | ⚪ | — | |
| **Z report** | 🟠 fabricated | `pos.html:1896-1910` hardcoded EGP figures; over/short is `var exp=14180` | |
| Shift handover | 🟢 | device-level `end('handover')` | not cash-level |
| Go-live validator | ✅ | **77 named checks** (60 baseline + 17 edge) | `NOT TESTED` is first-class and no profile can upgrade it; FAILs a simulator in production |
| Onboarding (13 derived steps) | ✅ | completion derived from the validator, not a stored flag | |
| Release identity / support bundle / audit export | ✅/🟡 | redacted bundle, leakage-tested | export has no UI |

### 15. Platform · Offline · Realtime

| Capability | Status | Evidence |
|---|---|---|
| **Client-side order queue** | 🔴 | `indexedDB` **0**, `serviceWorker` **0**, `sessionStorage` **0**, Cache API **0**, `navigator.onLine` **0** |
| **Tender with server unreachable** | 🔴 | `root.js:2561` "Local Mezze server unavailable — payment not taken." — no queue, no retry |
| `localStorage` actual use | — | language, theme, favourites frequency map, terminal-id string. **No order, line, payment or event.** |
| Terminal-side sync outbox | 🔴 dead | `mezze.sync.outbox` + `.cursor`: models + 4 ACL rows, **zero writers** anywhere |
| Windows station client | ⚪ | zero `.exe`/`.cs`/`.csproj`/`.msi` in the repo |
| Sync server (`register/push/pull/reconcile`) | 🟢 | fully built: dual idempotency (cursor + `unique(terminal,res_uuid)`), per-event savepoints, dead-lettering, commutative signed deltas |
| Multi-node replication in operation | ⚪ | **no node ever pushes** — a one-ended pipe |
| Transactional outbox | ✅ | `FOR UPDATE SKIP LOCKED`, strict per-aggregate ordering, visibility timeout, backoff, dead-letter, replay, metrics |
| Post-commit dispatch | ✅ | one `cr.postcommit` hook per request — this is what makes latency sub-second |
| WebSocket push | 🔵 | real socket + reconnect — **only in `pos.html`** |
| Bus long-poll | 🟢 | `/bus/poll` → `bus.bus._poll` — the only production realtime transport |
| Edge connectivity indicator | 🟢 | 20s poll of `/edge/status`; cached WAN probe; `paused` during outage |
| Station identity protocol | ✅ | one-time HMAC-fingerprinted activation codes → ECDSA P-256 challenge (nonce burned before mint) → 900s session → signed 7-day lease |
| Honest security levels | ✅ | A (TPM) / B (DPAPI) / C (unprotected software) — refuses to pretend software == hardware |
| Surface confinement | ✅ | a Register station gets 403 on `/mezze/kds`; typing `/odoo` into a till reaches nothing |
| Cron jobs | 🟢 | 3 registered (outbox 1min, nonce GC 1h, station-surface GC 10min) |
| **Orphan cron methods** | 🔴 | `rate_limit._cron_gc` and `emergency_access._cron_expire` are never scheduled |
| Migrations | 🟢 | 6 scripts, all idempotent; two **fail closed** on secret-migration error |
| API versioning | 🟡 | 3 of 6 prefixes are versioned (`/mezze/w1`, `/mezze/hardware`, `/mezze/aggregator` are not) |

---

## C. SCREEN INVENTORY

| Screen | Route / entry | Purpose | Main capabilities | Status |
|---|---|---|---|---|
| **Check-in / branch chooser** | `/mezze/start` (`auth=user`) | pick your register | branch list filtered by the user's own record rules; 5 surface links per branch; a station skips it | ✅ |
| **Register (Owl cashier)** | `/mezze/pos` | the till | catalogue, category nav, search, configurator, combos, cart, park/recall, orders workspace, table ops, split, comp/void (hidden by default), delivery form, customer + credit, payment screen, receipt | ✅ |
| **Kitchen Display (Owl)** | `/mezze/kds` | cook's board | ticket cards, bump, recall, station filter, timers, late alerts, cancelled banner, 4s poll | ✅ |
| **Floor (Owl)** | `/mezze/floor` | table monitor | multi-floor, live state, covers, dwell, totals, reservation holds, tap→Register. **Read-only** | 🟢 |
| **Drive-thru board** | `/mezze/drivethru?mode=order\|ops\|payment\|pickup` | 4 lane stations | order taker, lane board, call-forward, payment, handoff gate, OCB publish | ✅ |
| **Order Confirmation Board** | `/mezze/ocb/<display_token>` | customer-facing DT display | server-priced snapshot, token-scoped, rate-limited | 🟢 |
| **Kiosk** | static `kiosk.html` (station role) | self-order | eat-in/takeaway, config from branch, server-priced, pay-at-counter, idle privacy reset, EN/AR | ✅ |
| **Storefront** | static `shop.html?store=<tok>` | online pickup/delivery | menu, modifiers, combos, zones, COD/prepaid, promo code, status | 🟢 (client tax is wrong) |
| **Table QR** | static `qr.html?table=&qr=` | guest at the table | menu, order, bill, tip, pay, pay-online, upsell | 🟢 (client tax is wrong) |
| **Public checkout status** | `/checkout/s/<status_token>` | order tracking | server-rendered, RTL-aware, rate-limited | 🟢 |
| **Feedback** | static `feedback.html` | guest rating | 1–5 + comment, optional order link | ✅ |
| **CFD** | static `cfd.html` | customer display | polls a token-authed snapshot | 🟡 legacy — only the prototype pushes to it |
| **Courses board** | static `courses.html` | waiter coursing | hold / fire / board | 🔴 **served by no route, in no navigation, token in the URL** |
| **Onboarding / Go-Live console** | static `onboarding.html` | certification | 77 validator checks, 13 steps, version, support bundle | 🟠 **no controller route; needs the token production disables** |
| **Design prototype** | `/mezze/design/pos` | visual reference | 11 workspaces, 13 overlays, guided tour, 384-key i18n | 🔵 non-production |
| **Odoo backend — Mezze Stations** | menu → Enrol / Stations / Shifts | device fleet | enrol wizard, station list/form, shift list + revoke | 🟢 |
| **Odoo backend — POS orders** | native POS views + Mezze inherits | order review | adds cashier/terminal fields + **group-by**, split-family sub-list | 🟢 |
| `test_client.html` | none — outside `static/` | dev harness | — | 🔴 dead, unserved, unreferenced |

**Not reachable from any navigation:** `onboarding.html`, `courses.html`, `cfd.html`. **Reachable only by direct URL/QR by design:** `kiosk.html`, `shop.html`, `qr.html`, `feedback.html`. All are served publicly at `/mezze_bridge/static/*.html` with no Odoo auth — access control rests entirely on per-page query-string tokens.

---

## D. INTEGRATION INVENTORY

| Integration | Purpose | Direction | Real protocol? | Status | Evidence |
|---|---|---|---|---|---|
| Odoo `point_of_sale` / `pos_restaurant` | orders, stock, accounting | in-process | ✅ native | ✅ | `sync_from_ui`, `action_pos_order_paid` |
| Odoo `loyalty` | promos, coupons, gift cards, points | in-process | ✅ native | 🟢 | `main.py:5654-6127` |
| Odoo `stock` / `mrp` | pickings, scrap, MOs | in-process | ✅ native | 🟢 | waste, CK produce/dispatch |
| Odoo `bus` | realtime fan-out | in-process | ✅ native | 🟢 | via the outbox `mezze.bus.broadcast` consumer |
| Odoo `pos_online_payment` | POS ↔ `payment.transaction` | out + in | ✅ native | ✅ | Mezze only extends `_process_pos_online_payment` |
| `payment_demo` | prove the online path | out | ✅ native | ✅ | 5 tests |
| **Paymob** (`payment_paymob`) | card/wallet, Egypt | out | ✅ native provider | 🟡 **orphan** | tx has no `pos_order_id` → never becomes a `pos.payment` |
| Bank-app QR (EMV/SCT) | customer scans | out + manual in | ✅ native payload | 🟢 | no bank webhook; cashier confirms |
| Egypt InstaPay QR | — | — | — | ⚪ not certified | go-live WARNs |
| **ESC/POS over TCP :9100** | receipts, kitchen tickets, drawer | out | ✅ **REAL — the only wire protocol Mezze implements** | 🟢 | `domain/escpos.py` |
| Cash drawer (printer pin) | pop drawer | out | ✅ real (`ESC p`) | 🟢 | |
| **Card terminals** (Stripe/Adyen/Six/Worldline/any) | integrated card | — | ❌ **none** | ⚪ | `REGISTRY = { test: simulatorAdapter }`; server refuses rather than fakes |
| **Glory cash machine** | automated cash | — | ❌ none | ⚪ | native module exists but is browser-direct WebSocket welded to native PosStore |
| **Cashdro / Cashmatic** | automated cash | — | ❌ absent | ⚪ | named in a docstring header only |
| **Egypt ETA** (`l10n_eg_edi_eta`) | e-invoice clearance | out | ✅ real but native **and not a dependency** | 🟡 | Mezze invoices and *reads* the native fields; needs a USB token |
| **KSA ZATCA** | e-invoice clearance | — | ❌ a Selection value | ⚪ | |
| **Delivery aggregators** (Talabat/Jahez/HungerStation/…) | order ingestion | in | ❌ **no vendor code at all** | ⚪ | generic hardened webhook for a Mezze-invented format |
| Outbound status webhook | notify a partner | out | ✅ real HTTP + HMAC + SSRF defence | 🟢 | posts Mezze's own shape to one admin-set URL |
| Odoo `mail` | email campaigns | out | ✅ real `mail.mail` | 🟡 | never calls `.send()`; relies on the mail cron; one create per recipient |
| Odoo `sms` | SMS campaigns | out | ✅ real `sms.sms` | 🟡 | **`sms` is not in `depends`** — survives on its `auto_install` |
| **Meta WhatsApp Cloud** | WhatsApp campaigns | — | ❌ honest stub | ⚪ | `sent, state = 0, 'queued'` |
| **Barcode scanner** | product lookup | in | keyboard-HID passthrough, no code | 🟠 | catalog entry marked `disabled` |
| CFD / OCB displays | second screen | out | abstraction (config param / DB projection + bus) | 🟡 / 🟢 | |
| Scales · NFC · pole display · IoT Box | — | — | ❌ absent | ⚪ | Community has no IoT Box by design |
| Edge↔cloud replication | multi-node | — | server built, **no client** | ⚪ | `mezze.sync.outbox` has zero writers |

---

## E. KEY DATA MODELS

**Own models: 56** (+ 8 inherited: `pos.order`, `pos.order.line`, `pos.payment`, `pos.payment.method`, `res.partner`, `res.users`, `restaurant.table`, `ir.http`, `ir.config_parameter`, `payment.transaction`).

| Entity | One-line description | Location |
|---|---|---|
| `pos.order` *(extended)* | the check — + `mezze_channel`, `mezze_service_mode`, `mezze_parked`, `mezze_fired`, split-family columns, status token | `models/pos_order.py` |
| `pos.order.line` *(extended)* | + refund-ceiling ORM backstop | `models/pos_order.py:195` |
| `mezze.kds.ticket` / `.line` | one station's slice of one fire event; the KDS FSM lives here | `models/kds_ticket.py` |
| `mezze.terminal` | a till/device: token fingerprint, branch, role | `models/mezze_terminal.py` |
| `mezze.station.activation` / `.challenge` / `.session` / `.lease.signer` | device enrolment → ECDSA challenge → short session → signed offline lease | `models/mezze_station.py` |
| `mezze.station.surface.session` | a staff shift running on a device | `models/mezze_station_surface.py` |
| `mezze.cashier` | a person: PIN hash, role, allowed branches | `models/mezze_cashier.py` |
| `mezze.attendance` | clock in/out (deliberately not `hr.employee`) | `models/attendance.py` |
| `mezze.reservation` | a booking, 9-state FSM | `models/reservation.py` |
| `mezze.waitlist` | a walk-in queue entry, 7-state FSM | `models/waitlist.py` |
| `mezze.delivery` / `.zone` / `mezze.courier` | delivery order + named zone (no geography) + driver | `models/delivery.py`, `mezze_courier.py` |
| `mezze.drivethru` | a car visit: dual kitchen/vehicle journeys, lane + service sequences | `models/drivethru.py` |
| `mezze.ocb.display` | drive-thru customer board snapshot | `models/ocb.py` |
| `mezze.aggregator` / `.product.map` / `.order` | channel + SKU mapping + ingested order | `models/aggregator.py` |
| `mezze.terminal.transaction` | integrated card / cash-machine request, 10 normalized states | `models/mezze_terminal_txn.py` |
| `mezze.payment.device` | terminal / register / cash machine | `models/payment_platform.py` |
| `mezze.payment.qr` | bank-app QR, generate + manual confirm | `models/mezze_payment_qr.py` |
| `mezze.payment.reconciliation` / `.line` | end-of-session settlement vs expected | `models/payment_reconciliation.py` |
| `mezze.reversal` | an open payment reversal needing resolution | `models/mezze_reversal.py` |
| `mezze.einvoice` | e-invoice document (authority API is a TODO seam) | `models/mezze_einvoice.py` |
| `mezze.outbox.event` | **the** transactional outbox — ordered, claimable, retryable, dead-letterable | `models/outbox_event.py` |
| `mezze.sync.outbox` / `.cursor` | terminal-side change journal — **declared, zero writers** | `models/mezze_sync_outbox.py` |
| `mezze.sync.applied` / `.log` | cloud reconcile ledger + per-order sync audit | `models/mezze_sync_applied.py`, `mezze_sync_log.py` |
| `mezze.audit.log` | append-only business + security audit (~80 event types) | `models/mezze_audit_log.py` |
| `mezze.setting.def` / `.config.value` / `.config.template` / `.line` / `.assignment` / `mezze.settings` | the 7-scope configuration platform | `models/config_platform.py` |
| `mezze.api.nonce` / `mezze.rate.limit` / `mezze.secret.store` / `mezze.emergency.access` | replay protection, fixed-window limiter, envelope crypto, break-glass | `models/` |
| `mezze.printer` / `mezze.hw.job` | network printer + print/drawer idempotency ledger | `models/hardware.py`, `hw_job.py` |
| `mezze.golive.validator` / `mezze.onboarding` / `mezze.productization` | 77 checks, 13 derived steps, release identity + support bundle | `models/golive.py` etc. |
| `mezze.cart.pricing` | the one canonical pre-fire pricer | `models/cart_pricing.py` |
| `mezze.kitchen.readiness.mixin` | batched kitchen-ready computation | `models/kitchen_readiness.py` |
| `mezze.ck.request` | central-kitchen requisition | `models/ck_request.py` |
| `mezze.campaign` / `mezze.feedback` | marketing campaign + guest rating | `models/campaign.py`, `feedback.py` |
| `mezze.payment.provider` / `mezze.payment.transaction` | **dead** — never read anywhere | `models/mezze_payment.py` |

---

## F. END-TO-END WORKFLOWS (reconstructed from code)

**Counter sale (Owl Register).**
`/mezze/start` → pick branch → `/mezze/pos` mints a per-terminal token → `/bootstrap` → tap products (configurator for modifiers/combos) → **client-estimated** total on screen → **Charge** → `/orders/sync {draft:true}` (server prices and returns the authoritative total) → payment screen → `/orders/pay` per tender (server-authoritative amount, row lock, `tender_key`) → at remaining≤eps `action_pos_order_paid()` → loyalty accrual → receipt from `/payment/breakdown` → optional `/hw/print/receipt`.
⚠️ Counter orders produce **no kitchen tickets** on pay — the cashier must press **Fire**, which currently double-appends the cart.

**Dine-in.**
Floor → tap table → `/mezze/pos?table_id=` → `_resolve_table_context` validates → resume the earliest draft → build → **Send to table** (`/orders/sync`, safe) or **Fire** (`/orders/fire` → `_do_fire`: advisory lock → idempotency by `fire_uuid` → `_make_station_tickets` splits by station → outbox → bus) → guests eat → additional courses re-fire the delta → **Split** (`/split/state` → `/split/commit` with an optimistic revision) → pay per check → full settlement releases the table.
⚠️ Resuming a table rebuilds lines **stripped of modifiers, notes and combos**, and the next sync destroys them server-side.

**Kitchen.**
`_do_fire` → one `mezze.kds.ticket` per station (routing by English keyword) → outbox event → post-commit dispatch → `bus.bus` → KDS polls `/bus/poll` every 4s → cook bumps `fired→accepted→preparing→ready→served` (skips legal, backward only via one-step Recall) → `served` and `cancel` are absorbing. **No expo, no packing screen, no audible alert, no cancel button, no auto kitchen print.**

**Drive-thru.**
New car (lane + vehicle) → build on the Register's own catalogue → `/drivethru/quote` (server-priced) → `/drivethru/create` (draft order, `lane_sequence` from a PG sequence, OCB confirm) → kitchen cooks → board auto-advances `preparing→ready` → **Call forward** claims `service_sequence` once under `FOR UPDATE` → pay at the window → **Hand off**, which re-checks paid + kitchen-ready + at-the-right-window inside the transaction → `departed`. Terminal states are closed; repeating the ending action returns `{ok:true, unchanged:true}`.

**Guest QR order.**
Staff mint `/qr/table_link` → guest scans → `qr.html` holds only `(table_id, qr)` → `/qr/menu` → build (⚠️ **hardcoded 12% service + 14% VAT + EGP** shown to the guest) → `/qr/order` sanitises client lines and rings through the **same** `_do_fire` core as a waiter → `/qr/bill` → `/qr/pay` (tip + settle in one savepoint) or `/checkout/table/pay_online` → track via an opaque hashed status token.

**Delivery (COD).**
Storefront → pick zone → server validates zone/COD/hours/minimum → **real unpaid `pos.order`** + `mezze.delivery` + fee line (untaxed) → kitchen fires → `assigned → dispatched → out_for_delivery` (courier freed on terminal) → `/delivery/collect` row-locks and records exactly one payment, idempotent on `cod-<id>`.
⚠️ 3 of 4 creation paths omit `payment_mode`, so prepaid and online deliveries are permanently recorded as uncollected COD.

**Refund.** `/orders/refund` reconstructs lines server-side, enforces a per-line quantity ceiling and an order-level money ceiling **in integer minor units** under a per-original advisory lock, then creates the negative order. ⚠️ **No production UI reaches it**, and the refund is always booked to the config's *first* payment method.

**End of day.** `/sessions/<id>/close/preview` shows opening float, cash taken and expected → blocked while orders are open → `/sessions/<id>/close` delegates to native `action_pos_session_closing_control()`. ⚠️ **No counted amount is accepted, no discrepancy is computed, no audit row is written.** The screen tells the cashier to count the drawer against the figure — outside the software.

---

## G. HIDDEN / EXPERIMENTAL / UNFINISHED

- **89 of 197 routes (45%) have no production front-end caller**; **25 have neither a caller nor any test reference** — pure dark code, including `customer/deposit`, `customer/settle`, `hardware/print/kitchen`, `orders/exchange`, `giftcard/issue`, `promo/list`, `delivery/zone/save`, `delivery/couriers`, all five `ck/*`, `orders/kds`, `admin/audit/export`, `sync/v1/pull`, and three `w1/*`.
- **43 routes are reachable only from the non-production prototype** — the entire W1 finance/GL/reversal surface, marketing, clock, waste, gift-card balance, loyalty redeem, quick keys, CFD push, `/branches`, `/ck/request`.
- **Feature flags:** 76 of 101 catalog settings are `disabled`, 7 `hidden`. Runtime flags default to the *safe* side (`terminal_simulator_enabled` off, `webhook_allow_*` off) except `allow_manager_elevation`, whose OFF default hides Void and End-of-day.
- **Dead code found:** `mezze.payment.provider` and `mezze.payment.transaction` (never read), `mezze.sync.outbox`/`.cursor` (zero writers), `/orders/kds`, the floor `bill` state, `cart.js` subtotal row, `manager_gate.js` `refund`/`exchange` actions (no caller), `test_client.html` (unserved), 8 dead design tokens, two orphan cron methods.
- **TODO markers: 7 total. Zero FIXME, zero XXX, zero HACK.** All 7 are external-integration seams (ETA, PSP, aggregator adapters) or stale. **No commented-out code of any significance exists** — a scan for ≥4-line code-shaped comment runs found only prose and rationale.
- **`demo/` is not wired into the manifest.** Three idempotent manual seeds (images, pizza, promos), each documenting that it must be run by hand. Nothing loads them automatically — including the tests, which provision their own hermetic fixtures.
- **Deliberate, documented omissions** (not defects): item-level KDS bump, KDS priority, split-by-seat, route optimisation/GPS, `hr.employee` payroll linkage, IoT Box.

---

## H. TEST COVERAGE OBSERVATIONS

**99 files · 28,308 lines · 1,200 test methods · 291 `browser_js` call sites across 22 files · 61 Hoot JS tests · 8 real-thread concurrency harnesses (evidence, not regression).** All 93 test modules are imported — zero dark test files. The suite is hermetic and passes on `--without-demo=all`.

**Deep:** money invariants, order FSM, refund ceilings, authz + endpoint classification (structurally gated), outbox/webhook under real concurrency, station enrolment crypto (87 tests), split bill (66), kiosk configuration (82), drive-thru (~145 across 10 files), combos (49), reservations/floor, product-config sharing.

**Zero coverage on:** offline/edge sync (whole subsystem), e-invoicing, W1 finance/GL/reversals (13 of 17 routes), central kitchen (all 5 routes, including real MO and picking creation), marketing/campaigns, time clock, waste, gift cards, loyalty redemption, CFD, per-aggregator adapters, quick keys. **17 of 58 models are never named in any test. 83 of 197 routes (42%) have no textual reference in any test file.**

**The confidence caveat that matters most: 497 of 1,200 tests (41%) run with `mezze_bridge.api_security = 'observe'`** — authorization evaluated and audited but never blocking — while the shipped default is `enforce`. The module's own RC6 post-mortem says exactly this: *"a test that proves this in observe mode proves nothing about the product as it ships."* Compounding it, three sources disagree on the shipped posture: `main.py:544` docstring says "default observe", `main.py:555` code says `or 'enforce'`, `golive.py:95` says `or 'observe'`.

**The 32 current failures are all browser/CDP-driven, not domain logic** — but two are functional: `TestRegisterSessionIsolation` (13/15, the *only* class running the shipped `enforce` posture — so the RC6 token-eviction fix is currently unevidenced) and `TestOrderActionsUi` (**6/6, 100% red** — comp/void/fire wiring in the real Register is unproven). `TestMediaPreferences` (10/16) leaves the OS-level high-contrast contract unverified. 16 of the 32 are the same missing `default_branch_id` fixture pin already fixed for `TestDeliveryDriveThruUi`.

**No real payment device has ever been exercised by code in this repository.**

---

## I. FEATURE COUNTS

Counted over the ~330 discrete sub-features enumerated in §B.

| Status | Count | Share |
|---|---:|---:|
| ✅ Production-ready | 78 | 24% |
| 🟢 Implemented | 71 | 22% |
| 🟡 Partial | 62 | 19% |
| 🟠 UI-only / no production UI | 36 | 11% |
| 🔵 Prototype / experimental | 6 | 2% |
| ⚪ Planned (spec/doc/flag only) | 47 | 14% |
| 🔴 Broken / dead | 30 | 9% |

By category (total sub-features):

| Category | Total | ✅+🟢 | Category | Total | ✅+🟢 |
|---|---:|---:|---|---:|---:|
| POS / Order Entry | 48 | 24 | Reservations / Waitlist | 20 | 9 |
| Tables / Floor Plan | 26 | 14 | Delivery / Aggregators | 24 | 9 |
| Drive-Thru | 17 | 13 | Products / Menu / Pricing | 20 | 8 |
| Self-Service / QR / Online | 15 | 10 | Inventory | 14 | 6 |
| Payments | 37 | 21 | Purchasing | 7 | **0** |
| Checkout / Receipts / Hardware | 21 | 8 | Multi-branch / Config | 18 | 9 |
| KDS / Kitchen | 24 | 12 | Reporting / Live Ops | 24 | 8 |
| Central Kitchen | 9 | 3 | Employees / Security / Sessions | 30 | 17 |
| | | | Platform / Offline / Realtime | 20 | 10 |

---

## J. PRODUCT MATURITY (0–100, on implementation depth)

| Dimension | Score | Why |
|---|---:|---|
| **POS core** | **72** | Modifiers/combos/86/park/split are excellent and server-authoritative. Held back by three live defects (Fire double-append, recall strips configuration, notes not persisted), no weighted products, no barcode in the production client, and no discount UI. |
| **Restaurant operations** | **74** | Service modes, coursing, table ops and guest counts are real and well-guarded. Coursing has no reachable UI; courses persist in config params forever. |
| **Table service** | **68** | Transfer/merge/assign/guests are genuinely well-engineered (ordered locks, financial safety gate, KDS re-homing). But the floor is read-only, has no responsive layout, ships a dead state, and there is no waiter model at all. |
| **Checkout / payment** | **70** | The money spine is the best part of the product — idempotent, row-locked, server-authoritative, no fake-able path. Loses heavily on **zero real devices**, no cash rounding, `amount_return` never written, refunds hardcoded to the first payment method, and Paymob orphaned. |
| **Kitchen / KDS** | **66** | The state machine and its concurrency model are excellent. Routing is a hardcoded English keyword matcher, there's no expo/packing/audible alert/cancel button, recall corrupts prep-time data, and delivery is a 4s poll. |
| **Delivery** | **62** | COD is exemplary. Zones have no geography, ETA is a static per-zone integer, dispatch exists only in the prototype, `payment_mode` is mislabelled on 3 of 4 paths, and object scope is unwired on two money routes. |
| **Reservations** | **58** | Clean FSMs and an idempotent POS handoff. Undermined by a real double-booking hole on `confirmed`, no time editing, no calendar, no guest notification, no no-show sweep, and an unbounded availability scan. |
| **Customers / loyalty** | **55** | House-account credit is genuinely excellent — native-derived, no second ledger, three policies, concurrency-tested. Everything else is thin: no address book, no history, no tags; the loyalty program is never provisioned; redemption is client-trusted. |
| **Inventory** | **60** | Correctly delegates sales deduction to Odoo, then adds a real costing layer (BoM explosion, theoretical-vs-actual variance, burn-rate, `stock.scrap` waste, commissary MO→transfer). No lots, no expiry, no reorder rules, no UoM conversion, no production UI, and CK has zero tests. |
| **Reporting** | **45** | The endpoints are rich and the metrics are real. But the four production reporting workspaces **render blank on success**, there are no Odoo pivot/graph reports, no void or discount report, and the strongest reports (delivery, self-order, reconciliation) have no UI at all. Native POS Analysis by cashier/terminal partially rescues this. |
| **Multi-branch** | **65** | `_resolve_config` and the launcher are the best-designed multi-branch pieces I found — token-authoritative, fail-closed, record-rule-respecting. But ~15 collection endpoints ignore the scope helper and the module ships **zero `ir.rule` records**. |
| **Offline / reliability** | **30** | The *server-side* durability story is outstanding (transactional outbox, post-commit dispatch, dead-lettering, dual idempotency, PG-retry discipline). The *client* has no offline capability whatsoever, the terminal sync outbox has zero writers, and no Windows station client exists. Score reflects a one-ended pipe. |
| **Integrations** | **35** | Native Odoo reuse is genuine and correct. Every *external* integration is either delegated to a stock Odoo module or a simulator. Zero aggregator vendors, zero card terminals, zero cash machines, ZATCA absent, Paymob orphaned, WhatsApp a stub. ESC/POS is the one real protocol. |
| **Security / control** | **74** | Architecture is well above typical Odoo custom work: one gate, least-privilege capabilities, ECDSA device identity, atomic limiter, envelope crypto, real SSRF defence, durable PII-safe audit, tamper-proof security config. Deducted for signing and FSM defaulting to observe, 6 unclassified routes, 50/63 object scopes unwired, no `ir.rule`, an `ALL_CAPABILITIES` bug, and a fail-open gate. |
| **UX** | **68** | Real design system (12 themes × 39 tokens, WCAG-gated generator), best-in-class reduced-motion and high-contrast, 202 aria attributes in Owl templates, a thoughtful focus trap. Deducted for 31% token adoption, generator drift, 11 of 19 fonts being byte-identical duplicates, 2 focus traps for ~17 modal contexts, zero skip links, zero `sr-only`, and no guided tour outside the prototype. |
| **OVERALL PRODUCT** | **62** | A serious, well-architected backend with a real but partial front-end, honest self-documentation, and a large gap between what the prototype demonstrates and what the shipped app does. |

---

## K. TOP 20 STRONGEST IMPLEMENTED CAPABILITIES

1. **The money invariant discipline** — every tender path converges on one guarded `pos.payment` write; no second money engine.
2. **No browser path can fake a payment** — client outcomes are advisory; divergence is audited, never obeyed.
3. **Split Bill V2** — durable server-side family relations where native Odoo uses browser state; 66 tests.
4. **Refund ceilings in integer minor units** with a pure domain module *plus* an ORM `@api.constrains` backstop that also closes the bypass for core POS UI and direct `sync_from_ui`.
5. **The transactional outbox** — `FOR UPDATE SKIP LOCKED`, strict per-aggregate ordering, visibility timeout, backoff, dead-letter, replay.
6. **Post-commit dispatch arming** — one hook per request is what makes KDS latency sub-second rather than cron-bound.
7. **The KDS state machine** — forward-only with legal skips, row-locked, idempotent, terminal-absorbing, browser-proven under concurrency.
8. **The drive-thru terminal-state contract** — explicit `LEGAL_TRANSITIONS`, enforced at the single mutation point *and* the legacy `write()` back door; closes a real cancel→rehandoff defect.
9. **The drive-thru handoff gate** — three conditions evaluated live inside the mutating transaction, not as a disabled button.
10. **Station identity** — one-time HMAC-fingerprinted codes → ECDSA P-256 challenge (nonce burned before mint) → 900s session → signed lease, with honest TPM/DPAPI/software levels.
11. **Surface confinement** — a till is a till; typing `/odoo` into it reaches nothing.
12. **`_resolve_config`** — a scoped principal naming another branch is ignored *and logged*, not obeyed.
13. **The launcher** — lists branches using the user's own env, so record rules do the filtering and it can never widen access.
14. **Customer credit** — derived from native `partner.credit` with no second ledger; deposits and settlements are real posted `account.payment` with FIFO reconciliation.
15. **COD collection** — row-locked, idempotent, exactly one payment; the test collects three times and asserts one.
16. **`_sanitize_customer_lines`** — a whitelist, not a blacklist: a public client physically cannot express a price.
17. **Public status tokens** — 128-bit raw returned once, only the SHA-256 stored, TTL + revocation, generic 404, rate-limited.
18. **The shared product-config rules module** — one frozen definition consumed by both the Register and the drive-thru, structurally enforced by tests. Better than native Odoo, which uses separate combo and attribute popups.
19. **The go-live validator's refusal to flatter itself** — `NOT TESTED` is first-class and unupgradeable; a simulator in production is a hard FAIL.
20. **`domain/redaction.py` and `domain/webhook.py`** — a genuine structural redactor and real SSRF/DNS-rebind defence, not keyword blocklists.

---

## L. TOP 20 BIGGEST INCOMPLETE AREAS

1. **Offline** — no client persistence of any kind; a network failure loses the tender.
2. **Purchasing** — entirely absent.
3. **Real payment hardware** — no card terminal, no cash machine, ever exercised.
4. **Aggregators** — no vendor protocol code exists.
5. **Reporting UI** — the four production workspaces render blank on success.
6. **Cash control** — no counted amount, no discrepancy, no cash in/out, no X report, no audit row on close.
7. **Refund/exchange/reconciliation** — backend-complete, zero production UI.
8. **Prep-station routing** — hardcoded English keywords, no config, Arabic-blind.
9. **Realtime to the Register** — it subscribes to nothing; the waiter bell and 86 broadcast have no consumer.
10. **Floor-plan authoring** — read-only; no editing, no zoom, no responsive layout.
11. **Central kitchen** — real `mrp`/`stock` machinery with zero tests, no seed data, no shipping UI, unscoped branch input.
12. **Delivery dispatch** — prototype-only; production is a read-only list.
13. **Guest communication** — no reservation confirmation, no waitlist notification, WhatsApp a stub.
14. **Printed receipt compliance** — no Arabic, no QR/barcode, no VAT registration line.
15. **E-invoicing** — ETA delegated to a non-dependency; ZATCA is a Selection value.
16. **The settings catalog** — 76 of 101 inert; not one business setting.
17. **Config templates** — no API can add a line, so the publish/version machinery has no content.
18. **Object scope** — 50 of 63 Category-A routes unwired, including money routes; zero `ir.rule` records.
19. **Customer CRM** — a picker, not a CRM: no address book, history, notes, tags or segmentation.
20. **Physical certification** — every on-site acceptance directory is an empty placeholder.

---

## M. THINGS THAT LOOK FINISHED BUT AREN'T

1. **"Works fully offline — syncs to Odoo on reconnect"** (`pos.html:1367`) backed by `var offline=false, qc=3;` — the "3 queued orders" is a literal. Toggling changes a CSS class. **The single most dangerous claim in the product.**
2. **The Z report / shift close** — `pos.html:1896-1910` hardcodes gross EGP 38,940, VAT EGP 4,701, ETA 142/142; over/short is `var exp=14180`. Only the Close button is real.
3. **Live Ops branch bars and stock alerts** — `var BRANCHES=[…]`, `var AL=[…]` fixture arrays drawn first.
4. **Prototype money generally** — a hardcoded 10% discount and 12% service + 14% VAT that change the screen and never reach the order.
5. **Integrated terminals and cash machines** — full state machines, force-done, reconciliation flags, 18 tests, and `REGISTRY = { test: simulatorAdapter }`.
6. **Aggregators** — three models, encrypted secrets, HMAC, commission accounting, a docs file, vendor names in every docstring, and **zero vendor protocol code**. Also unconfigurable: no view exists for the channel or SKU map.
7. **Refunds** — the best-engineered code in the module, with no production button.
8. **Comp and Void** — real, audited, approval-gated, and **hidden by default**, because `terminal` lacks the capability and `allow_manager_elevation` defaults to `'0'` with no data file setting it.
9. **The Onboarding / Go-Live console** — has no route, and needs the shared admin token that production disables. Unusable in exactly the environment it exists to certify.
10. **Quick keys** — full pin/reorder API, bus broadcast, audit trail, shipped in the bootstrap payload, and discarded by the production client. Zero tests.
11. **The 101-setting configuration platform** — 18 work, all cosmetic.
12. **Config templates** — publish, version, assign, cascade… over content no API can create.
13. **The `brand` scope** — writes and audits a row the resolver never reads.
14. **"Bill requested"** — legend, CSS and mapping ship for a state the server cannot emit.
15. **The cart Subtotal row** — reads a getter that doesn't exist, so it can never render.
16. **Split "Evenly"** — the tab, the preview and a correct, unit-tested `even_amounts()` — and no endpoint.
17. **Change** — displayed on the receipt and the CFD, never persisted; overpay is rejected, so `amount_return` is structurally always 0.
18. **Gift cards** — issue/balance/redeem/sale all work, and selling one from the Owl register issues no card.
19. **Loyalty** — points, rewards, history, four money-path hooks — keyed on a program nothing ever creates.
20. **Waitlist "notify"** — the button, the state and the filter exist; nothing reaches the guest.
21. **Two-window drive-thru** — configurable, gated, tested by raw HTTP, and **UI-deadlocked**: no client can reach the pickup window the gate requires.
22. **Line notes** — typed, displayed, transmitted, dropped.
23. **The endpoint-coverage gate** — reports 100% while six routes, four of them financial, sit outside the registry, because its regex can't span a decorator ending in a comment.

### Features stronger than they appear

The **transactional outbox**, the **security gate and its durable audit**, **station identity crypto**, the **sync server** (dual idempotency, per-event savepoints, dead-lettering, commutative deltas), **`mezze.cart.pricing`**, **`_menu_domain`**, the **kitchen-readiness batching**, **`mezze.hw.job`** print idempotency, and the **83% of the settings catalog that honestly marks itself disabled with a reason** are all better than their surface presentation suggests.

### Hidden competitive advantages

- **Server-authoritative split bill with durable family relations** — native Odoo keeps this in browser state.
- **Refund ceilings enforced at the ORM layer**, so they hold for core POS UI and offline sync too, not just Mezze's own controller.
- **One fire core serving five channels** (waiter, QR, kiosk, online pickup, drive-thru) — combos, half-and-half, station routing, idempotency and locking written once.
- **A drive-thru handoff gate that cannot be smuggled past by a stale client.**
- **Device identity with honest hardware-backing levels** — most POS products claim TPM or say nothing.
- **A go-live validator that actively refuses to over-claim**, including failing its own simulators.
- **Print/drawer idempotency with stale-command expiry** — a dead-letter replay can never pop a till.
- **Structured MENA delivery addresses and bilingual customer surfaces at 100% key parity.**

---

## N. FINAL CONCLUSION — what can Mezze POS actually do today?

**Mezze POS can run a real restaurant shift, end to end, on Odoo 19 Community — provided the shift is cash-and-manual-card, on-premise, and English-printed.**

It can open a branch, ring up a check with modifiers and combos, hold and resume it, split it by item, route it to prep stations, show it on a kitchen board, take cash and manually-recorded card tenders with genuine idempotency and audit, comp or void with manager approval, seat a reservation, work a waitlist, take QR/kiosk/storefront orders with server-authoritative pricing, run a full drive-thru lane with a real vehicle FSM and a hard handoff gate, deliver with COD, and close the session through Odoo's own accounting. Underneath that sits an unusually serious platform: one authorization gate, a real transactional outbox, cryptographic device identity, envelope-encrypted secrets, and an append-only audit.

**What it cannot do today:** operate without the server, take a payment on any real terminal or cash machine, receive an order from any named aggregator, purchase anything, print an Arabic or tax-compliant receipt, reconcile a cash drawer, show a manager a dashboard in the production app, refund from the production till, or configure its own prep stations.

**The gap that matters most is not missing features — it is the distance between the prototype and the product.** `static/pos.html` is the most complete, most bilingual, most impressive artifact in the repository, and it is explicitly not production. 45% of the API has no production caller. When someone demos Mezze from that file, they are demonstrating fabricated totals, a fake offline mode, a hardcoded Z report, and a dozen workflows the shipped Register does not have.

**The three defects to fix before any competitive comparison:** Fire double-appends the cart, recall/resume silently strips and then destroys line configuration, and line notes are never persisted. All three corrupt real orders in normal use, and none is caught by the current tests.

**The codebase's most valuable trait is that it mostly tells the truth about itself** — `seat_reason: 'no_seat_model'`, `provider_integration_pending`, `NOT TESTED` as an unupgradeable status, 76 settings marked disabled with reasons, and a test literally named `test_unimplemented_settings_are_disabled_not_faked`. That honesty is rare, it is real, and it stops at the prototype's front door.
