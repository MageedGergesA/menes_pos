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
`product.combo.item` — `product_id` (the real dish) and `extra_price`.

**4. How is max selectable enforced?**
By two fields on the group. `point_of_sale` extends `product.combo`
(`addons/point_of_sale/models/product_combo.py`) with:

* `qty_max` — how many items may be taken from the group (default 1, constrained ≥ 1)
* `qty_free` — how many of them the meal's own price already covers (default 0 ≤ n ≤ qty_max)

Both default to 1, which is the familiar "choose one" — and that default is the whole
of what this document originally claimed the model could express. **That claim was
wrong**: an earlier revision of this page stated Odoo had no maximum-selectable field
and that multi-select combos were "something Odoo's combo model does not express". It
does express them, the POS ships them in `_load_pos_data_fields`, and its own combo
configurator implements a stepper against `qty_max`. The staff surfaces were built to
the default rather than to the model, so a branch configuring "two sides, one free"
was refused at its own till while its website took the order. Corrected here.

`_resolve_combo` now enforces Odoo's actual rule per group — `taken > qty_max` is
refused, `taken < qty_free` is refused — with the choose-one case falling out of the
defaults rather than being hardcoded beside them.

**5. How are included items represented?**
As the choice itself, at `extra_price = 0`. An "included" burger is simply the item
whose extra price is zero; the meal's own `list_price` already covers it.

**6. How is extra price calculated?**
Odoo's own arithmetic, mirrored in `_combo_child_vals` from `computeComboItems`
(`addons/point_of_sale/static/src/app/models/utils/compute_combo_items.js`):

* the items covered by `qty_free` are **included** — the meal's `list_price` is
  prorated across them by `combo.base_price × qty`, and the last included child
  absorbs the rounding;
* an item taken **beyond** `qty_free` is charged that group's `base_price`;
* every child then adds its own `item.extra_price`.

The preview (`mezze.cart.pricing`) and the panel's live total
(`design/product-config.js::extraPrice`) compute the same number the order will
charge — `max(0, taken − qty_free) × base_price + Σ qty × extra_price`, which is
Odoo's `computeComboExtraPrice` verbatim. Each child carries its own product's taxes;
the parent line is priced 0, which is Odoo's arrangement.

**7. How does Shop serialize the selection?**
`combo: [{item_id, product_id}]` per line, and its cart key already includes the item
ids. The staff surfaces send the *same* wire format, extended with an optional `qty`
— the server reads either a repeated entry or an explicit `qty`, so the older shape
stays valid. Shop's own picker is still choose-one and does not yet offer a
`qty_max > 1` group; recorded, not done.

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
{ kind:'combo', key:'c<id>', attribute:<group name>,
  multi:qty_max > 1, required:qty_free > 0, min:qty_free, max:qty_max,
  qty_free, qty_max, base_price,
  values:[{ id:<item_id>, product_id, name, price_extra:<extra_price> }] }
```

The operator reads that as "Choose up to 2 · 1 included" and a `×2` badge on the
chip; the field names never reach the screen. Line identity counts **units**, not
distinct items (`comboIds`), so one side and two sides are two different lines.

— so `defaultSelection`, `toggle`, `isOn`, `chosen`, `extraPrice`, `missingRequired`,
`isComplete` and `lineKey` all work on combos with no second algorithm, and both staff
surfaces render one loop. A combo group deliberately starts **empty**: "which burger"
is the question being asked, and answering it for the guest is how a wrong plate gets
made.

## Evidence

Both staff surfaces, driven on a real instance against a real `qty_max = 2,
qty_free = 1` group (Family Meal: one burger, up to two sides, one included):

| What | Shot |
|---|---|
| Drive-Thru lane — "Choose up to 2 · 1 included", `Fries ×2`, USD 125 | `evidence/combo-cardinality-lane.jpg` |
| Register — same group, same money, line reads "Classic Burger · Fries x2", Charge $125.00 | `evidence/combo-cardinality-register.jpg` |

Tests: `tests/test_combo_staff.py` (`--test-tags mezze_combo`) 47/0/0 on a fresh
`--without-demo=all` database; the full addon suite 915/0/0. Four negative controls
were applied and reverted byte-identically (sha256):

| Control | Tests that failed |
|---|---|
| server stops enforcing `qty_max` | 58, 60, 61 |
| server gives away the item beyond `qty_free` | 53, 54, 62 |
| panel quotes the extra item as free | 66, 67, 69 |
| line identity stops counting units | 64, 69 |

## Status of the other surfaces

| Surface | Combo selection | Note |
|---|---|---|
| Shop | already worked | its own picker; unchanged by this phase |
| Register | **added here** | shared configurator |
| Drive-Thru | **added here** | same rules, same panel |
| QR | still absent | the shared rules would make it small — `qr.html` already has a modifier sheet to extend. Recorded, not done. |
| Kiosk | still absent | the next product gap; out of scope here |

Shop and QR remain choose-one pickers: they are correct for the default
(`qty_max = 1`) and would mis-handle a group configured above it. Recorded, not
done — the correction here covers the two STAFF surfaces only.
