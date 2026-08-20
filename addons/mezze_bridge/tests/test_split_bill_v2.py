"""Split Bill V2 — the invariants, pinned.

A split moves ownership of items between checks. It is financial, never culinary,
and the tests that matter are the ones that would let money or food escape:

  * you cannot move what is not there, and two terminals cannot both move it;
  * a configured product moves whole or not at all;
  * root plus children equals the original, to the cent;
  * a bill split after the food was fired sends the kitchen nothing;
  * four people who split four ways are still four covers.

The domain tests run without a server on purpose — the rules should be readable
and provable on their own, not only through HTTP.
"""
import json

from odoo import fields
from odoo.tests import tagged

from ..domain import split_bill
from .common import MezzeHttpCase


@tagged('post_install', '-at_install', 'mezze_split')
class TestSplitBillDomain(MezzeHttpCase):
    """The rules, with no ORM in the way."""
    fixture_profile = 'POS'

    # ------------------------------------------------------- availability
    def test_01_available_is_original_minus_allocated(self):
        self.assertEqual(split_bill.available({'qty': 3, 'allocated': 0}), 3)
        self.assertEqual(split_bill.available({'qty': 3, 'allocated': 1}), 2)
        self.assertEqual(split_bill.available({'qty': 3, 'allocated': 3}), 0)

    def test_02_over_allocation_is_refused(self):
        lines = {1: {'qty': 3, 'allocated': 1}}
        self.assertEqual(
            split_bill.validate(lines, [{'origin_line_id': 1, 'quantity': 3}]),
            split_bill.REASON_OVER_ALLOCATED)
        self.assertIsNone(
            split_bill.validate(lines, [{'origin_line_id': 1, 'quantity': 2}]))

    def test_03_repeated_allocations_of_one_line_accumulate(self):
        """Two selections of two, against three available, is still over."""
        lines = {1: {'qty': 3, 'allocated': 0}}
        self.assertEqual(split_bill.validate(lines, [
            {'origin_line_id': 1, 'quantity': 2},
            {'origin_line_id': 1, 'quantity': 2}]),
            split_bill.REASON_OVER_ALLOCATED)

    def test_04_zero_and_negative_are_refused(self):
        lines = {1: {'qty': 3, 'allocated': 0}}
        for bad in (0, -1):
            self.assertEqual(
                split_bill.validate(lines, [{'origin_line_id': 1, 'quantity': bad}]),
                split_bill.REASON_NOT_POSITIVE)

    def test_05_fractional_quantity_is_refused_not_rounded(self):
        """SB-DEBT-FRACTIONAL-ITEM: deferred means refused, not quietly floored."""
        lines = {1: {'qty': 3, 'allocated': 0}}
        self.assertEqual(
            split_bill.validate(lines, [{'origin_line_id': 1, 'quantity': 0.5}]),
            split_bill.REASON_NOT_INTEGER)

    def test_06_an_unknown_line_is_refused(self):
        self.assertEqual(
            split_bill.validate({1: {'qty': 1, 'allocated': 0}},
                                [{'origin_line_id': 99, 'quantity': 1}]),
            split_bill.REASON_UNKNOWN_LINE)

    def test_07_an_empty_selection_is_refused(self):
        self.assertEqual(split_bill.validate({1: {'qty': 1, 'allocated': 0}}, []),
                         split_bill.REASON_EMPTY_RESULT)

    def test_08_a_paid_line_cannot_be_moved(self):
        """Value somebody has already settled is not casually re-owned."""
        lines = {1: {'qty': 3, 'allocated': 0, 'paid': True}}
        self.assertEqual(
            split_bill.validate(lines, [{'origin_line_id': 1, 'quantity': 1}]),
            split_bill.REASON_PAID)
        # ...and only an explicit, authorised correction may override it.
        self.assertIsNone(
            split_bill.validate(lines, [{'origin_line_id': 1, 'quantity': 1}],
                                allow_paid=True))

    # -------------------------------------------------- configuration atomicity
    def test_10_a_combo_child_cannot_travel_alone(self):
        lines = {
            1: {'qty': 2, 'allocated': 0, 'combo_children': [2]},
            2: {'qty': 2, 'allocated': 0, 'combo_parent_id': 1},
        }
        self.assertEqual(
            split_bill.validate(lines, [{'origin_line_id': 2, 'quantity': 1}]),
            split_bill.REASON_COMBO_CHILD)

    def test_11_selecting_a_parent_expands_to_its_children(self):
        lines = {
            1: {'qty': 2, 'allocated': 0, 'combo_children': [2, 3]},
            2: {'qty': 2, 'allocated': 0, 'combo_parent_id': 1},
            3: {'qty': 2, 'allocated': 0, 'combo_parent_id': 1},
        }
        out = split_bill.expand_combo_selection(lines, [{'origin_line_id': 1, 'quantity': 1}])
        got = {a['origin_line_id']: a['quantity'] for a in out}
        self.assertEqual(got, {1: 1.0, 2: 1.0, 3: 1.0},
                         "one meal must take its own fries and drink with it")
        self.assertIsNone(split_bill.validate(lines, out))

    def test_12_a_partial_combo_is_refused(self):
        lines = {
            1: {'qty': 2, 'allocated': 0, 'combo_children': [2]},
            2: {'qty': 2, 'allocated': 0, 'combo_parent_id': 1},
        }
        self.assertEqual(split_bill.validate(lines, [
            {'origin_line_id': 1, 'quantity': 2},
            {'origin_line_id': 2, 'quantity': 1}]),
            split_bill.REASON_COMBO_PARTIAL)

    # --------------------------------------------------------- even allocation
    def test_20_one_hundred_over_three_reconciles_exactly(self):
        parts = split_bill.even_amounts(100.0, 3)
        self.assertEqual(parts, [33.34, 33.33, 33.33])
        self.assertTrue(split_bill.reconciles(100.0, parts))

    def test_21_even_amounts_never_lose_or_invent_a_cent(self):
        for total in (100.0, 0.01, 0.03, 599.99, 1234.56, 7.0):
            for ways in (1, 2, 3, 4, 5, 7, 11):
                parts = split_bill.even_amounts(total, ways)
                self.assertEqual(len(parts), ways)
                self.assertTrue(split_bill.reconciles(total, parts),
                                "%s / %s did not reconcile: %s" % (total, ways, parts))

    def test_22_even_amounts_are_deterministic(self):
        self.assertEqual(split_bill.even_amounts(100.0, 3),
                         split_bill.even_amounts(100.0, 3))

    # ------------------------------------------------------------- fired state
    def test_30_fired_quantities_move_they_are_not_created(self):
        fired = {'7': 2.0, '9': 2.0}
        root, child = split_bill.transfer_fired(
            fired, [{'origin_line_id': 1, 'quantity': 1},
                    {'origin_line_id': 2, 'quantity': 1}],
            {1: 7, 2: 9})
        self.assertEqual(child, {'7': 1.0, '9': 1.0})
        self.assertEqual(root, {'7': 1.0, '9': 1.0})
        total_before = sum(fired.values())
        total_after = sum(root.values()) + sum(child.values())
        self.assertEqual(total_before, total_after,
                         "a split must redistribute what was fired, never add to it")

    def test_31_unfired_items_transfer_nothing(self):
        root, child = split_bill.transfer_fired(
            {}, [{'origin_line_id': 1, 'quantity': 2}], {1: 7})
        self.assertEqual(child, {})
        self.assertEqual(root, {})

    def test_32_moving_more_than_was_fired_transfers_only_what_was(self):
        root, child = split_bill.transfer_fired(
            {'7': 1.0}, [{'origin_line_id': 1, 'quantity': 3}], {1: 7})
        self.assertEqual(child, {'7': 1.0})
        self.assertEqual(root, {})

    # ------------------------------------------------------------------ covers
    def test_40_covers_are_conserved(self):
        self.assertTrue(split_bill.covers_conserved(4, [0, 0, 0], 4))
        self.assertFalse(split_bill.covers_conserved(4, [4, 4, 4], 4))


