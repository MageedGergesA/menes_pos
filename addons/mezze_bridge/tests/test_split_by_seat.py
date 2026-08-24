# -*- coding: utf-8 -*-
"""Splitting a table's bill by who ordered what.

Neither Odoo POS nor Mezze had a seat model, which is why "By seat" was offered and
permanently disabled with the reason ``no_seat_model``. That reason was true and
useless: it told a cashier about an absence they could do nothing about, at exactly
the moment a table asks the commonest question at the end of a shared meal.

The design decisions worth testing:

* **Zero is UNASSIGNED, not seat zero.** A bottle of wine in the middle of the table
  belongs to nobody in particular. A split by seat must be able to say that, rather
  than handing it to whoever is listed first — which is precisely the kind of thing a
  guest notices while a card machine is being held out to them.
* **The amounts are the server's.** The same rule as splitting evenly: a browser that
  computes its own version of a total eventually disagrees with the one that gets
  charged.
* **A seat is a SELECTION, not a second commit path.** Taking a seat's check goes
  through the ordinary ``/split/commit``, which already re-checks availability under
  a row lock, moves combos whole, and is idempotent. A by-seat route of its own would
  be a second place for all of that to be got right.
* **A seat shows what is LEFT.** A line half-moved onto another check contributes
  half — otherwise a seat that already paid part of its meal is billed for it twice.
"""
import json

from odoo.tests import tagged

from .common import MezzeHttpCase


