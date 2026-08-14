"""DT-PERF6.1 — kitchen readiness, batched, with the same answer.

The lane board asked the KDS *per car*: 36 cars in the queue meant 36 readiness
searches to draw one screen, and the cost grew with the queue — precisely when the
board matters most. Worse, a board request asked twice, once in the legacy
``preparing -> ready`` mirror and once per card payload.

Two things are pinned here, and they pull in opposite directions on purpose:

* **Parity.** Batched readiness must return exactly what the per-record method
  returned, for every case in ``docs/drive_thru/KITCHEN-READINESS-BATCH-AUDIT.md``
  — including the cancelled-ticket behaviour, which is inherited rather than
  "fixed", because a performance phase is the wrong place to redefine "ready".
* **Complexity.** The number of readiness queries must stop tracking the number of
  cars. Real SQL is counted, not mocked: the instrumentation records what actually
  reached the cursor.
"""
import json
import re
from contextlib import contextmanager
from unittest.mock import patch

from odoo.tests import tagged

from .common import MezzeHttpCase

#: Any statement that touches the KDS ticket table, however it was produced.
_KDS_SQL = re.compile(r'mezze_kds_ticket\b')


@contextmanager
def sql_spy(cr):
    """Record every statement that actually reaches the cursor.

    A spy rather than a stub: the real query still runs, so the test measures the
    production path instead of a description of it.
    """
    seen = []
    original = cr.execute

    def spy(query, params=None, log_exceptions=True):
        seen.append(str(getattr(query, 'code', query)))
        return original(query, params, log_exceptions)

    cr.execute = spy
    try:
        yield seen
    finally:
        cr.execute = original


