"""Transactional outbox — durable, ordered, idempotent event delivery.

Business code publishes by writing an event row INSIDE its own transaction
(``mezze.outbox.event.publish(...)``). If the transaction rolls back the event
vanishes; if it commits the event exists. A dispatcher then delivers events AFTER
commit, so no external side effect can run for an uncommitted business change and
no committed change can silently lose its event.

Ordering is strict per aggregate (an aggregate's next event is only claimable once
its predecessor is DONE); different aggregates proceed independently. Concurrency
is safe via ``FOR UPDATE SKIP LOCKED`` claiming + a visibility timeout that lets a
crashed worker's locked events be recovered.
"""

import json
import logging
import uuid
from datetime import timedelta

import psycopg2

from odoo import api, fields, models

from ..domain import outbox as policy

_logger = logging.getLogger(__name__)

# Concurrency errors that mean "retry the claim" rather than "fail". Odoo runs
# cursors at REPEATABLE READ, so a claim whose ordering NOT EXISTS reads a row
# another worker concurrently commits raises 40001; that is expected with
# multiple dispatcher workers and is handled by rolling back + retrying (the
# same class Odoo's request-level retrying() retries).
_PG_CONCURRENCY = (psycopg2.errors.SerializationFailure,
                   psycopg2.errors.DeadlockDetected,
                   psycopg2.errors.LockNotAvailable)

# event_type -> handler(env, event_record). A handler ACKs by returning; it asks
# for retry/dead-letter by raising (the exception type name is classified by
# domain.outbox.classify). Registered by consumers at import/registry time.
OUTBOX_CONSUMERS = {}


def register_consumer(event_type, handler):
    OUTBOX_CONSUMERS[event_type] = handler


class OutboxNoConsumer(Exception):
    """No handler registered for an event_type (a configuration failure)."""


class OutboxRetry(Exception):
    """A consumer may raise this to request an explicit retry."""