@tagged('post_install', '-at_install', 'mezze_split')
class TestSplitBillApi(MezzeHttpCase):
    """The endpoints, against a real server."""
    fixture_profile = 'POS'

    def setUp(self):
        super().setUp()
        self.env['ir.config_parameter'].sudo().set_param('mezze_bridge.api_security', 'enforce')
        from ..controllers.register_instance import mint_for_instance
        self.token, _t = mint_for_instance(self.env, self.pos_config, 'split-rid')

    def _post(self, path, payload):
        resp = self.url_open('/mezze/api/v1' + path, data=json.dumps(payload),
                             headers={'Content-Type': 'application/json',
                                      'X-Mezze-Token': self.token})
        try:
            return resp.status_code, resp.json()
        except Exception:  # noqa: BLE001
            return resp.status_code, {'ok': False, 'raw': resp.text[:200]}

    def _order(self, qty=3, price=10.0):
        return self.create_order_in_test_session(qty=qty, price=price)

    def _line(self, order):
        return order.lines[0]

    # ------------------------------------------------------------------ state
    def test_50_state_returns_the_movable_picture(self):
        order = self._order(qty=3)
        status, body = self._post('/split/state', {'order_id': order.id})
        self.assertEqual(status, 200, body)
        self.assertTrue(body['ok'])
        self.assertEqual(len(body['lines']), 1)
        row = body['lines'][0]
        self.assertEqual(row['qty'], 3)
        self.assertEqual(row['allocated'], 0)
        self.assertEqual(row['available'], 3)

    def test_51_by_seat_is_reported_unavailable_with_a_reason(self):
        """The brief forbids faking it; the honest answer is told, not hidden."""
        order = self._order()
        _s, body = self._post('/split/state', {'order_id': order.id})
        self.assertFalse(body['modes']['seat'])
        self.assertEqual(body['modes']['seat_reason'], 'no_seat_model')

    def test_52_state_is_one_round_trip_regardless_of_size(self):
        order = self._order(qty=1)
        for _i in range(19):
            self.env['pos.order.line'].sudo().create({
                'order_id': order.id, 'product_id': self.product.id, 'qty': 1,
                'price_unit': 5.0, 'price_subtotal': 5.0, 'price_subtotal_incl': 5.0})
        status, body = self._post('/split/state', {'order_id': order.id})
        self.assertEqual(status, 200)
        self.assertEqual(len(body['lines']), 20, "one call, twenty lines")

    # ----------------------------------------------------------------- commit
    def test_60_moving_one_of_three_leaves_two(self):
        order = self._order(qty=3, price=10.0)
        line = self._line(order)
        status, body = self._post('/split/commit', {
            'order_id': order.id, 'idempotency_key': 'k60',
            'allocations': [{'origin_line_id': line.id, 'quantity': 1}]})
        self.assertEqual(status, 200, body)
        order.invalidate_recordset()
        self.assertEqual(sum(order.lines.mapped('qty')), 2)
        child = self.env['pos.order'].browse(body['child']['id'])
        self.assertEqual(sum(child.lines.mapped('qty')), 1)

    def test_61_moving_all_three_drains_the_original_line(self):
        order = self._order(qty=3)
        line = self._line(order)
        st, body = self._post('/split/commit', {
            'order_id': order.id, 'idempotency_key': 'k61',
            'allocations': [{'origin_line_id': line.id, 'quantity': 3}]})
        self.assertEqual(st, 200, body)
        self.assertTrue(body.get('ok'), body)
        order.invalidate_recordset()
        self.assertEqual(len(order.lines), 0)

    def test_62_over_allocation_is_denied_by_the_server(self):
        order = self._order(qty=3)
        line = self._line(order)
        status, body = self._post('/split/commit', {
            'order_id': order.id, 'idempotency_key': 'k62',
            'allocations': [{'origin_line_id': line.id, 'quantity': 4}]})
        self.assertEqual(status, 400)
        self.assertEqual(body['error'], split_bill.REASON_OVER_ALLOCATED)
        order.invalidate_recordset()
        self.assertEqual(sum(order.lines.mapped('qty')), 3, "nothing moved")

    def test_63_the_family_sums_to_the_original(self):
        order = self._order(qty=3, price=10.0)
        original_total = order.amount_total
        line = self._line(order)
        _s, body = self._post('/split/commit', {
            'order_id': order.id, 'idempotency_key': 'k63',
            'allocations': [{'origin_line_id': line.id, 'quantity': 1}]})
        order.invalidate_recordset()
        child = self.env['pos.order'].browse(body['child']['id'])
        self.assertTrue(
            split_bill.reconciles(original_total, [order.amount_total, child.amount_total]),
            "root %s + child %s != original %s" % (
                order.amount_total, child.amount_total, original_total))

    def test_64_money_comes_from_the_server_not_the_client(self):
        """A tampered client cannot invent a cheaper check."""
        order = self._order(qty=2, price=10.0)
        line = self._line(order)
        _s, body = self._post('/split/commit', {
            'order_id': order.id, 'idempotency_key': 'k64',
            'allocations': [{'origin_line_id': line.id, 'quantity': 1}],
            'amount_total': 0.01, 'price_unit': 0.01, 'tax': 0.0})
        child = self.env['pos.order'].browse(body['child']['id'])
        self.assertEqual(child.lines[0].price_unit, 10.0,
                         "price must come from the line that was sold")

    # ------------------------------------------------------------ concurrency
    def test_70_a_stale_revision_is_refused_with_409(self):
        order = self._order(qty=3)
        line = self._line(order)
        stale = order.mezze_revision or 0
        self._post('/split/commit', {
            'order_id': order.id, 'idempotency_key': 'k70a',
            'allocations': [{'origin_line_id': line.id, 'quantity': 1}]})
        status, body = self._post('/split/commit', {
            'order_id': order.id, 'idempotency_key': 'k70b',
            'expected_revision': stale,
            'allocations': [{'origin_line_id': line.id, 'quantity': 1}]})
        self.assertEqual(status, 409)
        self.assertEqual(body['error'], 'stale_revision')

    def test_71_two_terminals_cannot_both_take_the_same_units(self):
        """Three burgers; both stations ask for two. Only one may win."""
        order = self._order(qty=3)
        line = self._line(order)
        first = self._post('/split/commit', {
            'order_id': order.id, 'idempotency_key': 'k71a',
            'allocations': [{'origin_line_id': line.id, 'quantity': 2}]})
        second = self._post('/split/commit', {
            'order_id': order.id, 'idempotency_key': 'k71b',
            'allocations': [{'origin_line_id': line.id, 'quantity': 2}]})
        self.assertEqual(first[0], 200, first)
        self.assertEqual(second[0], 400, second)
        self.assertEqual(second[1]['error'], split_bill.REASON_OVER_ALLOCATED)
        order.invalidate_recordset()
        self.assertEqual(sum(order.lines.mapped('qty')), 1)

    def test_72_three_rapid_activations_create_one_child(self):
        order = self._order(qty=3)
        line = self._line(order)
        payload = {'order_id': order.id, 'idempotency_key': 'k72',
                   'allocations': [{'origin_line_id': line.id, 'quantity': 1}]}
        results = [self._post('/split/commit', payload) for _i in range(3)]
        self.assertTrue(all(r[0] == 200 for r in results), results)
        children = self.env['pos.order'].sudo().search([('mezze_split_uuid', '=', 'k72')])
        self.assertEqual(len(children), 1, "a double tap is one split")
        self.assertTrue(results[1][1].get('duplicate'))
        order.invalidate_recordset()
        self.assertEqual(sum(order.lines.mapped('qty')), 2, "and it moved once")

    # -------------------------------------------------------------------- KDS
    def test_80_splitting_fired_food_sends_the_kitchen_nothing(self):
        """P0. A bill divided after the food went is not a second order."""
        order = self._order(qty=2)
        line = self._line(order)
        order.sudo().write({'mezze_fired': json.dumps({str(self.product.id): 2.0})})
        Ticket = self.env['mezze.kds.ticket'].sudo()
        before = Ticket.search_count([])
        _s, body = self._post('/split/commit', {
            'order_id': order.id, 'idempotency_key': 'k80',
            'allocations': [{'origin_line_id': line.id, 'quantity': 1}]})
        self.assertEqual(Ticket.search_count([]), before,
                         "a financial split must create 0 kitchen tickets")
        child = self.env['pos.order'].browse(body['child']['id'])
        order.invalidate_recordset()
        self.assertEqual(json.loads(child.mezze_fired or '{}'), {str(self.product.id): 1.0},
                         "the child's item must arrive already fired")
        self.assertEqual(json.loads(order.mezze_fired or '{}'), {str(self.product.id): 1.0})

    def test_81_an_unfired_split_carries_no_fired_state(self):
        order = self._order(qty=2)
        line = self._line(order)
        _s, body = self._post('/split/commit', {
            'order_id': order.id, 'idempotency_key': 'k81',
            'allocations': [{'origin_line_id': line.id, 'quantity': 1}]})
        child = self.env['pos.order'].browse(body['child']['id'])
        self.assertEqual(json.loads(child.mezze_fired or '{}'), {},
                         "food that was never sent must not arrive pre-fired")

    # ----------------------------------------------------------------- family
    def test_90_the_family_is_durable_and_reachable_from_either_end(self):
        order = self._order(qty=3)
        line = self._line(order)
        _s, body = self._post('/split/commit', {
            'order_id': order.id, 'idempotency_key': 'k90',
            'allocations': [{'origin_line_id': line.id, 'quantity': 1}]})
        child = self.env['pos.order'].browse(body['child']['id'])
        for member in (order, child):
            status, fam = self._post('/split/family', {'order_id': member.id})
            self.assertEqual(status, 200)
            ids = {c['id'] for c in fam['checks']}
            self.assertEqual(ids, {order.id, child.id})

    def test_91_the_relation_survives_a_reload(self):
        """Native keeps this in uiState; ours has to be in the database."""
        order = self._order(qty=2)
        line = self._line(order)
        _s, body = self._post('/split/commit', {
            'order_id': order.id, 'idempotency_key': 'k91',
            'allocations': [{'origin_line_id': line.id, 'quantity': 1}]})
        self.env.invalidate_all()
        child = self.env['pos.order'].browse(body['child']['id'])
        self.assertEqual(child.mezze_split_root_id, order)
        self.assertEqual(child.mezze_split_seq, 1)
        self.assertTrue(child.mezze_split_uuid)

    def test_92_covers_are_not_multiplied_by_splitting(self):
        order = self._order(qty=4)
        order.sudo().write({'customer_count': 4})
        line = self._line(order)
        for i, key in enumerate(('k92a', 'k92b', 'k92c'), start=1):
            self._post('/split/commit', {
                'order_id': order.id, 'idempotency_key': key,
                'allocations': [{'origin_line_id': line.id, 'quantity': 1}]})
        order.invalidate_recordset()
        family = order.mezze_split_family()
        total_covers = sum(m.customer_count or 0 for m in family)
        self.assertEqual(total_covers, 4,
                         "four people split four ways are still four covers, not sixteen")

    def test_93_line_provenance_is_recorded(self):
        order = self._order(qty=2)
        line = self._line(order)
        _s, body = self._post('/split/commit', {
            'order_id': order.id, 'idempotency_key': 'k93',
            'allocations': [{'origin_line_id': line.id, 'quantity': 1}]})
        child = self.env['pos.order'].browse(body['child']['id'])
        self.assertEqual(child.lines[0].mezze_split_origin_line_id, line)

    # ------------------------------------------------------------ permissions
    def test_95_splitting_needs_its_own_capability(self):
        from ..domain import authz
        self.assertIn(authz.ORDERS_SPLIT, authz.ROLE_CAPS['cashier'])
        self.assertIn(authz.ORDERS_SPLIT, authz.ROLE_CAPS['terminal'])
        # Correcting a PAID check is not routine service.
        self.assertNotIn(authz.ORDERS_SPLIT_PAID, authz.ROLE_CAPS['cashier'])
        self.assertIn(authz.ORDERS_SPLIT_PAID, authz.ROLE_CAPS['supervisor'])

    def test_96_split_payment_is_still_a_separate_thing(self):
        """The brief's conceptual line: splitting a BILL moves items; splitting a
        PAYMENT does not. The pay route must not have grown item semantics."""
        import inspect
        from ..controllers.main import MezzeBridgeController
        src = inspect.getsource(MezzeBridgeController.order_pay)
        self.assertNotIn('mezze_split_root_id', src)
        self.assertNotIn('allocations', src)

    # =====================================================  SB2.3 pay / undo
    def test_A0_a_child_can_name_itself_for_payment(self):
        """Split & Pay is impossible if the child cannot be addressed by uuid."""
        order = self._order(qty=2)
        line = self._line(order)
        _s, body = self._post('/split/commit', {
            'order_id': order.id, 'idempotency_key': 'kA0',
            'allocations': [{'origin_line_id': line.id, 'quantity': 1}]})
        self.assertTrue(body['child']['uuid'], "a child must carry the uuid /orders/pay takes")
        child = self.env['pos.order'].browse(body['child']['id'])
        self.assertEqual(child.uuid, body['child']['uuid'])
        self.assertNotEqual(child.uuid, order.uuid, "and it must be its own")

    def test_A1_a_child_can_actually_be_paid(self):
        order = self._order(qty=2, price=10.0)
        line = self._line(order)
        _s, body = self._post('/split/commit', {
            'order_id': order.id, 'idempotency_key': 'kA1',
            'allocations': [{'origin_line_id': line.id, 'quantity': 1}]})
        child_uuid = body['child']['uuid']
        method = self.pos_config.payment_method_ids[0]
        st, pay = self._post('/orders/pay', {
            'uuid': child_uuid, 'payment_method_id': method.id, 'amount': 10.0})
        self.assertEqual(st, 200, pay)
        self.assertTrue(pay.get('ok'), pay)
        child = self.env['pos.order'].browse(body['child']['id'])
        child.invalidate_recordset()
        self.assertGreater(child.amount_paid, 0)

    def test_A2_paying_a_child_does_not_settle_the_original(self):
        order = self._order(qty=2, price=10.0)
        line = self._line(order)
        _s, body = self._post('/split/commit', {
            'order_id': order.id, 'idempotency_key': 'kA2',
            'allocations': [{'origin_line_id': line.id, 'quantity': 1}]})
        method = self.pos_config.payment_method_ids[0]
        self._post('/orders/pay', {'uuid': body['child']['uuid'],
                                   'payment_method_id': method.id, 'amount': 10.0})
        order.invalidate_recordset()
        self.assertEqual(order.state, 'draft', "the rest of the table is still open")
        self.assertEqual(sum(order.lines.mapped('qty')), 1)

    # ------------------------------------------------------------- recombine
    def test_A3_an_unpaid_child_can_be_folded_back(self):
        order = self._order(qty=3, price=10.0)
        line = self._line(order)
        before = order.amount_total
        _s, body = self._post('/split/commit', {
            'order_id': order.id, 'idempotency_key': 'kA3',
            'allocations': [{'origin_line_id': line.id, 'quantity': 1}]})
        st, back = self._post('/split/recombine', {'child_id': body['child']['id']})
        self.assertEqual(st, 200, back)
        order.invalidate_recordset()
        self.assertEqual(sum(order.lines.mapped('qty')), 3, "the bill is whole again")
        self.assertTrue(split_bill.reconciles(before, [order.amount_total]))

    def test_A4_a_paid_child_cannot_be_folded_back(self):
        """Money has moved; unpicking it is a refund, not a split screen."""
        order = self._order(qty=2, price=10.0)
        line = self._line(order)
        _s, body = self._post('/split/commit', {
            'order_id': order.id, 'idempotency_key': 'kA4',
            'allocations': [{'origin_line_id': line.id, 'quantity': 1}]})
        method = self.pos_config.payment_method_ids[0]
        self._post('/orders/pay', {'uuid': body['child']['uuid'],
                                   'payment_method_id': method.id, 'amount': 10.0})
        st, back = self._post('/split/recombine', {'child_id': body['child']['id']})
        self.assertEqual(st, 403)
        self.assertEqual(back['error'], split_bill.REASON_PAID)

    def test_A5_recombining_returns_the_fired_state_too(self):
        order = self._order(qty=2)
        line = self._line(order)
        order.sudo().write({'mezze_fired': json.dumps({str(self.product.id): 2.0})})
        _s, body = self._post('/split/commit', {
            'order_id': order.id, 'idempotency_key': 'kA5',
            'allocations': [{'origin_line_id': line.id, 'quantity': 1}]})
        self._post('/split/recombine', {'child_id': body['child']['id']})
        order.invalidate_recordset()
        self.assertEqual(json.loads(order.mezze_fired or '{}'),
                         {str(self.product.id): 2.0},
                         "food that was already sent must not be forgotten by an undo")

    def test_A6_recombine_refuses_an_order_that_is_not_a_child(self):
        order = self._order(qty=1)
        st, body = self._post('/split/recombine', {'child_id': order.id})
        self.assertEqual(st, 400)
        self.assertEqual(body['error'], 'not_a_split_child')

    def test_A7_the_family_survives_a_recombine(self):
        """Provenance is never destroyed — a cancelled child is still family."""
        order = self._order(qty=3)
        line = self._line(order)
        _s, body = self._post('/split/commit', {
            'order_id': order.id, 'idempotency_key': 'kA7',
            'allocations': [{'origin_line_id': line.id, 'quantity': 1}]})
        child = self.env['pos.order'].browse(body['child']['id'])
        self._post('/split/recombine', {'child_id': child.id})
        child.invalidate_recordset()
        self.assertEqual(child.state, 'cancel')
        self.assertEqual(child.mezze_split_root_id, order,
                         "the root must still be able to explain what happened")


    # ------------------------------- the bug the full-cycle test found (SB2.7)
    def test_D0_a_second_guest_can_take_what_is_left(self):
        """After one split, the REST of the bill must still be splittable.

        Availability was qty minus what earlier splits took — but moving units
        already decrements the root's qty, so the same units were subtracted
        twice. A bill split once showed its last item as unavailable and the
        second guest could never take it.
        """
        order = self._order(qty=3, price=10.0)
        line = self._line(order)
        self._post('/split/commit', {
            'order_id': order.id, 'idempotency_key': 'kD0a',
            'allocations': [{'origin_line_id': line.id, 'quantity': 1}]})
        _s, state = self._post('/split/state', {'order_id': order.id})
        row = state['lines'][0]
        self.assertEqual(row['qty'], 2, 'two left on the bill')
        self.assertEqual(row['available'], 2,
                         'and all two must still be movable, not %s' % row['available'])
        # and the server must actually allow taking them
        st, body = self._post('/split/commit', {
            'order_id': order.id, 'idempotency_key': 'kD0b',
            'allocations': [{'origin_line_id': row['id'], 'quantity': 2}]})
        self.assertEqual(st, 200, body)
        order.invalidate_recordset()
        self.assertEqual(sum(order.lines.mapped('qty')), 0)

    def test_D1_the_last_unit_of_a_line_is_not_stranded(self):
        order = self._order(qty=2, price=10.0)
        line = self._line(order)
        self._post('/split/commit', {
            'order_id': order.id, 'idempotency_key': 'kD1a',
            'allocations': [{'origin_line_id': line.id, 'quantity': 1}]})
        _s, state = self._post('/split/state', {'order_id': order.id})
        row = state['lines'][0]
        self.assertEqual(row['available'], 1, 'the last one must still be takeable')
        self.assertEqual(row['allocated'], 1, 'and the screen still says one went elsewhere')

    def test_D2_over_allocation_is_still_refused_after_a_split(self):
        """Loosening availability must not loosen the ceiling."""
        order = self._order(qty=3)
        line = self._line(order)
        self._post('/split/commit', {
            'order_id': order.id, 'idempotency_key': 'kD2a',
            'allocations': [{'origin_line_id': line.id, 'quantity': 1}]})
        _s, state = self._post('/split/state', {'order_id': order.id})
        st, body = self._post('/split/commit', {
            'order_id': order.id, 'idempotency_key': 'kD2b',
            'allocations': [{'origin_line_id': state['lines'][0]['id'], 'quantity': 3}]})
        self.assertEqual(st, 400)
        self.assertEqual(body['error'], split_bill.REASON_OVER_ALLOCATED)


