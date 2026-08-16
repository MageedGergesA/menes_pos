# CONV-3 — product configuration is one contract, applied by both surfaces

"No onion, extra cheese, large" is the same question wherever an operator is standing.
Until this pass Mezze could only answer it in the lane: the drive-thru had the whole
capability and the Register had none of it.

## The gap was five links long, not one dialog

| # | where | what was wrong |
|---|---|---|
| 1 | `root.js` product map | dropped `modifiers` from `/bootstrap`, so the till never knew a product was configurable |
| 2 | `onSelectProduct` | always added straight to the cart |
| 3 | `OrderStore._findLine` | merged on product + note. Its own comment said *"modifiers … are legitimately distinct lines and must NOT merge"* — and nothing implemented it |
| 4 | `toSyncLines()` | had no field to carry a choice even if one existed |
| 5 | `/orders/sync` | a **second, modifier-blind line builder** beside `_build_lines`: a configured line would have reached the kitchen as a plain one |

Link 3 is the one that matters most. A cashier could not have configured a burger at
all — but if any future code had put values on a line, the store would silently have
merged the no-onion one into the plain one. One ticket, one plate wrong.

## What is shared now

| | |
|---|---|
| **The rules** | `static/design/product-config.js` — a plain script (not an ES module) so a static page and an asset bundle can both consume it. `groups · isConfigurable · defaultSelection · selectionFrom · toggle · isOn · chosen · extraPrice · missingRequired · isComplete · lineKey · describe` |
| **The panel** | `static/design/product-config.css` — `.mz-cfg` and its groups, chips, warning and foot, extracted from the drive-thru's private `.cfg*` |
| **The line control** | `.mz-line-edit` moved into `design/order-panel.css`: both surfaces reopen a configuration now |
| Kept per-surface | *placement* (the lane docks the panel over its catalogue; the Register floats it over the workspace) and the rendering itself — plain DOM in the lane, Owl at the till |

The rules are pure: no DOM, no framework, no network, no money formatting — asserted by
`test_01`. They are **not** an authority on price: `extraPrice` drives the live preview,
and the server re-derives every figure from the chosen values (`mezze.cart.pricing`,
`_build_lines`), dropping any value that does not belong to the product's own template.

Why share the *rules* and not a component: the Register is Owl inside an asset bundle and
the drive-thru board is a static page an appliance browser loads. Neither can import the
other. But the mistakes live in the rules, not the pixels, so the rules are the thing that
had to become one definition.

## What the Register gained

* a tap on a configurable product **asks**; a plain product still goes straight in
* the canonical panel, with the implied choice pre-selected so the ordinary order is one confirm
* a required group that is cleared **names itself** — "Choose a Portion", marked on the group
* a live item total that follows `price_extra`
* the chosen options on the cart line, and an **Edit** control that reopens the exact selection
* line identity that includes the configuration — so two differently-configured lines of the
  same product coexist, and two identical ones merge to a quantity
* `attribute_value_ids` all the way through `/orders/sync` onto `pos.order.line`, with the
  server-side `price_extra` and `full_product_name`

`/orders/sync` also gained the guard the fire path already had: over-selecting a
single-choice group is refused, and a value from another product's template is neither
attached nor priced.

## Evidence

`shots/conv3-register-configurator.jpg` — the panel open on the Register: Portion /
Remove / Extras / Options from Odoo's own attribute lines, Regular pre-selected, live
item total.

`shots/conv3-register-two-configurations.jpg` — the thing that was impossible before:

```
2×  [E-COM06] Corner Desk Right Sit        $ 294.00
    Large · Extra cheese
    [− 2 +]  $147.00 each   Edit  Note  ✕

    [E-COM06] Corner Desk Right Sit        $ 147.00
    Regular
    [− 1 +]                 Edit  Note  ✕

Total  3 items                             $ 441.00
```

## Tests

