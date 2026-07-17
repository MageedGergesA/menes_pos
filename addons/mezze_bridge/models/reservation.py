# Part of the Mezze POS platform. See LICENSE (LGPL-3).
"""Table reservations — a booking lifecycle on top of real restaurant.table.

Odoo Community has no restaurant booking system, so this is our own model. A
reservation books a real ``restaurant.table`` for a party at a time; when the
guests arrive it is *seated* (which drives the floor into table-service mode),
and it can also be marked no-show, cancelled or done.
"""
from odoo import api, fields, models


class MezzeReservation(models.Model):
    _name = 'mezze.reservation'
    _description = 'Mezze Table Reservation'
    _order = 'start asc, id asc'

    name = fields.Char(compute='_compute_name', store=True)
    # Either a known loyalty customer, or a walk-in booking (name + phone only).
    partner_id = fields.Many2one('res.partner', ondelete='set null')
    customer_name = fields.Char()
    phone = fields.Char()

    table_id = fields.Many2one('restaurant.table', required=True, ondelete='cascade', index=True)
    config_id = fields.Many2one('pos.config', index=True)
    start = fields.Datetime(required=True, index=True)
    duration = fields.Float(default=1.5, help="Hours the table is held")
    guests = fields.Integer(default=2)
    state = fields.Selection(
        [('booked', 'Booked'), ('seated', 'Seated'), ('no_show', 'No-show'),
         ('cancelled', 'Cancelled'), ('done', 'Done')],
        default='booked', required=True, index=True)
    note = fields.Char()
    # Set when the party is seated — links the reservation to its live order.
    pos_order_id = fields.Many2one('pos.order', ondelete='set null')

    @api.depends('customer_name', 'partner_id', 'table_id', 'start')
    def _compute_name(self):
        for r in self:
            who = r.customer_name or r.partner_id.name or 'Guest'
            tbl = ('T%s' % (r.table_id.table_number if r.table_id else '')) if r.table_id else ''
            r.name = '%s · %s' % (who, tbl)

    def _who(self):
        self.ensure_one()
        return self.customer_name or self.partner_id.name or 'Guest'