class MezzeOutboxEvent(models.Model):
    _name = 'mezze.outbox.event'
    _description = 'Mezze transactional outbox event'
    _order = 'id asc'   # id is the global monotonic ordering key

    event_id = fields.Char(required=True, index=True, copy=False,
                           default=lambda self: uuid.uuid4().hex)
    event_type = fields.Char(required=True, index=True)
    aggregate_type = fields.Char(index=True)
    aggregate_id = fields.Char(index=True)
    aggregate_version = fields.Integer()
    company_id = fields.Many2one('res.company', index=True)
    branch_id = fields.Many2one('pos.config', index=True)
    terminal = fields.Char()
    principal = fields.Char()
    correlation_id = fields.Char()
    created_at = fields.Datetime(default=fields.Datetime.now, index=True)
    visible_after = fields.Datetime(default=fields.Datetime.now, index=True)
    attempt_count = fields.Integer(default=0)
    status = fields.Selection(
        [(policy.PENDING, 'Pending'), (policy.INFLIGHT, 'In-flight'),
         (policy.DONE, 'Done'), (policy.FAILED, 'Failed'), (policy.DEAD, 'Dead-letter')],
        default=policy.PENDING, required=True, index=True)
    payload = fields.Text()
    payload_version = fields.Integer(default=1)
    idempotency_key = fields.Char(index=True, copy=False)
    last_error = fields.Char()
    next_retry = fields.Datetime(index=True)
    locked_until = fields.Datetime(index=True)
    worker_id = fields.Char()

    _event_id_uniq = models.Constraint('unique(event_id)', 'Duplicate outbox event_id.')
    _idem_uniq = models.Constraint('unique(idempotency_key)',
                                   'This event idempotency_key already exists.')

    # ------------------------------------------------------------------ publish
    @api.model
    def publish(self, event_type, payload=None, aggregate_type=None, aggregate_id=None,
                aggregate_version=None, idempotency_key=None, correlation_id=None,
                company_id=None, branch_id=None, terminal=None, principal=None,
                visible_after=None):
        """Append an event in the CURRENT transaction. Rolls back with the business
        change. ``idempotency_key`` defaults to the event_id (self-unique). A
        duplicate idempotency_key is swallowed (the event already exists) so a
        retried business op does not double-publish."""
        eid = uuid.uuid4().hex
        vals = {
            'event_id': eid, 'event_type': event_type,
            'aggregate_type': aggregate_type, 'aggregate_id': str(aggregate_id) if aggregate_id is not None else None,
            'aggregate_version': aggregate_version, 'company_id': company_id, 'branch_id': branch_id,
            'terminal': terminal, 'principal': principal, 'correlation_id': correlation_id,
            'payload': json.dumps(payload, default=str) if payload is not None else None,
            'idempotency_key': idempotency_key or eid,
            'visible_after': visible_after or fields.Datetime.now(),
        }
        try:
            with self.env.cr.savepoint():
                rec = self.sudo().create(vals)
            self._audit('outbox.event_created', rec)
            return rec
        except Exception:  # noqa: BLE001 — duplicate idempotency_key -> already published
            existing = self.sudo().search([('idempotency_key', '=', vals['idempotency_key'])], limit=1)
            return existing

    # ------------------------------------------------------------------ dispatch
    @api.model
    def _claim(self, worker_id, batch_size, visibility_seconds):
        """Atomically claim up to ``batch_size`` deliverable events (oldest per
        aggregate, respecting visibility/retry/lock and recovering stale locks),
        using FOR UPDATE SKIP LOCKED so no two workers claim the same row."""
        # Compare against a UTC-naive Python "now", NOT the DB now()/clock_timestamp():
        # Odoo stores every datetime as UTC-naive, but the DB session renders its
        # clock in the server timezone, so DB-clock comparisons would be off by the
        # UTC offset. A Python fields.Datetime.now() keeps visible_after / next_retry
        # / locked_until comparisons apples-to-apples in UTC. It also advances during
        # a long transaction (unlike now(), which is fixed at transaction start), so
        # an event published mid-transaction becomes claimable in that same txn.
        # Flush pending ORM writes so the raw claim SELECT sees the latest state
        # (e.g. a predecessor just marked done, a lock just set) — raw SQL bypasses
        # the ORM cache, and an unflushed write would make the claim read stale rows.
        self.env['mezze.outbox.event'].flush_model()
        now = fields.Datetime.now()
        self.env.cr.execute("""
            SELECT e.id FROM mezze_outbox_event e
            WHERE (e.status IN ('pending','failed')
                   OR (e.status='inflight' AND e.locked_until < %(now)s))
              AND e.visible_after <= %(now)s
              AND (e.next_retry IS NULL OR e.next_retry <= %(now)s)
              AND NOT EXISTS (
                    SELECT 1 FROM mezze_outbox_event p
                    WHERE p.aggregate_type IS NOT DISTINCT FROM e.aggregate_type
                      AND p.aggregate_id   IS NOT DISTINCT FROM e.aggregate_id
                      AND p.id < e.id AND p.status <> 'done')
            ORDER BY e.id
            LIMIT %(lim)s
            FOR UPDATE SKIP LOCKED
        """, {'now': now, 'lim': batch_size})
        ids = [r[0] for r in self.env.cr.fetchall()]
        if not ids:
            return self.browse()
        locked_until = fields.Datetime.now() + timedelta(seconds=visibility_seconds)
        self.env.cr.execute("""
            UPDATE mezze_outbox_event
            SET status='inflight', locked_until=%s, worker_id=%s, attempt_count=attempt_count+1
            WHERE id = ANY(%s)
        """, (locked_until, worker_id, ids))
        self.env.invalidate_all()
        return self.browse(ids)

    def _consume(self, event):
        handler = OUTBOX_CONSUMERS.get(event.event_type)
        if handler is None:
            raise OutboxNoConsumer(event.event_type)
        handler(self.env, event)

    @api.model
    def _dispatch_batch(self, worker_id='w', batch_size=50, max_attempts=5,
                        visibility_seconds=300, commit=False):
        """Claim + deliver one batch ATOMICALLY (single commit at the end).

        Claim and delivery share one transaction, so the row lock taken by the
        FOR UPDATE claim is held until the batch commits — no other worker can
        deliver the same event (duplicate-dispatch prevention), and a crash before
        commit rolls the whole batch back to PENDING (crash recovery; no stuck
        INFLIGHT, no half-delivered batch). On a Postgres concurrency error (40001
        etc., expected with multiple workers under Odoo's REPEATABLE READ) the whole
        batch is rolled back and retried with a fresh snapshot. Redelivery of an
        uncommitted attempt is therefore at-least-once; consumers must be idempotent
        on event_id. commit=False (tests) keeps everything in one caller transaction.
        """
        last = {'claimed': 0, 'delivered': 0, 'failed': 0, 'dead': 0}
        for _try in range(5):
            try:
                claimed = self._claim(worker_id, batch_size, visibility_seconds)
                delivered = failed = dead = 0
                for ev in claimed:
                    self._audit('outbox.dispatch_started', ev)
                    try:
                        with self.env.cr.savepoint():
                            self._consume(ev)
                        ev.write({'status': policy.DONE, 'locked_until': False,
                                  'last_error': False})
                        self._audit('outbox.dispatch_succeeded', ev)
                        delivered += 1
                    except _PG_CONCURRENCY:
                        raise  # 40001 poisons the txn -> outer rollback + retry
                    except Exception as exc:  # noqa: BLE001
                        fclass = policy.classify(type(exc).__name__)
                        nxt, backoff = policy.decide(fclass, ev.attempt_count, max_attempts)
                        vals = {'status': nxt, 'locked_until': False,
                                'last_error': ('%s:%s: %s' % (fclass, type(exc).__name__, exc))[:500]}
                        if backoff is not None:
                            vals['next_retry'] = fields.Datetime.now() + timedelta(seconds=backoff)
                        ev.write(vals)
                        if nxt == policy.DEAD:
                            dead += 1
                            self._audit('outbox.dead_letter', ev)
                        else:
                            failed += 1
                            self._audit('outbox.dispatch_failed', ev)
                if commit:
                    self.env.cr.commit()
                return {'claimed': len(claimed), 'delivered': delivered,
                        'failed': failed, 'dead': dead}
            except _PG_CONCURRENCY:
                self.env.cr.rollback()
                continue
        return last  # gave up this tick; the next tick retries with a fresh snapshot

    @api.model
    def _cron_dispatch(self):
        """Scheduled dispatcher tick (bounded work; durable claim)."""
        icp = self.env['ir.config_parameter'].sudo()
        batch = int(icp.get_param('mezze_bridge.outbox_batch', 100) or 100)
        maxa = int(icp.get_param('mezze_bridge.outbox_max_attempts', 8) or 8)
        vis = int(icp.get_param('mezze_bridge.outbox_visibility', 300) or 300)
        wid = 'cron-%s' % (self.env.cr.dbname or 'db')
        return self._dispatch_batch(worker_id=wid, batch_size=batch, max_attempts=maxa,
                                    visibility_seconds=vis, commit=True)

    # ------------------------------------------------------------------ replay
    def replay(self):
        """Manually re-queue dead/done events (operator action). Resets delivery
        metadata; keeps the immutable identity/payload."""
        for ev in self:
            ev.write({'status': policy.PENDING, 'attempt_count': 0, 'next_retry': False,
                      'locked_until': False, 'worker_id': False, 'last_error': False})
            self._audit('outbox.manual_replay', ev)
        return True

    # ------------------------------------------------------------------ metrics
    @api.model
    def metrics(self):
        self.env.cr.execute("SELECT status, count(*) FROM mezze_outbox_event GROUP BY status")
        by_status = dict(self.env.cr.fetchall())
        # UTC-naive param, not now(): created_at is stored UTC-naive (see _claim).
        self.env.cr.execute(
            "SELECT EXTRACT(EPOCH FROM %s::timestamp - min(created_at)) FROM mezze_outbox_event "
            "WHERE status IN ('pending','failed')", (fields.Datetime.now(),))
        oldest = self.env.cr.fetchone()[0]
        return {
            'queue_depth': (by_status.get(policy.PENDING, 0) + by_status.get(policy.FAILED, 0)),
            'inflight': by_status.get(policy.INFLIGHT, 0),
            'done': by_status.get(policy.DONE, 0),
            'dead': by_status.get(policy.DEAD, 0),
            'oldest_pending_age_seconds': float(oldest) if oldest is not None else 0.0,
            'by_status': by_status,
        }

    # ------------------------------------------------------------------ audit
    @api.model
    def _audit(self, event, ev):
        try:
            self.env['mezze.audit.log'].sudo().log(
                event, severity='info', res_model='mezze.outbox.event', res_id=ev.id,
                detail=json.dumps({'event_id': ev.event_id, 'event_type': ev.event_type,
                                   'aggregate': '%s:%s' % (ev.aggregate_type or '', ev.aggregate_id or ''),
                                   'status': ev.status, 'attempt': ev.attempt_count,
                                   'correlation_id': ev.correlation_id}, default=str))
        except Exception:  # noqa: BLE001 — audit must never break delivery
            _logger.exception("outbox audit failed: %s", event)
