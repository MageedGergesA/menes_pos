# Kiosk product configuration — what is there, and what it does with a configured product

Read from the Kiosk itself (`static/kiosk.html`, 326 lines) and from the endpoints it
calls, then driven in Chrome against six real products. Nothing here is inferred from
the staff Register.

## The surface as it stands

| Question | Answer |
|---|---|
| Route | none of its own — a static page, `/mezze_bridge/static/kiosk.html?store=<token>` |
| Files | `static/kiosk.html` only (markup + CSS + ~140 lines of JS in one IIFE) |
| Bootstrap | `POST /shop/config` (branch name, currency) then `POST /shop/menu` |
| Product cards | `.card` → name, price, image (`/shop/image/<store>/<id>`) or an emoji, and one **Add** button |
| Category model | `pos.category`, a horizontal pill row, client-side filter on `pos_categ_ids` |
| Cart | a JS array `[{id, name, price, qty}]`; a bottom bar + a review sheet with `−/+` steppers |
| Add to cart | `addToCart(id)` — **merges on `product.product` id alone** |
| Pricing | `cartTotal() = Σ list_price × qty`, client-side, from the menu payload |
| Order submission | `POST /shop/order {fulfillment:'kiosk', service_mode, lines:[{product_id, qty}]}` |
| Payment | pay-at-counter; the order is created UNPAID and the customer is shown a tracking number |
| KDS | server-side, inside `_do_fire` — the kiosk itself sends nothing about preparation |
| Product info | none — no description, no tags, no detail view; the card is the whole story |
| Variant / configuration support | **none** |
| Combo support | **none** |
| Editing a cart line | **none** — only quantity `−/+` and removal at zero |
| Arabic / RTL | full page toggle (`#k-lang`), `dir=rtl`, own EN/AR dictionary, IBM Plex Sans Arabic |
| Responsive contract | one `.wrap` at `max-width:1100px`, `auto-fill minmax(230px,1fr)` grid, fixed cart bar, sheet at `max-height:88vh` |
| Session isolation | 60 s idle → 15 s warning → `fullReset()` clears cart, service mode and screens |

The kiosk sends `{product_id, qty}` and nothing else. The **menu payload already
carries the configuration** — `modifiers`, `combos` (with `qty_max`, `qty_free`,
`base_price`), `is_combo` — because `/shop/menu` is shared with the storefront. The
kiosk reads none of it.

## The six products, opened in the CURRENT kiosk

Seeded on real models (`product.attribute` with `create_variant='no_variant'`,
`product.combo` / `product.combo.item`), POS category "Kiosk Test":

| | Product | Configuration | What the current kiosk does |
|---|---|---|---|
| A | K Simple Water 10 | none | **works** — one tap adds it |
| B | K Pizza Choice 50 | Size: Small / Medium +5 / Large +10, required, single-select | **silently adds at 50** with no size |
| C | K Loaded Fries 30 | Extras: Cheese +3 / Bacon +5 / Sauce +2, multi-select | **silently adds at 30**, no extras offered or charged |
| D | K Burger Meal 100 | 3 combo groups, all `qty_max=1, qty_free=1` | adds to cart, then the order is **refused at Place order** |
| E | K Family Meal 100 | burger + drink `1/1`, sides `qty_max=2, qty_free=1` | same — refused |
| F | K Coffee 20 | Shot: Single / Double +8 | **silently adds at 20** |

### Failure 1 — a combo is a dead end at the till

The customer can put a Burger Meal in the cart, review it, and press **Place order**.
The server refuses (correctly — the staff phase made `_resolve_combo` reject before any
write) and the kiosk shows the raw internal text:

```
Combo K Burger Meal needs 1 item(s) from K Choose your burger
```

English only, names an internal rule, and offers the customer no way forward. The
order cannot be completed at all. No orphan order is left behind (validation precedes
the write), which is the one part that already behaves.

### Failure 2 — a required choice is silently skipped

```
POST /shop/order  lines:[{product_id: <K Pizza Choice>, qty: 1}]
→ ok: true, total: 50.00, tracking 786
```

Order accepted. The kitchen is told "K Pizza Choice" with no size; the +5 / +10
surcharge is never charged. This is the worse of the two failures: the combo at least
fails loudly.

### Failure 3 — multi-select extras never reach the guest

Same shape as failure 2. `modifiers` are in the payload; the card has no way to show
them.

### Failure 4 — "Available in Self Order" is not honoured

`_menu_domain` filters on `available_in_pos` and a POS category, and nothing else.
With `K Water` set to `self_order_available = False` on its template:

```
/shop/menu   → K Water is LISTED
/shop/order  → ok: true, total 15.00
```

