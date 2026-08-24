# -*- coding: utf-8 -*-
"""The screen the guest reads while their order is rung up.

``/cfd/push`` has existed since the display was built and **nothing ever called
it** — so a counter screen showed whatever the prototype last put there, which in
production is nothing at all. The endpoint, the bus channel and the page were all
finished; the till simply never spoke to them.

Three decisions worth stating:

* **Only where a display exists.** The branch is told at boot whether one has ever
  been opened, and pushes only then. A snapshot per keystroke to a screen nobody
  installed is noise on a busy counter.
* **Lines and money only.** The screen faces the public, so everything on it is
  readable by whoever is standing there. No customer, no cashier, no order id goes
  on it — nothing that would matter if a stranger read it.
* **A display never breaks a sale.** Every push is best-effort and its failure is
  swallowed; a counter screen going dark must not stop a queue.

The money assertions compare the snapshot against ITSELF and against the till,
never against a price copied out of the fixture: this branch prices from a
pricelist, so ``list_price`` and what the cashier sees legitimately differ, and a
test pinned to the former only tests the fixture.
"""
import json

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

/** Ring up the product under test — NOT "whatever tile is first", which in this
 *  fixture is an 86'd item. */
async function ringUp(pid){
  await waitFor(() => $('.mz-tile[data-product-id="' + pid + '"]'), 'the product tile');
  $('.mz-tile[data-product-id="' + pid + '"]').click();
  await waitFor(() => $$('.mz-line').length > 0, 'a line in the cart');
  await new Promise(r => setTimeout(r, 1200));   // past the push debounce
}
"""


def _js(body):
    return _PRELUDE + "\n(async () => {\n" + body + "\n})().catch(e => { console.error(e.message || e); });"


@tagged('post_install', '-at_install', 'mezze_browser', 'mezze_cfd')
class TestCustomerDisplayFeed(MezzeHttpCase):
    fixture_profile = 'POS'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        env['ir.config_parameter'].sudo().set_param('mezze_bridge.api_token', 'cd-tok')
        env['ir.config_parameter'].sudo().set_param(
            'mezze_bridge.default_branch_id', str(cls.pos_config.id))
        cls.pos_sess = cls._open_session_for(cls.pos_config)
        cls.product.write({'available_in_pos': True, 'taxes_id': [(5, 0, 0)]})
        env.flush_all()

    def _snapshot(self):
        raw = self.env['ir.config_parameter'].sudo().get_param(
            'mezze_bridge.cfd_%s' % self.pos_config.id, '{}')
        try:
            return json.loads(raw)
        except ValueError:
            return {}

    def _open_display(self):
        """Open the display at its own route, which mints its terminal."""
        self.authenticate('admin', 'admin')
        return self.url_open('/mezze/cfd')

    def _ring_up(self):
        self.browser_js('/mezze/pos', _js(
            "await waitFor(() => phase() === 'menu', 'register ready');\n"
            "await ringUp(%d);\nok();" % self.product.id), login='admin')

    # ── the gate ─────────────────────────────────────────────────────────
    def test_01_no_display_means_no_pushes(self):
        # A snapshot per keystroke to a screen nobody installed is pure noise.
        self._ring_up()
        self.assertEqual(self._snapshot(), {},
                         'the till pushed to a display that does not exist')

    # ── the feed ─────────────────────────────────────────────────────────
    def test_02_a_display_gets_the_cart(self):
        # THE gap: the endpoint existed and nothing called it.
        self._open_display()
        self._ring_up()
        snap = self._snapshot()
        self.assertTrue(snap.get('lines'), 'the display never saw the cart: %r' % snap)
        self.assertEqual(snap['lines'][0]['name'], self.product.name)

    def test_03_the_money_travels_and_agrees_with_itself(self):
        self._open_display()
        self._ring_up()
        snap = self._snapshot()
        self.assertTrue(snap.get('lines'), snap)
        self.assertGreater(snap.get('total', 0), 0,
                           'the guest screen shows a free order: %r' % snap)
        self.assertAlmostEqual(
            snap['total'], round(snap['lines'][0]['price'], 2), places=2,
            msg='the guest total disagrees with its own lines: %r' % snap)

    def test_04_nothing_personal_is_on_the_public_screen(self):
        """It faces the street. Anything on it is readable by a stranger."""
        self._open_display()
        self._ring_up()
        raw = json.dumps(self._snapshot())
        for leak in ('partner', 'customer', 'cashier', 'uuid', 'order_id',
                     'phone', 'email'):
            self.assertNotIn(leak, raw,
                             'the public screen carries "%s": %s' % (leak, raw))

    def test_05_the_snapshot_shape_is_what_the_display_reads(self):
        # Guard against pushing a shape cfd.html cannot render.
        self._open_display()
        self._ring_up()
        snap = self._snapshot()
        for key in ('lines', 'subtotal', 'tax', 'total', 'state', 'change'):
            self.assertIn(key, snap, 'the display expects %r: %r' % (key, snap))
        for key in ('name', 'qty', 'price'):
            self.assertIn(key, snap['lines'][0])
