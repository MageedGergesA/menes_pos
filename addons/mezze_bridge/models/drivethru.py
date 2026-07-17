# Part of the Mezze POS platform. See LICENSE (LGPL-3).
"""Drive-thru lane — a car's trip through the lane on top of a real pos.order.

A drive-thru order is a normal ``pos.order`` fired to the kitchen like any other
(no table — it's an off-counter order), plus this record tracking the CAR through
the lane: which lane, a vehicle label, and a stage lifecycle

    preparing -> ready -> at_window -> collected
                                    \\-> cancelled

Kitchen readiness is derived from the order's KDS tickets (same as delivery), so
the lane board reflects real prep state. Payment is taken at the window: the
order is fired as a draft and settled when the car reaches the window, then
handed off (collected). Position-in-lane is derived FIFO from ``placed_at``.
"""
from odoo import api, fields, models

FLOW = ['preparing', 'ready', 'at_window', 'collected']


class MezzeDrivethru(models.Model):
    _name = 'mezze.drivethru'
    _description = 'Mezze Drive-Thru Car'
    _order = 'lane asc, placed_at asc, id asc'

    name = fields.Char(compute='_compute_name', store=True)
    pos_order_id = fields.Many2one('pos.order', required=True, ondelete='cascade', index=True)
    config_id = fields.Many2one('pos.config', related='pos_order_id.config_id', store=True, index=True)
    partner_id = fields.Many2one('res.partner', ondelete='set null')
    customer_name = fields.Char()
    lane = fields.Integer(default=1, index=True, help="Which drive-thru lane the car is in.")
    vehicle = fields.Char(help="Car description or plate, called out at the window.")
    state = fields.Selection(
        [('preparing', 'Preparing'), ('ready', 'Ready'),
         ('at_window', 'At window'), ('collected', 'Collected'),
         ('cancelled', 'Cancelled')],
        default='preparing', required=True, index=True)
    note = fields.Char()

    placed_at = fields.Datetime(default=fields.Datetime.now, index=True)
    ready_at = fields.Datetime()
    window_at = fields.Datetime()
    collected_at = fields.Datetime()

    @api.depends('lane', 'vehicle', 'pos_order_id')
    def _compute_name(self):
        for d in self:
            tag = d.vehicle or (d.pos_order_id.tracking_number or d.pos_order_id.pos_reference or '')
            d.name = 'Lane %s · %s' % (d.lane or 1, tag)

    def _who(self):
        self.ensure_one()
        return self.customer_name or self.partner_id.name or (self.vehicle or 'Car')

    def _kitchen_ready(self):
        """True when every KDS ticket for this order is ready/served (food done)."""
        self.ensure_one()
        tickets = self.env['mezze.kds.ticket'].search([('pos_order_id', '=', self.pos_order_id.id)])
        if not tickets:
            return True
        return all(t.state in ('ready', 'served') for t in tickets)

    def _paid(self):
        self.ensure_one()
        o = self.pos_order_id
        return o.state in ('paid', 'done', 'invoiced') or (o.amount_paid >= o.amount_total - 0.01)
