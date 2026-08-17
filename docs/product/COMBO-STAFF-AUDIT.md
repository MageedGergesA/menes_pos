# Combos — what already existed, and what the staff surfaces were missing

A branch could sell a meal deal on its public website and not at its own till. The
gap was never the model or the money: it was that neither surface a *cashier* uses
ever asked the question.

## The ten questions, answered from the code

**1. What identifies a combo product?**
`product.template.type == 'combo'`. Odoo constrains such a template to have at least
one entry in `combo_ids` and forbids a combo choice from itself being a combo
(`product_combo_item.py::_check_product_id_no_combo`). Mezze reads exactly that:
`p['is_combo'] = p['type'] == 'combo'`.

**2. How are combo-choice groups represented?**
`product.template.combo_ids` → `product.combo` records (`name`, `sequence`,
`combo_item_ids`, computed `base_price`). One `product.combo` is one question:
"choose your burger".

**3. How are options represented?**
`product.combo.item` — `product_id` (the real dish) and `extra_price`. Nothing else.
There is no per-item quantity and no per-group minimum/maximum in the model.

**4. How is max selectable enforced?**
It is not a field — it is the rule. Odoo's semantics are **exactly one item per
group**, and Mezze enforces that server-side in `_resolve_combo`: every picked item
must belong to one of *this* product's groups, the number of distinct groups picked
must equal the number of groups, and the number of picks must equal the number of
groups. Too few, too many, or two from one group are all refused. *A brief that asks
for "maximum selectable > 1" is asking for something Odoo's combo model does not
express; the multi-select case is served by product attributes (`display_type=multi`),
which the same configurator already handles.*

**5. How are included items represented?**
As the choice itself, at `extra_price = 0`. An "included" burger is simply the item
whose extra price is zero; the meal's own `list_price` already covers it.

**6. How is extra price calculated?**
Native and prorated, in `_combo_child_vals`: each child is priced
`combo.base_price × meal.list_price ÷ Σ base_price`, the last child absorbs the
rounding, and then `item.extra_price` is added. So Σ children == meal price + Σ chosen
extras, to the cent, with each child carrying its own product's taxes. The parent line
is priced 0 — the children carry the money, which is Odoo's own arrangement.

**7. How does Shop serialize the selection?**
`combo: [{item_id, product_id}]` per line, and its cart key already includes the item
ids. The staff surfaces now send the *same* wire format, so there is one contract.

**8. How does the server validate it?**
`_resolve_combo` (above). It ran at graft time, which was correct but late — this
phase moves the call **before** anything is written on both `/orders/sync` and the
fire path, because a refusal that leaves an orphan draft order in the session is not a
clean refusal. That was a real defect, found by a test written for this phase.

**9. How does it persist onto pos.order lines?**
Native fields: a parent line for the meal, and one child per group with
`combo_parent_id` set and `combo_item_id` recording which item it came from. Refunds,
invoicing and reporting therefore see what Odoo expects — `_get_invoice_lines_values`
already renders a combo parent as a `line_section`.

**10. How does KDS display it?**
`_combo_apply` returns `kds_items` — the real child dishes — and the caller routes
those to the kitchen. The kitchen prepares a Classic Burger and a Coke, not an
abstract "Burger Meal".

## What this phase added

Nothing on the server except the pre-write validation and combo-aware **preview**
pricing (`mezze.cart.pricing` now adds the chosen items' extra price and names them,
so the operator's panel and the customer's board quote what the order will cost).

Everything else is one client-side extension: `design/product-config.js` normalises a
combo group into the **same shape** as an attribute group —

```
{ kind:'combo', key:'c<id>', attribute:<group name>, multi:false, required:true,
  values:[{ id:<item_id>, product_id, name, price_extra:<extra_price> }] }
```

— so `defaultSelection`, `toggle`, `isOn`, `chosen`, `extraPrice`, `missingRequired`,
`isComplete` and `lineKey` all work on combos with no second algorithm, and both staff
surfaces render one loop. A combo group deliberately starts **empty**: "which burger"
is the question being asked, and answering it for the guest is how a wrong plate gets
made.

## Status of the other surfaces

| Surface | Combo selection | Note |
|---|---|---|
| Shop | already worked | its own picker; unchanged by this phase |
| Register | **added here** | shared configurator |
| Drive-Thru | **added here** | same rules, same panel |
| QR | still absent | the shared rules would make it small — `qr.html` already has a modifier sheet to extend. Recorded, not done. |
| Kiosk | still absent | the next product gap; out of scope here |
