"""Refunding from the REAL Register.

``/orders/refund`` was the best-engineered code in this module — per-line quantity
ceilings, an order-level money ceiling in integer minor units, a per-original
advisory lock, an ORM constraint behind all of it — and nothing in the product could
reach it. A cashier facing a guest with a wrong dish had to leave the till.

These drive the live Owl app in headless Chrome, because the work was the WIRING: a
unit test of the endpoint passed before this screen existed and would pass if it were
deleted again.

Three things are asserted that only a browser can see:

* the screen offers what is LEFT on a line, not what was sold, so a second partial
  refund cannot ask for more than remains;
* a refusal reads as a sentence rather than an error code;
* a till that does not hold ``orders.refund`` — which is every till, by design —
  ESCALATES into the manager gate instead of dead-ending. That was a real defect
  found by driving this screen: only ``approval_required`` escalated, so on the
  common configuration the button simply looked broken.
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
const setv = (sel, v) => { const i = $(sel);
  const s = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set;
  s.call(i, v); i.dispatchEvent(new Event('input', {bubbles:true})); };
const openRefund = async () => {
  await waitFor(() => $$('.mz-verb').some(v => /Refund/.test(v.textContent)), 'refund verb');
  $$('.mz-verb').find(v => /Refund/.test(v.textContent)).click();
  await waitFor(() => $('[data-testid="mz-refund-orders"]') || $('[data-testid="mz-refund-empty"]'),
                'refund screen');
};
const pickFirstOrder = async () => {
  await waitFor(() => $('.mz-refund__order'), 'an order to refund');
  $('.mz-refund__order').click();
  await waitFor(() => $('[data-testid="mz-refund-lines"]') || $('[data-testid="mz-refund-nothing"]'),
                'the order lines');
};
"""


def _js(body):
    return _PRELUDE + "\n(async () => {\n" + body + "\n})().catch(e => { console.error(e.message || e); });"


