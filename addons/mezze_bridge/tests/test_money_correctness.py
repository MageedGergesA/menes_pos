"""Wave 5 — money that comes out right.

Three separate ways Mezze got an amount wrong.

**Refunds went to the wrong tender.** ``/orders/refund`` booked every refund against
``config.payment_method_ids[:1]`` — the branch's FIRST method — regardless of how the
customer actually paid, with no parameter to override it. A card sale refunded against
Cash whenever Cash happened to be listed first, which misstates both the drawer and
the settlement.

**Cash rounding did not exist.** ``account.cash.rounding`` had zero occurrences in the
addon. In a country whose smallest coin is larger than its smallest currency unit the
till asked for an amount the drawer cannot physically make, and the cashier rounded it
in their head with nothing recording that they had.

**Weighed quantities were rounded to counts.** ``_loadOrderLines`` did
``Math.round(l.qty)``, so recalling a 0.4 kg line brought it back as 1 kg.
"""
import json

from odoo.tests import tagged

from .common import MezzeHttpCase


@tagged('post_install', '-at_install', 'mezze_money')
class TestRefundTender(MezzeHttpCase):
    fixture_profile = 'POS'

    def setUp(self):
        super().setUp()
        icp = self.env['ir.config_parameter'].sudo()
        icp.set_param('mezze_bridge.api_token', 'mny-tok')
        icp.set_param('mezze_bridge.api_security', 'observe')
        icp.set_param('mezze_bridge.env_profile', 'development')
        # Payment methods must be arranged BEFORE a session opens: Odoo refuses to
        # modify them on a config with an open session, which is the same caveat the
        # bridge already documents for its own gift-card and online methods.
        methods = self.pos_config.payment_method_ids
        self.cash = methods.filtered(lambda m: m.is_cash_count)[:1]
        self.card = methods.filtered(lambda m: not m.is_cash_count)[:1]
        if not self.card:
            self.card = self.env['pos.payment.method'].create({
                'name': 'Card', 'company_id': self.pos_config.company_id.id})
        # Put CASH first, so a naive implementation refunds to it.
        self.pos_config.write({'payment_method_ids': [
            (6, 0, (self.cash | self.card).ids)]})
        self.session = self.open_test_session()
        self.env.flush_all()

    def _post(self, path, body):
        r = self.url_open('/mezze/api/v1' + path,
                          data=json.dumps(dict(body, token='mny-tok')),
                          headers={'Content-Type': 'application/json'}, timeout=30)
        try:
            return r.status_code, r.json()
        except Exception:  # noqa: BLE001
            return r.status_code, {'_raw': r.text[:300]}

    def _paid_order(self, method, amount=100.0):
        order = self.create_order_in_test_session(session=self.session, price=amount)
        self.env['pos.payment'].create({
            'pos_order_id': order.id, 'amount': amount,
            'payment_method_id': method.id})
        order.write({'state': 'paid', 'amount_paid': amount})
        # The HTTP request reads through its own cursor view; unflushed ORM writes
        # are simply not there yet, and the refund would fall back to the branch
        # default exactly as if the order had never been paid.
        self.env.flush_all()
        return order

    def _all_lines(self, order):
        """Refunding is line-explicit by design — the endpoint reconstructs each
        line from server truth and refuses a request that does not name one."""
        return [{'line_id': l.id, 'product_id': l.product_id.id, 'qty': l.qty}
                for l in order.lines]

    def _refund_methods(self, res):
        self.assertTrue(res.get('ok'), res)
        oid = res.get('order_id') or res.get('refund_order_id')
        self.assertTrue(oid, 'refund response carried no order id: %s' % res)
        refund = self.env['pos.order'].browse(oid)
        return {p.payment_method_id: p.amount for p in refund.payment_ids}

    def test_01_a_card_sale_refunds_to_the_card(self):
        order = self._paid_order(self.card, 100.0)
        code, res = self._post('/orders/refund', {
            'session_id': self.session.id, 'original_order_id': order.id,
            'uuid': 'ref-card-1', 'lines': self._all_lines(order)})
        self.assertEqual(code, 200, res)
        methods = self._refund_methods(res)
        self.assertIn(self.card, methods,
                      'refunded to the branch default instead of the card')
        self.assertNotIn(self.cash, methods)

    def test_02_a_cash_sale_still_refunds_to_cash(self):
        order = self._paid_order(self.cash, 100.0)
        code, res = self._post('/orders/refund', {
            'session_id': self.session.id, 'original_order_id': order.id,
            'uuid': 'ref-cash-1', 'lines': self._all_lines(order)})
        self.assertEqual(code, 200, res)
        self.assertIn(self.cash, self._refund_methods(res))

    def test_03_a_split_tender_refunds_proportionally(self):
        order = self.create_order_in_test_session(session=self.session, price=100.0)
        self.env['pos.payment'].create([
            {'pos_order_id': order.id, 'amount': 60.0,
             'payment_method_id': self.card.id},
            {'pos_order_id': order.id, 'amount': 40.0,
             'payment_method_id': self.cash.id}])
        order.write({'state': 'paid', 'amount_paid': 100.0})
        self.env.flush_all()
        code, res = self._post('/orders/refund', {
            'session_id': self.session.id, 'original_order_id': order.id,
            'uuid': 'ref-split-1', 'lines': self._all_lines(order)})
        self.assertEqual(code, 200, res)
        methods = self._refund_methods(res)
        self.assertIn(self.card, methods, 'the card half was not returned to the card')
        self.assertIn(self.cash, methods, 'the cash half was not returned in cash')
        # the two shares add back up to the refund, with no cent invented or lost.
        # A refund's payments are NEGATIVE — money going back out — so compare on
        # magnitude rather than flipping one side's sign and hoping.
        refund = self.env['pos.order'].browse(res['order_id'])
        self.assertAlmostEqual(abs(sum(methods.values())),
                               abs(refund.amount_total), places=2)
        # and proportionally: the card carried 60% of the sale, so it takes 60% back
        by_method = {m.id: abs(v) for m, v in methods.items()}
        self.assertAlmostEqual(by_method[self.card.id], 60.0, places=2)
        self.assertAlmostEqual(by_method[self.cash.id], 40.0, places=2)

    def test_04_an_explicit_method_still_wins(self):
        # A customer who asks for the money back a different way gets it.
        order = self._paid_order(self.card, 100.0)
        code, res = self._post('/orders/refund', {
            'session_id': self.session.id, 'original_order_id': order.id,
            'uuid': 'ref-exp-1', 'payment_method_id': self.cash.id,
            'lines': self._all_lines(order)})
        self.assertEqual(code, 200, res)
        self.assertIn(self.cash, self._refund_methods(res))


