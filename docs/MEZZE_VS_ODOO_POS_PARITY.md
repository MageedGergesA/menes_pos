# Mezze vs Odoo POS — Feature Parity Report

**Compared:** Odoo 19 Community `point_of_sale` + the 35 `pos_*` modules that ship with it, against `mezze_bridge` @ `feature/split-bill-v2` (working tree, discounts included).
**Method:** source inventory of core POS config switches, screens, popups and Actions-dialog buttons, mapped against traced Mezze implementations. Verified at source, not from documentation.

---

## 0. The structural difference that explains most of this table

Mezze is **not an extension of the Odoo POS front-end.** It is a standalone Owl app with its own asset bundle that loads Owl + `@web/core` and nothing from `point_of_sale/static`. It talks to Odoo through its own JSON API and writes through `pos.order.sync_from_ui`.

That is a deliberate, defensible choice — it is what makes an Arabic-first, branch-scoped, station-authenticated till possible on Community. But it has one unavoidable consequence:

> **Every front-end feature of Odoo POS is opt-in for Mezze, and starts at zero.**

Nothing arrives for free. Anything native POS does in the browser — the numpad, the scale, barcode, lot selection, the Actions dialog, the ticket screen, the cash-in/out popup — exists in Mezze only if it was rebuilt.

The back-end half is the opposite: Mezze reuses Odoo wholesale (stock deduction, tax `compute_all`, pricelists, `loyalty`, `pos_online_payment`, session closing/accounting). That reuse is real and correct.

**A second, quantified consequence.** Of 25 headline `pos.config` switches an admin sees in Odoo's own POS settings, **Mezze reads 5**:

| Reads | Ignores completely |
|---|---|
| `limit_categories`, `default_fiscal_position_id`, `available_pricelist_ids`, `tip_product_id`, `use_presets` (kiosk only) | `receipt_header`, `receipt_footer`, `basic_receipt`, `manual_discount`, `restrict_price_control`, `cash_rounding`, `rounding_method`, `iface_tipproduct`, `set_tip_after_payment`, `iface_electronic_scale`, `note_ids`, `default_bill_ids`, `iface_printbill`, `iface_splitbill`, `amount_authorized_diff`, `set_maximum_difference`, `use_fast_payment`, `ship_later`, `fiscal_position_ids`, `iface_tax_included` |

An operator who configures the POS through Odoo's settings page will find most of those switches have no effect on the Mezze till.

---

## 1. Order entry

| Odoo POS | Mezze | Notes |
|---|---|---|
| Product grid, categories, search | ✅ full | Mezze's is image-led with real category counts; arguably better |
| **Numpad (qty / price / discount / backspace)** | ❌ | Mezze has +/− steppers only. No price entry, no qty typing |
| **Barcode scanner** | ❌ in production | Core has `barcode_reader_service` + nomenclature fallback. Mezze's bootstrap *sends* `barcode`/`default_code`; the Owl client discards both at map time. Only the non-production prototype scans |
| **Electronic scale** (`iface_electronic_scale`, `scale_screen`) | ❌ | No weighed products at all — `_loadOrderLines` does `Math.round(l.qty)`, destroying fractional quantities |
| Product configurator (attributes) | ✅ **better** | One frozen rules module shared by the Register *and* the drive-thru; core uses separate popups |
| Combos | ✅ full | Real `product.combo`, Odoo's own proration |
| **Optional / upsell products popup** | ❌ | Core `optional_products_popup`. Mezze has `/ai/upsell` (a genuine market-basket miner) but the production cashier never calls it |
| **Product Info popup** (margin, stock, pricelists) | ❌ | Core Actions button |
| Line notes | 🟡 partial | Mezze has free-text per line — but **it is never persisted**: `line_vals` has no `customer_note`. Core also has *predefined* notes (`note_ids`); Mezze has none |
| **Order-level customer note** | ❌ | Core Actions → Customer Note |
| **Lot / serial selection** (`select_lot_popup`) | ❌ | Mezze hardcodes `'pack_lot_ids': []` on every path |
| **Presets** (`pos.preset` — order type + own pricelist + fiscal position + time slots) | ❌ in Register | v19 feature. Mezze reads it only in the kiosk config path and reimplemented order type as a 2-value `mezze_service_mode` + free-text `mezze_channel` |
| **Refund from the till** | ❌ no UI | Core Actions → Refund. Mezze's backend is the best-engineered code in the module (integer-minor-unit ceilings, advisory lock, ORM backstop) and **no button reaches it** |
| **Order edit tracking** (`order_edit_tracking`) | ❌ | |
| **Ship later** (`ship_later`) | ❌ | |
| Park / resume | ✅ **better** | Mezze parks server-side with an explicit `mezze_parked` flag; core uses order tabs |
| **Ticket screen** (search past orders, reprint, filter, paginate) | 🟡 | Mezze has an Orders workspace (Open/Parked/Completed + search); no reprint of an older receipt |
| Recall a draft | 🔴 **lossy** | `/orders/get` omits `attribute_value_ids`, note and combo, so resuming a table rebuilds bare lines — and the next sync **destroys them server-side** |
| Fire to kitchen | 🔴 **defect** | `_ensurePersisted()` writes the whole cart, then `/orders/fire` sends the same whole cart, which APPENDS. First Fire doubles the order |

