"""Runtime proof of the atomic rate limiter (P6.2 Phase 9). Tagged mezze_runtime.

Proves fixed-window limiting, atomicity under real concurrent independent
connections (no double-allowance), and a stable 429 + Retry-After on a real
sensitive HTTP endpoint.
"""
import threading
import uuid

from odoo import SUPERUSER_ID, api
from odoo.sql_db import db_connect
from odoo.tests import common, tagged

BASE = '/mezze/api/v1'


@tagged('post_install', '-at_install', 'mezze_runtime')
class TestRateLimit(common.TransactionCase):

    def test_fixed_window_limit(self):
        RL = self.env['mezze.rate.limit']
        key = 'test:%s' % uuid.uuid4().hex
        results = [RL.hit(key, 5, 60)[0] for _ in range(7)]
        self.assertEqual(results, [True, True, True, True, True, False, False])
        # denied hit reports a positive Retry-After within the window
        self.assertGreater(RL.hit(key, 5, 60)[1], 0)

    def test_risk_specific_failure_policy(self):
        from odoo.addons.mezze_bridge.domain import rate_policy as rp
        RL = self.env['mezze.rate.limit']
        import time as _t
        window = int(_t.time()) - (int(_t.time()) % 60)
        # FAIL_CLOSED -> deny on limiter unavailability
        allowed, _, count = RL._on_unavailable('k1', 10, window, 60, int(_t.time()), rp.FAIL_CLOSED)
        self.assertFalse(allowed)
        self.assertEqual(count, -1)   # -1 signals 'limiter unavailable'
        # FAIL_OPEN -> allow
        self.assertTrue(RL._on_unavailable('k2', 10, window, 60, int(_t.time()), rp.FAIL_OPEN)[0])
        # DEGRADED -> conservative process-local ceiling (limit//2)
        k = 'deg:%s' % uuid.uuid4().hex
        deg = [RL._on_unavailable(k, 10, window, 60, int(_t.time()), rp.DEGRADED)[0] for _ in range(8)]
        self.assertEqual(sum(1 for d in deg if d), 5)   # ceil = 10//2
        # high-risk operations are classified FAIL_CLOSED, never open
        for op in ('orders/refund', 'orders/void', 'drawer/open', 'gl/export.csv', 'breakglass'):
            self.assertEqual(rp.failure_mode(op), rp.FAIL_CLOSED)
        # unknown op defaults to FAIL_CLOSED (safe)
        self.assertEqual(rp.failure_mode('some/new/op'), rp.FAIL_CLOSED)

    def test_atomic_under_real_concurrency(self):
        import time
        key = 'race:%s' % uuid.uuid4().hex
        limit = 10
        allowed = []
        lock = threading.Lock()
        dbname = self.env.cr.dbname
        window = int(time.time()) - (int(time.time()) % 60)
        sql = ("INSERT INTO mezze_rate_limit (key, window_start, count, "
               "create_uid, create_date, write_uid, write_date) "
               "VALUES (%s, %s, 1, 1, now(), 1, now()) "
               "ON CONFLICT (key, window_start) "
               "DO UPDATE SET count = mezze_rate_limit.count + 1 RETURNING count")

        import psycopg2

        def worker():
            # ONE real independent connection per thread (the same atomic upsert the
            # model uses) — proves cross-connection atomicity. Retry serialization
            # failures (REPEATABLE READ) so every thread records exactly one result.
            for _try in range(8):
                try:
                    with db_connect(dbname).cursor() as cr:
                        cr.execute(sql, (key, window))
                        count = cr.fetchone()[0]
                        cr.commit()
                    with lock:
                        allowed.append(count <= limit)
                    return
                except (psycopg2.errors.SerializationFailure, psycopg2.errors.DeadlockDetected):
                    continue
            with lock:
                allowed.append(None)   # exhausted -> counted, flagged

        ts = [threading.Thread(target=worker) for _ in range(25)]
        for t in ts:
            t.start()
        for t in ts:
            t.join(30)
        # exactly `limit` allowed across 25 racing independent connections
        self.assertEqual(sum(1 for a in allowed if a), limit)
        self.assertEqual(len(allowed), 25)


@tagged('post_install', '-at_install', 'mezze_runtime')
class TestRateLimitHttp(common.HttpCase):

    def setUp(self):
        super().setUp()
        ICP = self.env['ir.config_parameter'].sudo()
        self.shared = 'rl-shared'
        ICP.set_param('mezze_bridge.api_token', self.shared)
        ICP.set_param('mezze_bridge.api_security', 'enforce')
        ICP.set_param('mezze_bridge.env_profile', 'development')
        # clean the limiter for this principal/window (independent-commit rows persist)
        with db_connect(self.env.cr.dbname).cursor() as cr:
            cr.execute("DELETE FROM mezze_rate_limit WHERE key LIKE 'orders/comp%'")
            cr.commit()
        self.env.flush_all()

    def test_sensitive_endpoint_429_after_limit(self):
        import json
        # orders/comp is rate-limited to 10/60s per principal; admin has the cap.
        limited = 0
        allowed = 0
        for i in range(14):
            r = self.url_open(BASE + '/orders/comp',
                              data=json.dumps({'token': self.shared, 'order_uuid': 'rl-%d' % i}),
                              headers={'Content-Type': 'application/json'}, timeout=30)
            body = r.json() if r.status_code != 500 else {}
            if r.status_code == 429 or body.get('error') == 'rate_limited':
                limited += 1
                self.assertTrue(r.headers.get('Retry-After'))
            else:
                allowed += 1
        # exactly the 4 requests beyond the limit of 10 are throttled
        self.assertEqual(allowed, 10)
        self.assertEqual(limited, 4)
