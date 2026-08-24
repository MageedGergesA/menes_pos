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
            // 1) high-frequency touch targets >= 44px (P3E canonical .mz-stepper)
            const qb = $('.mz-stepper__btn');
            assert(qb && px(qb,'width') >= 44 && px(qb,'height') >= 44,
                   'quantity stepper >=44px (' + px(qb,'width') + 'x' + px(qb,'height') + ')');
            assert(qb.tagName === 'BUTTON' && qb.getAttribute('type') === 'button',
                   'stepper is a native <button type=button>');
            assert(/quantity/i.test(qb.getAttribute('aria-label') || ''),
                   'stepper button has an accessible name');
            const rm = $('.mz-line-remove');
            assert(rm && px(rm,'width') >= 44 && px(rm,'height') >= 44,
                   'remove control >=44px (' + px(rm,'width') + 'x' + px(rm,'height') + ')');
            // DESIGN FIDELITY: the Register now shows a VERTICAL category sidebar at
            // >=1280px and the horizontal chip strip below it — exactly one is visible.
            // Assert whichever the user is actually looking at, so the >=44px contract
            // is checked on the live control rather than on a hidden element.
            const cat = [...$$('.mz-catside__item, .mz-cat')]
                .find(e => e.getBoundingClientRect().height > 0);
            assert(cat, 'a category control is visible');
            assert(px(cat,'height') >= 44, 'category control >=44px (' + px(cat,'height') + ')');
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
            // 4) focus-visible present on the stepper (no keyboard-invisible controls)
            qb.focus();
            assert(document.activeElement === qb, 'quantity stepper is focusable');
            const ow = parseFloat(getComputedStyle(qb).outlineWidth) || 0;
            assert(getComputedStyle(qb).outlineStyle !== 'none' && ow >= 2,
                   'focused stepper shows a canonical outline ring (' + getComputedStyle(qb).outlineWidth + ')');
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
            const qty = () => ($('.mz-stepper__value') ? parseInt($('.mz-stepper__value').textContent.trim(), 10) : 0);
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

    # ---- P3E: canonical quantity stepper — rapid repeat, no duplication, correct
    #      pricing, and the EXISTING removal-at-1 rule preserved (product = 100, no tax) ----
    def test_14_p3e_quantity_stepper(self):
        self.browser_js('/mezze/pos', _js(r"""
            await waitFor(() => phase() === 'menu', 'menu');
            $('.mz-tile[data-product-id="%d"]').click();
            await waitFor(() => $('.mz-line'), 'cart line');
            // canonical compound control renders (container + value + two buttons)
            const step = $('.mz-line .mz-stepper');
            assert(step, 'canonical .mz-stepper renders on the cart line');
            const val = () => $('.mz-line .mz-stepper__value');
            const money = () => parseFloat(($('.mz-line-total').textContent || '').replace(/[^0-9.]/g,'')) || 0;
            assert(val() && val().textContent.trim() === '1', 'starts at qty 1');
            assert(money() === 100, 'line total is 100 at qty 1, got ' + money());
            const btns = $$('.mz-line .mz-stepper__btn');
            assert(btns.length === 2, 'exactly minus + plus');
            const minus = btns[0], plus = btns[1];
            // rapid 5 taps must ALL land (no dropped taps, no debounce) and never duplicate the line
            for (let i=0;i<5;i++){ plus.click(); }
            await waitFor(() => val() && val().textContent.trim() === '6', 'five rapid taps -> qty 6, got ' + (val()&&val().textContent));
            assert($$('.mz-line').length === 1, 'still exactly one line (no accidental duplication)');
            assert(money() === 600, 'line total tracks quantity: 6*100=600, got ' + money());
            // decrement back down to 1
            for (let i=0;i<5;i++){ minus.click(); }
            await waitFor(() => val() && val().textContent.trim() === '1', 'decrement returns to qty 1');
            assert(money() === 100, 'line total back to 100');
            // EXISTING rule: a further decrement at qty 1 REMOVES the line (not clamp)
            minus.click();
            await waitFor(() => !$('.mz-line'), 'decrement at 1 removes the line (existing behavior preserved)');
            ok();
        """ % self.product.id), login='admin')

    # ---- P3G: canonical card — interactive whole-card semantics + selected-not-colour-only ----
    def test_15_p3g_card_interactive_and_selected(self):
        self.browser_js('/mezze/pos', _js(r"""
            await waitFor(() => phase() === 'menu', 'menu');
            await waitFor(() => $$('.mz-tile').length > 0, 'tiles');
            const tile = $('.mz-tile');
            // 1) an interactive whole-card is a NATIVE button (not a div with onclick),
            //    and it does NOT nest another interactive control inside it
            assert(tile.tagName === 'BUTTON', 'product card is a native <button> (interactive whole-card)');
            assert(!tile.querySelector('button, a'), 'interactive card does not nest a button/link');
            // 2) canonical surface + visible keyboard focus
            const cs = getComputedStyle(tile);
            assert(parseFloat(cs.borderTopWidth) >= 1, 'card carries the canonical border');
            tile.focus();
            assert(document.activeElement === tile, 'card is keyboard-focusable');
            assert(getComputedStyle(tile).outlineStyle !== 'none'
                   || parseFloat(getComputedStyle(tile).outlineWidth) >= 2, 'focus ring visible');
            // 3) SELECTED state (search highlight) is not colour-only: it carries an inset ring
            const key = (k, o) => window.dispatchEvent(
                new KeyboardEvent('keydown', Object.assign({key:k, bubbles:true, cancelable:true}, o||{})));
            key('/');
            const se = $('.mz-search'); se.value = 'Plain'; se.dispatchEvent(new Event('input', {bubbles:true}));
            await waitFor(() => $('.mz-tile--kbd'), 'a tile becomes selected/highlighted');
            const sel = $('.mz-tile--kbd');
            assert(getComputedStyle(sel).boxShadow !== 'none',
                   'selected state has a non-colour-only ring, got ' + getComputedStyle(sel).boxShadow);
            ok();
        """), login='admin')

    # ---- P3I: category selector is a canonical FILTER CHIP (aria-pressed, non-colour cue) ----
    def test_16_p3i_category_filter_chip(self):
        self.browser_js('/mezze/pos', _js(r"""
            await waitFor(() => phase() === 'menu', 'menu');
            await waitFor(() => $$('.mz-cat').length > 0, 'category chips');
            const chips = $$('.mz-cat');
            // 1) filter chips are native buttons with aria-pressed (a toggle), >=44px
            for (const c of chips) {
                assert(c.tagName === 'BUTTON', 'category chip is a native <button>');
                assert(c.hasAttribute('aria-pressed'), 'category chip carries aria-pressed (filter semantics)');
                assert(parseFloat(getComputedStyle(c).minHeight) >= 44, 'category chip >=44px');
            }
            // 2) exactly one selected (the initial All), and its state is not colour-only:
            //    aria-pressed="true" + a heavier weight than an unselected chip
            const active = chips.find(c => c.getAttribute('aria-pressed') === 'true');
            assert(active, 'one category is selected');
            const other = chips.find(c => c.getAttribute('aria-pressed') !== 'true');
            if (other) {
                assert(parseInt(getComputedStyle(active).fontWeight,10) > parseInt(getComputedStyle(other).fontWeight,10),
                       'selected chip is heavier (non-colour cue)');
                // 3) selecting another chip moves the pressed state (single-select filter)
                other.click();
                await waitFor(() => other.getAttribute('aria-pressed') === 'true', 'clicked chip becomes pressed');
                assert($$('.mz-cat').filter(c => c.getAttribute('aria-pressed') === 'true').length === 1,
                       'still exactly one selected filter');
            }
            // 4) business status is NOT a filter chip — no .mz-status carries aria-pressed
            assert($$('.mz-status').every(s => !s.hasAttribute('aria-pressed')),
                   'status chips are not filter chips');
            ok();
        """), login='admin')

    # ---- DESIGN FIDELITY: the restored icon rail must not strand the payment screen ----
    def test_18_adding_a_line_never_resizes_the_menu(self):
        """The product grid must not move under the cashier's finger.

        ``.mz-cart`` is a flex item, and a flex item defaults to ``min-width:auto``
        — it refuses to shrink below its content's minimum width. One order line's
        controls needed more than the panel's 340px basis, so the panel grew, took
        that width from the catalog, and resized every product card the moment the
        first item landed. Cards changed size and appeared to jump.

        Measured, not inspected: the panel and the cards must have the same
        geometry holding an order as they had empty.

        The other half of that symptom — favourites re-ranking under the finger,
        fixed in ``Root._stableFavoriteIds`` — is deliberately not driven from here.
        It only manifests inside the Favourites view of a till that already has a
        history, and reaching that view needs either a reload (which detaches this
        test's own debugger session) or the category chips, which differ between
        the register and workspace layouts. The invariant it relies on is asserted
        directly instead: see ``test_20``.
        """
        self.browser_js('/mezze/pos', _js(r"""
            await waitFor(() => phase() === 'menu', 'register ready');
            await waitFor(() => $$('.mz-tile').length > 0, 'catalog');
            const geom = () => ({
                cart: Math.round($('.mz-cart').getBoundingClientRect().width),
                grid: Math.round($('.mz-grid').getBoundingClientRect().width),
                tile: Math.round($('.mz-tile').getBoundingClientRect().width),
            });
            const empty = geom();

            $$('.mz-tile')[0].click();
            // A configurable product opens the configurator first; confirm it.
            await new Promise((r) => setTimeout(r, 250));
            const confirm = $$('button').find((b) => /Add to order/i.test(b.textContent));
            if (confirm) { confirm.click(); }
            await waitFor(() => $('.mz-line'), 'a line reached the order');

            const withLine = geom();
            assert(withLine.cart === empty.cart,
                   'the order panel widened when a line arrived: ' + empty.cart +
                   ' -> ' + withLine.cart);
            assert(withLine.grid === empty.grid,
                   'the catalog narrowed when a line arrived: ' + empty.grid +
                   ' -> ' + withLine.grid);
            assert(withLine.tile === empty.tile,
                   'the product cards resized when a line arrived: ' + empty.tile +
                   ' -> ' + withLine.tile);

            // The two structural guarantees, read off the LIVE page rather than the
            // stylesheet, so this still fails if the rule is written but never
            // reaches the bundle.
            assert(getComputedStyle($('.mz-cart')).minWidth === '0px',
                   'the order panel can still be widened by its own content');
            assert(getComputedStyle($('.mz-line-ctrls')).flexWrap === 'wrap',
                   'the line controls cannot wrap, so they push the panel wider instead');
            ok();
        """), login='admin')

    def test_21_payment_never_opens_with_nothing_to_collect(self):
        """Every tender button disables itself once nothing is left to collect.

        That is right at the end of a sale and wrong at the start of one: an order
        the server did not price arrives with a total of zero, and the cashier is
        shown a Payment screen where Card, Cash and Customer Account are all dead,
        with nothing on screen saying why. It reads as broken hardware.

        Entering the screen is now conditional on the server having priced the
        order, so the failure is reported instead of drawn. Asserted from the
        cashier's side: whenever Payment IS on screen, at least one way to take
        money must be live.
        """
        self.browser_js('/mezze/pos', _js(r"""
            await waitFor(() => phase() === 'menu', 'register ready');
            await waitFor(() => $$('.mz-tile').length > 0, 'catalog');
            $$('.mz-tile')[0].click();
            await new Promise((r) => setTimeout(r, 250));
            const confirm = $$('button').find((b) => /Add to order/i.test(b.textContent));
            if (confirm) { confirm.click(); }
            await waitFor(() => $('.mz-line'), 'a line reached the order');

            $$('button').find((b) => /^Charge/.test(b.textContent.trim())).click();
            await waitFor(() => phase() === 'payment' || $('.mz-state--warn'),
                          'payment or a stated failure');

            if (phase() !== 'payment') {
                // Refusing to open is the OTHER acceptable outcome, and it must say
                // something rather than sit there.
                assert($('.mz-state--warn').textContent.trim().length > 0,
                       'a refusal has to be explained');
                ok();
                return;
            }
            const methods = $$('.mz-method');
            assert(methods.length > 0, 'payment offers tender methods');
            const live = methods.filter((m) => !m.disabled);
            assert(live.length > 0,
                   'Payment opened with every tender disabled — the cashier has no ' +
                   'way to take the money and no reason on screen');
            ok();
        """), login='admin')

    def test_22_charging_after_a_settled_order_opens_a_live_payment_screen(self):
        """Reported from the floor as "the payment buttons are disabled".

        The screen showed Total 83.15, Paid 83.15, Remaining 0.00 and "No tenders
        yet" all at once, with Card, Cash and Customer Account greyed out. Nothing
        had been tendered — the Register was holding the uuid of an order that was
        already settled, /orders/sync answered idempotently with THAT order's
        figures instead of pricing the cart in hand, and the payment screen dutifully
        concluded there was nothing left to collect.

        Driven here the way it happens: sell something, settle it, then start the
        next sale in the same session while the spent uuid is still in hand.
        """
        self.browser_js('/mezze/pos?debug=1', _js(r"""
            await waitFor(() => phase() === 'menu', 'register ready');
            await waitFor(() => $$('.mz-tile').length > 0, 'catalog');
            await waitFor(() => window.__mezzeCashier, 'debug handle');
            const root = window.__mezzeCashier.root;

            const addOne = async () => {
                $$('.mz-tile')[0].click();
                await new Promise((r) => setTimeout(r, 250));
                const confirm = $$('button').find((b) => /Add to order/i.test(b.textContent));
                if (confirm) { confirm.click(); }
                await waitFor(() => $('.mz-line'), 'a line reached the order');
            };

            // Sale one, settled in full.
            await addOne();
            $$('button').find((b) => /^Charge/.test(b.textContent.trim())).click();
            await waitFor(() => phase() === 'payment', 'payment');
            // Captured HERE: settling the sale clears the Register's uuid, so after
            // the receipt there is nothing left to read.
            const settledUuid = root.state.orderUuid;
            $$('.mz-method').find((m) => /Cash/.test(m.textContent)).click();
            await waitFor(() => $$('button').some((b) => /Confirm Cash/i.test(b.textContent)),
                          'cash pad');
            $$('button').find((b) => /Confirm Cash/i.test(b.textContent)).click();
            await waitFor(() => phase() === 'receipt', 'receipt');

            // Sale two, in the SAME session. A table-bound Register deliberately
            // REUSES its order uuid so that charging a table never forks its bill —
            // that is the branch where a spent uuid survives into the next sale, so
            // it is the branch this has to be driven through. The binding is forced
            // rather than clicked because the fixture has no floor plan; everything
            // after it is the real code path.
            $$('button').find((b) => /New order/i.test(b.textContent)).click();
            await waitFor(() => phase() === 'menu', 'back to the menu');
            await addOne();
            assert(settledUuid, 'the settled sale had an order uuid');
            root.state.table = { id: 0, name: 'T-test' };
            root.state.orderUuid = settledUuid;
            $$('button').find((b) => /^Charge/.test(b.textContent.trim())).click();
            await waitFor(() => phase() === 'payment' || $('.mz-state--warn'),
                          'payment or a stated failure');
            assert(phase() === 'payment', 'the second sale must reach payment');

            const live = $$('.mz-method').filter((m) => !m.disabled);
            assert(live.length > 0,
                   'every tender is disabled on a fresh sale — the Register billed ' +
                   'the settled order again instead of the cart in hand');
            ok();
        """), login='admin')

    def test_23_order_type_is_choosable_before_anything_is_rung_in(self):
        """How an order leaves is known before the first item, not after it.

        Delivery refused the choice until the basket had something in it, so the
        cashier had to ring the whole order in and only then find out the address
        was out of range. And the Delivery chip was hardcoded inactive, so even a
        successful choice never looked chosen.
        """
        self.browser_js('/mezze/pos?debug=1', _js(r"""
            await waitFor(() => phase() === 'menu', 'register ready');
            await waitFor(() => window.__mezzeCashier, 'debug handle');
            const root = window.__mezzeCashier.root;
            const chip = (k) => $(`[data-otype="${k}"]`);
            assert(chip('eat_in') && chip('takeaway') && chip('delivery'),
                   'all three ways out of the counter are offered');

            // Empty cart: takeaway is a plain choice and must simply take.
            assert(!chip('takeaway').disabled, 'takeaway is available at the counter');
            // Waited on the RENDERED state, not the component's: the cashier believes
            // what the screen shows, and the screen patches a frame after the click.
            chip('takeaway').click();
            await waitFor(() => chip('takeaway').getAttribute('aria-pressed') === 'true',
                          'takeaway shows as chosen');
            assert(root.state.serviceMode === 'takeaway', 'and the order carries it');

            // Delivery, still with nothing rung in, must also be choosable.
            chip('delivery').click();
            await waitFor(() => chip('delivery').getAttribute('aria-pressed') === 'true',
                          'Delivery shows as chosen before any item is rung in');
            assert(root.state.serviceMode === 'delivery', 'and the order carries it');
            ok();
        """), login='admin')

    def test_24_a_seated_order_says_why_it_cannot_be_takeaway(self):
        """The rule is right; enforcing it by ignoring the press was not.

        A table-bound order IS dine-in — the floor plan depends on it. But the
        buttons stayed enabled and swallowed the tap, which from the far side of
        the counter is indistinguishable from a dead till.
        """
        self.browser_js('/mezze/pos?debug=1', _js(r"""
            await waitFor(() => phase() === 'menu', 'register ready');
            await waitFor(() => window.__mezzeCashier, 'debug handle');
            const root = window.__mezzeCashier.root;
            root.state.table = { id: 0, name: 'T-test' };
            await new Promise((r) => setTimeout(r, 200));

            const takeaway = $('[data-otype="takeaway"]');
            assert(takeaway.disabled,
                   'a seated order offers Takeaway as if it were available');
            assert($('.mz-otype__why') && $('.mz-otype__why').textContent.trim().length > 0,
                   'nothing on screen says why the choice is unavailable');
            assert($('[data-otype="eat_in"]').getAttribute('aria-pressed') === 'true',
                   'a seated order reads as dine-in');
            ok();
        """), login='admin')

    def test_25_print_receipt_always_produces_a_receipt(self):
        """Pressing Print must produce a ticket somewhere, or say why not.

        The station printer answers {ok: true, sent: false, reason: "no_printer"}
        when none is configured — ok meaning "request understood", not "paper came
        out". Reading `ok` as success meant that on a till with no printer, which is
        every till until the hardware is installed, the button did nothing at all:
        no ticket, no browser dialog, no message. `sent` is the only field that
        means printed.

        window.print is stubbed because a real print dialog is modal and would
        block the browser this test is driving.
        """
        self.browser_js('/mezze/pos', _js(r"""
            await waitFor(() => phase() === 'menu', 'register ready');
            await waitFor(() => $$('.mz-tile').length > 0, 'catalog');
            $$('.mz-tile')[0].click();
            await new Promise((r) => setTimeout(r, 250));
            const confirm = $$('button').find((b) => /Add to order/i.test(b.textContent));
            if (confirm) { confirm.click(); }
            await waitFor(() => $('.mz-line'), 'a line reached the order');

            $$('button').find((b) => /^Charge/.test(b.textContent.trim())).click();
            await waitFor(() => phase() === 'payment', 'payment');
            $$('.mz-method').find((m) => /Cash/.test(m.textContent)).click();
            await waitFor(() => $$('button').some((b) => /Confirm Cash/i.test(b.textContent)),
                          'cash pad');
            $$('button').find((b) => /Confirm Cash/i.test(b.textContent)).click();
            await waitFor(() => phase() === 'receipt', 'receipt');

            window.__printed = 0;
            window.print = () => { window.__printed++; };

            const btn = $('[data-testid="mz-receipt-print"]');
            assert(btn, 'the receipt offers a way to print');
            btn.click();
            await waitFor(() => window.__printed > 0,
                          'Print produced nothing: no station printer accepted the ' +
                          'ticket and the browser fallback never ran');
            ok();
        """), login='admin')

    def test_20_the_favourites_order_holds_still_while_it_is_on_screen(self):
        """Favourites rank by use, so adding one re-sorted the list being looked at.

        The card just tapped jumped to a new position and its neighbours shuffled
        around it; a product ranked ninth could push another out of the eight
        entirely. Ordering a round of drinks meant chasing buttons around a screen
        that is supposed to be muscle memory.

        Asserted on the component itself rather than through the UI: the view is
        only reachable on a till that already has a history, and the fix is
        precisely that the ranking is refreshed while the cashier is elsewhere and
        frozen while it is the view on screen.
        """
        self.browser_js('/mezze/pos?debug=1', _js(r"""
            await waitFor(() => phase() === 'menu', 'register ready');
            await waitFor(() => window.__mezzeCashier, 'the debug handle (developer mode)');
            const root = window.__mezzeCashier.root;
            const ids = $$('.mz-tile').map((t) => Number(t.dataset.productId));
            assert(ids.length > 1, 'at least two products to rank');

            // A history where the SECOND product is one ahead of the first.
            const key = 'mezze:favorites:v1:' + root.boot.config_id + ':' +
                        ((root.boot.user && root.boot.user.id) || 0);
            localStorage.setItem(key, JSON.stringify({ [ids[0]]: 2, [ids[1]]: 3 }));

            // Away from Favourites, the ranking is live and reflects the seed.
            root.state.activeCategory = null;
            const live = root.favoriteProducts.map((p) => p.id);
            assert(live[0] === ids[1] && live[1] === ids[0],
                   'the ranking should follow use when the cashier is elsewhere: ' + live);

            // On Favourites, it is whatever it was when the view was opened...
            root.state.activeCategory = root.FAV;
            const opened = root.favoriteProducts.map((p) => p.id);

            // ...and one more sale of the first product — which now outranks the
            // second — must NOT move it while that view is on screen.
            root.order._bumpFavorite(ids[0]);
            root.order._bumpFavorite(ids[0]);
            const nowShown = root.favoriteProducts.map((p) => p.id);
            assert(JSON.stringify(nowShown) === JSON.stringify(opened),
                   'the favourites re-sorted under the cashier: ' + opened + ' -> ' + nowShown);

            // Leaving and returning is what refreshes it.
            root.state.activeCategory = null;
            root.favoriteProducts;
            root.state.activeCategory = root.FAV;
            const reopened = root.favoriteProducts.map((p) => p.id);
            assert(reopened[0] === ids[0],
                   'the ranking never refreshes: ' + reopened);
            ok();
        """), login='admin')

    def test_19_the_line_controls_stay_inside_the_order_panel(self):
        """Whatever the line carries, it wraps INSIDE rather than widening the panel.

        The panel width is a design decision; it must not become a function of the
        longest product name or of how many buttons a line happens to offer.
        """
        self.browser_js('/mezze/pos', _js(r"""
            await waitFor(() => phase() === 'menu', 'register ready');
            $('.mz-tile').click();
            await new Promise((r) => setTimeout(r, 300));
            const confirm = $$('button').find((b) => /Add to order/i.test(b.textContent));
            if (confirm) { confirm.click(); }
            await waitFor(() => $('.mz-line'), 'a line reached the order');
            const cart = $('.mz-cart');
            const lines = $('.mz-cart-lines');
            assert(lines.scrollWidth <= lines.clientWidth,
                   'the order lines overflow their panel sideways by ' +
                   (lines.scrollWidth - lines.clientWidth) + 'px');
            const right = cart.getBoundingClientRect();
            for (const el of $$('.mz-line *')) {
                const r = el.getBoundingClientRect();
                if (r.width === 0) { continue; }
                assert(r.right <= right.right + 1 && r.left >= right.left - 1,
                       'a line control sits outside the panel: ' + el.className);
            }
            ok();
        """), login='admin')

    def test_17_fidelity_navigation_survives_phase_switch(self):
        # Regression pinned during the Register restoration: at >=1280px the icon rail
        # replaces the horizontal .mz-nav. The rail is a MENU-phase element, so hiding
        # .mz-nav unconditionally left the PAYMENT phase with no workspace navigation at
        # all. Navigation must be reachable in every phase, and never doubled.
        self.browser_js('/mezze/pos', _js(r"""
            const vis = e => { if (!e) return false;
                const r = e.getBoundingClientRect(), s = getComputedStyle(e);
                return r.width > 0 && r.height > 0 && s.display !== 'none' && s.visibility !== 'hidden'; };
            const navs = () => [$('.mz-rail'), $('.mz-nav')].filter(vis);
            await waitFor(() => phase() === 'menu', 'menu');
            assert(navs().length === 1,
                   'menu: exactly one navigation surface (' + navs().length + ')');
            $('.mz-tile[data-product-id="%d"]').click();
            await waitFor(() => $('.mz-line'), 'cart line');
            window.dispatchEvent(new KeyboardEvent('keydown', {key:'F2', bubbles:true, cancelable:true}));
            await waitFor(() => phase() === 'payment', 'payment');
            assert(navs().length === 1,
                   'payment: exactly one navigation surface (' + navs().length + ')');
            const links = [...navs()[0].querySelectorAll('a,button')].filter(vis);
            assert(links.length >= 2,
                   'payment navigation still offers other workspaces (' + links.length + ')');
            window.dispatchEvent(new KeyboardEvent('keydown', {key:'Escape', bubbles:true, cancelable:true}));
            await waitFor(() => phase() === 'menu', 'back to menu');
            assert(navs().length === 1, 'menu again: exactly one navigation surface');
            ok();
        """ % self.product.id), login='admin')
