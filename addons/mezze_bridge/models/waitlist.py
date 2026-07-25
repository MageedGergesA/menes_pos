# Part of the Mezze POS platform. See LICENSE (LGPL-3).
"""Walk-in waitlist — the host stand queue.

A reservation books a table for a FUTURE time; a waitlist entry is a party
standing at the door NOW, waiting for any table to free up. When one does the
host *seats* them (which drops them onto the floor in table-service mode). Odoo
Community has no host-stand queue, so this is our own small model — deliberately
parallel to ``mezze.reservation``.
"""
from odoo import api, fields, models
from odoo.exceptions import UserError

# R1 — walk-in queue lifecycle: waiting -> notified -> seating -> seated, with
# left / no_response / cancelled terminals. 'seating' is the brief hold while the
# host walks the party to a table (prevents a second host double-seating them).
WL_TRANSITIONS = {
    'waiting': {'notified', 'seating', 'seated', 'cancelled', 'left', 'no_response'},
    'notified': {'seating', 'seated', 'cancelled', 'left', 'no_response'},
    'seating': {'seated', 'waiting', 'cancelled', 'left'},
    'seated': {'cancelled'},                 # a seated party leaves the queue
    'cancelled': {'waiting'},
    'left': {'waiting'},
    'no_response': {'waiting', 'notified'},
}
WL_ACTIONS = {'notify': 'notified', 'seating': 'seating', 'seat': 'seated',
              'cancel': 'cancelled', 'left': 'left', 'no_response': 'no_response',
              'no_show': 'no_response', 'restore': 'waiting'}


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
        [('waiting', 'Waiting'), ('notified', 'Notified'), ('seating', 'Seating'),
         ('seated', 'Seated'), ('left', 'Left'), ('no_response', 'No-response'),
         ('cancelled', 'Cancelled')],
        default='waiting', required=True, index=True)
    note = fields.Char()
    pref_area = fields.Char(help="Preferred area/section.")
    high_chair = fields.Boolean()
    accessible = fields.Boolean(help="Accessibility requirement.")
    is_vip = fields.Boolean()
    # Set when the party is seated.
    table_id = fields.Many2one('restaurant.table', ondelete='set null')
    pos_order_id = fields.Many2one('pos.order', ondelete='set null')

    def can_transition(self, action):
        self.ensure_one()
        target = WL_ACTIONS.get(action)
        if not target:
            return (False, 'unknown_action')
        if target == self.state:
            return (True, target)
        if target not in WL_TRANSITIONS.get(self.state, set()):
            return (False, 'invalid_transition:%s->%s' % (self.state, target))
        return (True, target)

    def apply_transition(self, action, table_id=None):
        self.ensure_one()
        ok, target = self.can_transition(action)
        if not ok:
            raise UserError("Waitlist entry cannot %s from %s (%s)." % (action, self.state, target))
        if target == self.state and not (target == 'seated' and table_id):
            return self
        vals = {'state': target}
        if target == 'seated' and table_id:
            vals['table_id'] = int(table_id)
        if target == 'waiting':                         # restore clears seating link
            vals.update({'table_id': False, 'pos_order_id': False})
        self.write(vals)
        return self

    @api.depends('customer_name', 'partner_id', 'party_size')
    def _compute_name(self):
        for r in self:
            who = r.customer_name or (r.partner_id.name if r.partner_id else False) or 'Guest'
            r.name = '%s · %s' % (who, r.party_size)

    def _who(self):
        self.ensure_one()
        return self.customer_name or (self.partner_id.name if self.partner_id else False) or 'Guest'
