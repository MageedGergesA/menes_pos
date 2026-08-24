# -*- coding: utf-8 -*-
"""Taking a tip at the till.

Mezze could already put a tip on a bill and only a GUEST could do it: the QR path
took one, and the cashier had no way. On a card that is the common case rather than
the rare one — the slip comes back with a figure written on it and somebody has to
put it in the till.

The mechanics are core's on purpose: a line on the native tip product, plus
``is_tipped``/``tip_amount``, which is what Odoo's reports and the session close
already read. What Mezze adds is the part a browser cannot be trusted with, and one
refusal that is the whole reason this was worth doing carefully:

**A post-payment tip on an integrated terminal is refused.** The amount the provider
captured is the authoritative one. Writing a larger figure into Odoo makes the day's
takings disagree with the settlement file, and the difference surfaces a month later
as a variance nobody can trace back to a Tuesday. Cash and manual tenders are
different — there the cashier IS the authority on what was collected.
"""
import json

from odoo.tests import tagged

from .common import MezzeHttpCase


@tagged('post_install', '-at_install', 'mezze_tips')
class TestTipsFromTill(MezzeHttpCase):
    fixture_profile = 'POS'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        env['ir.config_parameter'].sudo().set_param('mezze_bridge.api_token', 'tp-tok')
        # /mezze/pos resolves its branch from here; without it the page boots with
        # no config and the app never mounts.
        env['ir.config_parameter'].sudo().set_param(
            'mezze_bridge.default_branch_id', str(cls.pos_config.id))
        cls.cash = cls.pos_config.payment_method_ids.filtered('is_cash_count')[:1]
        cls.card = cls.pos_config.payment_method_ids.filtered(
            lambda m: not m.is_cash_count)[:1]
        # BEFORE the session opens: Odoo refuses to modify a payment method while
        # one is running, so configuring it later silently fails and the terminal
        # test would pass by never being a terminal.
        if not cls.card:
            cls.card = env['pos.payment.method'].sudo().create(
                {'name': 'TP Card', 'company_id': cls.pos_config.company_id.id})
            cls.pos_config.sudo().write({'payment_method_ids': [(4, cls.card.id)]})
        cls.card.sudo().write({'mezze_mode': 'odoo_terminal'})
        cls.pos_sess = cls._open_session_for(cls.pos_config)
        cls.dish = env['product.product'].sudo().create({
            'name': 'TP Plate', 'available_in_pos': True, 'list_price': 100.0,
            'type': 'consu'})
        cls.dish.write({'taxes_id': [(5, 0, 0)]})
        cls.product.write({'available_in_pos': True, 'taxes_id': [(5, 0, 0)]})
        env.flush_all()

    def _post(self, path, body):
        r = self.url_open('/mezze/api/v1' + path,
                          data=json.dumps(dict(body, token='tp-tok')),
                          headers={'Content-Type': 'application/json'})
        try:
            return r.status_code, r.json()
        except Exception:  # noqa: BLE001
            return r.status_code, {'raw': r.text[:200]}

    def _order(self, uuid='tp-1', paid_by=None):
        order = self.env['pos.order'].sudo().create({
            'session_id': self.pos_sess.id, 'uuid': uuid,
            'company_id': self.pos_config.company_id.id,
            'lines': [(0, 0, {'product_id': self.dish.id, 'qty': 1,
                              'price_unit': 100.0, 'price_subtotal': 100.0,
                              'price_subtotal_incl': 100.0, 'tax_ids': [(6, 0, [])]})],
            'amount_total': 100.0, 'amount_paid': 0.0, 'amount_tax': 0.0,
            'amount_return': 0.0})
        if paid_by:
            self.env['pos.payment'].sudo().create({
                'pos_order_id': order.id, 'amount': 100.0,
                'payment_method_id': paid_by.id})
            order.write({'state': 'paid', 'amount_paid': 100.0})
        self.env.flush_all()
        return order

    def _tip_line(self, order):
        order.invalidate_recordset()
        tp = self.pos_config.tip_product_id
        return order.lines.filtered(lambda l: tp and l.product_id == tp)

    # ── before the tender ────────────────────────────────────────────────
    def test_01_a_cashier_can_add_a_tip(self):
        # THE gap. Only the guest could do this.
        order = self._order('tp-add')
        code, res = self._post('/orders/tip', {'order_id': order.id, 'amount': 15.0})
        self.assertEqual(code, 200, res)
        self.assertAlmostEqual(res['tip'], 15.0, places=2)
        self.assertTrue(self._tip_line(order), 'no tip line was written')

    def test_02_it_reconciles_through_core_fields(self):
        # So the session close and every Odoo report see it without knowing Mezze.
        order = self._order('tp-core')
        self._post('/orders/tip', {'order_id': order.id, 'amount': 12.0})
        order.invalidate_recordset()
        self.assertTrue(order.is_tipped)
        self.assertAlmostEqual(order.tip_amount, 12.0, places=2)

    def test_03_the_bill_grows_by_the_tip(self):
        order = self._order('tp-total')
        self._post('/orders/tip', {'order_id': order.id, 'amount': 20.0})
        order.invalidate_recordset()
        self.assertAlmostEqual(order.amount_total, 120.0, places=2)

    def test_04_changing_it_replaces_rather_than_stacks(self):
        # A cashier correcting 5.00 to 15.00 must not have given away 20.00.
        order = self._order('tp-fix')
        self._post('/orders/tip', {'order_id': order.id, 'amount': 5.0})
        self._post('/orders/tip', {'order_id': order.id, 'amount': 15.0})
        order.invalidate_recordset()
        self.assertEqual(len(self._tip_line(order)), 1, 'two tip lines on one bill')
        self.assertAlmostEqual(order.tip_amount, 15.0, places=2)
        self.assertAlmostEqual(order.amount_total, 115.0, places=2)

    def test_05_zero_clears_it(self):
        order = self._order('tp-zero')
        self._post('/orders/tip', {'order_id': order.id, 'amount': 10.0})
        self._post('/orders/tip', {'order_id': order.id, 'amount': 0})
        order.invalidate_recordset()
        self.assertFalse(self._tip_line(order))
        self.assertFalse(order.is_tipped)
        self.assertAlmostEqual(order.amount_total, 100.0, places=2)

    # ── the guards ───────────────────────────────────────────────────────
    def test_10_a_negative_tip_is_refused(self):
        # A negative tip is a discount wearing a disguise, and discounts have their
        # own ceilings and approvals.
        order = self._order('tp-neg')
        code, res = self._post('/orders/tip', {'order_id': order.id, 'amount': -5})
        self.assertEqual(code, 400)
        self.assertEqual(res['error'], 'negative_tip')

    def test_11_a_typo_larger_than_the_bill_is_refused(self):
        # 500 meant as 5.00. Core warns; a warning on a busy till is a thing people
        # learn to tap through.
        order = self._order('tp-typo')
        code, res = self._post('/orders/tip', {'order_id': order.id, 'amount': 500.0})
        self.assertEqual(code, 400)
        self.assertEqual(res['error'], 'tip_implausible')
        self.assertAlmostEqual(res['ceiling'], 100.0, places=2)

    def test_12_nonsense_is_refused(self):
        order = self._order('tp-nan')
        code, res = self._post('/orders/tip', {'order_id': order.id, 'amount': 'lots'})
        self.assertEqual(code, 400)
        self.assertEqual(res['error'], 'bad_amount')

    # ── after the tender ─────────────────────────────────────────────────
    def test_20_a_cash_order_can_be_tipped_after_payment(self):
        order = self._order('tp-post-cash', paid_by=self.cash)
        code, res = self._post('/orders/tip', {'order_id': order.id, 'amount': 10.0})
        self.assertEqual(code, 200, res)
        self.assertTrue(res['after_payment'])
        order.invalidate_recordset()
        self.assertAlmostEqual(order.amount_total, 110.0, places=2)

    def test_21_the_payment_grows_with_it(self):
        # Otherwise the order reads as underpaid for ever.
        order = self._order('tp-post-pay', paid_by=self.cash)
        self._post('/orders/tip', {'order_id': order.id, 'amount': 10.0})
        order.invalidate_recordset()
        self.assertAlmostEqual(sum(order.payment_ids.mapped('amount')), 110.0,
                               places=2)

    def test_22_an_integrated_terminal_payment_is_refused(self):
        """THE rule. The provider's captured amount is the authoritative one."""
        self.assertEqual(self.card.mezze_mode, 'odoo_terminal',
                         'the fixture card is not an integrated terminal, so this '
                         'test would pass without testing anything')
        order = self._order('tp-post-term', paid_by=self.card)
        code, res = self._post('/orders/tip', {'order_id': order.id, 'amount': 10.0})
        self.assertEqual(code, 409, res)
        self.assertEqual(res['error'], 'tip_needs_provider_capture')
        order.invalidate_recordset()
        self.assertAlmostEqual(
            sum(order.payment_ids.mapped('amount')), 100.0, places=2,
            msg='Odoo now claims more was captured than the provider confirmed')

    def test_23_a_settled_order_is_tipped_once(self):
        order = self._order('tp-post-twice', paid_by=self.cash)
        self._post('/orders/tip', {'order_id': order.id, 'amount': 10.0})
        code, res = self._post('/orders/tip', {'order_id': order.id, 'amount': 10.0})
        self.assertEqual(code, 409)
        self.assertEqual(res['error'], 'already_tipped')
        order.invalidate_recordset()
        self.assertAlmostEqual(sum(order.payment_ids.mapped('amount')), 110.0,
                               places=2, msg='the guest was tipped twice')

    def test_24_it_is_audited(self):
        order = self._order('tp-audit', paid_by=self.cash)
        self._post('/orders/tip', {'order_id': order.id, 'amount': 7.0})
        rows = self.env['mezze.audit.log'].sudo().search(
            [('event', '=', 'order.tip')])
        self.assertTrue(rows, 'a tip changed the takings and left no audit row')


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
async function ringUpAndCharge(){
  await waitFor(() => $$('.mz-tile').length > 0, 'catalog');
  $$('.mz-tile')[0].click();
  await waitFor(() => $$('.mz-line').length > 0, 'a line in the cart');
  const charge = $$('button').find(b => /charge|pay/i.test(b.textContent||''));
  assert(charge, 'a Charge control exists');
  charge.click();
  await waitFor(() => phase() === 'payment', 'the payment screen');
}
"""


def _js(body):
    return _PRELUDE + "\n(async () => {\n" + body + "\n})().catch(e => { console.error(e.message || e); });"


@tagged('post_install', '-at_install', 'mezze_browser', 'mezze_tips')
class TestTipsUi(TestTipsFromTill):
    """The half the row was actually about: a cashier who can reach it.

    The endpoint above is only half the fix — Product Info and weighed selling both
    taught the same lesson this campaign, that a server rule nothing can reach does
    not close a row.
    """

    def test_30_the_payment_screen_offers_a_tip(self):
        self.browser_js('/mezze/pos', _js(r"""
            await waitFor(() => phase() === 'menu', 'register ready');
            await ringUpAndCharge();
            await waitFor(() => $('[data-testid="mz-tip"]'), 'the tip control');
            assert($$('[data-tip-pct]').length === 3, 'three suggestions');
            assert($('[data-testid="mz-tip-input"]'), 'and a typed amount');
            ok();
        """), login='admin')

    def test_31_a_suggestion_puts_a_tip_on_the_bill(self):
        self.browser_js('/mezze/pos', _js(r"""
            await waitFor(() => phase() === 'menu', 'register ready');
            await ringUpAndCharge();
            await waitFor(() => $('[data-tip-pct]'), 'the suggestions');
            $('[data-tip-pct]').click();
            await waitFor(() => $('[data-testid="mz-tip-amount"]'), 'the tip is shown');
            ok();
        """), login='admin')

    def test_32_the_tip_reaches_the_database(self):
        self.browser_js('/mezze/pos', _js(r"""
            await waitFor(() => phase() === 'menu', 'register ready');
            await ringUpAndCharge();
            await waitFor(() => $('[data-testid="mz-tip-input"]'), 'the typed field');
            const inp = $('[data-testid="mz-tip-input"]');
            const setter = Object.getOwnPropertyDescriptor(
                window.HTMLInputElement.prototype, 'value').set;
            setter.call(inp, '7');
            inp.dispatchEvent(new Event('change', {bubbles:true}));
            await waitFor(() => $('[data-testid="mz-tip-amount"]'), 'the tip is shown');
            ok();
        """), login='admin')
        self.env.invalidate_all()
        order = self.env['pos.order'].sudo().search(
            [('is_tipped', '=', True)], order='id desc', limit=1)
        self.assertTrue(order, 'no tipped order was written')
        self.assertAlmostEqual(order.tip_amount, 7.0, places=2)
