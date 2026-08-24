# -*- coding: utf-8 -*-
"""Typing a code, and paying with a gift card.

Mezze had a substantial loyalty back end — ``/loyalty/rewards|apply|remove``,
``/giftcard/issue|balance``, ``/promo/apply|list`` — and the register that ships
called **none of it**. Same shape as the Refund gap and the Z report: good code with
nothing able to reach it.

Two server pieces were genuinely missing, and both are about not making the till
guess:

* **One code box.** A guest hands over a slip. Nothing on it says whether it is a
  gift card, a coupon, or a promo code, and the cashier should not have to know.
  Without ``/codes/resolve`` the browser would have to try one engine, catch a 404,
  and try the next — so a genuinely bad code costs two round trips and reports
  whichever guess happened to run last, in that engine's vocabulary.

* **Gift card as a tender.** ``/orders/pay`` could not accept one at all. The card is
  spent at PAYMENT, against the balance that exists then — a balance read when the
  code was typed is a balance another till may have spent since.
"""
import json

from odoo.tests import tagged

from .common import MezzeHttpCase


@tagged('post_install', '-at_install', 'mezze_codes')
class TestCodesAndGiftCardTender(MezzeHttpCase):
    fixture_profile = 'POS'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        env['ir.config_parameter'].sudo().set_param('mezze_bridge.api_token', 'cd-tok')
        # Provision BEFORE the session opens, which is when a branch is provisioned in
        # reality: Odoo refuses to change a config's payment methods while a session
        # is open, and that is exactly why this moved out of the payment call.
        from ..models.loyalty_bootstrap import ensure_giftcard_payment_method
        ensure_giftcard_payment_method(env)
        cls.pos_sess = cls._open_session_for(cls.pos_config)
        cls.cash = cls.pos_config.payment_method_ids.filtered('is_cash_count')[:1]
        cls.product = env['product.product'].sudo().create({
            'name': 'CD Plate', 'available_in_pos': True, 'list_price': 100.0,
            'type': 'consu'})
        cls.product.write({'taxes_id': [(5, 0, 0)]})
        cls.gc_program = env['loyalty.program'].sudo().search(
            [('program_type', '=', 'gift_card')], limit=1) or \
            env['loyalty.program'].sudo().create(
                {'name': 'Mezze Gift Card', 'program_type': 'gift_card'})
        env.flush_all()

    # -- helpers ---------------------------------------------------------
    def _card(self, amount=50.0, code=None):
        vals = {'program_id': self.gc_program.id, 'points': amount}
        if code:
            vals['code'] = code
        return self.env['loyalty.card'].sudo().create(vals)

    def _order(self, total=100.0):
        o = self.env['pos.order'].sudo().create({
            'session_id': self.pos_sess.id,
            'company_id': self.pos_config.company_id.id,
            'lines': [(0, 0, {'product_id': self.product.id, 'qty': 1,
                              'price_unit': total, 'price_subtotal': total,
                              'price_subtotal_incl': total, 'tax_ids': [(6, 0, [])]})],
            'amount_total': total, 'amount_paid': 0.0,
            'amount_tax': 0.0, 'amount_return': 0.0})
        self.env.flush_all()
        return o

    def _post(self, path, body):
        r = self.url_open('/mezze/api/v1' + path,
                          data=json.dumps(dict(body, token='cd-tok')),
                          headers={'Content-Type': 'application/json'})
        return r.json()

    # -- one box, any code -----------------------------------------------
    def test_01_a_gift_card_code_is_recognised(self):
        card = self._card(50.0)
        order = self._order()
        d = self._post('/codes/resolve', {'code': card.code, 'order_uuid': order.uuid})
        self.assertTrue(d.get('ok'), d)
        self.assertEqual(d.get('kind'), 'gift_card')
        self.assertAlmostEqual(d.get('balance'), 50.0, places=2)
        self.assertTrue(d.get('usable'))

    def test_02_typing_a_gift_card_does_not_spend_it(self):
        # It is a tender, not a discount. Spending it on sight would take the money
        # before the sale exists, and the guest may still walk away.
        card = self._card(50.0)
        order = self._order()
        self._post('/codes/resolve', {'code': card.code, 'order_uuid': order.uuid})
        card.invalidate_recordset()
        self.assertAlmostEqual(card.points, 50.0, places=2,
                               msg='the card was spent merely by being typed')
        order.invalidate_recordset()
        self.assertAlmostEqual(order.amount_total, 100.0, places=2,
                               msg='a gift card must not discount the order')

    def test_03_an_unknown_code_says_so_once(self):
        order = self._order()
        d = self._post('/codes/resolve', {'code': 'NOTACODE-XYZ',
                                          'order_uuid': order.uuid})
        self.assertFalse(d.get('ok'))
        self.assertEqual(d.get('error'), 'unknown_code')
        self.assertIn('gift card', (d.get('message') or '').lower())

    def test_04_an_empty_code_is_refused_before_any_lookup(self):
        order = self._order()
        d = self._post('/codes/resolve', {'code': '   ', 'order_uuid': order.uuid})
        self.assertEqual(d.get('error'), 'empty_code')

    def test_05_an_expired_card_is_reported_but_not_usable(self):
        from odoo import fields as of
        card = self._card(50.0)
        card.sudo().write({'expiration_date': of.Date.subtract(of.Date.today(), days=1)})
        order = self._order()
        d = self._post('/codes/resolve', {'code': card.code, 'order_uuid': order.uuid})
        self.assertTrue(d.get('ok'), d)
        self.assertTrue(d.get('expired'))
        self.assertFalse(d.get('usable'),
                         'an expired card must not be offered as a tender')

    # -- paying with it --------------------------------------------------
    def test_10_a_gift_card_settles_part_of_a_bill(self):
        card = self._card(40.0)
        order = self._order(100.0)
        d = self._post('/orders/pay', {'uuid': order.uuid, 'gift_card_code': card.code})
        self.assertTrue(d.get('ok'), d)
        self.assertTrue(d.get('partial'), 'a 40 card cannot settle a 100 bill: %s' % d)
        self.assertAlmostEqual(d.get('remaining'), 60.0, places=2)
        card.invalidate_recordset()
        self.assertAlmostEqual(card.points, 0.0, places=2, msg='the card was not spent')

    def test_11_the_rest_goes_on_another_tender(self):
        card = self._card(40.0)
        order = self._order(100.0)
        self._post('/orders/pay', {'uuid': order.uuid, 'gift_card_code': card.code})
        d = self._post('/orders/pay', {'uuid': order.uuid, 'amount': 60.0,
                                       'payment_method_id': self.cash.id})
        self.assertTrue(d.get('ok'), d)
        order.invalidate_recordset()
        self.assertEqual(order.state, 'paid')
        self.assertAlmostEqual(order.amount_paid, 100.0, places=2)

    def test_12_a_card_is_never_spent_beyond_what_is_owed(self):
        card = self._card(500.0)
        order = self._order(100.0)
        d = self._post('/orders/pay', {'uuid': order.uuid, 'gift_card_code': card.code})
        self.assertTrue(d.get('ok'), d)
        card.invalidate_recordset()
        self.assertAlmostEqual(card.points, 400.0, places=2,
                               msg='the card was charged more than the bill')
        order.invalidate_recordset()
        self.assertEqual(order.state, 'paid')
        self.assertAlmostEqual(order.amount_return, 0.0, places=2,
                               msg='a gift card must never produce change')

    def test_13_the_remaining_balance_is_reported(self):
        card = self._card(500.0)
        order = self._order(100.0)
        d = self._post('/orders/pay', {'uuid': order.uuid, 'gift_card_code': card.code})
        self.assertAlmostEqual(d.get('gift_card_balance'), 400.0, places=2,
                               msg='the guest cannot be told what is left: %s' % d)

    def test_14_an_empty_card_is_refused_with_a_reason(self):
        card = self._card(0.0)
        order = self._order(100.0)
        d = self._post('/orders/pay', {'uuid': order.uuid, 'gift_card_code': card.code})
        self.assertFalse(d.get('ok'))
        self.assertEqual(d.get('error'), 'giftcard_empty')

    def test_15_an_expired_card_cannot_pay(self):
        from odoo import fields as of
        card = self._card(50.0)
        card.sudo().write({'expiration_date': of.Date.subtract(of.Date.today(), days=1)})
        order = self._order(100.0)
        d = self._post('/orders/pay', {'uuid': order.uuid, 'gift_card_code': card.code})
        self.assertEqual(d.get('error'), 'giftcard_expired')
        card.invalidate_recordset()
        self.assertAlmostEqual(card.points, 50.0, places=2, msg='an expired card was spent')

    def test_16_an_unknown_card_cannot_pay(self):
        order = self._order(100.0)
        d = self._post('/orders/pay', {'uuid': order.uuid, 'gift_card_code': 'NOPE-000'})
        self.assertEqual(d.get('error'), 'giftcard_not_found')

    def test_19_the_method_is_linked_to_the_branch_before_service(self):
        # The defect this provisioning exists for: the method existed but was not on
        # the config, so pos.payment refused it and the first gift card of the day
        # failed — every day, until someone closed the session.
        names = self.pos_config.payment_method_ids.mapped('name')
        self.assertIn('Gift Card', names,
                      'the branch cannot accept a gift card: %s' % names)

    def test_20_the_gift_card_method_is_not_a_customer_account(self):
        # Without a journal Odoo types it pay_later, Mezze reads that as a customer
        # account, and the credit gate demands a customer for a PREPAID instrument.
        pm = self.pos_config.payment_method_ids.filtered(lambda m: m.name == 'Gift Card')
        self.assertTrue(pm)
        self.assertNotEqual(pm.mezze_mode, 'customer_account')

    def test_17_the_payment_is_recorded_on_the_gift_card_method(self):
        # So the session's takings show gift cards as their own tender rather than
        # silently as cash.
        card = self._card(40.0)
        order = self._order(100.0)
        self._post('/orders/pay', {'uuid': order.uuid, 'gift_card_code': card.code})
        order.invalidate_recordset()
        self.assertEqual(len(order.payment_ids), 1)
        self.assertEqual(order.payment_ids.payment_method_id.name, 'Gift Card')

    def test_18_two_tills_cannot_spend_the_same_balance_twice(self):
        # The balance is read at PAYMENT, not when the code was typed.
        card = self._card(40.0)
        first, second = self._order(100.0), self._order(100.0)
        d1 = self._post('/orders/pay', {'uuid': first.uuid, 'gift_card_code': card.code})
        self.assertTrue(d1.get('ok'), d1)
        d2 = self._post('/orders/pay', {'uuid': second.uuid, 'gift_card_code': card.code})
        self.assertFalse(d2.get('ok'), 'the same 40 was spent twice: %s' % d2)
        self.assertEqual(d2.get('error'), 'giftcard_empty')


