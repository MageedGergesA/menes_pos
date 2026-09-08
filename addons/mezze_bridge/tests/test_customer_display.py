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


@tagged('post_install', '-at_install', 'mezze_browser', 'mezze_cfd')
class TestCustomerDisplayTax(MezzeHttpCase):
    """What the guest is told the tax is.

    The class above deliberately sells an UNTAXED product, so it could never have
    caught this: ``_pushCfdNow`` sent ``subtotal: estimate`` and a literal
    ``tax: 0``. The display has a VAT row — it is on the page, the guest can read
    it — and it has therefore always printed zero.

    Worse than the zero was what the page did with it. ``cfd.html`` derived its own
    split, ``svc = subtotal*0.12`` and ``vat = (subtotal+svc)*0.14``, and printed
    both whenever they happened to sum to the tax it was sent. Neither rate comes
    from anything the branch configured. It stayed invisible only because ``tax``
    was always 0 and the check therefore never matched; the first real tax value
    would have started printing a service charge the branch does not levy onto a
    guest-facing bill.

    So this pins the two properties that matter and nothing else: the display's
    money agrees with the till's, and every tax row on it was computed by the
    server rather than by the screen.
    """
    fixture_profile = 'POS'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        env['ir.config_parameter'].sudo().set_param('mezze_bridge.api_token', 'cd-tax-tok')
        env['ir.config_parameter'].sudo().set_param(
            'mezze_bridge.default_branch_id', str(cls.pos_config.id))
        cls.pos_sess = cls._open_session_for(cls.pos_config)
        tax = env['account.tax'].create({
            'name': 'VAT 14%', 'amount': 14.0, 'amount_type': 'percent',
            'type_tax_use': 'sale', 'price_include_override': 'tax_included',
            'company_id': cls.pos_config.company_id.id})
        cls.tax = tax
        cls.product.write({'available_in_pos': True, 'list_price': 114.0,
                           'taxes_id': [(6, 0, [tax.id])]})
        env.flush_all()

    def _snapshot(self):
        raw = self.env['ir.config_parameter'].sudo().get_param(
            'mezze_bridge.cfd_%s' % self.pos_config.id, '{}')
        try:
            return json.loads(raw)
        except ValueError:
            return {}

    def _open_display(self):
        self.authenticate('admin', 'admin')
        return self.url_open('/mezze/cfd')

    def _ring_up(self):
        self.browser_js('/mezze/pos', _js(
            "await waitFor(() => phase() === 'menu', 'register ready');\n"
            "await ringUp(%d);\nok();" % self.product.id), login='admin')

    def test_06_the_guest_screen_names_the_tax(self):
        self._open_display()
        self._ring_up()
        snap = self._snapshot()
        self.assertTrue(snap.get('lines'), snap)
        self.assertGreater(snap.get('tax', 0), 0,
                           'a taxed order reached the guest screen as tax-free: %r' % snap)
        self.assertTrue(snap.get('taxes'),
                        'the display was sent a tax it cannot name: %r' % snap)
        self.assertIn('VAT', ' '.join(t['label'] for t in snap['taxes']),
                      'the tax row is not named by the branch: %r' % snap['taxes'])

    def test_07_the_breakdown_reconciles(self):
        """Subtotal + tax must equal the total the guest is asked for. A guest-facing
        breakdown that does not add up is worse than none — it is an argument at the
        counter with a screen as the other party."""
        self._open_display()
        self._ring_up()
        snap = self._snapshot()
        named = sum(t['amount'] for t in snap.get('taxes') or [])
        self.assertAlmostEqual(named, snap['tax'], places=2,
                               msg='the named rows do not sum to the tax: %r' % snap)
        self.assertAlmostEqual(snap['subtotal'] + snap['tax'], snap['total'], places=2,
                               msg='the guest bill does not add up: %r' % snap)

    def test_08_the_display_agrees_with_the_till_on_a_tax_exclusive_branch(self):
        """The cashier's Charge button and the guest's TOTAL are the same number.

        Deliberately run on a branch that displays prices **tax-exclusive**
        (`iface_tax_included = 'subtotal'`), because that is the only configuration
        where the old push was actually wrong — and this test was vacuous until it
        said so. On the class's default tax-INCLUSIVE branch `estimatedTotal` and
        `grandTotal` are the same number, so an assertion there passes whichever of
        the two the push sends, and proves nothing. Its negative control confirmed
        it: reverting the fix failed tests 06 and 07 and left this one green.

        On this branch the till shows 100.00 as its running figure and charges
        114.00. A guest screen quoting 100.00 is quoting a price nobody pays.
        """
        self.pos_config.write({'iface_tax_included': 'subtotal'})
        self.env.flush_all()
        self.addCleanup(self.pos_config.write, {'iface_tax_included': 'total'})
        self._open_display()
        self.browser_js('/mezze/pos?debug=1', _js(
            "await waitFor(() => phase() === 'menu', 'register ready');\n"
            "await ringUp(%d);\n"
            "await waitFor(() => window.__mezzeCashier, 'debug handle');\n"
            "const o = window.__mezzeCashier.order;\n"
            "assert(Math.abs(o.estimatedTotal - o.grandTotal) > 0.01,\n"
            "  'this branch is not tax-exclusive, so the test proves nothing: '\n"
            "  + o.estimatedTotal + ' vs ' + o.grandTotal);\n"
            "console.log('MZTOTAL:' + o.grandTotal.toFixed(2)"
            " + '/' + o.subtotal.toFixed(2) + '/' + o.estimatedTotal.toFixed(2));\n"
            "ok();" % self.product.id), login='admin')
        snap = self._snapshot()
        gross = round(self.product.list_price, 2)          # 114.00, tax included
        net = round(gross / 1.14, 2)                       # 100.00, what the till displays
        self.assertAlmostEqual(
            snap['total'], gross, places=2,
            msg='the guest was quoted the net price, not what they pay: %r' % snap)
        self.assertNotAlmostEqual(
            snap['total'], net, places=2,
            msg='the guest screen is still quoting the tax-exclusive figure: %r' % snap)
        self.assertAlmostEqual(
            snap['subtotal'] + snap['tax'], snap['total'], places=2,
            msg='the tax-exclusive bill does not add up: %r' % snap)

    def test_09_no_rate_is_invented_by_the_screen(self):
        """The page must not carry a hardcoded service or VAT rate any more.

        A structural assertion on purpose: the defect was a literal in a file the
        browser tests do not read arithmetic out of, and it produced a plausible
        number rather than an error. Nothing else would have failed.
        """
        import os
        import re
        path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static', 'cfd.html')
        with open(path, encoding='utf-8') as fh:
            body = fh.read()
        # Strip line comments first. The fix leaves a comment that QUOTES the old
        # arithmetic to explain why it went, and an assertion that merely searched
        # the file would either trip on that comment or — worse — pass only because
        # of where the comment happens to sit. Neither tests the code.
        code = re.sub(r'(?<!:)//[^\n]*', '', body)
        for invented in ('*0.12', '*0.14', '* 0.12', '* 0.14'):
            self.assertNotIn(
                invented, code,
                'the customer display derives its own tax rate (%s) again' % invented)
        # ...and the row list must come from the payload, not from a constant.
        self.assertIn('s.taxes', code,
                      'the display no longer reads the named breakdown it is sent')
