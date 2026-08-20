"""SB2.7 — the Split Bill workspace in a real Chrome.

Everything the earlier phases proved, they proved by reading source or by calling
the server. This file is the first time the workspace is actually rendered, tapped
and driven, which is the only way to find out whether it mounts at all.

Tagged ``mezze_browser`` alongside the other Chrome suites so it can be selected or
skipped independently — headless Chrome is not reliably available everywhere, and a
suite that cannot run should say so rather than fail.
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
const money = (el) => parseFloat((el.textContent || '').replace(/[^0-9.\-]/g, '')) || 0;

/** Put one product in the cart, charge nothing — we only need a bill to split. */
async function seedCart(n){
  await waitFor(() => $$('.mz-tile').length > 0, 'catalog');
  for (let i = 0; i < (n || 1); i++) { $$('.mz-tile')[0].click(); }
  await waitFor(() => $$('.mz-line').length > 0, 'a line in the cart');
}

/** Open the Split workspace from the cart's action grid. */
async function openSplit(){
  const btn = $$('.mz-verb, .mz-cart-verb, button').find(
    (b) => /split|تقسيم/i.test(b.textContent || ''));
  assert(btn, 'a Split verb exists in the cart actions');
  btn.click();
  await waitFor(() => $('.mz-sb'), 'split workspace mounted');
}
"""


def _js(body):
    return _PRELUDE + "\n(async () => {\n" + body + "\n})().catch(e => { console.error(e.message || e); });"


