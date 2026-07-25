"""Runtime proof that real payment/refund/KDS code now USES the outbox.

Tagged ``mezze_runtime``. Exercises the actual controller publication helpers and
the migrated KDS consumer against a real Odoo + PostgreSQL: transactional publish,
rollback removes the event, publication idempotency, the KDS consumer pushing the
bus AFTER dispatch (and not redelivering), dead-letter on a bad payload, retry on
a transient failure, and strict fire -> paid -> refunded ordering on one order.
"""

from odoo import fields
from odoo.tests import common, tagged

from odoo.addons.mezze_bridge.controllers.main import MezzeBridgeController
from ..models.outbox_event import OUTBOX_CONSUMERS, OutboxRetry


def _paid_order(env, amount=10.0):
    s = env['pos.session'].search([('state', '=', 'opened')], limit=1)
    if not s:
        s = env['pos.session'].create({'config_id': env['pos.config'].search([], limit=1).id,
                                       'user_id': env.uid})
    c = s.config_id
    p = (env['product.product'].search([('available_in_pos', '=', True)], limit=1)
         or env['product.product'].search([], limit=1))
    o = env['pos.order'].create({
        'session_id': s.id, 'company_id': c.company_id.id,
        'lines': [(0, 0, {'product_id': p.id, 'qty': 1, 'price_unit': amount,
                          'price_subtotal': amount, 'price_subtotal_incl': amount, 'tax_ids': [(6, 0, [])]})],
        'amount_tax': 0.0, 'amount_total': amount, 'amount_paid': 0.0, 'amount_return': 0.0,
        'pricelist_id': c.pricelist_id.id or False})
    o.add_payment({'amount': amount, 'payment_method_id': c.payment_method_ids[:1].id,
                   'name': fields.Datetime.now(), 'pos_order_id': o.id})
    try:
        o.action_pos_order_paid()
    except Exception:  # noqa: BLE001
        o.write({'state': 'paid'})
    return o


