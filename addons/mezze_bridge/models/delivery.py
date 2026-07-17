# Part of the Mezze POS platform. See LICENSE (LGPL-3).
"""Delivery orders — the last-mile leg on top of a real paid pos.order.

A delivery is a normal (paid) ``pos.order`` that fires to the kitchen like any
other order, plus this record tracking the off-premise leg: address, fee, rider
and a dispatch lifecycle. Kitchen readiness is derived from the order's KDS
tickets, so the delivery board reflects the real prep state.
"""
from odoo import api, fields, models

FLOW = ['placed', 'preparing', 'ready', 'dispatched', 'delivered', 'failed']


class MezzeDeliveryZone(models.Model):
    _name = 'mezze.delivery.zone'
    _description = 'Mezze Delivery Zone'
    _order = 'sequence asc, id asc'

    name = fields.Char(required=True)
    config_id = fields.Many2one('pos.config', index=True)
    fee = fields.Float(help="Delivery fee charged for this zone")
    min_order = fields.Float(help="Minimum food subtotal to deliver to this zone")
    eta_minutes = fields.Integer(default=45, help="Typical door-to-door minutes")
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)


class MezzeDelivery(models.Model):
    _name = 'mezze.delivery'
    _description = 'Mezze Delivery'
    _order = 'placed_at desc, id desc'

    name = fields.Char(compute='_compute_name', store=True)
    pos_order_id = fields.Many2one('pos.order', ondelete='cascade', index=True)
    config_id = fields.Many2one('pos.config', related='pos_order_id.config_id', store=True, index=True)
    partner_id = fields.Many2one('res.partner', ondelete='set null')
    customer_name = fields.Char()
    phone = fields.Char()
    address = fields.Text()

    fee = fields.Float()
    zone_id = fields.Many2one('mezze.delivery.zone', ondelete='set null')
    rider = fields.Char()
    state = fields.Selection(
        [('placed', 'Placed'), ('preparing', 'Preparing'), ('ready', 'Ready'),
         ('dispatched', 'Out for delivery'), ('delivered', 'Delivered'), ('failed', 'Failed')],
        default='preparing', required=True, index=True)
    eta = fields.Datetime()
    note = fields.Char()

    placed_at = fields.Datetime(default=fields.Datetime.now, index=True)
    dispatched_at = fields.Datetime()
    delivered_at = fields.Datetime()

    @api.depends('customer_name', 'partner_id', 'pos_order_id')
    def _compute_name(self):
        for d in self:
            who = d.customer_name or d.partner_id.name or 'Customer'
            d.name = '%s · %s' % (who, d.pos_order_id.tracking_number or d.pos_order_id.pos_reference or '')

    def _who(self):
        self.ensure_one()
        return self.customer_name or self.partner_id.name or 'Customer'

    def _kitchen_ready(self):
        """True when every KDS ticket for this order is ready/served (i.e. the
        food is done and the rider can take it)."""
        self.ensure_one()
        tickets = self.env['mezze.kds.ticket'].search([('pos_order_id', '=', self.pos_order_id.id)])
        if not tickets:
            return True
        return all(t.state in ('ready', 'served') for t in tickets)
