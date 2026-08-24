"""Wave 2A — rewards priced by the server, written as native reward lines.

Three things were wrong at once.

**The programme was never created.** ``_loyalty_program`` only searched for a
programme named 'Mezze Rewards'. Nothing in the addon created it — not the data
files, the post-init hook, onboarding or the migrations — so on a fresh install
points were never earned and the rewards list was always empty. Gift cards
self-provisioned; loyalty did not.

**The redemption was client-trusted.** The till called ``/loyalty/redeem``, got a
number back, and posted that number to ``/orders/pay``, which wrote
``price_unit = -discount`` with no check that a reward existed or that a card had
been debited. Since ``/orders/pay`` needs only ORDERS_PAY while redeeming needs
LOYALTY_ADJUST, the money route was the weaker gate.

**The line was anonymous.** ``pos_loyalty`` is auto-installed in every Mezze
database, so ``pos.order.line`` already carried ``is_reward_line``, ``reward_id``,
``coupon_id`` and ``points_cost``. Mezze wrote a bare negative line instead, which
is exactly why ``sync_from_ui`` strips it.
"""
import json

from odoo.tests import TransactionCase, tagged

from ..domain import reward as rules
from .common import MezzeHttpCase


@tagged('post_install', '-at_install', 'mezze_reward')
class TestRewardRules(TransactionCase):
    """The pricing, without a database."""

    def test_01_percent_of_the_order(self):
        self.assertAlmostEqual(
            rules.discount_amount(rules.PERCENT, 10, 200.0), 20.0, places=2)

    def test_02_flat_per_order(self):
        self.assertAlmostEqual(
            rules.discount_amount(rules.PER_ORDER, 15, 200.0), 15.0, places=2)

    def test_03_per_point_scales_with_the_points_spent(self):
        self.assertAlmostEqual(
            rules.discount_amount(rules.PER_POINT, 0.5, 200.0, points_spent=40),
            20.0, places=2)

    def test_04_an_unknown_mode_is_worth_nothing(self):
        self.assertEqual(rules.discount_amount('bogus', 10, 200.0), 0.0)

    def test_05_the_cap_is_honoured(self):
        self.assertAlmostEqual(
            rules.discount_amount(rules.PERCENT, 50, 200.0, max_amount=25.0),
            25.0, places=2)

    def test_06_a_reward_can_never_make_a_bill_negative(self):
        self.assertAlmostEqual(
            rules.discount_amount(rules.PER_ORDER, 500, 200.0, remaining=30.0),
            30.0, places=2)

    def test_07_base_depends_on_applicability(self):
        self.assertEqual(rules.discount_base(rules.ORDER, 100.0, 7.0, 40.0), 100.0)
        self.assertEqual(rules.discount_base(rules.CHEAPEST, 100.0, 7.0, 40.0), 7.0)
        self.assertEqual(rules.discount_base(rules.SPECIFIC, 100.0, 7.0, 40.0), 40.0)

    def test_08_clear_wallet_spends_the_whole_balance(self):
        self.assertEqual(rules.spend_for(10, 250.0, clear_wallet=True), 250.0)
        self.assertEqual(rules.points_after(250.0, 10, clear_wallet=True), 0.0)
        self.assertEqual(rules.points_after(250.0, 10), 240.0)

    def test_09_refusals_name_themselves(self):
        self.assertEqual(rules.claimable(100, 0, 50, has_card=False)[1], rules.NO_CARD)
        self.assertEqual(rules.claimable(100, 10, 50)[1], rules.NOT_ENOUGH_POINTS)
        self.assertEqual(rules.claimable(100, 500, 0)[1], rules.NOTHING_TO_DISCOUNT)
        self.assertEqual(rules.claimable(100, 500, 50, already=True)[1],
                         rules.ALREADY_APPLIED)
        self.assertEqual(rules.claimable(100, 500, 50, reward_type='product',
                                         eligible_products=False)[1],
                         rules.NO_ELIGIBLE_PRODUCT)
        self.assertTrue(rules.claimable(100, 500, 50)[0])

    def test_10_a_product_reward_does_not_need_a_balance_to_discount(self):
        # A free product is claimable on an order with nothing left to discount.
        ok, _r = rules.claimable(100, 500, 0.0, reward_type='product')
        self.assertTrue(ok)


