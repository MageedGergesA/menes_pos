# -*- coding: utf-8 -*-
"""Answering a question about a product without leaving the order.

``/products/info`` already existed and nothing in the product could reach it, so
"how many have we got left?" was still answered by a guess or by walking away from
the till. These drive the live Owl app, because the work here was the WIRING: a unit
test of the endpoint passed before this card existed and would pass if it were
deleted again.

The rule worth testing twice is the FINANCE gate. The endpoint withholds cost and
margin from a till, and the card must not quietly reintroduce them — not as a value
it computes locally, and not as an empty row that reads as "the shop does not know".
"""
from odoo.tests import tagged

from .common import MezzeHttpCase

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
const openInfo = async (pid) => {
  await waitFor(() => $('[data-info-id="' + pid + '"]'), 'the info control on the card');
  $('[data-info-id="' + pid + '"]').click();
  await waitFor(() => $('[data-testid="mz-product-info"]'), 'the info card');
  await waitFor(() => $('[data-testid="mz-pinfo-price"]')
                   || $('[data-testid="mz-pinfo-error"]'), 'the lookup to land');
};
"""


def _js(body):
    return _PRELUDE + "\n(async () => {\n" + body + "\n})().catch(e => { console.error(e.message || e); });"


@tagged('post_install', '-at_install', 'mezze_browser', 'mezze_pinfo_ui')
class TestProductInfoUi(MezzeHttpCase):
    fixture_profile = 'POS'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        env['ir.config_parameter'].sudo().set_param(
            'mezze_bridge.default_branch_id', str(cls.pos_config.id))
        cls.pos_sess = cls._open_session_for(cls.pos_config)
        # A STORABLE product, so "on hand" is a real quantity rather than a fiction.
        cls.bottle = env['product.product'].sudo().create({
            'name': 'PI Sparkling Water', 'available_in_pos': True,
            'is_storable': True, 'type': 'consu',
            'list_price': 12.0, 'standard_price': 5.0,
            # A menu item carries a POS category; the boot payload filters on it to
            # keep loyalty utility products out of the grid.
            'pos_categ_ids': [(6, 0, cls.product.pos_categ_ids.ids)]})
        cls.bottle.write({'taxes_id': [(5, 0, 0)]})
        env['stock.quant'].sudo().with_context(inventory_mode=True).create({
            'product_id': cls.bottle.id,
            'location_id': env.ref('stock.stock_location_stock').id,
            'inventory_quantity': 17.0,
        }).action_apply_inventory()
        # A second price list, so the card has something to say about elsewhere.
        cls.delivery_pl = env['product.pricelist'].sudo().create({
            'name': 'PI Delivery', 'currency_id': cls.pos_config.currency_id.id,
            'item_ids': [(0, 0, {'applied_on': '0_product_variant',
                                 'product_id': cls.bottle.id,
                                 'compute_price': 'fixed', 'fixed_price': 15.0})],
        })
        cls.pos_config.sudo().write({
            'use_pricelist': True,
            'available_pricelist_ids': [(4, cls.delivery_pl.id)],
        })
        env.flush_all()

    def test_01_every_card_offers_a_way_to_ask(self):
        self.browser_js('/mezze/pos?ws=register', _js(r"""
            await waitFor(() => $$('.mz-tile').length > 0, 'the catalogue');
            assert($$('[data-info-id]').length === $$('.mz-tile').length,
                   'not every product card can be asked about');
            ok();
        """), login='admin')

    def test_02_the_control_names_its_product(self):
        # A row of identical "Info" buttons is indistinguishable in a screen
        # reader's element list.
        self.browser_js('/mezze/pos?ws=register', _js(r"""
            await waitFor(() => $('[data-info-id="%d"]'), 'the card');
            const label = $('[data-info-id="%d"]').getAttribute('aria-label') || '';
            assert(/PI Sparkling Water/.test(label),
                   'the info control does not name its product: ' + label);
            ok();
        """ % (self.bottle.id, self.bottle.id)), login='admin')

    def test_03_the_card_answers_price_and_tax(self):
        self.browser_js('/mezze/pos?ws=register', _js(r"""
            await openInfo(%d);
            assert(!$('[data-testid="mz-pinfo-error"]'), 'the lookup failed');
            assert(/12/.test($('[data-testid="mz-pinfo-price"]').textContent),
                   'the price is not shown');
            assert($('[data-testid="mz-pinfo-tax"]').textContent.trim().length > 0,
                   'the tax line is blank');
            ok();
        """ % self.bottle.id), login='admin')

    def test_04_it_says_how_many_are_left(self):
        # THE question this card exists for.
        self.browser_js('/mezze/pos?ws=register', _js(r"""
            await openInfo(%d);
            const stock = $('[data-testid="mz-pinfo-stock"]');
            assert(stock, 'a stocked product does not show its stock');
            const dd = stock.querySelector('dd');
            assert(Number(dd.dataset.qty) === 17,
                   'wrong quantity on hand: ' + dd.dataset.qty);
            ok();
        """ % self.bottle.id), login='admin')

    def test_05_an_untracked_product_claims_no_stock(self):
        # Printing "0 left" for a dish nobody counts is a lie a cashier acts on.
        self.browser_js('/mezze/pos?ws=register', _js(r"""
            await openInfo(%d);
            assert(!$('[data-testid="mz-pinfo-stock"]'),
                   'an untracked product was given a stock figure');
            ok();
        """ % self.product.id), login='admin')

    def test_06_a_till_is_not_shown_the_cost(self):
        # The server withholds it; the card must not reintroduce it — neither as a
        # number it computes nor as an empty row implying missing data.
        self.browser_js('/mezze/pos?ws=register', _js(r"""
            await openInfo(%d);
            assert(!$('[data-testid="mz-pinfo-cost"]'), 'the till shows the cost price');
            assert(!$('[data-testid="mz-pinfo-margin"]'), 'the till shows the margin');
            // Not a bare /5\.00/ — that matches the delivery price of 15.00, which is
            // the till's own business and belongs on this card.
            const body = $('[data-testid="mz-product-info"]').textContent;
            assert(!/(^|[^\d])5\.00/.test(body),
                   'the cost leaked into the card body: ' + body);
            assert(!/Cost|Margin/.test(body), 'a finance label is drawn: ' + body);
            ok();
        """ % self.bottle.id), login='admin')

    def test_07_other_price_lists_are_listed(self):
        self.browser_js('/mezze/pos?ws=register', _js(r"""
            await openInfo(%d);
            const pls = $('[data-testid="mz-pinfo-pricelists"]');
            assert(pls, 'the other price list is not shown');
            assert(/15/.test(pls.textContent),
                   'the delivery price is missing: ' + pls.textContent);
            ok();
        """ % self.bottle.id), login='admin')

    def test_08_asking_does_not_disturb_the_order(self):
        # Anything that unwinds an in-progress order to answer a question will not
        # be used twice.
        self.browser_js('/mezze/pos?ws=register', _js(r"""
            await waitFor(() => $('.mz-tile'), 'the catalogue');
            $('.mz-tile').click();
            await waitFor(() => $$('.mz-line').length === 1, 'a line in the cart');
            const before = $$('.mz-line').length;
            await openInfo(%d);
            $('[data-testid="mz-pinfo-close"]').click();
            await waitFor(() => !$('[data-testid="mz-product-info"]'), 'the card closes');
            assert($$('.mz-line').length === before,
                   'the order changed while a question was asked');
            ok();
        """ % self.bottle.id), login='admin')