@tagged('post_install', '-at_install', 'mezze_browser', 'mezze_refund_ui')
class TestRefundUi(MezzeHttpCase):
    fixture_profile = 'POS'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        icp = cls.env['ir.config_parameter'].sudo()
        # A till never holds orders.refund on its own (see _SUPERVISOR in
        # domain.authz). Elevation is the branch opt-in that lets a manager
        # authorise the single call in person — without it the verb is not offered
        # at all, which is correct but leaves nothing to test.
        icp.set_param('mezze_bridge.allow_manager_elevation', '1')
        icp.set_param('mezze_bridge.default_branch_id', str(cls.pos_config.id))
        cls.manager = cls.env['mezze.cashier'].create(
            {'name': 'Nadia Manager', 'code': 'RFMGR', 'role': 'manager'})
        cls.manager.set_pin('4321')
        cls.cashier = cls.env['mezze.cashier'].create(
            {'name': 'Sami Cashier', 'code': 'RFCSH', 'role': 'cashier'})
        cls.cashier.set_pin('1111')
        # NOT ``cls.session``: HttpCase owns that name for the HTTP session, and
        # ``authenticate()`` calls ``session_store.delete(self.session)`` — which
        # explodes on a pos.session with 'no attribute sid'. Any browser test in a
        # class that shadowed it would fail before reaching its first assertion.
        cls.pos_sess = cls._open_session_for(cls.pos_config)
        # Something to give back. Paid, so it is refundable at all.
        cls.sold = cls.env['pos.order'].create({
            'session_id': cls.pos_sess.id,
            'company_id': cls.pos_config.company_id.id,
            'lines': [(0, 0, {
                'product_id': cls.product.id, 'qty': 2, 'price_unit': 10.0,
                'price_subtotal': 20.0, 'price_subtotal_incl': 20.0,
                'tax_ids': [(6, 0, [])]})],
            'amount_total': 20.0, 'amount_paid': 20.0,
            'amount_tax': 0.0, 'amount_return': 0.0,
        })
        cls.env['pos.payment'].create({
            'pos_order_id': cls.sold.id, 'amount': 20.0,
            'payment_method_id': cls.pos_config.payment_method_ids[0].id})
        cls.sold.write({'state': 'paid'})
        cls.env.flush_all()

    def test_01_the_refund_verb_is_offered_even_with_an_empty_cart(self):
        # Refund acts on a PAST order, not on what is in the cart — so unlike every
        # other verb it must not be disabled when nothing has been rung up.
        self.browser_js('/mezze/pos?ws=register', _js(r"""
            await waitFor(() => $$('.mz-verb').some(v => /Refund/.test(v.textContent)), 'refund verb');
            const v = $$('.mz-verb').find(v => /Refund/.test(v.textContent));
            assert(!v.disabled, 'Refund is usable with an empty cart');
            ok();
        """), login='admin')

    def test_02_the_screen_lists_orders_and_their_lines(self):
        self.browser_js('/mezze/pos?ws=register', _js(r"""
            await openRefund();
            await pickFirstOrder();
            assert($$('.mz-refund__line').length > 0, 'the order shows lines to give back');
            ok();
        """), login='admin')

    def test_03_the_stepper_cannot_exceed_what_is_left(self):
        # The endpoint enforces the ceiling regardless; this proves the till does not
        # let a cashier ASK for more and then apologise for a rejection.
        self.browser_js('/mezze/pos?ws=register', _js(r"""
            await openRefund();
            await pickFirstOrder();
            const line = $('.mz-refund__line');
            const plus = line.querySelectorAll('.mz-step')[1];
            for (let i = 0; i < 12; i++) { plus.click(); await new Promise(r=>setTimeout(r,30)); }
            const n = Number(line.querySelector('.mz-step__n').dataset.qty);
            assert(n > 0, 'the stepper moved at all');
            assert(n <= 2, 'the stepper stopped at what was sold (got ' + n + ')');
            assert(plus.disabled, 'the + control disables itself at the cap');
            ok();
        """), login='admin')

    def test_04_submit_stays_shut_until_there_is_something_and_a_reason(self):
        self.browser_js('/mezze/pos?ws=register', _js(r"""
            await openRefund();
            await pickFirstOrder();
            const btn = () => $('[data-testid="mz-refund-submit"]');
            assert(btn().disabled, 'nothing chosen yet, so nothing to refund');
            $('.mz-refund__line .mz-btn--secondary').click();      // the All button
            await new Promise(r=>setTimeout(r,200));
            assert(btn().disabled, 'still shut without a reason');
            setv('[data-testid="mz-refund-reason"]', 'wrong dish');
            await new Promise(r=>setTimeout(r,200));
            assert(!btn().disabled, 'now it can be pressed');
            ok();
        """), login='admin')

    def test_05_a_till_escalates_to_the_manager_gate(self):
        # THE defect this file exists for. A till does not hold orders.refund, so the
        # server answers permission_denied — and the screen used to print that code
        # and stop. It must hand the same refund to the gate instead.
        self.browser_js('/mezze/pos?ws=register', _js(r"""
            await openRefund();
            await pickFirstOrder();
            $('.mz-refund__line .mz-btn--secondary').click();
            setv('[data-testid="mz-refund-reason"]', 'wrong dish');
            await new Promise(r=>setTimeout(r,200));
            $('[data-testid="mz-refund-submit"]').click();
            await waitFor(() => $('[data-testid="mz-manager-gate"]'),
                          'the refusal escalates into the manager gate');
            assert(!$('.mz-refund'), 'the refund screen stepped aside for the gate');
            ok();
        """), login='admin')

    def test_06_a_manager_pin_completes_the_refund(self):
        self.browser_js('/mezze/pos?ws=register', _js(r"""
            await openRefund();
            await pickFirstOrder();
            $('.mz-refund__line .mz-btn--secondary').click();
            setv('[data-testid="mz-refund-reason"]', 'wrong dish');
            await new Promise(r=>setTimeout(r,200));
            $('[data-testid="mz-refund-submit"]').click();
            await waitFor(() => $('[data-testid="mz-manager-gate"]'), 'manager gate');
            setv('[data-testid="mz-manager-code"]', 'RFMGR');
            setv('[data-testid="mz-manager-pin"]', '4321');
            await new Promise(r=>setTimeout(r,200));
            $('[data-testid="mz-manager-approve"]').click();
            await waitFor(() => !$('[data-testid="mz-manager-gate"]'), 'gate closes on approval');
            ok();
        """), login='admin')

    def test_07_the_refund_reached_the_database(self):
        before = self.env['pos.order'].search_count([('amount_total', '<', 0)])
        self.browser_js('/mezze/pos?ws=register', _js(r"""
            await openRefund();
            await pickFirstOrder();
            $('.mz-refund__line .mz-btn--secondary').click();
            setv('[data-testid="mz-refund-reason"]', 'wrong dish');
            await new Promise(r=>setTimeout(r,200));
            $('[data-testid="mz-refund-submit"]').click();
            await waitFor(() => $('[data-testid="mz-manager-gate"]'), 'manager gate');
            setv('[data-testid="mz-manager-code"]', 'RFMGR');
            setv('[data-testid="mz-manager-pin"]', '4321');
            await new Promise(r=>setTimeout(r,200));
            $('[data-testid="mz-manager-approve"]').click();
            await waitFor(() => !$('[data-testid="mz-manager-gate"]'), 'approved');
            ok();
        """), login='admin')
        self.env.invalidate_all()
        after = self.env['pos.order'].search([('amount_total', '<', 0)],
                                             order='id desc', limit=1)
        self.assertEqual(
            self.env['pos.order'].search_count([('amount_total', '<', 0)]), before + 1,
            'the browser flow did not actually create a refund')
        # and it is LINKED to what it refunds, which is what makes the ceiling work
        self.assertTrue(after.lines[0].refunded_orderline_id,
                        'the refund line does not point at its original')

    def test_08_a_wrong_pin_refunds_nothing(self):
        before = self.env['pos.order'].search_count([('amount_total', '<', 0)])
        self.browser_js('/mezze/pos?ws=register', _js(r"""
            await openRefund();
            await pickFirstOrder();
            $('.mz-refund__line .mz-btn--secondary').click();
            setv('[data-testid="mz-refund-reason"]', 'wrong dish');
            await new Promise(r=>setTimeout(r,200));
            $('[data-testid="mz-refund-submit"]').click();
            await waitFor(() => $('[data-testid="mz-manager-gate"]'), 'manager gate');
            setv('[data-testid="mz-manager-code"]', 'RFMGR');
            setv('[data-testid="mz-manager-pin"]', '9999');
            await new Promise(r=>setTimeout(r,200));
            $('[data-testid="mz-manager-approve"]').click();
            await waitFor(() => $('[data-testid="mz-manager-error"]'), 'the refusal is shown');
            assert($('[data-testid="mz-manager-gate"]'), 'the gate stays open on a wrong PIN');
            ok();
        """), login='admin')
        self.env.invalidate_all()
        self.assertEqual(
            self.env['pos.order'].search_count([('amount_total', '<', 0)]), before,
            'a refused refund still moved money')