**20 new** (`mezze_conv3`): five source-level (one shared module, both surfaces load it,
neither re-implements it, one panel definition, the store keys by configuration), eleven
browser tests (asks vs does not ask, required-group guard, live total, the configuration
reaches the line, line identity, correcting a choice, the choice travels to the server,
the same identity rule exercised through the **lane's** configurator, the till quoting the
price it will charge, and the foot's primary action on each surface), and four server
tests on the write path.

The drive-thru's own certified suites are the gate on the extraction being behaviour-neutral
there: **33/0/0** with the customization suite (`mezze_dt_custom`), and the wider
convergence suites green alongside it.

### Negative controls

Each sabotage applied, suites run, file restored byte-identically (sha256 verified):

| sabotage | tests that failed |
|---|---|
| the **shared** `lineKey` forgets the configuration | **2 — one per surface**: `test_14` (Register) and `test_17` (lane) |
| the Register stops carrying `modifiers` out of `/bootstrap` | 7 — the whole Register capability collapses at link 1 |
| the write path stops recording the chosen values | 1 — `test_20`, the failure that would have reached the kitchen |

**A negative control caught a hole in my own evidence.** The first run of the shared-rule
sabotage failed only ONE test, on the Register — because I had run the drive-thru suite
under a tag that does not exist (`mezze_drivethru_customization`; the real one is
`mezze_dt_custom`), so 17 tests had silently not run at all, in that control *and* in the
"81/0/0" verification before it. Re-run with the right tag, the lane suite surfaced a
second problem: its client-side line identity was covered only by a **source-shape**
assertion, which a rule that moved would fail for the wrong reason and a rule that broke
might not fail at all.

Both are fixed: `test_17_a_configured_line_is_keyed_by_its_configuration` now asserts the
property where the rule lives *and* that the board delegates to it, and a new behavioural
test drives the lane's real configurator through the same merge/split scenario the
Register's does. The sabotage now fails a behavioural test on **each** surface — which is
the actual claim being made.

## Three defects the demo found after the suites were green

Driving the finished thing with a real menu — two pizzas built out of Odoo's own
POS-time attributes — found three things 33 green tests had not.

**1. The till quoted a price it was not going to charge.** The panel previewed
$23.50 for a large stuffed-crust with extra cheese; the cart line, the order total
and the Charge button all said $12.00. The server was never wrong — `/orders/sync`
has always added `price_extra` — so the guest was charged correctly, but only after
being quoted the bare list price. `unitPrice()` now adds the line's `price_extra`
(display only; a restored line still wins, its server `price_unit` already includes
it), `addProduct` carries it from the panel via the shared `extraPrice` rule, and
the "$X each" label reads the line instead of the product.
`test_18_the_till_quotes_the_price_it_is_about_to_charge` walks panel → line →
order total → Charge button → the server's own `amount_total` on the payment
screen. Negative control: one failure, `the LINE costs what the panel previewed,
not the list price: 50`.

**2. The lane's primary action was a sliver.** Extracting the panel replaced the
drive-thru's private `.cfg*` classes with the canonical ones — and the lane's own
`.btn{width:100%}` ties on specificity with the shared `.mz-cfg__acts > *{width:auto}`
and is declared *later in its page*, so it won: Cancel filled the row and "Add to
order" rendered ~44px wide with its label wrapped over three lines. A regression
this pass introduced, invisible to every existing test because none of them assert
foot geometry. The width now lives on the named children
(`.mz-cfg__acts > .mz-cfg__add`), which cannot lose a source-order tie, and the
page's cache-bust token moved to `?v=f9` so an appliance browser actually reloads
it. `test_19` / `test_19b` assert the primary action dominates the foot — one per
surface, because a shared rule that only holds on one of them is not shared.

**3. Eight strings had no Arabic.** The full fresh-DB regression, not a focused
run, caught it: `test_68_arabic_staff_coverage_c2` demands every staff string carry
Arabic, and the configurator shipped *Add to order, Choose a %s, Choose any, Choose
one, Customize item, Edit, Item total, Save changes* in English only. Added to
`i18n/ar.po` and re-checked with the extractor the test itself uses — coverage
complete, no placeholder mismatch, no glossary collision.

The pattern in all three: the suites proved the RULES were shared and the data
reached the order. What they did not prove was that the thing an operator looks at
says the right number, in the right place, in their language.

## Recorded, not fixed

* **`.stop` is not the same as `stopPropagation()` in Owl.** The panel first used
  `t-on-click.stop` to keep a click off the scrim; the modifier stopped the event before
  Owl's delegated dispatcher reached the controls *inside* the panel, so every option,
  Cancel and Add rendered perfectly and did nothing. The Register's other modals already
  used the working idiom — `t-on-click="(ev) => ev.stopPropagation()"` — and the panel now
  matches them.
* **Combos are still published and still not configurable** from either surface.
  `_product_combos()` ships them and both clients keep them; nothing selects them. Stated
  as the limit it is, not implied as done.
* **The drive-thru board's `mods` and the payload's `modifiers`** are the same data under
  two names; the shared `groups()` accepts both rather than forcing a rename through a
  certified surface. Worth unifying when something else touches that boot payload.
