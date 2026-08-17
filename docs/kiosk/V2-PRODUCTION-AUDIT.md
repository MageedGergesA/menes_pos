# Kiosk V2 — audit of the production kiosk before implementation

Read from the running code at `80110f5`, and driven in Chrome. This is what the real
kiosk supplies (data, functionality, routes, contracts) — none of it is design
authority. The design authority is the approved Claude Design artifact
*Mezze Kiosk v2*.

## What exists today

| | |
|---|---|
| Route | static page — `/mezze_bridge/static/kiosk.html?store=<token>` (no controller of its own) |
| Files | `static/kiosk.html` (612 lines: markup + CSS + one IIFE), `static/design/customer-config.{js,css}` (the customer configurator), `static/design/product-config.js` (canonical rules, shared with Register + Drive-Thru) |
| Bootstrap | `POST /shop/config` → branch name, currency name; `POST /shop/menu {channel:'kiosk'}` → categories + products |
| Menu payload | `id, name, list_price, default_code, pos_categ_ids, type, modifiers, combos, is_combo, half_base, has_image` |
| Images | `GET /shop/image/<store>/<product>` — streams `image_512 → image_256 → image_1920`, 1 h cache, POS-availability gated |
| Cart | client array, identity via canonical `PC.lineKey` (attributes + combo items **and quantities**) |
| Pricing preview | `mezze.cart.pricing._price_cart` → `(rows, {subtotal, tax, total})`; deliberately omits a tax row when the branch has no tax |
| Order submission | `POST /shop/order {fulfillment:'kiosk', service_mode, lines:[{product_id, qty, attribute_value_ids, combo}]}` |
| Server authority | `_sanitize_customer_lines` (strips price/discount) → `_assert_available` → `_assert_selforder_allowed` → `_assert_customer_config` → `_do_fire` → `_resolve_combo` (qty_max/qty_free, before any write) → `_build_lines` → `_combo_apply` (Odoo's `computeComboItems` proration) |
| KDS | inside `_do_fire`: `_make_station_tickets` + `_publish_kds`; combo children reach the kitchen with their real quantities |
| Payment | **pay-at-counter only.** The order is created UNPAID (`state='draft'`, `amount_paid=0`) and the customer is given a tracking number. Native Odoo kiosk payment is Adyen/Stripe-terminal only; Mezze v1 deliberately does not fake a payment |
| Success | tracking number + "pay at the counter" copy |
| Session reset | 60 s idle → 15 s warning → `fullReset()`; also `New order` |
| Offline | none — a failed fetch shows a generic error string in the review sheet |
| Languages | in-page EN/AR dictionary + `dir=rtl`; product names come from Odoo records |

## Screens today vs the approved design

| Approved screen | Today |
|---|---|
| Welcome / attract | a centred `Welcome / Tap to start` panel with a service toggle — no hero, no brand lockup |
| Service mode | two buttons on the welcome screen; hardcoded `eat_in` / `takeaway` |
| Menu | **bottom-docked horizontal** category rail, 2 columns portrait, dark surface | 
| Product detail | **does not exist** — a plain product is added in one tap |
| Meal summary | a scrolling panel of component rows inside a modal scrim |
| Focused choice | **does not exist** — every group is on one screen |
| Cart | a bottom sheet with text rows |
| Review | the same sheet; no service row, no subtotal/tax breakdown |
| Payment | **does not exist** — Place order goes straight to success |
| Payment failure | **does not exist** |
| Success | a number and one line of copy |
| Offline / reconnect | **does not exist** |
| Upsell | one "Make it a meal?" bar above the order bar |

## Assets — already production-safe

`grep` for `fonts.googleapis|fonts.gstatic|cdn.|unpkg|jsdelivr` across `static/` returns
**nothing**. All four families are already self-hosted and declared in
`design/foundation.css`:

| Family | File |
|---|---|
| Hanken Grotesk | `fonts/Hanken-{400,500,600,700,800}-{latin,latinext}.woff2` |
| IBM Plex Sans Arabic | `fonts/IBMPlexArabic-{400,500,600,700}-arabic.woff2` |
| JetBrains Mono | `fonts/JetBrainsMono-{400,500,600,700}-latin.woff2` |
| Material Symbols Rounded | `fonts/MaterialSymbolsRounded-subset.woff2` (7.5 KB subset) |

The Material subset is small and was cut for `pos.html`'s glyph list; it cannot be
assumed to carry the kiosk's icons. The repo's own precedent (`pos.html`'s `ICONS`
map) is inline SVG, which needs no font at all — that is what V2 uses.

## Real Odoo configuration available (and currently unused by the kiosk)

| Fact | Source | Used today |
|---|---|---|
| Currency | `pos.config.currency_id` | name only |
| Tax | product taxes through `fiscal_position` in `_build_lines` / `_price_cart` | computed, never shown |
| Pricelist | `pos.config.pricelist_id` | yes (server-side) |
| Self-order availability | `product.template.self_order_available` (`pos_self_order`) | **yes** — menu + order gate |
| Self-order mode | `pos.config.self_ordering_mode` (`nothing/consultation/mobile/kiosk`) | no |
| Service mode | `pos.config.self_ordering_service_mode` (`counter` / `table`) | no — copy is hardcoded "pay at the counter" |
| Default language | `pos.config.self_ordering_default_language_id` | no |
| Presets | `pos.config.use_presets`, `available_preset_ids`, `default_preset_id` (`pos.preset`, translated labels, own pricelist + fiscal position) | no — `eat_in`/`takeaway` hardcoded |
| Payment methods | `pos.config.payment_method_ids` | no — kiosk is pay-at-counter |
| Product description | `product.template.description_sale` | no |
| Customer tags | `product.tag_ids` (`product.tag`) / POS `pos_categ_ids` | no |
| Images | `image_512` derivative already served bounded | yes |

## Gaps V2 must close

1. No welcome/attract screen, no brand lockup, no hero.
2. Service mode is hardcoded and invisible after the first screen.
3. Category rail is the wrong shape (bottom horizontal, not a vertical icon rail).
4. Menu is 2 columns, not the approved 3 (portrait) / 5 (landscape).
5. No product detail screen; no description, no tags, no photo fallback treatment.
6. Configurator is one long panel, not meal summary + focused choice.
7. Cart has no thumbnails, no per-line Edit/Remove buttons in the approved shape.
8. Review has no service row and no subtotal / tax / total breakdown.
9. No payment step, no failure state, no truthful "nothing has been charged" gate.
10. Success copy assumes counter collection regardless of `self_ordering_service_mode`.
11. No offline / reconnecting state; raw error strings can reach the screen.
12. Numbers are formatted with a fixed `toFixed(2)` and a currency name glued on, not
    with locale-aware formatting.

## What must NOT be re-implemented

The canonical configuration engine (`design/product-config.js`) and the server contract
are certified at 986/0/0 and stay exactly as they are: attributes, variants,
multi-select, price extras, native combos, `qty_max`, `qty_free`, `base_price`,
`extra_price`, repeated quantities, configuration-aware identity, editing, server price
authority and server validation. V2 is a presentation layer over them.
