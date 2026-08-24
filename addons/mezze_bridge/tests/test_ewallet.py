# -*- coding: utf-8 -*-
"""The customer's own prepaid balance.

An eWallet is the same instrument as a gift card with the code taken away: prepaid,
spent at payment, capped at what is on it. The differences are the ones a cashier
feels — it is found by WHO the guest is rather than by what they are holding, so it
needs a customer on the order and there is nothing to type, and it is topped up by
selling a product rather than issued as an object.

Two properties carry most of the weight here:

* a wallet must never be anonymous. A balance with no owner is money nobody can
  claim and anybody can spend, so both the tender and the top-up refuse without a
  customer rather than quietly using the first wallet they find; and
* topping up must be idempotent. Both settlement paths can reach the same order, and
  crediting twice invents money — exactly the failure the gift-card mint had to be
  protected from.
"""
import json

from odoo.tests import tagged

from .common import MezzeHttpCase


@tagged('post_install', '-at_install', 'mezze_ewallet')
class TestEWallet(MezzeHttpCase):
    fixture_profile = 'POS'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        env['ir.config_parameter'].sudo().set_param('mezze_bridge.api_token', 'ew-tok')
        from ..models.loyalty_bootstrap import ensure_giftcard_payment_method
        ensure_giftcard_payment_method(env)
        cls.pos_sess = cls._open_session_for(cls.pos_config)
        cls.cash = cls.pos_config.payment_method_ids.filtered('is_cash_count')[:1]
        cls.partner = env['res.partner'].sudo().create({'name': 'EW Regular'})
        cls.stranger = env['res.partner'].sudo().create({'name': 'EW Stranger'})
        cls.product = env['product.product'].sudo().create({
            'name': 'EW Plate', 'available_in_pos': True, 'list_price': 100.0,
            'type': 'consu'})
        cls.product.write({'taxes_id': [(5, 0, 0)]})
        env.flush_all()

    # -- helpers ---------------------------------------------------------
    @property
    def _ctl(self):
        from ..controllers.main import MezzeBridgeController
        return MezzeBridgeController()

    def _wallet(self, partner, amount=0.0):
        card = self._ctl._ewallet_card(self.env, partner, create=True)
        card.sudo().write({'points': amount})
        self.env.flush_all()
        return card

    def _order(self, total=100.0, partner=None, product=None):
        prod = product or self.product
        vals = {
            'session_id': self.pos_sess.id,
            'company_id': self.pos_config.company_id.id,
            'lines': [(0, 0, {'product_id': prod.id, 'qty': 1, 'price_unit': total,
                              'price_subtotal': total, 'price_subtotal_incl': total,
                              'tax_ids': [(6, 0, [])]})],
            'amount_total': total, 'amount_paid': 0.0,
            'amount_tax': 0.0, 'amount_return': 0.0}
        if partner:
            vals['partner_id'] = partner.id
        o = self.env['pos.order'].sudo().create(vals)
        self.env.flush_all()
        return o

    def _post(self, path, body):
        r = self.url_open('/mezze/api/v1' + path,
                          data=json.dumps(dict(body, token='ew-tok')),
                          headers={'Content-Type': 'application/json'})
        return r.json()

    # -- paying from it --------------------------------------------------
    def test_01_a_wallet_settles_part_of_a_bill(self):
        self._wallet(self.partner, 40.0)
        order = self._order(100.0, self.partner)
        d = self._post('/orders/pay', {'uuid': order.uuid, 'use_ewallet': True})
        self.assertTrue(d.get('ok'), d)
        self.assertTrue(d.get('partial'), 'a 40 wallet cannot settle a 100 bill: %s' % d)
        self.assertAlmostEqual(d.get('remaining'), 60.0, places=2)

    def test_02_it_is_never_charged_beyond_the_bill(self):
        card = self._wallet(self.partner, 500.0)
        order = self._order(100.0, self.partner)
        d = self._post('/orders/pay', {'uuid': order.uuid, 'use_ewallet': True})
        self.assertTrue(d.get('ok'), d)
        card.invalidate_recordset()
        self.assertAlmostEqual(card.points, 400.0, places=2,
                               msg='the wallet was charged more than the bill')
        order.invalidate_recordset()
        self.assertEqual(order.state, 'paid')
        self.assertAlmostEqual(order.amount_return, 0.0, places=2,
                               msg='a wallet must never produce change')

    def test_03_the_remaining_balance_is_reported(self):
        self._wallet(self.partner, 500.0)
        order = self._order(100.0, self.partner)
        d = self._post('/orders/pay', {'uuid': order.uuid, 'use_ewallet': True})
        self.assertAlmostEqual(d.get('ewallet_balance'), 400.0, places=2,
                               msg='the guest cannot be told what is left: %s' % d)

    def test_04_it_is_recorded_on_its_own_payment_method(self):
        self._wallet(self.partner, 40.0)
        order = self._order(100.0, self.partner)
        self._post('/orders/pay', {'uuid': order.uuid, 'use_ewallet': True})
        order.invalidate_recordset()
        self.assertEqual(order.payment_ids.payment_method_id.name, 'eWallet')

    def test_05_the_wallet_method_is_not_a_customer_account(self):
        # A wallet is money already handed over. Typed pay_later it would be put
        # through the credit gate, which asks whether the customer may owe more.
        pm = self.pos_config.payment_method_ids.filtered(lambda m: m.name == 'eWallet')
        self.assertTrue(pm, 'the branch cannot accept a wallet at all')
        self.assertNotEqual(pm.mezze_mode, 'customer_account')

    # -- never anonymous -------------------------------------------------
    def test_06_an_order_with_no_customer_cannot_pay_from_a_wallet(self):
        self._wallet(self.partner, 100.0)
        order = self._order(100.0)          # no partner
        d = self._post('/orders/pay', {'uuid': order.uuid, 'use_ewallet': True})
        self.assertFalse(d.get('ok'))
        self.assertEqual(d.get('error'), 'customer_required')

    def test_07_a_customer_without_a_wallet_is_told_so(self):
        order = self._order(100.0, self.stranger)
        d = self._post('/orders/pay', {'uuid': order.uuid, 'use_ewallet': True})
        self.assertEqual(d.get('error'), 'ewallet_missing')

    def test_08_an_empty_wallet_is_refused_with_a_reason(self):
        self._wallet(self.partner, 0.0)
        order = self._order(100.0, self.partner)
        d = self._post('/orders/pay', {'uuid': order.uuid, 'use_ewallet': True})
        self.assertEqual(d.get('error'), 'ewallet_empty')

    def test_09_one_customer_cannot_spend_another_customers_wallet(self):
        self._wallet(self.partner, 100.0)
        order = self._order(100.0, self.stranger)
        d = self._post('/orders/pay', {'uuid': order.uuid, 'use_ewallet': True})
        self.assertFalse(d.get('ok'), 'a stranger spent someone else\'s wallet: %s' % d)

    # -- topping up ------------------------------------------------------
    def test_10_selling_the_topup_product_credits_the_wallet(self):
        topup = self._ctl._ewallet_topup_product(self.env)
        order = self._order(50.0, self.partner, product=topup)
        d = self._post('/orders/pay', {'uuid': order.uuid, 'amount': 50.0,
                                       'payment_method_id': self.cash.id})
        self.assertTrue(d.get('ok'), d)
        card = self._ctl._ewallet_card(self.env, self.partner)
        card.invalidate_recordset()
        self.assertAlmostEqual(card.points, 50.0, places=2,
                               msg='the guest paid for a top-up and got nothing')
        self.assertAlmostEqual((d.get('ewallet_topup') or {}).get('balance'), 50.0,
                               places=2)

    def test_11_a_top_up_is_credited_once(self):
        topup = self._ctl._ewallet_topup_product(self.env)
        order = self._order(50.0, self.partner, product=topup)
        self._post('/orders/pay', {'uuid': order.uuid, 'amount': 50.0,
                                   'payment_method_id': self.cash.id})
        again = self._ctl._ewallet_topup(self.env, order, {})
        self.assertIsNone(again, 'a second top-up credited the wallet twice')
        card = self._ctl._ewallet_card(self.env, self.partner)
        card.invalidate_recordset()
        self.assertAlmostEqual(card.points, 50.0, places=2)

    def test_12_an_anonymous_top_up_credits_nothing(self):
        # Better to credit nobody than to credit the wrong wallet.
        topup = self._ctl._ewallet_topup_product(self.env)
        order = self._order(50.0, product=topup)      # no partner
        d = self._post('/orders/pay', {'uuid': order.uuid, 'amount': 50.0,
                                       'payment_method_id': self.cash.id})
        self.assertTrue(d.get('ok'), d)
        self.assertIsNone(d.get('ewallet_topup'))

    def test_13_an_ordinary_sale_credits_nothing(self):
        order = self._order(100.0, self.partner)
        d = self._post('/orders/pay', {'uuid': order.uuid, 'amount': 100.0,
                                       'payment_method_id': self.cash.id})
        self.assertTrue(d.get('ok'), d)
        self.assertIsNone(d.get('ewallet_topup'))

    def test_14_the_topup_product_carries_no_tax(self):
        # Money moving onto a wallet is a liability, not revenue. The tax is charged
        # when the wallet BUYS something; charging at both ends taxes the guest twice.
        topup = self._ctl._ewallet_topup_product(self.env)
        self.assertFalse(topup.taxes_id, 'a top-up must not be taxed')
        # The gift-card product carries the same intent and the same trap: the empty
        # taxes_id passed on create is overwritten by the company default.
        gift = self._ctl._giftcard_sale_product(self.env)
        self.assertFalse(gift.taxes_id, 'a gift-card sale must not be taxed either')

    # -- reading it ------------------------------------------------------
    def test_15_the_balance_endpoint_answers(self):
        self._wallet(self.partner, 75.0)
        d = self._post('/ewallet/balance', {'partner_id': self.partner.id})
        self.assertTrue(d.get('ok'), d)
        self.assertAlmostEqual(d.get('balance'), 75.0, places=2)
        self.assertTrue(d.get('has_wallet'))

    def test_16_a_customer_with_no_wallet_reads_as_zero_not_an_error(self):
        d = self._post('/ewallet/balance', {'partner_id': self.stranger.id})
        self.assertTrue(d.get('ok'), d)
        self.assertAlmostEqual(d.get('balance'), 0.0, places=2)
        self.assertFalse(d.get('has_wallet'))

    def test_17_a_balance_needs_a_customer(self):
        d = self._post('/ewallet/balance', {})
        self.assertEqual(d.get('error'), 'customer_required')
