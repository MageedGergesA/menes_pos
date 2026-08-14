"""DT-CORE6 — the product owns where each car physically is.

Before this, `mezze.drivethru.state` answered two questions with one value:
`preparing`/`ready` were written back from the KDS (kitchen truth) while
`at_window`/`collected` described the car. One flag had to stand for called
forward, at payment, at pickup and pulled forward, so a two-window branch could
not be represented and "which car is next" was a timer heuristic.

`vehicle_stage` is now the authority for position, `lane_sequence` records arrival
order within a lane, and `service_sequence` records the order cars actually
entered the merged path. `state` is kept in step as a legacy projection so every
existing reader keeps working.
"""
import json

from odoo import fields
from odoo.tests import tagged

from .common import MezzeHttpCase


@tagged('post_install', '-at_install', 'mezze_runtime', 'mezze_drivethru_seq')
class TestDriveThruSequence(MezzeHttpCase):
    fixture_profile = 'POS'

    def setUp(self):
        super().setUp()
        icp = self.env['ir.config_parameter'].sudo()
        icp.set_param('mezze_bridge.api_token', 'seq-tok')
        icp.set_param('mezze_bridge.api_security', 'observe')
        icp.set_param('mezze_bridge.env_profile', 'development')
        icp.set_param('mezze_bridge.drivethru_topology', 'combined')
        self.session = self.open_test_session()
        self.product = self.env['product.product'].search(
            [('available_in_pos', '=', True)], limit=1)
        self.env['mezze.drivethru'].sudo().search([]).unlink()
        self.env.flush_all()

    def _post(self, path, body):
        r = self.url_open('/mezze/api/v1' + path, data=json.dumps(dict(body, token='seq-tok')),
                          headers={'Content-Type': 'application/json'}, timeout=30)
        try:
            return r.status_code, r.json()
        except Exception:
            return r.status_code, {'_raw': r.text[:200]}

    def _car(self, vehicle, lane=1, paid=False):
        order = self.env['pos.order'].create({
            'session_id': self.session.id, 'company_id': self.company.id,
            'lines': [(0, 0, {'product_id': self.product.id, 'qty': 1,
                              'price_unit': 10.0, 'price_subtotal': 10.0,
                              'price_subtotal_incl': 10.0})],
            'amount_total': 10.0, 'amount_tax': 0.0,
            'amount_paid': 10.0 if paid else 0.0, 'amount_return': 0.0})
        return self.env['mezze.drivethru'].create(
            {'pos_order_id': order.id, 'lane': lane, 'vehicle': vehicle})

    # ---- A: single lane -----------------------------------------------------
    def test_arrival_order_is_recorded_once_and_never_rewritten(self):
        a, b, c = self._car('A'), self._car('B'), self._car('C')
        self.assertLess(a.lane_sequence, b.lane_sequence)
        self.assertLess(b.lane_sequence, c.lane_sequence)
        first = a.lane_sequence
        a._set_stage('called')
        a.invalidate_recordset()
        self.assertEqual(a.lane_sequence, first,
                         "a car's place in the line it joined is a historical fact")

    # ---- B: dual lane, the scenario the old model could not express ---------
    def test_two_lanes_merge_in_the_order_they_were_called(self):
        lane1 = [self._car(v, lane=1) for v in ('A', 'B', 'C')]
        lane2 = [self._car(v, lane=2) for v in ('D', 'E', 'F')]
        a, b, _c = lane1
        d, e, _f = lane2
        for car in (a, d, e, b):            # the operator calls A, D, E, B
            car._claim_service_sequence()
        self.env.flush_all()
        merged = self.env['mezze.drivethru'].search(
            [('service_sequence', '>', 0)]).sorted('service_sequence')
        self.assertEqual([x.vehicle for x in merged], ['A', 'D', 'E', 'B'])

        # and this is genuinely different from what arrival time would have said
        by_arrival = self.env['mezze.drivethru'].search([]).sorted('placed_at')
        self.assertNotEqual([x.vehicle for x in by_arrival][:4], ['A', 'D', 'E', 'B'],
                            'the merged order is not just placed_at in disguise')

    # ---- C: the oldest car is not the next car ------------------------------
    def test_next_physical_is_not_most_delayed(self):
        old = self._car('OLD SUV', lane=1)
        old.write({'placed_at': fields.Datetime.subtract(fields.Datetime.now(), minutes=15)})
        fresh = self._car('FRESH SEDAN', lane=2)
        fresh._claim_service_sequence()
        fresh._set_stage('payment_window')
        self.env.flush_all()
        code, board = self._post('/drivethru/board', {'config_id': self.pos_config.id})
        self.assertEqual(code, 200, board)
        cars = {c['vehicle']: c for c in board['cars']}
        # the car AT the window is the one being served...
        self.assertEqual(cars['FRESH SEDAN']['vehicle_stage'], 'payment_window')
        # ...while the longest wait is a different car, and the board says both
        self.assertGreater(cars['OLD SUV']['minutes'], cars['FRESH SEDAN']['minutes'])
        self.assertEqual(board['next_to_call'], old.id,
                         'next to call is the oldest car still IN LANE')

    # ---- idempotency --------------------------------------------------------
    def test_calling_a_car_forward_twice_does_not_renumber_it(self):
        a, b = self._car('A'), self._car('B')
        first = a._claim_service_sequence()
        b._claim_service_sequence()
        again = a._claim_service_sequence()
        self.assertEqual(first, again,
                         'a second call forward must not push the car behind B')
        a.invalidate_recordset()
        self.assertEqual(a.service_sequence, first)

    def test_repeated_transitions_do_not_rewrite_timestamps(self):
        a = self._car('A')
        a._set_stage('payment_window', called_at=fields.Datetime.now(),
                     window_at=fields.Datetime.now())
        a.invalidate_recordset()
        original = a.window_at
        a._set_stage('payment_window', window_at=fields.Datetime.now())
        a.invalidate_recordset()
        self.assertEqual(a.window_at, original, 'first stamp wins')

    # ---- concurrency --------------------------------------------------------
    def test_the_number_comes_from_the_database_not_from_a_table_read(self):
        """`max(service_sequence) + 1` is the wrong mechanism, and this pins that.

        Two terminals calling cars forward in the same instant both read the same
        maximum before either writes, and both mint the same number. The value
        comes from a PostgreSQL sequence instead, whose nextval is atomic across
        processes.

        Genuine multi-process concurrency cannot be exercised from inside an Odoo
        test transaction — the test cursor serialises, and committing is forbidden —
        so this asserts the MECHANISM (a real sequence object, strictly increasing,
        unaffected by what the table contains) and a live 20-way concurrent HTTP
        run is reported separately as evidence.
        """
        model = self.env['mezze.drivethru']
        name = model._SEQ_SERVICE
        first = model._next_sequence(name)

        # it is a real sequence object in the database, not a python counter
        self.env.cr.execute(
            "SELECT 1 FROM pg_class WHERE relkind = 'S' AND relname = %s", (name,))
        self.assertTrue(self.env.cr.fetchone(), 'a PostgreSQL sequence backs it')

        values = [model._next_sequence(name) for _i in range(20)]
        self.assertEqual(len(set(values)), 20, 'every claim is distinct')
        self.assertEqual(values, sorted(values), 'and strictly increasing')
        self.assertGreater(values[0], first)

        # and it does NOT depend on the table: deleting every car does not rewind it
        self.env['mezze.drivethru'].search([]).unlink()
        self.env.flush_all()
        after = model._next_sequence(name)
        self.assertGreater(after, values[-1],
                           'an empty table cannot make the sequence reissue a number')

    # ---- D: two windows -----------------------------------------------------
    def test_a_two_window_branch_tells_payment_and_pickup_apart(self):
        self.env['ir.config_parameter'].sudo().set_param(
            'mezze_bridge.drivethru_topology', 'two_window')
        self.env.flush_all()
        at_pay = self._car('PAYING', lane=1)
        at_pick = self._car('COLLECTING', lane=1)
        at_pay._set_stage('payment_window')
        at_pick._set_stage('pickup_window')
        self.env.flush_all()
        self.assertNotEqual(at_pay.vehicle_stage, at_pick.vehicle_stage,
                            'two cars at two windows are not the same position')
        # both were merely "at_window" under the old model
        self.assertEqual(at_pay.state, 'at_window')
        self.assertEqual(at_pick.state, 'at_window')
        # handoff happens at PICKUP in this topology
        self.assertFalse(at_pay._at_handoff_position())
        self.assertTrue(at_pick._at_handoff_position())

    def test_a_combined_branch_hands_off_at_its_single_window(self):
        self.env['ir.config_parameter'].sudo().set_param(
            'mezze_bridge.drivethru_topology', 'combined')
        self.env.flush_all()
        car = self._car('ONE WINDOW', lane=1)
        car._set_stage('payment_window')
        self.assertTrue(car._at_handoff_position(),
                        'a combined branch serves both jobs at one window')

    # ---- H: cancellation ----------------------------------------------------
    def test_cancelling_a_car_leaves_the_order_of_the_others_alone(self):
        a, b, c = self._car('A'), self._car('B'), self._car('C')
        for car in (a, b, c):
            car._claim_service_sequence()
        self.env.flush_all()
        b_seq = b.service_sequence
        b._set_stage('cancelled')
        self.env.flush_all()
        a.invalidate_recordset()
        c.invalidate_recordset()
        b.invalidate_recordset()
        self.assertEqual(b.service_sequence, b_seq,
                         'history keeps its number; only the ACTIVE queue closes up')
        self.assertLess(a.service_sequence, c.service_sequence,
                        'the cars around it keep their relative order')
        code, board = self._post('/drivethru/board', {'config_id': self.pos_config.id})
        active = [x['vehicle'] for x in board['cars']
                  if x['vehicle_stage'] not in ('departed', 'cancelled')]
        self.assertNotIn('B', active, 'a cancelled car leaves the active queue')

    # ---- J: persistence -----------------------------------------------------
    def test_the_order_survives_a_restart(self):
        # Nothing about physical position may live only in a browser.
        cars = [self._car(v) for v in ('A', 'B', 'C')]
        for car in cars:
            car._claim_service_sequence()
        self.env.flush_all()
        expected = [c.vehicle for c in
                    self.env['mezze.drivethru'].search([]).sorted('service_sequence')]
        self.env.invalidate_all()          # nothing cached survives
        rebuilt = [c.vehicle for c in
                   self.env['mezze.drivethru'].search([]).sorted('service_sequence')]
        self.assertEqual(rebuilt, expected)
        self.assertTrue(all(c.service_sequence for c in
                            self.env['mezze.drivethru'].search([])),
                        'reconstructed from the database, not from a session')

    # ---- legacy compatibility ----------------------------------------------
    def test_the_legacy_state_field_still_answers_for_old_readers(self):
        car = self._car('A')
        car._set_stage('payment_window')
        self.assertEqual(car.state, 'at_window', 'old readers see what they expect')
        car._set_stage('departed')
        self.assertEqual(car.state, 'collected')
        car2 = self._car('B')
        car2._set_stage('cancelled')
        self.assertEqual(car2.state, 'cancelled')
