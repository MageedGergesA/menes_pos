# -*- coding: utf-8 -*-
"""Four people, one bill.

``domain.split_bill.even_amounts`` has been in the tree, correct and unit-tested,
since split bill was written — and nothing in the product ever called it. Worse,
``/split/state`` advertised ``modes.even = True``, so the server was telling the till
it could do something no code implemented.

Splitting evenly is a PAYMENT pattern, not a restructuring of the order. The items
stay where they are and no child checks are created: four people paying a quarter
each still ate one meal, and the kitchen, the reports and the audit trail should go
on seeing one order. Each share is then tendered through the ordinary payment route,
which brings its own ceilings and approvals with it.

The property worth the endpoint is that the shares **sum back to the bill**. 100 into
3 is 33.34 / 33.33 / 33.33 — never 99.99, never 100.01 — with the odd cents going to
the earliest shares deterministically, so the same bill always divides the same way
and a report can be reproduced. That arithmetic is done on the server precisely so a
browser cannot be the thing that loses a cent.
"""
import json

from odoo.tests import tagged

from .common import MezzeHttpCase


@tagged('post_install', '-at_install', 'mezze_split_even')
class TestSplitEvenly(MezzeHttpCase):
    fixture_profile = 'POS'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        env['ir.config_parameter'].sudo().set_param('mezze_bridge.api_token', 'se-tok')
        cls.pos_sess = cls._open_session_for(cls.pos_config)
        cls.cash = cls.pos_config.payment_method_ids.filtered('is_cash_count')[:1]
        cls.dish = env['product.product'].sudo().create({
            'name': 'SE Plate', 'available_in_pos': True, 'list_price': 100.0,
            'type': 'consu'})
        cls.dish.write({'taxes_id': [(5, 0, 0)]})
        env.flush_all()

    def _order(self, total=100.0):
        o = self.env['pos.order'].sudo().create({
            'session_id': self.pos_sess.id,
            'company_id': self.pos_config.company_id.id,
            'lines': [(0, 0, {'product_id': self.dish.id, 'qty': 1,
                              'price_unit': total, 'price_subtotal': total,
                              'price_subtotal_incl': total, 'tax_ids': [(6, 0, [])]})],
            'amount_total': total, 'amount_paid': 0.0,
            'amount_tax': 0.0, 'amount_return': 0.0})
        self.env.flush_all()
        return o

    def _even(self, order, ways):
        r = self.url_open('/mezze/api/v1/split/even',
                          data=json.dumps({'uuid': order.uuid, 'ways': ways,
                                           'token': 'se-tok'}),
                          headers={'Content-Type': 'application/json'})
        return r.json()

    def _pay(self, order, amount):
        r = self.url_open('/mezze/api/v1/orders/pay',
                          data=json.dumps({'uuid': order.uuid, 'amount': amount,
                                           'payment_method_id': self.cash.id,
                                           'token': 'se-tok'}),
                          headers={'Content-Type': 'application/json'})
        return r.json()

    # -- the shares ------------------------------------------------------
    def test_01_a_bill_divides_into_equal_shares(self):
        d = self._even(self._order(100.0), 4)
        self.assertTrue(d.get('ok'), d)
        self.assertEqual(d['parts'], [25.0, 25.0, 25.0, 25.0])

    def test_02_an_awkward_division_still_sums_back(self):
        # THE property. Thirds of 100 must not quietly collect 99.99.
        d = self._even(self._order(100.0), 3)
        self.assertTrue(d.get('ok'), d)
        self.assertAlmostEqual(sum(d['parts']), 100.0, places=2)
        self.assertEqual(sorted(d['parts']), [33.33, 33.33, 33.34])
        self.assertTrue(d['reconciles'], 'the endpoint does not keep its own promise')

    def test_03_the_division_is_deterministic(self):
        order = self._order(100.0)
        self.assertEqual(self._even(order, 7)['parts'], self._even(order, 7)['parts'])

    def test_04_it_divides_what_is_LEFT_not_the_original(self):
        # A table that already put a deposit down is not four equal shares of the
        # whole bill any more; quoting them as if it were over-collects.
        order = self._order(100.0)
        self._pay(order, 20.0)
        order.invalidate_recordset()
        d = self._even(order, 4)
        self.assertTrue(d.get('ok'), d)
        self.assertAlmostEqual(d['remaining'], 80.0, places=2)
        self.assertEqual(d['parts'], [20.0, 20.0, 20.0, 20.0])

    # -- the limits ------------------------------------------------------
    def test_05_one_way_is_not_a_split(self):
        d = self._even(self._order(100.0), 1)
        self.assertEqual(d.get('error'), 'invalid_ways')

    def test_06_an_absurd_number_of_ways_is_refused(self):
        d = self._even(self._order(100.0), 500)
        self.assertEqual(d.get('error'), 'too_many_ways')

    def test_07_a_settled_order_has_nothing_to_divide(self):
        order = self._order(100.0)
        self._pay(order, 100.0)
        order.invalidate_recordset()
        self.assertEqual(self._even(order, 2).get('error'), 'nothing_due')

    def test_08_an_unknown_order_is_refused(self):
        r = self.url_open('/mezze/api/v1/split/even',
                          data=json.dumps({'uuid': 'nope', 'ways': 2,
                                           'token': 'se-tok'}),
                          headers={'Content-Type': 'application/json'})
        self.assertEqual(r.json().get('error'), 'unknown_order')

    # -- it does not restructure the order --------------------------------
    def test_09_no_child_checks_are_created(self):
        # Four people paying a quarter each still ate one meal.
        order = self._order(100.0)
        before = self.env['pos.order'].search_count([('session_id', '=', self.pos_sess.id)])
        self._even(order, 4)
        after = self.env['pos.order'].search_count([('session_id', '=', self.pos_sess.id)])
        self.assertEqual(after, before, 'splitting evenly created orders')
        order.invalidate_recordset()
        self.assertFalse(order.mezze_split_child_ids)

    def test_10_the_shares_settle_the_bill_when_all_are_paid(self):
        order = self._order(100.0)
        parts = self._even(order, 3)['parts']
        for amount in parts:
            d = self._pay(order, amount)
            self.assertTrue(d.get('ok'), d)
        order.invalidate_recordset()
        self.assertEqual(order.state, 'paid')
        self.assertAlmostEqual(order.amount_paid, 100.0, places=2)
        self.assertAlmostEqual(order.amount_return, 0.0, places=2,
                               msg='splitting evenly produced change')
