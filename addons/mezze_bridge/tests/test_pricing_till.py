"""Wave 4 — pricing that knows the customer, and the till affordances around it.

**The pricing bug is the serious one.** ``property_product_pricelist`` — the
partner's own agreed pricelist — appeared NOWHERE in the addon. Every order priced
against ``config.pricelist_id``, so a B2B customer with a negotiated agreement was
silently charged branch list price. It was easy to miss because the partner *was*
already used for the fiscal position: tax was customer-aware while price was not.

Alongside it, four core switches Mezze shipped without reading
(``restrict_price_control``, ``manual_discount``, ``basic_receipt``,
``iface_tax_included``), no way to switch pricelist or fiscal position on an order,
no order-level note, no product info, and a scanner that could not work because the
client discarded ``barcode`` and ``default_code`` from a payload that had always
carried them.
"""
import json

from odoo.tests import tagged

from .common import MezzeHttpCase


@tagged('post_install', '-at_install', 'mezze_pricing')
class TestPricingAndTill(MezzeHttpCase):
    fixture_profile = 'POS'

    def setUp(self):
        super().setUp()
        icp = self.env['ir.config_parameter'].sudo()
        icp.set_param('mezze_bridge.api_token', 'prc-tok')
        icp.set_param('mezze_bridge.api_security', 'observe')
        icp.set_param('mezze_bridge.env_profile', 'development')
        self.session = self.open_test_session()
        Pricelist = self.env['product.pricelist']
        self.trade = Pricelist.create({
            'name': 'Trade', 'currency_id': self.pos_config.currency_id.id,
            'item_ids': [(0, 0, {'compute_price': 'percentage',
                                 'percent_price': 50.0,
                                 'applied_on': '3_global'})]})
        # ``property_product_pricelist`` is COMPANY-DEPENDENT. Written outside the
        # till's own company it reads back as that company's default, which is a real
        # trap rather than a test artefact — it is how a negotiated price silently
        # stops applying on a second company.
        # ``specific_property_product_pricelist`` is the STORED field. In v19 the
        # familiar ``property_product_pricelist`` is a computed accessor that falls
        # back to a company default, so it is never empty and cannot express "this
        # customer negotiated a price".
        self.partner = self.env['res.partner'].with_company(
            self.pos_config.company_id).create({
                'name': 'Trade Tarek', 'customer_rank': 1,
                'specific_property_product_pricelist': self.trade.id})
        self.env.flush_all()

    def _post(self, path, body):
        r = self.url_open('/mezze/api/v1' + path,
                          data=json.dumps(dict(body, token='prc-tok')),
                          headers={'Content-Type': 'application/json'}, timeout=30)
        try:
            return r.status_code, r.json()
        except Exception:  # noqa: BLE001
            return r.status_code, {'_raw': r.text[:300]}

    def _order(self, uuid):
        return self.env['pos.order'].search([('uuid', '=', uuid)], limit=1)

    # ── the customer's own pricelist ─────────────────────────────────────────
    def test_01_a_partner_pricelist_is_honoured(self):
        uuid = 'prc-1'
        code, res = self._post('/orders/sync', {
            'uuid': uuid, 'session_id': self.session.id, 'draft': True,
            'partner_id': self.partner.id,
            'lines': [{'product_id': self.product.id, 'qty': 1}]})
        self.assertEqual(code, 200, res)
        order = self._order(uuid)
        list_price = self.product.lst_price
        self.assertEqual(order.pricelist_id, self.trade,
                         'the order did not price against the customer agreement')
        self.assertLess(order.lines[0].price_unit, list_price,
                        'the customer agreement was ignored — charged list price')

    def test_02_a_walk_in_still_pays_the_branch_price(self):
        uuid = 'prc-2'
        self._post('/orders/sync', {
            'uuid': uuid, 'session_id': self.session.id, 'draft': True,
            'lines': [{'product_id': self.product.id, 'qty': 1}]})
        order = self._order(uuid)
        self.assertAlmostEqual(order.lines[0].price_unit, self.product.lst_price,
                               places=2)

    def test_02b_a_named_customer_without_an_agreement_pays_the_branch_price(self):
        # The trap: v19's computed ``property_product_pricelist`` is never empty, so
        # reading it would re-price every named customer against a company default.
        plain = self.env['res.partner'].create({'name': 'Plain Pierre',
                                                'customer_rank': 1})
        uuid = 'prc-2b'
        self._post('/orders/sync', {
            'uuid': uuid, 'session_id': self.session.id, 'draft': True,
            'partner_id': plain.id,
            'lines': [{'product_id': self.product.id, 'qty': 1}]})
        order = self._order(uuid)
        self.assertEqual(order.pricelist_id, self.pos_config.pricelist_id,
                         'a customer with no agreement was moved off the branch list')

    def test_03_an_explicit_pricelist_must_be_one_the_branch_offers(self):
        # A till cannot be told to price against a list its branch does not trade on.
        rogue = self.env['product.pricelist'].create({
            'name': 'Rogue', 'currency_id': self.pos_config.currency_id.id,
            'item_ids': [(0, 0, {'compute_price': 'percentage',
                                 'percent_price': 90.0, 'applied_on': '3_global'})]})
        uuid = 'prc-3'
        self._post('/orders/sync', {
            'uuid': uuid, 'session_id': self.session.id, 'draft': True,
            'pricelist_id': rogue.id,
            'lines': [{'product_id': self.product.id, 'qty': 1}]})
        order = self._order(uuid)
        self.assertAlmostEqual(order.lines[0].price_unit, self.product.lst_price,
                               places=2, msg='an unoffered pricelist was accepted')

    def test_04_an_offered_pricelist_can_be_chosen(self):
        self.pos_config.write({'use_pricelist': True,
                               'available_pricelist_ids': [(4, self.trade.id)]})
        uuid = 'prc-4'
        self._post('/orders/sync', {
            'uuid': uuid, 'session_id': self.session.id, 'draft': True,
            'pricelist_id': self.trade.id,
            'lines': [{'product_id': self.product.id, 'qty': 1}]})
        order = self._order(uuid)
        self.assertLess(order.lines[0].price_unit, self.product.lst_price)

    # ── price control ────────────────────────────────────────────────────────
    def test_10_a_client_price_is_honoured_when_the_branch_allows_it(self):
        uuid = 'prc-10'
        self._post('/orders/sync', {
            'uuid': uuid, 'session_id': self.session.id, 'draft': True,
            'lines': [{'product_id': self.product.id, 'qty': 1, 'price_unit': 3.0}]})
        self.assertAlmostEqual(self._order(uuid).lines[0].price_unit, 3.0, places=2)

    def test_11_restrict_price_control_actually_restricts(self):
        # The switch existed in core and Mezze never read it: a client price was
        # honoured unconditionally.
        self.pos_config.write({'restrict_price_control': True})
        cashier = self.env['mezze.cashier'].create(
            {'name': 'Sara', 'code': 'PRC9', 'role': 'cashier'})
        uuid = 'prc-11'
        self._post('/orders/sync', {
            'uuid': uuid, 'session_id': self.session.id, 'draft': True,
            'cashier_id': cashier.id,
            'lines': [{'product_id': self.product.id, 'qty': 1, 'price_unit': 3.0}]})
        order = self._order(uuid)
        self.assertAlmostEqual(order.lines[0].price_unit, self.product.lst_price,
                               places=2, msg='a restricted branch still took a browser price')

    def test_11b_the_switch_also_holds_on_the_fire_path(self):
        """The SAME rule, on the other line builder.

        Found by mutation: deleting ``and allow_override`` from ``_build_lines``
        (the canonical builder) broke no test. ``test_11`` above covers
        ``/orders/sync``, which has a builder of its own; the canonical one backs
        fire, delivery, terminal sync and the aggregator, and nothing was watching
        it. The gate is correct — but a branch that restricts price control does so
        through four more doors than the suite knew about, and a future edit to that
        builder would have gone unnoticed.
        """
        self.pos_config.write({'restrict_price_control': True})
        cashier = self.env['mezze.cashier'].create(
            {'name': 'Fire Cashier', 'code': 'PRC7', 'role': 'cashier'})
        uuid = 'prc-11b'
        code, res = self._post('/orders/fire', {
            'uuid': uuid, 'session_id': self.session.id,
            'cashier_id': cashier.id,
            'lines': [{'product_id': self.product.id, 'qty': 1, 'price_unit': 3.0}]})
        order = self._order(uuid)
        self.assertTrue(order, 'the fire path did not create an order: %s' % (res,))
        self.assertAlmostEqual(
            order.lines[0].price_unit, self.product.lst_price, places=2,
            msg='a restricted branch took a browser price through /orders/fire')

    def test_11c_a_manager_may_still_price_on_the_fire_path(self):
        # Guard against closing the hole by breaking the exception: the switch
        # restricts a cashier, not everybody.
        self.pos_config.write({'restrict_price_control': True})
        mgr = self.env['mezze.cashier'].create(
            {'name': 'Fire Manager', 'code': 'PRC6', 'role': 'manager'})
        uuid = 'prc-11c'
        self._post('/orders/fire', {
            'uuid': uuid, 'session_id': self.session.id,
            'cashier_id': mgr.id,
            'lines': [{'product_id': self.product.id, 'qty': 1, 'price_unit': 3.0}]})
        order = self._order(uuid)
        self.assertTrue(order)
        self.assertAlmostEqual(
            order.lines[0].price_unit, 3.0, places=2,
            msg='a manager could not correct a price on a restricted branch')

    def test_12_a_manager_may_still_set_a_price_on_a_restricted_branch(self):
        # The switch restricts a cashier, not everybody — otherwise a manager could
        # not correct a mispriced item without leaving the till.
        self.pos_config.write({'restrict_price_control': True})
        mgr = self.env['mezze.cashier'].create(
            {'name': 'Mona', 'code': 'PRC8', 'role': 'manager'})
        uuid = 'prc-12'
        self._post('/orders/sync', {
            'uuid': uuid, 'session_id': self.session.id, 'draft': True,
            'cashier_id': mgr.id,
            'lines': [{'product_id': self.product.id, 'qty': 1, 'price_unit': 3.0}]})
        self.assertAlmostEqual(self._order(uuid).lines[0].price_unit, 3.0, places=2)

    # ── bootstrap tells the till what the branch expects ─────────────────────
    def test_20_bootstrap_carries_the_branch_policy(self):
        code, res = self._post('/bootstrap', {'config_id': self.pos_config.id})
        self.assertEqual(code, 200, res)
        for key in ('restrict_price_control', 'manual_discount', 'basic_receipt'):
            self.assertIn(key, res['config'], 'the till is never told about %r' % key)
        for key in ('pricelists', 'fiscal_positions', 'note_presets'):
            self.assertIn(key, res)

    def test_21_bootstrap_still_carries_the_codes_a_scanner_needs(self):
        _c, res = self._post('/bootstrap', {'config_id': self.pos_config.id})
        p = res['products'][0]
        self.assertIn('barcode', p)
        self.assertIn('default_code', p)

    # ── order-level note ─────────────────────────────────────────────────────
    def test_30_an_order_can_carry_its_own_note(self):
        uuid = 'prc-30'
        self._post('/orders/sync', {
            'uuid': uuid, 'session_id': self.session.id, 'draft': True,
            'lines': [{'product_id': self.product.id, 'qty': 1}]})
        order = self._order(uuid)
        code, res = self._post('/orders/note',
                               {'order_id': order.id, 'note': 'birthday - cake last'})
        self.assertEqual(code, 200, res)
        order.invalidate_recordset()
        self.assertEqual(order.internal_note, 'birthday - cake last')

    def test_31_a_paid_order_takes_no_note(self):
        uuid = 'prc-31'
        self._post('/orders/sync', {
            'uuid': uuid, 'session_id': self.session.id, 'draft': True,
            'lines': [{'product_id': self.product.id, 'qty': 1}]})
        order = self._order(uuid)
        order.write({'state': 'paid'})
        code, _res = self._post('/orders/note', {'order_id': order.id, 'note': 'late'})
        self.assertEqual(code, 400)

    # ── product info ─────────────────────────────────────────────────────────
    def test_40_product_info_answers_what_a_cashier_is_asked(self):
        code, res = self._post('/products/info',
                               {'product_id': self.product.id,
                                'config_id': self.pos_config.id})
        self.assertEqual(code, 200, res)
        for key in ('name', 'price', 'taxes', 'available', 'pricelists'):
            self.assertIn(key, res)

    def test_41_cost_and_margin_are_not_shown_to_a_till(self):
        # A cashier reading the shop's cost price off the till is not a feature.
        cashier = self.env['mezze.cashier'].create(
            {'name': 'Sara', 'code': 'PRC1', 'role': 'cashier'})
        code, res = self._post('/products/info',
                               {'product_id': self.product.id,
                                'config_id': self.pos_config.id,
                                'cashier_id': cashier.id})
        self.assertEqual(code, 200, res)
        self.assertNotIn('cost', res)
        self.assertNotIn('margin', res)

    def test_42_a_manager_does_see_the_margin(self):
        mgr = self.env['mezze.cashier'].create(
            {'name': 'Mona', 'code': 'PRC2', 'role': 'manager'})
        code, res = self._post('/products/info',
                               {'product_id': self.product.id,
                                'config_id': self.pos_config.id,
                                'cashier_id': mgr.id})
        self.assertEqual(code, 200, res)
        self.assertIn('margin', res)
