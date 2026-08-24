"""Discounts, and the authority behind them.

Mezze shipped with no way to take money off a bill. ``pos.order.line.discount`` is
a core field and ``_build_lines`` always honoured it, but no surface ever sent one,
no ceiling existed, and no audit event was written — so the only markdown a till
could reach was a 100% comp, and the only *reachable* discount in the product was
an unbounded one grafted through ``/orders/pay``.

Two things are proven here.

**The ceiling is a control, not a hint.** A cashier is bounded, a supervisor is
bounded higher, a manager is not bounded, and the numbers come from branch config
rather than from the client. A request that exceeds the operator's own authority is
refused and audited even when the security gate is in ``observe`` — a ceiling is a
business rule about money, not an authz rollout stage, so it must not be staged.

**The /orders/pay bypass is closed.** ``/orders/pay`` needs only ORDERS_PAY, which
a cashier and a bare terminal both hold, while ``/loyalty/redeem`` needs
LOYALTY_ADJUST and ``/promo/apply`` needs ORDERS_DISCOUNT — both supervisor-and-
above. The money route was therefore a way around the two gates that exist to bound
markdowns. It is now held to the same ceiling.
"""
import json

from odoo.tests import TransactionCase, tagged

from ..domain import discount as policy
from .common import MezzeHttpCase


@tagged('post_install', '-at_install', 'mezze_discount')
class TestDiscountPolicy(TransactionCase):
    """The pure policy. No database, no HTTP — just the rule."""

    def test_01_shipped_ceilings(self):
        self.assertEqual(policy.ceiling_for('cashier'), 10.0)
        self.assertEqual(policy.ceiling_for('supervisor'), 25.0)
        self.assertIsNone(policy.ceiling_for('manager'), "a manager is not bounded")
        self.assertIsNone(policy.ceiling_for('admin'))

    def test_02_a_bare_terminal_is_not_more_trusted_than_a_cashier(self):
        # The device standing on the counter with nobody named behind it must not
        # out-rank the least-privileged human who uses it.
        self.assertEqual(policy.ceiling_for('terminal'), policy.ceiling_for('cashier'))

    def test_03_branch_can_raise_its_own_ceiling(self):
        params = {'mezze_bridge.discount_ceiling_cashier': '20'}
        self.assertEqual(policy.ceiling_for('cashier', lambda k, d: params.get(k, d)), 20.0)

    def test_04_a_bad_parameter_never_widens_authority(self):
        # A typo in a config value must fall back to the DEFAULT, never to unlimited.
        for bad in ('abc', '', '-5', None):
            self.assertEqual(policy.ceiling_for('cashier', lambda k, d, b=bad: b), 10.0,
                             'ceiling widened on a bad parameter %r' % bad)

    def test_05_within_ceiling_is_allowed(self):
        v, d = policy.evaluate('cashier', 10, ceiling=10.0)
        self.assertEqual(v, policy.ALLOWED)
        self.assertEqual(d['percent'], 10.0)

    def test_06_over_ceiling_needs_approval_not_refusal(self):
        # Over the line is not "no" — a manager may still authorise it.
        v, _d = policy.evaluate('cashier', 40, ceiling=10.0)
        self.assertEqual(v, policy.NEEDS_APPROVAL)

    def test_07_unlimited_role_is_never_stopped(self):
        v, _d = policy.evaluate('manager', 100, ceiling=None)
        self.assertEqual(v, policy.ALLOWED)

    def test_08_a_role_without_the_capability_is_refused_not_offered_approval(self):
        v, _d = policy.evaluate('waiter', 5, ceiling=0.0, has_capability=False)
        self.assertEqual(v, policy.REFUSED,
                         'a role that cannot discount must not be shown an approval path')

    def test_09_percentages_outside_the_range_are_invalid(self):
        for bad in (0, -5, 101, 'x', None, float('nan'), float('inf')):
            v, _d = policy.evaluate('manager', bad, ceiling=None)
            self.assertEqual(v, policy.INVALID, 'accepted %r as a percentage' % bad)

    def test_10_only_rank_1_and_up_can_approve(self):
        self.assertFalse(policy.can_approve('cashier'))
        self.assertTrue(policy.can_approve('supervisor'))
        self.assertTrue(policy.can_approve('manager'))
        self.assertFalse(policy.can_approve('kitchen'))
        self.assertFalse(policy.can_approve(None), 'an unknown role must rank lowest')


