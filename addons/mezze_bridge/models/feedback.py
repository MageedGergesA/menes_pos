# Part of the Mezze POS platform. See LICENSE (LGPL-3).
"""Customer feedback — a post-order rating + comment.

A shopper rates their order (1–5 + an optional comment) from a link on the
receipt / storefront confirmation. Kept as its own small model on the branch's
pos.config so the manager sees a live rating pulse. Optionally linked to the
originating pos.order.
"""
from odoo import api, fields, models


class MezzeFeedback(models.Model):
    _name = 'mezze.feedback'
    _description = 'Mezze Customer Feedback'
    _order = 'create_date desc, id desc'

    config_id = fields.Many2one('pos.config', index=True)
    pos_order_id = fields.Many2one('pos.order', ondelete='set null')
    rating = fields.Integer(required=True, help="1–5 stars")
    comment = fields.Text()
    customer_name = fields.Char()
    phone = fields.Char()

    @api.constrains('rating')
    def _check_rating(self):
        for f in self:
            if not (1 <= (f.rating or 0) <= 5):
                from odoo.exceptions import ValidationError
                raise ValidationError("Rating must be between 1 and 5.")
