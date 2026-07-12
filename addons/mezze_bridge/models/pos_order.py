from odoo import fields, models


class PosOrder(models.Model):
    _inherit = 'pos.order'

    # JSON {product_id: qty} of what Mezze has already fired to the kitchen for
    # this (draft) order. Lets a re-fire send ONLY the newly-added items to the
    # stations instead of resending the whole ticket. Kept in our own field so
    # Odoo's native ``last_order_preparation_change`` merge logic never touches
    # it.
    mezze_fired = fields.Char(string='Mezze fired snapshot', copy=False)