`pos_self_order` (installed here) defines `self_order_available` on
`product.template` with `default=True`, and Odoo's own self-order domain ANDs
`[('self_order_available','=',True)]` onto the product query. Mezze's customer menu
never has. This is a hard gate for a customer surface and it is currently open.

### What already holds

| Probe | Result |
|---|---|
| client-sent `price_unit: 1.00` | **stripped** — `_sanitize_customer_lines` (§63); server charged 50.00 |
| more items than `qty_max` | **refused** — "allows at most 2 item(s) from …" |
| fewer than `qty_free` | **refused** |
| orphan order after a refusal | **none** |
| foreign attribute value from another product | accepted but **ignored** (`_line_attr_values` filters to the template) — not priced, not attached, but not refused either |

So the money is already safe. What is missing is the customer's ability to *say* what
they want, an explicit refusal for a foreign option, and the self-order gate.

## Server path a kiosk order already takes

```
/shop/order (fulfillment='kiosk')
  → _sanitize_customer_lines      strip price/discount, keep attribute_value_ids + combo
  → _selforder_paused             staff can pause the kiosk channel
  → _do_fire
      → _split_combos             plain / combo / half-&-half
      → _resolve_combo            per-group qty_max / qty_free — BEFORE any write
      → _build_lines              pricelist price + real price_extra, taxes via FP
      → _combo_apply              native parent + children, Odoo's proration
      → _make_station_tickets     KDS gets the real dishes
  → mezze_channel='kiosk', service mode, status token, tracking number
```

Every capability the brief asks for on the server already exists on this path and is
certified by the staff phase (915/0/0). The kiosk simply never uses it.

## What can be shared, and what must not be

`static/design/product-config.js` (`window.MezzeProductConfig`) is already consumed by
two surfaces with different markup — the Drive-Thru's static page and the Register's
Owl bundle — so it is proven shareable from a plain `<script>` tag:

| Rule | Shareable | Note |
|---|---|---|
| `groups(product)` | yes | normalises attribute lines AND combo groups into one shape |
| `defaultSelection` | yes | single-select attributes pre-answer, combo groups start empty |
| `toggle` / `isOn` / `countOf` / `roomLeft` | yes | includes `qty_max` cycling |
| `chosen` / `comboSelectionFrom` | yes | wire format `{item_id, product_id, qty}` |
| `extraPrice` | yes | Odoo's `computeComboExtraPrice`, verbatim |
| `missingRequired` / `isComplete` | yes | combo groups need `qty_free` items |
| `lineKey` / `comboIds` | yes | unit-counting identity |

What must **not** be shared is the staff *presentation*: a 640 px modal, 13 px price
chips, keyboard hints, Escape/`/` shortcuts and a dense two-column foot. A kiosk is
tapped by a stranger standing up, possibly on a 1080×1920 portrait screen.

Decision: the kiosk consumes `product-config.js` for every rule, and gets a **new
customer-facing renderer** (`design/customer-config.js` + `design/customer-config.css`)
that owns only markup, layout and touch behaviour. QR can adopt the same two files
later without a second engine — it is deliberately not wired now.

## Variants — what Mezze's model actually is

`_product_modifiers` only reads attribute lines whose attribute has
`create_variant = 'no_variant'`. An attribute that *creates* variants
(`create_variant='always'`) produces distinct `product.product` records, and those are
already separate cards on the menu with their own prices and images. So:

* the canonical resolved variant **is** the `product_id` the card carries — the kiosk
  never composes one from labels;
* POS-time attributes are the configuration surface.

Grouping several variant products behind one card with a size selector would be a new
product decision (and a different data contract). Recorded, not done.

## Notes, allergens, product info

* The kiosk has **no** free-text note box today. Per the brief it stays that way — a
  customer-entered kitchen note is an operational and allergen-safety decision, not a
  UI gap. Recorded as a separate product decision.
* No allergen or dietary metadata exists on these products; nothing will be inferred
  from option names.
* There is no product description / tag / detail view to preserve — the configurator is
  the first detail surface this kiosk has ever had, so it carries the image and price.

## Gap summary

| # | Gap | Severity |
|---|---|---|
| 1 | No configurator at all — required choices skipped silently | order is wrong AND under-charged |
| 2 | Combos unsellable — refused at Place order with an internal English message | customer dead end |
| 3 | Cart identity is `product_id` — two differently configured meals would merge | wrong plate |
| 4 | No edit of a configured line | correction impossible |
| 5 | `self_order_available` not honoured | products sold that the branch excluded from self-order |
| 6 | Foreign attribute value accepted (ignored, not refused) | silent acceptance of a bad request |
