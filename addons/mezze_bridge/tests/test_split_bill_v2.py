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