@tagged('post_install', '-at_install', 'mezze_split')
class TestSplitBillA11yAndArabic(MezzeHttpCase):
    """SB2.6 — the parts a shift actually lives with."""
    fixture_profile = 'POS'

    def _js(self):
        import pathlib
        base = pathlib.Path(__file__).resolve().parent.parent
        return (base / 'static/src/cashier/components/split_bill.js').read_text()

    def _xml(self):
        import pathlib
        base = pathlib.Path(__file__).resolve().parent.parent
        return (base / 'static/src/cashier/components/split_bill.xml').read_text()

    def _css(self):
        import pathlib
        base = pathlib.Path(__file__).resolve().parent.parent
        css = (base / 'static/src/cashier/cashier.css').read_text()
        return css[css.index('---- Split Bill V2'):]

    # ------------------------------------------------------------------ Arabic
    def test_B0_no_english_is_hardcoded_in_the_template(self):
        """Text lives in the component so it reaches i18n; a screen a shift reads
        in Arabic must not be the one place that stayed English."""
        import re
        leaked = re.findall(r'>([A-Za-z][A-Za-z .,&;—…]{3,})<', self._xml())
        self.assertEqual(leaked, [], "hardcoded English in the split template: %s" % leaked)

    def test_B1_every_visible_string_goes_through_translation(self):
        js = self._js()
        # Every label getter must call _t; a getter returning a bare string would
        # silently opt one sentence out of Arabic.
        import re
        for name, body in re.findall(r'get (\w+Label)\(\) \{ return ([^;]+);', js):
            self.assertIn('_t(', body, "%s does not translate" % name)

    def test_B2_the_arabic_catalogue_covers_the_workspace(self):
        import pathlib, re
        base = pathlib.Path(__file__).resolve().parent.parent
        po = (base / 'i18n/ar.po').read_text()
        have = set(re.findall(r'^msgid "((?:[^"\\]|\\.)*)"', po, re.M))
        wanted = set(re.findall(r'_t\("((?:[^"\\]|\\.)*)"', self._js()))
        missing = sorted(w for w in wanted if w not in have)
        self.assertEqual(missing, [], "not translated into Arabic: %s" % missing)

    def test_B3_no_directional_word_in_a_mirrored_layout(self):
        """'on the left' is right in English and wrong in Arabic — the panes mirror."""
        import re
        # Only the STRINGS a cashier reads — a comment explaining the rule is not
        # a violation of it.
        shown = ' '.join(re.findall(r'_t\("((?:[^"\\]|\\.)*)"', self._js())).lower()
        for word in ('on the left', 'on the right', 'left pane', 'right pane'):
            self.assertNotIn(word, shown)

    # --------------------------------------------------------------------- RTL
    def test_B4_the_css_uses_logical_properties_only(self):
        import re
        css = self._css()
        bad = re.findall(
            r'(margin-left|margin-right|padding-left|padding-right|border-left|'
            r'border-right|text-align:\s*(?:left|right))', css)
        self.assertEqual(bad, [], "physical direction properties break RTL: %s" % bad)

    def test_B5_the_selected_marker_is_not_a_physical_inset_shadow(self):
        """box-shadow has no logical form: inset 3px 0 0 stays on the LEFT in RTL."""
        css = self._css()
        self.assertNotIn('box-shadow:inset 3px 0 0', css.replace(' ', ''))
        self.assertIn('inset-inline-start', css)

    # ----------------------------------------------------------- accessibility
    def test_B6_touch_targets_clear_44px(self):
        import re
        css = self._css()
        for sel in ('.mz-sb__step', '.mz-sb__back', '.mz-sb__all', '.mz-sb__mode'):
            block = re.search(re.escape(sel) + r'\{([^}]*)\}', css)
            self.assertTrue(block, "%s has no rule" % sel)
            body = block.group(1)
            sizes = [int(n) for n in re.findall(r'(?:min-height|height|width):(\d+)px', body)]
            self.assertTrue(sizes, "%s sets no size" % sel)
            self.assertGreaterEqual(min(sizes), 44, "%s is under 44px: %s" % (sel, sizes))

    def test_B7_quantity_controls_are_48px_or_more(self):
        """The brief asks 48-56px for the primary quantity controls."""
        import re
        css = self._css()
        body = re.search(r'\.mz-sb__step\{([^}]*)\}', css).group(1)
        sizes = [int(n) for n in re.findall(r'(?:width|height):(\d+)px', body)]
        self.assertGreaterEqual(min(sizes), 48, sizes)

    def test_B8_rows_are_keyboard_operable(self):
        js, xml = self._js(), self._xml()
        self.assertIn('onRowKey', js)
        self.assertIn('t-on-keydown', xml)
        for key in ('" "', '"Enter"', '"ArrowRight"', '"ArrowLeft"'):
            self.assertIn(key, js, "no keyboard handling for %s" % key)

    def test_B9_no_positive_tabindex(self):
        import re
        bad = [t for t in re.findall(r'tabindex="(-?\d+)"', self._xml()) if int(t) > 0]
        self.assertEqual(bad, [], "positive tabindex hijacks tab order: %s" % bad)

    def test_C0_focus_is_visible(self):
        self.assertIn(':focus-visible', self._css())

    def test_C1_selected_state_is_not_colour_alone(self):
        """A colour-only selection is invisible to a colourblind cashier."""
        css = self._css()
        self.assertIn('.mz-sb__row--picked::before', css)

    def test_C4_every_css_token_the_workspace_uses_actually_exists(self):
        """An invented custom property is not a typo the browser reports — the whole
        declaration is silently dropped. `padding: var(--sp-12)` against a token that
        does not exist is simply NO padding, which is how this workspace shipped with
        every element flush against the edge and the footer totals overlapping. Nothing
        in the test suite could see it; only a person looking at the screen could.
        """
        import pathlib as _p, re, subprocess
        base = _p.Path(__file__).resolve().parent.parent
        css = (base / 'static/src/cashier/cashier.css').read_text()
        mine = css[css.index('---- End of day'):]
        used = set(re.findall(r'var\((--[a-z0-9-]+)', mine))
        defined = set()
        for f in ('static/design/foundation.css', 'static/mezze-design.css',
                  'static/src/cashier/cashier.css'):
            defined |= set(re.findall(r'(--[a-z0-9-]+)\s*:', (base / f).read_text()))
        missing = sorted(u for u in used if u not in defined)
        self.assertEqual(missing, [], "CSS tokens used but never defined: %s" % missing)

    # ------------------------------------------------------------- responsive
    def test_C2_narrow_tills_stack_instead_of_squeezing(self):
        css = self._css()
        self.assertIn('@media (max-width: 1100px)', css)
        narrow = css[css.index('@media (max-width: 1100px)'):]
        self.assertIn('grid-template-columns:1fr', narrow.replace(' ', ''),
                      "both panes must not stay side by side on a narrow till")

    def test_C3_the_two_totals_and_the_cta_survive_every_width(self):
        """Whatever the width, a cashier must still see remaining, new check and
        the primary action — that is the footer's whole job."""
        xml = self._xml()
        foot = xml[xml.index('mz-sb__foot'):]
        self.assertIn('remainingLabel', foot)
        self.assertIn('newCheckLabel', foot)
        self.assertIn('splitPayLabel', foot)
        css = self._css()
        self.assertIn('.mz-sb__foot{', css.replace(' ', ''))
        self.assertNotIn('display:none', css[css.index('@media (max-width: 1100px)'):],
                         "nothing in the footer may be hidden to fit")
