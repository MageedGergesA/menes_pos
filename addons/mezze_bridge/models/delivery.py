# Part of the Mezze POS platform. See LICENSE (LGPL-3).
"""Delivery orders — the last-mile leg on top of a real pos.order.

A delivery is a real ``pos.order`` (paid online/prepaid, OR unpaid Cash-on-Delivery)
that fires to the kitchen like any other order, plus this record tracking the
off-premise leg: structured address, fee, payment mode, courier and a server-
authoritative dispatch lifecycle. Kitchen readiness is derived from the order's KDS
tickets, so the delivery board reflects the real prep state.

S3: manual dispatch only — NO route optimization, GPS or fleet management.
"""
import json

from odoo import api, fields, models
from odoo.exceptions import UserError

# Weekday-indexed delivery-hours default (empty ⇒ open whenever a POS session is open).

# Server-authoritative lifecycle (§39). Transitions are guarded by _transition().
STATES = [
    ('placed', 'Placed'),            # created, awaiting acceptance (manual-accept only)
    ('accepted', 'Accepted'),        # restaurant accepted → will prepare
    ('preparing', 'Preparing'),      # kitchen working (KDS fired)
    ('ready', 'Ready'),              # food done, awaiting a courier
    ('assigned', 'Assigned'),        # a courier is assigned, not yet gone
    ('out_for_delivery', 'Out for delivery'),
    ('delivered', 'Delivered'),
    ('cancelled', 'Cancelled'),
    ('rejected', 'Rejected'),
]
TERMINAL = ('delivered', 'cancelled', 'rejected')
# Legal forward transitions: state -> {action: next_state}
_LEGAL = {
    'placed': {'accept': 'accepted', 'reject': 'rejected', 'cancel': 'cancelled'},
    'accepted': {'start_prep': 'preparing', 'cancel': 'cancelled'},
    'preparing': {'ready': 'ready', 'cancel': 'cancelled'},
    # from ready you may dispatch straight out (with a free-text rider) OR assign a
    # courier record first — both are supported for manual dispatch.
    'ready': {'assign': 'assigned', 'out': 'out_for_delivery', 'cancel': 'cancelled'},
    'assigned': {'out': 'out_for_delivery', 'unassign': 'ready', 'cancel': 'cancelled'},
    'out_for_delivery': {'delivered': 'delivered', 'cancel': 'cancelled'},
}
_CANCEL_REASONS = [
    ('customer_request', 'Customer request'), ('unavailable_item', 'Unavailable item'),
    ('outside_area', 'Outside delivery area'), ('kitchen_unable', 'Kitchen unable'),
    ('duplicate', 'Duplicate order'), ('payment_issue', 'Payment issue'), ('other', 'Other'),
]


