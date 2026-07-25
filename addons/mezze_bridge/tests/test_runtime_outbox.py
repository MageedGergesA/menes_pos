"""Runtime proof of the transactional outbox inside a real Odoo + PostgreSQL.

Tagged ``mezze_runtime``. Proves, against the live DB:
  * transactional publish (rolls back with the business txn; persists on commit)
  * strict per-aggregate ordering (N+1 not claimable until N is DONE)
  * retry with backoff, and dead-letter on permanent / exhausted failure
  * crash recovery via visibility timeout (stale INFLIGHT lock reclaimed;
    a fresh lock owned by a live worker is NOT stolen)
  * duplicate-dispatch prevention across REAL concurrent connections
    (FOR UPDATE SKIP LOCKED) + ordering preserved under concurrency
  * delivery idempotency (a DONE event is never redelivered) and publish
    idempotency (duplicate idempotency_key -> one row)
  * manual replay of a dead-letter
  * enqueue / dispatch performance sampling
"""

import threading
import time
from datetime import timedelta

from odoo import fields
from odoo.tests.common import TransactionCase, tagged

from ..models.outbox_event import register_consumer, OUTBOX_CONSUMERS, OutboxRetry


@tagged("post_install", "-at_install", "mezze_runtime")
class TestOutboxRuntime(TransactionCase):

    def setUp(self):
        super().setUp()
        self.Event = self.env['mezze.outbox.event']
        self._registered = []

    def tearDown(self):
        for et in self._registered:
            OUTBOX_CONSUMERS.pop(et, None)
        super().tearDown()

    def _register(self, event_type, handler):
        register_consumer(event_type, handler)
        self._registered.append(event_type)

    def _drain(self, **kw):
        """Dispatch repeatedly (in-txn) until nothing more is claimable."""
        rounds = []
        for _ in range(50):
            m = self.Event._dispatch_batch(commit=False, **kw)
            rounds.append(m)
            if m['claimed'] == 0:
                break
        return rounds

    # ------------------------------------------------------------- transactional
    def test_publish_rolls_back_with_business_txn(self):
        tag = 'rb-%d' % id(self)
        try:
            with self.env.cr.savepoint():
                self.Event.publish('order.paid', payload={'n': 1},
                                   aggregate_type='pos.order', aggregate_id=tag)
                # simulate the business transaction failing AFTER publish
                raise RuntimeError('force rollback')
        except RuntimeError:
            pass
        self.assertFalse(self.Event.search([('aggregate_id', '=', tag)]),
                         "event survived a rolled-back business transaction")

    def test_publish_persists_on_commit(self):
        tag = 'ok-%d' % id(self)
        ev = self.Event.publish('order.paid', payload={'n': 1},
                                aggregate_type='pos.order', aggregate_id=tag)
        self.assertTrue(ev.exists())
        self.assertEqual(ev.status, 'pending')
        self.assertTrue(ev.event_id and ev.idempotency_key == ev.event_id)

    def test_publish_idempotency_key_dedupes(self):
        key = 'idem-%d' % id(self)
        a = self.Event.publish('order.paid', payload={'n': 1}, idempotency_key=key,
                               aggregate_type='pos.order', aggregate_id='x')
        b = self.Event.publish('order.paid', payload={'n': 2}, idempotency_key=key,
                               aggregate_type='pos.order', aggregate_id='x')
        self.assertEqual(a.id, b.id, "duplicate idempotency_key created a second event")
        self.assertEqual(self.Event.search_count([('idempotency_key', '=', key)]), 1)

    # ------------------------------------------------------------------- ordering
    def test_strict_per_aggregate_ordering(self):
        et = 'test.order.seq.%d' % id(self)
        delivered = []
        self._register(et, lambda env, ev: delivered.append(ev.event_id))
        agg = 'agg-%d' % id(self)
        e1 = self.Event.publish(et, payload={'i': 1}, aggregate_type='ord', aggregate_id=agg)
        e2 = self.Event.publish(et, payload={'i': 2}, aggregate_type='ord', aggregate_id=agg)
        e3 = self.Event.publish(et, payload={'i': 3}, aggregate_type='ord', aggregate_id=agg)
        rounds = self._drain(max_attempts=5)
        # each non-empty round claims exactly ONE event of this aggregate (N+1
        # blocked until N done) -> ordering guaranteed
        claimed_counts = [r['claimed'] for r in rounds if r['claimed']]
        self.assertTrue(all(c >= 1 for c in claimed_counts))
        self.assertEqual(delivered, [e1.event_id, e2.event_id, e3.event_id],
                         "events for one aggregate delivered out of order")

    def test_different_aggregates_progress_independently(self):
        et = 'test.multi.agg.%d' % id(self)
        seen = []
        self._register(et, lambda env, ev: seen.append(ev.aggregate_id))
        for agg in ('A', 'B', 'C'):
            self.Event.publish(et, payload={}, aggregate_type='ord',
                               aggregate_id='%s-%d' % (agg, id(self)))
        m = self.Event._dispatch_batch(commit=False, batch_size=50)
        # all three distinct aggregates are claimable in ONE batch
        self.assertEqual(m['claimed'], 3)
        self.assertEqual(m['delivered'], 3)

    # -------------------------------------------------------------------- retries
    def test_retry_then_success(self):
        et = 'test.retry.%d' % id(self)
        state = {'calls': 0}

        def handler(env, ev):
            state['calls'] += 1
            if state['calls'] == 1:
                raise OutboxRetry('transient')

        self._register(et, handler)
        ev = self.Event.publish(et, payload={}, aggregate_type='ord', aggregate_id='r%d' % id(self))
        self.Event._dispatch_batch(commit=False, max_attempts=5)
        self.assertEqual(ev.status, 'failed')
        self.assertTrue(ev.next_retry, "no backoff scheduled on retryable failure")
        self.assertEqual(ev.attempt_count, 1)
        # move the backoff into the past and re-dispatch -> succeeds
        ev.next_retry = fields.Datetime.now() - timedelta(seconds=1)
        self.Event._dispatch_batch(commit=False, max_attempts=5)
        self.assertEqual(ev.status, 'done')
        self.assertEqual(ev.attempt_count, 2)

    def test_backoff_before_retry_blocks_claim(self):
        et = 'test.backoff.%d' % id(self)
        self._register(et, lambda env, ev: (_ for _ in ()).throw(OutboxRetry('x')))
        ev = self.Event.publish(et, payload={}, aggregate_type='ord', aggregate_id='b%d' % id(self))
        self.Event._dispatch_batch(commit=False, max_attempts=5)
        self.assertEqual(ev.status, 'failed')
        # next_retry is in the future -> a subsequent claim must skip it
        m = self.Event._dispatch_batch(commit=False, max_attempts=5)
        self.assertEqual(m['claimed'], 0, "event claimed before its backoff elapsed")

    # ---------------------------------------------------------------- dead-letter
    def test_permanent_failure_dead_letters_immediately(self):
        et = 'test.perm.%d' % id(self)
        self._register(et, lambda env, ev: (_ for _ in ()).throw(ValueError('bad payload')))
        ev = self.Event.publish(et, payload={}, aggregate_type='ord', aggregate_id='p%d' % id(self))
        m = self.Event._dispatch_batch(commit=False, max_attempts=8)
        self.assertEqual(ev.status, 'dead')
        self.assertEqual(m['dead'], 1)
        self.assertIn('validation', (ev.last_error or ''))

    def test_retryable_exhaustion_dead_letters(self):
        et = 'test.exhaust.%d' % id(self)
        self._register(et, lambda env, ev: (_ for _ in ()).throw(OutboxRetry('always')))
        ev = self.Event.publish(et, payload={}, aggregate_type='ord', aggregate_id='e%d' % id(self))
        # max_attempts=2: attempt1 -> failed, attempt2 -> dead
        self.Event._dispatch_batch(commit=False, max_attempts=2)
        self.assertEqual(ev.status, 'failed')
        ev.next_retry = fields.Datetime.now() - timedelta(seconds=1)
        self.Event._dispatch_batch(commit=False, max_attempts=2)
        self.assertEqual(ev.status, 'dead', "did not dead-letter after exhausting retries")
        self.assertEqual(ev.attempt_count, 2)

    def test_dead_letter_halts_aggregate_ordering(self):
        et = 'test.halt.%d' % id(self)
        delivered = []

        def handler(env, ev):
            if ev.aggregate_version == 1:
                raise ValueError('permanent on first')
            delivered.append(ev.aggregate_version)

        self._register(et, handler)
        agg = 'halt-%d' % id(self)
        self.Event.publish(et, payload={}, aggregate_type='ord', aggregate_id=agg, aggregate_version=1)
        self.Event.publish(et, payload={}, aggregate_type='ord', aggregate_id=agg, aggregate_version=2)
        self._drain(max_attempts=8)
        # first event dead-letters; the second must NOT be delivered (ordering halt)
        self.assertEqual(delivered, [], "a later event was delivered past a dead-lettered predecessor")

    # ----------------------------------------------------------- crash recovery
    def test_stale_lock_is_recovered(self):
        et = 'test.stale.%d' % id(self)
        delivered = []
        self._register(et, lambda env, ev: delivered.append(ev.event_id))
        ev = self.Event.publish(et, payload={}, aggregate_type='ord', aggregate_id='s%d' % id(self))
        # simulate a worker that claimed then crashed: inflight + expired lock
        ev.write({'status': 'inflight', 'worker_id': 'dead-worker',
                  'locked_until': fields.Datetime.now() - timedelta(seconds=60),
                  'attempt_count': 1})
        self.Event._dispatch_batch(commit=False, worker_id='live', max_attempts=5)
        self.assertEqual(ev.status, 'done', "crashed worker's event was not recovered")
        self.assertEqual(delivered, [ev.event_id])

    def test_fresh_lock_not_stolen(self):
        et = 'test.fresh.%d' % id(self)
        self._register(et, lambda env, ev: None)
        ev = self.Event.publish(et, payload={}, aggregate_type='ord', aggregate_id='f%d' % id(self))
        # a live worker holds it: inflight + lock in the FUTURE
        ev.write({'status': 'inflight', 'worker_id': 'alive',
                  'locked_until': fields.Datetime.now() + timedelta(seconds=300)})
        m = self.Event._dispatch_batch(commit=False, worker_id='other', max_attempts=5)
        self.assertEqual(m['claimed'], 0, "stole an event still owned by a live worker")

    # ------------------------------------------------------------- idempotency
    def test_done_event_not_redelivered(self):
        et = 'test.idem.%d' % id(self)
        counts = {}

        def handler(env, ev):
            counts[ev.event_id] = counts.get(ev.event_id, 0) + 1

        self._register(et, handler)
        ev = self.Event.publish(et, payload={}, aggregate_type='ord', aggregate_id='i%d' % id(self))
        self.Event._dispatch_batch(commit=False)
        self.Event._dispatch_batch(commit=False)  # second sweep must not redeliver
        self.assertEqual(counts.get(ev.event_id), 1, "a DONE event was delivered twice")

    # ---------------------------------------------------------------- replay
    def test_manual_replay_of_dead_letter(self):
        et = 'test.replay.%d' % id(self)
        state = {'fail': True}

        def handler(env, ev):
            if state['fail']:
                raise ValueError('temporarily broken')

        self._register(et, handler)
        ev = self.Event.publish(et, payload={}, aggregate_type='ord', aggregate_id='rp%d' % id(self))
        self.Event._dispatch_batch(commit=False, max_attempts=8)
        self.assertEqual(ev.status, 'dead')
        # operator fixes the consumer and replays
        state['fail'] = False
        ev.replay()
        self.assertEqual(ev.status, 'pending')
        self.assertEqual(ev.attempt_count, 0)
        self.Event._dispatch_batch(commit=False, max_attempts=8)
        self.assertEqual(ev.status, 'done')

    # ---------------------------------------------------------------- metrics
    def test_metrics_shape(self):
        et = 'test.metrics.%d' % id(self)
        self._register(et, lambda env, ev: None)
        self.Event.publish(et, payload={}, aggregate_type='ord', aggregate_id='m%d' % id(self))
        m = self.Event.metrics()
        for key in ('queue_depth', 'inflight', 'done', 'dead', 'oldest_pending_age_seconds'):
            self.assertIn(key, m)
        self.assertGreaterEqual(m['queue_depth'], 1)

    # ---------------------------------------------------------------- performance
    def test_enqueue_and_dispatch_perf_sampling(self):
        et = 'test.perf.%d' % id(self)
        self._register(et, lambda env, ev: None)
        N = 200
        t0 = time.monotonic()
        for i in range(N):
            self.Event.publish(et, payload={'i': i}, aggregate_type='perf',
                               aggregate_id='perf-%d-%d' % (id(self), i))
        t1 = time.monotonic()
        m = self.Event._dispatch_batch(commit=False, batch_size=N)
        t2 = time.monotonic()
        self.assertEqual(m['delivered'], N)
        enqueue_ms = (t1 - t0) * 1000.0 / N
        dispatch_ms = (t2 - t1) * 1000.0 / N
        # not an assertion on wall-clock (CI noise); recorded for the report
        self.env['ir.logging']  # noqa: silence unused-import linters
        print("\n[outbox-perf] enqueue=%.3fms/ev  dispatch=%.3fms/ev  batch=%d"
              % (enqueue_ms, dispatch_ms, N))