@tagged('post_install', '-at_install', 'mezze_discount')
class TestDiscountEndpoint(MezzeHttpCase):
    fixture_profile = 'POS'

    def setUp(self):
        super().setUp()
        icp = self.env['ir.config_parameter'].sudo()
        icp.set_param('mezze_bridge.api_token', 'disc-tok')
        # 'observe' ON PURPOSE: the ceiling must hold even when the authz gate is
        # audit-only, because a ceiling is a rule about money and not a rollout stage.
        icp.set_param('mezze_bridge.api_security', 'observe')
        icp.set_param('mezze_bridge.env_profile', 'development')
        Cashier = self.env['mezze.cashier']
        self.cash = Cashier.create({'name': 'Sara', 'code': 'DSC1', 'role': 'cashier'})
        self.sup = Cashier.create({'name': 'Nadia', 'code': 'DSC2', 'role': 'supervisor'})
        self.mgr = Cashier.create({'name': 'Mona', 'code': 'DSC3', 'role': 'manager'})
        self.mgr.set_pin('4321')
        self.sup.set_pin('1234')
        self.session = self.open_test_session()
        self.env.flush_all()

    # -- helpers ------------------------------------------------------------
    def _post(self, path, body):
        r = self.url_open('/mezze/api/v1' + path,
                          data=json.dumps(dict(body, token='disc-tok')),
                          headers={'Content-Type': 'application/json'}, timeout=30)
        try:
            return r.status_code, r.json()
        except Exception:  # noqa: BLE001
            return r.status_code, {'_raw': r.text[:300]}

    def _order(self, price=100.0, qty=1):
        return self.create_order_in_test_session(qty=qty, price=price, session=self.session)

    def _discount(self, order, percent, as_cashier, scope='order', **extra):
        return self._post('/orders/discount', dict({
            'session_id': self.session.id, 'order_id': order.id,
            'scope': scope, 'percent': percent,
            'cashier_id': as_cashier.id,
        }, **extra))

    def _audits(self, order):
        return self.env['mezze.audit.log'].sudo().search([
            ('event', '=', 'discount.override'),
            ('res_model', '=', 'pos.order'), ('res_id', '=', order.id)])

    # -- the happy path -----------------------------------------------------
    def test_20_a_cashier_may_discount_within_the_ceiling(self):
        order = self._order(price=100.0)
        before = order.amount_total
        code, res = self._discount(order, 10, self.cash)
        self.assertEqual(code, 200, res)
        self.assertTrue(res.get('ok'), res)
        order.invalidate_recordset()
        self.assertAlmostEqual(order.amount_total, before * 0.9, places=2,
                               msg='the money did not actually move')
        self.assertAlmostEqual(order.lines[0].discount, 10.0, places=2)

    def test_21_the_stored_subtotals_move_with_the_percentage(self):
        # discount is a percentage FIELD; price_subtotal/_incl are plain stored
        # columns. Writing only the field would change the receipt and not the bill.
        order = self._order(price=50.0, qty=2)
        self._discount(order, 10, self.cash)
        order.invalidate_recordset()
        line = order.lines[0]
        self.assertAlmostEqual(line.price_subtotal_incl, 90.0, places=2)
        self.assertAlmostEqual(order.amount_total, 90.0, places=2)

    # -- the ceiling --------------------------------------------------------
    def test_22_over_the_ceiling_a_cashier_is_refused(self):
        order = self._order(price=100.0)
        before = order.amount_total
        code, res = self._discount(order, 40, self.cash)
        self.assertEqual(code, 403, res)
        self.assertEqual(res.get('error'), 'approval_required', res)
        order.invalidate_recordset()
        self.assertAlmostEqual(order.amount_total, before, places=2,
                               msg='a refused discount still changed the bill')

    def test_23_a_refusal_is_audited(self):
        order = self._order()
        self._discount(order, 40, self.cash)
        rows = self._audits(order)
        self.assertTrue(rows, 'a refused discount left no trail')
        detail = json.loads(rows[0].detail or '{}')
        self.assertEqual(detail.get('refused'), 'over_ceiling')
        self.assertEqual(detail.get('role'), 'cashier')

    def test_24_a_manager_pin_authorises_the_same_discount(self):
        order = self._order(price=100.0)
        code, res = self._discount(order, 40, self.cash,
                                   manager_code='DSC3', manager_pin='4321')
        self.assertEqual(code, 200, res)
        order.invalidate_recordset()
        self.assertAlmostEqual(order.amount_total, 60.0, places=2)
        detail = json.loads(self._audits(order)[0].detail or '{}')
        self.assertEqual(detail.get('approver_cashier_id'), self.mgr.id,
                         'the approver must be named in the trail')

    def test_25_a_wrong_pin_does_not_authorise(self):
        order = self._order(price=100.0)
        before = order.amount_total
        code, res = self._discount(order, 40, self.cash,
                                   manager_code='DSC3', manager_pin='0000')
        self.assertEqual(code, 403, res)
        order.invalidate_recordset()
        self.assertAlmostEqual(order.amount_total, before, places=2)

    def test_26_a_cashier_cannot_approve_their_own_over_ceiling_discount(self):
        # Rank, not identity, is the rule — and a cashier ranks below the minimum.
        self.cash.set_pin('1111')
        order = self._order(price=100.0)
        before = order.amount_total
        code, _res = self._discount(order, 40, self.cash,
                                    manager_code='DSC1', manager_pin='1111')
        self.assertEqual(code, 403)
        order.invalidate_recordset()
        self.assertAlmostEqual(order.amount_total, before, places=2)

    def test_27_a_supervisor_is_bounded_higher_but_still_bounded(self):
        order = self._order(price=100.0)
        code, _res = self._discount(order, 25, self.sup)
        self.assertEqual(code, 200)
        other = self._order(price=100.0)
        code2, res2 = self._discount(other, 40, self.sup)
        self.assertEqual(code2, 403, res2)

    def test_28_a_manager_is_not_bounded(self):
        order = self._order(price=100.0)
        code, res = self._discount(order, 90, self.mgr)
        self.assertEqual(code, 200, res)
        order.invalidate_recordset()
        self.assertAlmostEqual(order.amount_total, 10.0, places=2)

    def test_29_the_branch_ceiling_is_honoured(self):
        self.env['ir.config_parameter'].sudo().set_param(
            'mezze_bridge.discount_ceiling_cashier', '30')
        order = self._order(price=100.0)
        code, res = self._discount(order, 25, self.cash)
        self.assertEqual(code, 200, res)

    # -- scope --------------------------------------------------------------
    def test_30_line_scope_touches_only_that_line(self):
        order = self._order(price=100.0)
        second = self.env['pos.order.line'].create({
            'order_id': order.id, 'product_id': self.product.id, 'qty': 1,
            'price_unit': 100.0, 'price_subtotal': 100.0, 'price_subtotal_incl': 100.0,
            'tax_ids': [(6, 0, [])]})
        code, res = self._post('/orders/discount', {
            'session_id': self.session.id, 'order_id': order.id, 'scope': 'line',
            'line_id': second.id, 'percent': 10, 'cashier_id': self.cash.id})
        self.assertEqual(code, 200, res)
        order.invalidate_recordset()
        self.assertAlmostEqual(order.lines[0].discount, 0.0, places=2,
                               msg='a line discount leaked onto another line')
        self.assertAlmostEqual(second.discount, 10.0, places=2)

    def test_31_a_line_discount_needs_a_target(self):
        order = self._order()
        code, res = self._post('/orders/discount', {
            'session_id': self.session.id, 'order_id': order.id,
            'scope': 'line', 'percent': 10, 'cashier_id': self.cash.id})
        self.assertEqual(code, 400, res)

    def test_32_a_comped_line_is_left_alone(self):
        # Re-pricing a 100% giveaway would quietly un-comp what a manager signed for.
        order = self._order(price=100.0)
        order.lines[0].write({'discount': 100.0, 'price_subtotal': 0.0,
                              'price_subtotal_incl': 0.0})
        code, res = self._discount(order, 10, self.cash)
        self.assertEqual(code, 400, res)
        self.assertEqual(res.get('error'), 'no_discountable_lines', res)
        order.invalidate_recordset()
        self.assertAlmostEqual(order.lines[0].discount, 100.0, places=2)

    # -- lifecycle ----------------------------------------------------------
    def test_33_a_paid_order_cannot_be_discounted(self):
        order = self._order(price=100.0)
        order.write({'state': 'paid'})
        code, res = self._discount(order, 10, self.mgr)
        self.assertEqual(code, 400, res)
        self.assertIn('open', (res.get('message') or '').lower())

    def test_34_an_invalid_percentage_is_refused(self):
        order = self._order()
        for bad in (0, 101, -5):
            code, res = self._discount(order, bad, self.mgr)
            self.assertEqual(code, 400, res)
            self.assertEqual(res.get('error'), 'invalid_discount', res)

    # -- the closed bypass --------------------------------------------------
    def test_40_orders_pay_cannot_be_used_to_dodge_the_ceiling(self):
        """The finding this work exists to close.

        /orders/pay accepted any ``discount`` + ``discount_product_id`` and wrote
        ``price_unit = -discount`` with no validation, while needing only ORDERS_PAY
        — which a cashier holds and which is a strictly weaker gate than the two
        routes that are supposed to bound a markdown.
        """
        order = self._order(price=100.0)
        code, res = self._post('/orders/pay', {
            'session_id': self.session.id, 'order_id': order.id,
            'amount': 100.0, 'cashier_id': self.cash.id,
            'discount': 60.0, 'discount_product_id': self.product.id,
        })
        self.assertEqual(code, 403, res)
        self.assertEqual(res.get('error'), 'approval_required', res)
        order.invalidate_recordset()
        self.assertEqual(order.state, 'draft', 'a refused discount still settled the bill')
        self.assertAlmostEqual(order.amount_total, 100.0, places=2)

    def test_41_a_small_discount_through_pay_is_still_fine(self):
        # The gate bounds the amount; it does not break the legitimate path.
        order = self._order(price=100.0)
        code, res = self._post('/orders/pay', {
            'session_id': self.session.id, 'order_id': order.id,
            'amount': 95.0, 'cashier_id': self.cash.id,
            'discount': 5.0, 'discount_product_id': self.product.id,
        })
        self.assertNotEqual(code, 403, res)

    def test_42_the_ceiling_holds_even_in_observe_mode(self):
        # setUp deliberately leaves the gate in 'observe'. A ceiling is a rule about
        # money, so it must not be staged behind an authz rollout flag.
        self.assertEqual(
            self.env['ir.config_parameter'].sudo().get_param('mezze_bridge.api_security'),
            'observe')
        order = self._order(price=100.0)
        code, _res = self._discount(order, 40, self.cash)
        self.assertEqual(code, 403, 'the ceiling was staged behind api_security')
