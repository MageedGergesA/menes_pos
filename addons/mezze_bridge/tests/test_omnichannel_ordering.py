"""R2A CP11 — Omnichannel ordering: channel convergence + customer status.

The channels (QR, pickup, delivery, drive-thru, aggregator) already converge on ONE
pos.order with server-authoritative pricing/86, HMAC aggregator, opaque status token
and unified KDS — proven by the existing test_selforder / test_delivery /
test_online_payment / test_runtime_o1 / test_runtime_p1 suites.

This file proves the CP11 HARDENING deltas (which those suites do not cover):

  * staff channel COLLECTION routes are branch-scoped (no cross-branch enumeration):
    delivery/list, drivethru/board, aggregator/orders
  * online-checkout delivery rejects another branch's zone
  * checkout/status no longer leaks the raw internal order.state
  * a pickup order is a canonical pos.order (KDS-fired, no delivery fee)
  * shop client price tampering is ignored (server total wins)
"""
import json
import re

from odoo.tests import tagged

from .common import MezzeHttpCase

_BOOT_RE = re.compile(r'<script[^>]*id="mezze-boot"[^>]*>(.*?)</script>', re.DOTALL)


@tagged('post_install', '-at_install', 'mezze_floor')
class TestOmnichannelOrdering(MezzeHttpCase):
    fixture_profile = 'RESTAURANT'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.product.write({'available_in_pos': True, 'list_price': 42.0, 'taxes_id': [(5, 0, 0)]})
        ICP = cls.env['ir.config_parameter'].sudo()
        ICP.set_param('mezze_bridge.default_branch_id', str(cls.pos_config.id))
        ICP.set_param('mezze_bridge.api_security', 'enforce')
        sess = cls.pos_config.current_session_id
        if not sess or sess.state not in ('opened', 'opening_control'):
            sess = cls.env['pos.session'].create(
                {'config_id': cls.pos_config.id, 'user_id': cls.env.uid})
        if sess.state == 'opening_control':
            try:
                sess.set_opening_control(0, None)
            except Exception:  # noqa: BLE001
                pass
        cls.psession = sess
        # a store token for THIS branch (branch A)
        ICP.set_param('mezze_bridge.store_token_%s' % cls.pos_config.id, 'storeA-tok')
        # the delivery-fee service product is lazily created on first use; pre-create
        # it so the read-only delivery/list render never triggers a write.
        if not cls.env['product.product'].sudo().search([('default_code', '=', 'MEZZE_DELIVERY_FEE')], limit=1):
            cls.env['product.product'].sudo().create({
                'name': 'Delivery', 'default_code': 'MEZZE_DELIVERY_FEE', 'type': 'service',
                'available_in_pos': True, 'taxes_id': [(6, 0, [])], 'list_price': 0.0})

    # -- helpers -----------------------------------------------------------
    def _boot(self, url='/mezze/pos'):
        resp = self.url_open(url)
        self.assertEqual(resp.status_code, 200, url)
        m = _BOOT_RE.search(resp.text)
        self.assertTrue(m, "boot payload present in %s" % url)
        return json.loads(m.group(1).replace('\\u003c', '<'))

    def _api(self, path, params, token=None):
        body = dict(params)
        if token:
            body['token'] = token
        return self.url_open('/mezze/api/v1' + path, data=json.dumps(body),
                             headers={'Content-Type': 'application/json'})

    def _second_branch(self):
        other = self.make_second_pos_config()
        osess = self.env['pos.session'].create({'config_id': other.id, 'user_id': self.env.uid})
        if osess.state == 'opening_control':
            try:
                osess.set_opening_control(0, None)
            except Exception:  # noqa: BLE001
                pass
        return other, osess

    def _order_on(self, config, session, uuid):
        return self.env['pos.order'].sudo().create({
            'session_id': session.id, 'config_id': config.id, 'company_id': config.company_id.id,
            'state': 'draft', 'uuid': uuid, 'amount_total': 42.0, 'amount_tax': 0.0,
            'amount_paid': 0.0, 'amount_return': 0.0,
            'lines': [(0, 0, {'product_id': self.product.id, 'qty': 1, 'price_unit': 42.0,
                              'price_subtotal': 42.0, 'price_subtotal_incl': 42.0})]})

    # ===================== SCOPE (the CP11 fixes) =====================
    def test_cp11_delivery_list_branch_scoped(self):
        self.authenticate('admin', 'admin')
        token = self._boot()['token']
        mine = self.env['mezze.delivery'].sudo().create({
            'pos_order_id': self._order_on(self.pos_config, self.psession, 'cp11-dlv-a').id,
            'customer_name': 'Mine A', 'payment_mode': 'cod', 'address': 'A', 'state': 'accepted'})
        other, osess = self._second_branch()
        foreign = self.env['mezze.delivery'].sudo().create({
            'pos_order_id': self._order_on(other, osess, 'cp11-dlv-b').id,
            'customer_name': 'Foreign B', 'payment_mode': 'cod', 'address': 'B', 'state': 'accepted'})
        for params in ({'scope': 'all'}, {'scope': 'all', 'config_id': other.id}):
            rows = self._api('/delivery/list', params, token).json().get('deliveries', [])
            ids = [d['id'] for d in rows]
            self.assertIn(mine.id, ids, 'own-branch delivery listed (%s)' % params)
            self.assertNotIn(foreign.id, ids, 'cross-branch delivery NOT listed (%s)' % params)

    def test_cp11_drivethru_board_branch_scoped(self):
        self.authenticate('admin', 'admin')
        token = self._boot()['token']
        mine = self.env['mezze.drivethru'].sudo().create({
            'pos_order_id': self._order_on(self.pos_config, self.psession, 'cp11-dt-a').id,
            'customer_name': 'Mine A', 'lane': 1, 'state': 'preparing'})
        other, osess = self._second_branch()
        foreign = self.env['mezze.drivethru'].sudo().create({
            'pos_order_id': self._order_on(other, osess, 'cp11-dt-b').id,
            'customer_name': 'Foreign B', 'lane': 1, 'state': 'preparing'})
        rows = self._api('/drivethru/board', {'config_id': other.id}, token).json().get('cars', [])
        ids = [c['id'] for c in rows]
        self.assertIn(mine.id, ids, 'own-branch car listed')
        self.assertNotIn(foreign.id, ids, 'cross-branch car NOT listed even with spoofed config_id')

    def test_cp11_aggregator_orders_branch_scoped(self):
        self.authenticate('admin', 'admin')
        token = self._boot()['token']
        other, osess = self._second_branch()
        chan_b = self.env['mezze.aggregator'].sudo().create({
            'code': 'foreignagg', 'name': 'Foreign Agg', 'config_id': other.id})
        foreign = self.env['mezze.aggregator.order'].sudo().create({
            'aggregator_id': chan_b.id, 'external_id': 'ext-b-1', 'state': 'received',
            'customer_name': 'Foreign B'})
        # aggregator routes live under /mezze/aggregator/*, not /mezze/api/v1/*
        body = self.url_open('/mezze/aggregator/orders',
                             data=json.dumps({'config_id': other.id, 'token': token}),
                             headers={'Content-Type': 'application/json'}).json()
        agg_ids = [o['id'] for o in body.get('orders', [])]
        chan_ids = [c['id'] for c in body.get('channels', [])]
        self.assertNotIn(foreign.id, agg_ids, 'cross-branch aggregator order NOT listed')
        self.assertNotIn(chan_b.id, chan_ids, 'cross-branch aggregator channel NOT listed')

    # ===================== online-checkout cross-branch zone =====================
    def test_cp11_online_delivery_cross_branch_zone_rejected(self):
        self.authenticate('admin', 'admin')
        other, _ = self._second_branch()
        zone_b = self.env['mezze.delivery.zone'].sudo().create({
            'name': 'Zone B', 'config_id': other.id, 'active': True, 'fee': 5.0, 'min_order': 0.0})
        zone_a = self.env['mezze.delivery.zone'].sudo().create({
            'name': 'Zone A', 'config_id': self.pos_config.id, 'active': True, 'fee': 7.0, 'min_order': 0.0})
        lines = [{'product_id': self.product.id, 'qty': 1}]
        # branch A store token + branch B zone -> rejected, no order
        r = self._api('/checkout/online/create', {
            'store': 'storeA-tok', 'fulfillment': 'delivery', 'zone_id': zone_b.id,
            'address': '10 Foreign St', 'who': 'X', 'lines': lines}).json()
        self.assertFalse(r.get('ok'), 'cross-branch zone refused: %s' % r)
        self.assertFalse(self.env['pos.order'].sudo().search([('uuid', 'like', 'chk-dlv-%')]),
                         'no order created on a rejected cross-branch zone')
        # own-branch zone -> accepted (fix does not over-reject)
        ok = self._api('/checkout/online/create', {
            'store': 'storeA-tok', 'fulfillment': 'delivery', 'zone_id': zone_a.id,
            'address': '1 Home St', 'who': 'Y', 'lines': lines}).json()
        self.assertTrue(ok.get('ok'), 'own-branch zone accepted: %s' % ok)

    # ===================== customer status payload safety =====================
    def test_cp11_checkout_status_hides_raw_order_state(self):
        self.authenticate('admin', 'admin')
        created = self._api('/checkout/online/create', {
            'store': 'storeA-tok', 'fulfillment': 'pickup',
            'lines': [{'product_id': self.product.id, 'qty': 1}]}).json()
        self.assertTrue(created.get('ok'), created)
        token = created['status_token']
        data = self._api('/checkout/status', {'status_token': token}).json()
        self.assertTrue(data.get('ok'), data)
        self.assertNotIn('order_state', data, 'raw internal order.state must not be exposed')
        self.assertIn('public_status', data, 'a mapped customer status is exposed instead')
        self.assertIn(data['public_status'],
                      ('received', 'confirmed', 'preparing', 'ready',
                       'out_for_delivery', 'completed', 'cancelled'))

    # ===================== canonical convergence + KDS =====================
    def test_cp11_pickup_is_canonical_order_kds_no_fee(self):
        self.authenticate('admin', 'admin')
        r = self._api('/shop/order', {
            'store': 'storeA-tok', 'fulfillment': 'pickup', 'customer': 'Mona',
            'lines': [{'product_id': self.product.id, 'qty': 2}]}).json()
        self.assertTrue(r.get('ok'), r)
        order = self.env['pos.order'].sudo().search(
            [('config_id', '=', self.pos_config.id), ('mezze_channel', '=', 'pickup')],
            order='id desc', limit=1)
        self.assertTrue(order, 'pickup created a canonical pos.order')
        self.assertAlmostEqual(order.amount_total, 84.0, places=2, msg='server-priced total')
        # no delivery fee line on a pickup order
        fee_lines = order.lines.filtered(lambda l: (l.product_id.default_code or '') == 'MEZZE_DELIVERY_FEE')
        self.assertFalse(fee_lines, 'pickup has no delivery fee')
        # it reached the KDS
        tickets = self.env['mezze.kds.ticket'].sudo().search([('pos_order_id', '=', order.id)])
        self.assertTrue(tickets, 'pickup order fired to the KDS')

    def test_cp11_shop_price_tamper_ignored(self):
        self.authenticate('admin', 'admin')
        # client claims price_unit=1 and a fat discount; server must ignore both
        r = self._api('/shop/order', {
            'store': 'storeA-tok', 'fulfillment': 'pickup', 'customer': 'Tamper',
            'lines': [{'product_id': self.product.id, 'qty': 1,
                       'price_unit': 1.0, 'discount': 90.0, 'price_subtotal_incl': 1.0}]}).json()
        self.assertTrue(r.get('ok'), r)
        order = self.env['pos.order'].sudo().search(
            [('config_id', '=', self.pos_config.id), ('mezze_channel', '=', 'pickup')],
            order='id desc', limit=1)
        self.assertAlmostEqual(order.amount_total, 42.0, places=2,
                               msg='server price wins over client-submitted $1')