@tagged('post_install', '-at_install', 'mezze_browser', 'mezze_codes')
class TestEnterCodeReachable(MezzeHttpCase):
    """The till can actually open it.

    Every endpoint test above passes with the register unable to reach any of this —
    which is precisely the state the loyalty back end was already in, and the state
    Refund and the Z report were in before them. So this drives the real app.
    """
    fixture_profile = 'POS'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        env['ir.config_parameter'].sudo().set_param(
            'mezze_bridge.default_branch_id', str(cls.pos_config.id))
        from ..models.loyalty_bootstrap import ensure_giftcard_payment_method
        ensure_giftcard_payment_method(env)
        cls.pos_sess = cls._open_session_for(cls.pos_config)
        cls.categ = env['pos.category'].sudo().search([], limit=1) \
            or env['pos.category'].sudo().create({'name': 'EC'})
        cls.dish = env['product.product'].sudo().create({
            'name': 'EC Plate', 'available_in_pos': True, 'list_price': 25.0,
            'type': 'consu', 'pos_categ_ids': [(6, 0, cls.categ.ids)]})
        cls.dish.write({'taxes_id': [(5, 0, 0)]})
        # The card must live on the programme the CONTROLLER resolves. Picking
        # "the first gift_card programme" independently is how a perfectly real card
        # comes back "not a gift card": more than one such programme can exist, and
        # the two searches then disagree.
        from ..controllers.main import MezzeBridgeController
        prog = MezzeBridgeController()._giftcard_program(env)
        cls.card = env['loyalty.card'].sudo().create(
            {'program_id': prog.id, 'points': 30.0})
        env.flush_all()

    _JS = r"""
        const $ = (s) => document.querySelector(s);
        const $$ = (s) => Array.from(document.querySelectorAll(s));
        async function waitFor(fn, label, ms=20000){
          const t0 = Date.now();
          while (Date.now()-t0 < ms){ try { if (fn()) return true; } catch(e){}
            await new Promise(r=>setTimeout(r,120)); }
          throw new Error('timeout waiting for: ' + label);
        }
        function assert(c,m){ if(!c) throw new Error('assert failed: ' + m); }
        const setv = (sel, v) => { const i = $(sel);
          const s = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set;
          s.call(i, v); i.dispatchEvent(new Event('input', {bubbles:true})); };
    """

    def test_30_the_till_offers_enter_code_and_accepts_a_gift_card(self):
        self.browser_js('/mezze/pos?ws=register', self._JS + r"""
            (async () => {
                // ring something up — Enter Code acts on an order
                await waitFor(() => $$('.mz-tile').length > 0, 'the menu');
                $$('.mz-tile')[0].click();
                await waitFor(() => $$('.mz-line').length > 0, 'a line in the cart');

                await waitFor(() => $$('.mz-verb').some(v => /Enter Code/.test(v.textContent)),
                              'the Enter Code verb');
                $$('.mz-verb').find(v => /Enter Code/.test(v.textContent)).click();
                await waitFor(() => $('[data-testid="mz-code-input"]'), 'the code screen');

                setv('[data-testid="mz-code-input"]', '%(code)s');
                await new Promise(r => setTimeout(r, 150));
                $('[data-testid="mz-code-submit"]').click();

                await waitFor(() => $('[data-testid="mz-code-gift"]')
                                 || $('[data-testid="mz-code-error"]'),
                              'a verdict on the code');
                assert($('[data-testid="mz-code-gift"]'),
                       'the gift card was not recognised: ' +
                       (($('[data-testid="mz-code-error"]')||{}).textContent || ''));
                console.log('test successful');
            })().catch(e => { console.error(e.message || e); });
        """ % {'code': self.card.code}, login='admin')

    def test_31_an_unknown_code_is_explained_not_swallowed(self):
        self.browser_js('/mezze/pos?ws=register', self._JS + r"""
            (async () => {
                await waitFor(() => $$('.mz-tile').length > 0, 'the menu');
                $$('.mz-tile')[0].click();
                await waitFor(() => $$('.mz-line').length > 0, 'a line in the cart');
                $$('.mz-verb').find(v => /Enter Code/.test(v.textContent)).click();
                await waitFor(() => $('[data-testid="mz-code-input"]'), 'the code screen');
                setv('[data-testid="mz-code-input"]', 'NOSUCHCODE');
                await new Promise(r => setTimeout(r, 150));
                $('[data-testid="mz-code-submit"]').click();
                await waitFor(() => $('[data-testid="mz-code-error"]'), 'a refusal');
                const msg = $('[data-testid="mz-code-error"]').textContent || '';
                assert(/gift card|coupon|promotion/i.test(msg),
                       'the refusal is not a sentence a cashier can act on: ' + msg);
                console.log('test successful');
            })().catch(e => { console.error(e.message || e); });
        """, login='admin')


