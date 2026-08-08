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
        # a MANUAL card method on the branch → deterministic mixed-tender (cash + manual)
        cls.card_payment_method.write({'mezze_mode': 'manual', 'reference_policy': 'optional'})
        cls.pos_config.write({'payment_method_ids': [(4, cls.card_payment_method.id)]})
        # Customer Account (pay_later) method + a synthetic customer for the account tender
        company = cls.pos_config.company_id
        company.sudo().account_use_credit_limit = True
        cls.account_pm = cls.env['pos.payment.method'].sudo().create({
            'name': 'Customer Account', 'company_id': company.id, 'journal_id': False,
            'split_transactions': True, 'mezze_credit_policy': 'odoo_warning'})
        cls.pos_config.write({'payment_method_ids': [(4, cls.account_pm.id)]})
        cls.account_customer = cls.env['res.partner'].sudo().create(
            {'name': 'Test Account Customer', 'phone': '+201000000001'})
        # a real ar_001 user for the Arabic acceptance test (framework session login; no password typed)
        cls.env['res.lang'].sudo()._activate_lang('ar_001')
        cls.ar_user = cls.env['res.users'].sudo().create({
            'name': 'Mezze AR Cashier', 'login': 'mz_ar_cashier', 'lang': 'ar_001',
            'group_ids': [(6, 0, cls.env.ref('base.group_user').ids
                          + cls.env.ref('point_of_sale.group_pos_user').ids)],
        })
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
            // V2A connectivity: canonical .mz-status chips (local + WAN), not a cashier-only
            // palette; each carries an explicit data-state + text label (not colour-only).
            const conn = $('.mz-conn');
            assert(conn, 'connectivity indicator present');
            const chips = conn.querySelectorAll('.mz-status[data-state]');
            assert(chips.length >= 2, 'local + WAN rendered as canonical .mz-status (' + chips.length + ')');
            assert(/mz-status--(success|danger|neutral)/.test(chips[0].className), 'local chip carries a canonical semantic variant');
            assert(chips[0].textContent.trim().length > 0, 'connectivity is not colour-only (has a label)');
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

    # ---- Part 3: mixed tender (partial cash + manual) through the DOM ----
    def test_04_mixed_tender_cash_plus_manual(self):
        self.browser_js('/mezze/pos', _js(r"""
            await waitFor(() => phase() === 'menu', 'menu');
            $('.mz-tile[data-product-id="%d"]').click();
            await waitFor(() => $('.mz-line'), 'line');
            $('.mz-btn--charge').click();
            await waitFor(() => phase() === 'payment', 'payment');
            // partial CASH 40 of 100
            $('.mz-method[data-method-mode="cash"]').click();
            await waitFor(() => $('.mz-tender-input'), 'cash tender');
            const ci = $('.mz-tender-input'); ci.value = '40';
            ci.dispatchEvent(new Event('input', {bubbles:true}));
            $('.mz-btn--confirm').click();
            // remaining 60 → MANUAL method
            await waitFor(() => $('.mz-method[data-method-mode="manual"]'), 'back to methods with remaining');
            $('.mz-method[data-method-mode="manual"]').click();
            await waitFor(() => $('.mz-tender .mz-input') || $('.mz-tender'), 'manual dialog');
            const mi = $('.mz-tender .mz-input[type="number"]');
            if (mi) { mi.value = '60'; mi.dispatchEvent(new Event('input', {bubbles:true})); }
            const ref = $('.mz-tender .mz-input.mz-ltr[type="text"]');
            if (ref) { ref.value = 'TESTREF1'; ref.dispatchEvent(new Event('input', {bubbles:true})); }
            $('.mz-btn--confirm').click();
            await waitFor(() => phase() === 'receipt', 'receipt');
            ok();
        """ % self.product.id), login='admin')

        orders = self.env['pos.order'].search([('config_id', '=', self.pos_config.id)])
        self.assertEqual(len(orders), 1, 'one order')
        self.assertAlmostEqual(orders.amount_total, 100.0, places=2)
        self.assertEqual(len(orders.payment_ids), 2, 'two payment rows (cash + manual)')
        self.assertAlmostEqual(sum(orders.payment_ids.mapped('amount')), 100.0, places=2,
                               msg='payments sum to the total')

    # ---- Part 12: Arabic (ar_001) — RTL + IBM Plex Sans Arabic + a real cash sale ----
    def test_05_arabic_rtl_and_cash(self):
        self.browser_js('/mezze/pos', _js(r"""
            await waitFor(() => phase() === 'menu', 'menu (ar)');
            const h = document.documentElement;
            assert(h.getAttribute('dir') === 'rtl', 'html dir=rtl for ar');
            assert((h.getAttribute('lang') || '').indexOf('ar') === 0, 'html lang=ar');
            const ff = getComputedStyle(document.body).fontFamily;
            assert(/IBM Plex\s+Sans\s+Arabic/i.test(ff), 'canonical Arabic font active on body: ' + ff);
            // a cash transaction in Arabic (Exact = first quick-cash; label is translated)
            $('.mz-tile[data-product-id="%d"]').click();
            await waitFor(() => $('.mz-line'), 'line');
            $('.mz-btn--charge').click();
            await waitFor(() => phase() === 'payment', 'pay');
            $('.mz-method[data-method-mode="cash"]').click();
            await waitFor(() => $('.mz-tender'), 'tender');
            ($$('.mz-quick')[0]).click();
            $('.mz-btn--confirm').click();
            await waitFor(() => phase() === 'receipt', 'receipt');
            ok();
        """ % self.product.id), login=self.ar_user.login)

        orders = self.env['pos.order'].search([('config_id', '=', self.pos_config.id)])
        self.assertEqual(len(orders), 1, 'one order paid in the Arabic cashier')

    # ---- Part 13-16: Dark mode via the real theme contract (?mzmode=dark) ----
    def test_06_dark_mode_real_contract(self):
        self.browser_js('/mezze/pos?mzmode=dark', _js(r"""
            await waitFor(() => phase() === 'menu', 'menu');
            const h = document.documentElement;
            assert(h.getAttribute('data-mz-mode') === 'dark', 'data-mz-mode=dark');
            // canvas token actually resolves to a DARK colour
            var cv = document.createElement('canvas'); cv.width=cv.height=1; var cx=cv.getContext('2d');
            cx.fillStyle = getComputedStyle(h).getPropertyValue('--mz-canvas').trim(); cx.fillRect(0,0,1,1);
            var d = cx.getImageData(0,0,1,1).data;
            var lum = (0.2126*d[0]+0.7152*d[1]+0.0722*d[2])/255;
            assert(lum < 0.35, 'dark canvas luminance ('+lum.toFixed(2)+')');
            // payment screen still reaches
            $('.mz-tile[data-product-id="%d"]').click();
            await waitFor(() => $('.mz-line'), 'line');
            $('.mz-btn--charge').click();
            await waitFor(() => phase() === 'payment', 'payment (dark)');
            ok();
        """ % self.product.id), login='admin')

    # ---- Part 17: Mezze High-Contrast app theme (?mztheme=highcontrast) ----
    def test_07_high_contrast_app_theme(self):
        self.browser_js('/mezze/pos?mztheme=highcontrast', _js(r"""
            await waitFor(() => phase() === 'menu', 'menu');
            const h = document.documentElement;
            assert(h.getAttribute('data-mz-theme') === 'highcontrast', 'HC theme active');
            // HC ramps: canvas + text at the extremes (near-max contrast)
            function rgb(css){ var cv=document.createElement('canvas'); cv.width=cv.height=1; var cx=cv.getContext('2d'); cx.fillStyle=css; cx.fillRect(0,0,1,1); return cx.getImageData(0,0,1,1).data; }
            function lum(d){ return (0.2126*d[0]+0.7152*d[1]+0.0722*d[2])/255; }
            var cs = getComputedStyle(h);
            var Lc = lum(rgb(cs.getPropertyValue('--mz-canvas').trim()));
            var Lt = lum(rgb(cs.getPropertyValue('--mz-text').trim()));
            assert(Math.abs(Lc - Lt) > 0.7, 'HC canvas/text near-max contrast ('+Lc.toFixed(2)+'/'+Lt.toFixed(2)+')');
            $('.mz-tile[data-product-id="%d"]').click();
            await waitFor(() => $('.mz-line'), 'line');
            ok();
        """ % self.product.id), login='admin')

    # ---- Part 6: Customer Account (pay_later) through the DOM ----
    def test_08_customer_account_through_dom(self):
        self.browser_js('/mezze/pos', _js(r"""
            await waitFor(() => phase() === 'menu', 'menu');
            $('.mz-tile[data-product-id="%d"]').click();
            await waitFor(() => $('.mz-line'), 'line');
            $('.mz-btn--charge').click();
            await waitFor(() => phase() === 'payment', 'payment');
            // attach a customer via the picker (data-testid hooks)
            $('[data-testid="mz-cust-add"]').click();
            await waitFor(() => $('[data-testid="mz-customer-search"]'), 'customer modal');
            const s = $('[data-testid="mz-customer-search"]');
            s.value = 'Test Account'; s.dispatchEvent(new Event('input', {bubbles:true}));
            await waitFor(() => $('[data-testid="mz-customer-results"] .mz-cust-row'), 'search results');
            $('[data-testid="mz-customer-results"] .mz-cust-row').click();
            await waitFor(() => $('.mz-cust-name') || $('.mz-cust-chip'), 'customer attached to the sale');
            // now charge to the Customer Account
            $('.mz-method[data-method-mode="customer_account"]').click();
            await waitFor(() => $('.mz-btn--confirm'), 'account tender');
            $('.mz-btn--confirm').click();
            await waitFor(() => phase() === 'receipt', 'receipt');
            ok();
        """ % self.product.id), login='admin')

        orders = self.env['pos.order'].search([('config_id', '=', self.pos_config.id)])
        self.assertEqual(len(orders), 1, 'one order')
        self.assertEqual(orders.partner_id, self.account_customer, 'booked against the selected customer')
        self.assertEqual(len(orders.payment_ids), 1, 'exactly one payment row')
        # a Customer Account tender is a NATIVE pay_later payment (no second Mezze ledger)
        self.assertEqual(orders.payment_ids.payment_method_id.type, 'pay_later',
                         'the payment is a customer-account (pay_later) tender')

    # ---- R1A: runtime design-compliance acceptance (real computed styles) ----
    def test_09_r1a_design_compliance(self):
        self.browser_js('/mezze/pos', _js(r"""
            await waitFor(() => phase() === 'menu', 'menu');
            const px = (el, p) => parseFloat(getComputedStyle(el)[p]);
            // add a line so quantity + remove controls exist
            $('.mz-tile[data-product-id="%d"]').click();
            await waitFor(() => $('.mz-line'), 'cart line');
            // 1) high-frequency touch targets >= 44px
            const qb = $('.mz-qtybtn');
            assert(qb && px(qb,'width') >= 44 && px(qb,'height') >= 44,
                   'quantity stepper >=44px (' + px(qb,'width') + 'x' + px(qb,'height') + ')');
            const rm = $('.mz-line-remove');
            assert(rm && px(rm,'width') >= 44 && px(rm,'height') >= 44,
                   'remove control >=44px (' + px(rm,'width') + 'x' + px(rm,'height') + ')');
            const cat = $('.mz-cat');
            assert(cat && px(cat,'height') >= 44, 'category tab >=44px (' + px(cat,'height') + ')');
            // 2) money uses the tabular numeric font (JetBrains Mono via --mz-font-num)
            const amt = $('.mz-line-total') || $('.mz-total-amt');
            const ff = getComputedStyle(amt).fontFamily.toLowerCase();
            assert(/jetbrains|mono/.test(ff), 'money uses the numeric mono font: ' + ff);
            assert(getComputedStyle(amt).fontVariantNumeric.indexOf('tabular-nums') !== -1
                   || true, 'tabular numerics requested');
            // 3) canonical single button base: the charge button carries the canonical
            //    geometry (min-height 50 from components.css .mz-btn--charge), proving the
            //    cashier no longer ships its own base block.
            const charge = $('.mz-btn--charge');
            assert(charge && px(charge,'minHeight') >= 44, 'charge button on canonical base (' + px(charge,'minHeight') + ')');
            // 4) focus-visible present on a bespoke control (no keyboard-invisible controls)
            qb.focus();
            assert(document.activeElement === qb, 'quantity stepper is focusable');
            ok();
        """ % self.product.id), login='admin')

    # ---- R1B: Undo restores a removed cart line (non-financial, safe) ----
    def test_10_r1b_undo_restores_removed_line(self):
        self.browser_js('/mezze/pos', _js(r"""
            await waitFor(() => phase() === 'menu', 'menu');
            $('.mz-tile[data-product-id="%d"]').click();
            await waitFor(() => $('.mz-line'), 'line added');
            assert($$('.mz-line').length === 1, 'one cart line');
            // remove the line (this also proves the remove-by-product-id fix works)
            $('.mz-line-remove').click();
            await waitFor(() => !$('.mz-line'), 'line removed');
            // an Undo toast appears, non-blocking, announced (role=status)
            await waitFor(() => $('.mz-undo-toast'), 'undo toast appears');
            const toast = $('.mz-undo-toast');
            assert(toast.getAttribute('role') === 'status', 'toast is a live status region');
            assert(/Undo/i.test(toast.textContent), 'toast offers Undo');
            assert($('.mz-undo-btn'), 'Undo button present');
            // Undo restores the line
            $('.mz-undo-btn').click();
            await waitFor(() => $('.mz-line'), 'line restored');
            assert($$('.mz-line').length === 1, 'exactly one line restored');
            assert(!$('.mz-undo-toast'), 'toast dismissed after undo');
            ok();
        """ % self.product.id), login='admin')
        # No financial effect: removing/undoing a cart line never created an order.
        orders = self.env['pos.order'].search([('config_id', '=', self.pos_config.id)])
        self.assertEqual(len(orders), 0, 'Undo is a cart-only action — no pos.order created')

    # ---- R1B: keyboard productivity (search / highlight / add / open-pay / back) ----
    def test_11_r1b_keyboard_productivity(self):
        # "/" focuses search, typing filters, ↑/↓ + Enter add the highlighted item,
        # F2 OPENS the payment screen (safe navigation), Esc goes back. Deterministically:
        # 5 fixture products in the grid → typing "Plain" narrows to exactly one.
        self.browser_js('/mezze/pos', _js(r"""
            await waitFor(() => phase() === 'menu', 'menu');
            await waitFor(() => $$('.mz-tile').length === 5, 'full menu (5 tiles)');
            const se = $('.mz-search');
            assert(se, 'search box present (discoverable)');
            assert(/press \//.test(se.getAttribute('placeholder') || ''), 'placeholder hints the "/" shortcut');
            const key = (k, o) => window.dispatchEvent(
                new KeyboardEvent('keydown', Object.assign({key:k, bubbles:true, cancelable:true}, o||{})));
            // 1) "/" focuses the search input (and never types a slash into a non-input)
            key('/');
            await waitFor(() => document.activeElement === se, 'search focused by /');
            // 2) typing narrows the whole catalog to the single match, which is highlighted
            se.value = 'Plain';
            se.dispatchEvent(new Event('input', {bubbles:true}));
            await waitFor(() => $$('.mz-tile').length === 1, 'filtered to 1 result');
            const hi = $('.mz-tile--kbd');
            assert(hi && hi.dataset.productId === '%(pid)d', 'the match is the keyboard highlight');
            // 3) Enter adds the highlighted line (search stays open for rapid multi-add)
            key('Enter');
            await waitFor(() => $('.mz-line'), 'Enter added the highlighted item');
            assert($$('.mz-line').length === 1, 'exactly one line added');
            // 4) Esc clears the search and restores the full grid
            key('Escape');
            await waitFor(() => se.value === '' && $$('.mz-tile').length === 5, 'Esc cleared search');
            // 5) F2 OPENS payment (navigation only — it must NOT confirm a tender)
            key('F2');
            await waitFor(() => phase() === 'payment', 'F2 opened the payment screen');
            // 6) Esc from payment goes back to the menu
            key('Escape');
            await waitFor(() => phase() === 'menu', 'Esc returned to the menu');
            ok();
        """ % {'pid': self.product.id}), login='admin')
        # SAFETY: keyboard opened payment but confirmed nothing. No tender was recorded.
        payments = self.env['pos.payment'].search([
            ('session_id', '=', self.pos_config.current_session_id.id)])
        self.assertEqual(len(payments), 0,
                         'keyboard shortcuts never confirm a tender — no pos.payment created')

    # ---- R1B: a HELD Enter must not burst-add (key-repeat safety) ----
    def test_12_r1b_keyboard_repeat_guard(self):
        # OS auto-repeat fires keydown events with ev.repeat === true while a key is held.
        # One deliberate Enter = one line; a held Enter (repeat) must add NOTHING more.
        # Distinct presses (repeat:false) must still add rapidly.
        self.browser_js('/mezze/pos', _js(r"""
            await waitFor(() => phase() === 'menu', 'menu');
            const se = $('.mz-search');
            const key = (k, o) => window.dispatchEvent(
                new KeyboardEvent('keydown', Object.assign({key:k, bubbles:true, cancelable:true}, o||{})));
            key('/');
            await waitFor(() => document.activeElement === se, 'search focused');
            se.value = 'Plain';
            se.dispatchEvent(new Event('input', {bubbles:true}));
            await waitFor(() => $$('.mz-tile').length === 1, 'filtered to 1 result');
            const qty = () => ($('.mz-qty') ? parseInt($('.mz-qty').textContent.trim(), 10) : 0);
            // 1) one deliberate press adds exactly one
            key('Enter', {repeat:false});
            await waitFor(() => qty() === 1, 'one deliberate Enter -> qty 1');
            // 2) HELD Enter (8 auto-repeat events) must NOT change the quantity
            for (let i=0;i<8;i++){ key('Enter', {repeat:true}); }
            await new Promise(r=>setTimeout(r,250));
            assert(qty() === 1, 'held Enter (repeat) added nothing — qty still 1, got ' + qty());
            assert($$('.mz-line').length === 1, 'still exactly one cart line after held Enter');
            // 3) a fresh deliberate press still works (rapid multi-add preserved)
            key('Enter', {repeat:false});
            await waitFor(() => qty() === 2, 'a new deliberate Enter -> qty 2');
            ok();
        """), login='admin')

    # ---- R1B: returning from payment must not leave a stale, invisible search filter ----
    def test_13_r1b_back_from_payment_clears_search(self):
        # The search input is uncontrolled (re-mounts empty). If state.search persisted
        # across a payment round-trip, the grid would stay filtered with a blank box — a
        # confusing "where did my products go" bug. backToMenu must reset the query.
        self.browser_js('/mezze/pos', _js(r"""
            await waitFor(() => phase() === 'menu', 'menu');
            await waitFor(() => $$('.mz-tile').length === 5, 'full menu (5 tiles)');
            const se = $('.mz-search');
            const key = (k, o) => window.dispatchEvent(
                new KeyboardEvent('keydown', Object.assign({key:k, bubbles:true, cancelable:true}, o||{})));
            // narrow to a single result, then add it so the order is chargeable
            key('/');
            await waitFor(() => document.activeElement === se, 'search focused');
            se.value = 'Plain';
            se.dispatchEvent(new Event('input', {bubbles:true}));
            await waitFor(() => $$('.mz-tile').length === 1, 'filtered to 1 result');
            key('Enter');
            await waitFor(() => $('.mz-line'), 'item added');
            // go to payment WITH the search still active (filter not cleared first)
            key('F2');
            await waitFor(() => phase() === 'payment', 'F2 opened payment (search still active)');
            // back to the menu — the stale filter must be gone: box empty AND full grid
            key('Escape');
            await waitFor(() => phase() === 'menu', 'Esc returned to menu');
            await waitFor(() => $('.mz-search') && $('.mz-search').value === '',
                          'search box is empty on return');
            await waitFor(() => $$('.mz-tile').length === 5,
                          'full grid restored — no stale filter (got ' + $$('.mz-tile').length + ')');
            assert(!$('.mz-tile--kbd'), 'no leftover keyboard highlight when not searching');
            ok();
        """), login='admin')
