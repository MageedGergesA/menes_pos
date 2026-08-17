# Kiosk product configuration — evidence

Everything below was produced against a running Odoo 19 instance with real
`product.attribute` / `product.combo` data. Nothing is illustrative.

## Fixtures

| | Product | Configuration |
|---|---|---|
| A | K Simple Water 10 | none |
| B | K Pizza Choice 50 | Size: Small / Medium +5 / Large +10 — required, single-select |
| C | K Loaded Fries 30 | Extras: Cheese +3 / Bacon +5 / Sauce +2 — multi-select |
| D | K Burger Meal 100 | 3 combo groups, `qty_max=1, qty_free=1` |
| E | K Family Meal 100 | burger + drink `1/1`; sides `qty_max=2, qty_free=1` |
| F | K Coffee 20 | Shot: Single / Double +8 |
| G | K Build Your Bowl 45 | 6 groups, 23 choices (layout stress) |

## Before — the gap, proven in the running kiosk

| Probe | Result |
|---|---|
| B added from the menu | **accepted at 50.00 with no size chosen**, order 967, tracking 786 |
| D added and ordered | **refused** with `Combo K Burger Meal needs 1 item(s) from K Choose your burger` on screen |
| `self_order_available = False` on K Water | **listed and ordered anyway**, 15.00 |
| foreign attribute value | accepted (ignored, not refused) |
| client `price_unit: 1.00` | already stripped — charged 50.00 |
| `qty` 3 in a `qty_max=2` group | already refused |

`docs/kiosk/shots/kiosk-before-unconfigured-cart.jpg`

## After

| Shot | What it shows |
|---|---|
| `kiosk-combo-qty2-free1.jpg` | E in English: "Choose up to 2 · 1 included", Fries with a `− 2 +` stepper, item total 150.00 |
| `kiosk-cart-configured.jpg` | the order sheet reading `K Double Burger · K Coke Zero · K Fries x2`, 150.00, with **Edit** |
| `kiosk-arabic.jpg` | the same panel in Arabic/RTL: "اختر حتى 2 · 1 مشمول", mirrored stepper, `+USD 20.00` keeping its sign |
| `kiosk-portrait-1080x1920.jpg` | portrait kiosk, one option per row, price and CTA in view |

## Money, end to end

Family Meal · Double Burger · Coke Zero · Fries ×2, then corrected to Fries + Salad:

| Stage | Value |
|---|---|
| panel running total | 153.00 |
| order sheet | 153.00 |
| server response | 153.00 |
| `pos.order.amount_total` (id 971, tracking 790) | 153.00 |
| child lines | Double 80 + Coke Zero 20 + Fries 25 + Salad 28 = 153.00 |
| KDS tickets | Kitchen: Double Burger, Coke Zero, Fries · Salad: Salad — each noted `K Family Meal` |

Proration is Odoo's, not a flat retail sum. Order 791 (Classic + Coke + Fries, retail
60+20+25 = 105) was charged **100.00** and split 60 / 15 / 25 across the children —
each group's `base_price` prorated against the meal price.

Attribute lines persist too: order 792 carried `K Coffee (Double)` and
`K Coffee (Single)` with their `product.template.attribute.value` ids on the lines, so
the receipt and order history read the choice.

## Security probes (kiosk endpoint, hand-made requests)

| Probe | Result |
|---|---|
| foreign attribute value from another product | **DENIED** — "Option 275 is not offered for K Pizza Choice" |
| combo item from another combo | **DENIED** |
| more than `qty_max` | **DENIED** |
| fewer than `qty_free` | **DENIED** |
| negative quantity | **DENIED** |
| quantity 1 000 000 | **DENIED** |
| product excluded from self-order | **DENIED** |
| `price_unit: 1.00` + `discount: 100` | **CORRECTED** — charged 60.00 |
| orders left behind by the refusals | **0** |

## Viewports

Measured inside a fixed-size frame so media queries see the kiosk's real dimensions.

| Viewport | Horizontal scroll | Overflowing nodes | Targets < 44 px | CTA in view |
|---|---|---|---|---|
| 1080×1920 portrait | no | 0 | 0 | yes |
| 1920×1080 | no | 0 | 0 | yes |
| 1366×768 | no | 0 | 0 | yes |
| 1280×720 | no | 0 | 0 | yes |
| 1024×768 | no | 0 | 0 | yes |

## Performance

No round trip is made while configuring — the groups arrive with the menu.

| | median | p95 |
|---|---|---|
| open a plain product (straight to cart) | 0.2 ms | 0.3 ms |
| open a one-attribute product | 1.0 ms | 21 ms |
| open a 3-group combo | 1.4 ms | 2.5 ms |
| open the 6-group / 23-choice product | 3.5 ms | 4.9 ms |
| a selection | 3.1 ms | 4.4 ms |
| RPCs during configuration | **0** | |

