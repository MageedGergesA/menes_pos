# Drive-thru product customization

An operator can now say *no onion*. The customer sees it on their board, the kitchen
sees it on the ticket, the price follows it, and the order still says it afterwards.

## What was actually built

Almost none of this is new. Mezze already had a server-authoritative configurator on
Odoo's native attribute model, and the Register already used it — the lane board
received every product's attribute groups in its boot payload and discarded them
(`MODIFIER-ARCHITECTURE-AUDIT.md`). **No modifier model was added.** Building one would
have created a second catalogue beside Odoo's, with a second set of rules for the same
restaurant question.

What this phase added is the lane's configurator, the plumbing for the chosen values,
and the tests that hold both honest.

## The contract, end to end

```
product.template.attribute.line  (create_variant='no_variant')
        │  _product_modifiers()          groups: required/multi/min/max + price_extra
        ▼
/bootstrap → the lane board keeps them        ← the one line that used to drop them
        │
        │  operator picks; the panel previews price_extra live
        ▼
cart line { product_id, qty, attribute_value_ids }
        │
        ├─► /ocb/publish  → server validates + prices → the customer's board
        └─► /drivethru/create → _line_attr_values() → pos.order.line
                                  attribute_value_ids + price_extra + _line_note()
                                                            │
                                                            └─► KDS ticket note
```

Every one of those steps existed except the two in the middle.

## Interaction

Complexity decides what happens on a tap.

| product | behaviour |
|---|---|
| no choices | **one tap**, straight into the cart, nothing opens |
| has choices | a configurator **docked beside the queue**, not over it |

The panel is docked because the operator must not lose sight of the car, the lane or
the timer to pick a sauce — verified with sixteen cars still readable behind it.

Selection semantics are the Register's, deliberately identical rather than merely
similar: choices keyed by attribute line, single-select groups pre-select their first
value so the common order is one confirm, multi groups toggle. A required group with
nothing chosen **names itself** — "Choose a Size", not "invalid configuration" — and
disables Add until it is answered.

Tap counts:

| | taps after the product |
|---|---|
| simple product | 0 (the product tap is the whole interaction) |
| product + one modifier | 2 — the option, then Add |
| product + three modifiers | 4 — three options, then Add |
| edit one modifier on an existing line | 3 — Edit, the option, Save |

## Money

The panel shows `price_extra` live (147 → 152 with Large → 155 with Extra cheese) and
is an authority over nothing. The **server** re-prices from the values themselves, on
both paths, through the same validation:

```python
ptav.filtered(lambda v: v.product_tmpl_id == product.product_tmpl_id)
```

A value that does not belong to this product's template is dropped — not rejected with
an error the customer would see, simply not counted. The same rule already guarded the
fire path; this phase extends it to the customer projection and tests both.

Client-supplied `price`, `line_total` and `price_extra` are ignored entirely.

## Line identity

`lineKey(product_id, sorted(attribute_value_ids))`. Merging on product id alone would
quietly turn a plain burger and a no-onion burger into two of the same thing, which is
the error this whole phase exists to prevent. Identical configurations still merge to a
quantity, because that is a real quantity.

## Editing

Reopening a line restores its exact selection and the button reads **Save changes**.
Removing an option drops the price and removes it from the customer's display — no
stale modifier. Correcting a choice never means deleting the line and starting again.

## Known limits, recorded

* **Combos are published but not yet configurable from the lane.** `_product_combos()`
  ships them and the board keeps them; the lane panel currently configures attribute
  groups only. Combo selection is a following phase, not a claim made here.
* **Optional products / upsell** (`optional_product_ids`) remain unused across Mezze.
  They are a different concept from a required choice and were deliberately left alone.
* **Free-text kitchen notes** already existed as the exception path and are unchanged.
  Structured choices are preferred wherever the product declares them.
* The `/bootstrap` payload builds modifier groups **per product**. It predates this
  phase, but the drive-thru now depends on it too — measured, not assumed (see
  `MODIFIER-EVIDENCE.md`).