@tagged('post_install', '-at_install', 'mezze_runtime', 'mezze_dt_perf')
class TestDriveThruReadinessBatch(MezzeHttpCase):
    fixture_profile = 'POS'

    def setUp(self):
        super().setUp()
        icp = self.env['ir.config_parameter'].sudo()
        # A per-BRANCH store token, not the legacy shared one: the legacy path writes
        # an audit row on every request, which a read-only route cannot do — that is
        # a pre-existing interaction, and using the token the product actually issues
        # keeps this test measuring readiness rather than authentication.
        icp.set_param('mezze_bridge.default_branch_id', str(self.pos_config.id))
        self.env['mezze.terminal'].sudo().create({
            'name': 'Perf lane', 'identifier': 'perf-lane', 'token': 'perf-tok',
            'branch_id': self.pos_config.id, 'role': 'terminal', 'active': True})
        icp.set_param('mezze_bridge.api_security', 'observe')
        icp.set_param('mezze_bridge.env_profile', 'development')
        # lazily created on first delivery render; pre-create so a read-only
        # /delivery/list never has to write
        if not self.env['product.product'].sudo().search(
                [('default_code', '=', 'MEZZE_DELIVERY_FEE')], limit=1):
            self.env['product.product'].sudo().create({
                'name': 'Delivery', 'default_code': 'MEZZE_DELIVERY_FEE', 'type': 'service',
                'available_in_pos': True, 'taxes_id': [(6, 0, [])], 'list_price': 0.0})
        self.session = self.open_test_session()
        self.product = self.env['product.product'].search(
            [('available_in_pos', '=', True)], limit=1)
        self.env['mezze.kds.ticket'].sudo().search([]).unlink()
        self.env['mezze.drivethru'].sudo().search([]).unlink()
        self.env.flush_all()

    # ---- fixtures -----------------------------------------------------------
    def _order(self):
        return self.env['pos.order'].create({
            'session_id': self.session.id, 'company_id': self.company.id,
            'lines': [(0, 0, {'product_id': self.product.id, 'qty': 1,
                              'price_unit': 10.0, 'price_subtotal': 10.0,
                              'price_subtotal_incl': 10.0})],
            'amount_total': 10.0, 'amount_tax': 0.0,
            'amount_paid': 0.0, 'amount_return': 0.0})

    def _car(self, states, lane=1, vehicle='CAR'):
        """A car whose order carries one KDS ticket per entry in ``states``.

        ``states`` is a list of ticket states; an empty list means the kitchen was
        never asked to cook anything.
        """
        order = self._order()
        for i, st in enumerate(states):
            self.env['mezze.kds.ticket'].create({
                'pos_order_id': order.id, 'station': 'Station %d' % (i + 1),
                'state': st})
        car = self.env['mezze.drivethru'].create({
            'pos_order_id': order.id, 'lane': lane, 'vehicle': vehicle,
            'vehicle_stage': 'lane'})
        self.env.flush_all()
        return car

    def _post(self, path, body):
        r = self.url_open('/mezze/api/v1' + path,
                          data=json.dumps(dict(body, token='perf-tok')),
                          headers={'Content-Type': 'application/json'}, timeout=60)
        return r.status_code, r.json()

    # ---------------------------------------------------------------- parity
    #: audit case -> (ticket states, expected readiness)
    CASES = [
        ('A no tickets',                    [],                                  True),
        ('B one preparing',                 ['preparing'],                       False),
        ('C one ready',                     ['ready'],                           True),
        ('D all ready',                     ['ready', 'ready', 'served'],        True),
        ('E one still preparing',           ['ready', 'preparing'],              False),
        ('F cancelled ticket blocks',       ['ready', 'cancel'],                 False),
        ('F2 only a cancelled ticket',      ['cancel'],                          False),
        ('G multiple stations, one behind', ['served', 'ready', 'fired'],        False),
        ('G2 multiple stations, all done',  ['served', 'served', 'ready'],       True),
        ('H accepted counts as not done',   ['accepted'],                        False),
    ]

    def test_01_batch_matches_the_scalar_answer_case_by_case(self):
        cars = self.env['mezze.drivethru']
        expected = {}
        for label, states, want in self.CASES:
            car = self._car(states, vehicle=label)
            cars |= car
            expected[car.id] = (label, want)
        batch = cars._kitchen_ready_map()
        self.assertEqual(set(batch), set(cars.ids), 'every record gets an answer')
        for car in cars:
            label, want = expected[car.id]
            self.assertEqual(batch[car.id], want, 'batch disagrees with the audit: %s' % label)
            self.assertEqual(car._kitchen_ready(), want,
                             'scalar disagrees with the audit: %s' % label)
            self.assertEqual(batch[car.id], car._kitchen_ready(),
                             'scalar and batch disagree: %s' % label)

    def test_02_an_empty_recordset_answers_nothing_rather_than_failing(self):
        self.assertEqual(self.env['mezze.drivethru']._kitchen_ready_map(), {})

    def test_03_mixed_channels_do_not_contaminate_each_other(self):
        # A counter order's tickets belong to a different pos.order, so they must be
        # invisible to a car — the batch widens the domain from one order to many,
        # which is exactly where a leak would appear.
        ready_car = self._car(['ready'], vehicle='READY')
        counter = self._order()
        self.env['mezze.kds.ticket'].create(
            {'pos_order_id': counter.id, 'station': 'Kitchen', 'state': 'preparing'})
        self.env.flush_all()
        self.assertTrue(ready_car._kitchen_ready_map()[ready_car.id],
                        "another order's unfinished ticket is not this car's problem")

    def test_04_deliveries_share_the_one_algorithm(self):
        # mezze.delivery carried a byte-identical copy of the readiness rule. Both
        # models now answer from the mixin, so they cannot drift apart.
        order = self._order()
        self.env['mezze.kds.ticket'].create(
            {'pos_order_id': order.id, 'station': 'Kitchen', 'state': 'preparing'})
        dlv = self.env['mezze.delivery'].create({
            'pos_order_id': order.id, 'customer_name': 'Nour', 'phone': '+201000000000',
            'address': '1 Road'})
        self.env.flush_all()
        self.assertFalse(dlv._kitchen_ready_map()[dlv.id])
        self.assertEqual(dlv._kitchen_ready(), dlv._kitchen_ready_map()[dlv.id])
        self.env['mezze.kds.ticket'].search(
            [('pos_order_id', '=', order.id)]).write({'state': 'ready'})
        self.env.flush_all()
        self.assertTrue(dlv._kitchen_ready_map()[dlv.id], 'readiness is live, not cached')

    def test_05_readiness_is_not_stored_on_the_row(self):
        # The KDS stays the single authority. A persisted mirror would need
        # invalidating from every ticket transition, recall and cancel.
        self.assertNotIn('kitchen_ready', self.env['mezze.drivethru']._fields,
                         'readiness must not become a stored field')
        self.assertNotIn('kitchen_ready', self.env['mezze.delivery']._fields)

    # ------------------------------------------------------- query complexity
    def _kds_queries_for(self, count):
        """KDS statements issued while answering readiness for ``count`` cars."""
        cars = self.env['mezze.drivethru']
        for i in range(count):
            cars |= self._car(['preparing'] if i % 3 else ['ready'], vehicle='C%d' % i)
        self.env.flush_all()
        # read the relation first: the measurement is of the READINESS work, not of
        # the caller's own prefetching, which any consumer pays once regardless
        cars.mapped('pos_order_id')
        with sql_spy(self.env.cr) as seen:
            result = cars._kitchen_ready_map()
        self.assertEqual(len(result), count)
        return len([q for q in seen if _KDS_SQL.search(q)])

    def test_10_readiness_queries_do_not_track_the_queue(self):
        # The gate. Before: 1 / 6 / 36 / 100 cars cost 1 / 6 / 36 / 100 searches.
        measured = {n: self._kds_queries_for(n) for n in (1, 6, 36, 100)}
        for n, q in measured.items():
            self.assertLessEqual(
                q, 2, 'readiness for %d cars took %d KDS queries (%r)' % (n, q, measured))
        self.assertEqual(measured[1], measured[100],
                         'the count still moves with the queue: %r' % (measured,))

    def test_11_one_query_is_what_we_actually_get(self):
        # Stated separately from the <= 2 gate so a regression to two queries is
        # visible as a change rather than silently absorbed by the ceiling.
        self.assertEqual(self._kds_queries_for(36), 1)

    # -------------------------------------------------- the board, over HTTP
    @contextmanager
    def _readiness_call_spy(self):
        """Count readiness entry points during a real request.

        The board runs in the HTTP worker thread on its own cursor, so SQL counted on
        the test cursor would miss it. Counting the entry points instead proves the
        shape that matters: the per-car scalar must not be reached at all, and the
        batch must be computed once for the whole request.
        """
        DT = type(self.env['mezze.drivethru'])
        calls = {'scalar': 0, 'batch': 0}
        scalar, batch = DT._kitchen_ready, DT._kitchen_ready_map

        def spy_scalar(records):
            calls['scalar'] += 1
            return scalar(records)

        def spy_batch(records):
            calls['batch'] += 1
            return batch(records)

        with patch.object(DT, '_kitchen_ready', spy_scalar), \
             patch.object(DT, '_kitchen_ready_map', spy_batch):
            yield calls

    def _board(self, cars):
        with self._readiness_call_spy() as calls:
            code, res = self._post('/drivethru/board', {'config_id': self.pos_config.id})
        self.assertEqual(code, 200, res)
        self.assertTrue(res.get('ok'), res)
        self.assertEqual(len(res['cars']), cars, res.get('cars'))
        return res, calls

    def test_20_a_board_request_computes_readiness_once(self):
        # Every car still cooking, so the legacy mirror has nothing to write and the
        # request runs exactly once — the clean measurement of "readiness per request".
        for i in range(12):
            self._car(['preparing'], vehicle='B%d' % i)
        self.env.flush_all()
        _res, calls = self._board(12)
        self.assertEqual(calls['batch'], 1,
                         'one board request, one readiness computation')
        self.assertEqual(calls['scalar'], 0,
                         'no per-car readiness search survives inside the request')

    def test_21_the_legacy_state_mirror_does_not_reintroduce_the_n_plus_1(self):
        # /drivethru/board still mirrors kitchen readiness onto the legacy `state`
        # field. That loop asked the KDS per car too, so optimising only the payload
        # would have moved the N+1 rather than closed it.
        #
        # A mirroring request writes, and the route is declared read-only, so Odoo
        # replays the whole request on a read-write cursor: the handler runs twice.
        # That is PRE-EXISTING routing behaviour, not something batching introduced —
        # what this pins is that each attempt costs ONE readiness computation and
        # never a per-car one, so the cost no longer scales with the queue either way.
        cars = [self._car(['ready'], vehicle='M%d' % i) for i in range(8)]
        self.assertTrue(all(c.state == 'preparing' for c in cars))
        _res, calls = self._board(8)
        self.assertEqual(calls['scalar'], 0, 'the mirror reads the batch too')
        self.assertLessEqual(calls['batch'], 2,
                             'at most one computation per transaction attempt')
        for car in cars:
            car.invalidate_recordset()
            self.assertEqual(car.state, 'ready', 'the mirror still works')

    def test_22_the_board_still_reports_the_right_answer_per_car(self):
        ready = self._car(['ready', 'served'], vehicle='DONE')
        cooking = self._car(['ready', 'preparing'], vehicle='COOKING')
        none = self._car([], vehicle='NOTICKETS')
        res, _calls = self._board(3)
        by_id = {c['id']: c for c in res['cars']}
        self.assertTrue(by_id[ready.id]['kitchen_ready'])
        self.assertFalse(by_id[cooking.id]['kitchen_ready'])
        self.assertTrue(by_id[none.id]['kitchen_ready'])

    def test_23_readiness_is_live_across_requests(self):
        # Batching must not introduce a stale answer: bumping the ticket between two
        # requests has to flip the board without anything being invalidated by hand.
        car = self._car(['preparing'], vehicle='LIVE')
        res, _c = self._board(1)
        self.assertFalse(res['cars'][0]['kitchen_ready'])
        self.env['mezze.kds.ticket'].search(
            [('pos_order_id', '=', car.pos_order_id.id)]).write({'state': 'ready'})
        self.env.flush_all()
        res, _c = self._board(1)
        self.assertTrue(res['cars'][0]['kitchen_ready'],
                        'a KDS bump reaches the board without a refresh of anything else')

    def test_24_the_delivery_board_shares_the_batched_contract(self):
        order = self._order()
        self.env['mezze.kds.ticket'].create(
            {'pos_order_id': order.id, 'station': 'Kitchen', 'state': 'ready'})
        self.env['mezze.delivery'].create({
            'pos_order_id': order.id, 'customer_name': 'Nour', 'phone': '+201000000001',
            'address': '2 Road'})
        self.env.flush_all()
        DLV = type(self.env['mezze.delivery'])
        calls = {'scalar': 0}
        scalar = DLV._kitchen_ready

        def spy(records):
            calls['scalar'] += 1
            return scalar(records)

        with patch.object(DLV, '_kitchen_ready', spy):
            code, res = self._post('/delivery/list', {'config_id': self.pos_config.id})
        self.assertEqual(code, 200, res)
        self.assertEqual(calls['scalar'], 0,
                         'the delivery board carried the identical per-row search')
        self.assertTrue(res['deliveries'][0]['kitchen_ready'], res)
