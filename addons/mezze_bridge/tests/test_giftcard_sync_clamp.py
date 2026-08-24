# -*- coding: utf-8 -*-
"""A gift card can never settle more than it holds.

Found by mutation: replacing

    gc_applied = min(gc_req, gift_card.points, round(total_incl, 2))

with ``gc_applied = gc_req`` in ``/orders/sync`` broke no test in the suite. Every
gift-card test went through ``/orders/pay`` — the tender path added later — and
nobody was watching the ``gift_card_amount`` parameter on sync, which is
**client-supplied**.

What the clamp actually protects is the DEBIT. ``gc_applied`` is written straight to
the card at line 1604 (``_giftcard_decrement``) once the order is paid, so a till
claiming 500 off a card holding 10 drives that card to **-490** — money spent that
was never loaded, and a balance that will keep paying for the next order too.

(An earlier draft of this file asserted something else and was wrong: it expected
``amount_paid`` to stay at the card's balance. It does not, and that is by design —
``/orders/sync`` with no ``payments`` and ``draft=False`` auto-tenders the remainder
onto the branch's first method, which is the deliberate shorthand for a client that
says "sold" without itemising. The clamp is about the card, not the bill total.)

Two separate ceilings are being asserted, because they fail differently:

* the card's BALANCE — spending money that was never loaded;
* the BILL — a card is not a source of change, so covering more than is owed would
  turn a gift card into a cash-out.
"""
import json

from odoo.tests import tagged

from .common import MezzeHttpCase


@tagged('post_install', '-at_install', 'mezze_giftcard')
class TestGiftCardSyncClamp(MezzeHttpCase):
    fixture_profile = 'POS'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        env['ir.config_parameter'].sudo().set_param('mezze_bridge.api_token', 'gs-tok')
        # BEFORE the session opens. Odoo refuses to change a config's payment
        # methods while a session is running, so provisioning afterwards silently
        # does nothing and every tender below is refused before reaching the clamp —
        # a suite that looks like it tests the rule and never gets near it.
        from ..models.loyalty_bootstrap import ensure_giftcard_payment_method
        ensure_giftcard_payment_method(env)
        cls.pos_sess = cls._open_session_for(cls.pos_config)
        cls.cash = cls.pos_config.payment_method_ids.filtered('is_cash_count')[:1]
        cls.dish = env['product.product'].sudo().create({
            'name': 'GS Plate', 'available_in_pos': True, 'list_price': 100.0,
            'type': 'consu'})
        cls.dish.write({'taxes_id': [(5, 0, 0)]})
        env.flush_all()

    def _post(self, path, body):
        r = self.url_open('/mezze/api/v1' + path,
                          data=json.dumps(dict(body, token='gs-tok')),
                          headers={'Content-Type': 'application/json'})
        try:
            return r.status_code, r.json()
        except Exception:  # noqa: BLE001
            return r.status_code, {'raw': r.text[:200]}

    def _card(self, balance):
        """A gift card carrying a known balance."""
        env = self.env
        prog = env['loyalty.program'].sudo().search(
            [('program_type', '=', 'gift_card')], limit=1)
        if not prog:
            prog = env['loyalty.program'].sudo().create({
                'name': 'GS Cards', 'program_type': 'gift_card',
                'applies_on': 'future', 'trigger': 'auto'})
        return env['loyalty.card'].sudo().create(
            {'program_id': prog.id, 'points': balance})

    def _sell(self, uuid, card, claim, qty=1):
        return self._post('/orders/sync', {
            'uuid': uuid, 'session_id': self.pos_sess.id, 'draft': False,
            'lines': [{'product_id': self.dish.id, 'qty': qty}],
            'gift_card_code': card.code, 'gift_card_amount': claim,
            'payments': [],
        })

    def _order(self, uuid):
        self.env.invalidate_all()
        return self.env['pos.order'].sudo().search([('uuid', '=', uuid)], limit=1)

    # ── the balance ceiling ──────────────────────────────────────────────
    def test_01_a_card_is_never_debited_past_its_balance(self):
        # THE finding. A 10-balance card asked to cover a 100 bill.
        card = self._card(10.0)
        self._sell('gs-over', card, 100.0)
        card.invalidate_recordset()
        self.assertGreaterEqual(
            round(card.points, 2), 0.0,
            'the card was driven to %s — money spent that was never loaded'
            % card.points)

    def test_02_it_gives_up_exactly_what_it_had(self):
        card = self._card(10.0)
        self._sell('gs-keep', card, 100.0)
        card.invalidate_recordset()
        self.assertAlmostEqual(
            card.points, 0.0, places=2,
            msg='a 10 card claiming 100 ended on %s' % card.points)

    def test_03_a_card_that_covers_the_bill_still_works(self):
        # Guard against fixing the ceiling by breaking the feature.
        card = self._card(500.0)
        code, res = self._sell('gs-ok', card, 100.0)
        self.assertEqual(code, 200, res)
        order = self._order('gs-ok')
        self.assertTrue(order, res)
        self.assertAlmostEqual(order.amount_paid, 100.0, places=2)

    # ── the bill ceiling ─────────────────────────────────────────────────
    def test_04_a_card_is_not_a_way_to_take_cash_out(self):
        # Covering more than is owed would make a gift card a cash-out.
        card = self._card(500.0)
        self._sell('gs-cashout', card, 400.0)
        order = self._order('gs-cashout')
        self.assertTrue(order)
        self.assertAlmostEqual(
            order.amount_paid, 100.0, places=2,
            msg='the card paid %s against a bill of 100' % order.amount_paid)

    def test_05_only_what_the_bill_needed_left_the_card(self):
        card = self._card(500.0)
        self._sell('gs-spend', card, 400.0)
        card.invalidate_recordset()
        self.assertAlmostEqual(
            card.points, 400.0, places=2,
            msg='a 100 bill took %s off the card' % (500.0 - card.points))