@tagged('post_install', '-at_install', 'mezze_reward')
class TestLoyaltyRewards(MezzeHttpCase):
    fixture_profile = 'POS'

    def setUp(self):
        super().setUp()
        icp = self.env['ir.config_parameter'].sudo()
        icp.set_param('mezze_bridge.api_token', 'loy-tok')
        icp.set_param('mezze_bridge.api_security', 'observe')
        icp.set_param('mezze_bridge.env_profile', 'development')
        self.session = self.open_test_session()
        self.partner = self.env['res.partner'].create({'name': 'Loyal Layla',
                                                       'customer_rank': 1})
        self.env.flush_all()

    def _post(self, path, body):
        r = self.url_open('/mezze/api/v1' + path,
                          data=json.dumps(dict(body, token='loy-tok')),
                          headers={'Content-Type': 'application/json'}, timeout=30)
        try:
            return r.status_code, r.json()
        except Exception:  # noqa: BLE001
            return r.status_code, {'_raw': r.text[:300]}

    def _programme(self):
        return self.env['loyalty.program'].sudo().search(
            [('name', '=', 'Mezze Rewards'), ('program_type', '=', 'loyalty')], limit=1)

    def _card(self, points):
        prog = self._programme()
        card = self.env['loyalty.card'].sudo().search(
            [('program_id', '=', prog.id), ('partner_id', '=', self.partner.id)], limit=1)
        if not card:
            card = self.env['loyalty.card'].sudo().create(
                {'program_id': prog.id, 'partner_id': self.partner.id, 'points': 0.0})
        card.write({'points': points})
        return card

    def _order(self, price=100.0, qty=1):
        order = self.create_order_in_test_session(qty=qty, price=price,
                                                  session=self.session)
        order.write({'partner_id': self.partner.id})
        return order

    # ── provisioning ─────────────────────────────────────────────────────────
    def test_20_the_programme_exists_after_install(self):
        # It used to not exist at all: every code path looked for a programme named
        # 'Mezze Rewards' and nothing anywhere created it, so loyalty was inert on
        # every fresh database.
        self.assertTrue(self._programme(),
                        'loyalty is inert — nothing provisioned the programme')

    def test_21_the_programme_can_actually_earn(self):
        prog = self._programme()
        self.assertTrue(prog.rule_ids, 'a programme with no rule can never earn')
        self.assertGreater(prog.rule_ids[0].reward_point_amount, 0)
        self.assertTrue(prog.reward_ids, 'a programme with no reward can never be spent')

    def test_22_provisioning_is_idempotent(self):
        from ..models.loyalty_bootstrap import ensure_loyalty_program
        first = self._programme().id
        again = ensure_loyalty_program(self.env)
        self.assertEqual(again.id, first, 'a second install created a second programme')
        self.assertEqual(len(self.env['loyalty.program'].sudo().search(
            [('name', '=', 'Mezze Rewards')])), 1)

    def test_23_a_read_route_never_provisions(self):
        # The lazy fix — create on first read — puts an INSERT on a read-only cursor,
        # which aborts the transaction and fails the read that triggered it.
        prog = self._programme()
        prog.sudo().write({'name': 'Renamed Away'})
        code, res = self._post('/loyalty/search', {'q': 'Layla'})
        self.assertEqual(code, 200, res)
        self.assertFalse(self.env['loyalty.program'].sudo().search(
            [('name', '=', 'Mezze Rewards')]),
            'a read route provisioned the programme')

    # ── listing ──────────────────────────────────────────────────────────────
    def test_30_rewards_list_says_why_a_reward_is_not_claimable(self):
        self._card(0.0)
        order = self._order()
        code, res = self._post('/loyalty/rewards',
                               {'partner_id': self.partner.id, 'order_id': order.id})
        self.assertEqual(code, 200, res)
        self.assertTrue(res['rewards'])
        r = res['rewards'][0]
        self.assertFalse(r['claimable'])
        self.assertEqual(r['reason'], rules.NOT_ENOUGH_POINTS)

    # ── applying ─────────────────────────────────────────────────────────────
    def test_40_applying_a_reward_writes_a_NATIVE_reward_line(self):
        card = self._card(500.0)
        order = self._order(price=100.0)
        rew = self._programme().reward_ids[0]
        code, res = self._post('/loyalty/apply', {
            'partner_id': self.partner.id, 'reward_id': rew.id, 'order_id': order.id})
        self.assertEqual(code, 200, res)
        order.invalidate_recordset()
        line = order.lines.filtered(lambda l: l.is_reward_line)
        self.assertTrue(line, 'the reward was not written as a reward line')
        self.assertEqual(line.reward_id, rew)
        self.assertEqual(line.coupon_id, card)
        self.assertAlmostEqual(line.points_cost, rew.required_points, places=2)

    def test_41_the_reward_actually_reduces_the_bill(self):
        self._card(500.0)
        order = self._order(price=100.0)
        before = order.amount_total
        rew = self._programme().reward_ids[0]
        self._post('/loyalty/apply', {'partner_id': self.partner.id,
                                      'reward_id': rew.id, 'order_id': order.id})
        order.invalidate_recordset()
        self.assertLess(order.amount_total, before)

    def test_42_the_points_are_debited_once(self):
        card = self._card(500.0)
        order = self._order(price=100.0)
        rew = self._programme().reward_ids[0]
        self._post('/loyalty/apply', {'partner_id': self.partner.id,
                                      'reward_id': rew.id, 'order_id': order.id})
        card.invalidate_recordset()
        self.assertAlmostEqual(card.points, 500.0 - rew.required_points, places=2)

    def test_43_the_same_reward_cannot_be_taken_twice(self):
        self._card(5000.0)
        order = self._order(price=100.0)
        rew = self._programme().reward_ids[0]
        self._post('/loyalty/apply', {'partner_id': self.partner.id,
                                      'reward_id': rew.id, 'order_id': order.id})
        code, res = self._post('/loyalty/apply', {'partner_id': self.partner.id,
                                                  'reward_id': rew.id,
                                                  'order_id': order.id})
        self.assertEqual(code, 400, res)
        self.assertEqual(res.get('error'), rules.ALREADY_APPLIED)

    def test_44_a_reward_without_the_points_is_refused_and_changes_nothing(self):
        self._card(1.0)
        order = self._order(price=100.0)
        before = order.amount_total
        rew = self._programme().reward_ids[0]
        code, res = self._post('/loyalty/apply', {'partner_id': self.partner.id,
                                                  'reward_id': rew.id,
                                                  'order_id': order.id})
        self.assertEqual(code, 400, res)
        order.invalidate_recordset()
        self.assertAlmostEqual(order.amount_total, before, places=2)

    def test_45_a_paid_order_cannot_take_a_reward(self):
        self._card(500.0)
        order = self._order(price=100.0)
        order.write({'state': 'paid'})
        rew = self._programme().reward_ids[0]
        code, _res = self._post('/loyalty/apply', {'partner_id': self.partner.id,
                                                   'reward_id': rew.id,
                                                   'order_id': order.id})
        self.assertEqual(code, 400)

    # ── removing ─────────────────────────────────────────────────────────────
    def test_50_removing_a_reward_returns_the_points(self):
        card = self._card(500.0)
        order = self._order(price=100.0)
        rew = self._programme().reward_ids[0]
        _c, res = self._post('/loyalty/apply', {'partner_id': self.partner.id,
                                                'reward_id': rew.id,
                                                'order_id': order.id})
        line_id = res['line_id']
        code, out = self._post('/loyalty/remove', {'line_id': line_id,
                                                   'order_id': order.id})
        self.assertEqual(code, 200, out)
        card.invalidate_recordset()
        self.assertAlmostEqual(card.points, 500.0, places=2,
                               msg='the guest paid points for a reward that was undone')

    def test_51_removing_restores_the_bill(self):
        self._card(500.0)
        order = self._order(price=100.0)
        before = order.amount_total
        rew = self._programme().reward_ids[0]
        _c, res = self._post('/loyalty/apply', {'partner_id': self.partner.id,
                                                'reward_id': rew.id,
                                                'order_id': order.id})
        self._post('/loyalty/remove', {'line_id': res['line_id'], 'order_id': order.id})
        order.invalidate_recordset()
        self.assertAlmostEqual(order.amount_total, before, places=2)

    # ── the reward never stacks on itself ────────────────────────────────────
    def test_60_a_percentage_reward_does_not_discount_another_reward(self):
        self._card(5000.0)
        order = self._order(price=100.0)
        prog = self._programme()
        pct = self.env['loyalty.reward'].sudo().create({
            'program_id': prog.id, 'reward_type': 'discount', 'discount': 50.0,
            'discount_mode': 'percent', 'discount_applicability': 'order',
            'required_points': 10.0})
        flat = self.env['loyalty.reward'].sudo().create({
            'program_id': prog.id, 'reward_type': 'discount', 'discount': 20.0,
            'discount_mode': 'per_order', 'discount_applicability': 'order',
            'required_points': 10.0})
        self._post('/loyalty/apply', {'partner_id': self.partner.id,
                                      'reward_id': flat.id, 'order_id': order.id})
        self._post('/loyalty/apply', {'partner_id': self.partner.id,
                                      'reward_id': pct.id, 'order_id': order.id})
        order.invalidate_recordset()
        rl = order.lines.filtered(lambda l: l.reward_id == pct)
        # 50% of the FOOD (100), not of food-minus-the-other-reward (80)
        self.assertAlmostEqual(abs(rl.price_subtotal_incl), 50.0, places=2,
                               msg='a reward was priced off another reward')