## 2. Pricing, discounts, taxes

| Odoo POS | Mezze | Notes |
|---|---|---|
| Line % discount (`manual_discount`) | ✅ **NEW** | Just built, with tiered per-role ceilings core does not have |
| Global order discount (`pos_discount`) | ✅ **NEW** | Mezze applies the % to every eligible line, keeping each line's own tax — core adds one discount product line and must pick a single tax for a mixed basket |
| **Discount authority / ceilings** | ✅ **Mezze only** | Core has one boolean (`restrict_price_control`) and no ceilings. Mezze: cashier 10% / supervisor 25% / manager unlimited, branch-configurable, manager PIN to exceed, `discount.override` audited |
| **Manual price override** | ❌ | Core numpad Price mode + `restrict_price_control`. Mezze's Owl client never emits `price_unit` |
| **Pricelist switch on the order** | ❌ | Core Actions → Price list. Mezze always uses `config.pricelist_id` |
| **Customer-specific pricelist** | ❌ | `property_product_pricelist` has **0 occurrences** in Mezze. A B2B partner is charged branch list price |
| **Fiscal position switch** | ❌ | Core Actions → Set fiscal position. Mezze applies `default_fiscal_position_id` only |
| **Tax regime toggle** (`tax_regime_selection`, Actions → Tax) | ❌ | |
| Tax computation | ✅ native | Both use `account.tax.compute_all` |
| **Cash rounding** (`cash_rounding`, `rounding_method`) | ❌ | Zero occurrences in Mezze |
| Tips | 🟡 | Core: `iface_tipproduct` + `set_tip_after_payment` (post-payment adjustment). Mezze: tip works on the **QR guest path only**; the cashier cannot take one |

## 3. Loyalty, coupons, gift cards

| Odoo POS (`pos_loyalty`, installed in every Mezze DB) | Mezze | Notes |
|---|---|---|
| **Enter Code** (coupon / gift card / promo code) | ❌ | Core Actions button |
| **Reward** (redeem points) | ❌ no UI | `/loyalty/redeem` is correct and unreachable from the Register |
| Points earning | ✅ | Wired into 4 money paths |
| **Loyalty program provisioning** | 🔴 | `_loyalty_program()` only *searches* for `'Mezze Rewards'`. Nothing ever creates it → loyalty is inert on a fresh install. Gift cards self-provision; loyalty doesn't |
| Gift card as a tender | 🟡 | Server-validated and correct, but not in `SUPPORTED_TENDER_MODES` — unreachable from the Owl till |
| Gift card sale mints a card | 🔴 | Only on the atomic-paid sync branch, which the draft-only Owl cashier never takes. Selling one from the Register issues **no card** |
| **eWallet** | ❌ | Core has Use/Refund eWallet buttons |
| Promotions / auto-discounts | 🟡 | Real engine, wired to the **customer storefront only** — the till gets no promotions |
| Buy-X-get-Y, free-product rewards | ❌ | Listed in `PROMO_TYPES`, returns `0.0` |
| **Reward-line metadata** | ❌ | `pos_loyalty` adds `is_reward_line`/`reward_id`/`coupon_id`/`points_cost` to `pos.order.line`. Mezze writes anonymous negative lines instead — which is why `sync_from_ui` strips them and `main.py` needs a create-draft-then-patch workaround |

## 4. Restaurant / table service