@tagged('post_install', '-at_install', 'mezze_browser', 'mezze_codes')
class TestRewardsReachable(MezzeHttpCase):
    """The rewards list, on the till.

    ``/loyalty/rewards`` answers with a reason for every reward the guest cannot
    take. That care is wasted if no surface shows it — and until now none did.
    """
    fixture_profile = 'POS'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        env['ir.config_parameter'].sudo().set_param(
            'mezze_bridge.default_branch_id', str(cls.pos_config.id))
        from ..models.loyalty_bootstrap import ensure_loyalty_program
        cls.program = ensure_loyalty_program(env)
        cls.pos_sess = cls._open_session_for(cls.pos_config)
        cls.categ = env['pos.category'].sudo().search([], limit=1) \
            or env['pos.category'].sudo().create({'name': 'RW'})
        cls.dish = env['product.product'].sudo().create({
            'name': 'RW Plate', 'available_in_pos': True, 'list_price': 25.0,
            'type': 'consu', 'pos_categ_ids': [(6, 0, cls.categ.ids)]})
        cls.dish.write({'taxes_id': [(5, 0, 0)]})
        cls.partner = env['res.partner'].sudo().create({'name': 'RW Regular'})
        env.flush_all()

    def test_40_a_customerless_order_says_so_instead_of_showing_nothing(self):
        # The honest answer to "what rewards does this guest have?" when there is no
        # guest attached is a sentence, not an empty box.
        self.browser_js('/mezze/pos?ws=register', r"""
            const $ = (s) => document.querySelector(s);
            const $$ = (s) => Array.from(document.querySelectorAll(s));
            async function waitFor(fn, label, ms=20000){
              const t0 = Date.now();
              while (Date.now()-t0 < ms){ try { if (fn()) return true; } catch(e){}
                await new Promise(r=>setTimeout(r,120)); }
              throw new Error('timeout waiting for: ' + label);
            }
            function assert(c,m){ if(!c) throw new Error('assert failed: ' + m); }
            (async () => {
                await waitFor(() => $$('.mz-tile').length > 0, 'the menu');
                $$('.mz-tile')[0].click();
                await waitFor(() => $$('.mz-line').length > 0, 'a line in the cart');
                $$('.mz-verb').find(v => /Enter Code/.test(v.textContent)).click();
                await waitFor(() => $('[data-testid="mz-code-input"]'), 'the code screen');
                assert($('[data-testid="mz-reward-nocustomer"]'),
                       'no explanation of why rewards are absent');
                console.log('test successful');
            })().catch(e => { console.error(e.message || e); });
        """, login='admin')

    def test_41_a_customer_sees_the_programme_and_their_balance(self):
        self.browser_js('/mezze/pos?ws=register', r"""
            const $ = (s) => document.querySelector(s);
            const $$ = (s) => Array.from(document.querySelectorAll(s));
            async function waitFor(fn, label, ms=20000){
              const t0 = Date.now();
              while (Date.now()-t0 < ms){ try { if (fn()) return true; } catch(e){}
                await new Promise(r=>setTimeout(r,120)); }
              throw new Error('timeout waiting for: ' + label);
            }
            function assert(c,m){ if(!c) throw new Error('assert failed: ' + m); }
            (async () => {
                await waitFor(() => $$('.mz-tile').length > 0, 'the menu');
                $$('.mz-tile')[0].click();
                await waitFor(() => $$('.mz-line').length > 0, 'a line in the cart');

                // attach a customer through the till's own picker
                const cust = $$('.mz-verb').find(v => /Customer/.test(v.textContent));
                assert(cust, 'no Customer verb');
                cust.click();
                await waitFor(() => $('.mz-cust-search, [data-testid="mz-customer-search"]'),
                              'the customer picker');
                const box = $('.mz-cust-search') || $('[data-testid="mz-customer-search"]');
                const setter = Object.getOwnPropertyDescriptor(
                    window.HTMLInputElement.prototype, 'value').set;
                setter.call(box, 'RW Regular');
                box.dispatchEvent(new Event('input', {bubbles:true}));
                await waitFor(() => $$('.mz-cust-row, .mz-cust__row').some(
                    r => /RW Regular/.test(r.textContent)), 'the customer in the results');
                $$('.mz-cust-row, .mz-cust__row').find(
                    r => /RW Regular/.test(r.textContent)).click();
                await new Promise(r => setTimeout(r, 400));

                $$('.mz-verb').find(v => /Enter Code/.test(v.textContent)).click();
                await waitFor(() => $('[data-testid="mz-code-input"]'), 'the code screen');
                await waitFor(() => $('[data-testid="mz-reward-list"]')
                                 || $('[data-testid="mz-reward-none"]'),
                              'the rewards section to settle');
                assert($('[data-testid="mz-reward-points"]'),
                       'the customer balance is not shown');
                assert($('[data-testid="mz-reward-list"]'),
                       'the programme has rewards but none are listed');
                // a reward the guest cannot afford must SAY why
                const why = $$('.mz-code__rewardwhy').map(e => e.textContent).join(' ');
                assert(/point|qualif|discount|card/i.test(why),
                       'an unavailable reward gives no reason: ' + why);
                console.log('test successful');
            })().catch(e => { console.error(e.message || e); });
        """, login='admin')
