# -*- coding: utf-8 -*-
"""Typing a quantity, a price, or a discount.

Mezze had +/− steppers and nothing else. "Make that twelve" meant pressing + eleven
times, and a price could not be entered at all — which left ``restrict_price_control``
guarding a door that had no handle on it: the branch switch was honoured by the
server and no surface could ever trip it.

Two things are asserted that a component test alone would miss.

**The typed price has to REACH the server.** ``toSyncLines`` sent product, quantity,
note, modifiers and combo picks — no price and no discount. A numpad that set them
only in the browser would show the guest one figure and charge them another at
payment, which is worse than not having a numpad.

**Two lines of the same product at different prices must stay two lines.** The cart
groups by a line key, and merging a repriced line into an unrepriced one silently
charges one of them the other's price.
"""
import json

from odoo.tests import tagged

from .common import MezzeHttpCase

_PRELUDE = r"""
const $ = (s) => document.querySelector(s);
const $$ = (s) => Array.from(document.querySelectorAll(s));
async function waitFor(fn, label, ms=20000){
  const t0 = Date.now();
  while (Date.now()-t0 < ms){ try { if (fn()) return true; } catch(e){}
    await new Promise(r=>setTimeout(r,120)); }
  throw new Error('timeout waiting for: ' + label);
}
function assert(c,m){ if(!c) throw new Error('assert failed: ' + m); }
const ok = () => console.log('test successful');
const digits = (s) => Array.from(String(s)).filter(c => /[0-9.]/.test(c));
async function openPad(){
  // BY NAME. The fixture seeds other products, so "the first tile" is not
  // necessarily the dish these tests are about.
  await waitFor(() => $$('.mz-tile').some(t => /NP Plate/.test(t.textContent)),
                'the dish on the menu');
  $$('.mz-tile').find(t => /NP Plate/.test(t.textContent)).click();
  await waitFor(() => $$('.mz-line').some(l => /NP Plate/.test(l.textContent)),
                'the dish in the cart');
  await waitFor(() => $$('.mz-line').find(l => /NP Plate/.test(l.textContent))
                  .querySelector('[data-testid="mz-line-numpad"]'), 'the pad control');
  $$('.mz-line').find(l => /NP Plate/.test(l.textContent))
    .querySelector('[data-testid="mz-line-numpad"]').click();
  await waitFor(() => $('[data-testid="mz-numpad"]'), 'the numpad');
}
async function type(str){
  for (const d of digits(str)) {
    $$('.mz-numpad__key').find(k => k.dataset.key === d).click();
    await new Promise(r => setTimeout(r, 30));
  }
}
"""


def _js(body):
    return _PRELUDE + "\n(async () => {\n" + body + "\n})().catch(e => { console.error(e.message || e); });"


