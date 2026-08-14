"""DT-UX5 — the kitchen can tell a car from a counter order.

`/drivethru/create` never stamped `pos.order.mezze_channel`, so drive-thru orders
read as plain counter orders everywhere downstream: the KDS badge, reporting by
channel, analytics. Delivery, kiosk, pickup and aggregator all stamp it; drive-thru
was the one flow that did not.

Identity on the ticket is resolved from the CAR RELATION rather than copied onto
the ticket, so lane and vehicle stay in one place and a ticket whose car is gone
degrades to absent rather than to a stale label.
"""
import json

from odoo import fields
from odoo.tests import tagged

from .common import MezzeHttpCase


@tagged('post_install', '-at_install', 'mezze_runtime', 'mezze_drivethru_kds')
class TestDriveThruKdsIdentity(MezzeHttpCase):
    fixture_profile = 'POS'

    def setUp(self):
        super().setUp()
        icp = self.env['ir.config_parameter'].sudo()
        icp.set_param('mezze_bridge.api_token', 'kds-tok')
        icp.set_param('mezze_bridge.api_security', 'observe')
        icp.set_param('mezze_bridge.env_profile', 'development')
        self.session = self.open_test_session()
        self.product = self.env['product.product'].search(
            [('available_in_pos', '=', True)], limit=1)
        self.env['mezze.kds.ticket'].sudo().search([]).unlink()
        self.env['mezze.drivethru'].sudo().search([]).unlink()
        self.env.flush_all()

    def _post(self, path, body):
        r = self.url_open('/mezze/api/v1' + path, data=json.dumps(dict(body, token='kds-tok')),
                          headers={'Content-Type': 'application/json'}, timeout=30)
        try:
            return r.status_code, r.json()
        except Exception:
            return r.status_code, {'_raw': r.text[:200]}

    def _order(self, channel=None):
        order = self.env['pos.order'].create({
            'session_id': self.session.id, 'company_id': self.company.id,
            'lines': [(0, 0, {'product_id': self.product.id, 'qty': 1,
                              'price_unit': 10.0, 'price_subtotal': 10.0,
                              'price_subtotal_incl': 10.0})],
            'amount_total': 10.0, 'amount_tax': 0.0,
            'amount_paid': 0.0, 'amount_return': 0.0})
        if channel:
            order.mezze_channel = channel
        return order

    def _ticket(self, order):
        return self.env['mezze.kds.ticket'].create(
            {'pos_order_id': order.id, 'station': 'Kitchen', 'state': 'preparing'})

    def _car(self, order, lane=1, vehicle='RED SUV'):
        return self.env['mezze.drivethru'].create(
            {'pos_order_id': order.id, 'lane': lane, 'vehicle': vehicle, 'state': 'preparing'})

    # ---- channel identity ---------------------------------------------------
    def test_creating_a_car_stamps_the_canonical_channel(self):
        code, res = self._post('/drivethru/create', {
            'session_id': self.session.id, 'lane': 1, 'vehicle': 'RED SUV',
            'lines': [{'product_id': self.product.id, 'qty': 1}]})
        self.assertEqual(code, 200, res)
        car = self.env['mezze.drivethru'].search([], order='id desc', limit=1)
        self.assertTrue(car, res)
        self.assertEqual(car.pos_order_id.mezze_channel, 'drivethru',
                         'the order itself knows it is drive-thru')

    def test_the_channel_survives_payment_and_collection(self):
        order = self._order()
        car = self._car(order)
        order.mezze_channel = 'drivethru'
        self.env.flush_all()
        car.write({'state': 'at_window'})
        order.write({'amount_paid': order.amount_total})
        self.env.flush_all()
        self._post('/drivethru/stage', {'drivethru_id': car.id, 'action': 'collected'})
        order.invalidate_recordset()
        self.assertEqual(order.mezze_channel, 'drivethru',
                         'identity is not lost when the car leaves')

    # ---- KDS payload --------------------------------------------------------
    def test_the_ticket_carries_lane_vehicle_and_a_clock_basis(self):
        order = self._order('drivethru')
        car = self._car(order, lane=2, vehicle='WHITE SEDAN')
        ticket = self._ticket(order)
        self.env.flush_all()
        payload = ticket._payload()
        self.assertEqual(payload['channel'], 'drivethru')
        dt = payload.get('drivethru')
        self.assertTrue(dt, 'drive-thru context is present')
        self.assertEqual(dt['lane'], 2)
        self.assertEqual(dt['vehicle'], 'WHITE SEDAN')
        self.assertEqual(dt['id'], car.id)
        self.assertTrue(dt['placed_at'], 'the same clock basis as the board')

    def test_a_counter_ticket_carries_no_vehicle_context(self):
        # No empty lane, no placeholder vehicle on non-drive-thru work.
        ticket = self._ticket(self._order('pos'))
        self.env.flush_all()
        payload = ticket._payload()
        self.assertNotEqual(payload['channel'], 'drivethru')
        self.assertFalse(payload.get('drivethru'),
                         'a counter ticket has no car (%s)' % payload.get('drivethru'))

    def test_identity_works_for_orders_created_before_the_channel_stamp(self):
        # Resolved from the RELATION, so historical rows need no data rewrite.
        order = self._order()                       # deliberately NO channel
        self._car(order, lane=1, vehicle='BLACK SUV')
        ticket = self._ticket(order)
        self.env.flush_all()
        payload = ticket.with_context(
            mezze_dt_map=ticket._drivethru_map())._payload()
        self.assertTrue(payload.get('drivethru'), 'the car is still resolvable')
        self.assertEqual(payload['drivethru']['vehicle'], 'BLACK SUV')

    def test_the_board_resolves_every_car_in_one_query(self):
        # The KDS board renders every ticket in a comprehension; a per-ticket lookup
        # would be an N+1 on the hottest screen in the product.
        tickets = self.env['mezze.kds.ticket']
        for i in range(8):
            order = self._order('drivethru')
            self._car(order, lane=(i % 2) + 1, vehicle='CAR %d' % i)
            tickets |= self._ticket(order)
        for _i in range(6):
            tickets |= self._ticket(self._order('pos'))
        self.env.flush_all()
        self.env.invalidate_all()
        mapping = tickets._drivethru_map()
        self.assertEqual(len(mapping), 8, 'every car resolved by ONE search')

        # Count actual car lookups while rendering. The shape is what matters: with
        # the map prefetched, rendering 14 tickets must not go back for a car even
        # once — that is the difference between O(1) and O(n) on the hottest screen.
        calls = []
        Drivethru = type(self.env['mezze.drivethru'])
        original = Drivethru.search

        def counting_search(self_model, *args, **kwargs):
            calls.append(1)
            return original(self_model, *args, **kwargs)

        Drivethru.search = counting_search
        try:
            payloads = [t._payload() for t in
                        tickets.with_context(mezze_dt_map=mapping)]
        finally:
            Drivethru.search = original
        self.assertEqual(len(calls), 0,
                         'no per-ticket car lookup (%d extra searches)' % len(calls))
        self.assertEqual(len([p for p in payloads if p.get('drivethru')]), 8)
        self.assertEqual(len([p for p in payloads if not p.get('drivethru')]), 6)

    # ---- end to end ---------------------------------------------------------
    def test_kds_ready_makes_the_car_ready_for_handoff(self):
        # The one contract Pickup depends on: KDS marks ready -> server truth
        # changes -> handoff becomes allowed. No second readiness field.
        order = self._order('drivethru')
        car = self._car(order)
        ticket = self._ticket(order)
        order.write({'amount_paid': order.amount_total})
        car.write({'state': 'at_window'})
        self.env.flush_all()
        self.assertFalse(car._kitchen_ready(), 'still cooking')
        self.assertEqual(self._post('/drivethru/stage',
                                    {'drivethru_id': car.id, 'action': 'collected'})[0], 409)
        ticket.write({'state': 'ready'})
        self.env.flush_all()
        self.assertTrue(car._kitchen_ready(), 'KDS readiness is the single authority')
        code, res = self._post('/drivethru/stage',
                               {'drivethru_id': car.id, 'action': 'collected'})
        self.assertEqual(code, 200, res)

    def test_one_ready_station_is_not_a_ready_order(self):
        # Two stations, one ready: the order is not ready and must not be handed off.
        order = self._order('drivethru')
        car = self._car(order)
        grill = self._ticket(order)
        drinks = self.env['mezze.kds.ticket'].create(
            {'pos_order_id': order.id, 'station': 'Drinks', 'state': 'preparing'})
        order.write({'amount_paid': order.amount_total})
        car.write({'state': 'at_window'})
        grill.write({'state': 'ready'})
        self.env.flush_all()
        self.assertFalse(car._kitchen_ready(), 'one station ready is not the order ready')
        self.assertEqual(self._post('/drivethru/stage',
                                    {'drivethru_id': car.id, 'action': 'collected'})[0], 409)
        drinks.write({'state': 'ready'})
        self.env.flush_all()
        self.assertTrue(car._kitchen_ready())
