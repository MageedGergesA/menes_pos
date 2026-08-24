# -*- coding: utf-8 -*-
"""The bill before payment, and a second copy of a receipt after it.

Mezze could print a receipt for a SETTLED order and nothing at all for an open one.
On a restaurant floor that means there is no way to hand a guest their bill — the
one slip the whole service builds towards — and no way to replace a receipt somebody
lost on the way out.

The bill is deliberately not a receipt, and the tests hold it to that: no tax QR, and
it says so on its face. A pro-forma that looks like a receipt is one a guest can walk
out holding and one an inspector can find in a drawer.

Reprint needed no server work at all — ``/print/receipt`` has always taken a uuid.
Nothing on the till ever passed one, which is the same unreachable-backend shape as
Refund, the Z report and the whole loyalty surface.
"""
import json

from odoo.tests import tagged

from .common import MezzeHttpCase


@tagged('post_install', '-at_install', 'mezze_bill')
class TestBillAndReprint(MezzeHttpCase):
    fixture_profile = 'POS'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        env['ir.config_parameter'].sudo().set_param('mezze_bridge.api_token', 'bl-tok')
        cls.pos_sess = cls._open_session_for(cls.pos_config)
        cls.cash = cls.pos_config.payment_method_ids.filtered('is_cash_count')[:1]
        cls.tax = env['account.tax'].sudo().create({
            'name': 'BL Tax 10%', 'amount': 10.0, 'amount_type': 'percent',
            'type_tax_use': 'sale', 'price_include_override': 'tax_excluded',
            'company_id': cls.pos_config.company_id.id})
        cls.dish = env['product.product'].sudo().create({
            'name': 'BL Plate', 'available_in_pos': True, 'list_price': 100.0,
            'type': 'consu', 'taxes_id': [(6, 0, cls.tax.ids)]})
        env.flush_all()

    def _order(self, paid=False):
        o = self.env['pos.order'].sudo().create({
            'session_id': self.pos_sess.id,
            'company_id': self.pos_config.company_id.id,
            'lines': [(0, 0, {'product_id': self.dish.id, 'qty': 1,
                              'price_unit': 100.0, 'price_subtotal': 100.0,
                              'price_subtotal_incl': 110.0,
                              'tax_ids': [(6, 0, self.tax.ids)]})],
            'amount_total': 110.0, 'amount_paid': 110.0 if paid else 0.0,
            'amount_tax': 10.0, 'amount_return': 0.0})
        if paid:
            self.env['pos.payment'].sudo().create({
                'pos_order_id': o.id, 'amount': 110.0,
                'payment_method_id': self.cash.id})
            o.sudo().write({'state': 'paid'})
        self.env.flush_all()
        return o

    def _bill_text(self, order, **kw):
        from ..models.hardware_render import receipt_ticket
        return receipt_ticket(order, bill=True, **kw).to_text()

    # -- the bill --------------------------------------------------------
    def test_01_an_unpaid_order_can_be_billed(self):
        text = self._bill_text(self._order())
        self.assertIn('BILL', text, 'the slip does not name itself')
        self.assertIn('110.00', text, 'the bill does not show what is owed:\n%s' % text)

    def test_02_it_says_it_is_not_a_receipt(self):
        # The whole point. A pro-forma that reads as a receipt is one a guest can
        # walk out holding.
        self.assertIn('not a receipt', self._bill_text(self._order()))

    def test_03_it_carries_no_tax_qr(self):
        # The QR is what makes a document a tax invoice.
        text = self._bill_text(self._order(), tax_qr='SOME-SIGNED-TLV-PAYLOAD')
        self.assertNotIn('QR', text,
                         'a pro-forma must not carry the tax QR:\n%s' % text)

    def test_04_a_receipt_still_carries_it(self):
        # Guard against fixing the bill by breaking the receipt.
        from ..models.hardware_render import receipt_ticket
        text = receipt_ticket(self._order(paid=True), tax_qr='SOME-SIGNED-TLV').to_text()
        self.assertIn('QR', text)

    def test_05_a_partly_paid_bill_shows_what_is_left(self):
        order = self._order()
        self.env['pos.payment'].sudo().create({
            'pos_order_id': order.id, 'amount': 40.0,
            'payment_method_id': self.cash.id})
        order.invalidate_recordset()
        text = self._bill_text(order)
        self.assertIn('40.00', text, 'the deposit already taken is not shown')
        self.assertIn('70.00', text, 'what is still due is not shown:\n%s' % text)

    def test_06_the_bill_shows_tax_per_rate(self):
        self.assertIn('BL Tax 10%', self._bill_text(self._order()))

    def test_07_the_endpoint_prints_an_open_order(self):
        order = self._order()
        r = self.url_open('/mezze/hardware/print/bill',
                          data=json.dumps({'uuid': order.uuid, 'preview': True,
                                           'token': 'bl-tok'}),
                          headers={'Content-Type': 'application/json'})
        d = r.json()
        self.assertTrue(d.get('ok'), d)
        self.assertIn('BILL', d.get('preview') or '',
                      'the endpoint did not render a bill: %s' % d)

    def test_08_an_unknown_order_is_refused(self):
        r = self.url_open('/mezze/hardware/print/bill',
                          data=json.dumps({'uuid': 'nope', 'token': 'bl-tok'}),
                          headers={'Content-Type': 'application/json'})
        self.assertEqual(r.json().get('error'), 'unknown_order')

    # -- the reprint -----------------------------------------------------
    def test_10_a_settled_order_can_be_reprinted_by_uuid(self):
        order = self._order(paid=True)
        r = self.url_open('/mezze/hardware/print/receipt',
                          data=json.dumps({'uuid': order.uuid, 'preview': True,
                                           'token': 'bl-tok'}),
                          headers={'Content-Type': 'application/json'})
        d = r.json()
        self.assertTrue(d.get('ok'), d)
        self.assertIn(order.pos_reference, d.get('preview') or '')

    def test_11_a_reprint_is_the_same_document(self):
        # Not "a receipt for the same order" — the same paper. A second copy that
        # differs from the first is a second document.
        from ..models.hardware_render import receipt_ticket
        order = self._order(paid=True)
        self.assertEqual(receipt_ticket(order).to_text(),
                         receipt_ticket(order).to_text())
