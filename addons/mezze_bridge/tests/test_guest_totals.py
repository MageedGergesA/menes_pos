# -*- coding: utf-8 -*-
"""The guest is quoted the BRANCH's arithmetic, not the browser's.

``shop.html`` and ``qr.html`` each computed their own totals in JavaScript::

    function withTax(base){ var svc=base*0.12; return base+svc+(base+svc)*0.14; }
    var svc=sub*0.12, vat=(sub+svc)*0.14;

Both rates, and the currency, were written into the page source. ``qr.html`` went
further and *named* them on screen — "Service 12%", "VAT 14%" — so a branch on any
other tax regime showed a paying customer a wrong number under a wrong label, in a
currency it might not trade in. ``shop.html`` also printed that tax-inclusive figure
on the row captioned "Subtotal".

None of it was driven by configuration, so none of it moved when the configuration
did. ``/shop/quote`` — the branch's pricelist, its taxes, its fiscal position, and
the same engine the kiosk already used — was already there.

Two properties are asserted, because either alone can pass while the guest is still
lied to:

* the SOURCE no longer contains a rate or a currency it could fall back on, and
* what the page RENDERS equals what the server says, on a branch whose tax is
  deliberately not 12/14.

The second is the one that matters, and it needs a browser: the endpoint was correct
before this change and stayed correct throughout — the defect was entirely in who
was trusted to do the arithmetic.
"""
import json
import os
import re

from odoo.tests import tagged

from .common import MezzeHttpCase

STORE = 'guesttotals'
STATIC = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static')

_PRELUDE = r"""
const $ = (s) => document.querySelector(s);
const $$ = (s) => Array.from(document.querySelectorAll(s));
async function waitFor(fn, label, ms=20000){
  const t0 = Date.now();
  while (Date.now()-t0 < ms){ try { if (fn()) return true; } catch(e){} await new Promise(r=>setTimeout(r,120)); }
  throw new Error('timeout waiting for: ' + label);
}
function assert(cond, msg){ if(!cond) throw new Error('assert failed: ' + msg); }
const ok = () => console.log('test successful');
const money = (s) => Number(String(s||'').replace(/[^0-9.]/g,'')) || 0;
"""


def _js(body):
    return _PRELUDE + "\n(async () => {\n" + body + "\n})().catch(e => { console.error(e.message || e); });"


class GuestTotalsFixture(MezzeHttpCase):
    # RESTAURANT: the table-menu test needs a table, and skipped without one.
    fixture_profile = 'RESTAURANT'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        icp = env['ir.config_parameter'].sudo()
        icp.set_param('mezze_bridge.store_token_%s' % cls.pos_config.id, STORE)

        # A tax that is neither 12 nor 14, so the old hardcoded arithmetic cannot
        # coincidentally agree with the branch's own.
        cls.tax = env['account.tax'].sudo().create({
            'name': 'GT Tax 10%', 'amount': 10.0, 'amount_type': 'percent',
            'type_tax_use': 'sale', 'price_include_override': 'tax_excluded',
            'company_id': cls.pos_config.company_id.id,
        })
        cls.categ = env['pos.category'].sudo().search([], limit=1) \
            or env['pos.category'].sudo().create({'name': 'GT'})
        cls.dish = env['product.product'].sudo().create({
            'name': 'GT Plate', 'available_in_pos': True, 'list_price': 100.0,
            'pos_categ_ids': [(6, 0, cls.categ.ids)], 'type': 'consu',
            'taxes_id': [(6, 0, cls.tax.ids)],
        })
        # A second product that attracts NO tax at all — the branch that charges
        # nothing must be quoted nothing, not a polite 0.00 row.
        cls.untaxed = env['product.product'].sudo().create({
            'name': 'GT Free Water', 'available_in_pos': True, 'list_price': 50.0,
            'pos_categ_ids': [(6, 0, cls.categ.ids)], 'type': 'consu',
        })
        cls.untaxed.write({'taxes_id': [(5, 0, 0)]})
        cls.pos_sess = cls._open_session_for(cls.pos_config)   # the storefront is "open"
        env.flush_all()

    def _api(self, path, body):
        r = self.url_open('/mezze/api/v1' + path, data=json.dumps(dict(body, store=STORE)),
                          headers={'Content-Type': 'application/json'})
        return r.json()

    def _read(self, name):
        with open(os.path.join(STATIC, name), encoding='utf-8') as fh:
            return fh.read()

    def _code(self, name):
        """The file with its comments removed.

        These guards ask what the page DOES. The comment explaining why the hardcoded
        rates were removed necessarily quotes them, and a guard that cannot tell code
        from prose would force the fix to be documented in vaguer terms than it
        deserves.
        """
        src = self._read(name)
        src = re.sub(r'/\*.*?\*/', ' ', src, flags=re.S)        # JS + CSS block
        src = re.sub(r'<!--.*?-->', ' ', src, flags=re.S)        # HTML
        src = re.sub(r'(?m)^\s*//.*$', ' ', src)                 # whole-line JS
        return src

    def _shop_url(self):
        return '/mezze_bridge/static/shop.html?store=%s' % STORE