@tagged('post_install', '-at_install', 'mezze_runtime')
class TestOutboxAdoption(common.TransactionCase):

    def setUp(self):
        super().setUp()
        self.ctrl = MezzeBridgeController()
        self.Event = self.env['mezze.outbox.event']
        self.order = _paid_order(self.env, 10.0)

    def _events(self, event_type, agg=None):
        dom = [('event_type', '=', event_type)]
        if agg is not None:
            dom.append(('aggregate_id', '=', str(agg)))
        return self.Event.search(dom)

    def _drain(self, **kw):
        for _ in range(20):
            if self.Event._dispatch_batch(commit=False, **kw)['claimed'] == 0:
                break

    # ---------------------------------------------------------- publication
    def test_payment_publishes_order_paid(self):
        self.ctrl._publish_order_paid(self.env, self.order)
        ev = self._events('order.paid.v1', self.order.id)
        self.assertEqual(len(ev), 1)
        self.assertEqual(ev.idempotency_key, 'order.paid:%s' % self.order.uuid)
        self.assertEqual(ev.status, 'pending')
        self.assertEqual(ev.aggregate_type, 'pos.order')

    def test_payment_publication_idempotent(self):
        self.ctrl._publish_order_paid(self.env, self.order)
        self.ctrl._publish_order_paid(self.env, self.order)   # duplicate pay -> one event
        self.assertEqual(len(self._events('order.paid.v1', self.order.id)), 1)

    def test_refund_publishes_order_refunded(self):
        refund = _paid_order(self.env, 4.0)
        self.ctrl._publish_order_refunded(self.env, refund, refund.uuid, self.order)
        ev = self._events('order.refunded.v1', self.order.id)   # aggregated on original
        self.assertEqual(len(ev), 1)
        self.assertEqual(ev.idempotency_key, 'order.refunded:%s' % refund.uuid)

    def test_publish_rolls_back_with_business_txn(self):
        before = self.Event.search_count([])
        try:
            with self.env.cr.savepoint():
                self.ctrl._publish_order_paid(self.env, self.order)
                raise RuntimeError('force rollback')
        except RuntimeError:
            pass
        self.assertFalse(self._events('order.paid.v1', self.order.id),
                         "event survived a rolled-back business transaction")
        self.assertEqual(self.Event.search_count([]), before)

    # ------------------------------------------------------------- KDS path
    def _kds_event(self, channel='mezze_kds_test', ready=False):
        sends = [{'channel': channel, 'message_type': 'mezze_kds_update', 'body': {'x': 1}}]
        return self.Event.publish('mezze.bus.broadcast', payload={'sends': sends},
                                  aggregate_type='pos.order', aggregate_id=str(self.order.id))

    def _bus_count(self, channel):
        self.env.flush_all()
        self.env.cr.execute("SELECT count(*) FROM bus_bus WHERE channel LIKE %s", ('%' + channel + '%',))
        return self.env.cr.fetchone()[0]

    def test_kds_consumer_pushes_bus_after_dispatch(self):
        ch = 'mezze_kds_adopt_%d' % self.order.id
        before = self._bus_count(ch)
        ev = self._kds_event(channel=ch)
        self.assertEqual(ev.status, 'pending')
        self.assertEqual(self._bus_count(ch), before, "bus pushed BEFORE dispatch")  # not yet
        self._drain()
        self.assertEqual(ev.status, 'done')
        self.assertEqual(self._bus_count(ch), before + 1, "KDS bus not pushed by dispatcher")
        # idempotent: a second sweep does not redeliver a done event
        self._drain()
        self.assertEqual(self._bus_count(ch), before + 1)

    def test_kds_consumer_dead_letters_bad_payload(self):
        ev = self.Event.publish('mezze.bus.broadcast',
                                payload={'sends': [{'message_type': 'x', 'body': {}}]},  # no channel
                                aggregate_type='pos.order', aggregate_id='bad-%d' % self.order.id)
        self._drain(max_attempts=8)
        self.assertEqual(ev.status, 'dead', "bad payload should dead-letter, not spin")

    def test_transient_failure_retries(self):
        et = 'test.adopt.transient'
        state = {'n': 0}

        def handler(env, event):
            state['n'] += 1
            if state['n'] == 1:
                raise OutboxRetry('transient bus error')
        OUTBOX_CONSUMERS[et] = handler
        try:
            ev = self.Event.publish(et, payload={}, aggregate_type='pos.order',
                                    aggregate_id='tr-%d' % self.order.id)
            self.Event._dispatch_batch(commit=False, max_attempts=5)
            self.assertEqual(ev.status, 'failed')
            ev.next_retry = fields.Datetime.now()
            self.Event._dispatch_batch(commit=False, max_attempts=5)
            self.assertEqual(ev.status, 'done')
        finally:
            OUTBOX_CONSUMERS.pop(et, None)

    # ------------------------------------------------------------- ordering
    def test_fire_paid_refund_ordering(self):
        types = ('mezze.bus.broadcast', 'order.paid.v1', 'order.refunded.v1')
        saved = {t: OUTBOX_CONSUMERS.get(t) for t in types}
        log = []
        for t in types:
            OUTBOX_CONSUMERS[t] = (lambda env, ev, _t=t: log.append(_t))
        try:
            agg = 'ord-%d' % self.order.id
            # publish in the causal order Fire -> Paid -> Refund on ONE aggregate
            self.Event.publish('mezze.bus.broadcast', payload={'sends': []},
                               aggregate_type='pos.order', aggregate_id=agg)
            self.Event.publish('order.paid.v1', payload={}, aggregate_type='pos.order', aggregate_id=agg)
            self.Event.publish('order.refunded.v1', payload={}, aggregate_type='pos.order', aggregate_id=agg)
            self._drain()
            self.assertEqual(log, list(types), "fire/paid/refund delivered out of order")
        finally:
            for t, fn in saved.items():
                if fn is None:
                    OUTBOX_CONSUMERS.pop(t, None)
                else:
                    OUTBOX_CONSUMERS[t] = fn

    def test_different_orders_dispatch_independently(self):
        other = _paid_order(self.env, 7.0)
        self.ctrl._publish_order_paid(self.env, self.order)
        self.ctrl._publish_order_paid(self.env, other)
        m = self.Event._dispatch_batch(commit=False, batch_size=50)
        self.assertGreaterEqual(m['claimed'], 2)   # distinct aggregates, both claimable at once
