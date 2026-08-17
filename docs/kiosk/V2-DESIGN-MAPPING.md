# Kiosk V2 — design component → production mapping

Design authority: the approved Claude Design artifact **Mezze Kiosk v2**
(`bf4e67c1-3d23-43a3-b268-b27b0ecd09df`), opened and driven in Chrome. Every row below
maps an approved component to the file that implements it, the Odoo data behind it, and
who is allowed to decide the value.

**Rule for the whole table: the prototype is authority for *appearance and behaviour*.
Odoo is authority for *every value*.**

| Design component | Production file / component | Odoo data source | Server authority |
|---|---|---|---|
| KioskShell | `static/kiosk.html` — `.k-shell` | — | — |
| TopBar | `.k-top` | `pos.config.name` (branch) | — |
| Brand lockup | `.k-brand` | branch name; `/shop/config` | — |
| LanguageControl | `.k-lang` | `pos.config.self_ordering_default_language_id` for the default; EN/AR dictionaries in-page for chrome, Odoo records for content | — |
| ServiceMode chip | `.k-svc` | `pos.preset` when `pos.config.use_presets`, else the branch's `eat_in`/`takeaway` service modes | order carries `service_mode`; server records `mezze_service_mode` |
| Start over | `.k-restart` | — | resets client state only; no order exists yet |
| CategoryRail | `.k-rail` (vertical, icon + label) | `pos.category` returned by `/shop/menu` | menu domain: `available_in_pos` + `self_order_available` |
| ProductGrid | `.k-grid` | `/shop/menu?channel=kiosk` products | self-order gate |
| ProductCard | `.k-card` | name, `list_price`, tags, `is_configurable` | price re-derived on order |
| ProductImage | `.k-shot` → `GET /shop/image/<store>/<id>` | `product.product.image_512` | store-token gated, POS-availability gated |
| Fallback (no photo) | `.k-shot--none` | — | — |
| ProductDetail | screen `detail` | name, `description_sale`, price, tags, image | — |
| MealSummary | screen `meal` | `product.combo` groups + POS attribute lines via `PC.groups()` | `_resolve_combo` |
| MealComponent | `.k-comp` | one group; chosen value from the shared selection | — |
| ChoiceScreen | screen `choice` | one group | — |
| ChoiceOption | `.k-opt` | `product.combo.item` / `product.template.attribute.value` | membership + cardinality checked server-side |
| QuantityStepper | `.k-step` | `qty_max` / `qty_free` from `product.combo` | `_resolve_combo` refuses over/under |
| StickyItemFooter | `.k-foot` | running total from `PC.extraPrice` + `list_price` | server re-prices |
| BottomOrderBar | `.k-bar` | cart count + `mezze.cart.pricing` total | server total wins at submit |
| Cart | screen `cart` | client cart, priced by `_price_cart` | — |
| CartLine | `.k-line` | product + canonical `lineKey` identity | — |
| FinancialSummary | `.k-money` | `_price_cart` → `{subtotal, tax, total}` | taxes from `account.tax` through the fiscal position |
| Review | screen `review` | same + service mode | — |
| PaymentMethod | screen `pay` | **only methods the branch can really use** — see below | `/shop/order` creates the order; amount is the server's |
| PaymentFailure | screen `payfail` | submission outcome | "nothing has been charged" only when no order exists server-side |
| Success | screen `done` | `tracking_number`, `self_ordering_service_mode` | order created by the server |
| Offline / Reconnect | `.k-net` banner | `navigator.onLine` + real request outcomes | — |
| Upsell | `.k-offer` | a real `product.combo` containing the added product | price = meal price − item price, both from Odoo |

## Prototype-only — replaced, not copied

The design deliberately carries prototype behaviour to demonstrate UX. None of it
becomes production truth.

| Prototype | Production |
|---|---|
| `marketLocale` picker (en-SA / ar-SA / ar-EG / ar-AE) | language from `?lang=` / the branch's default language; **formatting only** |
| `currency` picker (SAR / EGP / AED) | `pos.config.currency_id` |
| `taxRate 15%` field | taxes computed by `account.tax` through the fiscal position; **no tax row at all** when the branch has none |
| `orientation` picker | the physical screen |
| `showUpsell` toggle | an upsell exists only when the branch's own data yields one |
| Fake menu (Mixed Grill Meal, Shawarma Meal…) | `/shop/menu` |
| Fake order number `PAY-4412` | `pos.order.tracking_number` |
| Fake payment list (Card / Phone or watch / Pay at the counter) | the branch's real capability |
| "or browse files" image drop target | the approved no-photo fallback |
| Screen-jump chips, REACH overlay | absent from production |
| Pre-chosen meal components | Mezze's certified rule: a combo group starts **unanswered** ("Not chosen yet"), which is an approved design state |

## Payment — what is really available

`pos.config.payment_method_ids` exists, but Mezze's kiosk does not drive a terminal:
native Odoo self-order payment is Adyen/Stripe-terminal only, and Mezze v1 deliberately
creates an **unpaid** order and prints a number to pay at the counter (`payment_mode:
'pay_at_counter'`, `state='draft'`, `amount_paid=0`).

So the payment screen renders exactly one real method — **Pay at the counter** — with
its copy taken from `self_ordering_service_mode` (`counter` → pay and collect at the
counter; `table` → pay at the table). Card and Phone-or-watch are **not** rendered:
the design's method list is data-driven, and rendering a method the branch cannot honour
would be a decorative lie. When Mezze gains a certified terminal, the same screen grows
the extra rows without a redesign.

## Numbers and money

* Currency: `pos.config.currency_id` — symbol/name from Odoo, never from the locale.
* Tax: whatever `account.tax` produces through the fiscal position; the row is omitted
  when there is none, and its **label is the tax's own name**, not "VAT 15%".
* Formatting: `Intl.NumberFormat` with the active locale (`ar-SA`, `ar-EG`, `ar-AE`,
  `en-*`), which decides digit shape and separators only.
* Numeral system: honoured through the locale (`-u-nu-latn` when the branch prefers
  Latin digits in an Arabic UI), never by transliterating computed digits by hand.

## Geometry (design cross-check)

| | Portrait 1080×1920 | Landscape 1920×1080 |
|---|---|---|
| Top bar | ~109 px | ~109 px |
| Category rail | ~201 px wide (18.6 %) | ~237 px |
| Product grid | 3 columns | 5 columns |
| Product card | ~264 × 518, media ~63 % | ~311 × 384 |
| Grid gap | ~20 px | ~20 px |
| Order bar | ~173 px | ~173 px |
| Primary CTA | ~124 px | — |
| Smallest ordinary control | — | ~72 px |
