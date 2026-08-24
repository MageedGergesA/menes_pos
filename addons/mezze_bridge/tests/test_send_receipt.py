# -*- coding: utf-8 -*-
"""Sending the guest their receipt.

Core's ``action_send_receipt`` takes JPEGs of the ticket that the native POS renders
to a canvas in the browser. Mezze's till has no such canvas — and screenshotting a
receipt to send it is a strange way to deliver text: an image is unsearchable,
unreadable to a screen reader, and large.

What is sent is the SAME ticket the printer gets, as text, so the paper copy and the
emailed copy cannot disagree. That is the property most of these tests are about.

SMS is deliberately conditional. Odoo Community's ``sms`` module sends through IAP,
which is a paid service a branch may not have, and this addon does not depend on it.
The endpoint says so rather than accepting a number and dropping it — a receipt
silently not sent is worse than one refused.
"""
import json

from odoo.tests import tagged

from .common import MezzeHttpCase


@tagged('post_install', '-at_install', 'mezze_send_receipt')
class TestSendReceipt(MezzeHttpCase):
    fixture_profile = 'POS'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        env['ir.config_parameter'].sudo().set_param('mezze_bridge.api_token', 'sr-tok')
        cls.pos_sess = cls._open_session_for(cls.pos_config)
        cls.cash = cls.pos_config.payment_method_ids.filtered('is_cash_count')[:1]
        cls.dish = env['product.product'].sudo().create({
            'name': 'SR Plate', 'available_in_pos': True, 'list_price': 60.0,
            'type': 'consu'})
        cls.dish.write({'taxes_id': [(5, 0, 0)]})
        env.flush_all()

    def _order(self):
        o = self.env['pos.order'].sudo().create({
            'session_id': self.pos_sess.id,
            'company_id': self.pos_config.company_id.id,
            'lines': [(0, 0, {'product_id': self.dish.id, 'qty': 1,
                              'price_unit': 60.0, 'price_subtotal': 60.0,
                              'price_subtotal_incl': 60.0, 'tax_ids': [(6, 0, [])]})],
            'amount_total': 60.0, 'amount_paid': 60.0,
            'amount_tax': 0.0, 'amount_return': 0.0})
        self.env['pos.payment'].sudo().create({
            'pos_order_id': o.id, 'amount': 60.0,
            'payment_method_id': self.cash.id})
        o.sudo().write({'state': 'paid'})
        self.env.flush_all()
        return o

    def _send(self, order, **kw):
        r = self.url_open('/mezze/api/v1/orders/send_receipt',
                          data=json.dumps(dict(kw, order_uuid=order.uuid,
                                               token='sr-tok')),
                          headers={'Content-Type': 'application/json'})
        return r.json()

    # -- email -----------------------------------------------------------
    def test_01_a_receipt_can_be_emailed(self):
        order = self._order()
        d = self._send(order, email='guest@example.com')
        self.assertTrue(d.get('ok'), d)
        self.assertTrue(d['sent']['email'])

    def test_02_the_attachment_is_the_receipt_itself(self):
        # Not a re-rendering: the same ticket the printer gets, so the paper copy and
        # the emailed copy cannot disagree.
        order = self._order()
        self._send(order, email='guest@example.com')
        att = self.env['ir.attachment'].sudo().search(
            [('res_model', '=', 'pos.order'), ('res_id', '=', order.id),
             ('mimetype', '=', 'text/plain')], limit=1)
        self.assertTrue(att, 'nothing was attached')
        body = att.raw.decode('utf-8')
        from ..models.hardware_render import receipt_ticket
        self.assertEqual(body, receipt_ticket(order).to_text(),
                         'the emailed receipt is not the printed one')
        self.assertIn(order.pos_reference, body)

    def test_03_the_address_is_remembered_on_the_order(self):
        order = self._order()
        self._send(order, email='guest@example.com')
        order.invalidate_recordset()
        if 'email' in order._fields:
            self.assertEqual(order.email, 'guest@example.com')

    def test_04_a_mail_is_actually_queued(self):
        order = self._order()
        before = self.env['mail.mail'].sudo().search_count([])
        self._send(order, email='guest@example.com')
        after = self.env['mail.mail'].sudo().search_count([])
        self.assertGreater(after, before, 'no mail was created')

    def test_05_a_nonsense_address_is_refused(self):
        d = self._send(self._order(), email='not-an-address')
        self.assertFalse(d.get('ok'))
        self.assertEqual(d.get('error'), 'bad_email')

    def test_06_sending_nowhere_is_refused(self):
        d = self._send(self._order())
        self.assertEqual(d.get('error'), 'no_destination')

    def test_07_an_unknown_order_is_refused(self):
        r = self.url_open('/mezze/api/v1/orders/send_receipt',
                          data=json.dumps({'order_uuid': 'nope',
                                           'email': 'a@b.com', 'token': 'sr-tok'}),
                          headers={'Content-Type': 'application/json'})
        self.assertEqual(r.json().get('error'), 'order_not_found')

    def test_08_it_is_audited(self):
        order = self._order()
        self._send(order, email='guest@example.com')
        row = self.env['mezze.audit.log'].sudo().search(
            [('event', '=', 'receipt.sent'), ('res_id', '=', order.id)], limit=1)
        self.assertTrue(row, 'sending a guest their receipt was not recorded')

    # -- sms -------------------------------------------------------------
    def test_10_sms_is_honest_about_whether_it_can_send(self):
        # Either the branch has a gateway and it sends, or it says it has none. What
        # it must never do is accept the number and quietly drop it.
        order = self._order()
        d = self._send(order, phone='+201000000000')
        if 'sms.sms' in self.env:
            self.assertTrue(d.get('ok'), d)
            self.assertTrue(d['sent']['sms'])
        else:
            self.assertFalse(d.get('ok'))
            self.assertEqual((d.get('problems') or {}).get('sms'), 'no_gateway')

    def test_11_email_still_works_when_sms_cannot(self):
        # A missing SMS gateway must not cost the guest their emailed receipt.
        order = self._order()
        d = self._send(order, email='guest@example.com', phone='+201000000000')
        self.assertTrue(d.get('ok'), d)
        self.assertTrue(d['sent']['email'])
