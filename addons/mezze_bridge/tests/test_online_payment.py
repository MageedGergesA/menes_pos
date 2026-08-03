"""S2C-5 — Online customer payments.

Two concerns:
  * TestCheckoutHttp — the Mezze customer-checkout boundary (server-authoritative
    create, 86/zone revalidation BEFORE any order, native pay-URL handoff, tokenized
    status, IDOR). Always run.
  * TestOnlineFinalization — the pay-before-fire KDS hook + status mapping over the
    authoritative payment.transaction state, incl. exactly-once. Uses the Demo
    provider; the true end-to-end (Demo UI → tx done → pos.payment) is also
    browser-proven.
"""
import json

from odoo.tests import tagged

from .common import MezzeHttpCase


@tagged('post_install', '-at_install', 'mezze_runtime')
class TestCheckoutHttp(MezzeHttpCase):
    fixture_profile = 'POS'

    def setUp(self):
        super().setUp()
        icp = self.env['ir.config_parameter'].sudo()
        icp.set_param('mezze_bridge.api_token', 'oc-tok')
        icp.set_param('mezze_bridge.api_security', 'observe')
        icp.set_param('mezze_bridge.env_profile', 'development')
        # publish the Demo provider for this company so an online method is available
        self.demo = self.env.ref('payment.payment_provider_demo').sudo()
        bankj = self.env['account.journal'].search(
            [('type', '=', 'bank'), ('company_id', '=', self.company.id)], limit=1)
        if not bankj:
            bankj = self.env['account.journal'].create(
                {'name': 'Bank OC', 'code': 'OCBK', 'type': 'bank', 'company_id': self.company.id})
        self.demo.with_context(allowed_company_ids=[self.company.id]).write(
            {'company_id': self.company.id, 'state': 'test', 'is_published': True,
             'journal_id': bankj.id})
        # a real menu product + a store token for the branch
        self.prod = self._fixture_products['plain'] if hasattr(self, '_fixture_products') else \
            self.env['product.product'].search([('available_in_pos', '=', True)], limit=1)
        self.prod.write({'pos_categ_ids': [(6, 0, self.env['pos.category'].search([], limit=1).ids
                                            or [self.env['pos.category'].create({'name': 'C'}).id])]})
        self.store = self.env['ir.config_parameter'].sudo().get_param(
            'mezze_bridge.store_token_%s' % self.pos_config.id)
        if not self.store:
            self.store = 'st0123456789abcdef'
            self.env['ir.config_parameter'].sudo().set_param(
                'mezze_bridge.store_token_%s' % self.pos_config.id, self.store)
        # provision the online payment method on the config BEFORE opening a session
        # (native POS forbids changing payment methods while a session is open)
        self.env['pos.payment.method']._mezze_get_or_create_online_method(self.pos_config)
        self.open_test_session()
        self.env.flush_all()

    def _post(self, path, body):
        r = self.url_open('/mezze/api/v1' + path, data=json.dumps(dict(body, token='oc-tok')),
                          headers={'Content-Type': 'application/json'}, timeout=30)
        try:
            return r.status_code, r.json()
        except Exception:
            return r.status_code, {'_raw': r.text[:200]}

    def _lines(self, qty=2):
        return [{'product_id': self.prod.id, 'qty': qty}]

    def _paycount(self, order_id):
        return self.env['pos.payment'].search_count([('pos_order_id', '=', order_id)])

    def _kdscount(self, order_id):
        return self.env['mezze.kds.ticket'].search_count([('pos_order_id', '=', order_id)])

    # -- create ---------------------------------------------------------------
    def test_create_pickup_deferred_no_fire(self):
        st, r = self._post('/checkout/online/create',
                           {'store': self.store, 'fulfillment': 'pickup', 'lines': self._lines(2)})
        self.assertTrue(r['ok'], r)
        self.assertTrue(r['status_token'])
        order = self.env['pos.order']._mezze_resolve_status_token(r['status_token'])
        self.assertTrue(order)
        self.assertTrue(order.mezze_online)
        self.assertEqual(order.state, 'draft')
        # server-authoritative total (client sent no total); kitchen NOT fired yet
        self.assertGreater(order.amount_total, 0)
        self.assertEqual(self._kdscount(order.id), 0)
        self.assertEqual(self._paycount(order.id), 0)

    def test_86_blocks_before_order(self):
        # 86 the product on this branch
        self.env['mezze.hardware'] if False else None
        before = self.env['pos.order'].search_count([])
        # mark unavailable
        self.prod.write({'available_in_pos': False})
        st, r = self._post('/checkout/online/create',
                           {'store': self.store, 'fulfillment': 'pickup', 'lines': self._lines()})
        self.assertEqual(st, 400)
        self.assertEqual(r['error'], 'checkout_rejected')
        self.assertEqual(self.env['pos.order'].search_count([]), before)  # no order created

    # -- pay handoff ----------------------------------------------------------
    def test_pay_returns_native_pos_pay_url(self):
        _, r = self._post('/checkout/online/create',
                          {'store': self.store, 'fulfillment': 'pickup', 'lines': self._lines()})
        tok = r['status_token']
        st, p = self._post('/checkout/online/pay', {'status_token': tok})
        self.assertTrue(p['ok'], p)
        self.assertIn('/pos/pay/', p['pay_url'])
        self.assertIn('access_token=', p['pay_url'])
        # the order now has an online method with a provider
        order = self.env['pos.order']._mezze_resolve_status_token(tok)
        self.assertTrue(order.access_token)
        self.assertEqual(self._paycount(order.id), 0)  # no payment taken at handoff

    # -- status + IDOR --------------------------------------------------------
    def test_status_and_idor(self):
        _, r = self._post('/checkout/online/create',
                          {'store': self.store, 'fulfillment': 'pickup', 'lines': self._lines()})
        tok = r['status_token']
        st, s = self._post('/checkout/status', {'status_token': tok})
        self.assertTrue(s['ok'])
        self.assertEqual(s['payment'], 'awaiting')
        # a wrong/guessed token cannot read any order
        st, s2 = self._post('/checkout/status', {'status_token': 'deadbeef' * 4})
        self.assertEqual(st, 404)

    def test_forged_success_has_no_finalize_endpoint(self):
        """There is NO Mezze endpoint that can mark an order paid — only the
        authoritative payment.transaction can. A public 'paid=true' is inert."""
        _, r = self._post('/checkout/online/create',
                          {'store': self.store, 'fulfillment': 'pickup', 'lines': self._lines()})
        tok = r['status_token']
        order = self.env['pos.order']._mezze_resolve_status_token(tok)
        # try to force it via status / pay with a fabricated success flag
        self._post('/checkout/status', {'status_token': tok, 'paid': True, 'state': 'done'})
        self._post('/checkout/online/pay', {'status_token': tok, 'paid': True})
        self.assertEqual(order.state, 'draft')
        self.assertEqual(self._paycount(order.id), 0)