# =====================================================================
@tagged('post_install', '-at_install', 'mezze_guest_totals')
class TestGuestTotalsSource(GuestTotalsFixture):
    """No rate and no currency the page could fall back on."""

    # The exact shapes that were there. Written as patterns rather than a blanket
    # ban on the digits, so an unrelated 0.12 somewhere in the file cannot make this
    # fail for the wrong reason.
    _RATE_PATTERNS = [
        r'\*\s*0\.12\b',
        r'\*\s*0\.14\b',
        r'\bsvc\s*=\s*[a-z]+\s*\*',
        r'function\s+withTax',
    ]

    def test_01_no_invented_tax_rate_in_the_storefront(self):
        src = self._code('shop.html')
        for pat in self._RATE_PATTERNS:
            self.assertFalse(
                re.search(pat, src),
                'shop.html still computes tax in the browser (%r). The branch prices '
                'the cart via /shop/quote.' % pat)

    def test_02_no_invented_tax_rate_on_the_table_page(self):
        src = self._code('qr.html')
        for pat in self._RATE_PATTERNS:
            self.assertFalse(
                re.search(pat, src),
                'qr.html still computes tax in the browser (%r).' % pat)

    def test_03_no_hardcoded_currency_on_the_table_page(self):
        # Every price on this page used to be prefixed with a literal "EGP".
        src = self._code('qr.html')
        self.assertNotIn(
            'EGP', src,
            'qr.html still hardcodes a currency; it must label money with the '
            "branch's own currency from /qr/menu or /shop/quote.")

    def test_04_no_rate_is_named_in_a_label(self):
        # "Service 12%" / "VAT 14%" were shown to the guest as fact.
        for name in ('qr.html', 'shop.html'):
            src = self._code(name)
            for bad in ('Service 12%', 'VAT 14%', '١٢٪', '١٤٪'):
                self.assertNotIn(bad, src,
                                 '%s names a tax rate in a label: %r' % (name, bad))

    def test_05_both_pages_ask_the_server(self):
        for name in ('qr.html', 'shop.html'):
            self.assertIn("'/shop/quote'", self._code(name),
                          '%s does not price its cart on the server' % name)


