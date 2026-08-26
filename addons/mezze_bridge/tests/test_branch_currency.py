# -*- coding: utf-8 -*-
"""A branch is charged in ITS currency, not its parent company's.

``pos.config.currency_id`` is whatever the till's sale journal trades in, and only
falls back to the company's when the journal has none of its own (core's
``_compute_currency``). A duty-free counter, an airport café or a hotel POS running
a Gulf currency inside a company that keeps its books in another is an ordinary
Odoo configuration — and Mezze already knows it exists, because a refund presented
across a currency boundary is rejected as ``CURRENCY_MISMATCH``.

The pre-fire cart pricer did not know it. ``mezze.cart.pricing._price_cart`` took
``config.company_id.currency_id`` and then rounded every figure to a hard-coded two
places. Both are wrong on a 3-decimal currency:

* ``compute_all`` rounds tax at the precision of the currency it is handed, so the
  tax was computed to the company's two places, not the branch's three;
* the row and cart totals were then rounded to 2 again on the way out.

Measured on a branch trading in KWD inside a USD company: a four-line cart the
branch prices at **7.946** was quoted to the guest as **7.950**, and each line lost
its third decimal (0.752 shown as 0.75). A fils per line, on every cart, in the
direction of the house.

The label was wrong with it. The customer's Order Confirmation Board and the
drive-thru quote both named ``company_id.currency_id`` — so a board showing a KWD
bill was labelled **USD**, and handed the client the company's **2** decimals to
format three-decimal money with.

The till path had it right all along: ``bootstrap`` already passed
``config.currency_id`` into ``compute_all``. One of the two paths through this
addon's money knew the answer; the customer-facing one did not.
"""
import json

from odoo.tests import tagged

from .common import MezzeHttpCase