(p95 on the first measurement includes first-run JIT; the 21 ms outlier is the first
panel opened in the page's life.)

## Customer effort

| Task | Taps |
|---|---|
| simple item | 1 |
| one-choice item (accepting the implied answer) | 2 — Choose, Add |
| one-choice item (changing the answer) | 3 |
| 3-group combo | 5 — Choose, 3 answers, Add |
| combo with a second side | 6 |
| edit one choice from the order | 4 — Review, Edit, new answer, Save |
| remove a line | 1 (stepper to zero from the review sheet) |

## Negative controls

Each sabotage was applied to the working tree, the `mezze_kiosk` suite was run on a
fresh database, and the file was restored and verified **byte-identical (sha256)**.

| # | Sabotage | Tests that failed |
|---|---|---|
| 1 | server stops enforcing `qty_max` | `test_33_more_than_qty_max_is_refused` |
| 2 | server ignores `qty_free` when pricing | `test_14`, `test_16`, `test_52` |
| 3 | the kiosk client is trusted for the price | `test_30_a_client_price_never_reaches_the_money` |
| 4 | combo quantity dropped from the line identity | `test_48`, `test_55` |
| 5 | a product excluded from self-order is allowed | `test_22` |
| 6 | the configuration is dropped before the kitchen | `test_18_the_kitchen_is_told_the_real_dishes` |
| 7 | cancelling still leaves the item in the order | `test_50`, `test_64` |
| 8 | the final order skips server revalidation | `test_22`, `test_31`, `test_36` |

Every control produced at least one failure and every restore was byte-identical.

## Shots

`docs/kiosk/shots/` — `kiosk-single-choice`, `kiosk-multi-extra`, `kiosk-combo-qty1`,
`kiosk-combo-qty2-free1`, `kiosk-combo-extra-price`, `kiosk-required-validation`,
`kiosk-edit-config`, `kiosk-cart-configured`, `kiosk-long-config`, `kiosk-arabic`,
`kiosk-portrait-1080x1920`, `kiosk-landscape-1366x768`, `kiosk-payment-total`,
`kiosk-kds-configured`, and `kiosk-before-unconfigured-cart` (the gap).

## Refinements added after scoring

Scoring the configurator honestly against the rubric surfaced three gaps; each was
closed and pinned by a test rather than argued away.

| Gap | Closed by | Test |
|---|---|---|
| no sense of position in a 6-question product | "3 of 6" per group, from four questions up | `test_56` |
| a radiogroup that ignored arrow keys | arrow keys move and choose within a choose-one group | `test_57` |
| "Choose Choose your burger" was possible for some group names | the verb is added only when the name does not already carry it | `test_58` |

## Benchmarked layout (KFC / McDonald's principles)

Driven in fixed-size frames so the media queries see real kiosk dimensions.

| Measure | Result |
|---|---|
| Chrome (header + rail + order bar) at 1080×1920 | under 30 % of the screen; the menu gets the rest |
| Portrait columns | 2 large image-led cards |
| Landscape columns (1920×1080) | 5 |
| Category rail | fade mask + a chip cut by the edge; active chip scrolled into view |
| Card | one `<button>`, image taller than its text block, ≥ 200 px tall |
| Order bar centre | y = 1870 / 1920 — easy reach |
| Category rail centre | y = 1772 / 1920 — easy reach |
| Language / service mode / identity | y = 46 / 1920 — information band, rarely touched |
| Meal builder | three components, each one line once answered, each with **Change** |
| Recommendation | "Make it a meal? +USD 40.00", both answers 190×60 px, order total still on screen (USD 60.00) |
| Second recommendation after the next item | none |

Shots: `kiosk-portrait-menu`, `kiosk-landscape-menu-1920x1080`,
`kiosk-meal-builder-components`, `kiosk-offer-make-it-a-meal`,
`kiosk-arabic-meal-builder`, `kiosk-reach-zones-1080x1920`.

### Defects found while driving the redesign

| | |
|---|---|
| The category rail did not scroll the chosen chip into view — the rail showed one category while the heading showed another | `scrollIntoView({inline:'center'})` after each render |
| A second recommendation appeared after the next item, because the budget was spent on *answering* the offer rather than on *showing* it | one per order, counted when shown |
| The two answers on the offer were different widths (173 vs 137 px) because the labels differ in length | both given the same min-width |

## Defects found and fixed while driving it

| | |
|---|---|
| A choose-one group locked its other options once one was chosen (`roomLeft` applied to every group) | the customer could not change their mind without deselecting |
| The quantity stepper never rendered: a `<button>` nested inside the option `<button>` — invalid HTML, the parser drops the inner one | found by measuring a 0×0 box, not by looking |
| Focus landed on the first option, which reads as a choice already made | now lands on the panel |
| `+USD 5.00` rendered as `USD 5.00+` in Arabic | the price is bidi-isolated |
| Tapping the already-chosen required option emptied the group | a customer cannot un-choose a required choice |
| The cart badge kept the previous customer's count after an order was placed | cleared with the cart |
| Pressing "Order here" before the menu arrived left an empty grid forever | boot re-renders when the data lands |
| The hero image ate a third of a 768 px-tall screen | capped below 820 px of height |
| `forced-color-adjust:none` on the selection mark | caught by the repo's own `test_10_no_broad_forced_color_optout` in the full regression — the state now uses `Highlight`/`HighlightText`, which forced-colors honours without overriding the user's palette |