# =====================================================================
@tagged('post_install', '-at_install', 'mezze_guest_totals')
class TestGuestTotalsEndpoint(GuestTotalsFixture):
    """What the branch actually charges."""

    def test_10_quote_uses_the_branch_tax_not_twelve_and_fourteen(self):
        d = self._api('/shop/quote', {'lines': [{'product_id': self.dish.id, 'qty': 1}]})
        self.assertTrue(d.get('ok'), d)
        money = d['money']
        self.assertAlmostEqual(money['subtotal'], 100.0, places=2)
        self.assertAlmostEqual(money['tax'], 10.0, places=2)
        self.assertAlmostEqual(money['total'], 110.0, places=2)
        # what the browser used to print for the same cart
        self.assertNotAlmostEqual(money['total'], 127.68, places=2)

    def test_11_a_branch_with_no_tax_is_quoted_no_tax(self):
        d = self._api('/shop/quote', {'lines': [{'product_id': self.untaxed.id, 'qty': 2}]})
        self.assertTrue(d.get('ok'), d)
        self.assertAlmostEqual(d['money']['tax'], 0.0, places=2)
        self.assertAlmostEqual(d['money']['total'], 100.0, places=2)
        self.assertFalse(d.get('tax_label'),
                         'a branch that charges no tax must not be given a tax name')

    def test_12_the_tax_row_is_named_by_the_tax_that_applied(self):
        d = self._api('/shop/quote', {'lines': [{'product_id': self.dish.id, 'qty': 1}]})
        self.assertEqual(d.get('tax_label'), 'GT Tax 10%')

    def test_13_the_quote_carries_the_branch_currency(self):
        d = self._api('/shop/quote', {'lines': [{'product_id': self.dish.id, 'qty': 1}]})
        # A guest surface labels money the way the till does — the shop's
        # configured symbol. Payment payloads keep the ISO code; that split is
        # asserted in test_currency_and_initials.
        self.assertEqual(d.get('currency'), self.pos_config.currency_id.symbol
                         or self.pos_config.currency_id.name)

    def test_14_the_table_menu_names_the_currency(self):
        """qr.html labels every price from its first paint and only had the id before.

        This test had never run once. It read the QR credential from
        ``ir.config_parameter['mezze_bridge.qr_secret_<id>']`` — a key nothing in the
        product ever writes — so the call was always refused and the test always
        skipped itself. The real credential is the TABLE's own ``mezze_qr_token``,
        which is what ``_qr_resolve`` compares against.
        """
        table = self.env['restaurant.table'].sudo().search(
            [('floor_id.pos_config_ids', 'in', self.pos_config.ids)], limit=1)
        self.assertTrue(table, 'the restaurant fixture provides a table')
        qr = table._mezze_ensure_qr_token()
        d = self._api('/qr/menu', {'table_id': table.id, 'qr': qr})
        self.assertTrue(d.get('ok'), d)
        self.assertEqual(d.get('currency'), self.pos_config.currency_id.symbol
                         or self.pos_config.currency_id.name)

    def test_15_the_table_menu_refuses_a_wrong_qr_token(self):
        # The (table, token) pair IS the phone's only credential; if the wrong token
        # opened the menu, every table's menu would be readable from any QR code.
        table = self.env['restaurant.table'].sudo().search(
            [('floor_id.pos_config_ids', 'in', self.pos_config.ids)], limit=1)
        table._mezze_ensure_qr_token()
        d = self._api('/qr/menu', {'table_id': table.id, 'qr': 'not-the-token'})
        self.assertFalse(d.get('ok'), 'a wrong QR token opened the table menu')


# =====================================================================
@tagged('post_install', '-at_install', 'mezze_browser', 'mezze_guest_totals')
class TestGuestTotalsBrowser(GuestTotalsFixture):
    """What the guest is actually shown.

    The endpoint was already right before this change; the defect was that the page
    did not ask it. Only a browser can tell the difference.
    """

    def test_20_the_storefront_shows_the_branchs_total(self):
        self.browser_js(self._shop_url(), _js(r"""
            await waitFor(() => $$('.card, .pcard, [data-pid]').length > 0
                             || $$('button').some(b => /GT Plate/.test(b.textContent)), 'menu');
            const add = $$('button').find(b => /GT Plate/.test(b.textContent))
                     || $$('[data-pid]').find(e => /GT Plate/.test(e.textContent));
            assert(add, 'the taxed dish is on the menu');
            add.click();
            // The line-sum paints immediately; the branch's total arrives with the
            // quote. Wait for the SERVER's answer, or this races its own placeholder.
            await waitFor(() => money(($('#cbtot')||{}).textContent) > 100.5,
                          'the branch total to arrive from /shop/quote');
            const shown = money($('#cbtot').textContent);
            // 100 + the branch's own 10% — NOT 100 * 1.2768, which is what the page
            // used to print from its own hardcoded rates.
            assert(Math.abs(shown - 110) < 0.51,
                   'storefront total should be the branch 110, got ' + shown);
            assert(Math.abs(shown - 127.68) > 0.51,
                   'storefront is still using the hardcoded 12% + 14%');
            ok();
        """), login=None)

    def test_21_subtotal_means_subtotal(self):
        # The tax-inclusive figure used to be printed on the "Subtotal" row.
        self.browser_js(self._shop_url(), _js(r"""
            await waitFor(() => $$('button').some(b => /GT Plate/.test(b.textContent)), 'menu');
            $$('button').find(b => /GT Plate/.test(b.textContent)).click();
            await waitFor(() => money(($('#cbtot')||{}).textContent) > 100.5, 'the branch total');
            const open = $('#cartopen'); if (open) open.click();
            await new Promise(r => setTimeout(r, 250));
            const co = $$('button').find(b => /Checkout|إتمام/.test(b.textContent));
            if (co) co.click();
            await waitFor(() => money(($('#co-sub')||{}).textContent) > 0, 'a checkout subtotal');
            const sub = money($('#co-sub').textContent);
            const tot = money($('#co-total').textContent);
            assert(Math.abs(sub - 100) < 0.51, 'Subtotal must be the subtotal, got ' + sub);
            assert(tot > sub, 'the total must exceed the subtotal when tax applies');
            ok();
        """), login=None)
