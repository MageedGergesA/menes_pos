# -*- coding: utf-8 -*-
"""Showing prices with or without tax.

``iface_tax_included`` is a core setting Mezze shipped in its boot payload and never
read. A branch that set "Tax-Excluded Price" got tax-included prices anyway, and a
cashier quoting a guest the other figure for one order had no way to ask for it —
core's Actions → Tax.

The decision worth recording is that the SERVER sends both figures. Deriving one from
the other in the browser is the obvious shortcut and it is wrong on exactly the
branches that care: multiple taxes, price-included flags and fiscal positions are not
arithmetic a browser should attempt. Odoo's own ``compute_all`` runs once per product
when the catalogue is built, and the toggle then only chooses a field.
"""
import json

from odoo.tests import tagged

from .common import MezzeHttpCase


@tagged('post_install', '-at_install', 'mezze_taxdisplay')
class TestTaxDisplay(MezzeHttpCase):
    fixture_profile = 'POS'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        env['ir.config_parameter'].sudo().set_param('mezze_bridge.api_token', 'tx-tok')
        cls.tax = env['account.tax'].sudo().create({
            'name': 'TX 10%', 'amount': 10.0, 'amount_type': 'percent',
            'type_tax_use': 'sale', 'price_include_override': 'tax_excluded',
            'company_id': cls.pos_config.company_id.id})
        cls.categ = env['pos.category'].sudo().search([], limit=1) \
            or env['pos.category'].sudo().create({'name': 'TX'})
        cls.dish = env['product.product'].sudo().create({
            'name': 'TX Plate', 'available_in_pos': True, 'list_price': 100.0,
            'type': 'consu', 'pos_categ_ids': [(6, 0, cls.categ.ids)],
            'taxes_id': [(6, 0, cls.tax.ids)]})
        cls.untaxed = env['product.product'].sudo().create({
            'name': 'TX Water', 'available_in_pos': True, 'list_price': 50.0,
            'type': 'consu', 'pos_categ_ids': [(6, 0, cls.categ.ids)]})
        cls.untaxed.write({'taxes_id': [(5, 0, 0)]})
        cls.pos_sess = cls._open_session_for(cls.pos_config)
        env.flush_all()

    def _boot(self):
        r = self.url_open('/mezze/api/v1/bootstrap',
                          data=json.dumps({'token': 'tx-tok'}),
                          headers={'Content-Type': 'application/json'})
        return r.json()

    def _product(self, boot, name):
        return next(p for p in boot['products'] if p['name'].endswith(name))

    # -- both figures come from the server --------------------------------
    def test_01_the_catalogue_carries_both_prices(self):
        b = self._boot()
        self.assertTrue(b.get('ok'), b)
        p = self._product(b, 'TX Plate')
        self.assertAlmostEqual(p['price_excl'], 100.0, places=2)
        self.assertAlmostEqual(p['price_incl'], 110.0, places=2)

    def test_02_an_untaxed_product_reads_the_same_either_way(self):
        p = self._product(self._boot(), 'TX Water')
        self.assertAlmostEqual(p['price_excl'], 50.0, places=2)
        self.assertAlmostEqual(p['price_incl'], 50.0, places=2)

    def test_03_the_branch_setting_reaches_the_till(self):
        # It was already in the payload and nothing read it; assert it is still there
        # so the toggle has a starting point.
        self.assertIn(self._boot()['config'].get('iface_tax_included'),
                      ('total', 'subtotal'))

    def test_04_the_prices_are_odoo_s_own_arithmetic(self):
        """Not a browser-side multiplication: the same ``compute_all`` result.

        The comparison applies the BRANCH-company filter the endpoint applies. An
        earlier version of this test used ``taxes_id`` unfiltered and failed at
        125.00 vs 110.00, because product creation had attached another company's
        default sale tax alongside the one under test. The endpoint was right and the
        test was wrong — and re-deriving the same figure by a slightly different rule
        is exactly the bug that made a cart taxed at 10% get labelled "15%" earlier in
        this work.
        """
        b = self._boot()
        p = self._product(b, 'TX Plate')
        taxes = self.dish.taxes_id.filtered(
            lambda t: t.company_id == self.pos_config.company_id) or self.dish.taxes_id
        computed = taxes.compute_all(
            100.0, currency=self.pos_config.currency_id, quantity=1.0,
            product=self.dish)
        self.assertAlmostEqual(p['price_incl'], round(computed['total_included'], 2),
                               places=2)
        # And the branch's own tax is genuinely in play, so this is not a vacuous
        # comparison of two untaxed numbers.
        self.assertGreater(p['price_incl'], p['price_excl'])

    # -- the toggle on the till -------------------------------------------
    def test_10_the_till_can_switch_between_them(self):
        self.env['ir.config_parameter'].sudo().set_param(
            'mezze_bridge.default_branch_id', str(self.pos_config.id))
        self.browser_js('/mezze/pos?ws=register', r"""
            const $$ = (s) => Array.from(document.querySelectorAll(s));
            async function waitFor(fn, label, ms=20000){
              const t0 = Date.now();
              while (Date.now()-t0 < ms){ try { if (fn()) return true; } catch(e){}
                await new Promise(r=>setTimeout(r,120)); }
              throw new Error('timeout waiting for: ' + label);
            }
            function assert(c,m){ if(!c) throw new Error('assert failed: ' + m); }
            const tile = () => $$('.mz-tile').find(t => /TX Plate/.test(t.textContent));
            const shown = () => {
              const el = tile().querySelector('.mz-tile-price');
              return Number((el.textContent || '').replace(/[^0-9.]/g, ''));
            };
            (async () => {
                await waitFor(() => tile(), 'the menu');
                const before = shown();
                assert(before === 100 || before === 110,
                       'the tile shows neither figure: ' + before);

                const verb = $$('.mz-verb').find(v => /Prices (with|without) tax/.test(v.textContent));
                assert(verb, 'no Tax verb on the till');
                verb.click();
                await waitFor(() => shown() !== before, 'the price to switch');

                const after = shown();
                assert((before === 100 && after === 110) || (before === 110 && after === 100),
                       'the toggle produced neither figure: ' + before + ' -> ' + after);
                console.log('test successful');
            })().catch(e => { console.error(e.message || e); });
        """, login='admin')
