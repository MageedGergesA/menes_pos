# -*- coding: utf-8 -*-
"""The branch's own promotions, on the till.

``/shop/order`` applied automatic promotions; the register applied none. A guest
ordering online got "spend 100, take 10% off"; the same guest at the counter did
not, and the cashier had no way to give it to them — the promotion existed, was
active, and simply never reached the till.

The property these tests are built around is that ``/promo/auto`` **reconciles**
rather than adds. It has to be safe to call after every change to a cart, and the
obvious implementation — evaluate and graft — stacks a fresh discount every time an
item is rung up, quietly giving the order away. So the same call is made repeatedly
and the discount is required not to move.

A TYPED coupon is deliberately out of scope of the reconcile: the guest presented it
to earn it, and re-deriving could drop a single-use code that has already been
consumed.
"""
import json

from odoo.tests import tagged

from .common import MezzeHttpCase


@tagged('post_install', '-at_install', 'mezze_promo')
class TestAutoPromotions(MezzeHttpCase):
    fixture_profile = 'POS'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        env['ir.config_parameter'].sudo().set_param('mezze_bridge.api_token', 'pr-tok')
        cls.pos_sess = cls._open_session_for(cls.pos_config)
        cls.product = env['product.product'].sudo().create({
            'name': 'PR Plate', 'available_in_pos': True, 'list_price': 100.0,
            'type': 'consu'})
        cls.product.write({'taxes_id': [(5, 0, 0)]})
        cls.discount_product = env['product.product'].sudo().create({
            'name': 'PR Discount', 'type': 'service', 'list_price': 0.0,
            'available_in_pos': True})
        cls.discount_product.write({'taxes_id': [(5, 0, 0)]})
        # "Spend 100 or more, take 10% off" — automatic, no code.
        cls.program = env['loyalty.program'].sudo().create({
            'name': 'PR Spend and Save',
            'program_type': 'promotion',
            'trigger': 'auto',
            'applies_on': 'current',
            'rule_ids': [(0, 0, {'minimum_amount': 100.0})],
            'reward_ids': [(0, 0, {
                'reward_type': 'discount', 'discount': 10.0,
                'discount_mode': 'percent', 'discount_applicability': 'order',
                'discount_line_product_id': cls.discount_product.id})],
        })
        env.flush_all()

    # -- helpers ---------------------------------------------------------
    def _order(self, qty=1):
        total = 100.0 * qty
        o = self.env['pos.order'].sudo().create({
            'session_id': self.pos_sess.id,
            'company_id': self.pos_config.company_id.id,
            'lines': [(0, 0, {'product_id': self.product.id, 'qty': qty,
                              'price_unit': 100.0, 'price_subtotal': total,
                              'price_subtotal_incl': total, 'tax_ids': [(6, 0, [])]})],
            'amount_total': total, 'amount_paid': 0.0,
            'amount_tax': 0.0, 'amount_return': 0.0})
        self.env.flush_all()
        return o

    def _auto(self, order):
        r = self.url_open('/mezze/api/v1/promo/auto',
                          data=json.dumps({'order_uuid': order.uuid, 'token': 'pr-tok'}),
                          headers={'Content-Type': 'application/json'})
        return r.json()

    def _reward_lines(self, order):
        order.invalidate_recordset()
        return order.lines.filtered('is_reward_line')

    # -- it happens at all -----------------------------------------------
    def test_01_an_eligible_cart_gets_the_branch_promotion(self):
        order = self._order()
        d = self._auto(order)
        self.assertTrue(d.get('ok'), d)
        self.assertTrue(d.get('promotions'),
                        'the branch published a promotion the till never applied: %s' % d)
        self.assertAlmostEqual(d['discount'], 10.0, places=2)

    def test_02_the_order_total_actually_moves(self):
        order = self._order()
        self._auto(order)
        order.invalidate_recordset()
        self.assertAlmostEqual(order.amount_total, 90.0, places=2)

    def test_03_an_ineligible_cart_gets_nothing(self):
        # The rule is "spend 100 or more". A 100 order qualifies; halve it.
        order = self._order()
        order.lines[0].sudo().write({
            'qty': 1, 'price_unit': 40.0, 'price_subtotal': 40.0,
            'price_subtotal_incl': 40.0})
        order.sudo().write({'amount_total': 40.0})
        self.env.flush_all()
        d = self._auto(order)
        self.assertTrue(d.get('ok'), d)
        self.assertFalse(d.get('promotions'), 'a promotion was invented: %s' % d)
        self.assertAlmostEqual(d['discount'], 0.0, places=2)

    # -- THE property ----------------------------------------------------
    def test_04_calling_it_again_does_not_discount_again(self):
        order = self._order()
        first = self._auto(order)
        second = self._auto(order)
        third = self._auto(order)
        self.assertAlmostEqual(first['discount'], 10.0, places=2)
        self.assertAlmostEqual(second['discount'], 10.0, places=2,
                               msg='a second reconcile changed the discount')
        self.assertAlmostEqual(third['discount'], 10.0, places=2)
        order.invalidate_recordset()
        self.assertAlmostEqual(order.amount_total, 90.0, places=2,
                               msg='the order was discounted more than once')
        self.assertEqual(len(self._reward_lines(order)), 1,
                         'the promotion was grafted more than once')

    def test_05_it_follows_the_cart_down(self):
        # Ring up more, then remove it: the promotion has to go with it.
        order = self._order(qty=2)
        self._auto(order)
        order.invalidate_recordset()
        self.assertAlmostEqual(order.amount_total, 180.0, places=2)
        order.lines.filtered(lambda l: not l.is_reward_line)[0].sudo().write({
            'qty': 1, 'price_subtotal': 40.0, 'price_subtotal_incl': 40.0,
            'price_unit': 40.0})
        self.env.flush_all()
        d = self._auto(order)
        self.assertFalse(d.get('promotions'),
                         'the promotion survived the cart becoming ineligible')
        order.invalidate_recordset()
        self.assertAlmostEqual(order.amount_total, 40.0, places=2)

    def test_06_the_promotion_line_is_a_reward_line(self):
        # Which is what stops the KDS cooking it, stops /orders/discount marking it
        # down a second time, and stops a re-read counting it as an item.
        order = self._order()
        self._auto(order)
        rewards = self._reward_lines(order)
        self.assertEqual(len(rewards), 1)
        self.assertLess(rewards.price_unit, 0, 'a discount line must be negative')

    def test_07_a_cart_emptied_of_items_keeps_no_discount(self):
        order = self._order()
        self._auto(order)
        order.lines.filtered(lambda l: not l.is_reward_line).sudo().unlink()
        self.env.flush_all()
        d = self._auto(order)
        self.assertTrue(d.get('ok'), d)
        self.assertEqual(len(self._reward_lines(order)), 0,
                         'a discount outlived the items that earned it')
        order.invalidate_recordset()
        self.assertAlmostEqual(order.amount_total, 0.0, places=2)

    def test_08_an_unknown_order_is_refused(self):
        r = self.url_open('/mezze/api/v1/promo/auto',
                          data=json.dumps({'order_uuid': 'no-such-order',
                                           'token': 'pr-tok'}),
                          headers={'Content-Type': 'application/json'})
        self.assertEqual(r.json().get('error'), 'order_not_found')