@tagged('post_install', '-at_install', 'mezze_money')
class TestCashRounding(MezzeHttpCase):
    fixture_profile = 'POS'

    def setUp(self):
        super().setUp()
        icp = self.env['ir.config_parameter'].sudo()
        icp.set_param('mezze_bridge.api_token', 'mny-tok')
        icp.set_param('mezze_bridge.api_security', 'observe')
        icp.set_param('mezze_bridge.env_profile', 'development')
        self.session = self.open_test_session()
        company = self.pos_config.company_id
        acc = self.env['account.account'].search(
            [('company_ids', 'in', company.id)], limit=1)
        self.rounding = self.env['account.cash.rounding'].create({
            'name': 'Nearest 0.05', 'rounding': 0.05, 'strategy': 'add_invoice_line',
            'rounding_method': 'HALF-UP',
            'profit_account_id': acc.id, 'loss_account_id': acc.id})
        self.cash = self.pos_config.payment_method_ids.filtered(
            lambda m: m.is_cash_count)[:1]
        self.env.flush_all()

    def _post(self, path, body):
        r = self.url_open('/mezze/api/v1' + path,
                          data=json.dumps(dict(body, token='mny-tok')),
                          headers={'Content-Type': 'application/json'}, timeout=30)
        try:
            return r.status_code, r.json()
        except Exception:  # noqa: BLE001
            return r.status_code, {'_raw': r.text[:300]}

    def test_10_the_rounding_rule_itself_behaves(self):
        self.assertAlmostEqual(self.rounding.round(10.02), 10.00, places=2)
        self.assertAlmostEqual(self.rounding.round(10.03), 10.05, places=2)

    def test_11_a_cash_tender_is_rounded_to_a_payable_amount(self):
        self.pos_config.write({'rounding_method': self.rounding.id,
                               'cash_rounding': True,
                               'only_round_cash_method': False})
        order = self.create_order_in_test_session(session=self.session, price=10.03)
        code, res = self._post('/orders/pay', {
            'session_id': self.session.id, 'order_id': order.id,
            'payment_method_id': self.cash.id})
        self.assertEqual(code, 200, res)
        paid = sum(self.env['pos.order'].browse(order.id).payment_ids.mapped('amount'))
        self.assertAlmostEqual(paid % 0.05, 0.0, places=2,
                               msg='the till asked for an amount the drawer cannot make')

    def test_12_without_a_rule_nothing_is_rounded(self):
        order = self.create_order_in_test_session(session=self.session, price=10.03)
        code, res = self._post('/orders/pay', {
            'session_id': self.session.id, 'order_id': order.id,
            'payment_method_id': self.cash.id})
        self.assertEqual(code, 200, res)
        paid = sum(self.env['pos.order'].browse(order.id).payment_ids.mapped('amount'))
        self.assertAlmostEqual(paid, 10.03, places=2)

    def test_13_only_round_cash_method_spares_a_card(self):
        # A shop rounds because a coin does not exist. Rounding a card payment would
        # invent a difference the acquirer will not agree with.
        card = self.pos_config.payment_method_ids.filtered(
            lambda m: not m.is_cash_count)[:1]
        if not card:
            self.skipTest('fixture has no non-cash method')
        self.pos_config.write({'rounding_method': self.rounding.id,
                               'cash_rounding': True,
                               'only_round_cash_method': True})
        order = self.create_order_in_test_session(session=self.session, price=10.03)
        code, res = self._post('/orders/pay', {
            'session_id': self.session.id, 'order_id': order.id,
            'payment_method_id': card.id})
        self.assertEqual(code, 200, res)
        paid = sum(self.env['pos.order'].browse(order.id).payment_ids.mapped('amount'))
        self.assertAlmostEqual(paid, 10.03, places=2,
                               msg='a card payment was rounded')


