"""S2C-5 — Online customer payments.

Reuses Odoo's native online-payment engine end to end (pos_online_payment +
the payment framework + provider addons — see docs/…/online-payment-audit.md).
Mezze adds only what Odoo does not own for a *customer-channel* order:

  * ``mezze_online`` marks an order that will be paid online (Table QR / pickup /
    delivery) and whose kitchen work must NOT fire until the payment is
    authoritatively successful (pay-before-fire);
  * ``payment.transaction._process_pos_online_payment`` is extended so that, AFTER
    Odoo's native exactly-once finalization (tx done → account.payment → pos.payment
    → order paid), the KDS fires EXACTLY ONCE for the paid online order — never on
    pending/failed/canceled;
  * a safe customer status projection over the authoritative order/transaction
    state (return-not-authority).

Mezze creates NO second payment engine and never sets ``tx.state`` itself.
"""
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


def mezze_station_of(product):
    """Route a product to a prep station by name/category keywords (mirrors the
    controller's ``_station_of`` so paid-online KDS uses the same routing)."""
    hay = (product.display_name or '').lower()
    if 'pos_categ_ids' in product._fields:
        hay += ' ' + ' '.join(product.pos_categ_ids.mapped('name')).lower()

    def has(*ws):
        return any(w in hay for w in ws)

    if has('espresso', 'latte', 'cappuccino', 'coffee', 'flat white', 'cortado',
           'americano', 'mocha', 'macchiato'):
        return 'Barista'
    if has('tea', 'juice', 'soda', 'cola', 'water', 'drink', 'mojito', 'smoothie',
           'shake', 'lemonade'):
        return 'Bar'
    if has('croissant', 'cake', 'pastry', 'dessert', 'cookie', 'cheesecake', 'muffin',
           'brownie', 'tart', 'pain'):
        return 'Pastry'
    if has('pizza'):
        return 'Pizza'
    if has('salad'):
        return 'Salad'
    return 'Kitchen'


class PosOrderOnline(models.Model):
    _inherit = 'pos.order'

    # Set when a customer-channel order is routed to online payment; its kitchen
    # work is deferred until an authoritative successful payment.
    mezze_online = fields.Boolean(string='Online payment order', default=False, index=True, copy=False)
    # Exactly-once guard for the paid-online KDS fire.
    mezze_kds_fired = fields.Boolean(default=False, copy=False)

    def _mezze_kitchen_items(self):
        """(product, qty, note) tuples for real menu lines — skips fees/tips and
        discount/void lines so the kitchen only sees food."""
        self.ensure_one()
        items = []
        for line in self.lines:
            if line.qty <= 0 or (line.price_unit or 0.0) <= 0:
                continue
            code = (line.product_id.default_code or '').upper()
            if any(t in code for t in ('DELIVERY', 'FEE', 'TIP', 'HALFHALF', 'DISCOUNT')):
                continue
            note = ''
            items.append((line.product_id, line.qty, note))
        return items

    def _mezze_fire_online_kds(self):
        """Fire the KDS for a paid online order EXACTLY ONCE. Concurrency-safe (row
        lock + a durable flag) so duplicate/concurrent/lost-response finalizations
        never double-fire the kitchen. No-op if already fired or nothing to cook."""
        self.ensure_one()
        self.env.cr.execute("SELECT id FROM pos_order WHERE id=%s FOR UPDATE", (self.id,))
        self.invalidate_recordset(['mezze_kds_fired'])
        if self.mezze_kds_fired:
            return self.env['mezze.kds.ticket']
        items = self._mezze_kitchen_items()
        if not items:
            self.mezze_kds_fired = True
            return self.env['mezze.kds.ticket']
        Ticket = self.env['mezze.kds.ticket'].sudo()
        table_label = None
        if 'table_id' in self._fields and self.table_id:
            tbl = self.table_id
            table_label = 'T%s' % (tbl.table_number if 'table_number' in tbl._fields else tbl.id)
        by_station = {}
        for (p, qty, note) in items:
            by_station.setdefault(mezze_station_of(p), []).append((p, qty, note))
        tickets = Ticket.browse()
        fire_uuid = 'online:%s' % (self.pos_reference or self.uuid or self.id)
        for st, its in by_station.items():
            tickets |= Ticket.create({
                'pos_order_id': self.id, 'station': st, 'state': 'fired',
                'fire_uuid': fire_uuid, 'table_label': table_label,
                'server_name': 'Online order', 'guests': self.customer_count or 0, 'course': 1,
                'line_ids': [(0, 0, {'product_id': p.id, 'name': p.display_name,
                                     'qty': q, 'note': n}) for (p, q, n) in its],
            })
        self.mezze_kds_fired = True
        # best-effort real-time push via the transactional outbox (post-commit)
        try:
            sends = tickets._bus_sends()
            if sends:
                self.env['mezze.outbox.event'].publish(
                    'mezze.bus.broadcast', payload={'sends': sends},
                    aggregate_type='pos.order', aggregate_id=str(self.id),
                    idempotency_key='kds:online:%s' % self.id,
                    company_id=self.company_id.id,
                    branch_id=self.config_id.id if self.config_id else None)
        except Exception:  # noqa: BLE001 — never break the payment flow on a push error
            _logger.exception("Mezze online KDS publish failed (order=%s)", self.id)
        return tickets

    def mezze_online_status(self):
        """Safe customer-facing status for an online-payment order. Combines the
        AUTHORITATIVE order state and the latest online payment.transaction state —
        the browser return URL never decides this."""
        self.ensure_one()
        tx = self.env['payment.transaction'].sudo().search(
            [('pos_order_id', '=', self.id)], order='id desc', limit=1)
        paid = self.state in ('paid', 'done', 'invoiced')
        if paid:
            pay = 'success'
        elif tx and tx.state == 'done':
            pay = 'success'
        elif tx and tx.state == 'authorized':
            pay = 'success'
        elif tx and tx.state == 'pending':
            pay = 'pending'
        elif tx and tx.state == 'error':
            pay = 'failed'
        elif tx and tx.state == 'cancel':
            pay = 'canceled'
        elif tx and tx.state == 'draft':
            pay = 'confirming'
        else:
            pay = 'awaiting'
        prec = self.currency_id.decimal_places or 2
        return {
            'payment': pay,                        # awaiting|confirming|pending|success|failed|canceled
            'order_state': self.state,
            'kds_fired': self.mezze_kds_fired,
            'amount_total': round(self.amount_total, prec),
            'amount_due': round(self.amount_total - self.amount_paid, prec),
            'currency': self.currency_id.name,
            'channel': self.mezze_channel or '',
            'reference': self.pos_reference or '',
        }