@tagged('post_install', '-at_install', 'mezze_currency')
class TestBranchCurrency(MezzeHttpCase):
    """A POS whose journal trades in a currency the company does not keep."""
    fixture_profile = 'POS'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        env['ir.config_parameter'].sudo().set_param('mezze_bridge.api_token', 'bc-tok')

        # A 3-decimal currency. The MENA case this is really about: KWD, BHD, OMR
        # and JOD all carry three, and every one of them can sit on a POS journal
        # inside a company keeping 2-decimal books.
        cls.kwd = env['res.currency'].sudo().with_context(active_test=False).search(
            [('name', '=', 'KWD')], limit=1)
        cls.kwd.write({'active': True})
        assert cls.kwd.decimal_places == 3, 'KWD is expected to carry three decimals'
        assert cls.kwd != cls.company.currency_id, \
            'this fixture needs the branch currency to differ from the company one'

        journal = env['account.journal'].sudo().create({
            'name': 'Mezze Duty Free Sale', 'code': 'MZDF', 'type': 'sale',
            'currency_id': cls.kwd.id, 'company_id': cls.company.id})
        # No pricelist: core forbids attaching one whose currency differs from the
        # config's, and this test is about how money is ROUNDED and LABELLED, not
        # about converting between currencies.
        cls.foreign = env['pos.config'].sudo().create({
            'name': 'Mezze Duty Free', 'journal_id': journal.id,
            'company_id': cls.company.id})
        cls.foreign.invalidate_recordset()

        cls.tax = env['account.tax'].sudo().create({
            'name': 'Branch 14%', 'amount': 14.0, 'amount_type': 'percent',
            'type_tax_use': 'sale', 'company_id': cls.company.id,
            'price_include_override': 'tax_excluded'})
        # Prices that are exact at two places -- `list_price` is stored at the
        # "Product Price" precision, so a sub-cent menu price would be rounded away
        # before this test ever reached the pricer. The THIRD decimal is created by
        # the tax, which is the realistic case anyway: a menu priced in whole fils
        # whose 14% lands on a fraction of one.
        # A real menu item carries a POS category -- `_menu_domain` filters on it to
        # keep loyalty utility products off the till, so a product without one never
        # reaches the menu at all.
        cls.categ = env['pos.category'].sudo().create({'name': 'Duty Free'})
        cls.menu = env['product.product'].sudo().create([
            {'name': 'Karak Tea', 'type': 'consu', 'available_in_pos': True,
             'list_price': 0.35, 'taxes_id': [(6, 0, [cls.tax.id])],
             'pos_categ_ids': [(6, 0, [cls.categ.id])]},
            {'name': 'Falafel Wrap', 'type': 'consu', 'available_in_pos': True,
             'list_price': 0.75, 'taxes_id': [(6, 0, [cls.tax.id])],
             'pos_categ_ids': [(6, 0, [cls.categ.id])]},
        ])
        cls.menu.write({'taxes_id': [(6, 0, [cls.tax.id])]})
        env.flush_all()
        # A product can carry taxes belonging to another company, and the branch only
        # ever charges its own. Stated here so an expectation computed from `cls.tax`
        # below is provably the tax the branch actually applies -- otherwise these
        # tests could agree with the code for the wrong reason.
        for product in cls.menu:
            charged = product.taxes_id.filtered(
                lambda t: t.company_id == cls.foreign.company_id)
            assert charged == cls.tax, (
                'fixture drift: %s is charged %r, not the single branch tax'
                % (product.name, charged.mapped('name')))

    def _cart(self):
        return [{'product_id': self.menu[0].id, 'qty': 2},
                {'product_id': self.menu[1].id, 'qty': 3}]

    def _priced(self, config=None):
        return self.env['mezze.cart.pricing']._price_cart(
            config or self.foreign, self._cart())

    # ── the arithmetic ───────────────────────────────────────────────────
    def test_01_the_cart_is_priced_at_the_branchs_precision(self):
        """THE bug. The branch trades in a 3-decimal currency; the pricer rounded
        to the company's 2 and the third decimal was dropped off every line."""
        rows, money = self._priced()
        dp = self.foreign.currency_id.decimal_places
        self.assertEqual(dp, 3)

        # What the branch itself says the cart costs, computed line by line in its
        # own currency — the answer the pricer has to agree with.
        expected = 0.0
        for product, qty in zip(self.menu, (2.0, 3.0)):
            c = self.tax.compute_all(
                product.list_price, currency=self.foreign.currency_id,
                quantity=qty, product=product)
            expected += c['total_included']
        expected = round(expected, dp)

        self.assertAlmostEqual(
            money['total'], expected, places=dp,
            msg='the cart was quoted %.3f where the branch prices it %.3f — the '
                'money was rounded at the COMPANY currency\'s precision'
                % (money['total'], expected))

    def test_02_a_line_keeps_its_third_decimal(self):
        """The per-row half: `line_total` was rounded to a literal 2."""
        rows, _money = self._priced()
        self.assertTrue(rows)
        c = self.tax.compute_all(
            self.menu[0].list_price, currency=self.foreign.currency_id,
            quantity=2.0, product=self.menu[0])
        self.assertAlmostEqual(
            rows[0]['line_total'], round(c['total_included'], 3), places=3,
            msg='a line on a 3-decimal branch was rounded to 2 places')

    def test_03_the_tax_is_computed_in_the_branchs_currency(self):
        """The root cause, stated on its own: `compute_all` rounds at the precision
        of the currency it is given, so handing it the wrong one is not cosmetic."""
        _rows, money = self._priced()
        branch = sum(
            self.tax.compute_all(p.list_price, currency=self.foreign.currency_id,
                                 quantity=q, product=p)['total_included']
            - self.tax.compute_all(p.list_price, currency=self.foreign.currency_id,
                                   quantity=q, product=p)['total_excluded']
            for p, q in zip(self.menu, (2.0, 3.0)))
        self.assertAlmostEqual(money['tax'], round(branch, 3), places=3)

    def test_04_an_ordinary_single_currency_branch_is_unchanged(self):
        """The guard on the fix. Almost every branch keeps the company's currency,
        and that overwhelmingly common case must round exactly as it always did."""
        self.assertEqual(self.pos_config.currency_id, self.company.currency_id)
        _rows, money = self._priced(self.pos_config)
        for key in ('subtotal', 'tax', 'total'):
            self.assertAlmostEqual(money[key], round(money[key], 2), places=6,
                                   msg='a 2-decimal branch gained decimals it does '
                                       'not have')

    # ── the label ────────────────────────────────────────────────────────
    def test_10_the_customer_board_names_the_branchs_currency(self):
        """A KWD bill on the guest's board was labelled USD."""
        display, _token = self.env['mezze.ocb.display'].sudo()._provision(self.foreign)
        display._publish(self._cart())
        payload = json.loads(display.payload or '{}')
        cur = payload.get('currency') or {}
        self.assertEqual(cur.get('name'), self.foreign.currency_id.name,
                         'the board labels the guest\'s money with the COMPANY '
                         'currency, not the one the branch charges in')
        self.assertEqual(cur.get('decimals'), 3,
                         'the board is told to format 3-decimal money to 2 places')

    def test_11_the_drive_thru_quote_names_the_branchs_currency(self):
        r = self.url_open(
            '/mezze/api/v1/drivethru/quote',
            data=json.dumps({'token': 'bc-tok', 'config_id': self.foreign.id,
                             'lines': self._cart()}),
            headers={'Content-Type': 'application/json'})
        res = r.json()
        self.assertTrue(res.get('ok'), res)
        self.assertEqual((res.get('currency') or {}).get('name'),
                         self.foreign.currency_id.name)
        self.assertEqual((res.get('currency') or {}).get('decimals'), 3)

    def test_12_a_blank_symbol_still_labels_the_money(self):
        """Every other surface falls back to the ISO code; these three sent an
        empty string, so the guest's screen showed a bare number."""
        self.foreign.currency_id.sudo().write({'symbol': ''})
        self.env.flush_all()
        display, _token = self.env['mezze.ocb.display'].sudo()._provision(self.foreign)
        display._publish(self._cart())
        board = (json.loads(display.payload or '{}').get('currency') or {})
        self.assertEqual(board.get('symbol'), self.foreign.currency_id.name)

        r = self.url_open(
            '/mezze/api/v1/drivethru/quote',
            data=json.dumps({'token': 'bc-tok', 'config_id': self.foreign.id,
                             'lines': self._cart()}),
            headers={'Content-Type': 'application/json'})
        self.assertEqual((r.json().get('currency') or {}).get('symbol'),
                         self.foreign.currency_id.name)

    # ── the till ─────────────────────────────────────────────────────────
    def test_20_the_menu_the_till_loads_carries_the_branchs_precision(self):
        """`bootstrap` passed the right currency into `compute_all` all along, then
        rounded the result to a literal 2 on the way out."""
        self._open_session_for(self.foreign)
        r = self.url_open(
            '/mezze/api/v1/bootstrap',
            data=json.dumps({'token': 'bc-tok', 'config_id': self.foreign.id}),
            headers={'Content-Type': 'application/json'})
        res = r.json()
        self.assertTrue(res.get('ok'), res)
        by_id = {p['id']: p for p in (res.get('products') or [])}
        tea = by_id.get(self.menu[0].id)
        self.assertTrue(tea, 'the branch menu did not reach the till')
        c = self.tax.compute_all(
            self.menu[0].list_price, currency=self.foreign.currency_id,
            quantity=1.0, product=self.menu[0])
        # The TAX-INCLUSIVE price is the one that carries the third decimal here:
        # 0.350 net becomes 0.399 gross, and at two places that is 0.40. Asserting
        # on `price_excl` would pass either way, because a net price exact at two
        # places is unchanged by rounding it to three.
        self.assertAlmostEqual(
            tea['price_incl'], round(c['total_included'], 3), places=3,
            msg='the till was sent a menu rounded to the company\'s 2 places: '
                '%r where the branch prices it %r'
                % (tea['price_incl'], round(c['total_included'], 3)))
        self.assertNotAlmostEqual(
            round(c['total_included'], 3), round(c['total_included'], 2), places=3,
            msg='fixture drift: this price no longer differs between 2 and 3 '
                'decimals, so the test can no longer detect the bug')