@tagged('post_install', '-at_install', 'mezze_money')
class TestWeighedProducts(MezzeHttpCase):
    fixture_profile = 'POS'

    def setUp(self):
        super().setUp()
        icp = self.env['ir.config_parameter'].sudo()
        icp.set_param('mezze_bridge.api_token', 'mny-tok')
        icp.set_param('mezze_bridge.api_security', 'observe')
        icp.set_param('mezze_bridge.env_profile', 'development')
        self.session = self.open_test_session()
        self.product.write({'to_weight': True})
        self.env.flush_all()

    def _post(self, path, body):
        r = self.url_open('/mezze/api/v1' + path,
                          data=json.dumps(dict(body, token='mny-tok')),
                          headers={'Content-Type': 'application/json'}, timeout=30)
        try:
            return r.status_code, r.json()
        except Exception:  # noqa: BLE001
            return r.status_code, {'_raw': r.text[:300]}

    def test_20_the_catalogue_says_which_products_are_weighed(self):
        code, res = self._post('/bootstrap', {'config_id': self.pos_config.id})
        self.assertEqual(code, 200, res)
        mine = [p for p in res['products'] if p['id'] == self.product.id]
        self.assertTrue(mine, 'the fixture product is not in the catalogue')
        self.assertTrue(mine[0]['to_weight'],
                        'the till is never told this product is sold by weight')
        self.assertIn('uom_name', mine[0])

    def test_21_a_fractional_quantity_survives_the_server(self):
        uuid = 'wgt-1'
        self._post('/orders/sync', {
            'uuid': uuid, 'session_id': self.session.id, 'draft': True,
            'lines': [{'product_id': self.product.id, 'qty': 0.4}]})
        order = self.env['pos.order'].search([('uuid', '=', uuid)], limit=1)
        self.assertAlmostEqual(order.lines[0].qty, 0.4, places=3,
                               msg='a measured quantity was rounded to a count')

    def test_22_the_fraction_survives_being_read_back(self):
        uuid = 'wgt-2'
        self._post('/orders/sync', {
            'uuid': uuid, 'session_id': self.session.id, 'draft': True,
            'lines': [{'product_id': self.product.id, 'qty': 0.4}]})
        _c, res = self._post('/orders/get', {'uuid': uuid})
        self.assertAlmostEqual(res['lines'][0]['qty'], 0.4, places=3)
