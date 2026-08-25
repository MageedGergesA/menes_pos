# -*- coding: utf-8 -*-
"""What the drawer is supposed to hold at close.

Found by mutation: replacing

    expected = cash_start + cash_payments

with ``expected = cash_payments`` broke **no test in the suite**. The opening float
could be dropped from the expected-cash calculation and everything stayed green.

It is load-bearing. ``expected`` is what the counted cash is measured against, so
forgetting the float understates it by exactly the float — and a drawer that is
perfectly correct then reports a surplus of that amount at every single close. On a
branch with ``set_maximum_difference`` on, a correct drawer would also trip the
variance ceiling and demand a manager every night, which is the fastest way to teach
a shop that the variance check is noise to be clicked through.

The formula lives in **two** places — the close preview and the close itself — with
nothing tying them together. That is the "derive twice, differently" shape that has
already produced real bugs in this codebase, so the last test here pins them to each
other rather than to a number: whatever the rule is, the screen a cashier reads and
the arithmetic that judges them must not be able to disagree.
"""
import json

from odoo.tests import tagged

from .common import MezzeHttpCase


@tagged('post_install', '-at_install', 'mezze_cash_close')
class TestExpectedCash(MezzeHttpCase):
    fixture_profile = 'POS'

    OPENING_FLOAT = 200.0

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        env['ir.config_parameter'].sudo().set_param('mezze_bridge.api_token', 'cx-tok')
        cls.pos_sess = cls._open_session_for(cls.pos_config)
        # A branch that opens with a float in the drawer, which is every branch.
        cls.pos_sess.sudo().write(
            {'cash_register_balance_start': cls.OPENING_FLOAT})
        cls.cash = cls.pos_config.payment_method_ids.filtered('is_cash_count')[:1]
        cls.dish = env['product.product'].sudo().create({
            'name': 'CX Plate', 'available_in_pos': True, 'list_price': 50.0,
            'type': 'consu'})
        cls.dish.write({'taxes_id': [(5, 0, 0)]})
        env.flush_all()

    def _post(self, path, body):
        r = self.url_open('/mezze/api/v1' + path,
                          data=json.dumps(dict(body, token='cx-tok')),
                          headers={'Content-Type': 'application/json'})
        try:
            return r.status_code, r.json()
        except Exception:  # noqa: BLE001
            return r.status_code, {'raw': r.text[:200]}

    def _take_cash(self, amount=50.0, uuid='cx-1'):
        order = self.env['pos.order'].sudo().create({
            'session_id': self.pos_sess.id, 'uuid': uuid,
            'company_id': self.pos_config.company_id.id,
            'lines': [(0, 0, {'product_id': self.dish.id, 'qty': 1,
                              'price_unit': amount, 'price_subtotal': amount,
                              'price_subtotal_incl': amount, 'tax_ids': [(6, 0, [])]})],
            'amount_total': amount, 'amount_paid': amount, 'amount_tax': 0.0,
            'amount_return': 0.0})
        self.env['pos.payment'].sudo().create({
            'pos_order_id': order.id, 'amount': amount,
            'payment_method_id': self.cash.id})
        order.write({'state': 'paid'})
        self.env.flush_all()
        return order

    def _preview(self):
        return self._post('/sessions/%d/close/preview' % self.pos_sess.id, {})

    # ── the float is part of what the drawer should hold ─────────────────
    def test_01_the_preview_counts_the_opening_float(self):
        self._take_cash(50.0)
        code, res = self._preview()
        self.assertEqual(code, 200, res)
        self.assertAlmostEqual(res['cash_opening'], self.OPENING_FLOAT, places=2)
        self.assertAlmostEqual(res['cash_payments'], 50.0, places=2)
        self.assertAlmostEqual(
            res['cash_expected'], self.OPENING_FLOAT + 50.0, places=2,
            msg='the float was dropped from what the drawer should hold: %r' % res)

    def test_02_a_correct_drawer_reports_no_variance(self):
        """THE finding. Forget the float and a correct drawer looks 200 over."""
        self._take_cash(50.0, uuid='cx-2')
        code, res = self._post('/sessions/%d/close' % self.pos_sess.id,
                               {'counted_cash': self.OPENING_FLOAT + 50.0})
        self.assertEqual(code, 200, res)
        # No `or 0.0` fallback anywhere below: a missing key must fail loudly, not
        # read as "no variance". The first draft of this file used the wrong key
        # name and passed green against a mutant, which is the whole lesson.
        self.assertIsNotNone(res.get('cash_difference'), res)
        self.assertAlmostEqual(
            res['cash_difference'], 0.0, places=2,
            msg='a drawer holding exactly the right cash reported a variance: %r' % res)

    def test_03_a_genuinely_short_drawer_still_shows_it(self):
        # Guard against fixing the false surplus by never reporting anything.
        self._take_cash(50.0, uuid='cx-3')
        code, res = self._post('/sessions/%d/close' % self.pos_sess.id,
                               {'counted_cash': self.OPENING_FLOAT + 50.0 - 30.0})
        self.assertEqual(code, 200, res)
        self.assertAlmostEqual(res['cash_difference'], -30.0, places=2,
                               msg='a drawer 30 short reported %r' % res)

    # ── the two copies of the formula must agree ─────────────────────────
    def test_10_the_screen_and_the_close_use_the_same_arithmetic(self):
        """The formula lives in two places with nothing tying them together.

        Pinned to each OTHER rather than to a number: whatever the rule is, the
        figure a cashier is shown before counting and the figure their count is
        judged against must not be able to drift apart.
        """
        self._take_cash(50.0, uuid='cx-4')
        _c, preview = self._preview()
        expected_on_screen = preview['cash_expected']
        # Count exactly what the screen said, and the close must call it square.
        _c2, closed = self._post('/sessions/%d/close' % self.pos_sess.id,
                                 {'counted_cash': expected_on_screen})
        self.assertIsNotNone(closed.get('cash_difference'), closed)
        self.assertAlmostEqual(
            closed['cash_difference'], 0.0, places=2,
            msg='counting exactly what the screen asked for produced a variance: '
                'preview=%r close=%r' % (preview, closed))
        # And the close must echo the same expectation it judged against.
        self.assertAlmostEqual(closed['cash_expected'], expected_on_screen, places=2)