| Odoo POS (`pos_restaurant`) | Mezze | Notes |
|---|---|---|
| Floor plan **rendering** | ✅ **better** | Live state, covers, dwell, money-on-floor, reservation holds, non-colour-safe status |
| Floor plan **editing** (create/move/resize/rotate tables) | ❌ | Core has a full edit mode. Mezze's only `restaurant.table` write in the entire addon is `mezze_qr_token` — authoring is 100% Odoo backend |
| Table transfer / merge | ✅ **better** | Ordered advisory locks, KDS ticket re-homing, and a financial safety gate (409 if either side has payments) core does not have |
| Guests count | ✅ | |
| **Course management** | 🟡 backend only | Core Actions → Course / Transfer course. Mezze's `/courses/*` works; its only UI is a static page **no route serves**, authenticating by token in the URL |
| Split bill | ✅ **much better** | Core keeps it in browser `uiState`. Mezze has durable family columns on `pos.order`, row locks, optimistic revisions, combo atomicity, fired-KDS redistribution, backend views. 66 tests |
| **Split evenly** | ❌ | The pure function exists and is unit-tested; no endpoint calls it |
| **Split by seat** | ❌ both | Neither has a seat model. Mezze declares it honestly (`seat_reason: 'no_seat_model'`) |
| **Print bill** (`iface_printbill`) | ❌ | Core Actions → Bill (pre-payment bill). Mezze prints only at payment |
| **Kitchen Display** | ✅ **Mezze only on Community** | Core's Preparation Display is Enterprise. Mezze built its own: row-locked FSM, forward-only with legal skips, cancel-as-projection, Arabic RTL |
| Kitchen printing | 🟡 | Both print kitchen tickets. Mezze routes per station — but **never auto-prints on fire**, only on request, and prints no modifiers or notes |
| Tip after payment | ❌ | `set_tip_after_payment` unread |

## 5. Payments

| Odoo POS | Mezze | Notes |
|---|---|---|
| Cash, multiple tenders, partial | ✅ **better** | Per-tender idempotency via `unique(pos_order_id, mezze_tender_key)`; server-authoritative amounts; no browser path can fake a payment |
| **Change / overtender** | 🔴 | Core computes and stores `amount_return`. Mezze **rejects** overpay server-side, so `amount_return` is structurally always 0 and "Change" on the receipt is display-only |
| **Fast payment methods** (`use_fast_payment`) | ❌ | v19 one-tap validate from the product screen |
| **Payment terminals** (Adyen, Stripe, Razorpay, Viva, Pine Labs, QFPay, Mercado Pago, Six) | ❌ **none** | 8 vendor modules ship with core. Mezze's `terminal_service.js` is `REGISTRY = { test: simulatorAdapter }` — real providers are refused server-side rather than faked |
| Integrated-terminal orchestration | ✅ **better shape** | 10 normalized states, uncertain-never-auto-retried, manager Force Done with its own provenance, reconciliation flag. Just no device behind it |
| **Glory cash machine** (`pos_glory_cash`) | ❌ | Ships in core; browser-welded to native `PosStore`, so Mezze cannot reuse it. Refused as `device_integration_pending` |
| Online payment (`pos_online_payment`) | ✅ native reuse | Mezze delegates to Odoo's own `/pos/pay` page |
| Paymob | 🟡 orphan | Creates a real `payment.transaction` with **no `pos_order_id`**, so it can never become a `pos.payment` |
| Bank-app QR | ✅ | Uses native `get_qr_code`; cashier-confirmed, provenance `'manual'` — same honesty as core's QR popup |
| **Customer account / credit** | ✅ **Mezze only** | Derived from native `partner.credit` with no second ledger; three policies, deposit + FIFO settle, concurrency-tested |
| **Cash in / cash out** (`cash_move_popup`) | ❌ | No endpoint, no model |
| **Money details / denomination count** (`default_bill_ids`, `money_details_popup`) | ❌ | |
| Payment reconciliation | ✅ **Mezze only** | Expected vs settlement per method/device, tolerance gate, manager approval. No UI though |

## 6. Receipts & printing

