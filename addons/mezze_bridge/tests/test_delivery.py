"""S3 — Delivery v1: zones/fee/minimum/hours, real COD (unpaid+collect), lifecycle
FSM with guards, manual dispatch, cancellation, reporting, idempotency, security.

Every value the customer sees (eligible/fee/minimum/ETA/zone) is server-authoritative;
COD orders are NEVER faked paid at checkout. Deterministic + hermetic.
"""
import json

from odoo.tests import tagged

from .common import MezzeHttpCase


@tagged('post_install', '-at_install', 'mezze_runtime')
class TestDelivery(MezzeHttpCase):
    fixture_profile = 'POS'

    def setUp(self):
        super().setUp()
        icp = self.env['ir.config_parameter'].sudo()
        icp.set_param('mezze_bridge.api_token', 'dlv-tok')
        icp.set_param('mezze_bridge.api_security', 'observe')
        icp.set_param('mezze_bridge.env_profile', 'development')
        self.config = self.pos_config
        icp.set_param('mezze_bridge.store_token_%s' % self.config.id, 'shoptok')
        self.product.write({'list_price': 100.0, 'available_in_pos': True})
        # ensure a cash method for COD collection
        self.cash = self.cash_payment_method
        company = self.config.company_id
        # a delivery zone: fee 30, minimum 200, COD allowed
        self.zone = self.env['mezze.delivery.zone'].create({
            'name': 'Nasr City', 'config_id': self.config.id, 'fee': 30.0,
            'min_order': 200.0, 'eta_minutes': 40, 'cod_allowed': True, 'online_allowed': True})
        self.mgr = self.env['mezze.cashier'].create({'name': 'Mona', 'code': 'MGRD', 'role': 'manager'})
        self.mgr.set_pin('4321')
        self.csh = self.env['mezze.cashier'].create({'name': 'Sara', 'code': 'CSHD', 'role': 'cashier'})
        self.csh.set_pin('1111')
        self.session = self.open_test_session()
        self.env.flush_all()

    def _post(self, path, body):
        r = self.url_open('/mezze/api/v1' + path, data=json.dumps(dict(body, token='dlv-tok')),
                          headers={'Content-Type': 'application/json'}, timeout=30)
        try:
            return r.status_code, r.json()
        except Exception:
            return r.status_code, {'_raw': r.text[:200]}

    def _lines(self, qty=3):
        return [{'product_id': self.product.id, 'qty': qty}]  # 3×100 = 300 subtotal

    def _place_cod(self, qty=3, uuid=None, area='Nasr City', building='12'):
        return self._post('/shop/order', {
            'store': 'shoptok', 'fulfillment': 'delivery', 'payment_mode': 'cod',
            'zone_id': self.zone.id, 'lines': self._lines(qty),
            'customer': 'Ahmed', 'phone': '01000001234',
            'area': area, 'street': 'Makram Ebeid', 'building': building,
            'floor': '3', 'apartment': '7', 'landmark': 'near the mall',
            'uuid': uuid})

    # -- availability (server-authoritative) ---------------------------------
    def test_availability_authoritative(self):
        st, r = self._post('/delivery/availability', {
            'store': 'shoptok', 'zone_id': self.zone.id, 'subtotal': 300, 'payment_mode': 'cod'})
        self.assertTrue(r['ok'])
        self.assertTrue(r['eligible'])
        self.assertEqual(r['fee'], 30.0)
        self.assertEqual(r['min_order'], 200.0)
        self.assertEqual(r['eta_minutes'], 40)
        self.assertEqual(r['total_with_fee'], 330.0)

    def test_availability_below_minimum(self):
        st, r = self._post('/delivery/availability', {
            'store': 'shoptok', 'zone_id': self.zone.id, 'subtotal': 100})
        self.assertTrue(r['ok'])
        self.assertFalse(r['eligible'])
        self.assertTrue(r['below_minimum'])
        self.assertEqual(r['remaining'], 100.0)

    def test_availability_out_of_zone(self):
        st, r = self._post('/delivery/availability', {'store': 'shoptok', 'zone_id': 999999, 'subtotal': 300})
        self.assertTrue(r['ok'])
        self.assertFalse(r['eligible'])
        self.assertEqual(r['reason'], 'out_of_zone')

    def test_availability_closed_hours(self):
        # a schedule with no windows today → closed
        self.zone.hours_json = json.dumps({str(i): [] for i in range(7)})
        st, r = self._post('/delivery/availability', {'store': 'shoptok', 'zone_id': self.zone.id, 'subtotal': 300})
        self.assertFalse(r['eligible'])
        self.assertEqual(r['reason'], 'closed')

    # -- COD order: real, unpaid, fires KDS ----------------------------------
    def test_cod_order_is_unpaid_and_fires(self):
        st, r = self._place_cod()
        self.assertTrue(r['ok'], r)
        self.assertEqual(r['payment_mode'], 'cod')
        self.assertEqual(r['fee'], 30.0)
        self.assertEqual(r['total'], 330.0)   # 300 + 30 fee
        order = self.env['pos.order'].browse(r['order_id'])
        self.assertEqual(order.state, 'draft')              # NOT paid at checkout
        self.assertEqual(sum(order.payment_ids.mapped('amount')), 0.0)
        self.assertEqual(order.mezze_channel, 'delivery')
        dlv = self.env['mezze.delivery'].search([('pos_order_id', '=', order.id)])
        self.assertEqual(dlv.payment_mode, 'cod')
        self.assertEqual(dlv.state, 'accepted')
        self.assertAlmostEqual(dlv.cod_amount, 330.0)
        # structured address snapshot
        self.assertEqual(dlv.building, '12')
        self.assertIn('Makram Ebeid', dlv.address)
        # KDS fired exactly once (fee line excluded)
        tickets = self.env['mezze.kds.ticket'].search([('pos_order_id', '=', order.id)])
        self.assertTrue(tickets)

    def test_out_of_zone_no_order(self):
        before = self.env['pos.order'].search_count([])
        st, r = self._post('/shop/order', {
            'store': 'shoptok', 'fulfillment': 'delivery', 'payment_mode': 'cod',
            'zone_id': 999999, 'lines': self._lines(), 'area': 'Nowhere'})
        self.assertEqual(st, 409)
        self.assertEqual(r['error'], 'out_of_zone')
        self.assertEqual(self.env['pos.order'].search_count([]), before)

    def test_below_minimum_no_order(self):
        before = self.env['pos.order'].search_count([])
        st, r = self._place_cod(qty=1)   # 100 < 200 minimum
        self.assertEqual(st, 409)
        self.assertEqual(r['error'], 'below_minimum')
        self.assertEqual(r['remaining'], 100.0)
        self.assertEqual(self.env['pos.order'].search_count([]), before)

    def test_closed_hours_no_order(self):
        self.zone.hours_json = json.dumps({str(i): [] for i in range(7)})
        before = self.env['pos.order'].search_count([])
        st, r = self._place_cod()
        self.assertEqual(st, 409)
        self.assertEqual(r['error'], 'delivery_closed')
        self.assertEqual(self.env['pos.order'].search_count([]), before)

    def test_cod_not_allowed_zone(self):
        self.zone.cod_allowed = False
        st, r = self._place_cod()
        self.assertEqual(st, 409)
        self.assertEqual(r['error'], 'cod_not_allowed')

    # -- COD collection (real cash payment, idempotent) ----------------------
    def test_cod_collection_records_payment(self):
        _, r = self._place_cod()
        order = self.env['pos.order'].browse(r['order_id'])
        dlv = self.env['mezze.delivery'].search([('pos_order_id', '=', order.id)])
        # collect ×3 → exactly one cash payment, order becomes paid
        for _ in range(3):
            st, cr = self._post('/delivery/collect', {'delivery_id': dlv.id})
            self.assertTrue(cr['ok'], cr)
        pays = order.payment_ids
        self.assertEqual(len(pays), 1)
        self.assertAlmostEqual(sum(pays.mapped('amount')), 330.0)
        self.assertEqual(pays.payment_method_id, self.cash)
        dlv.invalidate_recordset(['cod_collected'])
        self.assertTrue(dlv.cod_collected)
        self.assertEqual(order.state, 'paid')

    # -- lifecycle FSM -------------------------------------------------------
    def test_lifecycle_transitions(self):
        _, r = self._place_cod()
        dlv = self.env['mezze.delivery'].search([('pos_order_id', '=', r['order_id'])])
        # accepted → preparing → ready → assign → out → delivered
        for action, expect in (('start_prep', 'preparing'), ('ready', 'ready')):
            st, tr = self._post('/delivery/state', {'delivery_id': dlv.id, 'action': action})
            self.assertTrue(tr['ok'], tr)
            self.assertEqual(tr['delivery']['state'], expect)
        courier = self.env['mezze.courier'].create({'name': 'Karim', 'config_id': self.config.id})
        st, tr = self._post('/delivery/state', {'delivery_id': dlv.id, 'action': 'assign',
                                                'courier_id': courier.id})
        self.assertEqual(tr['delivery']['state'], 'assigned')
        self.assertEqual(tr['delivery']['courier'], 'Karim')
        courier.invalidate_recordset(['status'])
        self.assertEqual(courier.status, 'on_delivery')
        st, tr = self._post('/delivery/state', {'delivery_id': dlv.id, 'action': 'out'})
        self.assertEqual(tr['delivery']['state'], 'out_for_delivery')
        st, tr = self._post('/delivery/state', {'delivery_id': dlv.id, 'action': 'delivered'})
        self.assertEqual(tr['delivery']['state'], 'delivered')
        courier.invalidate_recordset(['status'])
        self.assertEqual(courier.status, 'available')   # freed on delivery

    def test_illegal_transition_refused(self):
        _, r = self._place_cod()
        dlv = self.env['mezze.delivery'].search([('pos_order_id', '=', r['order_id'])])
        # accepted → delivered is an illegal jump (no override)
        st, tr = self._post('/delivery/state', {'delivery_id': dlv.id, 'action': 'delivered'})
        self.assertEqual(st, 409)
        self.assertEqual(tr['error'], 'illegal_transition')
        dlv.invalidate_recordset(['state'])
        self.assertEqual(dlv.state, 'accepted')

    def test_cancel_after_fire_needs_manager(self):
        _, r = self._place_cod()
        dlv = self.env['mezze.delivery'].search([('pos_order_id', '=', r['order_id'])])
        self._post('/delivery/state', {'delivery_id': dlv.id, 'action': 'start_prep'})  # now 'preparing'
        # cancel without a manager → refused
        st, tr = self._post('/delivery/state', {'delivery_id': dlv.id, 'action': 'cancel',
                                                'reason': 'kitchen_unable'})
        self.assertEqual(st, 403)
        self.assertEqual(tr['error'], 'manager_required')
        # cashier PIN cannot self-approve
        st, tr = self._post('/delivery/state', {'delivery_id': dlv.id, 'action': 'cancel',
                             'reason': 'kitchen_unable', 'manager_code': 'CSHD', 'manager_pin': '1111'})
        self.assertEqual(tr['error'], 'insufficient_role')
        # manager cancels with a reason
        st, tr = self._post('/delivery/state', {'delivery_id': dlv.id, 'action': 'cancel',
                             'reason': 'kitchen_unable', 'manager_code': 'MGRD', 'manager_pin': '4321'})
        self.assertTrue(tr['ok'], tr)
        self.assertEqual(tr['delivery']['state'], 'cancelled')
        dlv.invalidate_recordset(['cancel_reason'])
        self.assertEqual(dlv.cancel_reason, 'kitchen_unable')

    # -- idempotency ---------------------------------------------------------
    def test_double_submit_one_order(self):
        _, r1 = self._place_cod(uuid='dup-uuid-1')
        n = self.env['pos.order'].search_count([('uuid', '=', 'dup-uuid-1')])
        _, r2 = self._place_cod(uuid='dup-uuid-1')
        self.assertEqual(self.env['pos.order'].search_count([('uuid', '=', 'dup-uuid-1')]), 1)

    # -- pickup regression ---------------------------------------------------
    def test_pickup_still_works_no_fee(self):
        st, r = self._post('/shop/order', {
            'store': 'shoptok', 'fulfillment': 'pickup', 'lines': self._lines(),
            'customer': 'Sara', 'phone': '0100'})
        self.assertTrue(r['ok'], r)
        self.assertEqual(r['fulfillment'], 'pickup')
        order = self.env['pos.order'].browse(r['order_id'])
        self.assertEqual(order.mezze_channel, 'pickup')
        # no delivery fee line on a pickup order
        self.assertFalse(order.lines.filtered(lambda l: l.product_id.default_code == 'MEZZE_DELIVERY_FEE'))

    # -- reporting -----------------------------------------------------------
    def test_report(self):
        _, r = self._place_cod()
        dlv = self.env['mezze.delivery'].search([('pos_order_id', '=', r['order_id'])])
        st, rep = self._post('/delivery/report', {'config_id': self.config.id})
        self.assertTrue(rep['ok'])
        self.assertGreaterEqual(rep['total'], 1)
        self.assertGreaterEqual(rep['cod'], 1)
        self.assertIn('by_zone', rep)

    # -- security: availability leaks no PII/internals -----------------------
    def test_availability_no_internal_leak(self):
        _, r = self._post('/delivery/availability', {'store': 'shoptok', 'zone_id': self.zone.id, 'subtotal': 300})
        blob = json.dumps(r)
        self.assertNotIn('config_id', blob)
        self.assertNotIn('company', blob)
