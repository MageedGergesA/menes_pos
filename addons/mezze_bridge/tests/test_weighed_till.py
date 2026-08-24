# -*- coding: utf-8 -*-
"""Ringing up something sold by weight.

The data path for weighed products was already right and the till could not use it:
the pad refused the decimal point in Qty mode by design, so 0.4 kg of cheese could
not be entered at all. These drive the real Owl app, because that gap was invisible
to every server-side test — the endpoint accepted 0.4 happily, and nothing could
send it one.

Two of the assertions are about a money error rather than a feature:

* a weighed product must ASK for its weight when it is added. Leaving 1 behind does
  not mean "one of them", it means one kilogram at whatever a kilogram costs;
* a weighed line shows no ``+``. Tapping plus on 0.4 kg of cheese means a whole
  extra kilo, which is not what a cashier reaching for a plus sign is asking for.
"""
from odoo.tests import tagged

from .common import MezzeHttpCase

_PRELUDE = r"""
const $ = (s) => document.querySelector(s);
const $$ = (s) => Array.from(document.querySelectorAll(s));
const phase = () => ($('.mz-app') ? $('.mz-app').dataset.phase : null);
async function waitFor(fn, label, ms=20000){
  const t0 = Date.now();
  while (Date.now()-t0 < ms){ try { if (fn()) return true; } catch(e){} await new Promise(r=>setTimeout(r,120)); }
  throw new Error('timeout waiting for: ' + label + ' (phase=' + phase() + ')');
}
function assert(cond, msg){ if(!cond) throw new Error('assert failed: ' + msg); }
const ok = () => console.log('test successful');
const tile = (id) => $('.mz-tile[data-product-id="' + id + '"]');
// Owl renders on the next frame, so a buffer read straight after a click sees the
// value from BEFORE the keystroke. Every press waits for the paint.
const key = async (k) => {
  const b = $('[data-key="' + k + '"]'); assert(b, 'key ' + k); b.click();
  await new Promise(r => setTimeout(r, 80));
};
"""


def _js(body):
    return _PRELUDE + "\n(async () => {\n" + body + "\n})().catch(e => { console.error(e.message || e); });"


