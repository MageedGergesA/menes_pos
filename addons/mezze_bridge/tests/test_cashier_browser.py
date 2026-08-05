"""V1 — authenticated browser certification of the REAL Owl cashier (/mezze/pos).

Uses Odoo's own ``HttpCase.browser_js(login=...)`` — the framework authenticates the
headless Chrome via the test session, so NO password is typed and NO auth bypass is
introduced. Production ``/mezze/pos`` stays ``auth='user'``. Self-provisions through the
hermetic Mezze POS fixture (company/branch/config/session/products/payment methods).

Tagged ``mezze_browser`` so it can be selected/skipped independently of the headless
Python suite (Chrome may be absent in some CI).
"""
from odoo.tests import tagged

from .common import MezzeHttpCase

# Shared JS prelude: polling waiter + $ helpers. Appended before each assertion body.
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
"""


def _js(body):
    return _PRELUDE + "\n(async () => {\n" + body + "\n})().catch(e => { console.error(e.message || e); });"


@tagged('post_install', '-at_install', 'mezze_browser')
class TestCashierBrowser(MezzeHttpCase):
    fixture_profile = 'POS'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # setUpClass writes are committed → visible to the HTTP worker (separate cursor)
        # that serves /mezze/pos + /bootstrap. Per-test setUp writes are NOT reliably
        # visible, so all browser-visible provisioning happens here.
        # deterministic: known price, NO tax → amount_total == list_price exactly
        cls.product.write({'available_in_pos': True, 'list_price': 100.0, 'taxes_id': [(5, 0, 0)]})
        # cash must be on the resolved branch so the payment screen offers it
        cls.pos_config.write({'payment_method_ids': [(4, cls.cash_payment_method.id)]})
        # Pin the cashier's resolved branch to OUR provisioned config...
        cls.env['ir.config_parameter'].sudo().set_param(
            'mezze_bridge.default_branch_id', str(cls.pos_config.id))
        # ...and force its session fully 'opened', so /bootstrap's _ensure_open_session
        # RETURNS it without writing. (V1 finding: /bootstrap lacks readonly=False yet
        # _ensure_open_session writes on auto-open / opening_control → 400 under the
        # test readonly cursor. Pre-opening avoids the write entirely — no production
        # change made in this verification phase.)
        sess = cls.pos_config.current_session_id
        if sess:
            if sess.state == 'opening_control':
                try:
                    sess.set_opening_control(0, None)
                except Exception:  # noqa: BLE001
                    pass
            if sess.state != 'opened':
                sess.sudo().write({'state': 'opened'})
        cls.env.flush_all()

    # ---- Part E: mount ----
    def test_01_cashier_mounts_real_not_demo(self):
        self.browser_js('/mezze/pos', _js(r"""
            await waitFor(() => phase() === 'menu', 'phase=menu (Owl ready)');
            assert($('.mz-workspace'), 'workspace mounted');
            assert(!$('.mz-state--warn'), 'no auth_required banner');
            assert(!$('.mz-state--error'), 'no error state');
            assert($('.mz-btn--charge'), 'Charge action exists');
            assert($('.mz-cart-empty'), 'cart starts empty');
            assert($$('.mz-tile').length > 0, 'real catalog rendered (>=1 tile)');
            // branch/user context from the server boot (not demo)
            assert($('.mz-branch') && $('.mz-branch').textContent.trim().length > 0, 'branch name present');
            assert($('.mz-user') && $('.mz-user').textContent.trim().length > 0, 'user name present');
            // Part J connectivity snapshot: the shipped cashier renders ONE signal (.mz-conn
            // with data-state = local). Assert it exists and carries a state (not colour-only:
            // it also renders a text label next to the dot).
            assert($('.mz-conn') && $('.mz-conn').getAttribute('data-state'), 'connectivity indicator present with a state');
            ok();
        """), login='admin')

    # ---- Part F: real cash transaction through the DOM ----
    def test_02_cash_transaction_through_dom(self):
        self.browser_js('/mezze/pos', _js(r"""
            await waitFor(() => phase() === 'menu', 'menu');
            const tile = $('.mz-tile[data-product-id="%d"]');
            assert(tile, 'the known priced product tile');
            tile.click();""" % self.product.id + r"""
            await waitFor(() => $('.mz-line'), 'cart line added');
            assert($('.mz-cart-count') && $('.mz-cart-count').textContent.trim() !== '0', 'cart count > 0');
            $('.mz-btn--charge').click();
            await waitFor(() => phase() === 'payment', 'payment screen');
            const cash = $('.mz-method[data-method-mode="cash"]');
            assert(cash, 'cash method available');
            cash.click();
            await waitFor(() => $('.mz-tender'), 'cash tender dialog');
            // "Exact" quick-cash tenders the full remaining (change = 0)
            const exact = $$('.mz-quick').find(b => /exact/i.test(b.textContent));
            assert(exact, 'Exact quick-cash');
            exact.click();
            const confirm = $('.mz-btn--confirm');
            assert(confirm, 'confirm button');
            confirm.click();
            await waitFor(() => phase() === 'receipt' && $('.mz-receipt[data-testid="mz-receipt"]'), 'receipt shown');
            const ref = $('.mz-receipt-ref');
            assert(ref && ref.textContent.trim().length > 0, 'receipt carries a pos_reference');
            ok();
        """), login='admin')

        # DB truth after the browser path
        orders = self.env['pos.order'].search([('config_id', '=', self.pos_config.id)])
        self.assertEqual(len(orders), 1, 'exactly one pos.order created by the browser')
        order = orders
        self.assertAlmostEqual(order.amount_total, 100.0, places=2)
        self.assertIn(order.state, ('paid', 'done', 'invoiced'))
        cash_pms = order.payment_ids.filtered(
            lambda p: p.payment_method_id == self.cash_payment_method)
        self.assertEqual(len(order.payment_ids), 1, 'exactly one payment row')
        self.assertEqual(len(cash_pms), 1, 'the single payment is cash')
        self.assertAlmostEqual(order.payment_ids.amount, 100.0, places=2)

    # ---- Part G: double confirm must not create a duplicate payment ----
    def test_03_double_confirm_no_duplicate(self):
        self.browser_js('/mezze/pos', _js(r"""
            await waitFor(() => phase() === 'menu', 'menu');
            $$('.mz-tile:not(.mz-tile--out)')[0].click();
            await waitFor(() => $('.mz-line'), 'line added');
            $('.mz-btn--charge').click();
            await waitFor(() => phase() === 'payment', 'payment');
            $('.mz-method[data-method-mode="cash"]').click();
            await waitFor(() => $('.mz-tender'), 'tender');
            ($$('.mz-quick').find(b => /exact/i.test(b.textContent))).click();
            const confirm = $('.mz-btn--confirm');
            // rapid double click on the same confirm control
            confirm.click(); confirm.click();
            await waitFor(() => phase() === 'receipt', 'receipt');
            ok();
        """), login='admin')

        orders = self.env['pos.order'].search([('config_id', '=', self.pos_config.id)])
        self.assertEqual(len(orders), 1, 'double confirm still made exactly one order')
        self.assertEqual(len(orders.payment_ids), 1,
                         'double confirm still made exactly one payment (UI honours server idempotency)')