class MezzeDeliveryZone(models.Model):
    _name = 'mezze.delivery.zone'
    _description = 'Mezze Delivery Zone'
    _order = 'priority asc, sequence asc, id asc'

    name = fields.Char(required=True)
    config_id = fields.Many2one('pos.config', index=True)
    fee = fields.Float(help="Delivery fee charged for this zone")
    min_order = fields.Float(help="Minimum food subtotal to deliver to this zone")
    eta_minutes = fields.Integer(default=45, help="Typical door-to-door minutes")
    sequence = fields.Integer(default=10)
    priority = fields.Integer(default=10, help="Lower wins when zones overlap")
    active = fields.Boolean(default=True)
    # S3 richness — which tenders this zone accepts.
    cod_allowed = fields.Boolean(string='Cash on delivery allowed', default=True)
    online_allowed = fields.Boolean(string='Online payment allowed', default=True)
    # Narrow per-zone delivery hours: JSON {weekday(0=Mon): [[from_min, to_min], ...]}.
    # Empty/blank ⇒ open whenever a POS session is open (no extra restriction).
    hours_json = fields.Char(string='Delivery hours (JSON)', default='')

    def _is_open(self, when):
        """True if the zone delivers at datetime ``when`` (naive UTC ok for v1).
        Empty schedule ⇒ always open. Never trusts the client."""
        self.ensure_one()
        raw = (self.hours_json or '').strip()
        if not raw:
            return True
        try:
            sched = json.loads(raw)
        except (ValueError, TypeError):
            return True
        windows = sched.get(str(when.weekday())) or []
        minute = when.hour * 60 + when.minute
        return any(int(a) <= minute < int(b) for a, b in windows)

    def _safe(self, when=None):
        """PII-free public projection for the storefront."""
        self.ensure_one()
        return {
            'id': self.id, 'name': self.name, 'fee': round(self.fee, 2),
            'min_order': round(self.min_order, 2), 'eta_minutes': self.eta_minutes,
            'cod_allowed': self.cod_allowed, 'online_allowed': self.online_allowed,
            'open': self._is_open(when) if when else True,
        }


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
    # Structured MENA address (immutable snapshot on the order) + composed display text.
    address = fields.Text(help='Composed display snapshot (immutable operational fact).')
    area = fields.Char()
    street = fields.Char()
    building = fields.Char()
    floor = fields.Char()
    apartment = fields.Char()
    landmark = fields.Char()

    fee = fields.Float()
    zone_id = fields.Many2one('mezze.delivery.zone', ondelete='set null')
    # S3 payment mode: cod (unpaid until collected) | online | prepaid (legacy immediate).
    payment_mode = fields.Selection(
        [('cod', 'Cash on delivery'), ('online', 'Online'), ('prepaid', 'Prepaid')],
        default='cod', required=True, index=True)
    cod_amount = fields.Float(help='Cash to collect on delivery (order total).')
    cod_collected = fields.Boolean(default=False, index=True)
    cod_collected_at = fields.Datetime()
    cod_payment_id = fields.Many2one('pos.payment', ondelete='set null', copy=False,
                                     help='The ONE cash payment recorded at collection.')

    # Manual dispatch (§46-48).
    courier_id = fields.Many2one('mezze.courier', ondelete='set null', index=True)
    rider = fields.Char(help='Legacy free-text courier label (superseded by courier_id).')
    assigned_by = fields.Char()
    assigned_at = fields.Datetime()

    state = fields.Selection(STATES, default='accepted', required=True, index=True)
    cancel_reason = fields.Selection(_CANCEL_REASONS)
    reject_reason = fields.Char()
    eta = fields.Datetime()
    eta_minutes = fields.Integer(default=45)
    note = fields.Char()

    placed_at = fields.Datetime(default=fields.Datetime.now, index=True)
    accepted_at = fields.Datetime()
    ready_at = fields.Datetime()
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
        """True when every KDS ticket for this order is ready/served."""
        self.ensure_one()
        tickets = self.env['mezze.kds.ticket'].search([('pos_order_id', '=', self.pos_order_id.id)])
        if not tickets:
            return True
        return all(t.state in ('ready', 'served') for t in tickets)

    # ------------------------------------------------------------------ address
    @api.model
    def _compose_address(self, parts):
        """Build the display snapshot from structured parts (order kept human-natural)."""
        seq = []
        for key, label in (('apartment', 'Apt'), ('floor', 'Floor'), ('building', 'Bldg'),
                           ('street', ''), ('area', ''), ('landmark', '')):
            v = (parts.get(key) or '').strip()
            if v:
                seq.append(('%s %s' % (label, v)).strip())
        return ', '.join(seq)

    # ------------------------------------------------------------------ lifecycle
    def _transition(self, action, actor=None, reason=None, courier=None, override=False):
        """Server-authoritative FSM step (§40). Rejects illegal jumps unless a manager
        ``override`` documents a recovery. Stamps timestamps + writes an audit line."""
        self.ensure_one()
        if self.state in TERMINAL and not override:
            raise UserError("This delivery is already %s." % dict(STATES)[self.state])
        legal = _LEGAL.get(self.state, {})
        nxt = legal.get(action)
        if not nxt and not override:
            raise UserError("Cannot %s a delivery that is %s." % (action, self.state))
        if action == 'reject' and not (reason or '').strip():
            raise UserError("A reason is required to reject a delivery.")
        if action == 'cancel' and not reason:
            raise UserError("A cancellation reason is required.")
        if action == 'assign' and not courier:
            raise UserError("A courier is required to assign a delivery.")
        vals = {'state': nxt or self.state}
        now = fields.Datetime.now()
        if nxt == 'accepted':
            vals['accepted_at'] = now
        elif nxt == 'ready':
            vals['ready_at'] = now
        elif nxt == 'out_for_delivery':
            vals['dispatched_at'] = now
        elif nxt == 'delivered':
            vals['delivered_at'] = now
        if action == 'assign':
            vals.update({'courier_id': courier.id, 'assigned_by': actor or '',
                         'assigned_at': now, 'rider': courier.name})
            courier.status = 'on_delivery'
        if action == 'unassign':
            vals.update({'courier_id': False, 'rider': False})
        if action == 'cancel':
            vals['cancel_reason'] = reason
        if action == 'reject':
            vals['reject_reason'] = (reason or '')[:200]
        # a completed delivery frees its courier
        if nxt in ('delivered', 'cancelled', 'rejected') and self.courier_id:
            self.courier_id.status = 'available'
        self.write(vals)
        self._log('delivery.%s' % action, {
            'delivery': self.id, 'order': self.pos_order_id.id, 'to': vals['state'],
            'actor': actor or '', 'reason': reason or '', 'override': bool(override),
            'courier': courier.name if courier else ''})
        return self

    # ------------------------------------------------------------------ COD
    def _collect_cod(self, actor=None):
        """Record the ONE real cash pos.payment when the driver hands cash back /
        the cashier confirms collection (§31). Idempotent; never fakes receipt before
        this. Only for COD deliveries with an unpaid order."""
        self.ensure_one()
        if self.payment_mode != 'cod':
            raise UserError("Only a Cash-on-Delivery order can be collected.")
        # serialise + idempotent on this delivery row
        self.env.cr.execute("SELECT id FROM mezze_delivery WHERE id=%s FOR UPDATE", (self.id,))
        self.invalidate_recordset(['cod_collected', 'cod_payment_id'])
        if self.cod_collected and self.cod_payment_id:
            return self.cod_payment_id
        order = self.pos_order_id
        prec = order.currency_id.decimal_places or 2
        due = round(order.amount_total - sum(order.payment_ids.mapped('amount')), prec)
        if due <= 0:
            self.write({'cod_collected': True, 'cod_collected_at': fields.Datetime.now()})
            return self.env['pos.payment']
        method = self._cod_cash_method(order.config_id)
        key = 'cod-%s' % self.id
        existing = order.payment_ids.filtered(lambda p: p.mezze_tender_key == key)
        if not existing:
            order.add_payment({
                'amount': due, 'payment_method_id': method.id, 'name': fields.Datetime.now(),
                'pos_order_id': order.id, 'mezze_tender_key': key,
                'mezze_confirmation_source': 'manual'})
            existing = order.payment_ids.filtered(lambda p: p.mezze_tender_key == key)
        pay = existing[:1]
        eps = 1.0 / (10 ** prec)
        if round(order.amount_total - sum(order.payment_ids.mapped('amount')), prec) <= eps \
                and order.state == 'draft':
            order.action_pos_order_paid()
        self.write({'cod_collected': True, 'cod_collected_at': fields.Datetime.now(),
                    'cod_payment_id': pay.id})
        self._log('delivery.cod_collected',
                  {'delivery': self.id, 'order': order.id, 'amount': due, 'actor': actor or ''})
        return pay

    @api.model
    def _cod_cash_method(self, config):
        """The branch cash pos.payment.method for recording collected COD cash."""
        cash = config.payment_method_ids.filtered(
            lambda m: m.is_cash_count or m.mezze_mode == 'cash')[:1]
        return cash or config.payment_method_ids[:1]

    # ------------------------------------------------------------------ projection
    def _safe(self, staff=False):
        """Dashboard/status projection. ``staff`` includes operational detail; the
        public customer view (staff=False) hides phone/full address/internal notes."""
        self.ensure_one()
        order = self.pos_order_id
        base = {
            'id': self.id, 'state': self.state,
            'tracking': order.tracking_number or order.pos_reference or '',
            'total': round(order.amount_total, 2), 'fee': round(self.fee, 2),
            'payment_mode': self.payment_mode, 'eta_minutes': self.eta_minutes,
            'kitchen_ready': self._kitchen_ready(),
        }
        if not staff:
            base['area'] = self.area or ''
            return base
        base.update({
            'customer': self._who(), 'phone': self.phone or '',
            'area': self.area or '', 'address': self.address or '',
            'note': self.note or '',
            'courier': self.courier_id.name or self.rider or '',
            'courier_id': self.courier_id.id or False,
            'cod_collected': self.cod_collected,
            'cod_amount': round(self.cod_amount, 2) if self.payment_mode == 'cod' else 0.0,
            'paid': round(sum(order.payment_ids.mapped('amount')), 2),
            'placed_at': fields.Datetime.to_string(self.placed_at) if self.placed_at else '',
        })
        return base

    def _log(self, event, detail, severity='info'):
        try:
            self.env['mezze.audit.log'].sudo().log(
                event, severity=severity, res_model='pos.order',
                res_id=self.pos_order_id.id, res_uuid=self.pos_order_id.uuid or False,
                detail=json.dumps(detail, default=str))
        except Exception:  # noqa: BLE001
            pass
