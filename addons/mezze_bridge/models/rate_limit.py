"""Atomic multi-worker rate limiter (P6.2 Phase 9).

A fixed-window counter in PostgreSQL. ``hit`` is atomic across Odoo worker
PROCESSES via a single ``INSERT ... ON CONFLICT DO UPDATE ... RETURNING`` — the
row lock serialises concurrent increments so exactly ``limit`` requests are
allowed per window regardless of how many workers race. No Redis / external
dependency; reuses the existing PostgreSQL the deployment already runs.
"""
import threading
import time

import psycopg2

from odoo import api, fields, models
from odoo.sql_db import db_connect

from ..domain import rate_policy

# process-local emergency counter for DEGRADED_BOUNDED ops when the shared limiter
# is unavailable — best-effort, per-worker, conservative (never atomic across
# workers, but bounded so an outage can't become unlimited).
_LOCAL = {}
_LOCAL_LOCK = threading.Lock()


class MezzeRateLimit(models.Model):
    _name = 'mezze.rate.limit'
    _description = 'Mezze fixed-window rate limiter'

    key = fields.Char(required=True, index=True)
    window_start = fields.Integer(required=True, index=True)
    count = fields.Integer(default=0)

    _key_window_uniq = models.Constraint('unique(key, window_start)',
                                         "One counter per key+window.")

    @api.model
    def hit(self, key, limit, window_seconds, fail_mode=rate_policy.FAIL_CLOSED):
        """Atomically record one hit. Returns (allowed, retry_after_seconds, count).

        Runs on an INDEPENDENT connection that commits per hit, so: (a) it works on
        read-only endpoints (exports), (b) the count is NOT undone if the business
        transaction later rolls back, and (c) it is atomic across worker PROCESSES
        (the ON CONFLICT upsert takes the row lock). If the shared limiter is
        UNAVAILABLE (retries exhausted), the risk-specific ``fail_mode`` decides:
        FAIL_CLOSED -> deny (count=-1), DEGRADED -> conservative process-local
        ceiling, FAIL_OPEN -> allow. count=-1 signals 'limiter unavailable'."""
        now = int(time.time())
        window = now - (now % int(window_seconds))
        sql = ("INSERT INTO mezze_rate_limit (key, window_start, count, "
               "create_uid, create_date, write_uid, write_date) "
               "VALUES (%s, %s, 1, 1, now(), 1, now()) "
               "ON CONFLICT (key, window_start) "
               "DO UPDATE SET count = mezze_rate_limit.count + 1, write_date = now() "
               "RETURNING count")
        count = None
        for _try in range(6):   # retry Postgres serialization/deadlock (REPEATABLE READ)
            try:
                with db_connect(self.env.cr.dbname).cursor() as cr:
                    cr.execute(sql, (key, window))
                    count = cr.fetchone()[0]
                    cr.commit()
                break
            except (psycopg2.errors.SerializationFailure, psycopg2.errors.DeadlockDetected):
                continue
        if count is None:
            return self._on_unavailable(key, limit, window, window_seconds, now, fail_mode)
        allowed = count <= int(limit)
        retry_after = (window + int(window_seconds) - now) if not allowed else 0
        return (allowed, retry_after, count)

    def _on_unavailable(self, key, limit, window, window_seconds, now, fail_mode):
        retry_after = window + int(window_seconds) - now
        if fail_mode == rate_policy.FAIL_OPEN:
            return (True, 0, -1)
        if fail_mode == rate_policy.DEGRADED:
            # conservative per-worker ceiling: half the shared limit, floored at 1
            ceil = max(1, int(limit) // 2)
            with _LOCAL_LOCK:
                w, c = _LOCAL.get(key, (window, 0))
                if w != window:
                    w, c = window, 0
                c += 1
                _LOCAL[key] = (w, c)
            return (c <= ceil, retry_after, -1)
        return (False, retry_after, -1)   # FAIL_CLOSED -> deny

    @api.model
    def _cron_gc(self):
        """Delete counters older than a bounded retention (past all windows)."""
        keep = int(self.env['ir.config_parameter'].sudo().get_param(
            'mezze_bridge.rate_limit_retention', 3600) or 3600)
        cutoff = int(time.time()) - keep
        self.env.cr.execute("DELETE FROM mezze_rate_limit WHERE window_start < %s", (cutoff,))
        return self.env.cr.rowcount