| Odoo POS | Mezze | Notes |
|---|---|---|
| On-screen receipt | ✅ | Mezze's is fully bilingual with per-rate tax lines |
| ESC/POS printing | ✅ | The only wire protocol Mezze implements itself (raw TCP :9100) |
| **Receipt header / footer** (`receipt_header`, `receipt_footer`) | ❌ | Unread by Mezze |
| **Basic / gift receipt** (`basic_receipt` — no prices) | ❌ | |
| **Arabic on the printed receipt** | 🔴 | `escpos.py` encodes `cp437` — Arabic prints as `?????`. Every printed label is a hardcoded English literal, not `_()`-wrapped. The *screen* receipt is fully bilingual |
| **QR / barcode on the printed receipt** | ❌ | No `GS ( k` anywhere. Core has `qr_code_popup` + receipt QR. Blocks a ZATCA/ETA signed QR |
| **VAT / tax-registration line on paper** | ❌ | Also absent: company address, cashier name, per-rate tax split, change, tip, logo |
| Reprint an older receipt | 🟡 | Endpoint supports it; no UI reaches it. Core has it on the ticket screen |
| **Retry-print popup** | ❌ | Core `retry_print_popup`. Mezze has a durable `mezze.hw.job` ledger instead — different, arguably better |
| **Email / SMS receipt** (`pos_sms`) | ❌ | |
| Print idempotency | ✅ **Mezze only** | `mezze.hw.job` unique key + stale-drawer expiry so a dead-letter replay can't pop a till |

## 7. Sessions & cash control

| Odoo POS | Mezze | Notes |
|---|---|---|
| Open session / opening control | ✅ native | |
| **Counted cash at close** (`closing_popup`, `money_details_popup`) | 🔴 **absent** | `/sessions/<id>/close` accepts **no counted amount**. Mezze computes *expected* and tells the cashier to count the drawer outside the software |
| **Discrepancy / over-short** | 🔴 absent | `cash_register_difference` is only ever **read**, in `/w1/gl/sessions`. Core enforces `set_maximum_difference` / `amount_authorized_diff` |
| **Maximum-difference enforcement** | ❌ | Unread |
| Session closing entry | ✅ native | Mezze delegates to `action_pos_session_closing_control()` |
| **Closing entry by product** (`is_closing_entry_by_product`) | ❌ | |
| Audit row on close | 🔴 | Mezze writes none |
| **X report** | ❌ both | Neither has a true mid-shift X report |
| Z report | 🔴 | Core's closing report is real. Mezze's is **hardcoded fixture data** in the non-production prototype (`var exp=14180`) |
| Shift handover | ✅ **Mezze only** | Device-level staff shift with PIN + revocable session |

## 8. Self-service & omnichannel

| Odoo POS | Mezze | Notes |
|---|---|---|
| Self-order kiosk (`pos_self_order`) | ✅ own build | Native kiosk requires an Adyen/Stripe terminal; Mezze's is pay-at-counter, bilingual, with idle privacy reset |
| Table QR ordering | ✅ own build | Server-authoritative pricing, token scoped to one table |
| Online storefront | ✅ **Mezze only** | Core has no POS storefront |
| **Guest-facing cart totals** | 🔴 | `shop.html` and `qr.html` hardcode 12% service + 14% VAT (and `'EGP'`) in the browser. `/shop/quote` exists and is correct — the kiosk uses it, these two don't |
| Delivery + COD | ✅ **Mezze only** | Real unpaid order, row-locked idempotent collection |
| Drive-thru | ✅ **Mezze only** | 4-station board, vehicle FSM with a closed terminal region, PG-sequence merge ordering, 3-condition handoff gate |
| **Aggregator integrations** | ❌ both | Neither ships a Talabat/Jahez/etc. adapter. Mezze has a hardened generic webhook for a format it invented |

## 9. Hardware

| Odoo POS | Mezze |
|---|---|
| Receipt printer (ESC/POS) | ✅ both |
| Cash drawer | ✅ both (Mezze: config-gated, default OFF, no call from the production cashier) |
| **IoT Box / hardware proxy** (`proxy_ip`, `other_devices`) | ❌ Mezze — Community has no IoT Box; Mezze drives hardware server-side by design |
| **Epson ePOS / iMin direct printers** | ❌ Mezze |
| **Barcode scanner** | ❌ Mezze in production |
| **Electronic scale** | ❌ Mezze |
| Customer display | 🟡 both — core has `customer_display`; Mezze's OCB is drive-thru only, CFD is prototype-driven |

## 10. Reporting & back office

