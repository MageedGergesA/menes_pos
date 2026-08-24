# -*- coding: utf-8 -*-
"""A guest may hand over more than the bill, and get change.

Mezze refused every tender larger than the balance::

    if tender - remaining > eps:
        return {'error': 'overpay', ...}

and the till capped the amount before it ever left the browser::

    return roundTo(Math.min(e, Number(remaining || 0)), decimals);

Between them, over-payment was impossible, so ``amount_return`` was always zero.
The "Change" line on the payment screen and on the printed receipt was a preview of
something no record was ever made of: a guest handing 100 for a 73 bill was rung up
as having handed 73, and the drawer's expected cash was understated by the change
the cashier actually gave out of it.

The model here is core's, not a new one: the full amount tendered is recorded as one
positive payment, and the change goes back as a SEPARATE negative payment on the
cash method flagged ``is_change``. That is what makes Odoo's own computes land —
``amount_paid`` settles to the order total and ``amount_return`` to the change —
without Mezze writing either field. Anything that reads the payment lines (the
session's cash figures, the closing entry, the reports) therefore adds up on its own.

Cash only. A card cannot hand coins back, so a non-cash over-payment is still
refused — but now with a reason that says so.
"""
import json

from odoo.tests import tagged

from .common import MezzeHttpCase


@tagged('post_install', '-at_install', 'mezze_change')
class TestChangeAndOvertender(MezzeHttpCase):
    fixture_profile = 'POS'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.pos_sess = cls._open_session_for(cls.pos_config)
        cls.cash = cls.pos_config.payment_method_ids.filtered('is_cash_count')[:1]
        cls.card = cls.pos_config.payment_method_ids.filtered(
            lambda m: not m.is_cash_count)[:1]
        cls.product = env['product.product'].sudo().create({
            'name': 'CH Plate', 'available_in_pos': True, 'list_price': 73.0,
            'type': 'consu'})
        cls.product.write({'taxes_id': [(5, 0, 0)]})
        env['ir.config_parameter'].sudo().set_param('mezze_bridge.api_token', 'ch-tok')
        env.flush_all()

    def _order(self, total=73.0):
        o = self.env['pos.order'].sudo().create({
            'session_id': self.pos_sess.id,
            'company_id': self.pos_config.company_id.id,
            'lines': [(0, 0, {
                'product_id': self.product.id, 'qty': 1, 'price_unit': total,
                'price_subtotal': total, 'price_subtotal_incl': total,
                'tax_ids': [(6, 0, [])]})],
            'amount_total': total, 'amount_paid': 0.0,
            'amount_tax': 0.0, 'amount_return': 0.0,
        })
        self.env.flush_all()
        return o

    def _pay(self, order, amount, method):
        r = self.url_open(
            '/mezze/api/v1/orders/pay',
            data=json.dumps({'uuid': order.uuid, 'amount': amount,
                             'payment_method_id': method.id, 'token': 'ch-tok'}),
            headers={'Content-Type': 'application/json'})
        return r.json()

    # ---- the defect ----------------------------------------------------
    def test_01_cash_overtender_is_accepted(self):
        if not self.cash:
            self.skipTest('no cash method on this config')
        order = self._order(73.0)
        d = self._pay(order, 100.0, self.cash)
        self.assertTrue(d.get('ok'), 'a cash overtender must be accepted: %s' % d)

    def test_02_change_is_reported_to_the_till(self):
        if not self.cash:
            self.skipTest('no cash method on this config')
        order = self._order(73.0)
        d = self._pay(order, 100.0, self.cash)
        self.assertAlmostEqual(d.get('change') or 0.0, 27.0, places=2,
                               msg='the till is not told what to hand back: %s' % d)

    def test_03_change_is_stored_on_the_order(self):
        if not self.cash:
            self.skipTest('no cash method on this config')
        order = self._order(73.0)
        self._pay(order, 100.0, self.cash)
        order.invalidate_recordset()
        self.assertAlmostEqual(order.amount_return, 27.0, places=2,
                               msg='amount_return is still structurally zero')

    def test_04_the_order_settles_to_its_own_total(self):
        # The positive tender and the negative change must net to the bill, or the
        # session's cash and the closing entry are wrong.
        if not self.cash:
            self.skipTest('no cash method on this config')
        order = self._order(73.0)
        self._pay(order, 100.0, self.cash)
        order.invalidate_recordset()
        self.assertAlmostEqual(order.amount_paid, 73.0, places=2)
        self.assertEqual(order.state, 'paid')

    def test_05_change_is_a_real_payment_line_flagged_as_change(self):
        # Core's shape, so everything that reads payment lines keeps working.
        if not self.cash:
            self.skipTest('no cash method on this config')
        order = self._order(73.0)
        self._pay(order, 100.0, self.cash)
        order.invalidate_recordset()
        amounts = sorted(order.payment_ids.mapped('amount'))
        self.assertEqual([round(a, 2) for a in amounts], [-27.0, 100.0],
                         'expected a 100 tender and a -27 change line')
        change_line = order.payment_ids.filtered('is_change')
        self.assertEqual(len(change_line), 1, 'the change line must be flagged is_change')
        self.assertTrue(change_line.payment_method_id.is_cash_count,
                        'change must go back on a cash method')

    # ---- the limit -----------------------------------------------------
    def test_06_a_card_cannot_be_overpaid(self):
        if not self.card:
            self.skipTest('no non-cash method on this config')
        order = self._order(73.0)
        d = self._pay(order, 100.0, self.card)
        self.assertFalse(d.get('ok'), 'a card must not accept an overpayment')
        self.assertEqual(d.get('error'), 'overpay_not_cash')

    def test_07_exact_and_partial_tenders_are_unchanged(self):
        if not self.cash:
            self.skipTest('no cash method on this config')
        exact = self._order(73.0)
        d = self._pay(exact, 73.0, self.cash)
        self.assertTrue(d.get('ok'), d)
        self.assertAlmostEqual(d.get('change') or 0.0, 0.0, places=2)
        exact.invalidate_recordset()
        self.assertAlmostEqual(exact.amount_return, 0.0, places=2)
        self.assertEqual(exact.state, 'paid')

        part = self._order(73.0)
        d2 = self._pay(part, 40.0, self.cash)
        self.assertTrue(d2.get('ok'), d2)
        self.assertTrue(d2.get('partial'))
        self.assertAlmostEqual(d2.get('remaining'), 33.0, places=2)

    def test_08_the_receipt_prints_the_change(self):
        # hardware_render already had `if order.amount_return: tk.lr('Change', ...)`.
        # It never fired, because amount_return could not be anything but zero.
        if not self.cash:
            self.skipTest('no cash method on this config')
        order = self._order(73.0)
        self._pay(order, 100.0, self.cash)
        order.invalidate_recordset()
        from ..models.hardware_render import receipt_ticket
        text = receipt_ticket(order).to_text()
        self.assertIn('Change', text, 'the receipt does not show the change')
        self.assertIn('27', text, 'the receipt does not show the change AMOUNT:\n%s' % text)
