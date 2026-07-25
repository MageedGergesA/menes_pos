# Part of the Mezze POS platform. See LICENSE (LGPL-3).
"""Table reservations — a booking lifecycle on top of real restaurant.table.

Odoo Community has no restaurant booking system, so this is our own model. A
reservation books a real ``restaurant.table`` for a party at a time; when the
guests arrive it is *seated* (which drives the floor into table-service mode),
and it can also be marked no-show, cancelled or done.
"""
from odoo import api, fields, models
from odoo.exceptions import UserError

# R1 — arrival/check-in lifecycle. A reservation moves booked -> confirmed ->
# (late) -> arrived -> seated -> done, with no-show/cancelled terminals and an
# explicit restore out of cancelled. The map is the SINGLE source of legal
# transitions; the controller and UI both go through apply_transition().
RES_TRANSITIONS = {
    'booked': {'confirmed', 'arrived', 'waiting', 'late', 'no_show', 'cancelled', 'seated'},
    'confirmed': {'arrived', 'waiting', 'late', 'no_show', 'cancelled', 'seated'},
    'late': {'arrived', 'waiting', 'no_show', 'cancelled', 'seated'},
    'waiting': {'arrived', 'seated', 'no_show', 'cancelled'},
    'arrived': {'seated', 'waiting', 'no_show', 'cancelled'},
    'seated': {'done', 'cancelled'},          # a seated party can only complete (or be cancelled by a manager)
    'done': set(),                            # terminal — a completed reservation cannot be re-seated
    'no_show': {'booked'},                    # restore only
    'cancelled': {'booked'},                  # restore only (explicit action)
}
# action name -> target state
RES_ACTIONS = {'confirm': 'confirmed', 'arrive': 'arrived', 'wait': 'waiting',
               'late': 'late', 'seat': 'seated', 'no_show': 'no_show',
               'cancel': 'cancelled', 'complete': 'done', 'done': 'done',
               'restore': 'booked'}


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
        [('booked', 'Booked'), ('confirmed', 'Confirmed'), ('late', 'Late'),
         ('waiting', 'Waiting'), ('arrived', 'Arrived'), ('seated', 'Seated'),
         ('done', 'Completed'), ('no_show', 'No-show'), ('cancelled', 'Cancelled')],
        default='booked', required=True, index=True)
    note = fields.Char()
    arrival_note = fields.Char(help="Note recorded at check-in (arrival).")
    arrived_at = fields.Datetime(copy=False)
    is_vip = fields.Boolean(help="VIP / priority guest.")
    occasion = fields.Char(help="Special occasion (birthday, anniversary…).")
    # Set when the party is seated — links the reservation to its live order.
    pos_order_id = fields.Many2one('pos.order', ondelete='set null')

    def can_transition(self, action):
        """(ok, target_or_reason) — is ``action`` legal from the current state?"""
        self.ensure_one()
        target = RES_ACTIONS.get(action)
        if not target:
            return (False, 'unknown_action')
        if target == self.state:
            return (True, target)                      # idempotent no-op is allowed
        if target not in RES_TRANSITIONS.get(self.state, set()):
            return (False, 'invalid_transition:%s->%s' % (self.state, target))
        return (True, target)

    def apply_transition(self, action, arrival_note=None):
        """Apply a guarded lifecycle transition. Raises UserError on an illegal
        move (e.g. seating a completed/cancelled reservation, or re-seating one
        that is already seated at a live table). Idempotent for a same-state action."""
        self.ensure_one()
        ok, target = self.can_transition(action)
        if not ok:
            raise UserError("Reservation cannot %s from %s (%s)." % (action, self.state, target))
        if target == self.state:
            return self
        vals = {'state': target}
        if target == 'arrived':
            vals['arrived_at'] = fields.Datetime.now()
            if arrival_note:
                vals['arrival_note'] = arrival_note
        if target == 'seated':
            # one reservation cannot be seated at two live tables at once: a party
            # already linked to an OPEN (draft) order may not be re-seated elsewhere.
            if self.pos_order_id and self.pos_order_id.state == 'draft' and self.state == 'seated':
                raise UserError("This reservation is already seated at a live table.")
        if target == 'booked':                          # restore clears arrival + order link
            vals.update({'arrived_at': False, 'pos_order_id': False})
        self.write(vals)
        return self

    @api.depends('customer_name', 'partner_id', 'table_id', 'start')
    def _compute_name(self):
        for r in self:
            who = r.customer_name or r.partner_id.name or 'Guest'
            tbl = ('T%s' % (r.table_id.table_number if r.table_id else '')) if r.table_id else ''
            r.name = '%s · %s' % (who, tbl)

    def _who(self):
        self.ensure_one()
        return self.customer_name or self.partner_id.name or 'Guest'
