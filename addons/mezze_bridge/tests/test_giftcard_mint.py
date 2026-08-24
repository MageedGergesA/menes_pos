# -*- coding: utf-8 -*-
"""Selling a gift card has to actually mint one.

The minting lived inline in the atomic-paid branch of ``/orders/sync`` — the single
call that creates an order and settles it at once. The Owl register does not take
that path: it syncs a DRAFT and then settles through ``/orders/pay``. So on the till
that ships, selling a gift card collected the money and issued nothing. The customer
paid for a card that was never created, and nothing anywhere recorded that they had.

Two properties are asserted, and the second matters as much as the first:

* selling the gift-card product on the REGISTER's path mints a card, and
* it mints exactly one. Both settlement paths may legitimately reach the same order,
  and a gift card minted twice is money invented twice.

The code also has to leave the building. A card whose number never reaches paper is
a card the customer cannot present, so the receipt is asserted too — and it reads the
codes from the cards themselves rather than from a response payload, so a reprint
carries the same numbers as the original.
"""
import json

from odoo.tests import tagged

from .common import MezzeHttpCase


@tagged('post_install', '-at_install', 'mezze_giftcard')
class TestGiftCardMint(MezzeHttpCase):
    fixture_profile = 'POS'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        env['ir.config_parameter'].sudo().set_param('mezze_bridge.api_token', 'gc-tok')
        cls.pos_sess = cls._open_session_for(cls.pos_config)
        cls.cash = cls.pos_config.payment_method_ids.filtered('is_cash_count')[:1]
        env.flush_all()

    # -- helpers ---------------------------------------------------------
    @property
    def _gc_product(self):
        from ..controllers.main import MezzeBridgeController as MezzeBridge
        return MezzeBridge()._giftcard_sale_product(self.env)

    def _draft_selling_a_card(self, amount=200.0):
        """An order for the gift-card product, left DRAFT — the register's shape."""
        prod = self._gc_product
        order = self.env['pos.order'].sudo().create({
            'session_id': self.pos_sess.id,
            'company_id': self.pos_config.company_id.id,
            'lines': [(0, 0, {
                'product_id': prod.id, 'qty': 1, 'price_unit': amount,
                'price_subtotal': amount, 'price_subtotal_incl': amount,
                'tax_ids': [(6, 0, [])]})],
            'amount_total': amount, 'amount_paid': 0.0,
            'amount_tax': 0.0, 'amount_return': 0.0,
        })
        self.env.flush_all()
        return order

    def _pay(self, order, amount):
        r = self.url_open(
            '/mezze/api/v1/orders/pay',
            data=json.dumps({'uuid': order.uuid, 'amount': amount,
                             'payment_method_id': self.cash.id, 'token': 'gc-tok'}),
            headers={'Content-Type': 'application/json'})
        return r.json()

    def _cards_for(self, order):
        rows = self.env['mezze.audit.log'].sudo().search([
            ('event', '=', 'giftcard.issue'), ('res_model', '=', 'pos.order'),
            ('res_id', '=', order.id)])
        codes = [json.loads(r.detail or '{}').get('code') for r in rows]
        codes = [c for c in codes if c]
        return self.env['loyalty.card'].sudo().search([('code', 'in', codes)]) \
            if codes else self.env['loyalty.card']

    # -- the defect ------------------------------------------------------
    def test_01_paying_on_the_till_mints_the_card(self):
        order = self._draft_selling_a_card(200.0)
        d = self._pay(order, 200.0)
        self.assertTrue(d.get('ok'), d)
        cards = self._cards_for(order)
        self.assertEqual(len(cards), 1,
                         'selling a gift card on the register minted nothing')
        self.assertAlmostEqual(cards.points, 200.0, places=2)

    def test_02_the_code_is_returned_to_the_till(self):
        order = self._draft_selling_a_card(150.0)
        d = self._pay(order, 150.0)
        issued = d.get('gift_cards') or []
        self.assertEqual(len(issued), 1,
                         'the till is never told the code it just sold: %s' % d)
        self.assertTrue(issued[0].get('code'))
        self.assertAlmostEqual(issued[0].get('amount'), 150.0, places=2)

    def test_03_the_card_is_worth_what_was_paid(self):
        order = self._draft_selling_a_card(75.5)
        self._pay(order, 75.5)
        self.assertAlmostEqual(self._cards_for(order).points, 75.5, places=2)

    # -- and only one ----------------------------------------------------
    def test_04_a_second_settlement_does_not_mint_a_second_card(self):
        # Both settlement paths may reach the same order. Minting twice would invent
        # money, so the mint is idempotent on the order's own audit trail.
        order = self._draft_selling_a_card(200.0)
        self._pay(order, 200.0)
        from ..controllers.main import MezzeBridgeController as MezzeBridge
        again = MezzeBridge()._mint_giftcards(self.env, order, {}, via='sale')
        self.assertEqual(again, [], 'a second mint issued another card')
        self.assertEqual(len(self._cards_for(order)), 1,
                         'the order minted more than one card')

    def test_05_an_ordinary_order_mints_nothing(self):
        prod = self.env['product.product'].sudo().create({
            'name': 'GC Not A Card', 'available_in_pos': True, 'list_price': 30.0,
            'type': 'consu'})
        prod.write({'taxes_id': [(5, 0, 0)]})
        order = self.env['pos.order'].sudo().create({
            'session_id': self.pos_sess.id,
            'company_id': self.pos_config.company_id.id,
            'lines': [(0, 0, {'product_id': prod.id, 'qty': 1, 'price_unit': 30.0,
                              'price_subtotal': 30.0, 'price_subtotal_incl': 30.0,
                              'tax_ids': [(6, 0, [])]})],
            'amount_total': 30.0, 'amount_paid': 0.0,
            'amount_tax': 0.0, 'amount_return': 0.0})
        self.env.flush_all()
        d = self._pay(order, 30.0)
        self.assertTrue(d.get('ok'), d)
        self.assertFalse(d.get('gift_cards'),
                         'a normal sale must not mint a gift card')
        self.assertEqual(len(self._cards_for(order)), 0)

    # -- the customer can use it -----------------------------------------
    def test_06_the_receipt_carries_the_code(self):
        order = self._draft_selling_a_card(200.0)
        self._pay(order, 200.0)
        order.invalidate_recordset()
        from ..models.hardware_render import receipt_ticket
        text = receipt_ticket(order).to_text()
        code = self._cards_for(order).code
        self.assertIn('GIFT CARD', text, 'the receipt does not mention the card')
        self.assertIn(code, text,
                      'the code the customer must present is not on the receipt:\n%s' % text)

    def test_07_a_reprint_carries_the_same_code(self):
        # The codes are read from the cards, not from the pay response, so the second
        # copy is the same document.
        order = self._draft_selling_a_card(200.0)
        self._pay(order, 200.0)
        order.invalidate_recordset()
        from ..models.hardware_render import receipt_ticket
        first = receipt_ticket(order).to_text()
        second = receipt_ticket(order).to_text()
        self.assertEqual(first, second, 'a reprint is not the same receipt')
        self.assertIn(self._cards_for(order).code, second)

    def test_08_a_gift_receipt_omits_the_code(self):
        # A gift receipt hides prices; printing the card number on it would hand the
        # balance to whoever the gift is for AND to whoever sees the slip.
        order = self._draft_selling_a_card(200.0)
        self._pay(order, 200.0)
        order.invalidate_recordset()
        from ..models.hardware_render import receipt_ticket
        text = receipt_ticket(order, gift=True).to_text()
        self.assertNotIn(self._cards_for(order).code, text)
