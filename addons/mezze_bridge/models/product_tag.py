"""Dietary tags on the till — carried by Odoo's OWN product tag, not a new model.

The design's category rail ends in a `DIETARY` heading and a row of filter chips
(Veg · Vegan · No gluten · No nuts). The obvious temptation is a bespoke
`mezze.dietary.tag`; there is no reason for one. `product.tag` has existed in
core since v17, hangs off `product.template.product_tag_ids`, is translatable and
already carries a colour — everything a dietary chip needs, and it means a
restaurant that already tags its catalogue keeps those tags.

What core does NOT have is a way to say "this tag is a DIET, so put it on the
till as a filter". Every product tag is a chip would be noise: a catalogue tagged
"Summer menu" or "Supplier: Nile Foods" would push those onto the cashier's rail.
One boolean makes the branch curate the list, and adds no table.
"""
from odoo import fields, models


class ProductTag(models.Model):
    _inherit = 'product.tag'

    mezze_is_allergen = fields.Boolean(
        string="Allergen",
        help="Name this tag under the item on the till, so a cashier is told "
             "before they ring it up rather than after the guest asks.")

    mezze_is_dietary = fields.Boolean(
        string="Dietary filter",
        help="Show this tag as a dietary filter on the Register's category rail. "
             "Leave off for tags that organise the catalogue rather than describe "
             "what is in the dish.")
