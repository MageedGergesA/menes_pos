# Part of the Mezze POS platform. See LICENSE (LGPL-3).
"""Walk-in waitlist — the host stand queue.

A reservation books a table for a FUTURE time; a waitlist entry is a party
standing at the door NOW, waiting for any table to free up. When one does the
host *seats* them (which drops them onto the floor in table-service mode). Odoo
Community has no host-stand queue, so this is our own small model — deliberately
parallel to ``mezze.reservation``.
"""
from odoo import api, fields, models


class MezzeWaitlist(models.Model):
    _name = 'mezze.waitlist'
    _description = 'Mezze Walk-in Waitlist'
    _order = 'create_date asc, id asc'

    name = fields.Char(compute='_compute_name', store=True)
    # A known loyalty customer, or a walk-in (name + phone only).
    partner_id = fields.Many2one('res.partner', ondelete='set null')
    customer_name = fields.Char()
    phone = fields.Char()

    config_id = fields.Many2one('pos.config', index=True)
    party_size = fields.Integer(default=2)
    quoted_wait = fields.Integer(help="Quoted wait in minutes")
    state = fields.Selection(
        [('waiting', 'Waiting'), ('notified', 'Notified'), ('seated', 'Seated'),
         ('no_show', 'No-show'), ('cancelled', 'Cancelled')],
        default='waiting', required=True, index=True)
    note = fields.Char()
    # Set when the party is seated.
    table_id = fields.Many2one('restaurant.table', ondelete='set null')
    pos_order_id = fields.Many2one('pos.order', ondelete='set null')

    @api.depends('customer_name', 'partner_id', 'party_size')
    def _compute_name(self):
        for r in self:
            who = r.customer_name or (r.partner_id.name if r.partner_id else False) or 'Guest'
            r.name = '%s · %s' % (who, r.party_size)

    def _who(self):
        self.ensure_one()
        return self.customer_name or (self.partner_id.name if self.partner_id else False) or 'Guest'
