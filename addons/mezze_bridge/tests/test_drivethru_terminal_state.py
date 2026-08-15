"""Drive-thru terminal lifecycle — a finished visit cannot be brought back.

The master state audit traced a hole the certified suite had never touched:
``/drivethru/stage`` checked that the record existed and nothing else, and
``_set_stage`` had no terminal guard at all. So two authenticated calls —

    cancel  ->  window  ->  collected

walked a *cancelled* visit back to the window and handed food out against it. The
same shape resurrected a departed car. Neither the endpoint nor the model refused,
because the vehicle journey had a start and an end but no wall at the end.

``mezze.delivery`` had solved exactly this years earlier with ``TERMINAL`` +
``_LEGAL`` + a guarded ``_transition``; the drive-thru simply never got its wall.

These tests are the wall. They are written against ``vehicle_stage``, never the
legacy ``state`` field, because ``state`` still carries kitchen values
(``preparing``/``ready``) and cannot answer where a car is.
"""
import json

from odoo.exceptions import UserError
from odoo.tests import tagged

from ..models.drivethru import (ACTIVE_STAGES, LEGAL_TRANSITIONS, TERMINAL_STAGES,
                                VEHICLE_STAGE_KEYS)
from .common import MezzeHttpCase


@tagged('post_install', '-at_install', 'mezze_runtime', 'mezze_drivethru_terminal')
class TestDriveThruTerminalState(MezzeHttpCase):
    fixture_profile = 'POS'

    def setUp(self):
        super().setUp()
        icp = self.env['ir.config_parameter'].sudo()
        icp.set_param('mezze_bridge.api_token', 'term-tok')
        icp.set_param('mezze_bridge.api_security', 'observe')
        icp.set_param('mezze_bridge.env_profile', 'development')
        icp.set_param('mezze_bridge.drivethru_topology', 'combined')
        self.session = self.open_test_session()
        self.product = self.env['product.product'].search(
            [('available_in_pos', '=', True)], limit=1)
        self.env['mezze.drivethru'].sudo().search([]).unlink()
        self.env.flush_all()

    # ---- fixtures -----------------------------------------------------------
    def _post(self, path, body):
        r = self.url_open('/mezze/api/v1' + path,
                          data=json.dumps(dict(body, token='term-tok')),
                          headers={'Content-Type': 'application/json'}, timeout=30)
        try:
            return r.status_code, r.json()
        except Exception:                                       # noqa: BLE001
            return r.status_code, {'_raw': r.text[:200]}

    def _car(self, vehicle='RED SUV', paid=True, lane=1):
        order = self.env['pos.order'].create({
            'session_id': self.session.id, 'company_id': self.company.id,
            'lines': [(0, 0, {'product_id': self.product.id, 'qty': 1,
                              'price_unit': 10.0, 'price_subtotal': 10.0,
                              'price_subtotal_incl': 10.0})],
            'amount_total': 10.0, 'amount_tax': 0.0,
            'amount_paid': 10.0 if paid else 0.0, 'amount_return': 0.0})
        car = self.env['mezze.drivethru'].create({
            'pos_order_id': order.id, 'lane': lane, 'vehicle': vehicle,
            'vehicle_stage': 'lane'})
        self.env.flush_all()
        return car

    def _stage(self, car, action):
        return self._post('/drivethru/stage',
                          {'drivethru_id': car.id, 'action': action})

    def _cancelled_car(self, vehicle='CANCELLED'):
        car = self._car(vehicle)
        car._claim_service_sequence()
        code, _res = self._stage(car, 'cancel')
        self.assertEqual(code, 200)
        car.invalidate_recordset()
        self.assertEqual(car.vehicle_stage, 'cancelled')
        return car

    def _departed_car(self, vehicle='DEPARTED'):
        """A car taken all the way through a legitimate handoff."""
        car = self._car(vehicle, paid=True)
        self.assertEqual(self._stage(car, 'window')[0], 200)
        code, res = self._stage(car, 'collected')
        self.assertEqual(code, 200, res)
        car.invalidate_recordset()
        self.assertEqual(car.vehicle_stage, 'departed')
        self.assertTrue(car.collected_at)
        return car

    # ---- the contract itself ------------------------------------------------
    def test_01_the_transition_map_covers_every_stage_and_closes_the_terminals(self):
        self.assertEqual(sorted(LEGAL_TRANSITIONS), sorted(VEHICLE_STAGE_KEYS),
                         'every declared stage needs a declared contract')
        for stage in TERMINAL_STAGES:
            self.assertEqual(LEGAL_TRANSITIONS[stage], (),
                             '%s must reach nothing' % stage)
        for stage in ACTIVE_STAGES:
            self.assertTrue(LEGAL_TRANSITIONS[stage],
                            'an active car must still be able to move (%s)' % stage)

    # ---- 1 + 2: a cancelled visit cannot be resurrected ---------------------
    def test_02_cancelled_cannot_be_called_forward(self):
        car = self._cancelled_car()
        code, res = self._stage(car, 'window')
        self.assertEqual(code, 409, res)
        self.assertEqual(res.get('error'), 'invalid_transition', res)
        car.invalidate_recordset()
        self.assertEqual(car.vehicle_stage, 'cancelled',
                         'the refusal left the visit exactly where it was')

    def test_03_cancelled_cannot_be_collected(self):
        car = self._cancelled_car()
        code, res = self._stage(car, 'collected')
        self.assertEqual(code, 409, res)
        self.assertEqual(res.get('error'), 'invalid_transition', res)
        car.invalidate_recordset()
        self.assertFalse(car.collected_at, 'nothing was ever handed over')
        self.assertEqual(car.vehicle_stage, 'cancelled')

    def test_04_the_two_step_resurrection_is_closed(self):
        # The exact sequence the audit traced: cancel, walk it back to the window,
        # then hand food out against a void order.
        car = self._cancelled_car('THE EXPLOIT')
        self.assertEqual(self._stage(car, 'window')[0], 409)
        self.assertEqual(self._stage(car, 'collected')[0], 409)
        car.invalidate_recordset()
        self.assertEqual(car.vehicle_stage, 'cancelled')
        self.assertFalse(car.collected_at)

    def test_05_a_cancelled_visit_cannot_be_charged(self):
        # Taking money for a cancelled order is the same defect wearing a hat.
        car = self._cancelled_car()
        paid_before = car.pos_order_id.amount_paid
        code, res = self._stage(car, 'pay')
        self.assertEqual(code, 409, res)
        self.assertEqual(res.get('error'), 'invalid_transition')
        car.pos_order_id.invalidate_recordset()
        self.assertEqual(car.pos_order_id.amount_paid, paid_before)

    def test_06_cancelling_a_cancelled_visit_is_a_harmless_no_op(self):
        # A stale board will do this. It should agree, not alarm.
        car = self._cancelled_car()
        code, res = self._stage(car, 'cancel')
        self.assertEqual(code, 200, res)
        self.assertTrue(res.get('unchanged'), 'and says plainly that it did nothing')
        car.invalidate_recordset()
        self.assertEqual(car.vehicle_stage, 'cancelled')

    # ---- 3 + 4 + 6: a departed visit stays departed -------------------------
    def test_07_departed_cannot_be_called_forward(self):
        car = self._departed_car()
        first = car.collected_at
        code, res = self._stage(car, 'window')
        self.assertEqual(code, 409, res)
        self.assertEqual(res.get('error'), 'invalid_transition', res)
        car.invalidate_recordset()
        self.assertEqual(car.vehicle_stage, 'departed')
        self.assertEqual(car.collected_at, first)

    def test_08_departed_cannot_be_cancelled_after_the_fact(self):
        car = self._departed_car()
        code, res = self._stage(car, 'cancel')
        self.assertEqual(code, 409, res)
        self.assertEqual(res.get('error'), 'invalid_transition')
        car.invalidate_recordset()
        self.assertEqual(car.vehicle_stage, 'departed',
                         'a handed-off order is not cancellable by moving the car')

    def test_09_handing_off_twice_is_idempotent_and_keeps_the_first_timestamp(self):
        car = self._departed_car()
        first = car.collected_at
        seq = car.service_sequence
        code, res = self._stage(car, 'collected')
        self.assertEqual(code, 200, res)
        self.assertTrue(res.get('unchanged'))
        car.invalidate_recordset()
        self.assertEqual(car.collected_at, first, 'the original handoff time stands')
        self.assertEqual(car.service_sequence, seq)

    # ---- 7: history is preserved -------------------------------------------
    def test_10_a_refused_transition_rewrites_no_history(self):
        car = self._car('HISTORY')
        self.assertEqual(self._stage(car, 'window')[0], 200)
        car.invalidate_recordset()
        before = (car.lane_sequence, car.service_sequence,
                  car.called_at, car.window_at, car.placed_at)
        self.assertEqual(self._stage(car, 'cancel')[0], 200)
        for action in ('window', 'pickup', 'hold', 'collected', 'ready', 'pay'):
            self.assertEqual(self._stage(car, action)[0], 409,
                             '%s must be refused on a cancelled visit' % action)
        car.invalidate_recordset()
        self.assertEqual((car.lane_sequence, car.service_sequence,
                          car.called_at, car.window_at, car.placed_at), before,
                         'a cancelled car keeps its number and its timestamps')

    # ---- 8 + 9 + 10: the live journeys still work ---------------------------
    def test_11_the_combined_window_journey_still_completes(self):
        self.env['ir.config_parameter'].sudo().set_param(
            'mezze_bridge.drivethru_topology', 'combined')
        self.env.flush_all()
        car = self._car('COMBINED')
        self.assertEqual(self._stage(car, 'window')[0], 200)
        car.invalidate_recordset()
        self.assertEqual(car.vehicle_stage, 'payment_window')
        self.assertTrue(car.service_sequence, 'it claimed its place in the merged path')
        code, res = self._stage(car, 'collected')
        self.assertEqual(code, 200, res)
        car.invalidate_recordset()
        self.assertEqual(car.vehicle_stage, 'departed')

    def test_12_the_two_window_journey_still_completes(self):
        self.env['ir.config_parameter'].sudo().set_param(
            'mezze_bridge.drivethru_topology', 'two_window')
        self.env.flush_all()
        car = self._car('TWO WINDOW')
        self.assertEqual(self._stage(car, 'window')[0], 200)
        car.invalidate_recordset()
        self.assertEqual(car.vehicle_stage, 'payment_window')
        # handoff happens at PICKUP here, so payment is not yet the place
        self.assertEqual(self._stage(car, 'collected')[0], 409)
        self.assertEqual(self._stage(car, 'pickup')[0], 200)
        car.invalidate_recordset()
        self.assertEqual(car.vehicle_stage, 'pickup_window')
        code, res = self._stage(car, 'collected')
        self.assertEqual(code, 200, res)
        car.invalidate_recordset()
        self.assertEqual(car.vehicle_stage, 'departed')

    def test_13_active_cars_can_still_move_between_positions(self):
        # The guard must close the exit, not the lane. Holding and going back to
        # pay are movements real branches make.
        car = self._car('MOVING')
        self.assertEqual(self._stage(car, 'window')[0], 200)
        self.assertEqual(self._stage(car, 'hold')[0], 200)
        car.invalidate_recordset()
        self.assertEqual(car.vehicle_stage, 'holding')
        self.assertEqual(self._stage(car, 'window')[0], 200)
        car.invalidate_recordset()
        self.assertEqual(car.vehicle_stage, 'payment_window')

    # ---- 11: the handoff matrix is untouched --------------------------------
    def test_14_the_handoff_gates_are_not_weakened(self):
        unpaid = self._car('UNPAID', paid=False)
        self.assertEqual(self._stage(unpaid, 'window')[0], 200)
        code, res = self._stage(unpaid, 'collected')
        self.assertEqual(code, 409, res)
        self.assertEqual(res.get('error'), 'unpaid', 'still the payment gate, not ours')

        cooking = self._car('COOKING', paid=True)
        self.env['mezze.kds.ticket'].create(
            {'pos_order_id': cooking.pos_order_id.id, 'station': 'Kitchen',
             'state': 'preparing'})
        self.env.flush_all()
        self.assertEqual(self._stage(cooking, 'window')[0], 200)
        code, res = self._stage(cooking, 'collected')
        self.assertEqual(res.get('error'), 'kitchen_not_ready', res)

        in_lane = self._car('IN LANE', paid=True)
        code, res = self._stage(in_lane, 'collected')
        self.assertEqual(res.get('error'), 'not_at_window', res)

    # ---- the model refuses too, not only the endpoint -----------------------
    def test_15_the_model_refuses_a_terminal_move_without_an_endpoint(self):
        car = self._cancelled_car()
        for stage in ('lane', 'called', 'payment_window', 'pickup_window',
                      'holding', 'departed'):
            with self.assertRaises(UserError, msg='cancelled -> %s must raise' % stage):
                car._set_stage(stage)
        car.invalidate_recordset()
        self.assertEqual(car.vehicle_stage, 'cancelled')

    def test_16_the_legacy_state_field_is_not_a_back_door(self):
        # write() derives vehicle_stage from the legacy field for compatibility. That
        # derivation is the other way into a terminal record, so it holds too.
        car = self._departed_car()
        with self.assertRaises(UserError):
            car.write({'state': 'at_window'})
        car.invalidate_recordset()
        self.assertEqual(car.vehicle_stage, 'departed')
        self.assertEqual(car.state, 'collected')

    # ---- the race the audit asked about ------------------------------------
    def test_17_a_cancel_that_lands_first_wins_against_a_later_call_forward(self):
        # Two tills, one car. Whatever the operators intended, the cancellation is
        # authoritative once it commits, and the call-forward that arrives after it
        # must not put the car back at a window. Ordered rather than threaded: a POS
        # test cursor serialises, so real parallelism here would deadlock rather than
        # test anything — the interleaving that matters is which write LANDS first,
        # and that is what this asserts. A genuine 4-worker HTTP race is recorded in
        # docs/drive_thru/TERMINAL-STATE-RACE-EVIDENCE.md.
        car = self._car('CONTESTED')
        self.assertEqual(self._stage(car, 'window')[0], 200)
        self.assertEqual(self._stage(car, 'cancel')[0], 200)     # till A wins
        code, res = self._stage(car, 'window')                   # till B, a beat late
        self.assertEqual(code, 409, res)
        self.assertEqual(res.get('error'), 'invalid_transition')
        car.invalidate_recordset()
        self.assertEqual(car.vehicle_stage, 'cancelled',
                         'the final state is never payment_window after a cancel wins')

    def test_18_a_cancelled_car_leaves_the_board_so_a_stale_client_reconciles(self):
        car = self._car('GONE')
        self.assertEqual(self._stage(car, 'cancel')[0], 200)
        code, board = self._post('/drivethru/board', {'config_id': self.pos_config.id})
        self.assertEqual(code, 200)
        row = [c for c in board['cars'] if c['id'] == car.id]
        self.assertTrue(row, 'it is still reported, within the done-window')
        self.assertEqual(row[0]['vehicle_stage'], 'cancelled',
                         'and reported as finished, which is what the client filters on')