| Odoo POS | Mezze | Notes |
|---|---|---|
| POS Analysis pivot/graph | ✅ inherited | Mezze's orders are real `pos.order`, and `pos_order_views.xml` adds **group-by Cashier and Terminal** — so Odoo's own pivot works for free |
| Session / order back-office views | ✅ native | |
| **Mezze's own reports** | 🟡 | Rich endpoints (ops, manager dashboard, HQ roll-up, GL, food-cost variance, burn-rate, delivery KPIs) — but the four production reporting workspaces **render blank on success**, and there are no pivot/graph reports of Mezze's own |
| **Back-office UI for Mezze models** | 🔴 | 56 models, **4** with any view, **one** menu tree. Reservations, waitlist, delivery, couriers, aggregators, campaigns, feedback, KDS tickets, audit log and the config platform have no backend screen at all |

## 11. Platform

| Odoo POS | Mezze |
|---|---|
| **Offline operation** | ✅ core (IndexedDB + sync) / 🔴 **Mezze has none** — zero `indexedDB`, zero service worker, no queue. A network failure loses the tender |
| Multi-session / multi-device | ✅ both |
| Branch scoping | ✅ **Mezze far stronger** — token-authoritative, fail-closed |
| Device identity | ✅ **Mezze only** — ECDSA P-256 enrolment, honest TPM/DPAPI/software levels, surface confinement |
| Audit trail | ✅ **Mezze only** — ~80 append-only event types |
| Arabic / RTL | ✅ **Mezze far stronger** — 94% staff coverage, 100% on customer surfaces, 92.8% logical-property CSS |

---

## 12. What Mezze has that Odoo POS does not

1. **Kitchen Display on Community** — core's Preparation Display is Enterprise-only.
2. **Drive-thru** — no core equivalent at any edition.
3. **Delivery with zones, fees, COD and courier dispatch.**
4. **Online storefront + table-QR ordering** wired to the same fire core.
5. **Reservations and waitlist** with proper FSMs and POS handoff.
6. **Discount ceilings by role** — core has one boolean, no tiers, no approval, no audit event.
7. **Customer credit / house accounts** derived from native `partner.credit`.
8. **Server-authoritative split bill** with durable family relations.
9. **Cryptographic station identity** and path-confined surfaces.
10. **An append-only business + security audit trail.**
11. **Payment reconciliation** (expected vs settlement per method/device).
12. **Food-cost variance, ingredient burn-rate, `stock.scrap` waste** with money impact.
13. **Central-kitchen requisition** on real MOs and pickings.
14. **Arabic-first bilingual UI** across staff and customer surfaces.
15. **Transactional outbox** with ordered delivery, dead-lettering and replay.

---

## 13. Summary

**Where Mezze beats core:** split bill, table transfer/merge, product configurator, branch scoping, device identity, audit, KDS on Community, and everything omnichannel (drive-thru, delivery, storefront, QR, reservations). The money spine — idempotent, row-locked, server-authoritative — is stronger than core's.

**Where Mezze is behind core, ranked by operational pain:**

| # | Gap | Why it hurts |
|---|---|---|
| 1 | **No offline** | Core keeps selling through a network drop. Mezze loses the tender outright |
| 2 | **No refund from the till** | Backend is done and ceiling-enforced; there is simply no button |
| 3 | **No cash counting / discrepancy at close** | A till that cannot reconcile its own drawer |
| 4 | **No payment terminal** | 8 vendor modules in core; Mezze has a simulator |
| 5 | **Fire double-appends; recall strips modifiers; notes not persisted** | Three defects that corrupt real orders in normal use |
| 6 | **No loyalty redeem / Enter Code, program never provisioned** | Loyalty is inert on a fresh install |
| 7 | **No barcode, no scale, no numpad, no price override** | Basic till affordances |
| 8 | **No pricelist switch, no customer pricelist, no fiscal-position switch** | Blocks B2B and multi-regime trading |
| 9 | **Arabic receipts don't print; no QR on paper** | Blocks ZATCA/ETA compliance in the target market |
| 10 | **No cash rounding, no cashier tips, no lots/serials** | |

**The honest one-line summary:** Mezze is a stronger *restaurant platform* than Odoo POS and a weaker *till*. It wins on everything around the sale — kitchen, tables, channels, identity, audit, Arabic — and loses on the sale itself: no offline, no refund button, no drawer reconciliation, no real payment device, and a handful of order-entry affordances a cashier reaches for hourly.
