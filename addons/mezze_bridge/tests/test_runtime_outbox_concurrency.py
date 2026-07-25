"""Duplicate-dispatch prevention + ordering under REAL concurrent connections.

Tagged ``mezze_runtime``. True OS-thread concurrency is not reliably observable
inside Odoo's test transaction (the registry is patched to hand out TestCursors,
and cross-thread ORM over pooled connections is unsafe) — the end-to-end threaded
proof lives in ``tests/concurrency/outbox_race.py`` (run via ``odoo shell``).

Here we prove the same guarantees DETERMINISTICALLY with two genuinely independent
PostgreSQL connections (``db_connect``) in one thread: connection A claims a batch
and HOLDS its FOR UPDATE locks (uncommitted); connection B then claims and, thanks
to FOR UPDATE SKIP LOCKED, receives a DISJOINT set — never the rows A holds. The
per-aggregate ordering predicate is proven the same way (B cannot claim A2 while
A1 is unfinished).
"""

from odoo import SUPERUSER_ID, api
from odoo.sql_db import db_connect
from odoo.tests.common import TransactionCase, tagged

from ..models.outbox_event import register_consumer, OUTBOX_CONSUMERS

_EVENT_TYPE = 'test.concurrency.outbox'


@tagged("post_install", "-at_install", "mezze_runtime")
class TestOutboxConcurrency(TransactionCase):

    def setUp(self):
        super().setUp()
        register_consumer(_EVENT_TYPE, lambda env, ev: None)
        self.dbname = self.env.cr.dbname
        self._cleanup()
        self._seed()

    def tearDown(self):
        OUTBOX_CONSUMERS.pop(_EVENT_TYPE, None)
        self._cleanup()
        super().tearDown()

    def _cleanup(self):
        conn = db_connect(self.dbname)
        with conn.cursor() as cr:
            cr.execute("DELETE FROM mezze_outbox_event WHERE event_type=%s", (_EVENT_TYPE,))
            cr.commit()

    def _seed(self):
        self.independent = ['ind-%d' % i for i in range(20)]
        self.ordered_agg = 'ordered-pair'
        conn = db_connect(self.dbname)
        with conn.cursor() as cr:
            env = api.Environment(cr, SUPERUSER_ID, {})
            Event = env['mezze.outbox.event']
            for agg in self.independent:
                Event.publish(_EVENT_TYPE, payload={}, aggregate_type='cc', aggregate_id=agg)
            self.e1 = Event.publish(_EVENT_TYPE, payload={'i': 1}, aggregate_type='cc',
                                    aggregate_id=self.ordered_agg, aggregate_version=1).id
            self.e2 = Event.publish(_EVENT_TYPE, payload={'i': 2}, aggregate_type='cc',
                                    aggregate_id=self.ordered_agg, aggregate_version=2).id
            cr.commit()

    def test_skip_locked_prevents_duplicate_claim(self):
        """Two independent connections claiming at once get DISJOINT rows, and the
        ordered aggregate never yields A2 while A1 is still held (ordering)."""
        conn_a = db_connect(self.dbname)
        conn_b = db_connect(self.dbname)
        cr_a = conn_a.cursor()
        cr_b = conn_b.cursor()
        try:
            env_a = api.Environment(cr_a, SUPERUSER_ID, {})
            env_b = api.Environment(cr_b, SUPERUSER_ID, {})
            # A claims 8 and HOLDS the locks (no commit yet)
            claimed_a = env_a['mezze.outbox.event']._claim('A', 8, 300)
            ids_a = set(claimed_a.ids)
            self.assertEqual(len(ids_a), 8, "A did not claim a full batch")

            # B claims 8 concurrently -> SKIP LOCKED skips A's locked rows
            claimed_b = env_b['mezze.outbox.event']._claim('B', 8, 300)
            ids_b = set(claimed_b.ids)
            self.assertEqual(len(ids_b), 8, "B did not claim a full batch")

            # duplicate-dispatch prevention: no row claimed by both connections
            self.assertEqual(ids_a & ids_b, set(),
                             "the same event was claimed by two connections")

            # ordering: whichever connection holds the ordered aggregate's e1, the
            # OTHER must not have claimed e2 (a later event of the same aggregate)
            holder = ids_a if self.e1 in ids_a else ids_b
            other = ids_b if self.e1 in ids_a else ids_a
            if self.e1 in holder:
                self.assertNotIn(self.e2, other,
                                 "claimed a later aggregate event before its predecessor")
                self.assertNotIn(self.e2, holder,
                                 "claimed two events of one aggregate at once")

            cr_a.rollback()
            cr_b.rollback()
        finally:
            cr_a.close()
            cr_b.close()

    def test_end_to_end_drain_two_connections(self):
        """Sequentially drain with two independent connections (each commits its
        batch), proving every event is delivered exactly once and the ordered pair
        stays in order — the deterministic analogue of the threaded harness."""
        delivered = []
        register_consumer(_EVENT_TYPE, lambda env, ev: delivered.append(ev.id))
        try:
            for _ in range(60):
                progressed = 0
                for wid in ('A', 'B'):
                    conn = db_connect(self.dbname)
                    with conn.cursor() as cr:
                        env = api.Environment(cr, SUPERUSER_ID, {})
                        m = env['mezze.outbox.event']._dispatch_batch(
                            worker_id=wid, batch_size=4, max_attempts=5,
                            visibility_seconds=300, commit=True)
                        progressed += m['claimed']
                if progressed == 0:
                    break
        finally:
            register_consumer(_EVENT_TYPE, lambda env, ev: None)

        conn = db_connect(self.dbname)
        with conn.cursor() as cr:
            cr.execute("SELECT status, count(*) FROM mezze_outbox_event "
                       "WHERE event_type=%s GROUP BY status", (_EVENT_TYPE,))
            by_status = dict(cr.fetchall())
        total = len(self.independent) + 2
        self.assertEqual(by_status.get('done'), total, "not all delivered: %s" % by_status)
        self.assertEqual(len(delivered), total, "delivered count wrong")
        self.assertEqual(len(set(delivered)), total, "an event was delivered twice")
        self.assertLess(delivered.index(self.e1), delivered.index(self.e2),
                        "ordered aggregate delivered out of order")
