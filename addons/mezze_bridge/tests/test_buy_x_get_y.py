# -*- coding: utf-8 -*-
"""Buy two, get one.

``buy_x_get_y`` was already in ``PROMO_TYPES``, so such a programme was evaluated
against every cart — and then silently thrown away, because ``_promo_eval`` only ever
accepted a ``discount`` reward and returned ``None`` for a product one.

That is worse than not supporting it. The branch publishes a promotion, it matches
the cart, nothing happens, and nothing is said. Nobody finds out until a guest asks
where their free coffee is.

The giveaway is expressed as the reward PRODUCT at 100% off rather than as a negative
discount line, and that choice is what most of these tests pin:

* the guest sees the free item NAMED on the receipt — "Buy 2 get 1: -60.00" tells
  them a number, not what they were given;
* the kitchen sees an item to make, not an accounting adjustment; and
* the order total still moves by exactly the value given away.
"""
import json

from odoo.tests import tagged

from .common import MezzeHttpCase


@tagged('post_install', '-at_install', 'mezze_bogo')
class TestBuyXGetY(MezzeHttpCase):
    fixture_profile = 'POS'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        env['ir.config_parameter'].sudo().set_param('mezze_bridge.api_token', 'bg-tok')
        cls.pos_sess = cls._open_session_for(cls.pos_config)
        cls.coffee = env['product.product'].sudo().create({
            'name': 'BG Coffee', 'available_in_pos': True, 'list_price': 30.0,
            'type': 'consu'})
        cls.coffee.write({'taxes_id': [(5, 0, 0)]})
        # "Buy 2 coffees, get 1 free" — a PRODUCT reward, not a discount.
        cls.program = env['loyalty.program'].sudo().create({
            'name': 'BG Buy 2 Get 1',
            'program_type': 'buy_x_get_y',
            'trigger': 'auto',
            'applies_on': 'current',
            'rule_ids': [(0, 0, {'minimum_qty': 2,
                                 'product_ids': [(6, 0, cls.coffee.ids)]})],
            'reward_ids': [(0, 0, {
                'reward_type': 'product',
                'reward_product_id': cls.coffee.id,
                'reward_product_qty': 1})],
        })
        env.flush_all()

    def _order(self, qty=2):
        total = 30.0 * qty
        o = self.env['pos.order'].sudo().create({
            'session_id': self.pos_sess.id,
            'company_id': self.pos_config.company_id.id,
            'lines': [(0, 0, {'product_id': self.coffee.id, 'qty': qty,
                              'price_unit': 30.0, 'price_subtotal': total,
                              'price_subtotal_incl': total, 'tax_ids': [(6, 0, [])]})],
            'amount_total': total, 'amount_paid': 0.0,
            'amount_tax': 0.0, 'amount_return': 0.0})
        self.env.flush_all()
        return o

    def _auto(self, order):
        r = self.url_open('/mezze/api/v1/promo/auto',
                          data=json.dumps({'order_uuid': order.uuid, 'token': 'bg-tok'}),
                          headers={'Content-Type': 'application/json'})
        return r.json()

    def _reward_lines(self, order):
        order.invalidate_recordset()
        return order.lines.filtered('is_reward_line')

    # -- it applies at all -------------------------------------------------
    def test_01_a_qualifying_cart_gets_the_free_item(self):
        order = self._order(qty=2)
        d = self._auto(order)
        self.assertTrue(d.get('ok'), d)
        self.assertTrue(d.get('promotions'),
                        'an active buy-2-get-1 matched and produced nothing: %s' % d)

    def test_02_the_free_item_appears_as_the_product_itself(self):
        # Not a negative line. The guest should read what they were given.
        order = self._order(qty=2)
        self._auto(order)
        rewards = self._reward_lines(order)
        self.assertEqual(len(rewards), 1)
        self.assertEqual(rewards.product_id, self.coffee,
                         'the giveaway is not the product that was given')
        self.assertAlmostEqual(rewards.discount, 100.0, places=2)

    def test_03_it_costs_the_guest_nothing(self):
        order = self._order(qty=2)
        self._auto(order)
        order.invalidate_recordset()
        self.assertAlmostEqual(order.amount_total, 60.0, places=2,
                               msg='the free coffee was charged for')

    def test_04_the_line_still_shows_what_it_normally_costs(self):
        # 100% off rather than price_unit 0 — the difference between a gift and a
        # mystery on the receipt.
        order = self._order(qty=2)
        self._auto(order)
        self.assertAlmostEqual(self._reward_lines(order).price_unit, 30.0, places=2)

    # -- and only when it should ------------------------------------------
    def test_05_a_cart_below_the_threshold_gets_nothing(self):
        order = self._order(qty=1)
        d = self._auto(order)
        self.assertFalse(d.get('promotions'), 'a free item was given away too early')
        self.assertEqual(len(self._reward_lines(order)), 0)

    def test_06_reconciling_twice_does_not_give_two_away(self):
        order = self._order(qty=2)
        self._auto(order)
        self._auto(order)
        self._auto(order)
        self.assertEqual(len(self._reward_lines(order)), 1,
                         'the promotion gave away a free item on every reconcile')
        order.invalidate_recordset()
        self.assertAlmostEqual(order.amount_total, 60.0, places=2)

    def test_07_it_is_a_reward_line_so_nothing_else_touches_it(self):
        # Which is what keeps the KDS from treating it as ordinary demand and
        # /orders/discount from marking a giveaway down a second time.
        order = self._order(qty=2)
        self._auto(order)
        self.assertTrue(self._reward_lines(order).is_reward_line)