@tagged('post_install', '-at_install', 'mezze_seat')
class TestSplitBySeat(MezzeHttpCase):
    fixture_profile = 'POS'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        env['ir.config_parameter'].sudo().set_param('mezze_bridge.api_token', 'st-tok')
        cls.pos_sess = cls._open_session_for(cls.pos_config)
        cls.burger = env['product.product'].sudo().create({
            'name': 'ST Burger', 'available_in_pos': True, 'list_price': 40.0,
            'type': 'consu'})
        cls.wine = env['product.product'].sudo().create({
            'name': 'ST Wine', 'available_in_pos': True, 'list_price': 100.0,
            'type': 'consu'})
        (cls.burger | cls.wine).write({'taxes_id': [(5, 0, 0)]})
        # Splitting is a cashier capability, not an anonymous one — the calls below
        # act as a real cashier rather than as a bare branch token.
        cls.cashier = env['mezze.cashier'].sudo().create(
            {'name': 'Seat Cashier', 'code': 'STCSH', 'role': 'cashier'})
        env.flush_all()

    def _post(self, path, body):
        r = self.url_open('/mezze/api/v1' + path,
                          data=json.dumps(dict(body, token='st-tok',
                                               cashier_id=self.cashier.id)),
                          headers={'Content-Type': 'application/json'})
        return r.json()

    def _table_order(self, uuid='st-1', lines=None):
        payload = {'uuid': uuid, 'session_id': self.pos_sess.id, 'draft': True,
                   'lines': lines if lines is not None else [
                       {'product_id': self.burger.id, 'qty': 1, 'seat': 1},
                       {'product_id': self.burger.id, 'qty': 1, 'seat': 2},
                       {'product_id': self.wine.id, 'qty': 1},
                   ]}
        res = self._post('/orders/sync', payload)
        self.assertTrue(res.get('ok'), res)
        self.env.invalidate_all()
        return self.env['pos.order'].sudo().search([('uuid', '=', uuid)], limit=1)

    # ── the seat itself ───────────────────────────────────────────────────
    def test_01_a_seat_survives_the_sync(self):
        order = self._table_order()
        seats = sorted(l.mezze_seat for l in order.lines)
        self.assertEqual(seats, [0, 1, 2],
                         'the seats did not reach the database: %r' % seats)

    def test_02_two_guests_ordering_the_same_dish_are_two_lines(self):
        # Merging them would put one plate on the bill and lose which of them is
        # paying for it.
        order = self._table_order()
        burgers = order.lines.filtered(lambda l: l.product_id == self.burger)
        self.assertEqual(len(burgers), 2,
                         'the two burgers were merged into one line')

    def test_03_an_unassigned_line_is_shared_not_seat_zero(self):
        order = self._table_order()
        wine = order.lines.filtered(lambda l: l.product_id == self.wine)
        self.assertEqual(wine.mezze_seat, 0)

    def test_04_a_nonsense_seat_is_dropped_rather_than_refusing_the_sale(self):
        # A seat is an annotation on an order. Refusing to sell a meal because a
        # browser sent "3a" would be the wrong trade.
        order = self._table_order('st-bad', [
            {'product_id': self.burger.id, 'qty': 1, 'seat': '3a'}])
        self.assertEqual(order.lines[0].mezze_seat, 0)

    def test_05_an_absurd_seat_number_is_dropped(self):
        order = self._table_order('st-big', [
            {'product_id': self.burger.id, 'qty': 1, 'seat': 5000}])
        self.assertEqual(order.lines[0].mezze_seat, 0)

    # ── the mode gate ─────────────────────────────────────────────────────
    def test_10_by_seat_turns_on_once_a_seat_is_assigned(self):
        order = self._table_order('st-on')
        d = self._post('/split/state', {'order_id': order.id})
        self.assertTrue(d['modes']['seat'], d['modes'])
        self.assertEqual(d['modes']['seat_reason'], '')

    def test_11_and_stays_off_with_an_actionable_reason_otherwise(self):
        order = self._table_order('st-off', [
            {'product_id': self.burger.id, 'qty': 2}])
        d = self._post('/split/state', {'order_id': order.id})
        self.assertFalse(d['modes']['seat'])
        self.assertEqual(d['modes']['seat_reason'], 'no_seats_assigned')

    # ── the grouping ──────────────────────────────────────────────────────
    def test_20_each_seat_gets_its_own_total(self):
        order = self._table_order('st-tot')
        d = self._post('/split/seats', {'order_id': order.id})
        self.assertTrue(d.get('ok'), d)
        by_seat = {s['seat']: s for s in d['seats']}
        self.assertEqual(sorted(by_seat), [1, 2])
        self.assertAlmostEqual(by_seat[1]['amount'], 40.0, places=2)
        self.assertAlmostEqual(by_seat[2]['amount'], 40.0, places=2)

    def test_21_the_shared_bottle_is_not_given_to_seat_one(self):
        # THE rule this feature exists to get right.
        order = self._table_order('st-shr')
        d = self._post('/split/seats', {'order_id': order.id})
        self.assertAlmostEqual(d['shared_total'], 100.0, places=2)
        for s in d['seats']:
            self.assertNotIn('ST Wine', json.dumps(s['lines']),
                             'the shared bottle was attached to seat %s' % s['seat'])

    def test_22_the_seats_and_the_shared_add_up_to_the_bill(self):
        order = self._table_order('st-sum')
        d = self._post('/split/seats', {'order_id': order.id})
        total = sum(s['amount'] for s in d['seats']) + d['shared_total']
        self.assertAlmostEqual(total, order.amount_total, places=2,
                              msg='the seats do not reconcile to the bill')

    def test_23_a_seat_shows_what_is_left_not_what_was_ordered(self):
        # A line already moved onto another check contributes what remains, or a
        # seat that has part-paid is billed for it twice.
        order = self._table_order('st-part', [
            {'product_id': self.burger.id, 'qty': 2, 'seat': 1}])
        line = order.lines[0]
        moved = self._post('/split/commit', {
            'order_id': order.id, 'idempotency_key': 'st-part-k1',
            'allocations': [{'origin_line_id': line.id, 'quantity': 1}]})
        self.assertTrue(moved.get('ok'), moved)
        d = self._post('/split/seats', {'order_id': order.id})
        seat1 = [s for s in d['seats'] if s['seat'] == 1][0]
        self.assertAlmostEqual(seat1['amount'], 40.0, places=2,
                               msg='the seat was billed for a plate already moved')

    def test_24_a_bill_with_no_seats_reports_everything_as_shared(self):
        order = self._table_order('st-none', [
            {'product_id': self.wine.id, 'qty': 1}])
        d = self._post('/split/seats', {'order_id': order.id})
        self.assertEqual(d['seats'], [])
        self.assertAlmostEqual(d['shared_total'], 100.0, places=2)

    # ── committing a seat ─────────────────────────────────────────────────
    def test_30_a_seats_selection_commits_through_the_ordinary_route(self):
        order = self._table_order('st-cmt')
        d = self._post('/split/seats', {'order_id': order.id})
        seat1 = [s for s in d['seats'] if s['seat'] == 1][0]
        allocations = [{'origin_line_id': r['line_id'], 'quantity': r['qty']}
                       for r in seat1['lines']]
        res = self._post('/split/commit', {
            'order_id': order.id, 'idempotency_key': 'st-cmt-k1',
            'allocations': allocations})
        self.assertTrue(res.get('ok'), res)
        self.assertAlmostEqual(res['child']['amount_total'], 40.0, places=2)

    def test_31_the_child_keeps_the_seat_it_came_from(self):
        # A check handed to seat 1 that has forgotten it is seat 1 cannot be
        # reconciled with the table afterwards.
        order = self._table_order('st-keep')
        d = self._post('/split/seats', {'order_id': order.id})
        seat1 = [s for s in d['seats'] if s['seat'] == 1][0]
        res = self._post('/split/commit', {
            'order_id': order.id, 'idempotency_key': 'st-keep-k1',
            'allocations': [{'origin_line_id': r['line_id'], 'quantity': r['qty']}
                            for r in seat1['lines']]})
        self.assertTrue(res.get('ok'), res)
        self.env.invalidate_all()
        child = self.env['pos.order'].sudo().browse(res['child']['id'])
        self.assertEqual(child.lines[0].mezze_seat, 1,
                         'the seat did not travel onto the new check')

    def test_33_recombining_brings_the_seat_home(self):
        # A check pulled back onto the table by mistake must not cost the table its
        # seat assignments.
        order = self._table_order('st-recomb', [
            {'product_id': self.burger.id, 'qty': 1, 'seat': 3}])
        line = order.lines[0]
        made = self._post('/split/commit', {
            'order_id': order.id, 'idempotency_key': 'st-recomb-k1',
            'allocations': [{'origin_line_id': line.id, 'quantity': 1}]})
        self.assertTrue(made.get('ok'), made)
        back = self._post('/split/recombine', {'child_id': made['child']['id']})
        self.assertTrue(back.get('ok'), back)
        self.env.invalidate_all()
        order = self.env['pos.order'].sudo().search([('uuid', '=', 'st-recomb')], limit=1)
        self.assertEqual(sorted(l.mezze_seat for l in order.lines), [3],
                         'the seat was lost on the way back to the table')

    def test_32_after_taking_a_seat_it_is_gone_from_the_grouping(self):
        order = self._table_order('st-gone')
        d = self._post('/split/seats', {'order_id': order.id})
        seat1 = [s for s in d['seats'] if s['seat'] == 1][0]
        self._post('/split/commit', {
            'order_id': order.id, 'idempotency_key': 'st-gone-k1',
            'allocations': [{'origin_line_id': r['line_id'], 'quantity': r['qty']}
                            for r in seat1['lines']]})
        again = self._post('/split/seats', {'order_id': order.id})
        self.assertEqual([s['seat'] for s in again['seats']], [2],
                         'a seat already taken is still being offered')
