# Product customization — what already exists (DT-UX7A Phase 0)

Read-only audit at `3deacd0`, before any implementation, because the answer changes
the work from *building a modifier engine* to *wiring one that is already here*.

## The headline

**Mezze already has a complete, server-authoritative product configurator, built on
Odoo's native attribute model, and the Register already uses it.** The drive-thru
Order Taker receives the configuration data in its boot payload and **throws it away**.

```js
// static/drivethru.html:517  — the entire gap, in one line
PRODUCTS = (d.products || []).filter(p => (p.list_price||0) > 0)
  .map(p => ({ id: p.id, name: …, price: p.list_price }));   // modifiers, combos dropped
```

```js
// static/pos.html:4752 — the Register keeps them
… mods: p.modifiers || [], isCombo: !!p.is_combo, combos: p.combos || [], …
```

So **no new model is needed, and none was added.** Building `mezze.modifier` here
would have created a second catalogue alongside Odoo's, and a second set of rules for
the same restaurant question.

## What each Odoo concept is, and its real status here

| Concept | Odoo model | Status in Mezze |
|---|---|---|
| POS-time attributes ("modifiers") | `product.template.attribute.line` with `create_variant='no_variant'` | **USED** — `_product_modifiers()`, consumed by the Register |
| Attribute values + price extra | `product.template.attribute.value.price_extra` | **USED** — real `price_extra`, summed server-side |
| Multi-checkbox groups | `attribute.display_type == 'multi'` | **USED** — becomes an optional any-of group |
| Single-select groups | any other `display_type` | **USED** — required exactly-one |
| Product variants (`create_variant='always'`) | separate `product.product` | **NOT** treated as modifiers — correctly, they are different products |
| Combos | `product.combo` / `product.combo.item` | **USED** — `_product_combos()`, `extra_price` per item |
| Half-and-half | Mezze-specific `halves` cart key | **USED** — `_split_combos()` |
| Optional products / upsell | Odoo `optional_product_ids` | **NOT USED** anywhere. Not a modifier; out of scope here |
| Kitchen note (free text) | line `note` | **USED** — the exception path, not a modifier substitute |
| Customer note | `pos.order.line.customer_note` | referenced once (`main.py:4112`); not part of this contract |

## The canonical contract, already on the server

**Publish** — `_product_modifiers(env, product)` returns, per POS-time attribute line:

```python
{'line_id', 'attribute_id', 'attribute', 'display_type',
 'multi', 'required', 'min', 'max',
 'values': [{'id': ptav_id, 'name', 'price_extra'}]}
```

`required`/`min`/`max` come from the attribute's own `display_type`, not from a Mezze
rule table. This already ships in `/bootstrap` (`main.py:934`) for every product,
which is why the drive-thru needs no new endpoint.

**Validate** — `_line_attr_values(env, product, line)`:

```python
ptav = env['product.template.attribute.value'].browse(ids).exists()
return ptav.filtered(lambda v: v.product_tmpl_id == product.product_tmpl_id)
```

Its docstring already states the threat it closes: *"filtered to THIS product's
template so a client cannot inject another product's options (or arbitrary ids)"*.
**Server-side injection protection exists today**; this phase must not weaken it, and
the security tests it deserves are what this phase adds.

**Price** — `price_extra = sum(ptavs.mapped('price_extra'))` (`main.py:1515`). The
client's numbers are never used.

**Persist** — `vals['attribute_value_ids'] = [(6, 0, ptavs.ids)]` on the POS order
line, plus a composed display name, so the configuration survives into order history.

**Kitchen** — `_line_note()` turns the chosen values into the ticket note, so KDS
already receives modifiers as readable text rather than an opaque blob.

## What is therefore actually missing

1. The drive-thru board keeps `modifiers`/`combos` from its boot payload instead of
   discarding them.
2. A touch-first configurator on the lane board — the only genuinely new UI.
3. `attribute_value_ids` travels in the drive-thru cart line and on to
   `/drivethru/create` (the fire path already understands it).
4. The OCB projection carries the chosen value names (it already renders modifiers).
5. Cart line identity stops being product-id-only, so two differently configured
   burgers are two lines.

## One performance risk, noted before it is created

`/bootstrap` calls `_product_modifiers` **per product**, and each call walks
`product_tmpl_id.attribute_line_ids` → `product_template_value_ids`. On a 172-product
menu that is a per-product traversal at boot. It exists today and is not introduced by
this phase, but this phase makes it load-bearing for the drive-thru too, so it must be
measured rather than assumed harmless.

## Naming

Odoo's semantics are preserved in the backend — an attribute value is a
`product.template.attribute.value`, a combo choice is a `product.combo.item`, a note
is a note. "Modifier" is the operator- and customer-facing word for what a cashier
selects, used in the UI and in the OCB payload, not a new internal type.