class PaymentTransactionOnline(models.Model):
    _inherit = 'payment.transaction'

    def _process_pos_online_payment(self):
        """Extend Odoo's native exactly-once POS finalization: after it links the
        payment to the order, fire the kitchen ONCE for a paid Mezze online order.
        Firing rides on the native finalization, so it inherits its exactly-once /
        concurrency / lost-response guarantees. Nothing fires unless the tx is
        authoritatively successful and the order is actually paid."""
        super()._process_pos_online_payment()
        for tx in self:
            order = tx.pos_order_id
            if not order or tx.state not in ('authorized', 'done'):
                continue
            if not order.mezze_online:
                continue
            if order.state in ('paid', 'done', 'invoiced') and not order.mezze_kds_fired:
                try:
                    order._mezze_fire_online_kds()
                except Exception:  # noqa: BLE001 — a KDS failure must not undo a real payment
                    _logger.exception("Mezze online KDS fire failed (tx=%s, order=%s)", tx.id, order.id)


class PosPaymentMethodOnline(models.Model):
    _inherit = 'pos.payment.method'

    @api.model
    def _mezze_get_or_create_online_method(self, config):
        """Ensure the config has an is_online_payment method wired to every
        published, non-disabled provider. Reuses Odoo's own get-or-create.

        NOTE (native POS rule): a config's payment methods can't be changed while a
        session is OPEN. So the online method is attached only when it is safe to do
        so (no open session) — a real deployment provisions it at setup. If a session
        is already open and the method isn't on the config yet, we return it anyway
        (linked to providers); the caller reports 'not configured' rather than
        crashing."""
        company = config.company_id
        pm = self.sudo()._get_or_create_online_payment_method(company.id, config.id)
        providers = self.env['payment.provider'].sudo().search([
            ('company_id', '=', company.id), ('state', 'in', ('enabled', 'test')),
            ('is_published', '=', True)])
        if providers:
            pm.sudo().online_payment_provider_ids = [(6, 0, providers.ids)]
        if pm.id not in config.payment_method_ids.ids and not config.current_session_id:
            config.sudo().write({'payment_method_ids': [(4, pm.id)]})
        return pm