@tagged('post_install', '-at_install', 'mezze_browser', 'mezze_split_browser')
class TestSplitBillBrowser(MezzeHttpCase):
    fixture_profile = 'POS'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Committed here, not in setUp: the HTTP worker serving /mezze/pos runs on its
        # own cursor and cannot see per-test writes.
        cls.product.write({'available_in_pos': True, 'list_price': 100.0, 'taxes_id': [(5, 0, 0)]})
        cls.pos_config.write({'payment_method_ids': [(4, cls.cash_payment_method.id)]})
        cls.env['ir.config_parameter'].sudo().set_param(
            'mezze_bridge.default_branch_id', str(cls.pos_config.id))
        sess = cls.pos_config.current_session_id
        if sess:
            if sess.state == 'opening_control':
                try:
                    sess.set_opening_control(0, None)
                except Exception:  # noqa: BLE001
                    pass
            if sess.state != 'opened':
                sess.sudo().write({'state': 'opened'})
        cls.env['res.lang'].sudo()._activate_lang('ar_001')
        cls.ar_user = cls.env['res.users'].sudo().create({
            'name': 'Mezze AR Split', 'login': 'mz_ar_split', 'lang': 'ar_001',
            'group_ids': [(6, 0, cls.env.ref('base.group_user').ids
                           + cls.env.ref('point_of_sale.group_pos_user').ids)],
        })
        cls.env.flush_all()

    # ------------------------------------------------------------------ mount
    def test_01_the_workspace_mounts(self):
        """The one that could not be proven by reading source."""
        self.browser_js('/mezze/pos', _js(r"""
            await waitFor(() => phase() === 'menu', 'register ready');
            await seedCart(3);
            await openSplit();
            assert($('.mz-sb__top'), 'header');
            assert($('.mz-sb__modes'), 'mode tabs');
            await waitFor(() => $$('.mz-sb__row').length > 0, 'lines listed');
            assert($('.mz-sb__foot'), 'footer with the totals and the CTA');
            ok();
        """), login='admin')

    def test_02_by_seat_is_offered_but_disabled_with_a_reason(self):
        self.browser_js('/mezze/pos', _js(r"""
            await waitFor(() => phase() === 'menu', 'register ready');
            await seedCart(1);
            await openSplit();
            const modes = $$('.mz-sb__mode');
            assert(modes.length === 3, 'three modes (' + modes.length + ')');
            const seat = modes[1];
            assert(seat.disabled, 'By seat is disabled, not hidden');
            assert((seat.title || '').length > 0, 'and says why');
            ok();
        """), login='admin')

    # ------------------------------------------------------------- selection
    def test_03_one_tap_moves_one_unit(self):
        """The speed target: a tap is a unit, with no quantity modal."""
        self.browser_js('/mezze/pos', _js(r"""
            await waitFor(() => phase() === 'menu', 'register ready');
            await seedCart(3);
            await openSplit();
            await waitFor(() => $('.mz-sb__row'), 'a row');
            const before = money($('.mz-sb__sum--new strong'));
            $('.mz-sb__rowbtn').click();
            await waitFor(() => money($('.mz-sb__sum--new strong')) > before, 'new check grew');
            assert($('.mz-sb__sel').textContent.trim() === '1', 'exactly one selected');
            assert(!$('.mz-modal'), 'no quantity modal appeared for qty 1');
            ok();
        """), login='admin')

    def test_04_the_two_totals_move_in_opposite_directions(self):
        self.browser_js('/mezze/pos', _js(r"""
            await waitFor(() => phase() === 'menu', 'register ready');
            await seedCart(3);
            await openSplit();
            await waitFor(() => $('.mz-sb__row'), 'a row');
            const rem0 = money($$('.mz-sb__sum strong')[0]);
            const new0 = money($('.mz-sb__sum--new strong'));
            $('.mz-sb__rowbtn').click();
            await waitFor(() => money($('.mz-sb__sum--new strong')) > new0, 'new check grew');
            const rem1 = money($$('.mz-sb__sum strong')[0]);
            assert(rem1 < rem0, 'remaining fell (' + rem0 + ' -> ' + rem1 + ')');
            ok();
        """), login='admin')

    def test_05_plus_and_minus_and_move_all(self):
        self.browser_js('/mezze/pos', _js(r"""
            await waitFor(() => phase() === 'menu', 'register ready');
            await seedCart(3);
            await openSplit();
            await waitFor(() => $('.mz-sb__row'), 'a row');
            const sel = () => $('.mz-sb__sel').textContent.trim();
            const steps = $$('.mz-sb__step');
            steps[1].click();                       // +
            await waitFor(() => sel() === '1', 'plus selected one');
            steps[1].click();
            await waitFor(() => sel() === '2', 'plus selected two');
            steps[0].click();                       // -
            await waitFor(() => sel() === '1', 'minus wound it back');
            $('.mz-sb__all').click();               // move all
            await waitFor(() => sel() === '3', 'move all took the rest (' + sel() + ')');
            ok();
        """), login='admin')

    def test_06_selection_cannot_exceed_what_is_there(self):
        self.browser_js('/mezze/pos', _js(r"""
            await waitFor(() => phase() === 'menu', 'register ready');
            await seedCart(2);
            await openSplit();
            await waitFor(() => $('.mz-sb__row'), 'a row');
            for (let i = 0; i < 6; i++) { $$('.mz-sb__step')[1].click(); }
            await new Promise(r => setTimeout(r, 300));
            const sel = parseInt($('.mz-sb__sel').textContent.trim(), 10);
            assert(sel <= 2, 'never more than the bill holds (got ' + sel + ')');
            ok();
        """), login='admin')

    def test_07_reset_and_cancel_change_nothing(self):
        self.browser_js('/mezze/pos', _js(r"""
            await waitFor(() => phase() === 'menu', 'register ready');
            await seedCart(3);
            const lines = $$('.mz-line').length;
            await openSplit();
            await waitFor(() => $('.mz-sb__row'), 'a row');
            $('.mz-sb__rowbtn').click();
            await waitFor(() => $('.mz-sb__sel').textContent.trim() === '1', 'selected');
            $$('.mz-sb__acts .mz-btn')[1].click();          // Reset
            await waitFor(() => $('.mz-sb__sel').textContent.trim() === '0', 'reset cleared it');
            $$('.mz-sb__acts .mz-btn')[0].click();          // Cancel
            await waitFor(() => !$('.mz-sb'), 'workspace closed');
            assert($$('.mz-line').length === lines, 'the cart is untouched');
            ok();
        """), login='admin')

    def test_08_the_cta_carries_the_amount_and_is_disabled_when_empty(self):
        self.browser_js('/mezze/pos', _js(r"""
            await waitFor(() => phase() === 'menu', 'register ready');
            await seedCart(2);
            await openSplit();
            await waitFor(() => $('.mz-sb__go'), 'primary action');
            assert($('.mz-sb__go').disabled, 'nothing selected -> nothing to press');
            $('.mz-sb__rowbtn').click();
            await waitFor(() => !$('.mz-sb__go').disabled, 'enabled once something is selected');
            assert(/[0-9]/.test($('.mz-sb__go').textContent),
                   'the button says what it costs: ' + $('.mz-sb__go').textContent);
            ok();
        """), login='admin')

    # ------------------------------------------------------------ a11y / RTL
    def test_09_rows_are_operable_from_the_keyboard(self):
        self.browser_js('/mezze/pos', _js(r"""
            await waitFor(() => phase() === 'menu', 'register ready');
            await seedCart(3);
            await openSplit();
            await waitFor(() => $('.mz-sb__rowbtn'), 'a row');
            const row = $('.mz-sb__rowbtn');
            row.focus();
            assert(document.activeElement === row, 'the row takes focus');
            row.dispatchEvent(new KeyboardEvent('keydown', {key: ' ', bubbles: true}));
            await waitFor(() => $('.mz-sb__sel').textContent.trim() === '1', 'Space selected one');
            row.dispatchEvent(new KeyboardEvent('keydown', {key: 'ArrowRight', bubbles: true}));
            await waitFor(() => $('.mz-sb__sel').textContent.trim() === '2', 'Arrow stepped up');
            ok();
        """), login='admin')

    def test_10_touch_targets_are_at_least_44px_in_the_browser(self):
        """Measured on the rendered box, not read off the stylesheet."""
        self.browser_js('/mezze/pos', _js(r"""
            await waitFor(() => phase() === 'menu', 'register ready');
            await seedCart(2);
            await openSplit();
            await waitFor(() => $('.mz-sb__step'), 'controls');
            for (const sel of ['.mz-sb__step', '.mz-sb__back', '.mz-sb__all', '.mz-sb__go']) {
                const el = $(sel);
                if (!el) continue;
                const r = el.getBoundingClientRect();
                assert(r.height >= 44, sel + ' is ' + Math.round(r.height) + 'px tall');
            }
            ok();
        """), login='admin')

    def test_11_arabic_renders_right_to_left(self):
        self.browser_js('/mezze/pos', _js(r"""
            await waitFor(() => phase() === 'menu', 'register ready');
            assert(document.documentElement.dir === 'rtl', 'page is RTL');
            await seedCart(2);
            await openSplit();
            await waitFor(() => $('.mz-sb__title'), 'split header');
            const title = $('.mz-sb__title').textContent.trim();
            assert(/[؀-ۿ]/.test(title), 'the title is Arabic: ' + title);
            // the marker must sit on the RIGHT edge of a mirrored row
            $('.mz-sb__rowbtn').click();
            await waitFor(() => $('.mz-sb__row--picked'), 'a picked row');
            const row = $('.mz-sb__row--picked');
            const mark = getComputedStyle(row, '::before');
            assert(mark.content !== 'none', 'the selected marker is drawn');
            ok();
        """), login='mz_ar_split', timeout=120)

    # ------------------------------------------------------------- responsive
    def test_12_the_footer_survives_a_1024_till(self):
        self.browser_js('/mezze/pos', _js(r"""
            await waitFor(() => phase() === 'menu', 'register ready');
            await seedCart(3);
            await openSplit();
            await waitFor(() => $('.mz-sb__foot'), 'footer');
            const foot = $('.mz-sb__foot');
            const r = foot.getBoundingClientRect();
            assert(r.width > 0 && r.height > 0, 'footer is visible');
            assert($$('.mz-sb__sum').length === 2, 'both totals still shown');
            assert($('.mz-sb__go'), 'and the primary action');
            // nothing may scroll the page sideways
            assert(document.documentElement.scrollWidth <= window.innerWidth + 2,
                   'no horizontal overflow (' + document.documentElement.scrollWidth +
                   ' vs ' + window.innerWidth + ')');
            ok();
        """), login='admin')


    def test_14_split_pay_then_split_again_does_not_crash_the_till(self):
        """The full cycle, in one go — and the crash a real cashier hit.

        Pressing Split again after paying a child destroyed the root component:
        the receipt data was cleared while the receipt phase was still mounted,
        and Owl rendered in that gap because there is an await between them. The
        till went blank. This drives the whole path: split, pay, split again.
        """
        self.browser_js('/mezze/pos', _js(r"""
            const errs = [];
            window.addEventListener('error', e => errs.push(e.message));
            window.addEventListener('unhandledrejection', e => errs.push(String(e.reason)));

            await waitFor(() => phase() === 'menu', 'register ready');
            await seedCart(3);
            await openSplit();
            await waitFor(() => $('.mz-sb__rowbtn'), 'a row');
            $('.mz-sb__rowbtn').click();
            await waitFor(() => !$('.mz-sb__go').disabled, 'something selected');
            $('.mz-sb__go').click();

            // Split & pay hands the CHILD straight to Payment.
            await waitFor(() => phase() === 'payment', 'payment for the child');
            const cash = $('.mz-method[data-method-mode="cash"]');
            assert(cash, 'a cash method');
            cash.click();
            await waitFor(() => $('.mz-tender'), 'tender dialog');
            const exact = $$('.mz-quick').find(b => /exact/i.test(b.textContent));
            assert(exact, 'Exact quick-cash');
            exact.click();
            $('.mz-btn--confirm').click();
            await waitFor(() => phase() === 'receipt', 'receipt');

            // ...and the family actions, not a blank till.
            const again = $$('.mz-sb__afteracts .mz-btn').find(
                b => /again|مرة أخرى/i.test(b.textContent));
            assert(again, 'Split again is offered after a child is paid');
            again.click();

            await waitFor(() => phase() === 'menu', 'back on the till');
            assert($('.mz-app'), 'the root component survived');
            assert(!errs.some(e => /lifecycle|Destroying the root/i.test(e)),
                   'Owl error during the transition: ' + errs.join(' | '));
            ok();
        """), login='admin', timeout=180)


@tagged('post_install', '-at_install', 'mezze_browser', 'mezze_split_browser')
class TestSplitBillBrowser1024(TestSplitBillBrowser):
    """The same workspace on a small till. Two panes must not become two slivers."""
    browser_size = '1024,768'

    def test_13_narrow_stacks_rather_than_squeezes(self):
        self.browser_js('/mezze/pos', _js(r"""
            await waitFor(() => phase() === 'menu', 'register ready');
            await seedCart(3);
            await openSplit();
            await waitFor(() => $('.mz-sb__panes'), 'panes');
            const panes = $$('.mz-sb__pane');
            assert(panes.length === 2, 'both panes exist');
            const a = panes[0].getBoundingClientRect();
            const b = panes[1].getBoundingClientRect();
            // stacked: the second starts below the first, not beside it
            assert(b.top >= a.top + 40, 'panes stack on a narrow till');
            assert(a.width > window.innerWidth * 0.8, 'and each gets the width');
            ok();
        """), login='admin')
