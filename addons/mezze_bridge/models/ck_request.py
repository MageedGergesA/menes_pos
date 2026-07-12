# Part of the Mezze POS platform. See LICENSE (LGPL-3).
"""Central-kitchen requests — a branch pulls prep from the commissary.

A request is fulfilled with REAL Odoo objects: production is a ``mrp.production``
manufacturing order at the Central Kitchen location, and distribution is an
internal ``stock.picking`` transfer from Central Kitchen to the branch's stock
location. This record just tracks the request lifecycle and links those.
"""
from odoo import api, fields, models


class MezzeCkRequest(models.Model):
    _name = 'mezze.ck.request'
    _description = 'Mezze Central Kitchen Request'
    _order = 'requested_at desc, id desc'

    name = fields.Char(compute='_compute_name', store=True)
    branch_id = fields.Many2one('pos.config', required=True, index=True)
    product_id = fields.Many2one('product.product', required=True)
    qty = fields.Float(default=1.0)
    state = fields.Selection(
        [('requested', 'Requested'), ('produced', 'Produced'),
         ('dispatched', 'In transit'), ('received', 'Received'),
         ('cancelled', 'Cancelled')],
        default='requested', required=True, index=True)
    note = fields.Char()
    production_id = fields.Many2one('mrp.production', ondelete='set null')
    picking_id = fields.Many2one('stock.picking', ondelete='set null')
    requested_at = fields.Datetime(default=fields.Datetime.now, index=True)

    @api.depends('branch_id', 'product_id', 'qty')
    def _compute_name(self):
        for r in self:
            r.name = '%s × %s → %s' % (
                int(r.qty), r.product_id.default_code or r.product_id.name or '',
                r.branch_id.name or '')