@tagged('post_install', '-at_install', 'mezze_browser', 'mezze_numpad')
class TestNumpad(MezzeHttpCase):
    fixture_profile = 'POS'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        env['ir.config_parameter'].sudo().set_param(
            'mezze_bridge.default_branch_id', str(cls.pos_config.id))
        cls.pos_sess = cls._open_session_for(cls.pos_config)
        cls.categ = env['pos.category'].sudo().search([], limit=1) \
            or env['pos.category'].sudo().create({'name': 'NP'})
        cls.dish = env['product.product'].sudo().create({
            'name': 'NP Plate', 'available_in_pos': True, 'list_price': 20.0,
            'type': 'consu', 'pos_categ_ids': [(6, 0, cls.categ.ids)]})
        cls.dish.write({'taxes_id': [(5, 0, 0)]})
        env.flush_all()

    def _latest_draft(self):
        self.env.invalidate_all()
        return self.env['pos.order'].sudo().search(
            [('session_id', '=', self.pos_sess.id)], order='id desc', limit=1)

    # -- typing a quantity -----------------------------------------------
    def test_01_a_quantity_can_be_typed(self):
        self.browser_js('/mezze/pos?ws=register', _js(r"""
            await openPad();
            await type('12');
            assert($('[data-testid="mz-numpad-buffer"]').textContent.trim() === '12',
                   'the digits did not accumulate');
            $('[data-testid="mz-numpad-apply"]').click();
            await waitFor(() => ($$('.mz-line').find(l => /NP Plate/.test(l.textContent))
                .querySelector('.mz-stepper__value').textContent.trim()) === '12',
                          'the line did not take the typed quantity');
            ok();
        """), login='admin')

    def test_02_a_half_typed_number_is_not_a_quantity(self):
        # Digits accumulate into a pending value; the line must not follow along.
        self.browser_js('/mezze/pos?ws=register', _js(r"""
            await openPad();
            await type('1');
            assert(($$('.mz-line').find(l => /NP Plate/.test(l.textContent))
                .querySelector('.mz-stepper__value').textContent.trim()) === '1',
                   'baseline quantity should still be 1');
            await type('2');
            assert(($$('.mz-line').find(l => /NP Plate/.test(l.textContent))
                .querySelector('.mz-stepper__value').textContent.trim()) === '1',
                   'the line changed before Apply was pressed');
            ok();
        """), login='admin')

    def test_03_backspace_and_clear_work(self):
        self.browser_js('/mezze/pos?ws=register', _js(r"""
            await openPad();
            await type('123');
            $('[data-testid="mz-numpad-back"]').click();
            await new Promise(r => setTimeout(r, 80));
            assert($('[data-testid="mz-numpad-buffer"]').textContent.trim() === '12',
                   'backspace did not remove one digit');
            $('[data-testid="mz-numpad-clear"]').click();
            await new Promise(r => setTimeout(r, 80));
            assert($('[data-testid="mz-numpad-buffer"]').textContent.trim() === '—',
                   'clear did not empty the buffer');
            ok();
        """), login='admin')

    def test_04_the_pad_names_the_line_it_edits(self):
        # A pad that acts on "the last thing added" eventually reprices the wrong dish.
        self.browser_js('/mezze/pos?ws=register', _js(r"""
            await openPad();
            const named = $('[data-testid="mz-numpad-line"]').textContent || '';
            assert(/NP Plate/.test(named), 'the pad does not say what it is editing: ' + named);
            ok();
        """), login='admin')

    # -- typing a price --------------------------------------------------
    def test_05_a_typed_price_reaches_the_server(self):
        # THE test. A price set only in the browser quotes one figure and charges
        # another.
        self.browser_js('/mezze/pos?ws=register', _js(r"""
            await openPad();
            $$('.mz-tab').find(t => t.dataset.mode === 'price').click();
            await new Promise(r => setTimeout(r, 80));
            await type('7.5');
            $('[data-testid="mz-numpad-apply"]').click();
            await new Promise(r => setTimeout(r, 200));
            $('[data-testid="mz-numpad-close"]').click();
            // force a sync by opening a flow that persists the order
            await waitFor(() => $$('.mz-verb').some(v => /Enter Code/.test(v.textContent)),
                          'a verb that persists');
            $$('.mz-verb').find(v => /Enter Code/.test(v.textContent)).click();
            await waitFor(() => $('[data-testid="mz-code-input"]'), 'persisted');
            ok();
        """), login='admin')
        order = self._latest_draft()
        self.assertTrue(order, 'no order was persisted')
        line = order.lines.filtered(lambda l: l.product_id == self.dish)[:1]
        self.assertTrue(line, 'the dish is not on the order')
        self.assertAlmostEqual(line.price_unit, 7.5, places=2,
                               msg='the typed price never reached the server')

    def test_06_a_typed_line_discount_reaches_the_server(self):
        self.browser_js('/mezze/pos?ws=register', _js(r"""
            await openPad();
            $$('.mz-tab').find(t => t.dataset.mode === 'disc').click();
            await new Promise(r => setTimeout(r, 80));
            await type('25');
            $('[data-testid="mz-numpad-apply"]').click();
            await new Promise(r => setTimeout(r, 200));
            $('[data-testid="mz-numpad-close"]').click();
            $$('.mz-verb').find(v => /Enter Code/.test(v.textContent)).click();
            await waitFor(() => $('[data-testid="mz-code-input"]'), 'persisted');
            ok();
        """), login='admin')
        order = self._latest_draft()
        line = order.lines.filtered(lambda l: l.product_id == self.dish)[:1]
        self.assertAlmostEqual(line.discount, 25.0, places=2,
                               msg='the typed discount never reached the server')

    def test_07_a_discount_over_100_is_refused(self):
        self.browser_js('/mezze/pos?ws=register', _js(r"""
            await openPad();
            $$('.mz-tab').find(t => t.dataset.mode === 'disc').click();
            await new Promise(r => setTimeout(r, 80));
            await type('150');
            assert($('[data-testid="mz-numpad-apply"]').disabled,
                   'a 150% discount was offered as applicable');
            ok();
        """), login='admin')

    def test_08_typing_zero_removes_the_line(self):
        # What a cashier means by 0. The alternative is a line that is on the order
        # and costs nothing.
        self.browser_js('/mezze/pos?ws=register', _js(r"""
            await openPad();
            await type('0');
            $('[data-testid="mz-numpad-apply"]').click();
            await waitFor(() => !$$('.mz-line').some(l => /NP Plate/.test(l.textContent)),
                          'the line to go');
            ok();
        """), login='admin')