@tagged('post_install', '-at_install', 'mezze_runtime')
class TestOnlineFinalization(MezzeHttpCase):
    fixture_profile = 'POS'

    def setUp(self):
        super().setUp()
        self.demo = self.env.ref('payment.payment_provider_demo').sudo()
        bankj = self.env['account.journal'].search(
            [('type', '=', 'bank'), ('company_id', '=', self.company.id)], limit=1) or \
            self.env['account.journal'].create(
                {'name': 'Bank OF', 'code': 'OFBK', 'type': 'bank', 'company_id': self.company.id})
        self.demo.with_context(allowed_company_ids=[self.company.id]).write(
            {'company_id': self.company.id, 'state': 'test', 'is_published': True,
             'journal_id': bankj.id})
        self.method = self.env['pos.payment.method']._mezze_get_or_create_online_method(self.pos_config)
        self.partner = self.env['res.partner'].create({'name': 'Online Cust'})
        self.demo_pm = self.env.ref('payment_demo.payment_method_demo')
        self.session = self.open_test_session()
        self.env.flush_all()

    def _online_order(self, price=100.0):
        o = self.create_order_in_test_session(price=price, session=self.session)
        o.write({'state': 'draft', 'mezze_online': True, 'partner_id': self.partner.id})
        self.env.flush_all()
        return o

    def _tx(self, order):
        return self.env['payment.transaction'].create({
            'provider_id': self.demo.id, 'payment_method_id': self.demo_pm.id,
            'reference': 'OC-%s' % order.id, 'amount': order.amount_total,
            'currency_id': order.currency_id.id, 'partner_id': self.partner.id,
            'pos_order_id': order.id})

    def _kds(self, o):
        return self.env['mezze.kds.ticket'].search_count([('pos_order_id', '=', o.id)])

    def _pay(self, o):
        return self.env['pos.payment'].search_count([('pos_order_id', '=', o.id)])

    # -- pure hook: exactly-once KDS + status --------------------------------
    def test_kds_fire_once_idempotent(self):
        o = self._online_order()
        t1 = o._mezze_fire_online_kds()
        n1 = self._kds(o)
        t2 = o._mezze_fire_online_kds()   # again
        self.assertGreater(n1, 0)
        self.assertEqual(self._kds(o), n1)   # no double-fire
        self.assertTrue(o.mezze_kds_fired)

    def test_status_maps_tx_states(self):
        o = self._online_order()
        self.assertEqual(o.mezze_online_status()['payment'], 'awaiting')
        tx = self._tx(o)
        tx._set_pending()
        self.assertEqual(o.mezze_online_status()['payment'], 'pending')
        tx._set_error('x')
        self.assertEqual(o.mezze_online_status()['payment'], 'failed')

    # -- native finalization (Demo) ------------------------------------------
    def test_demo_success_one_effect(self):
        o = self._online_order()
        tx = self._tx(o)
        tx._set_done()
        tx._post_process()
        self.assertEqual(o.state, 'paid')
        self.assertEqual(self._pay(o), 1)
        self.assertGreater(self._kds(o), 0)             # kitchen fired on paid
        self.assertTrue(o.mezze_kds_fired)
        self.assertEqual(o.mezze_online_status()['payment'], 'success')

    def test_demo_pending_then_done(self):
        o = self._online_order()
        tx = self._tx(o)
        tx._set_pending()
        tx._post_process()
        self.assertEqual(o.state, 'draft')
        self.assertEqual(self._pay(o), 0)
        self.assertEqual(self._kds(o), 0)               # nothing fires on pending
        # now it settles
        tx._set_done()
        tx._post_process()
        self.assertEqual(o.state, 'paid')
        self.assertEqual(self._pay(o), 1)
        self.assertGreater(self._kds(o), 0)

    def test_demo_error_no_effect(self):
        o = self._online_order()
        tx = self._tx(o)
        tx._set_error('declined')
        tx._post_process()
        self.assertEqual(o.state, 'draft')
        self.assertEqual(self._pay(o), 0)
        self.assertEqual(self._kds(o), 0)

    def test_demo_cancel_no_effect(self):
        o = self._online_order()
        tx = self._tx(o)
        tx._set_canceled()
        tx._post_process()
        self.assertEqual(o.state, 'draft')
        self.assertEqual(self._pay(o), 0)
        self.assertEqual(self._kds(o), 0)

    def test_duplicate_finalization_one_effect(self):
        o = self._online_order()
        tx = self._tx(o)
        tx._set_done()
        tx._post_process()
        tx._post_process()   # replay the same successful finalization
        tx._post_process()
        self.assertEqual(self._pay(o), 1)               # ONE payment
        # KDS tickets fired exactly once
        fired = self.env['mezze.kds.ticket'].search([('pos_order_id', '=', o.id)])
        self.assertEqual(len(set(fired.mapped('fire_uuid'))), 1)
