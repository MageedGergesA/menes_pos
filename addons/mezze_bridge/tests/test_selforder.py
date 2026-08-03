"""S4 — customer self-ordering: kiosk (pay-at-counter), price/discount injection
rejected, modifier over-selection rejected, 86, channel pause/resume + governance,
self-order status + by-channel analytics. Deterministic + hermetic.

Table-QR ordering, two-phone concurrency, combos, and the status token are already
certified (S1–S3) and reused unchanged — these tests cover the S4 additions.
"""
import json

from odoo.tests import tagged

from .common import MezzeHttpCase


@tagged('post_install', '-at_install', 'mezze_runtime')
class TestSelfOrder(MezzeHttpCase):
    fixture_profile = 'POS'

    def setUp(self):
        super().setUp()
        icp = self.env['ir.config_parameter'].sudo()
        icp.set_param('mezze_bridge.api_token', 'so-tok')
        icp.set_param('mezze_bridge.api_security', 'observe')
        icp.set_param('mezze_bridge.env_profile', 'development')
        self.config = self.pos_config
        icp.set_param('mezze_bridge.store_token_%s' % self.config.id, 'sostore')
        self.product.write({'list_price': 100.0, 'available_in_pos': True})
        self.cash = self.cash_payment_method
        self.session = self.open_test_session()
        self.env.flush_all()

    def _post(self, path, body):
        r = self.url_open('/mezze/api/v1' + path, data=json.dumps(dict(body, token='so-tok')),
                          headers={'Content-Type': 'application/json'}, timeout=30)
        try:
            return r.status_code, r.json()
        except Exception:
            return r.status_code, {'_raw': r.text[:200]}

    def _lines(self, qty=2, **extra):
        return [dict({'product_id': self.product.id, 'qty': qty}, **extra)]

    # -- kiosk: real pay-at-counter (unpaid) ---------------------------------
    def test_kiosk_order_pay_at_counter(self):
        st, r = self._post('/shop/order', {'store': 'sostore', 'fulfillment': 'kiosk',
                                           'service_mode': 'eat_in', 'lines': self._lines(2),
                                           'uuid': 'kiosk-1'})
        self.assertTrue(r['ok'], r)
        self.assertEqual(r['fulfillment'], 'kiosk')
        self.assertEqual(r['payment_mode'], 'pay_at_counter')
        self.assertEqual(r['service_mode'], 'eat_in')
        order = self.env['pos.order'].browse(r['order_id'])
        self.assertEqual(order.state, 'draft')                 # NOT paid at the kiosk
        self.assertEqual(sum(order.payment_ids.mapped('amount')), 0.0)
        self.assertEqual(order.mezze_channel, 'kiosk')
        self.assertEqual(order.mezze_service_mode, 'eat_in')
        self.assertTrue(self.env['mezze.kds.ticket'].search([('pos_order_id', '=', order.id)]))
        self.assertTrue(r['status_token'])

    # -- §63 price / discount injection rejected -----------------------------
    def test_price_injection_ignored(self):
        # client tries price_unit=1 and discount=100 on a 100-each product
        st, r = self._post('/shop/order', {
            'store': 'sostore', 'fulfillment': 'kiosk', 'lines': self._lines(2, price_unit=1, discount=100),
            'uuid': 'inject-1'})
        self.assertTrue(r['ok'], r)
        order = self.env['pos.order'].browse(r['order_id'])
        # server recomputes: 2 × 100 (+ tax), never 2 × 1
        self.assertGreaterEqual(order.amount_total, 200.0)

    # -- modifier over-selection rejected ------------------------------------
    def test_modifier_over_selection_rejected(self):
        attr = self.env['product.attribute'].create({
            'name': 'Size', 'create_variant': 'no_variant', 'display_type': 'radio'})
        v1 = self.env['product.attribute.value'].create({'name': 'S', 'attribute_id': attr.id})
        v2 = self.env['product.attribute.value'].create({'name': 'L', 'attribute_id': attr.id})
        aline = self.env['product.template.attribute.line'].create({
            'product_tmpl_id': self.product.product_tmpl_id.id, 'attribute_id': attr.id,
            'value_ids': [(6, 0, [v1.id, v2.id])]})
        both = aline.product_template_value_ids.ids   # 2 values for a single-select
        self.env.flush_all()
        before = self.env['pos.order'].search_count([])
        st, r = self._post('/shop/order', {
            'store': 'sostore', 'fulfillment': 'kiosk', 'uuid': 'mod-1',
            'lines': [{'product_id': self.product.id, 'qty': 1, 'attribute_value_ids': both}]})
        self.assertFalse(r['ok'])
        self.assertEqual(self.env['pos.order'].search_count([]), before)   # no order

    # -- 86 blocks a kiosk order ---------------------------------------------
    def test_86_blocks_kiosk(self):
        self._post('/menu/eightysix', {'config_id': self.config.id,
                                       'product_id': self.product.id, 'available': False})
        before = self.env['pos.order'].search_count([])
        st, r = self._post('/shop/order', {'store': 'sostore', 'fulfillment': 'kiosk',
                                           'lines': self._lines(1), 'uuid': '86-1'})
        self.assertFalse(r['ok'])
        self.assertEqual(self.env['pos.order'].search_count([]), before)

    # -- pause / resume + governance -----------------------------------------
    def test_pause_blocks_then_resume(self):
        st, r = self._post('/selforder/pause', {'config_id': self.config.id,
                                                'channel': 'kiosk', 'paused': True})
        self.assertTrue(r['ok'])
        self.assertTrue(r['paused'])
        before = self.env['pos.order'].search_count([])
        st, r = self._post('/shop/order', {'store': 'sostore', 'fulfillment': 'kiosk',
                                           'lines': self._lines(1), 'uuid': 'pause-1'})
        self.assertEqual(st, 409)
        self.assertEqual(r['error'], 'selforder_paused')
        self.assertEqual(self.env['pos.order'].search_count([]), before)   # nothing into nowhere
        # resume
        self._post('/selforder/pause', {'config_id': self.config.id, 'channel': 'kiosk', 'paused': False})
        st, r = self._post('/shop/order', {'store': 'sostore', 'fulfillment': 'kiosk',
                                           'lines': self._lines(1), 'uuid': 'pause-2'})
        self.assertTrue(r['ok'], r)

    # -- self-order status ---------------------------------------------------
    def test_status_channels(self):
        self._post('/selforder/pause', {'config_id': self.config.id, 'channel': 'delivery', 'paused': True})
        st, r = self._post('/selforder/status', {'store': 'sostore'})
        self.assertTrue(r['ok'])
        self.assertTrue(r['open'])                     # a session is open
        self.assertTrue(r['channels']['kiosk'])        # kiosk available
        self.assertFalse(r['channels']['delivery'])    # delivery paused
        blob = json.dumps(r)
        self.assertNotIn('company', blob)

    # -- by-channel analytics ------------------------------------------------
    def test_report_by_channel(self):
        self._post('/shop/order', {'store': 'sostore', 'fulfillment': 'kiosk',
                                   'lines': self._lines(2), 'uuid': 'rep-1'})
        st, rep = self._post('/selforder/report', {'config_id': self.config.id})
        self.assertTrue(rep['ok'])
        self.assertGreaterEqual(rep['total'], 1)
        self.assertIn('kiosk', rep['by_channel'])
        self.assertGreaterEqual(rep['payment_due'], 1)   # kiosk order is unpaid (due)
        self.assertTrue(rep['top_items'])
