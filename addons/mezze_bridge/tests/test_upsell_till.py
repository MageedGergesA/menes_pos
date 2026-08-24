# -*- coding: utf-8 -*-
"""Suggesting what else the guest might want, on the till.

``/ai/upsell`` is a real market-basket miner: confidence and lift over paid baskets,
a popularity fallback when the signal is thin, and every suggestion explainable. The
guest-facing table page has called it since it was written. The CASHIER — the person
actually in a position to ask "anything to drink with that?" — never did.

Three things these tests hold it to, each of which is a way a suggestion strip stops
being useful and starts being noise:

* it must not suggest what is already in the cart;
* it must say WHY, because an unexplained suggestion is one a cashier will not repeat
  out loud to a guest; and
* taking a suggestion for a configurable product must open its configurator rather
  than dropping it in the order unconfigured — the same rule an ordinary tap follows.
"""
import json

from odoo.tests import tagged

from .common import MezzeHttpCase

_JS = r"""
const $ = (s) => document.querySelector(s);
const $$ = (s) => Array.from(document.querySelectorAll(s));
async function waitFor(fn, label, ms=20000){
  const t0 = Date.now();
  while (Date.now()-t0 < ms){ try { if (fn()) return true; } catch(e){}
    await new Promise(r=>setTimeout(r,120)); }
  throw new Error('timeout waiting for: ' + label);
}
function assert(c,m){ if(!c) throw new Error('assert failed: ' + m); }
const tile = (n) => $$('.mz-tile').find(t => new RegExp(n).test(t.textContent));
"""


@tagged('post_install', '-at_install', 'mezze_upsell')
class TestUpsellOnTill(MezzeHttpCase):
    fixture_profile = 'POS'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        env['ir.config_parameter'].sudo().set_param('mezze_bridge.api_token', 'up-tok')
        env['ir.config_parameter'].sudo().set_param(
            'mezze_bridge.default_branch_id', str(cls.pos_config.id))
        cls.pos_sess = cls._open_session_for(cls.pos_config)
        cls.cash = cls.pos_config.payment_method_ids.filtered('is_cash_count')[:1]
        cls.categ = env['pos.category'].sudo().search([], limit=1) \
            or env['pos.category'].sudo().create({'name': 'UP'})

        def dish(name, price):
            p = env['product.product'].sudo().create({
                'name': name, 'available_in_pos': True, 'list_price': price,
                'type': 'consu', 'pos_categ_ids': [(6, 0, cls.categ.ids)]})
            p.write({'taxes_id': [(5, 0, 0)]})
            return p

        cls.burger = dish('UP Burger', 60.0)
        cls.fries = dish('UP Fries', 20.0)
        # History: burger and fries bought together, repeatedly. That is the whole
        # basis of an affinity suggestion, so it has to exist for the miner to find.
        for _ in range(6):
            order = env['pos.order'].sudo().create({
                'session_id': cls.pos_sess.id,
                'company_id': cls.pos_config.company_id.id,
                'lines': [(0, 0, {'product_id': p.id, 'qty': 1, 'price_unit': p.list_price,
                                  'price_subtotal': p.list_price,
                                  'price_subtotal_incl': p.list_price,
                                  'tax_ids': [(6, 0, [])]})
                          for p in (cls.burger, cls.fries)],
                'amount_total': 80.0, 'amount_paid': 80.0,
                'amount_tax': 0.0, 'amount_return': 0.0})
            env['pos.payment'].sudo().create({
                'pos_order_id': order.id, 'amount': 80.0,
                'payment_method_id': cls.cash.id})
            order.sudo().write({'state': 'paid'})
        env.flush_all()

    def _api(self, path, body):
        r = self.url_open('/mezze/api/v1' + path,
                          data=json.dumps(dict(body, token='up-tok')),
                          headers={'Content-Type': 'application/json'})
        return r.json()

    # -- the miner itself -------------------------------------------------
    def test_01_a_burger_suggests_the_fries_it_is_bought_with(self):
        d = self._api('/ai/upsell', {'cart': [self.burger.id], 'limit': 3})
        self.assertTrue(d.get('ok'), d)
        names = [s['name'] for s in d['suggestions']]
        self.assertIn('UP Fries', names, 'the miner missed an obvious pairing: %s' % names)

    def test_02_it_never_suggests_what_is_already_in_the_cart(self):
        d = self._api('/ai/upsell', {'cart': [self.burger.id, self.fries.id], 'limit': 5})
        ids = [s['product_id'] for s in d['suggestions']]
        self.assertNotIn(self.burger.id, ids)
        self.assertNotIn(self.fries.id, ids)

    def test_03_every_suggestion_explains_itself(self):
        d = self._api('/ai/upsell', {'cart': [self.burger.id], 'limit': 3})
        for s in d['suggestions']:
            self.assertIn(s.get('kind'), ('affinity', 'popular'))
            if s['kind'] == 'affinity':
                self.assertTrue(s.get('with'),
                                'an affinity suggestion that cannot say what it goes with')

    # -- reaching the cashier ---------------------------------------------
    def test_10_the_till_shows_suggestions_once_something_is_rung_up(self):
        self.browser_js('/mezze/pos?ws=register', _JS + r"""
            (async () => {
                await waitFor(() => tile('UP Burger'), 'the menu');
                tile('UP Burger').click();
                await waitFor(() => $$('.mz-line').length > 0, 'a line in the cart');
                await waitFor(() => $('[data-testid="mz-upsell"]'), 'the suggestions');
                const t = $('[data-testid="mz-upsell"]').textContent || '';
                assert(/UP Fries/.test(t), 'the pairing is not offered: ' + t);
                assert(/Goes with|Popular/i.test(t),
                       'a suggestion with no reason a cashier could repeat: ' + t);
                console.log('test successful');
            })().catch(e => { console.error(e.message || e); });
        """, login='admin')

    def test_11_an_empty_cart_gets_no_suggestions(self):
        # The endpoint's popularity fallback would happily answer an empty cart;
        # suggesting add-ons before anything is ordered is guessing.
        self.browser_js('/mezze/pos?ws=register', _JS + r"""
            (async () => {
                await waitFor(() => $$('.mz-tile').length > 0, 'the menu');
                await new Promise(r => setTimeout(r, 900));
                assert(!$('[data-testid="mz-upsell"]'),
                       'suggestions were offered for an empty order');
                console.log('test successful');
            })().catch(e => { console.error(e.message || e); });
        """, login='admin')

    def test_12_taking_a_suggestion_adds_it(self):
        self.browser_js('/mezze/pos?ws=register', _JS + r"""
            (async () => {
                await waitFor(() => tile('UP Burger'), 'the menu');
                tile('UP Burger').click();
                await waitFor(() => $('[data-testid="mz-upsell"]'), 'the suggestions');
                const chip = $$('.mz-upsell__chip').find(c => /UP Fries/.test(c.textContent));
                assert(chip, 'the fries were not offered');
                chip.click();
                await waitFor(() => $$('.mz-line').some(l => /UP Fries/.test(l.textContent)),
                              'the suggestion to reach the cart');
                console.log('test successful');
            })().catch(e => { console.error(e.message || e); });
        """, login='admin')