@tagged('post_install', '-at_install', 'mezze_browser', 'mezze_weigh_ui')
class TestWeighedTill(MezzeHttpCase):
    fixture_profile = 'POS'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        env['ir.config_parameter'].sudo().set_param(
            'mezze_bridge.default_branch_id', str(cls.pos_config.id))
        cls.pos_sess = cls._open_session_for(cls.pos_config)
        kg = env.ref('uom.product_uom_kgm')
        cls.cheese = env['product.product'].sudo().create({
            'name': 'WT Cheese', 'available_in_pos': True, 'to_weight': True,
            'uom_id': kg.id, 'list_price': 200.0, 'type': 'consu',
            'pos_categ_ids': [(6, 0, cls.product.pos_categ_ids.ids)]})
        cls.cheese.write({'taxes_id': [(5, 0, 0)]})
        cls.product.write({'available_in_pos': True, 'list_price': 40.0,
                           'taxes_id': [(5, 0, 0)]})
        env.flush_all()

    def test_01_adding_a_weighed_product_asks_for_its_weight(self):
        # Leaving 1 behind is not "one of them" — it is a kilogram, at whatever a
        # kilogram costs.
        self.browser_js('/mezze/pos', _js(r"""
            await waitFor(() => phase() === 'menu', 'register ready');
            await waitFor(() => tile(%d), 'the weighed product');
            tile(%d).click();
            await waitFor(() => $('[data-testid="mz-numpad"]'),
                          'the pad opens on its own for a weighed item');
            ok();
        """ % (self.cheese.id, self.cheese.id)), login='admin')

    def test_02_an_ordinary_product_is_not_interrupted(self):
        # Guard against fixing the weighed case by breaking every other sale.
        self.browser_js('/mezze/pos', _js(r"""
            await waitFor(() => phase() === 'menu', 'register ready');
            await waitFor(() => tile(%d), 'the ordinary product');
            tile(%d).click();
            await new Promise(r => setTimeout(r, 500));
            assert(!$('[data-testid="mz-numpad"]'),
                   'a countable product opened the pad');
            ok();
        """ % (self.product.id, self.product.id)), login='admin')

    def test_03_the_pad_takes_a_decimal_for_a_weight(self):
        # THE gap. This keystroke was refused, so the product could not be sold.
        self.browser_js('/mezze/pos', _js(r"""
            await waitFor(() => phase() === 'menu', 'register ready');
            tile(%d).click();
            await waitFor(() => $('[data-testid="mz-numpad"]'), 'the pad');
            await key('0'); await key('.'); await key('4');
            assert($('[data-testid="mz-numpad-buffer"]').textContent.trim() === '0.4',
                   'the decimal was refused: '
                   + $('[data-testid="mz-numpad-buffer"]').textContent);
            $('[data-testid="mz-numpad-apply"]').click();
            await new Promise(r => setTimeout(r, 300));
            assert($('[data-testid="mz-line-weight"]'), 'the line shows a weight');
            assert(Number($('[data-testid="mz-line-weight"]').dataset.qty) === 0.4,
                   'the weight did not reach the line');
            ok();
        """ % self.cheese.id), login='admin')

    def test_04_a_countable_line_still_refuses_one(self):
        # The rule did not go away — it became the product's decision.
        self.browser_js('/mezze/pos', _js(r"""
            await waitFor(() => phase() === 'menu', 'register ready');
            tile(%d).click();
            await new Promise(r => setTimeout(r, 400));
            await waitFor(() => $('[data-testid="mz-line-numpad"]'), 'the pad control');
            $('[data-testid="mz-line-numpad"]').click();
            await waitFor(() => $('[data-testid="mz-numpad"]'), 'the pad');
            await key('1'); await key('.'); await key('5');
            assert($('[data-testid="mz-numpad-buffer"]').textContent.trim() === '15',
                   'a decimal got into a COUNT: '
                   + $('[data-testid="mz-numpad-buffer"]').textContent);
            ok();
        """ % self.product.id), login='admin')

    def test_05_the_pad_names_the_unit(self):
        # "Qty: 0.4" reads as a mistake; "Weight (kg)" reads as a scale.
        self.browser_js('/mezze/pos', _js(r"""
            await waitFor(() => phase() === 'menu', 'register ready');
            tile(%d).click();
            await waitFor(() => $('[data-testid="mz-numpad"]'), 'the pad');
            const qty = $('[data-mode="qty"]');
            assert(/kg/i.test(qty.textContent),
                   'the mode does not name the unit: ' + qty.textContent);
            ok();
        """ % self.cheese.id), login='admin')

    def test_06_a_weighed_line_has_no_plus(self):
        # "+" on 0.4 kg of cheese means a whole extra kilogram.
        self.browser_js('/mezze/pos', _js(r"""
            await waitFor(() => phase() === 'menu', 'register ready');
            tile(%d).click();
            await waitFor(() => $('[data-testid="mz-numpad"]'), 'the pad');
            await key('0'); await key('.'); await key('5');
            $('[data-testid="mz-numpad-apply"]').click();
            await new Promise(r => setTimeout(r, 300));
            $('[data-testid="mz-numpad-close"]').click();
            await new Promise(r => setTimeout(r, 200));
            const line = $('.mz-line');
            assert(!line.querySelector('.mz-stepper'),
                   'a weighed line offers a stepper');
            assert(/kg/.test(line.textContent), 'the line does not state its unit');
            ok();
        """ % self.cheese.id), login='admin')

    def test_07_no_scale_means_no_weigh_button(self):
        # A control that reports "no scale" the first time it is pressed has taught
        # the cashier not to press it again.
        self.browser_js('/mezze/pos', _js(r"""
            await waitFor(() => phase() === 'menu', 'register ready');
            tile(%d).click();
            await waitFor(() => $('[data-testid="mz-numpad"]'), 'the pad');
            assert(!$('[data-testid="mz-numpad-weigh"]'),
                   'a branch with no scale offered to weigh');
            ok();
        """ % self.cheese.id), login='admin')

    def test_08_the_weight_reaches_the_database(self):
        self.browser_js('/mezze/pos', _js(r"""
            await waitFor(() => phase() === 'menu', 'register ready');
            tile(%d).click();
            await waitFor(() => $('[data-testid="mz-numpad"]'), 'the pad');
            await key('0'); await key('.'); await key('4');
            $('[data-testid="mz-numpad-apply"]').click();
            await new Promise(r => setTimeout(r, 300));
            $('[data-testid="mz-numpad-close"]').click();
            await waitFor(() => $$('.mz-verb').some(v => /Park/i.test(v.textContent)),
                          'the Park verb');
            $$('.mz-verb').find(v => /Park/i.test(v.textContent)).click();
            await new Promise(r => setTimeout(r, 1200));
            ok();
        """ % self.cheese.id), login='admin')
        self.env.invalidate_all()
        line = self.env['pos.order.line'].sudo().search(
            [('product_id', '=', self.cheese.id)], order='id desc', limit=1)
        self.assertTrue(line, 'no weighed line was written at all')
        self.assertAlmostEqual(line.qty, 0.4, places=3,
                               msg='the measurement was rounded on the way in')
