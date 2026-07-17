# Part of the Mezze POS platform. See LICENSE (LGPL-3).
"""Kitchen Display System (KDS) ticket state-machine.

A *ticket* is one station's slice of a single fire event. When a waiter fires a
course to an order, we split the newly-fired items by station (Barista / Bar /
Pastry / Kitchen …) and create one ``mezze.kds.ticket`` per station. Each ticket
carries the classic kitchen life-cycle::

    fired -> accepted -> preparing -> ready -> served
                      \\-> cancel

Every transition is persisted with a timestamp *and* broadcast on the real Odoo
bus (``bus.bus``) so any number of KDS screens and waiter tablets stay in sync
in real time. Tickets are insert-only per fire event (keyed by ``fire_uuid``),
which makes concurrent fires to the same table naturally safe — two waiters
firing at once produce two independent tickets, never a lost update.
"""
from odoo import api, fields, models

# Forward-only life-cycle. Index in this list defines "later"; a transition is
# allowed only to a strictly later state (skips permitted, e.g. fired->ready),
# to ``cancel`` from any live state, or one step back via an explicit recall.
FLOW = ['fired', 'accepted', 'preparing', 'ready', 'served']
# state -> the datetime field stamped when the ticket ENTERS that state
STAMP = {
    'accepted': 'accepted_at',
    'preparing': 'preparing_at',
    'ready': 'ready_at',
    'served': 'served_at',
}


class MezzeKdsTicket(models.Model):
    _name = 'mezze.kds.ticket'
    _description = 'Mezze KDS Ticket'
    _order = 'fired_at asc, id asc'

    name = fields.Char(compute='_compute_name', store=True)
    pos_order_id = fields.Many2one(
        'pos.order', required=True, ondelete='cascade', index=True)
    config_id = fields.Many2one(
        'pos.config', related='pos_order_id.config_id', store=True, index=True)
    session_id = fields.Many2one(
        'pos.session', related='pos_order_id.session_id', store=True, index=True)
    station = fields.Char(required=True, index=True)
    state = fields.Selection(
        [('fired', 'Fired'), ('accepted', 'Accepted'), ('preparing', 'Preparing'),
         ('ready', 'Ready'), ('served', 'Served'), ('cancel', 'Cancelled')],
        default='fired', required=True, index=True)
    # Idempotency key of the fire event that created this ticket. A retried fire
    # with the same fire_uuid returns the existing tickets instead of appending.
    fire_uuid = fields.Char(index=True, copy=False)
    # Snapshots taken at fire time so the board reads without extra joins and
    # survives the table being cleared / server reassigned later.
    table_label = fields.Char()
    server_name = fields.Char()
    guests = fields.Integer()
    course = fields.Integer(help="1 for the first fire on this order, 2 for the next, …")

    fired_at = fields.Datetime(default=fields.Datetime.now, index=True)
    accepted_at = fields.Datetime()
    preparing_at = fields.Datetime()
    ready_at = fields.Datetime()
    served_at = fields.Datetime()

    line_ids = fields.One2many('mezze.kds.ticket.line', 'ticket_id')

    @api.depends('table_label', 'station', 'course')
    def _compute_name(self):
        for t in self:
            where = t.table_label or 'Counter'
            t.name = "%s · %s%s" % (
                where, t.station, (' · course %d' % t.course) if t.course > 1 else '')

    # ------------------------------------------------------------------
    # State machine
    # ------------------------------------------------------------------
    def _set_state(self, new_state):
        """Advance one ticket to ``new_state`` under a row lock.

        Locking the row and re-reading the state makes concurrent bumps from two
        KDS screens safe: the first commits, the second sees the fresh state and
        the guard turns its call into a no-op instead of double-advancing.
        Returns ``(changed, reason)``.
        """
        self.ensure_one()
        # Row lock — serialize concurrent transitions on the same ticket.
        self.env.cr.execute(
            "SELECT state FROM mezze_kds_ticket WHERE id = %s FOR UPDATE", (self.id,))
        cur = self.env.cr.fetchone()[0]
        if cur == new_state:
            return (False, 'noop')            # already there — idempotent
        if cur in ('served', 'cancel'):
            return (False, 'terminal')        # can't leave a terminal state
        if new_state == 'cancel':
            ok = True
        elif new_state in FLOW and cur in FLOW:
            ok = FLOW.index(new_state) > FLOW.index(cur)   # forward-only
        else:
            ok = False
        if not ok:
            return (False, 'illegal')
        vals = {'state': new_state}
        if new_state in STAMP and not self[STAMP[new_state]]:
            vals[STAMP[new_state]] = fields.Datetime.now()
        self.write(vals)
        self._broadcast()
        return (True, 'ok')

    def action_recall(self):
        """Step one state backwards (kitchen mis-bump). Broadcasts."""
        self.ensure_one()
        self.env.cr.execute(
            "SELECT state FROM mezze_kds_ticket WHERE id = %s FOR UPDATE", (self.id,))
        cur = self.env.cr.fetchone()[0]
        if cur not in FLOW or FLOW.index(cur) == 0:
            return (False, 'floor')
        prev = FLOW[FLOW.index(cur) - 1]
        self.write({'state': prev})
        self._broadcast()
        return (True, 'ok')

    # ------------------------------------------------------------------
    # Real-time broadcast on the Odoo bus
    # ------------------------------------------------------------------
    def _kds_channel(self):
        return 'mezze_kds_%s' % (self.config_id.id or 0)

    def _waiter_channel(self):
        return 'mezze_waiter_%s' % (self.config_id.id or 0)

    def _payload(self):
        self.ensure_one()
        return {
            'id': self.id,
            'order_id': self.pos_order_id.id,
            'uuid': self.pos_order_id.uuid,
            'tracking': self.pos_order_id.tracking_number or self.pos_order_id.pos_reference or '',
            'station': self.station,
            'state': self.state,
            'table': self.table_label,
            'server': self.server_name,
            'guests': self.guests,
            'course': self.course,
            'fired_at': fields.Datetime.to_string(self.fired_at) if self.fired_at else None,
            'ready_at': fields.Datetime.to_string(self.ready_at) if self.ready_at else None,
            'items': [{'product_id': l.product_id.id, 'name': l.name, 'qty': l.qty,
                       'note': l.note or ''} for l in self.line_ids],
        }

    def _broadcast(self):
        """Push this ticket's new state on the real Odoo bus.

        KDS screens listen on the per-config kitchen channel; waiter tablets
        listen on the waiter channel but only care once a ticket is Ready.
        """
        for t in self:
            payload = t._payload()
            t.env['bus.bus']._sendone(t._kds_channel(), 'mezze_kds_update', payload)
            if t.state == 'ready':
                t.env['bus.bus']._sendone(t._waiter_channel(), 'mezze_waiter_ready', payload)


class MezzeKdsTicketLine(models.Model):
    _name = 'mezze.kds.ticket.line'
    _description = 'Mezze KDS Ticket Line'

    ticket_id = fields.Many2one('mezze.kds.ticket', required=True, ondelete='cascade', index=True)
    product_id = fields.Many2one('product.product', required=True)
    name = fields.Char()
    qty = fields.Float(default=1.0)
    note = fields.Char(help="Modifiers / kitchen note")
