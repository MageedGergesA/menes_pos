"""Drive-thru handoff safety — a car may not be handed food that is not cooked.

Before this, `collected` required payment only. Kitchen readiness was returned by
the board (`kitchen_ready`) and shown on the row, but nothing stopped the
transition, so a mis-tap handed out an order the kitchen was still preparing.

The gate is SERVER-side on purpose: a disabled button is a hint, not a control. A
client holding a stale board — or any other caller of the endpoint — must be
refused at mutation time.
"""
import json

from odoo.tests import tagged

from .common import MezzeHttpCase


@tagged('post_install', '-at_install', 'mezze_runtime', 'mezze_drivethru_gate')
class TestDriveThruHandoffGate(MezzeHttpCase):
    fixture_profile = 'POS'

    def setUp(self):
        super().setUp()
        icp = self.env['ir.config_parameter'].sudo()
        icp.set_param('mezze_bridge.api_token', 'gate-tok')
        icp.set_param('mezze_bridge.api_security', 'observe')
        icp.set_param('mezze_bridge.env_profile', 'development')
        self.session = self.open_test_session()
        self.product = self.env['product.product'].search(
            [('available_in_pos', '=', True)], limit=1)
        self.env.flush_all()

    def _post(self, path, body):
        r = self.url_open('/mezze/api/v1' + path, data=json.dumps(dict(body, token='gate-tok')),
                          headers={'Content-Type': 'application/json'}, timeout=30)
        try:
            return r.status_code, r.json()
        except Exception:
            return r.status_code, {'_raw': r.text[:200]}

    def _car(self, paid, kitchen_ready):
        """A car in one of the four truth-table states."""
        order = self.env['pos.order'].create({
            'session_id': self.session.id, 'company_id': self.company.id,
            'lines': [(0, 0, {'product_id': self.product.id, 'qty': 1,
                              'price_unit': 10.0, 'price_subtotal': 10.0,
                              'price_subtotal_incl': 10.0})],
            'amount_total': 10.0, 'amount_tax': 0.0,
            'amount_paid': 10.0 if paid else 0.0, 'amount_return': 0.0})
        car = self.env['mezze.drivethru'].create({
            'pos_order_id': order.id, 'lane': 1, 'vehicle': 'RED SUV',
            'state': 'ready' if kitchen_ready else 'preparing'})
        # Kitchen readiness is DERIVED from the order's KDS tickets, so a ticket is
        # what makes it false — not the drivethru state field.
        if not kitchen_ready:
            self.env['mezze.kds.ticket'].create({
                'pos_order_id': order.id, 'station': 'Kitchen', 'state': 'preparing'})
        self.env.flush_all()
        self.assertEqual(car._paid(), paid)
        self.assertEqual(car._kitchen_ready(), kitchen_ready)
        return car

    def _collect(self, car):
        return self._post('/drivethru/stage',
                          {'drivethru_id': car.id, 'action': 'collected'})

    # ---- the four-way truth table ------------------------------------------
    def test_paid_and_kitchen_not_ready_is_denied(self):
        car = self._car(paid=True, kitchen_ready=False)
        code, res = self._collect(car)
        self.assertEqual(code, 409, res)
        self.assertEqual(res.get('error'), 'kitchen_not_ready')
        self.assertNotEqual(car.state, 'collected', 'nothing was handed off')

    def test_unpaid_and_kitchen_ready_is_denied(self):
        car = self._car(paid=False, kitchen_ready=True)
        code, res = self._collect(car)
        self.assertEqual(code, 409, res)
        self.assertEqual(res.get('error'), 'unpaid')
        self.assertNotEqual(car.state, 'collected')

    def test_unpaid_and_kitchen_not_ready_is_denied(self):
        car = self._car(paid=False, kitchen_ready=False)
        code, res = self._collect(car)
        self.assertEqual(code, 409, res)
        # payment is reported first; either refusal is correct, but it must refuse
        self.assertIn(res.get('error'), ('unpaid', 'kitchen_not_ready'))
        self.assertNotEqual(car.state, 'collected')

    def test_paid_and_kitchen_ready_passes(self):
        car = self._car(paid=True, kitchen_ready=True)
        code, res = self._collect(car)
        self.assertEqual(code, 200, res)
        self.assertTrue(res.get('ok'), res)
        car.invalidate_recordset()
        self.assertEqual(car.state, 'collected')
        self.assertTrue(car.collected_at, 'the handoff is timestamped')

    # ---- the gate is not a disabled button ----------------------------------
    def test_a_stale_client_cannot_smuggle_a_handoff(self):
        # The client may have read a board where the order looked ready. The check
        # runs at MUTATION time against live state, so it still refuses.
        car = self._car(paid=True, kitchen_ready=True)
        ticket = self.env['mezze.kds.ticket'].create(
            {'pos_order_id': car.pos_order_id.id, 'station': 'Kitchen', 'state': 'preparing'})
        self.env.flush_all()
        self.assertFalse(car._kitchen_ready(), 'the kitchen went back to work')
        code, res = self._collect(car)
        self.assertEqual(code, 409, res)
        self.assertEqual(res.get('error'), 'kitchen_not_ready')
        self.assertTrue(ticket.exists())

    # ---- idempotency ---------------------------------------------------------
    def test_collecting_twice_does_not_corrupt_the_record(self):
        car = self._car(paid=True, kitchen_ready=True)
        code1, _r1 = self._collect(car)
        self.assertEqual(code1, 200)
        car.invalidate_recordset()
        first = car.collected_at
        code2, res2 = self._collect(car)
        car.invalidate_recordset()
        self.assertEqual(car.state, 'collected', 'still collected, not corrupted')
        self.assertEqual(car.collected_at, first,
                         'the original handoff timestamp is not overwritten (%s)' % res2)
