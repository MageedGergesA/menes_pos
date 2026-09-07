# Part of the Mezze POS platform. See LICENSE (LGPL-3).
"""Mezze Bridge API controller.

Design contract
---------------
* The external Mezze frontend speaks ONLY this JSON HTTP API. It never touches
  Odoo ORM-RPC / JSON-RPC.
* Reads reuse the ``pos.load.mixin`` field lists via curated ``search_read``.
* Writes reuse ``pos.order.sync_from_ui`` so real ``stock`` moves and (on session
  close) ``account`` entries are produced by Odoo's own POS flow. We never
  reinvent order creation or the session close.
* Idempotency piggybacks on the native ``pos.order.uuid`` (``sync_from_ui``
  upserts by uuid); we add a ``mezze.sync.log`` audit row on top.

v19 notes (verified against odoo/odoo/http.py):
* ``type='json'`` is now a DEPRECATED ALIAS for ``type='jsonrpc'`` (JSON-RPC 2.0
  envelope in/out). The task wants a clean REST-JSON contract (bare body in,
  bare JSON out) reachable by plain ``curl``/``fetch`` -> that is the new
  ``type='json2'`` dispatcher. We use ``json2`` for the API routes and keep
  ``/health`` on ``type='http'``.
* CORS preflight ``Access-Control-Allow-Headers`` is HARD-CODED in the framework
  and does NOT include ``X-Mezze-Token``. A browser cross-origin call carrying
  that custom header is therefore blocked at preflight. So ``_authenticate``
  accepts the token from the ``X-Mezze-Token`` header (curl path) OR from a
  ``token`` field in the JSON body / query string (browser path).
"""
import base64
import datetime
import hashlib
import json
import logging
import os
import re
from urllib.parse import quote

import psycopg2

from odoo import SUPERUSER_ID, _, api, fields, http
from odoo.exceptions import UserError
from odoo.modules.registry import Registry
from odoo.sql_db import db_connect
from odoo.http import request
from markupsafe import escape

from odoo.tools import float_round

from . import approval
from ..domain import order_guard
from ..domain import refund as order_refund_rules
from ..domain import discount as discount_policy
from ..domain import reward as reward_rules
from ..domain import modifiers as mezze_mods
from ..domain import authz
from ..domain import station_routing, station_surface
from ..domain import webhook
from ..domain import signing_policy
from ..domain import rate_policy
from ..domain.preparation import empty_preparation_change

_logger = logging.getLogger(__name__)

# Lifecycle-guard mode (ir.config_parameter 'mezze_bridge.fsm_guard'):
#   'off'      – guard disabled.
#   'observe'  – default. Illegal operations are recorded to the audit log but
#                control flow is UNCHANGED (zero behaviour risk).
#   'enforce'  – illegal operations are rejected before any mutation.
FSM_GUARD_PARAM = 'mezze_bridge.fsm_guard'

API_PREFIX = '/mezze/api/v1'
TOKEN_PARAM = 'mezze_bridge.api_token'
USER_PARAM = 'mezze_bridge.api_user_id'

# Postgres concurrency errors Odoo's request-level retrying() re-runs on a fresh
# snapshot. Our broad handlers must let these propagate instead of swallowing
# them into a JSON error (which would also poison the aborted transaction).
_RETRYABLE_PG = (
    psycopg2.errors.SerializationFailure,
    psycopg2.errors.DeadlockDetected,
    psycopg2.errors.LockNotAvailable,
)


def _display_currency(config):
    """What a GUEST should see money labelled as.

    The Register renders the currency's ``symbol`` -- "LE" for Egypt -- while every
    customer surface sent ``name``, the ISO code, so one shop showed "LE" on the till
    and "EGP" on its own storefront, kiosk and table menu. Whichever a shop prefers,
    it must be the same on both sides of the counter, and the operator already chose
    it: ``symbol`` is the configured display, so a branch that sets it to "ج.م" gets
    that everywhere rather than only on the till.

    Deliberately NOT used for machine-facing payloads. A payment provider is entitled
    to ISO 4217 and would reject "LE", so checkout, the charge payloads and the
    outbound order events keep ``currency_id.name``.
    """
    currency = config.currency_id
    return currency.symbol or currency.name

def _cash_position(session):
    """What the drawer should hold, in one place.

    The float the shift opened with is part of it. Leave it out and a drawer
    holding exactly the right money reports a surplus of the float every single
    day — and on a branch with a variance ceiling, demands a manager every night,
    which is the fastest way to teach a shop that the variance check is noise.

    This lived twice: once in the close preview the cashier reads before counting,
    once in the close that judges the count. Two spellings of one rule, with
    nothing keeping them in step. They are the same function now so they cannot
    drift, and ``test_cash_expected`` pins the screen and the close to each other
    rather than to a number.

    Module-level on purpose: a ``_private`` method shared by two controller
    classes in one addon silently shadows, and this codebase has already lost an
    endpoint that way.
    """
    cash_start = session.cash_register_balance_start or 0.0
    cash_payments = sum(session.order_ids.mapped('payment_ids').filtered(
        lambda p: p.payment_method_id.is_cash_count).mapped('amount'))
    return cash_start, cash_payments, cash_start + cash_payments

def _reraise_if_retryable(exc):
    """Re-raise ``exc`` unchanged if it (or any error it wraps) is a Postgres
    concurrency failure, so ``service_model.retrying`` can re-run the request."""
    cur = exc
    seen = 0
    while cur is not None and seen < 8:
        if isinstance(cur, _RETRYABLE_PG):
            raise exc
        cur = cur.__cause__ or cur.__context__
        seen += 1


class MezzeBridgeController(http.Controller):

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _json(self, payload, status=200):
        """Return a bare JSON response with an explicit HTTP status."""
        return request.make_json_response(payload, status=status)

    # Controller-prefix table (longest first) for deriving an endpoint id from the
    # request path. The id matches the keys in domain.authz (the ONE registry).
    _ROUTE_PREFIXES = ('/mezze/api/v1/', '/mezze/sync/v1/', '/mezze/hardware/',
                       '/mezze/w1/', '/mezze/aggregator/', '/mezze/')

    def _endpoint_id(self, path=None):
        """Canonical endpoint id from the request path (e.g. '/mezze/api/v1/orders/pay'
        -> 'orders/pay'), matching domain.authz's registry keys."""
        path = path if path is not None else (request.httprequest.path or '')
        for pfx in self._ROUTE_PREFIXES:
            if path.startswith(pfx):
                return path[len(pfx):]
        return path.lstrip('/')

    def _authorize(self, endpoint=None, target_order=None):
        """THE single authorization entry for every protected route. Derives the
        endpoint id from the request path (unless given) and delegates entirely to
        the canonical ``_security_gate`` — there is no separate authentication or
        capability logic. Returns ``None`` to proceed, else a ready-to-return
        rejection. Kept as the drop-in replacement for the removed legacy
        ``_authenticate``/``_auth`` so every call site runs the one gate."""
        env = self._api_env()
        return self._security_gate(env, endpoint or self._endpoint_id(),
                                   target_order=target_order)

    def _correlation_id(self):
        """Best-effort request/correlation id for tracing a guard event to its
        request. Never raises; returns None outside a request context."""
        try:
            h = request.httprequest.headers
            return (h.get('X-Correlation-Id') or h.get('X-Request-Id')
                    or getattr(request, 'session', None) and request.session.sid or None)
        except Exception:  # noqa: BLE001
            return None

    # ==================================================================
    # P5 adoption — publish business events to the transactional outbox
    # ==================================================================
    # These publish INSIDE the request transaction (so an event exists only if
    # the business change commits) and arm a single post-commit dispatch so the
    # consumer runs immediately AFTER commit — the 1-minute cron is the durable
    # fallback. The outbox/dispatcher/retry/ordering engine itself is untouched.

    def _arm_outbox_dispatch(self, env):
        """Schedule ONE post-commit outbox dispatch for this request. Events
        published in this transaction are delivered right after it commits, not up
        to a cron interval later. Idempotent per cursor; never raises into the
        business flow; a failed dispatch is retried by the cron."""
        cr = env.cr
        if cr.postcommit.data.get('mezze_outbox_armed'):
            return
        cr.postcommit.data['mezze_outbox_armed'] = True
        dbname = cr.dbname

        @cr.postcommit.add
        def _dispatch_after_commit():
            try:
                with Registry(dbname).cursor() as ncr:
                    nenv = api.Environment(ncr, SUPERUSER_ID, {})
                    nenv['mezze.outbox.event']._dispatch_batch(
                        worker_id='postcommit', batch_size=200, commit=True)
            except Exception:  # noqa: BLE001 — send-and-forget; cron retries
                _logger.exception("Mezze post-commit outbox dispatch failed (cron will retry)")

    def _publish_event(self, env, event_type, payload, aggregate_type='pos.order',
                       order=None, aggregate_id=None, idempotency_key=None,
                       company_id=None, branch_id=None, terminal=None, principal=None):
        """Publish one event in the current transaction + arm post-commit dispatch.
        Never raises into the business flow (a publish failure must not roll back a
        committed sale — the audit/cron catch it)."""
        try:
            agg = aggregate_id if aggregate_id is not None else (str(order.id) if order else None)
            env['mezze.outbox.event'].publish(
                event_type, payload=payload,
                aggregate_type=aggregate_type, aggregate_id=agg,
                idempotency_key=idempotency_key,
                correlation_id=self._correlation_id(),
                company_id=company_id or (order.company_id.id if order else None),
                branch_id=branch_id or (order.config_id.id if order and order.config_id else None),
                terminal=terminal, principal=principal,
            )
            self._arm_outbox_dispatch(env)
        except Exception:  # noqa: BLE001
            _logger.exception("Mezze publish(%s) failed", event_type)

    def _publish_webhook(self, env, channel, order, topic, business_payload):
        """Publish an outbound integration webhook (Category A) to the outbox. The
        aggregate is per integration+order so accepted->cancelled stay ordered while
        different orders/integrations dispatch concurrently. Credentials/URL are NOT
        in the payload — the consumer resolves them server-side from the channel."""
        op_uuid = order.uuid or str(order.id)
        self._publish_event(
            env, 'integration.webhook.deliver.v1',
            {'integration_id': channel.id, 'topic': topic, 'aggregate_type': 'pos.order',
             'aggregate_id': str(order.id), 'payload_version': 1, 'payload': business_payload,
             'delivery_policy': 'default'},
            aggregate_type='integration.webhook',
            aggregate_id='wh:%s:%s' % (channel.id, order.id),
            idempotency_key=webhook.webhook_key(channel.id, topic, op_uuid),
            company_id=channel.config_id.company_id.id, branch_id=channel.config_id.id)

    def _publish_receipt_print(self, env, order, printer, purpose='receipt', copy_seq=1, drawer=False):
        """Publish a receipt print job (Category A, config-gated). Aggregate is the
        PRINTER, so jobs to one printer serialise while different printers run
        concurrently. No document content is stored — the consumer re-renders from
        the authoritative order at delivery time."""
        if not printer:
            return
        self._publish_event(
            env, 'hardware.print.requested.v1',
            {'doc_type': purpose, 'order_id': order.id, 'printer_config_id': printer.id,
             'company_id': order.company_id.id, 'branch_id': order.config_id.id,
             'copy': copy_seq, 'template_version': 1, 'purpose': purpose, 'drawer': bool(drawer)},
            aggregate_type='hardware.printer', aggregate_id='printer:%s' % printer.id,
            idempotency_key=webhook.print_key(printer.id, order.id, purpose, copy_seq),
            company_id=order.company_id.id, branch_id=order.config_id.id,
            terminal=str(order.config_id.id))

    def _mark_edits_against_fired(self, env, order):
        """Stamp core's edit flags by comparing the cart against what was FIRED.

        ``pos.order.is_edited`` and ``has_deleted_line`` are core fields that drive
        Odoo's own "this order changed after it was sent" reporting and the order
        printer's change slips. Mezze already knew the answer — ``mezze_fired`` is a
        cumulative snapshot of what the kitchen has been told — and never wrote it
        down, so every Mezze order looked pristine to core no matter how many times a
        guest changed their mind after firing.

        The comparison is per PRODUCT, because that is the granularity the fired
        snapshot has. A quantity that went UP is not an edit: more food is a new
        fire, which the kitchen already hears about as its own ticket. What counts is
        a quantity that went DOWN, or a fired product no longer on the order at all —
        those are the ones nobody downstream would otherwise notice.
        """
        if 'is_edited' not in env['pos.order.line']._fields:
            return
        try:
            fired = {int(k): float(v)
                     for k, v in json.loads(order.mezze_fired or '{}').items()}
        except (TypeError, ValueError):
            return
        if not fired:
            return
        current = {}
        for l in order.lines:
            if l.qty > 0:
                current[l.product_id.id] = current.get(l.product_id.id, 0.0) + l.qty
        deleted = False
        for pid, was in fired.items():
            now = current.get(pid, 0.0)
            if now + 1e-6 < was:
                if now <= 1e-6:
                    deleted = True
                else:
                    lines = order.lines.filtered(lambda l: l.product_id.id == pid)
                    lines[:1].sudo().write({'is_edited': True})
        if deleted and 'has_deleted_line' in order._fields:
            order.sudo().write({'has_deleted_line': True})

    def _apply_ship_later(self, env, order, config, shipping_date):
        """Honour the branch's Ship Later switch.

        ``pos.config.ship_later`` was read into the boot payload and then ignored, so
        a till could show the option and nothing would come of it. A shipping date is
        a promise to a customer about stock, so it is REFUSED rather than silently
        dropped when the branch has not enabled it — a date that quietly does nothing
        is worse than a date the cashier is told they cannot set.
        """
        if shipping_date in (None, '', False):
            return None
        if not getattr(config, 'ship_later', False):
            return {'ok': False, 'error': 'ship_later_disabled',
                    'message': 'This branch does not deliver later.'}
        if 'shipping_date' not in order._fields:
            return {'ok': False, 'error': 'unsupported'}
        try:
            when = fields.Date.to_date(shipping_date)
        except (TypeError, ValueError):
            return {'ok': False, 'error': 'bad_shipping_date'}
        if not when:
            return {'ok': False, 'error': 'bad_shipping_date'}
        if when < fields.Date.context_today(order):
            # A delivery promised for yesterday is a promise nobody can keep.
            return {'ok': False, 'error': 'shipping_date_in_the_past',
                    'date': str(when)}
        order.sudo().write({'shipping_date': when})
        return None

    def _publish_fire_hardware(self, env, order, tickets):
        """Config-gated: on a fire, queue ONE kitchen print per station.

        A branch that prints instead of screens had no automatic path at all — the
        endpoint existed and somebody had to press it, which on a busy pass means
        the ticket that gets forgotten is the one the kitchen never knew about.

        Off by default, like the receipt and drawer gates beside it: turning a
        printer on for every fire is a decision a branch makes once it has a printer
        at the pass, not something a version bump should start doing to it.

        One event per STATION, keyed on the station, so the pizza printer and the
        barista printer serialise independently and a re-delivered event cannot
        print the same ticket twice.
        """
        icp = env['ir.config_parameter'].sudo()
        if str(icp.get_param('mezze_bridge.hw_auto_kitchen', '')).strip().lower() \
                not in ('1', 'true', 'yes', 'on'):
            return
        seen = set()
        for t in (tickets or []):
            station = (getattr(t, 'station', '') or '').strip()
            if not station or station in seen:
                continue
            seen.add(station)
            printer = self._kitchen_printer(env, order.config_id, station)
            if not printer:
                continue
            self._publish_event(
                env, 'hardware.print.requested.v1',
                {'doc_type': 'kitchen', 'station': station, 'order_id': order.id,
                 'printer_config_id': printer.id,
                 'company_id': order.company_id.id, 'branch_id': order.config_id.id,
                 'copy': 1, 'template_version': 1, 'purpose': 'kitchen'},
                aggregate_type='hardware.printer',
                aggregate_id='printer:%s' % printer.id,
                idempotency_key=webhook.print_key(
                    printer.id, order.id, 'kitchen:%s' % station, 1),
                company_id=order.company_id.id, branch_id=order.config_id.id,
                terminal=str(order.config_id.id))

    def _kitchen_printer(self, env, config, station):
        """The kitchen printer serving one station, or the branch's catch-all."""
        P = env['mezze.printer'].sudo()
        dom = [('config_id', '=', config.id), ('printer_type', '=', 'kitchen'),
               ('active', '=', True)]
        printers = P.search(dom)
        exact = printers.filtered(lambda p: (p.station or '').strip().lower()
                                  == (station or '').strip().lower())
        return exact[:1] or printers.filtered(lambda p: not p.station)[:1]

    def _publish_pay_hardware(self, env, order, kw):
        """Config-gated: on a committed payment, queue the receipt print and/or the
        cash-drawer kick through the outbox. Default OFF — the POS keeps using the
        synchronous /print + /drawer endpoints until a branch opts in. When receipt
        auto-print is on, the drawer kick rides inside the receipt (no double open);
        a standalone drawer event is used only when the drawer is auto but the
        receipt is not."""
        icp = env['ir.config_parameter'].sudo()

        def _on(key):
            return str(icp.get_param(key, '')).strip().lower() in ('1', 'true', 'yes', 'on')

        auto_receipt, auto_drawer = _on('mezze_bridge.hw_auto_receipt'), _on('mezze_bridge.hw_auto_drawer')
        if not (auto_receipt or auto_drawer):
            return
        printer = env['mezze.printer'].search(
            [('config_id', '=', order.config_id.id), ('printer_type', '=', 'receipt'),
             ('active', '=', True)], limit=1)
        if not printer:
            return
        is_cash = any(p.payment_method_id.is_cash_count for p in order.payment_ids)
        drawer_needed = bool(auto_drawer and printer.open_drawer and is_cash)
        principal = str(kw.get('cashier_id') or '') or None
        if auto_receipt:
            self._publish_receipt_print(env, order, printer, purpose='receipt', drawer=drawer_needed)
            if drawer_needed:
                # the drawer is kicked by the receipt itself; record the authorised
                # drawer intent as a standalone command only when there is no receipt.
                pass
        elif drawer_needed:
            self._publish_drawer_open(env, order, printer, reason='cash_payment', principal=principal)

    def _publish_drawer_open(self, env, order, printer, reason='cash_payment', principal=None):
        """Publish a drawer-open (Category A, config-gated). Aggregate is the
        TERMINAL. The consumer expires stale commands so a delayed replay cannot
        pop a drawer."""
        if not printer:
            return
        term = str(order.config_id.id)
        self._publish_event(
            env, 'hardware.drawer.open.requested.v1',
            {'operation_id': order.uuid, 'printer_config_id': printer.id,
             'company_id': order.company_id.id, 'branch_id': order.config_id.id,
             'reason': reason, 'source_ref': str(order.id)},
            aggregate_type='hardware.terminal', aggregate_id='terminal:%s' % term,
            idempotency_key=webhook.drawer_key(term, order.uuid or order.id),
            company_id=order.company_id.id, branch_id=order.config_id.id,
            terminal=term, principal=principal)

    def _publish_kds(self, env, tickets, order, natural_key=None):
        """Publish a KDS/waiter broadcast to the outbox instead of pushing the bus
        inline. The dispatcher's ``mezze.bus.broadcast`` consumer performs the
        actual push after commit."""
        if not tickets:
            return
        sends = tickets._bus_sends()
        if not sends:
            return
        self._publish_event(
            env, 'mezze.bus.broadcast', {'sends': sends}, order=order,
            idempotency_key=('kds:%s' % natural_key) if natural_key else None)

    def _publish_order_paid(self, env, order):
        """order.paid.v1 — published only after payment invariants pass, in the
        same transaction. Idempotent on the order uuid (a duplicate pay of the same
        order maps to one logical event)."""
        self._publish_event(
            env, 'order.paid.v1',
            {'order_id': order.id, 'uuid': order.uuid, 'pos_reference': order.pos_reference,
             'amount_total': order.amount_total, 'amount_paid': order.amount_paid,
             'currency': order.currency_id.name, 'company_id': order.company_id.id,
             'config_id': order.config_id.id, 'partner_id': order.partner_id.id or None},
            order=order, idempotency_key='order.paid:%s' % order.uuid)

    def _publish_order_refunded(self, env, refund_order, refund_uuid, orig):
        """order.refunded.v1 — published only after the refund succeeds, in the
        same transaction. Reuses the refund uuid as identity; aggregated on the
        original order so it orders after that order's paid event."""
        self._publish_event(
            env, 'order.refunded.v1',
            {'refund_order_id': refund_order.id, 'refund_uuid': refund_uuid,
             'original_order_id': orig.id if orig else None,
             'amount_total': refund_order.amount_total},
            aggregate_id=str(orig.id if orig else refund_order.id),
            idempotency_key='order.refunded:%s' % refund_uuid,
            company_id=refund_order.company_id.id,
            branch_id=refund_order.config_id.id if refund_order.config_id else None)

    # ==================================================================
    # P4 — canonical authentication / authorization / request-integrity
    # ==================================================================
    def _resolve_principal(self, env):
        """Resolve ONE canonical principal from the request credentials.

        Priority: a valid per-terminal token (``mezze.terminal.token``) ->
        principal is that terminal (company/branch from it); else the shared admin
        token -> principal 'admin'. Returns a dict with ``ok``/``reason`` and, on
        success, terminal/cashier/company/branch/permissions/secret. Never trusts
        client-supplied company/branch ids — they come from the resolved records.
        """
        req = request.httprequest
        token = req.headers.get('X-Mezze-Token') or request.params.get('token')
        term_id = req.headers.get('X-Mezze-Terminal') or request.params.get('terminal_id')
        cashier_id = req.headers.get('X-Mezze-Cashier') or request.params.get('cashier_id')
        if not token:
            return {'ok': False, 'reason': authz.AUTHENTICATION_REQUIRED}

        provided_kid = req.headers.get('X-Mezze-Key-Id')
        Term = env['mezze.terminal'].sudo()
        # Look up the terminal by the NON-REVERSIBLE fingerprint of the presented
        # token (no plaintext token is stored). active_test=False so a REVOKED
        # terminal is still resolved (reported terminal_revoked). Fall back to a
        # legacy plaintext match for un-migrated rows / dev without a master key.
        fp = env['mezze.secret.store'].token_hash(token) if token else None
        terminal = Term
        # WS-0 — a Mezze Station presents a SHORT-LIVED session token minted by
        # /mezze/station/v1/auth after signing a server nonce with its device key.
        # It resolves to the station's own terminal principal, so a station gets the
        # same least-privilege capabilities as any device and no new authorization
        # path exists. An expired/revoked session, or a revoked device, resolves to
        # nothing and falls through to the normal failure.
        if token:
            _sess = env['mezze.station.session'].sudo().resolve(token)
            if _sess:
                terminal = _sess.terminal_id.sudo().with_context(active_test=False)
        if token and not terminal and fp:
            terminal = Term.with_context(active_test=False).search(
                ['|', ('token_fingerprint', '=', fp), ('prev_token_fingerprint', '=', fp)], limit=1)
        if token and not terminal:   # legacy plaintext fallback
            terminal = Term.with_context(active_test=False).search(
                ['|', ('token', '=', token), ('prev_token', '=', token)], limit=1)
        shared = env['ir.config_parameter'].sudo().get_param(TOKEN_PARAM)
        key_reason = None
        principal_type = None
        emergency_caps = None       # set only for an emergency-activation principal
        emergency_company = None
        if terminal:
            if not terminal.active:
                return {'ok': False, 'reason': authz.TERMINAL_REVOKED, 'terminal_id': terminal.identifier}
            principal = 'terminal:%s' % terminal.identifier
            principal_type = terminal.role
            branch = terminal.branch_id
            # the bearer token IS the HMAC signing key: the secret is the PRESENTED
            # token (never a stored plaintext). Key id validity + rotation grace are
            # checked separately.
            secret = token
            _ok, key_reason = self._resolve_signing_key(env, terminal, provided_kid)
        elif shared and token == shared:
            icp = env['ir.config_parameter'].sudo()
            # the shared admin token can be DISABLED (fails closed) as terminals
            # migrate to per-terminal credentials.
            if str(icp.get_param('mezze_bridge.shared_token_disabled', '')).strip().lower() in ('1', 'true', 'yes'):
                return {'ok': False, 'reason': authz.AUTHENTICATION_FAILED}
            # P6.2/P6.5 — normal shared-admin is DISABLED in production. Access is
            # only via a live EMERGENCY ACTIVATION (scoped, capability-narrowed,
            # ≤1h, signed, audited); otherwise it fails closed.
            profile = (icp.get_param('mezze_bridge.env_profile') or 'development').strip().lower()
            emergency = env['mezze.emergency.access'].current()
            if profile == 'production' and not emergency:
                return {'ok': False, 'reason': authz.AUTHENTICATION_FAILED}
            terminal = Term
            secret = shared
            if emergency:
                # emergency principal: SCOPED (not scope-bypassing) to the activation's
                # company/branch, with only the granted capabilities.
                principal = 'emergency:%s' % emergency.id
                principal_type = 'admin'      # machine principal -> mandatory signing
                branch = emergency.branch_id or env['pos.config'].sudo()
                emergency_company = emergency.company_id.id or (
                    branch.company_id.id if branch else None)
                emergency_caps = emergency.caps()
                try:
                    env['mezze.audit.log'].sudo().log(
                        'security.emergency_use', severity='warning',
                        detail='{"activation": %s, "branch": %s}'
                               % (emergency.id, emergency.branch_id.id or 'null'))
                except Exception:  # noqa: BLE001
                    pass
            else:
                principal = 'admin:shared'
                principal_type = 'admin'
                branch = icp.get_param('mezze_bridge.default_branch_id')
                branch = env['pos.config'].sudo().browse(int(branch)) if (branch and str(branch).isdigit()) else env['pos.config'].sudo()
                try:
                    env['mezze.audit.log'].sudo().log('api.legacy_shared_token', severity='info',
                                                      detail=json.dumps({'principal': 'admin:shared'}))
                except Exception:  # noqa: BLE001
                    pass
        else:
            return {'ok': False, 'reason': authz.AUTHENTICATION_FAILED}

        # optional explicit terminal id must match the authenticated terminal
        if term_id and terminal and terminal.identifier != term_id:
            return {'ok': False, 'reason': authz.AUTHENTICATION_FAILED}

        cashier = env['mezze.cashier'].sudo()
        if cashier_id and str(cashier_id).isdigit():
            c = cashier.browse(int(cashier_id))
            if c.exists():
                if not c.active:
                    return {'ok': False, 'reason': authz.AUTHENTICATION_FAILED, 'cashier_id': c.id}
                cashier = c
        # permissions (least privilege): a cashier narrows to that person's role; a
        # bare terminal principal gets ONLY its role's capabilities (POS caps — never
        # admin); the deprecated shared-admin keeps all caps for back-compat.
        if cashier:
            perms = authz.capabilities_for(cashier.role)
        elif emergency_caps is not None:
            perms = emergency_caps                          # narrow incident capabilities
        elif principal == 'admin:shared':
            perms = authz.ALL_CAPABILITIES
        else:
            perms = authz.capabilities_for(principal_type)   # terminal / integration / backoffice

        company = (branch.company_id.id if branch else None) or emergency_company or env.company.id
        return {
            'ok': True, 'principal': principal, 'principal_type': principal_type,
            # only the plain shared-admin bypasses scope; an emergency principal is
            # SCOPED to its activation's company/branch (is_admin False).
            'is_admin': principal == 'admin:shared',
            'terminal': terminal, 'cashier': cashier,
            'company_id': company,
            'branch_id': branch.id if branch else None,
            'permissions': perms, 'secret': secret, 'key_reason': key_reason,
        }

    def _resolve_signing_key(self, env, terminal, provided_kid):
        """Validate the presented key id against the terminal's active/previous key
        + rotation grace. The signing SECRET is the presented bearer token (no
        plaintext stored); this only decides key-id validity. Returns
        (ok_bool, key_reason_or_None):
          * no kid, or kid == active kid  -> (True, None)
          * kid == previous kid, in grace -> (True, None)
          * kid == previous kid, expired  -> (False, revoked_key)
          * any other kid                 -> (False, unknown_key)
        """
        if not provided_kid or provided_kid == terminal.kid or not terminal.kid:
            return (True, None)
        if terminal.prev_kid and provided_kid == terminal.prev_kid:
            grace = int(env['ir.config_parameter'].sudo().get_param(
                'mezze_bridge.key_grace_seconds', 300) or 300)
            if terminal.key_rotated_at:
                age = (fields.Datetime.now() - terminal.key_rotated_at).total_seconds()
                if age <= grace:
                    return (True, None)
            return (False, authz.REVOKED_KEY)
        return (False, authz.UNKNOWN_KEY)

    def _verify_integrity(self, env, ctx, require_signature):
        """Verify request signing + replay when signature headers are present (or
        required). Returns None (ok) or a precise reason code. HMAC-SHA256 only over
        the deterministic canonical string (algo version + kid + principal + method
        + exact route + body digest + timestamp + nonce); constant-time compare;
        durable nonce claim AFTER a valid signature so a bad signature never burns a
        nonce. The signing key is resolved from the key id (rotation-aware)."""
        import hashlib
        import hmac
        import time as _time
        # Verify + claim the nonce ONCE per request: a route may run the gate more
        # than once (e.g. entry authorize + a later object-scope re-check), and the
        # nonce is single-use, so a second verification would self-collide as a
        # replay. Cache the successful result on the per-request environ.
        if request.httprequest.environ.get('mezze.sig_verified'):
            return None
        h = request.httprequest.headers
        ts = h.get('X-Mezze-Timestamp')
        nonce = h.get('X-Mezze-Nonce')
        sig = h.get('X-Mezze-Signature')
        kid = h.get('X-Mezze-Key-Id') or (ctx.get('terminal').kid if ctx.get('terminal') else None)
        # reject duplicate signed headers (header smuggling)
        for hdr in ('X-Mezze-Signature', 'X-Mezze-Nonce', 'X-Mezze-Timestamp'):
            if len(h.get_all(hdr) if hasattr(h, 'get_all') else h.getlist(hdr)) > 1:
                return authz.INVALID_SIGNATURE
        if not (ts or nonce or sig):
            return authz.SIGNATURE_REQUIRED_CODE if require_signature else None
        if not (ts and nonce and sig):
            return authz.SIGNATURE_REQUIRED_CODE if require_signature else authz.INVALID_SIGNATURE
        # the key id must resolve to a usable secret (rotation grace / revocation)
        if ctx.get('key_reason'):
            return ctx['key_reason']            # unknown_key / revoked_key
        if not ctx.get('secret'):
            return authz.INVALID_SIGNATURE
        try:
            skew = int(env['ir.config_parameter'].sudo().get_param(
                'mezze_bridge.clock_skew_seconds', 300) or 300)
            ts_i = float(ts)
        except (TypeError, ValueError):
            return authz.INVALID_SIGNATURE
        now = _time.time()
        if ts_i - now > skew:
            return authz.FUTURE_SIGNATURE
        if now - ts_i > skew:
            return authz.EXPIRED_SIGNATURE
        body = request.httprequest.get_data() or b''
        body_sha = hashlib.sha256(body).hexdigest()
        canonical = signing_policy.canonical_string(
            request.httprequest.method, request.httprequest.path, body_sha,
            ts, nonce, ctx['principal'], kid or '')
        expected = hmac.new(str(ctx['secret']).encode(), canonical.encode(),
                            hashlib.sha256).hexdigest()
        if not authz.signatures_equal(expected, sig):
            return authz.INVALID_SIGNATURE
        if not env['mezze.api.nonce'].claim(ctx['principal'], nonce):
            return authz.REPLAYED_REQUEST
        request.httprequest.environ['mezze.sig_verified'] = True
        return None

    def _branch_company_of(self, record):
        """Derive the AUTHORITATIVE (company_id, branch_id) from a target record,
        never from client input. Works for any record exposing config_id / branch_id
        / company_id (orders, sessions, printers, terminals, reservations, deliveries)."""
        company = branch = None
        f = record._fields
        # the record's OWN company_id is authoritative first (a refund order carries
        # its company); fall back to the branch's company only when absent.
        if 'company_id' in f and record.company_id:
            company = record.company_id.id
        if 'config_id' in f and record.config_id:
            branch = record.config_id.id
            if company is None:
                company = record.config_id.company_id.id
        elif 'branch_id' in f and record.branch_id:
            branch = record.branch_id.id
            if company is None and record.branch_id.company_id:
                company = record.branch_id.company_id.id
        return (company, branch)

    def _security_gate(self, env, endpoint, target_order=None, target=None, require_signature=False):
        """The ONE authz/integrity gate for an endpoint. Flag-gated by
        ``mezze_bridge.api_security`` (off|observe|enforce, default observe).

        observe: evaluate + audit denials, but never block (existing behaviour
        preserved). enforce: reject before the business logic. Returns None to
        proceed or a ready-to-return rejection JSON.
        """
        try:
            # Rollout complete: the canonical gate is ENFORCING by default. Shared-
            # token (admin) clients are unaffected (all capabilities + scope bypass);
            # per-terminal/cashier principals get least privilege. 'observe' (audit-
            # only) and 'off' remain available for staged diagnostics/rollback.
            mode = env['ir.config_parameter'].sudo().get_param('mezze_bridge.api_security') or 'enforce'
            if mode == 'off':
                return None
            ctx = self._resolve_principal(env)
            # AUTHENTICATION is the baseline every protected route already enforced
            # via the removed legacy auth — so an unauthenticated / revoked principal
            # is rejected in observe AND enforce (never silently let through). Only
            # AUTHORIZATION (capability / scope / signature) is staged by mode below.
            if not ctx['ok']:
                self._audit_security(env, endpoint, ctx['reason'], ctx)
                status = 401 if ctx['reason'] in (authz.AUTHENTICATION_REQUIRED,
                                                  authz.AUTHENTICATION_FAILED) else 403
                return self._json({'ok': False, 'error': ctx['reason']}, status=status)
            # --- AUTHORIZATION (capability -> scope -> signature) ---
            reason = None
            cap = authz.ENDPOINT_CAPABILITY.get(endpoint)
            elevated_by = None
            if cap and not (cap in ctx['permissions']):
                # MANAGER ELEVATION — a supervisor/manager standing at the till may
                # authorise ONE call the operator's own principal cannot make (comp,
                # void, refund …). This is how a restaurant actually works: the
                # cashier keeps the least-privilege principal, and the manager types
                # their PIN for the single exception rather than taking over the
                # terminal or having their own capabilities permanently granted to it.
                #
                # It is deliberately narrow:
                #   - the PIN is verified server-side against mezze.cashier here; the
                #     client never asserts a role, it only supplies a credential
                #   - the approver must genuinely HOLD the capability being borrowed,
                #     so this can never grant more than the approver has
                #   - it applies to this request only — nothing is stored on the
                #     terminal's principal
                #   - both identities are audited, so the trail names the operator
                #     AND the approver
                # Off unless the branch enables it, so the strict model stays default.
                elevated_by = self._elevated_approver(env, cap)
                if elevated_by is None:
                    reason = authz.PERMISSION_DENIED
            # OBJECT authorization: scope the AUTHORITATIVE target record (order for
            # money routes; any config/branch-bearing record via ``target``). The
            # shared-admin principal is not branch-scoped; terminal/cashier are.
            scope_rec = target if target is not None else target_order
            if not reason and scope_rec is not None and scope_rec.exists():
                tcompany, tbranch = self._branch_company_of(scope_rec)
                sv = authz.check_scope(ctx['company_id'], ctx['branch_id'],
                                       tcompany, tbranch,
                                       allow_cross_company=ctx.get('is_admin'),
                                       allow_cross_branch=ctx.get('is_admin'))
                if not sv.ok:
                    reason = sv.reason
            if not reason:
                # signing handling from the explicit policy state machine, resolved
                # by PRINCIPAL TYPE (machine principals enforce by default) and route
                # sensitivity. observe audits invalid/missing but never blocks and
                # never treats an invalid signature as valid; enforce blocks.
                getp = lambda k: env['ir.config_parameter'].sudo().get_param(k)  # noqa: E731
                ptype = ctx.get('principal_type') or 'admin'
                handling = signing_policy.effective(
                    signing_policy.mode_for(getp, ptype), endpoint, authz.SIGNATURE_REQUIRED)
                if require_signature:
                    handling = signing_policy.ENFORCE
                if handling != signing_policy.OFF:
                    sig_reason = self._verify_integrity(
                        env, ctx, handling == signing_policy.ENFORCE)
                    if sig_reason and handling == signing_policy.ENFORCE:
                        reason = sig_reason
                    elif sig_reason:
                        self._audit_security(env, endpoint, 'observe:%s' % sig_reason, ctx)
            if elevated_by is not None and not reason:
                self._audit_security(env, endpoint,
                                     'elevated:%s:by=%s' % (cap, elevated_by.code), ctx)
            if reason:
                self._audit_security(env, endpoint, reason, ctx)
                if mode == 'enforce':
                    status = 401 if reason in (authz.AUTHENTICATION_REQUIRED, authz.AUTHENTICATION_FAILED) else 403
                    return self._json({'ok': False, 'error': reason}, status=status)
                return None
            # P6.2 — narrow, atomic (multi-worker) rate limit for sensitive flows,
            # keyed by authoritative principal/terminal. Checked ONCE per request,
            # after authz, before business logic. Stable 429 (no existence leak).
            if endpoint in rate_policy.RATE_LIMITED_ENDPOINTS and not \
                    request.httprequest.environ.get('mezze.rate_checked'):
                request.httprequest.environ['mezze.rate_checked'] = True
                lim = rate_policy.limit_for(endpoint)
                if lim:
                    key = rate_policy.limit_key(
                        endpoint, ctx['principal'],
                        terminal=ctx['terminal'].identifier if ctx.get('terminal') else None,
                        company=ctx.get('company_id'))
                    fail_mode = rate_policy.failure_mode(endpoint)
                    allowed, retry_after, count = env['mezze.rate.limit'].hit(
                        key, lim[0], lim[1], fail_mode=fail_mode)
                    if not allowed:
                        unavailable = count == -1     # limiter backend was down
                        self._audit_security(
                            env, endpoint,
                            'rate_limiter_unavailable' if unavailable else 'rate_limited', ctx)
                        if mode == 'enforce':
                            err = 'rate_limiter_unavailable' if unavailable else 'rate_limited'
                            status = 503 if unavailable else 429
                            return request.make_json_response(
                                {'ok': False, 'error': err, 'retry_after': retry_after},
                                headers=[('Retry-After', str(retry_after))], status=status)
            return None
        except Exception:  # noqa: BLE001 — a security gate must never break the flow in observe
            _logger.exception("Mezze security gate failed (endpoint=%s)", endpoint)
            return None

    def _audit_security(self, env, endpoint, reason, ctx=None):
        """DURABLE, PII-safe audit of a denied/observed security decision.

        Written on an INDEPENDENT database cursor that commits by itself, so a
        denial persists even when the request runs in a READ-ONLY transaction (Odoo
        19 defaults ``auth='none'`` routes to readonly) and cannot corrupt the
        request transaction. A logging failure NEVER grants access — the gate has
        already decided; this only records it. Never logs tokens / secrets / full
        signatures / raw bodies / PAN / PII (only presence booleans + reason code).
        """
        principal = (ctx or {}).get('principal')
        detail = {
            'endpoint': endpoint, 'method': request.httprequest.method,
            'reason_code': reason, 'principal': principal,
            'principal_type': (ctx or {}).get('principal_type'),
            'required_capability': authz.ENDPOINT_CAPABILITY.get(endpoint),
            'company_id': (ctx or {}).get('company_id'),
            'branch_id': (ctx or {}).get('branch_id'),
            'terminal': (ctx.get('terminal').identifier if ctx and ctx.get('terminal') else None),
            'cashier_id': (ctx.get('cashier').id if ctx and ctx.get('cashier') else None),
            'signature_present': bool(request.httprequest.headers.get('X-Mezze-Signature')),
            'key_id_present': bool(request.httprequest.headers.get('X-Mezze-Key-Id')),
            'legacy_token': principal == 'admin:shared',
            'correlation_id': self._correlation_id(),
        }
        try:
            with db_connect(env.cr.dbname).cursor() as acr:
                acr.execute(
                    "INSERT INTO mezze_audit_log (event, severity, detail, "
                    "create_uid, create_date, write_uid, write_date) "
                    "VALUES ('api.security_denied','warning',%s,1,now(),1,now())",
                    (json.dumps(detail, default=str),))
                acr.commit()
        except Exception:  # noqa: BLE001 — durability best-effort; never blocks the decision
            _logger.warning("Mezze durable security audit failed (endpoint=%s reason=%s)",
                            endpoint, reason)

    def _fsm_guard(self, env, order, operation, endpoint=None):
        """Validate a lifecycle ``operation`` on ``order`` against the RFC-001 FSM.

        The ONE executable authority for "which operations are legal in which
        order state" (RFC-001 lifecycle; RFC-000 no-duplicate-rules). Endpoints
        call this instead of hand-coding ``if state != 'draft'``.

        Reads the authoritative state SERVER-SIDE (never trusts client input).
        Returns ``None`` when the operation may proceed; returns a ready-to-return
        rejection dict ONLY in 'enforce' mode on a forbidden operation. In the
        default 'observe' mode it records the attempt (rich, PII-safe telemetry)
        and returns ``None`` so control flow — and restaurant operations — are
        unchanged. Any error fails safe (returns ``None``; never blocks).
        """
        try:
            if not order or not order.exists():
                return None
            mode = (env['ir.config_parameter'].sudo().get_param(FSM_GUARD_PARAM)
                    or order_guard.MODE_OBSERVE)
            uuid = getattr(order, 'uuid', False) or None
            config = getattr(order, 'config_id', False)
            ctx = {
                'endpoint': endpoint,
                'order_id': order.id,
                'order_uuid': uuid,
                'branch_id': config.id if config else None,
                'company_id': config.company_id.id if config and config.company_id else None,
                'actor_uid': env.uid,
                'correlation_id': self._correlation_id(),
                'ts': fields.Datetime.to_string(fields.Datetime.now()),
            }
            res = order_guard.evaluate(order.state, operation, mode, ctx)
            if res.audit_detail:
                env['mezze.audit.log'].sudo().log(
                    'order.fsm_violation', severity='warning',
                    res_model='pos.order', res_id=order.id, res_uuid=uuid or False,
                    detail=json.dumps(res.audit_detail, default=str))
            if res.blocked:
                return {'ok': False, 'error': 'forbidden_transition',
                        'message': res.verdict.reason, 'state': order.state,
                        'operation': operation}
            return None
        except Exception:  # noqa: BLE001 — a guard must never break the money/kitchen flow
            _logger.exception("Mezze FSM guard failed (operation=%s)", operation)
            return None

    def _api_env(self):
        """Return an env bound to the configured API user.

        Runs as a real internal user (config param ``mezze_bridge.api_user_id``,
        else Mitchell Admin, else the first internal user). This user carries POS
        rights, so we avoid ``sudo`` superuser edge cases (e.g. ``open_ui``'s
        SUPERUSER guard) while still reusing core flows unchanged.
        """
        su = request.env(user=SUPERUSER_ID)
        uid_param = su['ir.config_parameter'].get_param(USER_PARAM)
        if uid_param and str(uid_param).isdigit():
            uid = int(uid_param)
        else:
            api_user = su.ref('base.user_admin', raise_if_not_found=False)
            if not api_user:
                api_user = su['res.users'].search(
                    [('share', '=', False), ('active', '=', True)], limit=1)
            uid = api_user.id
        return request.env(user=uid)

    def _resolve_config(self, env, config_id=None):
        """The branch an API caller is working in — decided by its TOKEN.

        This used to read a client-supplied ``config_id`` and otherwise take the
        first pos.config in the database. Both halves were wrong:

        * a station enrolled to the restaurant was handed the front counter's
          catalogue, payment methods and session, because "first config" is not
          an answer to "which till is this";
        * and the branch came from the request body, so a terminal scoped to one
          branch could simply ask for another's — the exact client-asserted scope
          that ``_mezze_principal_scope`` exists to refuse everywhere else.

        Now the token decides. A caller may still NAME its own branch (harmless,
        and convenient for the shared-admin principal, which is scope-bypassing by
        design and genuinely serves every branch), but naming somebody else's is
        ignored rather than obeyed.
        """
        Config = env['pos.config']
        requested = Config.browse(int(config_id)) if config_id else Config
        scope = self._mezze_principal_scope(env)
        if scope.get('ok') and not scope.get('is_admin') and scope.get('branch'):
            own = Config.browse(scope['branch'])
            if own.exists():
                if requested and requested.exists() and requested.id != own.id:
                    _logger.info(
                        "branch claim ignored: token is scoped to %s, request asked for %s",
                        own.id, requested.id)
                return own
        if requested and requested.exists():
            return requested
        return Config.search([], limit=1)

    def _ensure_open_session(self, env, config):
        """Return an open ``pos.session`` for ``config``, opening one if needed.

        Reuses core session lifecycle: ``pos.session.create`` -> auto
        ``action_pos_session_open`` -> ``set_opening_control`` -> state 'opened'.
        We intentionally do NOT call ``pos.config.open_ui`` because it raises for
        SUPERUSER and returns a client action rather than a record.
        """
        session = config.current_session_id
        if session and session.state in ('opened', 'opening_control'):
            if session.state == 'opening_control':
                session.set_opening_control(0, None)
            return session
        session = env['pos.session'].create({
            'config_id': config.id,
            'user_id': env.uid,
        })
        session.set_opening_control(0, None)
        return session

    def _audit(self, env, event, order=None, **extra):
        """Best-effort append to the immutable ``mezze.audit.log`` trail.

        Never raises into the caller's money flow — a failed audit write must not
        roll back a completed sale (it is logged server-side for follow-up). When
        an ``order`` is given, its model/id/uuid/branch/amount are attached
        automatically so every money event is attributable.
        """
        try:
            vals = dict(extra)
            if order is not None and order:
                vals.setdefault('res_model', 'pos.order')
                vals.setdefault('res_id', order.id)
                vals.setdefault('res_uuid', order.uuid or '')
                vals.setdefault('config_id', order.config_id.id or False)
                vals.setdefault('amount', order.amount_total)
            env['mezze.audit.log'].log(event, **vals)
        except Exception:  # noqa: BLE001
            _logger.exception("Mezze audit wiring failed for event %s", event)

    def _actor(self, env, kw):
        """Resolve the acting cashier/terminal from the request body for
        attribution. Only sets a value when the record actually exists, so a
        stale/bad id never drops the whole audit row (a missing FK would make the
        best-effort append silently fail). ``terminal_id`` may be the DB id or the
        terminal's string ``identifier``.
        """
        out = {}
        cid = kw.get('cashier_id')
        if cid and str(cid).isdigit():
            cashier = env['mezze.cashier'].browse(int(cid))
            if cashier.exists():
                out['cashier_id'] = cashier.id
        tid = kw.get('terminal_id')
        if tid:
            term = None
            if str(tid).isdigit():
                term = env['mezze.terminal'].browse(int(tid))
                term = term if term.exists() else None
            else:
                term = env['mezze.terminal'].search([('identifier', '=', tid)], limit=1)
            if term:
                out['terminal_id'] = term.id
        return out

    # -- terminal-scoped receipt reference -------------------------------------
    # Two OFFLINE terminals each running a local Odoo would otherwise mint the
    # same pos_reference sequence ("Order 0001"), colliding when they sync up.
    # We namespace the receipt number with THIS node's terminal identity so it
    # is globally unique; the sync apply-path preserves it. See docs/SYNC.md.
    def _node_terminal(self, env):
        """This node's own terminal identity (config param, set per install /
        bundled .exe). ``None`` on a plain single-node cloud → references keep
        Odoo's default sequence (opt-in, so existing behaviour is unchanged)."""
        return env['ir.config_parameter'].sudo().get_param('mezze_bridge.terminal_id') or None

    def _terminal_ref(self, config, ident, tail):
        """Globally-unique, human-readable receipt ref: ``M<config>-<term>-<tail>``."""
        return 'M%s-%s-%s' % (config.id, str(ident)[-8:], tail)

    def _stamp_ref(self, env, order, ident, tail):
        """Stamp a terminal-scoped pos_reference on a fresh order when this node
        has a terminal identity. No-op otherwise."""
        if ident and order:
            order.sudo().write({'pos_reference': self._terminal_ref(order.config_id, ident, tail)})

    def _tip_product(self, env, config):
        """The tip product — reuse Odoo's native POS tip product
        (``pos.config.tip_product_id`` / the ``TIPS`` product) so tips reconcile
        through the standard `pos.order.tip_amount`/`is_tipped` path. Created on
        first use if the config has none."""
        p = config.tip_product_id
        if p:
            return p
        Product = env['product.product'].sudo()
        p = Product.search([('default_code', '=', 'TIPS')], limit=1)
        if not p:
            p = Product.create({
                'name': 'Tips', 'default_code': 'TIPS', 'type': 'service',
                'available_in_pos': True, 'taxes_id': [(6, 0, [])], 'list_price': 0.0})
        config.sudo().tip_product_id = p.id
        return p

    # ------------------------------------------------------------------
    # Health (no auth) — connectivity probe
    # ------------------------------------------------------------------
    @http.route(f'{API_PREFIX}/health', type='http', auth='none',
                methods=['GET'], csrf=False, cors='*')
    def health(self, **kw):
        return request.make_json_response({
            'ok': True,
            'odoo': '19.0',
            'module': 'mezze_bridge',
        })

    # ------------------------------------------------------------------
    # Bootstrap — catalog + config + open session
    # ------------------------------------------------------------------
    @http.route(f'{API_PREFIX}/bootstrap', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*', readonly=False)
    def bootstrap(self, config_id=None, **kw):
        auth = self._authorize()
        if auth:
            return auth
        try:
            env = self._api_env()
            config = self._resolve_config(env, config_id)
            if not config:
                return self._json({
                    'ok': False,
                    'error': 'no_pos_config',
                    'message': "No pos.config found. Create a Point of Sale first.",
                }, status=404)
            env = env(context=dict(env.context, allowed_company_ids=[config.company_id.id], company_id=config.company_id.id))
            config = config.with_env(env)
            session = self._ensure_open_session(env, config)

            # Payment methods bound to this config. The mezze_* policy fields let the
            # cashier UI drive tender behaviour from CONFIGURATION (mode, device /
            # reference / duplicate policy, partial/mixed, manager approval) without
            # any hardcoded method identity. Implementation values (mezze_mode etc.)
            # are for behaviour only — the UI shows the configured `name`.
            payment_methods = config.payment_method_ids.read([
                'id', 'name', 'is_cash_count', 'mezze_mode', 'mezze_terminal_provider',
                'device_policy', 'reference_policy', 'reference_scope', 'duplicate_policy',
                'mezze_allow_partial', 'mezze_allow_mixed', 'mezze_manager_approval',
                'mezze_credit_policy'])

            # Price at the precision of the currency this BRANCH trades in. A till
            # on a foreign-currency journal (a duty-free or hotel POS) can run a
            # 3-decimal Gulf currency inside a 2-decimal company, and pinning the
            # rounding to 2 quietly drops a fils off every price on the menu.
            _dp = config.currency_id.decimal_places or 2

            # Taxes available in the config's company.
            taxes = env['account.tax'].search_read(
                [('type_tax_use', '=', 'sale'),
                 ('company_id', '=', config.company_id.id)],
                ['id', 'name', 'amount'])

            # POS categories.
            categories = self._menu_categories(env, config)

            # Products available in POS (curated projection of the pos.load.mixin
            # field set — we return only what the Mezze frontend needs).
            products = env['product.product'].search_read(
                self._menu_domain(env, config),
                ['id', 'display_name', 'list_price', 'barcode', 'default_code',
                 'taxes_id', 'pos_categ_ids', 'uom_id', 'type', 'to_weight'])
            blocked86 = self._eightysix_ids(env, config.id)
            catname = {c['id']: (c['name'] or '') for c in categories}
            # eligible halves = pizzas (a POS category named "pizza"), minus the
            # half-&-half base itself (default_code HALFHALF)
            half_options = []
            for p in products:
                # Normalise display_name -> name for the frontend.
                p['name'] = p.pop('display_name')
                prod = env['product.product'].browse(p['id'])
                p['modifiers'] = self._product_modifiers(env, prod)
                p['combos'] = self._product_combos(env, prod)
                p['is_combo'] = p['type'] == 'combo'
                p['available'] = p['id'] not in blocked86     # False => 86'd on this branch
                p['half_base'] = (p.get('default_code') == 'HALFHALF')
                p['has_image'] = bool(prod.image_256)          # POS grid thumbnail (served via /shop/image)
                # Sold by weight. The till has to know, because a weighed line's
                # quantity is a measurement and not a count — and Mezze rounded every
                # quantity to a whole number on the way back in, which silently turned
                # 0.4 kg into 0 and then into 1.
                p['to_weight'] = bool(p.get('to_weight'))
                p['uom_name'] = prod.uom_id.name or ''
                # Whether this product is TRACKED, so the till knows to ask for the
                # batch. Without it the server could record a lot and no surface
                # would ever collect one.
                p['tracking'] = getattr(prod, 'tracking', 'none') or 'none'
                # BOTH prices, computed HERE.
                #
                # The till can show prices with or without tax (core's Actions → Tax),
                # and the obvious implementation is to ship one price and let the
                # browser derive the other. That is the same mistake the storefront
                # made: multiple taxes, price-included flags and fiscal positions are
                # not arithmetic a browser should be doing, and it will be wrong on
                # exactly the branches that care. Odoo's own `compute_all` runs once
                # per product here and the toggle then only picks a field.
                taxes = prod.taxes_id.filtered(
                    lambda t: t.company_id == config.company_id) or prod.taxes_id
                if taxes:
                    computed = taxes.compute_all(
                        p['list_price'], currency=config.currency_id, quantity=1.0,
                        product=prod)
                    p['price_excl'] = round(computed['total_excluded'], _dp)
                    p['price_incl'] = round(computed['total_included'], _dp)
                else:
                    p['price_excl'] = p['price_incl'] = round(p['list_price'], _dp)
                is_pizza = any('pizza' in catname.get(cid, '').lower()
                               for cid in (p.get('pos_categ_ids') or []))
                if is_pizza and not p['half_base'] and p['available']:
                    half_options.append({'id': p['id'], 'name': p['name'],
                                         'price': p['list_price']})

            return {
                'ok': True,
                'session_id': session.id,
                'config': {
                    'id': config.id,
                    'name': config.name,
                    'currency_id': config.currency_id.id,
                    'currency': config.currency_id.name,
                    'company_id': config.company_id.id,
                    'pricelist_id': config.pricelist_id.id or False,
                    # Core switches Mezze shipped without reading. A till cannot
                    # honour a policy it was never told about.
                    'restrict_price_control': bool(
                        getattr(config, 'restrict_price_control', False)),
                    'manual_discount': bool(getattr(config, 'manual_discount', True)),
                    # Design v3 `tillBarred`. A staffing policy, not a capability:
                    # the rail shows these destinations LOCKED rather than hiding
                    # them, so a barred server can see the branch decided.
                    'servers_off_till': bool(
                        getattr(config, 'mezze_servers_off_till', False)),
                    # Whether this branch has a scale worth asking. Sent at boot
                    # rather than probed per line: a till that offers "Weigh" and
                    # then reports "no scale" has taught the cashier to distrust the
                    # button, and one extra round trip per weighed item on a busy
                    # counter is a round trip nobody has.
                    # Whether a customer display has ever been opened for this
                    # branch. Sent at boot so the till pushes its cart only where
                    # somebody is watching — a snapshot per keystroke to a screen
                    # that does not exist is pure noise on a busy counter.
                    'has_cfd': bool(env['mezze.terminal'].sudo().with_context(
                        active_test=False).search_count(
                        [('identifier', '=', 'cfd-%s' % config.id)])),
                    'has_scale': bool(env['mezze.scale'].sudo().search_count(
                        [('config_id', '=', config.id), ('active', '=', True),
                         ('host', '!=', False)])),
                    'iface_tax_included': getattr(config, 'iface_tax_included', 'subtotal'),
                    # Core's one-tap validation from the product screen. The branch
                    # chooses WHICH methods qualify; Mezze then narrows that to the
                    # ones that can actually complete in a single tap — a method that
                    # requires a device or a reference cannot, and offering a button
                    # that is always refused is worse than not offering it.
                    # v19 order types, with whatever pricing each carries. The till
                    # names the preset; the server turns that into a pricelist.
                    'use_presets': bool(getattr(config, 'use_presets', False)),
                    'presets': [
                        {'id': p.id, 'name': p.name,
                         'default': p.id == config.default_preset_id.id,
                         'identification': p.identification}
                        for p in (config.available_preset_ids or config.default_preset_id)
                    ] if getattr(config, 'use_presets', False) else [],
                    'use_fast_payment': bool(getattr(config, 'use_fast_payment', False)),
                    # Empty when the branch has the feature OFF. Shipping the list
                    # anyway and trusting every consumer to check the flag is how a
                    # disabled feature gets offered by the one caller that forgets.
                    'fast_payment_method_ids': [
                        pm.id for pm in getattr(config, 'fast_payment_method_ids',
                                                config.browse())
                        if pm.device_policy != 'required'
                        and pm.reference_policy != 'required'
                    ] if getattr(config, 'use_fast_payment', False) else [],
                    'basic_receipt': bool(getattr(config, 'basic_receipt', False)),
                    'ship_later': bool(getattr(config, 'ship_later', False)),
                },
                # The lists a cashier can switch BETWEEN. Mezze priced every order
                # against the branch list and offered no way to change it, so a
                # customer-specific agreement had nowhere to be applied at the till.
                'pricelists': [
                    {'id': pl.id, 'name': pl.name,
                     'is_default': pl.id == config.pricelist_id.id}
                    for pl in (config.available_pricelist_ids or config.pricelist_id)
                ],
                'fiscal_positions': [
                    {'id': fp.id, 'name': fp.name,
                     'is_default': fp.id == config.default_fiscal_position_id.id}
                    for fp in (config.fiscal_position_ids
                               or config.default_fiscal_position_id)
                ],
                # Odoo's predefined kitchen notes (pos.note). Typing "no onion" on
                # every ticket is how notes end up inconsistent enough to be useless
                # to a kitchen.
                'note_presets': [
                    {'id': n.id, 'name': n.name}
                    for n in (config.note_ids if 'note_ids' in config._fields
                              else env['pos.note'].browse())
                ],
                'payment_methods': payment_methods,
                'taxes': taxes,
                'categories': categories,
                'products': products,
                'quick_keys': self._quickkeys(env, config.id),
                'half_options': half_options,
                'gift_sale_product_id': self._giftcard_sale_product(env).id,
            }
        except Exception as exc:  # noqa: BLE001 - never leak a 500 traceback
            _logger.exception("Mezze bootstrap failed")
            return self._json({
                'ok': False,
                'error': 'bootstrap_failed',
                'message': str(exc),
            }, status=400)

    # ------------------------------------------------------------------
    # Order sync — idempotent, reuses pos.order.sync_from_ui
    # ------------------------------------------------------------------
    @http.route(f'{API_PREFIX}/orders/sync', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*', readonly=False)
    def order_sync(self, uuid=None, session_id=None, lines=None, payments=None,
                   expected_revision=None,
                   partner_id=None, amount_total=None, table_id=None,
                   discount=None, discount_product_id=None, tip=None,
                   gift_card_code=None, gift_card_amount=None, draft=False,
                   service_mode=None, shipping_date=None, **kw):
        auth = self._authorize()
        if auth:
            return auth

        payload_hash = hashlib.sha256(
            json.dumps({
                'uuid': uuid, 'session_id': session_id, 'lines': lines,
                'payments': payments, 'partner_id': partner_id,
            }, sort_keys=True, default=str).encode()
        ).hexdigest()

        if not uuid:
            return self._json({'ok': False, 'error': 'missing_uuid',
                               'message': "'uuid' is required."}, status=400)

        env = self._api_env()
        Log = env['mezze.sync.log'].sudo()
        log = Log.create({
            'name': 'Mezze %s' % uuid,
            'uuid': uuid,
            'status': 'received',
            'payload_hash': payload_hash,
        })

        try:
            # ---- Idempotency: native pos.order.uuid ----
            existing = env['pos.order'].search([('uuid', '=', uuid)], limit=1)
            if existing:
                # Another terminal may have moved this check since the client
                # last read it. Refuse rather than overwrite — the quantities
                # being replaced are somebody else's work, and the comment
                # below records what silent staleness already cost once.
                stale = self._assert_revision(existing, expected_revision)
                if stale:
                    return stale
            # A DRAFT is a working cart, not a submission, and it has to be allowed to
            # change. Short-circuiting every repeat of a uuid meant the second save of
            # a table's bill was silently ignored: the cashier added two waters, the
            # server kept the older lines, and the payment screen — which takes its
            # total from THIS response — offered 16.33 for an 18.60 order. The same
            # staleness made Split show a bill the cashier was not looking at.
            #
            # Odoo's own sync_from_ui is built for this ("update orders that are in
            # draft status") and calls _ensure_to_keep_last_preparation_change, so
            # what the kitchen has already been told survives the update. Falling
            # through to it is therefore reusing the native contract, not loosening
            # one: the idempotent return still guards everything that could be
            # double-charged.
            _updatable_draft = bool(
                existing
                and draft
                and existing.state == 'draft'
                and not existing.payment_ids
                # A split has already divided this bill. Re-syncing the till's cart
                # over the root would resurrect lines that moved to another check.
                and not existing.mezze_split_root_id
                and not existing.mezze_split_child_ids
            )
            if existing and not _updatable_draft:
                log.write({
                    'status': 'ok',
                    'pos_order_id': existing.id,
                    'session_id': existing.session_id.id,
                    'message': 'Idempotent hit: order already exists, not duplicated.',
                })
                return {
                    'ok': True,
                    'duplicate': True,
                    'order_id': existing.id,
                    'pos_reference': existing.pos_reference,
                    'uuid': existing.uuid,
                    'amount_total': existing.amount_total,
                    'amount_paid': existing.amount_paid,
                    # The version the caller is now looking at. Without it a
                    # client cannot send expected_revision on its next write, and
                    # the stale-write guard stays dormant.
                    'revision': int(existing.mezze_revision or 0),
                }

            session = env['pos.session'].browse(int(session_id))
            if not session.exists():
                raise ValueError("Unknown session_id %s" % session_id)
            config = session.config_id
            env = env(context=dict(env.context, allowed_company_ids=[config.company_id.id], company_id=config.company_id.id))
            session = session.with_env(env)
            config = config.with_env(env)
            currency = session.currency_id
            partner = env['res.partner'].browse(int(partner_id)) if partner_id else env['res.partner']
            pricelist, fiscal_position = self._resolve_pricing(
                env, config, partner, pricelist_id=kw.get('pricelist_id'),
                fiscal_position_id=kw.get('fiscal_position_id'))
            # A chosen PRESET decides the pricing when the caller named nothing
            # explicit. Applied AFTER _resolve_pricing and not through it, because
            # that helper deliberately refuses a pricelist the branch does not list —
            # a till must not be able to name one it does not trade on. A preset's
            # pricelist is not client input: it came from `available_preset_ids`, so
            # it is the branch's own configuration and passing it through a guard
            # meant for untrusted values would reject the branch's own choice.
            if not kw.get('pricelist_id') and not kw.get('fiscal_position_id'):
                preset_pl, preset_fp = self._preset_pricing(env, config, kw.get('preset_id'))
                if preset_pl:
                    pricelist = env['product.pricelist'].browse(preset_pl)
                if preset_fp:
                    fiscal_position = env['account.fiscal.position'].browse(preset_fp)

            # BOOKING A TIME. Checked before anything is written, and under a lock, so
            # two tills cannot both take the last place in a slot.
            booked_preset = env['pos.preset']
            booked_time = False
            if kw.get('preset_id') and 'use_presets' in config._fields and config.use_presets:
                allowed = config.available_preset_ids or config.default_preset_id
                booked_preset = allowed.filtered(
                    lambda p: p.id == int(kw['preset_id']))[:1]
            if booked_preset and kw.get('preset_time'):
                try:
                    booked_time = fields.Datetime.to_datetime(kw['preset_time'])
                except (TypeError, ValueError):
                    return self._json({'ok': False, 'error': 'bad_preset_time',
                                       'message': 'That is not a time.'}, status=400)
                existing = env['pos.order'].search([('uuid', '=', uuid)], limit=1)
                full = self._assert_slot_free(env, booked_preset, booked_time, existing)
                if full:
                    return self._json(full, status=409)
            allow_override = self._price_override_allowed(env, config)

            # Combos and half-&-half are built as parent+child lines AFTER the
            # order exists (the child→parent link needs real ids), so split them
            # out of the flat line loop and graft them onto a draft.
            plain_lines, combo_carts, half_carts = self._split_combos(env, lines)
            # Validate every combo selection BEFORE anything is written. The picks
            # used to be resolved only at graft time, after the order existed — so a
            # cart carrying an item from another combo was correctly refused with a
            # 400 and still left an orphan draft order behind in the session. A
            # refusal has to leave the session exactly as it found it.
            for cart in (combo_carts or []):
                self._resolve_combo(env, env['product.product'].browse(
                    int(cart['product_id'])), cart)

            # ---- Build order lines server-side (do NOT trust client totals) ----
            AccountTax = env['account.tax']
            order_lines = []
            total_base = 0.0
            total_incl = 0.0
            for line in plain_lines:
                product = env['product.product'].browse(int(line['product_id']))
                if not product.exists():
                    raise ValueError("Unknown product_id %s" % line.get('product_id'))
                self._assert_available(env, config, product)      # reject 86'd items
                # CONV-3: the chosen POS-time attribute values. This path had none —
                # it was a second, modifier-blind line builder beside _build_lines, so
                # a till could show "no onion" and the kitchen would never hear it.
                # Same guard and same surcharge as the fire/pay/qr path.
                mezze_delta, mezze_cmds = self._validate_mezze_modifiers(env, product, line)
                if product.product_tmpl_id.mezze_modifier_group_ids:
                    # One system per product: the attribute path is skipped
                    # entirely, so a colliding id cannot be surcharged twice.
                    ptavs = env['product.template.attribute.value']
                else:
                    self._validate_modifiers(env, product, line)  # reject over-selection
                    ptavs = self._line_attr_values(env, product, line)
                price_extra = sum(ptavs.mapped('price_extra')) + mezze_delta
                qty = float(line.get('qty', 1.0))
                line_disc = float(line.get('discount', 0.0))   # per-line %, not the loyalty redeem
                # price_unit: honour client override, else pricelist price. The client
                # sends the BASE price; the server adds the modifier surcharge, so a
                # configured line can never be priced by the browser.
                if line.get('price_unit') is not None and allow_override:
                    price_unit = float(line['price_unit'])
                else:
                    price_unit = pricelist._get_product_price(product, qty) if pricelist \
                        else product.lst_price
                price_unit += price_extra

                # tax_ids: honour client override, else product taxes through FP.
                if line.get('tax_ids'):
                    tax_ids = AccountTax.browse([int(t) for t in line['tax_ids']])
                else:
                    company_taxes = product.taxes_id.filtered_domain(
                        AccountTax._check_company_domain(env.company))
                    tax_ids = fiscal_position.map_tax(company_taxes)

                price_after_disc = price_unit * (1 - line_disc / 100.0)
                if tax_ids:
                    tv = tax_ids.compute_all(price_after_disc, currency, qty,
                                             product=product, partner=partner or None)
                    subtotal = tv['total_excluded']
                    subtotal_incl = tv['total_included']
                else:
                    subtotal = price_after_disc * qty
                    subtotal_incl = subtotal

                total_base += subtotal
                total_incl += subtotal_incl
                line_vals = {
                    'product_id': product.id,
                    'qty': qty,
                    'price_unit': price_unit,
                    'discount': line_disc,
                    'tax_ids': [(6, 0, tax_ids.ids)],
                    'price_subtotal': subtotal,
                    'price_subtotal_incl': subtotal_incl,
                    # Same rule as the canonical builder: a tracked product records
                    # WHICH batch went out, an untracked one records nothing.
                    'pack_lot_ids': self._lot_commands(product, line, qty),
                }
                # The cashier's typed instruction is DURABLE. It used to be
                # accepted by the route, shown in the panel, sent on every sync —
                # and never written, so it vanished the moment the order was
                # re-synced or resumed. Only /orders/comp ever wrote this field.
                _note = (line.get('note') or line.get('mod') or '').strip()
                if _note and 'customer_note' in env['pos.order.line']._fields:
                    line_vals['customer_note'] = _note[:200]
                # Same rule as the canonical builder, for the same reason: a seat
                # written on one path and dropped on the other would make a split
                # by seat depend on how the order happened to be sent.
                _seat = self._seat_number(line)
                if _seat:
                    line_vals['mezze_seat'] = _seat
                if mezze_cmds:
                    # Structured selections as rows, never a joined label.
                    line_vals['mezze_modifier_ids'] = mezze_cmds
                if ptavs:
                    line_vals['attribute_value_ids'] = [(6, 0, ptavs.ids)]
                    line_vals['price_extra'] = price_extra
                    line_vals['full_product_name'] = '%s (%s)' % (
                        product.display_name,
                        ', '.join(ptavs.mapped('product_attribute_value_id.name')))
                order_lines.append((0, 0, line_vals))

            # ---- Tip / gratuity: a tax-free line on the native tip product, so
            # it reconciles through pos.order.tip_amount + is_tipped. Added to the
            # total so the tender covers it. ----
            tip_amt = round(float(tip or 0.0), 2)
            if tip_amt > 0:
                tip_product = self._tip_product(env, config)
                order_lines.append((0, 0, {
                    'product_id': tip_product.id, 'qty': 1, 'price_unit': tip_amt,
                    'discount': 0.0, 'tax_ids': [(6, 0, [])],
                    'price_subtotal': tip_amt, 'price_subtotal_incl': tip_amt,
                    'pack_lot_ids': []}))
                total_base += tip_amt
                total_incl += tip_amt

            # ---- S2C-1 cashier DRAFT: persist the order UNPAID so the tender is
            # taken via /orders/pay, which enforces the S2 payment policy engine
            # (device / reference / duplicate / manager approval). Server-computed
            # totals are authoritative; the browser never dictates the amount. Only
            # a plain order takes this path — combos/half/loyalty/gift keep the
            # existing atomic build-and-pay flow. ----
            if draft and not (combo_carts or half_carts or (discount and discount_product_id)
                              or gift_card_code):
                draft_dict = {
                    'uuid': uuid, 'session_id': session.id, 'company_id': config.company_id.id,
                    'user_id': env.uid, 'partner_id': partner.id or False,
                    'pricelist_id': pricelist.id or False,
                    'fiscal_position_id': fiscal_position.id or False,
                    'name': 'Mezze %s' % uuid,
                    'date_order': fields.Datetime.to_string(fields.Datetime.now()),
                    # An UPDATE has to REPLACE the draft's lines, not add to them.
                    # sync_from_ui writes the payload's line commands onto the order,
                    # and these are all (0, 0, ...) creates — so without the explicit
                    # clear, re-saving a cart of 2 onto a draft of 1 left a draft of 3
                    # and a guest billed for items nobody ordered. The clear is scoped
                    # to drafts that _updatable_draft already vetted: never a paid
                    # order, never one a split has divided.
                    'lines': ([(5, 0, 0)] + order_lines) if existing else order_lines,
                    'payment_ids': [],
                    'amount_tax': total_incl - total_base, 'amount_total': total_incl,
                    'amount_paid': 0.0, 'amount_return': 0.0,
                    'last_order_preparation_change': empty_preparation_change(), 'to_invoice': False,
                    'state': 'draft',
                }
                if table_id and 'table_id' in env['pos.order']._fields:
                    draft_dict['table_id'] = int(table_id)
                if existing:
                    # sync_from_ui's UPDATE branch pops 'access_token' off the payload
                    # unconditionally, so an update without one raises KeyError before
                    # it ever reaches the order. Send the token the order already has:
                    # this identifies the same record, it does not re-issue anything.
                    draft_dict['access_token'] = existing.access_token or ''
                env['pos.order'].sync_from_ui([draft_dict])
                order = env['pos.order'].search([('uuid', '=', uuid)], limit=1)
                if not order:
                    raise ValueError("sync_from_ui did not persist the draft order")
                self._stamp_ref(env, order, self._node_terminal(env), order.id)
                # Eat-in vs takeaway is the CASHIER's call at the counter and it is
                # not derivable from anything else: a counter order with no table is
                # ambiguous until someone says which it is. It carries real meaning
                # downstream (packaging, and tax treatment in several MENA regimes),
                # so it is stored rather than guessed.
                self._apply_service_mode(order, service_mode)
                self._apply_preset_booking(order, booked_preset, booked_time)
                ship_err = self._apply_ship_later(env, order, config, shipping_date)
                if ship_err:
                    return self._json(ship_err, status=400)
                # CP10 — close the seat->order loop for a table's lazily-created DRAFT
                # order too (the full-order path already does this): a seated
                # reservation/waitlist on this table adopts the order + propagates its
                # guest/customer context. Idempotent (only fills an empty pos_order_id);
                # never raises into the sync path.
                self._mezze_stamp_actor(env, order)
                self._mezze_link_seated_order(env, order)
                # The composition just changed, so the version other terminals
                # hold is now old. `mezze_revision` said it was "bumped on every
                # authoritative change" but only split/* ever moved it, which
                # left the stale-write guard comparing 0 to 0 for ever.
                order.mezze_bump_revision()
                log.write({'status': 'ok', 'pos_order_id': order.id,
                           'session_id': order.session_id.id, 'message': 'Draft order synced.'})
                return {'ok': True, 'duplicate': False, 'draft': True,
                        'order_id': order.id, 'pos_reference': order.pos_reference,
                        'uuid': order.uuid, 'amount_total': order.amount_total,
                        'amount_paid': order.amount_paid,
                        'revision': int(order.mezze_revision or 0)}

            # ---- Gift card tender: validate the card and reserve the amount it
            # covers as its OWN pos.payment (on the Gift Card method); the rest of
            # the bill is settled by the client's other tenders. The card is
            # decremented only AFTER the order is confirmed paid (below). ----
            gift_card = None
            gc_applied = 0.0
            if gift_card_code:
                gift_card = self._giftcard_by_code(env, gift_card_code)
                if not gift_card:
                    raise ValueError("Gift card %s not found" % gift_card_code)
                if gift_card.expiration_date and gift_card.expiration_date < fields.Date.today():
                    raise ValueError("Gift card %s has expired" % gift_card.code)
                gc_req = round(float(gift_card_amount), 2) if gift_card_amount else gift_card.points
                gc_applied = min(gc_req, gift_card.points, round(total_incl, 2))
                if gc_applied <= 0:
                    raise ValueError("Gift card %s has no balance" % gift_card.code)

            # ---- Build payments. When the client sends several tenders (a
            # split bill, or mixed cash+card), record ONE pos.payment per tender
            # so the split is faithful; the LAST tender absorbs any rounding drift
            # so the payments always sum to the SERVER-computed tax-inclusive total
            # (the order can never disagree with the displayed bill). ----
            pay_target = round(total_incl - gc_applied, 2)     # what non-gift tenders cover
            plist = [p for p in (payments or [])
                     if p.get('payment_method_id') and float(p.get('amount', 0) or 0) > 0]
            order_payments = []
            if pay_target > 0:
                if len(plist) >= 2:
                    running = 0.0
                    for i, p in enumerate(plist):
                        amt = (round(pay_target - running, 2) if i == len(plist) - 1
                               else round(float(p['amount']), 2))
                        running += amt
                        order_payments.append((0, 0, {'amount': amt, 'name': fields.Datetime.now(),
                                                       'payment_method_id': int(p['payment_method_id'])}))
                else:
                    pmid = int(plist[0]['payment_method_id']) if plist \
                        else (config.payment_method_ids[:1].id)
                    order_payments.append((0, 0, {'amount': pay_target, 'name': fields.Datetime.now(),
                                                  'payment_method_id': pmid}))
            if gc_applied > 0:
                gc_pm = self._giftcard_pm(env, config)
                order_payments.append((0, 0, {'amount': gc_applied, 'name': fields.Datetime.now(),
                                              'payment_method_id': gc_pm.id}))
            pmid = order_payments[0][2]['payment_method_id'] if order_payments \
                else (config.payment_method_ids[:1].id)
            paid_total = total_incl

            # Loyalty redemption needs a discount LINE, which
            # sync_from_ui strips (it wants reward-line metadata). So for a
            # redeemed order we create a DRAFT, add the discount line via ORM,
            # then finalise the (discounted) payment ourselves. Combos likewise
            # need their parent/child lines grafted on after create, so both
            # take the draft-then-finalise path.
            redeeming = bool(discount and discount_product_id)
            needs_draft = redeeming or bool(combo_carts) or bool(half_carts)
            # Gift-card tender flows through the direct (paid) sync; combining it
            # with a combo/comp/loyalty order in one ticket isn't wired yet.
            if gift_card and needs_draft:
                raise ValueError("Gift-card payment can't yet combine with "
                                 "combos, comp, or loyalty redemption in one order")

            # ---- Assemble the exact dict pos.order.sync_from_ui expects ----
            # (shape mirrors point_of_sale/tests/common.py::create_ui_order_data)
            order_dict = {
                'uuid': uuid,
                'session_id': session.id,
                'company_id': config.company_id.id,
                'user_id': env.uid,
                'partner_id': partner.id or False,
                'pricelist_id': pricelist.id or False,
                'fiscal_position_id': fiscal_position.id or False,
                'name': 'Mezze %s' % uuid,
                'date_order': fields.Datetime.to_string(fields.Datetime.now()),
                # Same reason as the fast path: sync_from_ui WRITES these commands
                # onto an existing draft, and they are all creates. Re-saving a cart
                # that contains a combo would otherwise leave the order holding both
                # the old lines and the new ones. `existing` is only truthy here when
                # _updatable_draft vetted it, which already means an unsplit, unpaid
                # draft that the caller asked to keep as a draft.
                'lines': ([(5, 0, 0)] + order_lines) if existing else order_lines,
                'payment_ids': [] if needs_draft else order_payments,
                'amount_tax': total_incl - total_base,
                'amount_total': total_incl,
                'amount_paid': 0.0 if needs_draft else paid_total,
                'amount_return': 0.0,
                'last_order_preparation_change': empty_preparation_change(),
                'to_invoice': False,
            }
            if needs_draft:
                order_dict['state'] = 'draft'      # finalise after grafting lines
            # else: no 'state' key -> _process_order finalises it as paid.
            if existing:
                # sync_from_ui's UPDATE branch pops 'access_token' off the payload
                # unconditionally, so an update without one raises KeyError before it
                # ever reaches the order. Send the token the order already has: this
                # identifies the same record, it does not re-issue anything.
                order_dict['access_token'] = existing.access_token or ''

            if table_id and 'table_id' in env['pos.order']._fields:
                order_dict['table_id'] = int(table_id)
            result = env['pos.order'].sync_from_ui([order_dict])
            synced = (result or {}).get('pos.order') or []
            order = env['pos.order'].search([('uuid', '=', uuid)], limit=1)
            if not order:
                raise ValueError("sync_from_ui did not persist the order")

            # R1/CP10: back-link a seated reservation/waitlist for this table to its
            # live order + propagate guest/customer context (idempotent; never raises
            # into the money path). Closes the seat->order loop for the lazy order.
            self._mezze_stamp_actor(env, order)
            self._mezze_link_seated_order(env, order)

            combo_kds = []
            if needs_draft:
                # (a) graft native combo + half-&-half parent/child lines.
                if combo_carts:
                    _cb, _ci, combo_kds = self._combo_apply(env, config, partner,
                                                            order, combo_carts)
                if half_carts:
                    _hb, _hi, half_kds = self._halfhalf_apply(env, config, partner,
                                                              order, half_carts)
                    combo_kds += half_kds
                # (b) graft the loyalty discount line.
                if redeeming:
                    d = float(discount)
                    dp = env['product.product'].browse(int(discount_product_id))
                    # carry the same taxes as the menu so the discount reduces the
                    # taxed total pre-tax, consistent with the displayed bill.
                    dtax = dp.taxes_id
                    tv = dtax.compute_all(-d, config.currency_id, 1, product=dp) if dtax else None
                    dsub = tv['total_excluded'] if tv else -d
                    dincl = tv['total_included'] if tv else -d
                    order.write({'lines': [(0, 0, {
                        'product_id': dp.id, 'qty': 1, 'price_unit': -d,
                        'discount': 0.0, 'tax_ids': [(6, 0, dtax.ids)],
                        'price_subtotal': dsub, 'price_subtotal_incl': dincl, 'pack_lot_ids': []})]})
                # (c) recompute the total across ALL lines, then (d) settle once.
                tot_base = sum(order.lines.mapped('price_subtotal'))
                tot_incl = sum(order.lines.mapped('price_subtotal_incl'))
                order.write({'amount_tax': tot_incl - tot_base, 'amount_total': tot_incl})
                if draft:
                    # THE CALLER ASKED FOR A DRAFT. Stop here.
                    #
                    # `needs_draft` above is a staging flag — "build it open so the
                    # combo/loyalty lines can be grafted on" — and it has nothing to
                    # do with whether the guest has paid. Falling through settled the
                    # bill: add_payment() for the full amount against whatever payment
                    # method happened to be first on the config, then
                    # action_pos_order_paid(). No cashier chose a tender, no drawer
                    # opened, no card was presented. The order simply became paid.
                    #
                    # It was reachable from anything that saves a cart before charging
                    # — Save, assign a table, open Split — as soon as that cart held a
                    # combo or a half-and-half, because those are exactly the carts the
                    # plain draft path above refuses to take. Splitting then failed
                    # with "the split was refused", which is true but names the wrong
                    # thing: the bill had already been closed and paid lines cannot
                    # move.
                    #
                    # A draft does not fire to the kitchen here either — table orders
                    # fire through /orders/fire, and the plain draft path above does
                    # not queue tickets, so neither does this one.
                    self._stamp_ref(env, order, self._node_terminal(env), order.id)
                    self._apply_service_mode(order, service_mode)
                    self._apply_preset_booking(order, booked_preset, booked_time)
                    ship_err = self._apply_ship_later(env, order, config, shipping_date)
                    if ship_err:
                        return self._json(ship_err, status=400)
                    log.write({'status': 'ok', 'pos_order_id': order.id,
                               'session_id': order.session_id.id,
                               'message': 'Draft order synced.'})
                    return {'ok': True, 'duplicate': False, 'draft': True,
                            'order_id': order.id, 'pos_reference': order.pos_reference,
                            'uuid': order.uuid, 'amount_total': order.amount_total,
                            'amount_paid': order.amount_paid}
                pm = (env['pos.payment.method'].browse(int(payments[0]['payment_method_id']))
                      if payments else config.payment_method_ids[:1])
                order.add_payment({'amount': order.amount_total, 'payment_method_id': pm.id,
                                   'name': fields.Datetime.now(), 'pos_order_id': order.id})
                order.action_pos_order_paid()

            # ---- café counter order → put its drinks/food on the KDS/BDS queue.
            # Table orders arrive via /orders/fire; counter orders come here, so
            # this is where a coffee-shop sale enters the barista queue. Its
            # native tracking_number becomes the customer pickup number. The
            # combo PARENT line (a section, no station) is skipped; its real
            # child dishes ride in via combo_kds. ----
            tickets = self._make_station_tickets(
                env, order,
                [(l.product_id, l.qty,
                  ', '.join(l.attribute_value_ids.mapped('product_attribute_value_id.name')))
                 for l in order.lines
                 if l.product_id.type != 'combo' and not l.combo_parent_id] + combo_kds,
                'sync:%s' % uuid, 1)
            self._publish_kds(env, tickets, order, natural_key='sync:%s' % uuid)

            # ---- terminal-scoped receipt number (offline collision-safety) ----
            self._stamp_ref(env, order, self._node_terminal(env), order.id)

            # ---- record the tip on the native pos.order fields ----
            if tip_amt > 0 and order:
                order.sudo().write({'is_tipped': True, 'tip_amount': tip_amt})

            # ---- gift card: decrement the balance now the order is paid ----
            gc_balance = None
            if gift_card and gc_applied > 0:
                self._giftcard_decrement(env, gift_card, gc_applied,
                                         order.pos_reference or order.id)
                gc_balance = gift_card.points
                self._audit(env, 'giftcard.redeem', order, **self._actor(env, kw),
                            detail=json.dumps({'code': gift_card.code, 'applied': gc_applied,
                                               'balance': gc_balance}, default=str))

            # ---- gift card SALE: selling the GIFTCARD product mints a card ----
            issued_cards = self._mint_giftcards(env, order, kw, via='sale')

            # ---- loyalty: award real points if a customer is attached ----
            earned, balance = self._loyalty_earn(env, order)

            log.write({
                'status': 'ok',
                'pos_order_id': order.id,
                'session_id': order.session_id.id,
                'message': 'Order synced (%d queue tickets).' % len(tickets),
            })
            self._audit(env, 'order.pay', order, **self._actor(env, kw),
                        detail=json.dumps({'via': 'order_sync', 'tickets': len(tickets),
                                           'partner_id': partner_id}, default=str))
            return {
                'ok': True,
                'duplicate': False,
                'order_id': order.id,
                'pos_reference': order.pos_reference,
                'tracking_number': order.tracking_number or '',
                'uuid': order.uuid,
                'amount_total': order.amount_total,
                'amount_paid': order.amount_paid,
                'synced_records': len(synced),
                'tickets': len(tickets),
                'gift_card_applied': gc_applied or 0.0, 'gift_card_balance': gc_balance,
                'issued_gift_cards': issued_cards,
                'loyalty_earned': earned, 'loyalty_balance': balance,
            }
        except Exception as exc:  # noqa: BLE001 - clean JSON, never a 500
            _logger.exception("Mezze order sync failed for uuid=%s", uuid)
            try:
                log.write({'status': 'error', 'message': str(exc)})
            except Exception:  # noqa: BLE001
                pass
            return self._json({
                'ok': False,
                'error': 'sync_failed',
                'uuid': uuid,
                'message': str(exc),
            }, status=400)

    # ------------------------------------------------------------------
    # Table service: fire a DRAFT order (deferred payment) + pay it later
    # ------------------------------------------------------------------
    def _line_attr_values(self, env, product, line):
        """Validated ``product.template.attribute.value`` recordset for a line's
        chosen modifiers, filtered to THIS product's template so a client cannot
        inject another product's options (or arbitrary ids)."""
        ids = line.get('attribute_value_ids') or []
        if not ids:
            return env['product.template.attribute.value']
        ptav = env['product.template.attribute.value'].browse([int(i) for i in ids]).exists()
        return ptav.filtered(lambda v: v.product_tmpl_id == product.product_tmpl_id)

    def _line_note(self, env, product, line):
        """Kitchen note for a line — its chosen modifiers AND any free text.

        This used to return one or the other. A configured line therefore reached
        the kitchen with its modifiers and WITHOUT the cashier's typed instruction:
        "no onion" survived, "allergy - no nuts" did not, and nothing said so. Both
        belong on the ticket, so both are sent, modifiers first because that is the
        order the cook reads.
        """
        ptavs = self._line_attr_values(env, product, line)
        parts = []
        if ptavs:
            parts.append(', '.join(ptavs.mapped('product_attribute_value_id.name')))
        free = (line.get('note') or line.get('mod') or '').strip()
        if free:
            parts.append(free)
        return ' · '.join(parts)

    def _menu_domain(self, env, config=None):
        """POS-available products for a BRANCH, mirroring Odoo's own POS domain.

        This used to take no config at all, and so could not be branch-aware: it
        answered "every POS product in the database" for every till. A restaurant
        that had restricted itself to two categories still saw the whole catalogue
        in Mezze while Odoo's own POS showed 26 items — the same shop, two
        different menus, and the Mezze one wrong.

        The three terms that were missing are the three Odoo applies in
        ``product.template._load_pos_data_domain``:

        * the **company** domain, or another company's products leak onto the till;
        * ``sale_ok``, because a product that is not for sale is not a menu item;
        * ``limit_categories`` / ``iface_available_categ_ids`` — the branch's own
          restriction, which is the whole point of the setting.

        Kept on top of that: loyalty reward/discount products are POS-available
        only so their lines survive order sync, and must never appear on a menu.
        """
        rewards = env['loyalty.reward'].sudo().search([])
        rules = env['loyalty.rule'].sudo().search([])
        hidden = set(rewards.mapped('discount_line_product_id').ids)
        hidden |= set(rewards.mapped('reward_product_id').ids)
        hidden |= set(rules.mapped('product_ids').ids)     # gift-card / ewallet triggers
        # A real menu item carries a POS category; loyalty utility products
        # (discount lines, gift-card, e-wallet top-up) do not — filter them out.
        dom = [('available_in_pos', '=', True),
               ('product_tmpl_id.available_in_pos', '=', True),
               ('sale_ok', '=', True),
               ('pos_categ_ids', '!=', False)]
        if config:
            dom += list(env['product.product']._check_company_domain(config.company_id))
            if config.limit_categories and config.iface_available_categ_ids:
                dom.append(('pos_categ_ids', 'in', config.iface_available_categ_ids.ids))
        if hidden:
            dom.append(('id', 'not in', list(hidden)))
        return dom

    def _menu_categories(self, env, config=None):
        """The POS categories a branch actually shows, in the same spirit."""
        dom = []
        if config and config.limit_categories and config.iface_available_categ_ids:
            dom = [('id', 'in', config.iface_available_categ_ids.ids)]
        # NOTE: /shop/menu builds its own category list rather than calling this,
        # and consequently does NOT honour `limit_categories` the way this does.
        # Left alone here: reconciling the two changes what a limited branch shows
        # and is a decision of its own, not part of the kiosk redesign.
        return env['pos.category'].search_read(dom, ['id', 'name'])

    # ------------------------------------------------------------------
    # Self-order availability — Odoo's own gate, honoured on customer surfaces
    # ------------------------------------------------------------------
    # `pos_self_order` adds `self_order_available` to product.template (default True)
    # and ANDs it onto its own product domain. A branch that switches a product off for
    # self-order means it: the kiosk must not list it and must not sell it, however the
    # request arrives. The field only exists when that module is installed, so this is a
    # soft gate rather than a hard dependency — where it is absent, POS availability is
    # the only truth there is.
    _SELFORDER_CHANNELS_GATED = ('kiosk',)

    def _selforder_gate_field(self, env):
        return 'self_order_available' if 'self_order_available' in env['product.template']._fields else None

    def _selforder_domain(self, env, channel):
        """Extra domain terms for a self-order channel's menu. Empty for the rest."""
        fname = self._selforder_gate_field(env)
        if channel in self._SELFORDER_CHANNELS_GATED and fname:
            return [('product_tmpl_id.%s' % fname, '=', True)]
        return []

    def _assert_selforder_allowed(self, env, channel, products):
        """Refuse a product the branch excluded from self-order. Called on the ORDER
        path as well as the menu, because a hand-made request never went through the
        menu at all."""
        fname = self._selforder_gate_field(env)
        if channel not in self._SELFORDER_CHANNELS_GATED or not fname:
            return
        for product in products:
            if not product.product_tmpl_id[fname]:
                raise ValueError("Product %s is not available for self-order"
                                 % product.display_name)

    def _assert_customer_config(self, env, product, line):
        """Customer configuration guard for an UNTRUSTED self-order client.

        The staff paths filter an unknown attribute value out silently, which keeps the
        money right; a public kiosk should say no rather than quietly accept a request
        it does not understand. Every chosen value must belong to this product's
        template AND to a group the customer was actually offered, and the quantity has
        to be a real one.
        """
        qty = line.get('qty', 1)
        try:
            qty = float(qty)
        except (TypeError, ValueError):
            raise ValueError("Invalid quantity for %s" % product.display_name)
        if not (qty == qty) or qty <= 0 or qty > self._SELFORDER_MAX_QTY:   # NaN, 0, negative, absurd
            raise ValueError("Invalid quantity for %s" % product.display_name)
        ids = [int(i) for i in (line.get('attribute_value_ids') or [])]
        if not ids:
            return
        offered = set()
        for al in product.product_tmpl_id.attribute_line_ids:
            if al.attribute_id.create_variant == 'no_variant':
                offered |= set(al.product_template_value_ids.ids)
        unknown = [i for i in ids if i not in offered]
        if unknown:
            raise ValueError("Option %s is not offered for %s"
                             % (unknown[0], product.display_name))

    def _assert_revision(self, order, expected):
        """Refuse a write based on a version of this check that has since moved.

        Two terminals may hold one table open. ``mezze_revision`` already existed
        and was already bumped through one method — but only ``split/commit``
        ever checked it, so every other way of changing a check accepted a stale
        write silently. That is the collision the design draws a banner for.

        Returns a ready-to-return 409 body, or None to proceed. The body carries
        the CURRENT lines as well as the revision: the client knows what it had,
        the server knows what is there now, and the banner names the difference
        ("Kofta quantity differs — yours 4 · theirs 3"). Sending only a revision
        would leave the client able to say "something changed" and nothing more.

        Not an error to log with a stack: on a busy floor this is a normal
        Tuesday, and the caller is expected to resolve rather than crash.
        """
        if expected is None:
            # A caller that does not track revisions (kiosk, QR, an aggregator
            # push) is not lying about one. Enforcing here would break every
            # client that never held a check open in the first place.
            return None
        try:
            expected = int(expected)
        except (TypeError, ValueError):
            return self._json({'ok': False, 'error': 'bad_revision'}, status=400)
        current = int(order.mezze_revision or 0)
        if expected == current:
            return None
        return self._json({
            'ok': False,
            'error': 'stale_revision',
            'revision': current,
            'expected': expected,
            # What the check looks like NOW, so the client can show the
            # difference rather than silently redrawing over someone's work.
            'lines': [{
                'id': l.id,
                'product_id': l.product_id.id,
                'name': l.full_product_name or l.product_id.display_name,
                'qty': l.qty,
                'price_unit': l.price_unit,
                'note': l.note or '',
            } for l in order.lines],
        }, status=409)

    def _validate_mezze_modifiers(self, env, product, line):
        """Validate this line's Mezze modifier selections and price them.

        THE single server-side answer to "can we sell this configuration right
        now". Called from BOTH line builders -- ``_build_lines`` (fire/pay/qr/
        shop/checkout/sync/aggregator) and ``order_sync``'s own loop -- because
        the design's requirement is that every order-entry point sees the same
        check, and this file already carries two builders.

        Returns ``(price_delta, selection_commands)``. Raises ValueError naming
        the reason: a refusal a guest cannot understand is one that gets worked
        around at the till.

        The delta is summed from the OPTION RECORDS, never the client -- the same
        rule the surrounding price handling already follows.
        """
        groups = product.product_tmpl_id.mezze_modifier_group_ids
        raw = line.get('mezze_modifiers') or []
        if groups and not raw:
            # Every existing surface echoes back the ids the SERVER handed it in
            # `values[].id`, under the key it has always used. For a Mezze-backed
            # product those are option ids, so read them rather than refusing:
            # six surfaces send this key, and breaking all of them to rename a
            # field would be a migration that takes the product down with it.
            raw = line.get('attribute_value_ids') or []
        if not raw and not groups.filtered('required'):
            return 0.0, []
        Option = env['mezze.modifier.option'].sudo()
        try:
            option_ids = [int(i) for i in raw]
        except (TypeError, ValueError):
            raise ValueError("Invalid modifier selection for %s" % product.display_name)
        options = Option.browse(option_ids).exists()
        if len(options) != len(option_ids):
            raise ValueError("Unknown modifier option for %s" % product.display_name)
        # An option from a group this product does not carry is not unknown by
        # id -- it is simply not on offer here, and is refused as such.
        offered = set(groups.ids)
        for o in options:
            if o.group_id.id not in offered:
                raise ValueError("%s is not offered for %s"
                                 % (o.name, product.display_name))

        selections = [mezze_mods.Selection(g=o.group_id.code, t=o.id,
                                           label=o.name, p=o.price_delta)
                      for o in options]
        errors = mezze_mods.validate(groups.as_domain(), selections)
        if errors:
            raise ValueError(self._mezze_mod_message(errors[0], groups, Option,
                                                     product))
        commands = [(0, 0, {'group_id': o.group_id.id, 'option_id': o.id,
                            'label': o.name, 'price_delta': o.price_delta})
                    for o in options]
        return mezze_mods.total_delta(selections), commands

    def _mezze_mod_message(self, error, groups, Option, product):
        """A refusal a guest can act on, not a code.

        The 86 case names the OPTION, so a server can offer the next size rather
        than saying "unavailable" and ending the conversation.
        """
        code, ref = error
        if code == mezze_mods.ERR_UNAVAILABLE:
            return "%s is not available right now." % (Option.browse(ref).name or "That option")
        if code == mezze_mods.ERR_UNKNOWN_OPTION:
            return "That option is not on the menu."
        if code == mezze_mods.ERR_UNKNOWN_GROUP:
            return "That modifier group is not on the menu."
        name = groups.filtered(lambda g: g.code == ref).name or ref
        if code == mezze_mods.ERR_REQUIRED:
            return "%s needs a choice of %s." % (product.display_name, name)
        if code == mezze_mods.ERR_MIN:
            return "Choose more from %s." % name
        if code == mezze_mods.ERR_MAX:
            return "Too many choices from %s." % name
        return str(code)

    _SELFORDER_MAX_QTY = 99      # a kiosk order of 100+ of one line is a mistake or an attack

    def _product_modifiers(self, env, product):
        """Modifier groups for a product — the ONE reader every surface calls.

        Serves Mezze modifier groups (``mezze.modifier.group``, design BE-010)
        when the product carries them, and falls back to the older POS-time
        (``no_variant``) attribute lines when it does not.

        The payload SHAPE is identical either way, deliberately: the Register,
        QR, shop, kiosk and drive-thru menus all read this one function, so the
        migration off attributes changes what backs the answer without changing
        the answer. Once every product is migrated the fallback is dead code and
        the attribute path can go.
        """
        if product.product_tmpl_id.mezze_modifier_group_ids:
            return self._mezze_product_modifiers(product)
        groups = []
        for al in product.product_tmpl_id.attribute_line_ids:
            if al.attribute_id.create_variant != 'no_variant':
                continue
            multi = al.attribute_id.display_type == 'multi'
            n = len(al.product_template_value_ids)
            groups.append({
                'line_id': al.id,
                'attribute_id': al.attribute_id.id,
                'attribute': al.attribute_id.name,
                'display_type': al.attribute_id.display_type,   # radio / multi / select / color
                'multi': multi,
                # A single-select (non-multi) group is required-exactly-one; a multi
                # group is optional-any. Server enforces the MAX (≤1 for single-select);
                # the UI enforces the required minimum.
                'required': not multi,
                'min': 0 if multi else 1,
                'max': n if multi else 1,
                'values': [{'id': v.id, 'name': v.product_attribute_value_id.name,
                            'price_extra': v.price_extra}
                           for v in al.product_template_value_ids],
            })
        return groups

    def _mezze_product_modifiers(self, product):
        """Mezze groups in the payload shape every menu surface already reads.

        ``values[].price_extra`` keeps its name even though the field is
        ``price_delta``: five surfaces read that key, and renaming it to be
        tidier would break them all for no gain.
        """
        groups = []
        for g in product.product_tmpl_id.mezze_modifier_group_ids.sorted('sequence'):
            multi = g.max_select != 1
            groups.append({
                # `line_id` is what shop.html/pos.html/qr.html key their selection
                # map on. Same value as group_id -- emitted under the old name
                # because "shape-identical" has to mean identical, not nearly.
                'line_id': g.id,
                'group_id': g.id,
                'code': g.code,
                'attribute': g.name,
                'display_type': 'multi' if multi else 'radio',
                'multi': multi,
                'required': g.required,
                'min': g.min_select,
                'max': g.max_select or len(g.option_ids),
                'is_combo': g.is_combo,
                # 86 lives on the option: an unavailable choice is still LISTED,
                # marked, so a guest sees the dish is fine and only that size is
                # gone. Hiding it silently reads as "we do not make it".
                'values': [{'id': o.id, 'name': o.name, 'price_extra': o.price_delta,
                            'available': o.available, 'is_default': o.is_default}
                           for o in g.option_ids.sorted('sequence')],
            })
        return groups

    def _validate_modifiers(self, env, product, line):
        """Server-authoritative modifier guard: a single-select (non-multi) group may
        carry AT MOST one value. Rejects injection/over-selection; values are already
        filtered to this product's template by _line_attr_values."""
        ptavs = self._line_attr_values(env, product, line)
        if not ptavs:
            return
        single_attr_ids = {al.attribute_id.id for al in product.product_tmpl_id.attribute_line_ids
                           if al.attribute_id.create_variant == 'no_variant'
                           and al.attribute_id.display_type != 'multi'}
        seen = {}
        for v in ptavs:
            aid = v.attribute_id.id
            seen[aid] = seen.get(aid, 0) + 1
        for aid, cnt in seen.items():
            if aid in single_attr_ids and cnt > 1:
                raise UserError("Only one option may be chosen for %r."
                                % env['product.attribute'].browse(aid).name)

    def _product_combos(self, env, product):
        """Combo groups for a combo-type product: each group and its selectable
        items (real ``product.combo`` / ``product.combo.item``). Empty for
        non-combo products. The frontend renders one picker per group; the
        server re-prices on sync so the client's choice can't move the money."""
        if product.type != 'combo':
            return []
        groups = []
        for combo in product.product_tmpl_id.combo_ids:
            groups.append({
                'combo_id': combo.id,
                'name': combo.name,
                # Odoo's own cardinality, from point_of_sale's extension of
                # product.combo: qty_max is how many items may be taken from this
                # group, qty_free how many the meal's price already covers. Both
                # default to 1, which is the familiar "choose one" combo — but a
                # branch may configure "choose up to 2, one included", and the
                # client cannot honour a rule it was never told.
                'qty_max': combo.qty_max,
                'qty_free': combo.qty_free,
                # each item beyond qty_free costs the group's base price, so the
                # client needs it to preview what it is about to charge
                'base_price': combo.base_price,
                'items': [{'item_id': it.id, 'product_id': it.product_id.id,
                           'name': it.product_id.display_name,
                           'extra_price': it.extra_price}
                          for it in combo.combo_item_ids],
            })
        return groups

    def _sanitize_customer_lines(self, lines):
        """S4 §63 — strip any client-sent price_unit / discount / total from a public
        customer order so the server recomputes the base price from the pricelist and
        applies discounts only via server-validated promos. A shopper can never inject
        a price. Keeps product_id / qty / attribute_value_ids / mezze_modifiers /
        note only.

        ``mezze_modifiers`` is a list of OPTION IDS, never prices: the server
        reads each option's own ``price_delta``, so passing one through here
        cannot inject a surcharge any more than passing a product id can."""
        clean = []
        for l in (lines or []):
            clean.append({
                'product_id': l.get('product_id'),
                'qty': l.get('qty', 1),
                'attribute_value_ids': l.get('attribute_value_ids') or [],
                'mezze_modifiers': l.get('mezze_modifiers') or [],
                'combo': l.get('combo'), 'halves': l.get('halves'),
                'note': (l.get('note') or '')[:200],
            })
        return clean

    def _lot_commands(self, product, line, qty):
        """``pack_lot_ids`` for one line, from the lot or serial numbers it names.

        Mezze wrote ``'pack_lot_ids': []`` on every path, so a tracked product left
        the branch with no record of WHICH batch went out. For food that is the whole
        point of tracking one: an allergen or contamination recall has to answer which
        orders received a given lot, and an empty list cannot.

        Two rules, both from what tracking MEANS rather than from convenience:

        * a SERIAL is one physical item, so the count must equal the quantity — three
          bottles cannot leave under two serials, and letting them makes the trail
          quietly wrong instead of obviously incomplete;
        * an untracked product is given none. A browser may send whatever it likes;
          inventing a lot for something the branch does not track would put fiction in
          the audit trail.
        """
        names = [str(n).strip() for n in (line.get('lot_names') or []) if str(n).strip()]
        tracking = getattr(product, 'tracking', 'none')
        if tracking not in ('lot', 'serial') or not names:
            return []
        if tracking == 'serial' and len(names) != int(qty):
            raise ValueError(
                "%s is tracked by serial: %d serial number(s) for a quantity of %g"
                % (product.display_name, len(names), qty))
        # De-duplicated, order preserved: the same lot typed twice is one lot, and a
        # repeated SERIAL is two items claiming one identity.
        seen, unique = set(), []
        for n in names:
            if n not in seen:
                seen.add(n)
                unique.append(n)
        if tracking == 'serial' and len(unique) != len(names):
            raise ValueError(
                "%s: the same serial number was given twice" % product.display_name)
        return [(0, 0, {'lot_name': n}) for n in unique]

    #: A table of more than this many seats is a typo, not a table. The cap exists
    #: so a client cannot write an arbitrary integer into every line of a bill.
    MAX_SEAT = 99

    def _seat_number(self, line):
        """Which seat ordered this line, or 0 for nobody in particular.

        Zero is not seat zero — it is UNASSIGNED, and it is what a shared bottle of
        wine in the middle of the table is. A split by seat must be able to say "this
        was not claimed" rather than handing it to whoever happens to be first.

        Anything that is not a plausible seat becomes 0 rather than an error: a seat
        is an annotation on an order, and refusing to sell a meal because a browser
        sent "3a" would be the wrong trade.
        """
        raw = line.get('seat')
        if raw in (None, '', False):
            return 0
        try:
            seat = int(raw)
        except (TypeError, ValueError):
            return 0
        return seat if 0 < seat <= self.MAX_SEAT else 0

    # A namespace of its own so a slot booking cannot collide with the fire lock.
    _SLOT_LOCK_NS = 0x4D5A5301

    def _preset_slot_capacity(self, env, preset, when):
        """(taken, capacity) for one preset at one moment.

        Reuses core's ``_compute_slots_usage`` — the same map the native front end
        reads — so a slot cannot look full in one product and free in the other.
        """
        capacity = max(1, int(preset.slots_per_interval or 1))
        usage = preset._compute_slots_usage()
        key = when.strftime("%Y-%m-%d %H:%M:%S")
        taken = len(usage.get(key) or [])
        return taken, capacity

    def _assert_slot_free(self, env, preset, when, order=None):
        """Refuse a booking into a full slot.

        Core computes slot usage and leaves the CAPACITY decision to its front end.
        A capacity enforced in a browser is not a capacity: two tills reading the
        same free slot both book it, and a kitchen that promised five orders at 19:40
        has seven. The check therefore runs here, and under a lock, because the read
        and the write have to be one step.
        """
        if not preset or not preset.use_timing or not when:
            return None
        env.cr.execute("SELECT pg_advisory_xact_lock(%s, %s)",
                       (self._SLOT_LOCK_NS, preset.id))
        taken, capacity = self._preset_slot_capacity(env, preset, when)
        # An order already holding this slot is not competing with itself.
        if order and order.exists() and order.preset_time == when \
                and order.preset_id.id == preset.id:
            taken = max(0, taken - 1)
        if taken >= capacity:
            return {'ok': False, 'error': 'slot_full',
                    'message': 'That time is fully booked.',
                    'taken': taken, 'capacity': capacity}
        return None

    @http.route(f'{API_PREFIX}/preset/slots', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*', readonly=True)
    def preset_slots(self, preset_id=None, **kw):
        """What is still free, for a preset that manages orders by time.

        A branch taking delivery or collection orders needs to promise a time it can
        actually keep — which is what `slots_per_interval` is for, and what nothing in
        Mezze read.
        """
        auth = self._authorize(endpoint='preset/slots')
        if auth:
            return auth
        env = self._api_env()
        try:
            config = self._resolve_config(env, kw.get('config_id'))
            allowed = config.available_preset_ids or config.default_preset_id
            preset = allowed.filtered(lambda p: p.id == int(preset_id or 0))[:1]
            if not preset:
                return self._json({'ok': False, 'error': 'unknown_preset'}, status=404)
            if not preset.use_timing:
                # Not an error: most order types are not scheduled, and saying so is
                # more use than an empty list that looks like "fully booked".
                return {'ok': True, 'preset_id': preset.id, 'use_timing': False,
                        'slots': []}
            capacity = max(1, int(preset.slots_per_interval or 1))
            usage = preset._compute_slots_usage()
            slots = [{'at': at, 'taken': len(ids or []), 'capacity': capacity,
                      'free': max(0, capacity - len(ids or []))}
                     for at, ids in sorted(usage.items())]
            return {'ok': True, 'preset_id': preset.id, 'use_timing': True,
                    'capacity': capacity,
                    'interval_minutes': int(preset.interval_time or 0),
                    'slots': slots}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze preset_slots failed")
            return self._json({'ok': False, 'error': 'preset_slots_failed',
                               'message': str(exc)}, status=400)

    def _preset_pricing(self, env, config, preset_id):
        """A preset's own pricelist and fiscal position, if the branch uses presets.

        ``pos.preset`` is v19's order type — eat-in, takeaway, delivery — and each one
        may price differently: a takeaway VAT rate, a delivery pricelist. Mezze read
        presets in the kiosk path only and rebuilt order type on the till as a
        two-value field plus free text, so a branch that priced its order types
        through Odoo got the eat-in price on every till order.

        Resolved from the PRESET ID rather than from a pricelist the browser names.
        The till says which order type the guest chose; what that costs is the
        branch's configuration to decide, and a client that could name a pricelist
        directly could name a cheaper one.
        """
        if not preset_id or 'use_presets' not in config._fields or not config.use_presets:
            return None, None
        allowed = config.available_preset_ids or config.default_preset_id
        preset = allowed.filtered(lambda p: p.id == int(preset_id))[:1]
        if not preset:
            # An id the branch does not offer is not an error worth failing a sale
            # over — it is simply not a preset here, so the branch's own defaults
            # stand.
            return None, None
        return (preset.pricelist_id.id or None,
                preset.fiscal_position_id.id or None)

    def _resolve_pricing(self, env, config, partner, pricelist_id=None,
                         fiscal_position_id=None):
        """The pricelist and fiscal position an order actually prices against.

        Mezze always used ``config.pricelist_id`` and nothing else. The partner's own
        pricelist — ``property_product_pricelist``, which appeared NOWHERE in the
        addon — was never consulted, so a B2B customer with a negotiated agreement was
        silently charged branch list price. The asymmetry was easy to miss because the
        partner *was* already used for the fiscal position, so tax was customer-aware
        while price was not.

        Precedence: an explicit choice, then the partner's own, then the branch.

        An explicit pricelist must be one the branch actually offers
        (``available_pricelist_ids``); a till cannot be told to price against a list
        its branch does not trade on. The partner's own is honoured whether or not it
        is in that list, because that agreement was made with the customer rather than
        configured on the till.
        """
        pricelist = config.pricelist_id
        # Use the SPECIFIC pricelist, not the computed accessor.
        #
        # In v19 ``property_product_pricelist`` is a computed field that always
        # resolves to something — it falls back to a company default when the partner
        # has no agreement of their own. Reading it here would therefore re-price
        # EVERY named customer against that default instead of the branch list, which
        # is a bigger change than the bug being fixed. ``specific_property_product_
        # pricelist`` is the stored field that means what we actually want: this
        # customer negotiated a price.
        if partner:
            agreed = getattr(partner, 'specific_property_product_pricelist', False)
            if agreed is False:      # older schema without the split
                agreed = getattr(partner, 'property_product_pricelist', False)
            if agreed:
                pricelist = agreed
        if pricelist_id:
            chosen = env['product.pricelist'].browse(int(pricelist_id)).exists()
            allowed = config.available_pricelist_ids or config.pricelist_id
            if chosen and chosen in allowed:
                pricelist = chosen
        fiscal_position = (partner.property_account_position_id
                           if partner else env['account.fiscal.position'])
        fiscal_position = fiscal_position or config.default_fiscal_position_id
        if fiscal_position_id:
            fp = env['account.fiscal.position'].browse(int(fiscal_position_id)).exists()
            allowed_fp = config.fiscal_position_ids or config.default_fiscal_position_id
            if fp and (not allowed_fp or fp in allowed_fp):
                fiscal_position = fp
        return pricelist, fiscal_position

    def _price_override_allowed(self, env, config):
        """Whether this till may send its own ``price_unit``.

        ``restrict_price_control`` is a core switch Mezze never read: the line
        builders honoured a client price unconditionally. They still do when the
        branch allows it — but a branch that restricts price control now actually
        restricts it.
        """
        if not getattr(config, 'restrict_price_control', False):
            return True
        role = self._acting_role(env)
        return role in ('supervisor', 'manager', 'admin', 'administrator')

    def _build_lines(self, env, config, partner, lines, pricelist_id=None,
                     fiscal_position_id=None):
        """Server-side, tax-correct order-line builder shared by fire/pay/qr.
        Applies modifier ``price_extra`` server-side (never trusts the client's
        total) and records the chosen ``attribute_value_ids`` on the line.
        Returns (line commands, total_excl, total_incl)."""
        currency = config.currency_id
        pricelist, fiscal_position = self._resolve_pricing(
            env, config, partner, pricelist_id=pricelist_id,
            fiscal_position_id=fiscal_position_id)
        allow_override = self._price_override_allowed(env, config)
        AccountTax = env['account.tax']
        order_lines, base, incl = [], 0.0, 0.0
        for line in (lines or []):
            product = env['product.product'].browse(int(line['product_id']))
            if not product.exists():
                raise ValueError("Unknown product_id %s" % line.get('product_id'))
            self._assert_available(env, config, product)      # reject 86'd items
            mezze_delta, mezze_cmds = self._validate_mezze_modifiers(env, product, line)
            if not product.product_tmpl_id.mezze_modifier_group_ids:
                self._validate_modifiers(env, product, line)   # reject over-selection
            qty = float(line.get('qty', 1.0))
            discount = float(line.get('discount', 0.0))
            # Modifiers: sum the real price_extra of the chosen attribute values.
            ptavs = (env['product.template.attribute.value']
                     if product.product_tmpl_id.mezze_modifier_group_ids
                     else self._line_attr_values(env, product, line))
            price_extra = sum(ptavs.mapped('price_extra')) + mezze_delta
            # Client sends the BASE unit price (or none); the server adds the
            # modifier surcharge so totals can't be tampered with.
            if line.get('price_unit') is not None and allow_override:
                base_price = float(line['price_unit'])
            else:
                base_price = pricelist._get_product_price(product, qty) if pricelist else product.lst_price
            price_unit = base_price + price_extra
            if line.get('tax_ids'):
                tax_ids = AccountTax.browse([int(t) for t in line['tax_ids']])
            else:
                company_taxes = product.taxes_id.filtered_domain(AccountTax._check_company_domain(env.company))
                tax_ids = fiscal_position.map_tax(company_taxes)
            price_after = price_unit * (1 - discount / 100.0)
            if tax_ids:
                tv = tax_ids.compute_all(price_after, currency, qty, product=product, partner=partner or None)
                subtotal, subtotal_incl = tv['total_excluded'], tv['total_included']
            else:
                subtotal = subtotal_incl = price_after * qty
            base += subtotal
            incl += subtotal_incl
            vals = {
                'product_id': product.id, 'qty': qty, 'price_unit': price_unit,
                'discount': discount, 'tax_ids': [(6, 0, tax_ids.ids)],
                'price_subtotal': subtotal, 'price_subtotal_incl': subtotal_incl,
                'pack_lot_ids': self._lot_commands(product, line, qty),
            }
            _note = (line.get('note') or line.get('mod') or '').strip()
            if _note and 'customer_note' in env['pos.order.line']._fields:
                vals['customer_note'] = _note[:200]
            _seat = self._seat_number(line)
            if _seat:
                vals['mezze_seat'] = _seat
            if mezze_cmds:
                # Structured selections as rows, never a joined label.
                vals['mezze_modifier_ids'] = mezze_cmds
            if ptavs:
                vals['attribute_value_ids'] = [(6, 0, ptavs.ids)]
                vals['price_extra'] = price_extra
                vals['full_product_name'] = '%s (%s)' % (
                    product.display_name, ', '.join(ptavs.mapped('product_attribute_value_id.name')))
            order_lines.append((0, 0, vals))
        return order_lines, base, incl

    # ------------------------------------------------------------------
    # Combos / meal deals — native reuse (product.combo + pos.order.line
    # combo_parent_id/combo_item_id). A combo is a PARENT line on the combo
    # product priced 0, plus one priced CHILD line per chosen item. The child
    # prices are the native proration of the combo's list price across the
    # groups' base_price (see point_of_sale compute_combo_items.js) so the
    # customer pays exactly the combo price + item extras, and each child keeps
    # its own product/tax/BoM — so the live food-cost moat survives per-item.
    # ------------------------------------------------------------------
    def _combo_child_vals(self, env, config, partner, combo_product, chosen):
        """Native-faithful child-line values for one combo.

        ``chosen`` is ``[(product.combo.item, qty)]`` — Odoo's cardinality allows a
        group to hold more than one item (``qty_max``) of which only some are
        covered by the meal's price (``qty_free``). Returns a list of per-child
        dicts (product, qty, taxes, price_unit, subtotals, combo_item_id).

        The arithmetic is Odoo's own, from ``computeComboItems``: the parent's list
        price is prorated across the INCLUDED items by their group's ``base_price``,
        the last included child absorbs the rounding, an item taken BEYOND
        ``qty_free`` is charged the group's ``base_price``, and every child then
        adds its own ``extra_price``.
        """
        currency = config.currency_id
        pp_digits = env['decimal.precision'].precision_get('Product Price')
        parent_lst = combo_product.lst_price
        fiscal_position = (partner.property_account_position_id
                           or config.default_fiscal_position_id)
        AccountTax = env['account.tax']
        # split each pick into the part the meal price covers and the part beyond it
        included, extra, free_taken = [], [], {}
        for item, qty in ((it, int(q)) for it, q in chosen):
            gid = item.combo_id.id
            free_left = max(0, item.combo_id.qty_free - free_taken.get(gid, 0))
            n_free = min(qty, free_left)
            if n_free:
                free_taken[gid] = free_taken.get(gid, 0) + n_free
                included.append((item, n_free))
            if qty - n_free:
                extra.append((item, qty - n_free))
        original_total = sum(it.combo_id.base_price * q for it, q in included)
        if original_total <= 0:
            raise ValueError("Combo %s has no priceable groups" % combo_product.display_name)
        remaining = parent_lst
        priced = []
        for i, (item, qty) in enumerate(included):
            price_unit = float_round(item.combo_id.base_price * parent_lst / original_total,
                                     precision_digits=pp_digits)
            remaining -= price_unit * qty
            if i == len(included) - 1:               # the last child absorbs the rounding
                price_unit += remaining
            priced.append((item, qty, price_unit + item.extra_price))
        for item, qty in extra:
            price_unit = float_round(item.combo_id.base_price, precision_digits=pp_digits)
            priced.append((item, qty, price_unit + item.extra_price))

        out = []
        for item, qty, price_unit in priced:
            child = item.product_id
            taxes = child.taxes_id.filtered_domain(AccountTax._check_company_domain(env.company))
            taxes = fiscal_position.map_tax(taxes)
            if taxes:
                tv = taxes.compute_all(price_unit, currency, qty, product=child,
                                       partner=partner or None)
                sub, sub_incl = tv['total_excluded'], tv['total_included']
            else:
                sub = sub_incl = price_unit * qty
            out.append({'product': child, 'qty': qty, 'taxes': taxes,
                        'price_unit': price_unit, 'subtotal': sub,
                        'subtotal_incl': sub_incl, 'combo_item_id': item.id})
        return out

    def _resolve_combo(self, env, combo_product, cart):
        """Validate a cart's combo selection against the product's real groups.

        Enforces Odoo's own cardinality — at most ``qty_max`` and at least
        ``qty_free`` items per group (both default to 1, which is the familiar
        "choose one") — and that every picked item belongs to THIS combo, so a
        client can't smuggle a cheaper item in from another combo. Returns
        ``[(product.combo.item, qty)]`` ordered by item id.
        """
        if combo_product.type != 'combo':
            raise ValueError("Product %s is not a combo" % combo_product.display_name)
        groups = combo_product.product_tmpl_id.combo_ids
        picks = cart.get('combo') or []
        # A pick may carry an explicit qty, or the same item may simply appear more
        # than once — the shop has always sent one entry per chosen item. Both are
        # read into one map so a browser cannot smuggle a quantity past the count.
        qty_by_item = {}
        for p in picks:
            if not p.get('item_id'):
                continue
            iid = int(p['item_id'])
            qty_by_item[iid] = qty_by_item.get(iid, 0) + max(1, int(p.get('qty') or 1))
        chosen = env['product.combo.item'].browse(sorted(qty_by_item)).exists()
        if len(chosen) != len(qty_by_item):
            raise ValueError("Unknown combo item in %s" % combo_product.display_name)
        for it in chosen:
            if it.combo_id not in groups:
                raise ValueError("Item %s is not part of combo %s"
                                 % (it.product_id.display_name, combo_product.display_name))
        # Odoo's cardinality, per group: at most qty_max items, and at least
        # qty_free — the same rule its own POS confirm button applies. "Exactly one
        # per group" was only ever the default case (qty_max = qty_free = 1).
        for group in groups:
            taken = sum(qty_by_item[it.id] for it in chosen if it.combo_id == group)
            if taken > group.qty_max:
                raise ValueError("Combo %s allows at most %s item(s) from %s"
                                 % (combo_product.display_name, group.qty_max, group.name))
            if taken < group.qty_free:
                raise ValueError("Combo %s needs %s item(s) from %s"
                                 % (combo_product.display_name, group.qty_free, group.name))
        return [(env['product.combo.item'].browse(i), q)
                for i, q in sorted(qty_by_item.items())]

    def _combo_apply(self, env, config, partner, order, combo_carts):
        """ORM-create native combo parent+child lines on an existing ``order``.

        Returns ``(base, incl, kds_items)`` where ``kds_items`` is a list of
        ``(child_product, qty, note)`` tuples so the caller can route the combo's
        real dishes to the kitchen. The combo PARENT line is priced 0 (children
        carry the money); each CHILD carries its product's own taxes.
        """
        Line = env['pos.order.line']
        add_base = add_incl = 0.0
        kds_items = []
        for cart in (combo_carts or []):
            combo_product = env['product.product'].browse(int(cart['product_id']))
            if not combo_product.exists():
                raise ValueError("Unknown combo product %s" % cart.get('product_id'))
            chosen = self._resolve_combo(env, combo_product, cart)
            # a 86'd combo, or a combo whose chosen item is 86'd, can't be sold
            self._assert_available(env, config, combo_product)
            for _item, _qty in chosen:
                self._assert_available(env, config, _item.product_id)
            child_vals = self._combo_child_vals(env, config, partner, combo_product, chosen)
            parent = Line.create({
                'order_id': order.id, 'product_id': combo_product.id, 'qty': 1,
                'price_unit': 0.0, 'discount': 0.0, 'tax_ids': [(6, 0, [])],
                'price_subtotal': 0.0, 'price_subtotal_incl': 0.0, 'pack_lot_ids': [],
            })
            for cv in child_vals:
                Line.create({
                    'order_id': order.id, 'product_id': cv['product'].id,
                    'qty': cv['qty'],
                    'price_unit': cv['price_unit'], 'discount': 0.0,
                    'tax_ids': [(6, 0, cv['taxes'].ids)],
                    'price_subtotal': cv['subtotal'], 'price_subtotal_incl': cv['subtotal_incl'],
                    'combo_parent_id': parent.id, 'combo_item_id': cv['combo_item_id'],
                    'pack_lot_ids': [],
                })
                add_base += cv['subtotal']
                add_incl += cv['subtotal_incl']
                kds_items.append((cv['product'], float(cv['qty']),
                                  combo_product.display_name))
        return add_base, add_incl, kds_items

    # ------------------------------------------------------------------
    # Half-and-half — one base, two halves, each priced/cost-tracked
    # ------------------------------------------------------------------
    # Modelled like a combo: the PARENT line (the half-&-half base) carries the
    # charged price + tax; two CHILD "half" lines carry qty 0.5 of the real pizza
    # products at price 0, so each half books HALF its BoM food cost — the moat
    # holds even on a split pizza. The kitchen sees ONE ticket "½ A / ½ B".
    def _halfhalf_price(self, env, a, b):
        """Charge for a split pizza. 'max' (default) = the pricier half sets the
        price; 'avg' = mean of the two. Per-branch via mezze_bridge.halfhalf_pricing."""
        rule = (env['ir.config_parameter'].sudo().get_param(
            'mezze_bridge.halfhalf_pricing', 'max') or 'max').strip().lower()
        pa, pb = a.lst_price, b.lst_price
        if rule == 'avg':
            return round((pa + pb) / 2.0, 2)
        return max(pa, pb)

    def _halfhalf_apply(self, env, config, partner, order, half_carts):
        """ORM-create the parent + two half child lines on ``order``. Returns
        ``(base, incl, kds_items)``; the KDS gets one labelled pizza per split."""
        Line = env['pos.order.line']
        currency = config.currency_id
        fp = (partner.property_account_position_id or config.default_fiscal_position_id)
        AccountTax = env['account.tax']
        add_base = add_incl = 0.0
        kds_items = []
        for cart in (half_carts or []):
            base_product = env['product.product'].browse(int(cart['product_id']))
            if not base_product.exists():
                raise ValueError("Unknown half-&-half base %s" % cart.get('product_id'))
            hids = [int(h) for h in (cart.get('halves') or [])]
            if len(hids) != 2:
                raise ValueError("Half-&-half needs exactly two halves")
            a = env['product.product'].browse(hids[0])
            b = env['product.product'].browse(hids[1])
            if not (a.exists() and b.exists()):
                raise ValueError("Unknown half product")
            self._assert_available(env, config, base_product)
            self._assert_available(env, config, a | b)
            price = self._halfhalf_price(env, a, b)
            taxes = (base_product.taxes_id or a.taxes_id).filtered_domain(
                AccountTax._check_company_domain(env.company))
            taxes = fp.map_tax(taxes)
            if taxes:
                tv = taxes.compute_all(price, currency, 1, product=base_product,
                                       partner=partner or None)
                sub, sub_incl = tv['total_excluded'], tv['total_included']
            else:
                sub = sub_incl = price
            name = '½ %s / ½ %s' % (a.display_name, b.display_name)
            parent = Line.create({
                'order_id': order.id, 'product_id': base_product.id, 'qty': 1,
                'price_unit': price, 'discount': 0.0, 'tax_ids': [(6, 0, taxes.ids)],
                'price_subtotal': sub, 'price_subtotal_incl': sub_incl,
                'pack_lot_ids': [], 'full_product_name': name,
            })
            for half in (a, b):
                Line.create({
                    'order_id': order.id, 'product_id': half.id, 'qty': 0.5,
                    'price_unit': 0.0, 'discount': 0.0, 'tax_ids': [(6, 0, [])],
                    'price_subtotal': 0.0, 'price_subtotal_incl': 0.0,
                    'combo_parent_id': parent.id, 'pack_lot_ids': [],
                })
            add_base += sub
            add_incl += sub_incl
            kds_items.append((base_product, 1.0, name))
        return add_base, add_incl, kds_items

    @staticmethod
    def _split_combos(env, lines):
        """Partition a cart into (plain_lines, combo_carts, half_carts). A cart
        line is a COMBO when its product is ``type=='combo'`` (or it carries a
        ``combo`` selection); a HALF-AND-HALF when it carries a ``halves`` list
        of two products. Both build parent+child lines after the order exists."""
        plain, combos, halves = [], [], []
        for line in (lines or []):
            product = env['product.product'].browse(int(line['product_id']))
            if line.get('halves'):
                halves.append(line)
            elif line.get('combo') or product.type == 'combo':
                combos.append(line)
            else:
                plain.append(line)
        return plain, combos, halves

    def _station_of(self, product):
        """Route a product to a prep station.

        The RULE lives in ``domain/station_routing`` because the outbox print
        consumer needs the same answer: a copy in each place is a rule that
        disagrees with itself the first time somebody adds a keyword to one of them.
        """
        cats = (product.pos_categ_ids.mapped('name')
                if 'pos_categ_ids' in product._fields else ())
        return station_routing.station_for(product.display_name, cats)

    # Stations a customer physically waits at / picks up from — the beverage
    # queue (BDS / coffee shop) is exactly these.
    _BEVERAGE_STATIONS = station_routing.BEVERAGE_STATIONS

    def _make_station_tickets(self, env, order, items, fire_uuid, course, server_override=None):
        """Create one ``mezze.kds.ticket`` per station from ``items`` — a list of
        ``(product, qty, note)`` tuples. Shared by table fire (/orders/fire),
        café counter sync (/orders/sync) and customer QR order (/qr/order) so all
        feed the same KDS/BDS boards. ``server_override`` labels the ticket's
        origin (e.g. a QR self-order). Returns the created tickets (caller
        broadcasts)."""
        Ticket = env['mezze.kds.ticket']
        table_label = None
        if 'table_id' in order._fields and order.table_id:
            tbl = order.table_id
            table_label = 'T%s' % (tbl.table_number if 'table_number' in tbl._fields else tbl.id)
        server_name = server_override or (order.user_id.name if order.user_id else None)
        guest_n = order.customer_count if 'customer_count' in order._fields else 0
        by_station = {}
        for (p, qty, note) in items:
            if qty <= 0:
                continue
            by_station.setdefault(self._station_of(p), []).append((p, qty, note))
        tickets = Ticket.browse()
        for st, its in by_station.items():
            tickets |= Ticket.create({
                'pos_order_id': order.id, 'station': st, 'state': 'fired',
                'fire_uuid': fire_uuid, 'table_label': table_label,
                'server_name': server_name, 'guests': guest_n, 'course': course,
                'line_ids': [(0, 0, {'product_id': p.id, 'name': p.display_name,
                                     'qty': q, 'note': n}) for (p, q, n) in its],
            })
        return tickets

    # Advisory-lock namespace so our keys never collide with other apps'.
    _FIRE_LOCK_NS = 27749
    _REFUND_LOCK_NS = 27750   # advisory-lock namespace for per-original refund serialization

    def _unfired_lines(self, order):
        """The order's lines that have NOT yet been sent to the kitchen.

        ``mezze_fired`` is a cumulative ``{product_id: qty}`` snapshot of the order
        as it stood at the last fire, so the difference against the CURRENT lines is
        exactly what a re-fire owes the kitchen.

        This exists because the standalone cashier holds the whole cart client-side
        and persists it before every action. It cannot send "the items being added
        now" the way /orders/fire's append contract expects — it does not know which
        ones the server already has. It used to send the whole cart anyway, on top of
        a draft that already held the whole cart, and ``_do_fire`` appended it: the
        first Fire doubled the order's lines and its total.

        Reading the delta off the order removes the guesswork. The waiter and QR
        paths are untouched — they still append what they send.

        Returns ``[(line, qty_to_fire)]``.
        """
        try:
            budget = {str(k): float(v)
                      for k, v in json.loads(order.mezze_fired or '{}').items()}
        except (ValueError, TypeError):
            budget = {}
        out = []
        for line in order.lines.sorted(key=lambda l: l.id):
            if line.qty <= 0:
                continue
            # A combo PARENT is a priced-0 section; its child dishes are the food, and
            # they are lines in their own right, so the parent never goes to a station.
            if line.combo_line_ids:
                continue
            # A reward is a markdown, not something anybody cooks.
            if 'is_reward_line' in line._fields and line.is_reward_line:
                continue
            key = str(line.product_id.id)
            already = budget.get(key, 0.0)
            take = min(already, line.qty)
            budget[key] = already - take
            remaining = line.qty - take
            if remaining > 0:
                out.append((line, remaining))
        return out

    def _fire_order_delta(self, env, order, fire_uuid, server_override=None):
        """Fire everything on ``order`` that the kitchen has not seen yet.

        The lines already exist — they were written by /orders/sync — so nothing is
        built, priced or grafted here. That is the whole point: pricing happened once,
        on the sync, and firing must not re-do it.
        """
        Ticket = env['mezze.kds.ticket']
        pending = self._unfired_lines(order)
        if not pending:
            return {'ok': True, 'nothing_to_fire': True, 'order_id': order.id,
                    'pos_reference': order.pos_reference, 'state': order.state,
                    'amount_total': order.amount_total, 'fire_uuid': fire_uuid,
                    'fired_now': [], 'tickets': []}
        course = len(set(Ticket.search(
            [('pos_order_id', '=', order.id)]).mapped('fire_uuid'))) + 1
        items, fired_now = [], []
        for line, qty in pending:
            note = line.customer_note or '' if 'customer_note' in line._fields else ''
            attrs = ', '.join(line.attribute_value_ids.mapped(
                'product_attribute_value_id.name'))
            full = ' · '.join([p for p in (attrs, note) if p])
            product = line.product_id
            items.append((product, qty, full))
            fired_now.append({'product_id': product.id, 'name': product.display_name,
                              'qty': qty, 'station': self._station_of(product),
                              'note': full})
        tickets = self._make_station_tickets(env, order, items, fire_uuid, course,
                                             server_override=server_override)
        self._publish_kds(env, tickets, order, natural_key=fire_uuid)
        self._publish_fire_hardware(env, order, tickets)
        # Against the PREVIOUS snapshot, before it is overwritten below.
        self._mark_edits_against_fired(env, order)
        current = {}
        for l in order.lines:
            if l.qty > 0:
                current[str(l.product_id.id)] = current.get(str(l.product_id.id), 0.0) + l.qty
        order.sudo().write({'mezze_fired': json.dumps(current)})
        return {'ok': True, 'order_id': order.id, 'pos_reference': order.pos_reference,
                'tracking': order.tracking_number or order.pos_reference,
                'state': order.state, 'amount_total': order.amount_total,
                'table_id': order.table_id.id if order.table_id else None,
                'course': course, 'fire_uuid': fire_uuid, 'fired_now': fired_now,
                'tickets': [t._payload() for t in tickets]}

    def _do_fire(self, env, uuid, session, config, table_id, lines,
                 partner_id, guests, fire_uuid, server_override=None, defer_fire=False):
        """Concurrency-safe append-fire CORE, shared by the waiter (/orders/fire)
        and customer QR (/qr/order) paths. Advisory-lock on the table → idempotent
        (by fire_uuid) → find-or-create the table's single open draft → APPEND the
        new items → one KDS ticket per station → broadcast. Caller must have set
        the company context on ``env``. Returns the result dict.

        ``defer_fire`` (S2C-5): build/append the draft order WITHOUT firing the
        kitchen — used by the online-payment (pay-before-fire) path, which fires
        exactly once on authoritative payment success."""
        Order = env['pos.order']
        Ticket = env['mezze.kds.ticket']

        # ---- serialize concurrent fires to the same table / order ----
        if table_id:
            lock_key = int(table_id)
        else:
            lock_key = int(hashlib.sha1(uuid.encode()).hexdigest(), 16) % (2 ** 31)
        env.cr.execute("SELECT pg_advisory_xact_lock(%s, %s)", (self._FIRE_LOCK_NS, lock_key))

        # ---- idempotency: has this exact fire already been processed? ----
        done = Ticket.search([('fire_uuid', '=', fire_uuid)])
        if done:
            order = done[0].pos_order_id
            return {
                'ok': True, 'idempotent': True, 'order_id': order.id,
                'pos_reference': order.pos_reference, 'state': order.state,
                'tracking': order.tracking_number or order.pos_reference,
                'amount_total': order.amount_total,
                'table_id': order.table_id.id if order.table_id else None,
                'fire_uuid': fire_uuid,
                'tickets': [t._payload() for t in done],
                'fired_now': [i for t in done for i in
                              [{'product_id': l.product_id.id, 'name': l.name,
                                'qty': l.qty, 'station': t.station} for l in t.line_ids]],
            }

        partner = env['res.partner'].browse(int(partner_id)) if partner_id else env['res.partner']
        # Combos + half-&-half become parent/child lines grafted on after the
        # order exists; keep them out of the flat plain-line build.
        plain_lines, combo_carts, half_carts = self._split_combos(env, lines)
        # Same rule on the fire path the lane uses: refuse before writing, so a bad
        # selection never leaves a half-made order or a kitchen ticket behind.
        for cart in (combo_carts or []):
            self._resolve_combo(env, env['product.product'].browse(
                int(cart['product_id'])), cart)
        order_lines, base, incl = self._build_lines(env, config, partner, plain_lines)

        # ---- find the table's open draft (append target), else create ----
        order = Order.browse()
        if table_id and 'table_id' in Order._fields:
            order = Order.search([('table_id', '=', int(table_id)),
                                  ('state', '=', 'draft'),
                                  ('session_id', '=', session.id)], limit=1)
        if not order:
            order = Order.search([('uuid', '=', uuid), ('state', '=', 'draft')], limit=1)
        already = Order.search([('uuid', '=', uuid)], limit=1)
        # FSM authority: fire is legal only from an open lifecycle. In 'enforce'
        # this rejects before any ticket/broadcast side effect; in 'observe' it
        # records the attempt and the legacy raise below still governs behaviour.
        blocked = self._fsm_guard(env, already, 'fire', endpoint='_do_fire')
        if blocked:
            return blocked
        if already and already.state != 'draft':
            raise ValueError("Order %s is already %s — cannot re-fire"
                             % (already.pos_reference, already.state))

        if order:
            # APPEND the new items to the existing draft, then recompute the
            # totals across ALL lines (old + new) so nothing is clobbered.
            vals = {'lines': order_lines, 'amount_paid': 0.0}
            if guests and 'customer_count' in order._fields:
                vals['customer_count'] = int(guests)
            if partner.id:
                vals['partner_id'] = partner.id
            order.write(vals)
            tot_base = sum(order.lines.mapped('price_subtotal'))
            tot_incl = sum(order.lines.mapped('price_subtotal_incl'))
            order.write({'amount_tax': tot_incl - tot_base, 'amount_total': tot_incl})
        else:
            order_dict = {
                'uuid': uuid, 'session_id': session.id, 'company_id': config.company_id.id,
                'user_id': env.uid, 'partner_id': partner.id or False,
                'pricelist_id': config.pricelist_id.id or False,
                'name': 'Mezze %s' % uuid,
                'date_order': fields.Datetime.to_string(fields.Datetime.now()),
                'lines': order_lines, 'payment_ids': [],
                'amount_tax': incl - base, 'amount_total': incl,
                'amount_paid': 0.0, 'amount_return': 0.0,
                'last_order_preparation_change': empty_preparation_change(), 'to_invoice': False,
                'state': 'draft',                   # <- keeps it unpaid/open
            }
            if table_id and 'table_id' in Order._fields:
                order_dict['table_id'] = int(table_id)
            if guests and 'customer_count' in Order._fields:
                order_dict['customer_count'] = int(guests)
            Order.sync_from_ui([order_dict])
            order = Order.search([('uuid', '=', uuid)], limit=1)

        # ---- graft combo + half-&-half parent/child lines, then re-total ----
        combo_kds = []
        if combo_carts:
            _cb, _ci, combo_kds = self._combo_apply(env, config, partner, order, combo_carts)
        if half_carts:
            _hb, _hi, half_kds = self._halfhalf_apply(env, config, partner, order, half_carts)
            combo_kds += half_kds
        if combo_carts or half_carts:
            tot_base = sum(order.lines.mapped('price_subtotal'))
            tot_incl = sum(order.lines.mapped('price_subtotal_incl'))
            order.write({'amount_tax': tot_incl - tot_base, 'amount_total': tot_incl})

        # ---- create one KDS ticket per station from the NEW items ----
        # (the combo parent line is a priced-0 section, so its real child dishes
        # are routed via combo_kds rather than the parent product.)
        course = len(set(Ticket.search([('pos_order_id', '=', order.id)]).mapped('fire_uuid'))) + 1
        items, fired_now = [], []
        for line in plain_lines:
            p = env['product.product'].browse(int(line['product_id']))
            qty = float(line.get('qty', 1.0))
            note = self._line_note(env, p, line)
            items.append((p, qty, note))
            fired_now.append({'product_id': p.id, 'name': p.display_name,
                              'qty': qty, 'station': self._station_of(p), 'note': note})
        for cp, cq, cnote in combo_kds:
            items.append((cp, cq, cnote))
            fired_now.append({'product_id': cp.id, 'name': cp.display_name,
                              'qty': cq, 'station': self._station_of(cp), 'note': cnote})
        if defer_fire:
            # Online payment (pay-before-fire): mark the order online and DO NOT
            # fire the kitchen now — the paid-online hook fires it exactly once.
            order.sudo().write({'mezze_online': True})
            tickets = Ticket.browse()
        else:
            tickets = self._make_station_tickets(env, order, items, fire_uuid, course,
                                                 server_override=server_override)
            self._publish_kds(env, tickets, order, natural_key=fire_uuid)
            self._publish_fire_hardware(env, order, tickets)

        # Against the PREVIOUS snapshot, before it is overwritten below.
        self._mark_edits_against_fired(env, order)
        # keep the cumulative fired snapshot fresh for /orders/get resume
        current = {}
        for l in order.lines:
            if l.qty > 0:
                current[str(l.product_id.id)] = current.get(str(l.product_id.id), 0.0) + l.qty
        order.sudo().write({'mezze_fired': json.dumps(current)})

        return {
            'ok': True, 'order_id': order.id, 'pos_reference': order.pos_reference,
            'tracking': order.tracking_number or order.pos_reference,
            'state': order.state, 'amount_total': order.amount_total,
            'table_id': order.table_id.id if order.table_id else None,
            'course': course, 'fire_uuid': fire_uuid,
            'fired_now': fired_now,
            'tickets': [t._payload() for t in tickets],
        }

    @http.route(f'{API_PREFIX}/orders/fire', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*', readonly=False)
    def order_fire(self, uuid=None, session_id=None, table_id=None, lines=None,
                   partner_id=None, guests=None, fire_uuid=None, reconcile=None, **kw):
        """Fire a course to the kitchen.

        Two callers, two honest semantics:

        * **APPEND** (default) — ``lines`` is the set of items being added *now*,
          not the whole cart, so two waiters firing to the same table both add their
          items instead of clobbering each other. This is the waiter and QR path.

        * **RECONCILE** (``reconcile=True``) — the caller holds the whole cart and
          has already persisted it through /orders/sync, so it cannot say which items
          are new. The server works that out from ``mezze_fired`` and fires only the
          difference. This is the standalone cashier, which used to send the whole
          cart into the APPEND path on top of a draft that already held it — and so
          doubled the order's lines and its total on the first Fire.
        """
        auth = self._authorize()
        if auth:
            return auth
        if not uuid:
            return self._json({'ok': False, 'error': 'missing_uuid'}, status=400)
        reconcile = str(reconcile).lower() in ('1', 'true', 'yes') if reconcile is not None else False
        if not lines and not reconcile:
            return self._json({'ok': False, 'error': 'no_lines'}, status=400)
        env = self._api_env()
        # P4 canonical security gate on the waiter fire route: authn + orders.fire
        # capability (flag-gated, observe default). The shared _do_fire core is NOT
        # gated because it also serves the public qr/order path.
        denied = self._security_gate(env, 'orders/fire')
        if denied:
            return denied
        if not fire_uuid:
            sig = hashlib.sha1(json.dumps(lines or [], sort_keys=True).encode()).hexdigest()[:12]
            fire_uuid = '%s:%s' % (uuid, sig)
        log = env['mezze.sync.log'].sudo().create({'name': 'Fire %s' % uuid, 'uuid': uuid, 'status': 'received'})
        try:
            session = env['pos.session'].browse(int(session_id))
            if not session.exists():
                raise ValueError("Unknown session_id %s" % session_id)
            config = session.config_id
            env = env(context=dict(env.context, allowed_company_ids=[config.company_id.id], company_id=config.company_id.id))
            session = session.with_env(env)
            config = config.with_env(env)
            if reconcile:
                order = env['pos.order'].search(
                    [('uuid', '=', uuid), ('state', '=', 'draft'),
                     ('session_id', '=', session.id)], limit=1)
                if not order and table_id:
                    order = env['pos.order'].search(
                        [('table_id', '=', int(table_id)), ('state', '=', 'draft'),
                         ('session_id', '=', session.id)], limit=1)
                if not order:
                    # Nothing persisted yet — there is no cart on the server to
                    # reconcile against, so this is an ordinary first fire.
                    result = self._do_fire(env, uuid, session, config, table_id, lines,
                                           partner_id, guests, fire_uuid)
                else:
                    denied2 = self._security_gate(env, 'orders/fire', target_order=order)
                    if denied2:
                        return denied2
                    blocked = self._fsm_guard(env, order, 'fire', endpoint='orders/fire')
                    if blocked:
                        return blocked
                    # Same table lock the append path takes, so a waiter appending and
                    # a till reconciling cannot interleave on one table.
                    env.cr.execute("SELECT pg_advisory_xact_lock(%s, %s)",
                                   (self._FIRE_LOCK_NS,
                                    int(table_id) if table_id else
                                    int(hashlib.sha1(uuid.encode()).hexdigest(), 16) % (2 ** 31)))
                    if env['mezze.kds.ticket'].search([('fire_uuid', '=', fire_uuid)]):
                        result = {'ok': True, 'idempotent': True, 'order_id': order.id,
                                  'pos_reference': order.pos_reference, 'state': order.state,
                                  'amount_total': order.amount_total, 'fire_uuid': fire_uuid,
                                  'fired_now': [], 'tickets': []}
                    else:
                        result = self._fire_order_delta(env, order, fire_uuid)
            else:
                result = self._do_fire(env, uuid, session, config, table_id, lines,
                                       partner_id, guests, fire_uuid)
            log.write({'status': 'ok', 'pos_order_id': result.get('order_id'),
                       'session_id': session.id,
                       'message': 'idempotent replay' if result.get('idempotent')
                                  else 'Fired course %s (%d tickets)' % (result.get('course'), len(result.get('tickets', [])))})
            return result
        except Exception as exc:  # noqa: BLE001
            # Let PG concurrency errors bubble up so Odoo re-runs the whole fire
            # on a fresh snapshot (the advisory lock already serialized us; this
            # just handles the stale REPEATABLE-READ snapshot on the loser).
            _reraise_if_retryable(exc)
            _logger.exception("Mezze fire failed for uuid=%s", uuid)
            try:
                log.write({'status': 'error', 'message': str(exc)})
            except Exception:  # noqa: BLE001
                pass
            return self._json({'ok': False, 'error': 'fire_failed', 'uuid': uuid, 'message': str(exc)}, status=400)

    def _dup_context(self, payments):
        """Masked, PII-safe context for a duplicate-reference modal — method, device,
        masked reference, amount, time. No PAN/secrets, no customer data."""
        def _mask(ref):
            ref = (ref or '').strip()
            if len(ref) <= 4:
                return ref
            return '••••' + (ref[-4:] if len(ref) < 10 else ref[-6:])
        return [{
            'method': p.payment_method_id.name,
            'device': p.mezze_device_id.name or '',
            'ref_masked': _mask(p.payment_ref_no),
            'amount': round(p.amount, 2),
            'time': fields.Datetime.to_string(p.create_date) if p.create_date else '',
        } for p in payments[:5]]

    def _credit_ctx(self, pos, policy):
        """PII-safe credit context for the cashier dialog (the cashier already
        selected this customer). Amounts only — no ledger/invoices/addresses."""
        return {'name': pos['name'], 'exposure': pos['exposure'], 'limit': pos['limit'],
                'projected': pos['projected'], 'over': pos['over'],
                'currency': pos['currency'], 'decimals': pos['decimals'], 'policy': policy}

    def _cash_rounding_for(self, config, payment_method):
        """The rounding rule that applies to THIS tender, or False.

        ``only_round_cash_method`` is why this is per-tender rather than per-order: a
        shop rounds because a coin does not exist, so the rule belongs to the cash
        being handed over and not to the bill. Rounding a card payment would invent a
        few piastres of difference the acquirer will not agree with.
        """
        rule = getattr(config, 'rounding_method', False)
        if not rule:
            return False
        if getattr(config, 'only_round_cash_method', False):
            if not (payment_method and payment_method.is_cash_count):
                return False
        return rule

    def _mezze_credit_gate(self, env, pm, order, config, tender, manager, mgr_auth_error, allow_credit):
        """S2C-6 credit governance for a Customer Account (pay_later) tender. Returns
        None to proceed, else a ready-to-return rejection. Concurrency-safe: locks the
        commercial partner and re-reads exposure inside the transaction so two
        registers cannot both pass on the same stale available credit."""
        if pm.mezze_mode != 'customer_account':
            return None
        partner = order.partner_id
        if not partner:
            # Customer Account must never work anonymously (§5)
            return self._json({'ok': False, 'error': 'customer_required',
                               'message': 'Select a customer for a Customer Account payment.'}, status=400)
        commercial = partner.commercial_partner_id
        # durable per-customer lock → serialise concurrent credit sales
        env.cr.execute("SELECT id FROM res_partner WHERE id=%s FOR UPDATE", (commercial.id,))
        pos = partner._mezze_credit_position(config.company_id, config, extra=tender)
        policy = pm.mezze_credit_policy or 'odoo_warning'
        if not pos['limit_active'] or pos['over'] <= 0:
            return None                                   # within limit / no limit set

        def _audit(event, extra=None):
            try:
                env['mezze.audit.log'].sudo().log(
                    event, severity='warning', res_model='pos.order', res_id=order.id,
                    res_uuid=order.uuid or False,
                    cashier_id=manager.id if (manager and extra == 'approved') else False,
                    detail=json.dumps(dict({'customer': commercial.id, 'name': commercial.name,
                                            'exposure': pos['exposure'], 'limit': pos['limit'],
                                            'amount': tender, 'projected': pos['projected'],
                                            'over': pos['over'], 'policy': policy}, **(extra or {}))))
            except Exception:  # noqa: BLE001
                pass

        if policy == 'hard_block':
            _audit('customer_credit.blocked')
            return self._json({'ok': False, 'error': 'credit_blocked',
                               'credit': self._credit_ctx(pos, policy)}, status=403)
        if policy == 'manager_approval':
            if manager:
                _audit('customer_credit.approved', {'approver_id': manager.id,
                                                    'approver': manager.name, 'role': manager.role})
                return None
            if mgr_auth_error:
                return self._json({'ok': False, 'error': mgr_auth_error,
                                   'credit': self._credit_ctx(pos, policy)}, status=403)
            return self._json({'ok': False, 'error': 'credit_needs_manager',
                               'credit': self._credit_ctx(pos, policy)}, status=409)
        # odoo_warning: warn, allow on explicit continue
        if allow_credit:
            _audit('customer_credit.warn_continue')
            return None
        return self._json({'ok': False, 'error': 'credit_warn',
                           'credit': self._credit_ctx(pos, policy)}, status=409)

    @http.route(f'{API_PREFIX}/orders/pay', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*', readonly=False)
    def order_pay(self, uuid=None, order_id=None, payment_method_id=None,
                  partner_id=None, discount=None, discount_product_id=None,
                  device_id=None, payment_ref=None, approval_code=None,
                  allow_duplicate=False, amount=None, tender_key=None,
                  manager_code=None, manager_pin=None, manager_reason=None,
                  allow_credit=False, gift_card_code=None, use_ewallet=False, **kw):
        """Record ONE tender against an order. Supports partial + mixed tender:
        the order is finalised (action_pos_order_paid) only when the remaining
        balance reaches zero; partial tenders leave it open/draft. Enforces the S2
        device/reference/duplicate policy BEFORE any pos.payment is created, and is
        idempotent per client-minted ``tender_key`` (safe double-click / retry)."""
        auth = self._authorize()
        if auth:
            return auth
        env = self._api_env()
        try:
            order = (env['pos.order'].search([('uuid', '=', uuid)], limit=1)
                     if uuid else env['pos.order'].browse(int(order_id)))
            if not order.exists():
                raise ValueError("Unknown order")
            denied = self._security_gate(env, 'orders/pay', target_order=order)
            if denied:
                return denied
            # Per-tender idempotency: a retried Confirm (double-click / network) with
            # the same tender_key must not create a second pos.payment.
            if tender_key:
                seen = order.payment_ids.filtered(lambda p: p.mezze_tender_key == str(tender_key))
                if seen:
                    paid = round(order.amount_paid, 2)
                    return {'ok': True, 'idempotent': True, 'order_id': order.id,
                            'pos_reference': order.pos_reference, 'state': order.state,
                            'amount_total': round(order.amount_total, 2), 'amount_paid': paid,
                            'remaining': round(order.amount_total - paid, 2)}
            blocked = self._fsm_guard(env, order, 'pay', endpoint='orders/pay')
            if blocked:
                return blocked
            if order.state != 'draft':
                return {'ok': True, 'already': True, 'order_id': order.id,
                        'pos_reference': order.pos_reference, 'state': order.state,
                        'amount_total': round(order.amount_total, 2),
                        'amount_paid': round(order.amount_paid, 2), 'remaining': 0.0}
            config = order.config_id
            env = env(context=dict(env.context, allowed_company_ids=[config.company_id.id], company_id=config.company_id.id))
            order = order.with_env(env)
            # "Charge is disabled until resolved" — the design blocks settlement
            # on a check another terminal has moved. Refusing here matters more
            # than anywhere else: paying a stale check settles a total the guest
            # was never shown.
            stale = self._assert_revision(order, kw.get('expected_revision'))
            if stale:
                return stale
            if partner_id and not order.partner_id:
                order.partner_id = int(partner_id)
            # loyalty redemption: append a tax-consistent discount line, refresh totals
            #
            # AUTHORITY. This path used to accept any ``discount`` + any
            # ``discount_product_id`` and write ``price_unit = -discount`` with no
            # check that a loyalty.reward existed, that a card had been debited, or
            # that /loyalty/redeem had ever been called. Because /orders/pay needs
            # only ORDERS_PAY — which a cashier and a bare terminal both hold — while
            # /loyalty/redeem needs LOYALTY_ADJUST and /promo/apply needs
            # ORDERS_DISCOUNT (both supervisor-and-above), the money route was a way
            # around the two gates that exist to bound markdowns.
            #
            # It is now held to the SAME tiered ceiling as /orders/discount. The
            # ceiling is a percentage and this path carries an amount, so the amount
            # is expressed as a share of the pre-discount total before it is judged.
            if discount and discount_product_id:
                d = float(discount)
                _base = order.amount_total or 0.0
                _pct = (d / _base * 100.0) if _base > 0 else 100.0
                _role = self._acting_role(env)
                _ceiling = self._discount_ceiling(env, _role)
                _has_cap = (authz.ORDERS_DISCOUNT in authz.capabilities_for(_role)) if _role else False
                _verdict, _detail = discount_policy.evaluate(
                    _role, _pct, ceiling=_ceiling, has_capability=_has_cap)
                if _verdict == discount_policy.NEEDS_APPROVAL:
                    _appr, _unused = self._verify_inline_approver(
                        env, kw.get('manager_code'), kw.get('manager_pin'),
                        min_rank=discount_policy.APPROVER_MIN_RANK)
                    if _appr and authz.ORDERS_DISCOUNT in authz.capabilities_for(_appr.role):
                        _verdict = discount_policy.ALLOWED
                if _verdict != discount_policy.ALLOWED:
                    self._audit(env, 'discount.override', order, severity='warning',
                                **self._actor(env, kw),
                                detail=json.dumps({'refused': _verdict, 'via': 'orders/pay',
                                                   'role': _role, 'amount': d, **_detail},
                                                  default=str))
                    return self._json(
                        {'ok': False, 'error': 'approval_required',
                         'message': 'That discount is above this role\'s limit.',
                         **_detail}, status=403)
                dp = env['product.product'].browse(int(discount_product_id))
                dtax = dp.taxes_id
                tv = dtax.compute_all(-d, config.currency_id, 1, product=dp) if dtax else None
                order.write({'lines': [(0, 0, {
                    'product_id': dp.id, 'qty': 1, 'price_unit': -d,
                    'price_subtotal': tv['total_excluded'] if tv else -d,
                    'price_subtotal_incl': tv['total_included'] if tv else -d,
                    'tax_ids': [(6, 0, dtax.ids)], 'pack_lot_ids': []})]})
                tot_base = sum(order.lines.mapped('price_subtotal'))
                tot_incl = sum(order.lines.mapped('price_subtotal_incl'))
                order.write({'amount_tax': tot_incl - tot_base, 'amount_total': tot_incl})
            # A gift-card tender is resolved BEFORE the device/duplicate policy runs,
            # so those checks see the method the payment is actually recorded on. The
            # card's BALANCE is deliberately not touched here — see the spend below.
            gift = None
            if gift_card_code:
                gift = self._giftcard_by_code(env, gift_card_code)
                if not gift:
                    return self._json({'ok': False, 'error': 'giftcard_not_found',
                                       'message': 'No gift card with that code.'},
                                      status=404)
                if gift.expiration_date and gift.expiration_date < fields.Date.today():
                    return self._json({'ok': False, 'error': 'giftcard_expired',
                                       'message': 'That gift card has expired.'},
                                      status=400)
            # An eWallet is the same prepaid instrument as a gift card, found by WHO
            # the guest is instead of by what they are holding. It therefore needs a
            # customer on the order — an anonymous wallet is a balance nobody can
            # claim — and, like the card, nothing is deducted until settlement.
            wallet = None
            if use_ewallet:
                partner = order.partner_id or (
                    env['res.partner'].sudo().browse(int(partner_id))
                    if partner_id else env['res.partner'])
                if not partner:
                    return self._json(
                        {'ok': False, 'error': 'customer_required',
                         'message': 'Attach a customer to pay from a wallet.'},
                        status=400)
                wallet = self._ewallet_card(env, partner)
                if not wallet:
                    return self._json(
                        {'ok': False, 'error': 'ewallet_missing',
                         'message': 'This customer has no wallet.'}, status=404)
            pm = (self._giftcard_pm(env, config) if gift
                  else self._ewallet_pm(env, config) if wallet
                  else (env['pos.payment.method'].browse(int(payment_method_id))
                        if payment_method_id else config.payment_method_ids[:1]))
            device = env['mezze.payment.device'].browse(int(device_id)) if device_id else None
            # Manager approval for a duplicate: verify a supervisor/manager PIN
            # inline — the SAME mezze.cashier PIN + role-rank model as /w1/approve —
            # on the terminal's own ORDERS_PAY channel. A cashier PIN can NEVER
            # authorize (role rank < manager), so this is not self-approvable.
            manager = None
            mgr_auth_error = None
            if manager_code and manager_pin:
                role_rank = {'cashier': 0, 'supervisor': 1, 'manager': 2}
                c = env['mezze.cashier'].sudo().search(
                    [('code', '=', manager_code), ('active', '=', True)], limit=1)
                if not c or not c.check_pin(manager_pin):
                    mgr_auth_error = 'bad_credentials'
                elif role_rank.get(c.role, 0) < 2:
                    mgr_auth_error = 'insufficient_role'
                else:
                    manager = c
            allow_dup = bool(allow_duplicate) or bool(manager)
            # S2 policy: device / reference / duplicate — BEFORE any financial effect.
            try:
                pol = pm.with_context(mezze_branch_id=config.id).mezze_validate_payment(
                    device=device, reference=payment_ref, allow_duplicate=allow_dup)
            except UserError as pe:
                # required-device / required-reference / BLOCK duplicate
                return self._json({'ok': False, 'error': 'payment_rejected',
                                   'message': str(pe)}, status=400)
            if pol['needs_manager'] and not manager:
                # Manager creds supplied but invalid → surface why (cashier PIN /
                # wrong PIN); otherwise ask the UI to collect a manager approval.
                if mgr_auth_error:
                    return self._json({'ok': False, 'error': mgr_auth_error,
                                       'duplicate': self._dup_context(pol['duplicates'])}, status=403)
                return self._json({'ok': False, 'error': 'duplicate_reference_needs_manager',
                                   'duplicate': self._dup_context(pol['duplicates'])}, status=409)
            if pol['duplicates'] and pm.duplicate_policy == 'warn' and not allow_dup:
                return self._json({'ok': False, 'error': 'duplicate_reference_warn',
                                   'duplicate': self._dup_context(pol['duplicates'])}, status=409)
            # Tender amount: default to the full remaining balance (single-tender
            # full pay). A smaller amount is a partial tender; overpay is rejected.
            prec = config.currency_id.decimal_places or 2
            eps = 1.0 / (10 ** prec)
            already = round(sum(order.payment_ids.mapped('amount')), prec)
            remaining = round(order.amount_total - already, prec)
            # CASH ROUNDING. ``account.cash.rounding`` had zero occurrences in Mezze,
            # so a country whose smallest coin is larger than its smallest currency
            # unit — most of them — could not be settled: the till asked for an amount
            # the drawer physically cannot make, and the cashier rounded it in their
            # head with nothing recording that they had.
            rounding = self._cash_rounding_for(config, pm)
            if rounding and remaining > 0:
                rounded = rounding.round(remaining)
                if abs(rounded - remaining) > eps / 2:
                    remaining = round(rounded, prec)
            tender = round(float(amount), prec) if amount is not None else remaining
            if tender <= 0:
                return self._json({'ok': False, 'error': 'invalid_amount',
                                   'message': 'Tender amount must be positive.'}, status=400)
            # OVERTENDER AND CHANGE. Mezze used to reject every tender larger than the
            # balance, which made change structurally impossible: a guest handing 100
            # for a 73 bill could not be served at all, and the "Change" figure on the
            # receipt was always a display-only zero.
            #
            # Overpay is only meaningful in CASH — a card cannot hand coins back — so a
            # non-cash method is still refused, and now says why.
            #
            # Core's model is followed exactly rather than reinvented: the full amount
            # given is recorded as one positive payment, and the change goes back as a
            # SEPARATE negative payment on the cash method flagged ``is_change``. That
            # is what makes ``amount_paid`` settle to the order total and
            # ``amount_return`` compute to the change — both are Odoo's own computes
            # over the payment lines, so the session's cash figures, the closing entry
            # and the reports all add up without Mezze touching them.
            # What the card can actually pay, decided against the balance that exists
            # NOW: a balance read when the code was typed is a balance another till
            # may have spent since. Capped three ways — what is on the card, what is
            # owed, and what was asked for — so a card can settle part of a bill and
            # the rest goes on another tender, which is how gift cards are used.
            if gift:
                if round(gift.points, prec) <= 0:
                    return self._json({'ok': False, 'error': 'giftcard_empty',
                                       'message': 'That gift card has no balance left.',
                                       'balance': 0.0}, status=400)
                tender = round(min(tender, gift.points, remaining), prec)
                if tender <= 0:
                    return self._json({'ok': False, 'error': 'invalid_amount',
                                       'message': 'Nothing left to charge to this card.'},
                                      status=400)

            if wallet:
                if round(wallet.points, prec) <= 0:
                    return self._json({'ok': False, 'error': 'ewallet_empty',
                                       'message': 'That wallet has no balance left.',
                                       'balance': 0.0}, status=400)
                tender = round(min(tender, wallet.points, remaining), prec)
                if tender <= 0:
                    return self._json({'ok': False, 'error': 'invalid_amount',
                                       'message': 'Nothing left to charge to this wallet.'},
                                      status=400)

            change_due = 0.0
            if tender - remaining > eps:
                if not pm.is_cash_count:
                    return self._json(
                        {'ok': False, 'error': 'overpay_not_cash', 'remaining': remaining,
                         'message': 'Only a cash tender can be over-paid; '
                                    'a card cannot give change.'}, status=400)
                change_due = round(tender - remaining, prec)
            # S2C-6 — Customer Account credit governance. Applies ONLY to the amount
            # charged to the account (`tender`). The receivable/limit are Odoo's; Mezze
            # enforces the configured policy with a durable per-customer lock so two
            # registers can't both pass on the same stale available credit.
            credit_block = self._mezze_credit_gate(
                env, pm, order, config, tender, manager, mgr_auth_error, bool(allow_credit))
            if credit_block:
                return credit_block
            pay_vals = {'amount': tender, 'payment_method_id': pm.id,
                        'name': fields.Datetime.now(), 'pos_order_id': order.id}
            if payment_ref:
                pay_vals['payment_ref_no'] = str(payment_ref).strip()
            if approval_code:
                pay_vals['payment_method_authcode'] = str(approval_code).strip()
            if device:
                pay_vals['mezze_device_id'] = device.id
            if tender_key:
                pay_vals['mezze_tender_key'] = str(tender_key)
            order.add_payment(pay_vals)
            if wallet:
                self._ewallet_decrement(env, wallet, tender,
                                        order.pos_reference or order.id)
                self._audit(env, 'ewallet.spend', order, **self._actor(env, kw),
                            detail=json.dumps({'applied': tender,
                                               'balance': wallet.points,
                                               'partner_id': order.partner_id.id},
                                              default=str))
            if gift:
                self._giftcard_decrement(env, gift, tender,
                                         order.pos_reference or order.id)
                self._audit(env, 'giftcard.redeem', order, **self._actor(env, kw),
                            detail=json.dumps({'code': gift.code, 'applied': tender,
                                               'balance': gift.points}, default=str))
            if change_due > 0:
                # A negative payment on the SAME cash method, exactly as core does when
                # a session records returned cash.
                order.add_payment({
                    'name': _('return'), 'pos_order_id': order.id,
                    'amount': -change_due, 'payment_date': fields.Datetime.now(),
                    'payment_method_id': pm.id, 'is_change': True,
                })
                # ``add_payment`` refreshes ``amount_paid`` (which nets to the bill on
                # its own) but not ``amount_return``: that field is plain stored, and
                # core fills it from the UI payload in ``_process_payment_lines``. This
                # flow has no such payload, so it is recorded here — by the same rule
                # core's own compute uses, the negative payment lines — rather than
                # from the local `change_due`, so the stored figure can only ever agree
                # with the lines behind it.
                order.sudo().amount_return = -sum(
                    p.amount for p in order.payment_ids if p.amount < 0)
            if manager:
                try:
                    env['mezze.audit.log'].sudo().log(
                        'payment.duplicate_approved', severity='warning', res_model='pos.order',
                        res_id=order.id, res_uuid=order.uuid or False, cashier_id=manager.id,
                        detail=json.dumps({'approver_id': manager.id, 'approver': manager.name,
                                           'role': manager.role, 'method': pm.name, 'amount': tender,
                                           'reason': (manager_reason or '')[:200]}))
                except Exception:  # noqa: BLE001
                    pass
            paid = round(order.amount_paid, prec)
            new_remaining = round(order.amount_total - paid, prec)
            if new_remaining <= eps:
                # Balance settled -> finalise the sale (reuses core lifecycle).
                order.action_pos_order_paid()
                # A gift card sold on the till is minted HERE, because this is where an
                # order the Owl register created actually becomes paid. Minting only in
                # /orders/sync's atomic branch meant the register took the money and
                # issued no card.
                issued_cards = self._mint_giftcards(env, order, kw, via='pay')
                # Selling the top-up product credits the customer's wallet, for the
                # same reason selling the gift-card product mints a card: the money
                # has just been collected on this order.
                topped_up = self._ewallet_topup(env, order, kw)
                earned, balance = self._loyalty_earn(env, order)
                self._audit(env, 'order.pay', order, **self._actor(env, kw),
                            detail=json.dumps({'via': 'order_pay', 'tender': tender, 'final': True}))
                self._publish_order_paid(env, order)
                self._publish_pay_hardware(env, order, kw)
                return {'ok': True, 'order_id': order.id, 'pos_reference': order.pos_reference,
                        'state': order.state, 'amount_total': round(order.amount_total, prec),
                        'amount_paid': round(order.amount_paid, prec), 'remaining': 0.0,
                        # What to hand back, and what Odoo recorded. Reported from the
                        # ORDER, not from the arithmetic above, so the till shows the
                        # figure that was actually stored against the sale.
                        'change': round(order.amount_return, prec),
                        # The codes have to reach the till: an issued card the cashier
                        # cannot read out or print is not an issued card.
                        'gift_cards': issued_cards,
                        # What is LEFT on the card just spent — the guest asks, and a
                        # cashier who has to look it up separately will not bother.
                        'gift_card_balance': (round(gift.points, prec) if gift else None),
                        'ewallet_balance': (round(wallet.points, prec) if wallet else None),
                        'ewallet_topup': topped_up,
                        'loyalty_earned': earned, 'loyalty_balance': balance}
            # Partial tender: order stays open/draft, still payable.
            self._audit(env, 'order.pay', order, **self._actor(env, kw),
                        detail=json.dumps({'via': 'order_pay', 'tender': tender, 'partial': True}))
            return {'ok': True, 'partial': True, 'order_id': order.id,
                    'pos_reference': order.pos_reference, 'state': 'draft',
                    'amount_total': round(order.amount_total, prec),
                    'amount_paid': paid, 'remaining': new_remaining,
                    'gift_card_balance': (round(gift.points, prec) if gift else None),
                    'ewallet_balance': (round(wallet.points, prec) if wallet else None)}
        except Exception as exc:  # noqa: BLE001
            _reraise_if_retryable(exc)
            _logger.exception("Mezze pay failed")
            return self._json({'ok': False, 'error': 'pay_failed', 'message': str(exc)}, status=400)

    @http.route(f'{API_PREFIX}/orders/get', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def order_get(self, uuid=None, order_id=None, **kw):
        """Fetch one order's lines — used to resume an open table into the cart."""
        auth = self._authorize()
        if auth:
            return auth
        try:
            env = self._api_env()
            order = (env['pos.order'].search([('uuid', '=', uuid)], limit=1)
                     if uuid else env['pos.order'].browse(int(order_id)))
            if not order.exists():
                return self._json({'ok': False, 'error': 'not_found'}, status=404)
            # CP9 — OBJECT-SCOPE authorization: a fetch by uuid/id must be confined to
            # the caller's branch/company. Without this a terminal token could read any
            # order (incl. a guessable sequential id) cross-branch/company. Reuses the
            # canonical gate (admin/shared bypasses; terminal/cashier are scoped).
            denied = self._security_gate(env, 'orders/get', target=order)
            if denied:
                return denied
            has_count = 'customer_count' in order._fields
            paid = round(order.amount_paid, 2)
            total = round(order.amount_total, 2)
            floor = (order.table_id.floor_id.name
                     if ('table_id' in order._fields and order.table_id and order.table_id.floor_id) else None)
            return {
                'ok': True, 'order_id': order.id, 'uuid': order.uuid,
                'pos_reference': order.pos_reference, 'state': order.state,
                'parked': bool(order.mezze_parked) if 'mezze_parked' in order._fields else False,
                'table_id': order.table_id.id if ('table_id' in order._fields and order.table_id) else None,
                'table': (str(order.table_id.table_number)
                          if ('table_id' in order._fields and order.table_id) else None),
                'floor': floor,
                'guests': order.customer_count if has_count else 0,
                'partner': ({'id': order.partner_id.id, 'name': order.partner_id.name}
                            if order.partner_id else None),
                'order_type': self._mezze_order_type(order),
                # CP9 partial-recall: the cashier must resume on the exact remaining
                # balance and never re-tender what is already paid.
                'amount_total': total, 'amount_paid': paid, 'remaining': round(total - paid, 2),
                # `discount` matters to the till, not just to reporting: a comp is
                # recorded as a 100% discount on the line, so a client that only read
                # price_unit rebuilt a comped line at full price and showed a total
                # the order was never going to charge.
                # A line is returned with everything it takes to REBUILD it. This
                # payload used to carry product/qty/price/discount only, so resuming
                # a table produced bare lines — and because /orders/sync replaces
                # lines wholesale, the next save then DESTROYED the modifiers, the
                # note and the combo structure on the server. "No onion, large, with
                # fries" became a plain burger, silently, on the second save.
                'lines': [{
                    'id': l.id,
                    'product_id': l.product_id.id, 'name': l.product_id.display_name,
                    'full_name': l.full_product_name or l.product_id.display_name,
                    'qty': l.qty, 'price_unit': l.price_unit,
                    'discount': l.discount,
                    'price_subtotal_incl': l.price_subtotal_incl,
                    'attribute_value_ids': l.attribute_value_ids.ids,
                    'price_extra': l.price_extra if 'price_extra' in l._fields else 0.0,
                    'note': (l.customer_note or '') if 'customer_note' in l._fields else '',
                    'combo_parent_id': l.combo_parent_id.id or None,
                    'combo_item_id': (l.combo_item_id.id or None)
                                     if 'combo_item_id' in l._fields else None,
                    'is_reward_line': bool(l.is_reward_line)
                                      if 'is_reward_line' in l._fields else False,
                } for l in order.lines if l.qty > 0],
            }
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze order_get failed")
            return self._json({'ok': False, 'error': 'get_failed', 'message': str(exc)}, status=400)

    def _apply_preset_booking(self, order, preset, when):
        """Record which order type and time this order took.

        Written on the order rather than held in the browser because the SLOT is
        counted from orders: a booking that lives only on a till is a place nobody
        else knows is taken.
        """
        if not order or not order.exists() or not preset:
            return
        vals = {}
        if 'preset_id' in order._fields and order.preset_id.id != preset.id:
            vals['preset_id'] = preset.id
        if when and 'preset_time' in order._fields and order.preset_time != when:
            vals['preset_time'] = when
        if vals:
            order.sudo().write(vals)

    def _apply_service_mode(self, order, service_mode):
        """Store an explicit eat-in/takeaway choice on the order (ignore anything else)."""
        if service_mode not in ('eat_in', 'takeaway'):
            return
        if 'mezze_service_mode' not in order._fields:
            return
        if order.mezze_service_mode != service_mode:
            order.sudo().write({'mezze_service_mode': service_mode})

    def _mezze_order_type(self, order):
        """Cashier-facing order class label (never a raw internal code)."""
        if 'table_id' in order._fields and order.table_id:
            return 'dine_in'
        chan = (order.mezze_channel or '') if 'mezze_channel' in order._fields else ''
        if chan == 'delivery':
            return 'delivery'
        mode = (order.mezze_service_mode or '') if 'mezze_service_mode' in order._fields else ''
        if mode == 'takeaway' or chan in ('pickup', 'kiosk', 'drivethru'):
            return 'takeaway'
        return 'counter'

    # ------------------------------------------------------------------
    # R2A CP6 — reverse workflow: assign a table to an existing draft +
    # authoritative guest count. Both are GUARDED writes to a draft pos.order
    # (never an FSM, never payment/KDS). Server enforces the assignment policy
    # (branch scope, occupied/reserved) that raw /orders/sync cannot.
    # ------------------------------------------------------------------
    @http.route(f'{API_PREFIX}/orders/assign_table', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*', readonly=False)
    def order_assign_table(self, uuid=None, table_id=None, config_id=None, **kw):
        auth = self._authorize()
        if auth:
            return auth
        try:
            env = self._api_env()
            order = env['pos.order'].search([('uuid', '=', uuid), ('state', '=', 'draft')], limit=1)
            if not order:
                return self._json({'ok': False, 'error': 'order_not_found'}, status=404)
            cfg = order.config_id
            if config_id and int(config_id) != cfg.id:
                return self._json({'ok': False, 'error': 'forbidden'}, status=403)
            if 'restaurant.table' not in env or 'table_id' not in order._fields:
                return self._json({'ok': False, 'error': 'not_restaurant'}, status=400)
            Table = env['restaurant.table'].sudo()
            table = (Table.with_context(active_test=False).browse(int(table_id))
                     if table_id and str(table_id).isdigit() else Table)
            # invalid / inactive / cross-branch table → refuse (no exposure, no crash)
            if (not table or not table.exists() or not table.active or not table.floor_id
                    or cfg.id not in table.floor_id.pos_config_ids.ids):
                return self._json({'ok': False, 'error': 'invalid_table'}, status=400)
            # serialize vs concurrent fires/moves on the target table
            env.cr.execute("SELECT pg_advisory_xact_lock(%s, %s)", (self._FIRE_LOCK_NS, int(table.id)))
            # OCCUPIED by a DIFFERENT draft → Transfer/Merge territory (CP7), never a
            # silent overwrite/merge here.
            other = env['pos.order'].search(
                [('table_id', '=', table.id), ('state', '=', 'draft'),
                 ('config_id', '=', cfg.id), ('id', '!=', order.id)], limit=1)
            if other:
                return self._json({'ok': False, 'error': 'table_occupied'}, status=409)
            # RESERVED and holding the table now → must check-in/seat first (reservation
            # FSM); do NOT bypass it by assigning a walk-in order.
            if 'mezze.reservation' in env:
                now = fields.Datetime.now()
                soon = now + datetime.timedelta(minutes=self.RES_LEAD_MIN)
                res = env['mezze.reservation'].search(
                    [('table_id', '=', table.id), ('state', '=', 'booked'),
                     ('start', '>=', fields.Datetime.to_string(now - datetime.timedelta(minutes=20))),
                     ('start', '<=', fields.Datetime.to_string(soon))], limit=1)
                if res:
                    return self._json({'ok': False, 'error': 'table_reserved'}, status=409)
            order.sudo().write({'table_id': table.id})
            name_field = 'table_number' if 'table_number' in Table._fields else 'name'
            return {'ok': True, 'uuid': order.uuid, 'table': {
                'id': table.id, 'name': str(table[name_field]), 'floor': table.floor_id.name,
                'order_uuid': order.uuid,
                'guests': order.customer_count if 'customer_count' in order._fields else 0,
            }}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze assign_table failed")
            return self._json({'ok': False, 'error': 'assign_failed', 'message': str(exc)}, status=400)

    @http.route(f'{API_PREFIX}/orders/set_guests', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*', readonly=False)
    def order_set_guests(self, uuid=None, guests=None, config_id=None, **kw):
        auth = self._authorize()
        if auth:
            return auth
        try:
            env = self._api_env()
            if 'customer_count' not in env['pos.order']._fields:
                return self._json({'ok': False, 'error': 'no_guest_field'}, status=400)
            order = env['pos.order'].search([('uuid', '=', uuid), ('state', '=', 'draft')], limit=1)
            if not order:
                return self._json({'ok': False, 'error': 'order_not_found'}, status=404)
            if config_id and int(config_id) != order.config_id.id:
                return self._json({'ok': False, 'error': 'forbidden'}, status=403)
            g = max(1, int(guests or 1))
            order.sudo().write({'customer_count': g})
            return {'ok': True, 'uuid': order.uuid, 'guests': order.customer_count}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze set_guests failed")
            return self._json({'ok': False, 'error': 'set_guests_failed', 'message': str(exc)}, status=400)

    # ------------------------------------------------------------------
    # Coursing — stage later courses as HELD, fire each on demand
    # ------------------------------------------------------------------
    # Firing already carries a course number (each fire = a course). Coursing
    # adds the missing half: the waiter stages later courses (appetiser / main /
    # dessert) as HELD — not yet sent to the kitchen — and fires each when the
    # table is ready. Held courses live in a per-table config-param (ephemeral,
    # like 86/quick-keys state); firing one pops it and rings it through the
    # normal fire path, so it lands as a real numbered course.
    def _held_key(self, table_id):
        return 'mezze_bridge.held_t%s' % int(table_id)

    def _held_get(self, env, table_id):
        raw = env['ir.config_parameter'].sudo().get_param(self._held_key(table_id), '[]')
        try:
            return json.loads(raw) or []
        except Exception:  # noqa: BLE001
            return []

    def _held_set(self, env, table_id, courses):
        env['ir.config_parameter'].sudo().set_param(
            self._held_key(table_id), json.dumps(courses or []))

    def _held_payload(self, env, course):
        items = []
        for l in (course.get('lines') or []):
            p = env['product.product'].browse(int(l['product_id']))
            items.append({'product_id': p.id, 'name': p.display_name,
                          'qty': float(l.get('qty', 1) or 0), 'note': l.get('note') or ''})
        return {'seq': course.get('seq'), 'name': course.get('name') or ('Course %s' % course.get('seq')),
                'held': True, 'items': items}

    def _fired_courses(self, env, table, session):
        """Fired courses for the table's open draft, grouped from KDS tickets."""
        order = env['pos.order'].search(
            [('table_id', '=', table.id), ('state', '=', 'draft'),
             ('session_id', '=', session.id)], limit=1)
        if not order:
            return []
        tickets = env['mezze.kds.ticket'].search([('pos_order_id', '=', order.id)])
        by_course = {}
        for tk in tickets:
            c = by_course.setdefault(tk.course or 1, {'seq': tk.course or 1, 'held': False,
                                                      'items': [], 'states': []})
            c['states'].append(tk.state)
            for l in tk.line_ids:
                c['items'].append({'product_id': l.product_id.id, 'name': l.name, 'qty': l.qty})
        out = []
        for c in by_course.values():
            st = c.pop('states')
            c['state'] = ('served' if all(s in ('served',) for s in st)
                          else 'ready' if all(s in ('ready', 'served') for s in st)
                          else 'preparing')
            c['name'] = 'Course %s' % c['seq']
            out.append(c)
        return out

    @http.route(f'{API_PREFIX}/courses/board', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def courses_board(self, table_id=None, **kw):
        """All courses for a table — fired (from the KDS) + held (staged), by seq."""
        auth = self._authorize()
        if auth:
            return auth
        try:
            env = self._api_env()
            table = env['restaurant.table'].browse(int(table_id))
            if not table.exists():
                return self._json({'ok': False, 'error': 'no_table'}, status=404)
            config = self._qr_config(env, table)
            env = env(context=dict(env.context, allowed_company_ids=[config.company_id.id],
                                   company_id=config.company_id.id))
            config = config.with_env(env)
            session = self._ensure_open_session(env, config)
            fired = self._fired_courses(env, table, session)
            held = [self._held_payload(env, c) for c in self._held_get(env, table.id)]
            courses = sorted(fired + held, key=lambda c: (c['seq'] or 99, c['held']))
            return {'ok': True, 'table_id': table.id, 'table_number': table.table_number,
                    'courses': courses}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze courses_board failed")
            return self._json({'ok': False, 'error': 'courses_board_failed', 'message': str(exc)}, status=400)

    @http.route(f'{API_PREFIX}/courses/hold', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*', readonly=False)
    def courses_hold(self, table_id=None, seq=None, name=None, lines=None, **kw):
        """Stage a HELD course for a table (not sent to the kitchen). Replaces any
        existing held course with the same seq. Empty lines removes it."""
        auth = self._authorize()
        if auth:
            return auth
        try:
            env = self._api_env()
            table = env['restaurant.table'].browse(int(table_id))
            if not table.exists():
                return self._json({'ok': False, 'error': 'no_table'}, status=404)
            seq = int(seq or 0)
            if not seq:
                return self._json({'ok': False, 'error': 'no_seq'}, status=400)
            held = [c for c in self._held_get(env, table.id) if int(c.get('seq', 0)) != seq]
            clean = [{'product_id': int(l['product_id']), 'qty': float(l.get('qty', 1) or 0),
                      'note': l.get('note') or ''} for l in (lines or []) if l.get('product_id')]
            if clean:
                held.append({'seq': seq, 'name': (name or '').strip() or ('Course %s' % seq),
                             'lines': clean})
            held.sort(key=lambda c: c['seq'])
            self._held_set(env, table.id, held)
            return {'ok': True, 'held': [self._held_payload(env, c) for c in held]}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze courses_hold failed")
            return self._json({'ok': False, 'error': 'courses_hold_failed', 'message': str(exc)}, status=400)

    @http.route(f'{API_PREFIX}/courses/fire', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*', readonly=False)
    def courses_fire(self, table_id=None, seq=None, uuid=None, fire_uuid=None, **kw):
        """Fire a HELD course: pop it, ring its lines through the normal fire path
        (so it lands as a real numbered KDS course), and drop it from the held
        list. Idempotency + concurrency are the shared _do_fire core's."""
        auth = self._authorize()
        if auth:
            return auth
        try:
            env = self._api_env()
            table = env['restaurant.table'].browse(int(table_id))
            if not table.exists():
                return self._json({'ok': False, 'error': 'no_table'}, status=404)
            seq = int(seq or 0)
            held = self._held_get(env, table.id)
            course = next((c for c in held if int(c.get('seq', 0)) == seq), None)
            if not course:
                return self._json({'ok': False, 'error': 'no_such_course'}, status=404)
            config = self._qr_config(env, table)
            env = env(context=dict(env.context, allowed_company_ids=[config.company_id.id],
                                   company_id=config.company_id.id))
            config = config.with_env(env)
            session = self._ensure_open_session(env, config)
            uuid = uuid or 'crs-t%s-%s' % (table.id, session.id)
            fire_uuid = fire_uuid or ('crs:%s:%s' % (uuid, seq))
            lines = [{'product_id': l['product_id'], 'qty': l['qty'],
                      'note': l.get('note')} for l in course['lines']]
            result = self._do_fire(env, uuid, session, config, table.id, lines,
                                   None, None, fire_uuid, server_override='Coursing')
            # drop the fired course from the held list
            self._held_set(env, table.id, [c for c in held if int(c.get('seq', 0)) != seq])
            self._audit(env, 'course.fire', env['pos.order'].browse(result.get('order_id')),
                        **self._actor(env, kw),
                        detail=json.dumps({'table': table.table_number, 'course': seq}, default=str))
            result['fired_course'] = seq
            return result
        except Exception as exc:  # noqa: BLE001
            _reraise_if_retryable(exc)
            _logger.exception("Mezze courses_fire failed")
            return self._json({'ok': False, 'error': 'courses_fire_failed', 'message': str(exc)}, status=400)

    # ------------------------------------------------------------------
    # QR ordering — public, per-table scoped self-service
    # ------------------------------------------------------------------
    def _qr_resolve(self, env, table_id, qr):
        """Validate a customer QR request. The (table_id, qr) pair is the ONLY
        credential the phone holds — it authorizes reading the menu and firing to
        THIS table, nothing else. Returns the table or raises."""
        if not table_id or not qr:
            raise ValueError("Missing table or QR token")
        table = env['restaurant.table'].sudo().browse(int(table_id))
        if not table.exists() or not table.mezze_qr_token or table.mezze_qr_token != qr:
            raise ValueError("Invalid QR token for this table")
        return table

    def _qr_config(self, env, table):
        """The pos.config a QR order for ``table`` should land in."""
        cfg = table.floor_id.pos_config_ids[:1] if 'pos_config_ids' in table.floor_id._fields else env['pos.config']
        return cfg or env['pos.config'].search([], limit=1)

    def _asset_version(self, filename):
        """Cache-busting stamp for a static front-end file: its mtime. Stable
        between deploys so browsers still cache the page, but it changes the
        moment the file is updated — a returning client then fetches the fresh
        build instead of a stale cached one. Falls back to '0' if not stat'able."""
        try:
            path = os.path.join(os.path.dirname(__file__), '..', 'static', filename)
            return str(int(os.path.getmtime(path)))
        except OSError:
            return '0'

    def _qr_asset_version(self):
        return self._asset_version('qr.html')

    @http.route('/mezze/design/pos', type='http', auth='user', methods=['GET'], csrf=False)
    def pos_launcher(self, **kw):
        """DESIGN PROTOTYPE launcher (non-production). The production cashier is the
        standalone Owl app at ``/mezze/pos`` (controllers/cashier.py); this route now
        serves the visual reference prototype (static/pos.html) under a clearly
        non-production path so the two never both appear to be the live POS.

        AUTHENTICATED entry to the prototype front-end. Requires an Odoo login
        (staff), then hands the current shared API token to the front-end via a
        same-origin, path-scoped, SameSite=Strict **cookie** and redirects to a
        CLEAN url (no token in the query string). This keeps the token out of the
        URL bar / browser history / Referer header — closing the token-in-URL
        residual — while still gating access to authenticated users only (the
        token is never hardcoded in the frontend nor served to anonymous users,
        killing the old public 'test123'). The direct static URL keeps its
        ``?token=`` fallback for offline terminals. See docs/W1.md."""
        token = request.env['ir.config_parameter'].sudo().get_param(TOKEN_PARAM, '')
        parts = []
        if kw.get('base'):
            parts.append('base=%s' % quote(str(kw['base']), safe=''))
        parts.append('v=%s' % self._asset_version('pos.html'))
        url = '/mezze_bridge/static/pos.html?' + '&'.join(parts)
        resp = request.redirect(url, local=True)
        resp.set_cookie(
            'mezze_pos_token', token,
            max_age=12 * 3600, path='/mezze_bridge/static',
            samesite='Strict', httponly=False,
            secure=request.httprequest.is_secure)
        return resp

    @http.route(f'{API_PREFIX}/qr/table_link', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def qr_table_link(self, table_id=None, **kw):
        """Staff-only: mint (if needed) + return a table's customer QR link so the
        POS can show/print the code. The frontend builds the absolute URL and the
        QR image (via Odoo's /report/barcode) from location.origin."""
        auth = self._authorize()
        if auth:
            return auth
        try:
            env = self._api_env()
            table = env['restaurant.table'].sudo().browse(int(table_id))
            if not table.exists():
                return self._json({'ok': False, 'error': 'not_found'}, status=404)
            token = table._mezze_ensure_qr_token()
            return {
                'ok': True, 'table_id': table.id, 'table_number': table.table_number,
                'qr_token': token,
                'path': '/mezze_bridge/static/qr.html?table=%s&qr=%s&v=%s' % (
                    table.id, token, self._qr_asset_version()),
            }
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze qr_table_link failed")
            return self._json({'ok': False, 'error': 'link_failed', 'message': str(exc)}, status=400)

    @http.route(f'{API_PREFIX}/qr/menu', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def qr_menu(self, table_id=None, qr=None, **kw):
        """Public: the customer menu for one table (scoped by its QR token)."""
        try:
            env = self._api_env()
            table = self._qr_resolve(env, table_id, qr)
            config = self._qr_config(env, table)
            if not config:
                return self._json({'ok': False, 'error': 'no_pos_config'}, status=404)
            env = env(context=dict(env.context, allowed_company_ids=[config.company_id.id], company_id=config.company_id.id))
            config = config.with_env(env)
            session = self._ensure_open_session(env, config)
            categories = env['pos.category'].search_read([], ['id', 'name'])
            products = env['product.product'].search_read(
                self._menu_domain(env, config),
                ['id', 'display_name', 'list_price', 'pos_categ_ids', 'type'])
            # customers never see 86'd items — hide them outright on the QR menu
            blocked86 = self._eightysix_ids(env, config.id)
            products = [p for p in products if p['id'] not in blocked86]
            for p in products:
                p['name'] = p.pop('display_name')
                prod = env['product.product'].browse(p['id'])
                p['modifiers'] = self._product_modifiers(env, prod)
                p['combos'] = self._product_combos(env, prod)
                p['is_combo'] = p['type'] == 'combo'
            return {
                'ok': True, 'session_id': session.id, 'config_id': config.id,
                'currency_id': config.currency_id.id,
                # The NAME as well as the id: the table page labels every price from
                # its first paint, and it used to print a hardcoded "EGP" because the
                # id alone told it nothing it could show a guest.
                'currency': _display_currency(config),
                'table_id': table.id, 'table_number': table.table_number,
                'floor': table.floor_id.name,
                'categories': categories, 'products': products,
            }
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze qr_menu failed")
            return self._json({'ok': False, 'error': 'qr_menu_failed', 'message': str(exc)}, status=400)

    @http.route(f'{API_PREFIX}/qr/order', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*', readonly=False)
    def qr_order(self, table_id=None, qr=None, lines=None, uuid=None,
                 fire_uuid=None, guests=None, **kw):
        """Public: a customer fires a course to their table. Reuses the exact same
        concurrency-safe ``_do_fire`` core as the waiter path, so a customer and a
        waiter ringing the same table at once both land (no lost order). We fire
        to the VALIDATED table only — a spoofed table_id/config is ignored."""
        try:
            env = self._api_env()
            table = self._qr_resolve(env, table_id, qr)
            if not lines:
                return self._json({'ok': False, 'error': 'no_lines'}, status=400)
            lines = self._sanitize_customer_lines(lines)   # §63 no client price/discount
            config = self._qr_config(env, table)
            if not config:
                return self._json({'ok': False, 'error': 'no_pos_config'}, status=404)
            env = env(context=dict(env.context, allowed_company_ids=[config.company_id.id], company_id=config.company_id.id))
            config = config.with_env(env)
            # S4: staff can pause table-QR ordering without closing the register — do
            # this BEFORE opening/creating a session so a customer scan can't force one.
            if self._selforder_paused(env, config, 'qr'):
                return self._json({'ok': False, 'error': 'selforder_paused',
                                   'message': 'Table ordering is temporarily unavailable.'}, status=409)
            session = self._ensure_open_session(env, config)
            uuid = uuid or 'qr-t%s-%s' % (table.id, session.id)
            if not fire_uuid:
                sig = hashlib.sha1(json.dumps(lines, sort_keys=True).encode()).hexdigest()[:12]
                fire_uuid = 'qr:%s:%s' % (uuid, sig)
            result = self._do_fire(env, uuid, session, config, table.id, lines,
                                   None, guests, fire_uuid, server_override='QR self-order')
            result['table_number'] = table.table_number
            return result
        except Exception as exc:  # noqa: BLE001
            _reraise_if_retryable(exc)
            _logger.exception("Mezze qr_order failed")
            return self._json({'ok': False, 'error': 'qr_order_failed', 'message': str(exc)}, status=400)

    # ------------------------------------------------------------------
    # QR pay-at-table — the diner settles their table's bill from their phone
    # ------------------------------------------------------------------
    def _qr_pay_method(self, env, config):
        """The payment method that settles a QR pay-at-table bill. A pos.payment
        may only reference a method already on the session's config, so we use a
        config method: a dedicated 'QR Pay' one if a manager provisioned it (for
        clean reporting), else the config's electronic (non-cash) method — a
        QR/online settle is electronic, not a cash drop. The real card capture is
        the gateway step (Paymob), gated separately."""
        methods = config.payment_method_ids
        named = methods.filtered(lambda m: m.name == 'QR Pay')
        if named:
            return named[:1]
        # fallback: a non-cash card/bank method, but NOT a gift-card / wallet
        # tender (those are ways to PAY, not settlement journals). Provision a
        # dedicated 'QR Pay' method (sessions closed) for clean reporting.
        def _is_tender(m):
            return any(w in (m.name or '').lower() for w in ('gift', 'wallet', 'ewallet'))
        electronic = methods.filtered(lambda m: not m.is_cash_count and not _is_tender(m))
        pm = electronic[:1] or methods.filtered(lambda m: not _is_tender(m))[:1] or methods[:1]
        if not pm:
            raise ValueError("No payment method configured for this branch")
        return pm

    def _qr_open_order(self, env, table, session):
        """The table's single open (unpaid) draft in the current session, if any."""
        return env['pos.order'].search(
            [('table_id', '=', table.id), ('state', '=', 'draft'),
             ('session_id', '=', session.id)], limit=1)

    def _qr_bill_payload(self, order):
        items = [{'name': l.product_id.display_name, 'qty': l.qty,
                  'price': round(l.price_subtotal_incl, 2)}
                 for l in order.lines
                 if l.qty > 0 and l.product_id.type != 'combo' and not l.combo_parent_id]
        if order.mezze_channel not in ('pos', 'dinein'):
            order.mezze_channel = 'qr'                 # a QR-originated table order
        stok = order._mezze_ensure_status_token()
        return {
            'order_id': order.id,
            'tracking': order.tracking_number or order.pos_reference or '',
            'status_token': stok,
            'items': items,
            'subtotal': round(order.amount_total - order.amount_tax, 2),
            'tax': round(order.amount_tax, 2),
            'total': round(order.amount_total, 2),
            'paid': order.state != 'draft',
        }

    @http.route(f'{API_PREFIX}/qr/bill', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def qr_bill(self, table_id=None, qr=None, **kw):
        """Public: the table's running bill (its open draft), scoped by QR token."""
        try:
            env = self._api_env()
            table = self._qr_resolve(env, table_id, qr)
            config = self._qr_config(env, table)
            if not config:
                return self._json({'ok': False, 'error': 'no_pos_config'}, status=404)
            env = env(context=dict(env.context, allowed_company_ids=[config.company_id.id],
                                   company_id=config.company_id.id))
            config = config.with_env(env)
            session = self._ensure_open_session(env, config)
            order = self._qr_open_order(env, table, session)
            base = {'ok': True, 'table_number': table.table_number,
                    'currency': _display_currency(config)}
            if not order:
                return dict(base, empty=True)
            return dict(base, empty=False, bill=self._qr_bill_payload(order))
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze qr_bill failed")
            return self._json({'ok': False, 'error': 'qr_bill_failed', 'message': str(exc)}, status=400)

    @http.route(f'{API_PREFIX}/qr/pay', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*', readonly=False)
    def qr_pay(self, table_id=None, qr=None, tip=None, **kw):
        """Public: the diner settles their table's bill. Optionally adds a tip,
        then closes the draft (add_payment + action_pos_order_paid) on the QR Pay
        method. The real card capture is the gateway step (Paymob), gated
        separately; this is the pay-at-table settle flow it plugs into."""
        try:
            env = self._api_env()
            table = self._qr_resolve(env, table_id, qr)
            config = self._qr_config(env, table)
            if not config:
                return self._json({'ok': False, 'error': 'no_pos_config'}, status=404)
            env = env(context=dict(env.context, allowed_company_ids=[config.company_id.id],
                                   company_id=config.company_id.id))
            config = config.with_env(env)
            session = self._ensure_open_session(env, config)
            order = self._qr_open_order(env, table, session)
            if not order:
                return self._json({'ok': False, 'error': 'no_bill',
                                   'message': 'No open bill for this table'}, status=404)
            order = order.with_env(env)
            tip_amt = round(float(tip or 0.0), 2)
            # tip + settle atomically: a failure must not leave a phantom tip line
            with env.cr.savepoint():
                if tip_amt > 0:
                    tp = self._tip_product(env, config)
                    order.write({'lines': [(0, 0, {
                        'product_id': tp.id, 'qty': 1, 'price_unit': tip_amt, 'discount': 0.0,
                        'tax_ids': [(6, 0, [])], 'price_subtotal': tip_amt,
                        'price_subtotal_incl': tip_amt, 'pack_lot_ids': []})]})
                    tb = sum(order.lines.mapped('price_subtotal'))
                    ti = sum(order.lines.mapped('price_subtotal_incl'))
                    order.write({'amount_tax': ti - tb, 'amount_total': ti,
                                 'is_tipped': True, 'tip_amount': tip_amt})
                pm = self._qr_pay_method(env, config)
                order.add_payment({'amount': order.amount_total, 'payment_method_id': pm.id,
                                   'name': fields.Datetime.now(), 'pos_order_id': order.id})
                order.action_pos_order_paid()
            self._audit(env, 'order.pay', order,
                        detail=json.dumps({'via': 'qr_pay', 'tip': tip_amt}, default=str))
            return {'ok': True, 'tracking': order.tracking_number or order.pos_reference,
                    'total': round(order.amount_total, 2), 'tip': tip_amt, 'paid': True}
        except Exception as exc:  # noqa: BLE001
            _reraise_if_retryable(exc)
            _logger.exception("Mezze qr_pay failed")
            return self._json({'ok': False, 'error': 'qr_pay_failed', 'message': str(exc)}, status=400)

    # ------------------------------------------------------------------
    # Online storefront — public menu + pickup/delivery ordering
    # ------------------------------------------------------------------
    # A PUBLIC front-end (shop.html) reachable off-premise. The shopper's browser
    # holds a per-branch STORE TOKEN (like the QR table token) — enough to read
    # the menu and place a pickup/delivery order for THIS branch, nothing else.
    # Pickup fires a draft to the kitchen (paid at the counter on collection);
    # delivery reuses the paid-cash delivery flow (pay-on-delivery). Real online
    # CARD payment is the deliberately-excluded, externally-gated part.
    def _store_token(self, env, config, create=True):
        key = 'mezze_bridge.store_token_%s' % config.id
        Param = env['ir.config_parameter'].sudo()
        tok = Param.get_param(key)
        if not tok and create:
            tok = os.urandom(12).hex()
            Param.set_param(key, tok)
        return tok

    def _store_config(self, env, store):
        """Resolve a store token to its pos.config (raises if unknown)."""
        if not store:
            raise ValueError("Missing store token")
        Param = env['ir.config_parameter'].sudo()
        for cfg in env['pos.config'].sudo().search([]):
            if Param.get_param('mezze_bridge.store_token_%s' % cfg.id) == store:
                return cfg
        raise ValueError("Unknown store")

    @http.route(f'{API_PREFIX}/shop/link', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def shop_link(self, config_id=None, **kw):
        """Staff-only: get (or mint) the branch's public storefront URL."""
        auth = self._authorize()
        if auth:
            return auth
        env = self._api_env()
        try:
            config = self._resolve_config(env, config_id)
            tok = self._store_token(env, config)
            return {'ok': True, 'config_id': config.id, 'branch': config.name,
                    'store': tok,
                    'url': '/mezze_bridge/static/shop.html?store=%s' % tok}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze shop_link failed")
            return self._json({'ok': False, 'error': 'shop_link_failed', 'message': str(exc)}, status=400)

    @http.route(f'{API_PREFIX}/shop/config', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def shop_config(self, store=None, **kw):
        """Public: the store's identity, open/closed status, fulfillment options
        and delivery zones — everything the storefront needs to render."""
        env = self._api_env()
        try:
            config = self._store_config(env, store)
            session = env['pos.session'].search(
                [('config_id', '=', config.id), ('state', '=', 'opened')], limit=1)
            zones = env['mezze.delivery.zone'].search(
                ['&', ('active', '=', True), '|', ('config_id', '=', config.id),
                 ('config_id', '=', False)])
            return {
                'ok': True, 'branch': config.name, 'open': bool(session),
                'currency': _display_currency(config),
                'fulfillment': ['pickup', 'delivery'],
                'zones': [self._zone_payload(z) for z in zones],
            }
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze shop_config failed")
            return self._json({'ok': False, 'error': 'shop_config_failed', 'message': str(exc)}, status=400)

    # ------------------------------------------------------------------
    # Kiosk V2 — the branch's real configuration, for a customer terminal
    # ------------------------------------------------------------------
    def _kiosk_service_options(self, env, config):
        """What service choices this branch actually offers.

        Odoo's own presets first (``pos.preset``, translated, with their own pricelist
        and fiscal position). A branch that does not use presets still has Mezze's two
        service modes, which are what the order records. Nothing is invented: a kiosk
        must not offer "Dine in" to a branch that only does takeaway.
        """
        out = []
        if 'use_presets' in config._fields and config.use_presets:
            presets = config.available_preset_ids or config.default_preset_id
            for p in presets:
                out.append({'id': p.id, 'name': p.name,
                            'service_mode': 'eat_in' if not p.is_return else 'eat_in',
                            'kind': 'preset',
                            'default': p.id == config.default_preset_id.id})
        if not out:
            svc = getattr(config, 'self_ordering_service_mode', False)
            # `kind` + `service_mode` are the contract a client renders from; the
            # English `name` is a fallback. A PRESET's name above is the branch's own
            # data and is shown as it is -- only these two generic modes are ours to
            # translate, and the kiosk does it in the guest's language.
            out = [{'id': False, 'name': 'Eat in', 'service_mode': 'eat_in',
                    'kind': 'service_mode', 'default': svc == 'table'},
                   {'id': False, 'name': 'Takeaway', 'service_mode': 'takeaway',
                    'kind': 'service_mode', 'default': svc != 'table'}]
        return out

    def _kiosk_partner(self, env, phone):
        """The customer behind a kiosk phone number, or an empty recordset.

        A kiosk asks for a phone and nothing else, so that is all this matches on and
        all it stores. An existing customer is REUSED -- the point of the number is to
        reach the same loyalty card the guest already has -- and a new one is created
        with the phone as its name, because inventing a person's name from nothing is
        worse than an order labelled by the number the guest typed.

        Digits only, and long enough to be a real number: a stray tap must not create
        a partner. Never raises -- a loyalty lookup failing is not a reason to lose an
        order that the kitchen is already cooking.
        """
        digits = re.sub(r'\D', '', str(phone or ''))
        if len(digits) < 7:
            return env['res.partner']
        try:
            Partner = env['res.partner'].sudo()
            # `phone` ONLY. res.partner.mobile was REMOVED in Odoo 19 -- searching it
            # raises KeyError: 'mobile' and, behind the except below, silently cost
            # every kiosk order its customer link.
            found = Partner.search([('phone', '=', digits)], limit=1)
            if found:
                return found
            return Partner.create({'name': digits, 'phone': digits, 'customer_rank': 1})
        except Exception:  # noqa: BLE001 -- never lose a fired order over a lookup
            _logger.exception("Mezze kiosk partner lookup failed")
            return env['res.partner']

    def _kiosk_payment_options(self, env, config):
        """Payment methods this kiosk can REALLY complete.

        Mezze's kiosk creates an unpaid order and prints a number: native self-order
        payment is terminal-only (Adyen/Stripe) and Mezze drives no terminal, so a card
        row here would be decoration the branch cannot honour. The list is data-driven,
        so a certified terminal later adds a row without a redesign.
        """
        counter = getattr(config, 'self_ordering_service_mode', 'counter') != 'table'
        # `code` and `at_table` are the contract; `name` and `hint` are an English
        # FALLBACK for a client with no dictionary of its own. The kiosk translates
        # from the code, because its language toggle is client-side: a label
        # translated here would stay in the language the config was fetched in and
        # would not follow the guest when they switch.
        return [{
            'code': 'pay_at_counter',
            'at_table': not counter,
            'name': 'Pay at the counter' if counter else 'Pay at your table',
            'hint': ('We print your number now — pay when you collect' if counter
                     else 'We print your number now — pay at your table'),
            'icon': 'storefront',
        }]

    @http.route(f'{API_PREFIX}/kiosk/config', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def kiosk_config(self, store=None, **kw):
        """Public: everything a kiosk terminal needs to render itself truthfully.

        Currency, tax behaviour, service choices, languages and payment capability all
        come from the branch's own Odoo configuration. The terminal decides nothing:
        it is a screen for values it is given.
        """
        env = self._api_env()
        try:
            config = self._store_config(env, store)
            session = env['pos.session'].search(
                [('config_id', '=', config.id), ('state', '=', 'opened')], limit=1)
            cur = config.currency_id
            default_lang = getattr(config, 'self_ordering_default_language_id', False)
            return {
                'ok': True,
                'branch': config.name,
                'open': bool(session),
                'currency': {
                    'name': cur.name, 'symbol': cur.symbol or cur.name,
                    'position': cur.position, 'decimals': cur.decimal_places,
                },
                'service_options': self._kiosk_service_options(env, config),
                'service_mode': getattr(config, 'self_ordering_service_mode', 'counter'),
                'payment_options': self._kiosk_payment_options(env, config),
                'default_lang': (default_lang.code or 'en_US')[:5].replace('_', '-')
                                if default_lang else None,
                # The MARKET, from the branch's own company. Locale decides digit shape
                # and separators and nothing else: ar-SA and ar-EG render Arabic-Indic
                # digits, ar-AE renders Latin ones, and the currency is still whatever
                # Odoo says it is.
                'country': (config.company_id.country_id.code or '') or None,
                'paused': self._selforder_paused(env, config, 'kiosk'),
            }
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze kiosk_config failed")
            return self._json({'ok': False, 'error': 'kiosk_config_failed',
                               'message': str(exc)}, status=400)

    @http.route(f'{API_PREFIX}/shop/quote', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def shop_quote(self, store=None, lines=None, **kw):
        """Public: what this cart costs, priced by the SERVER.

        The kiosk shows a running total on every screen, and that number has to be the
        branch's own arithmetic — its pricelist, its taxes, its fiscal position — not a
        sum the browser did. `mezze.cart.pricing` is the same engine the lane's customer
        board uses, and it deliberately reports no tax row for a branch that has no tax:
        inventing "VAT 15%" on a customer's screen is a lie with a number on it.
        """
        env = self._api_env()
        try:
            config = self._store_config(env, store)
            clean = self._sanitize_customer_lines(lines or [])
            rows, money = env['mezze.cart.pricing']._price_cart(config, clean)
            # The tax's own name, reported by the pass that CHARGED it.
            #
            # This used to re-derive the names here, from each product's taxes filtered
            # by ``env.company`` — which is the API env's company and admits
            # ``company_id = False`` besides. The engine filters by the BRANCH's
            # company. When the two disagreed the customer was shown a row charged at
            # one rate and captioned with another: a cart taxed at 10% was labelled
            # "15%". Deriving the label twice, in two different ways, is the bug; the
            # engine is now the single source for both the figure and its name.
            label = ' + '.join((money.get('tax_names') or [])[:2])
            return {'ok': True, 'rows': rows, 'money': money, 'tax_label': label,
                    'currency': _display_currency(config)}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze shop_quote failed")
            return self._json({'ok': False, 'error': 'shop_quote_failed',
                               'message': str(exc)}, status=400)

    @http.route(f'{API_PREFIX}/shop/menu', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def shop_menu(self, store=None, channel=None, **kw):
        """Public: the branch menu (products + modifiers + combos + half-&-half),
        86'd items excluded.

        ``channel='kiosk'`` asks for the SELF-ORDER menu, which additionally honours
        Odoo's ``self_order_available``. The storefront's own menu is unchanged."""
        env = self._api_env()
        try:
            config = self._store_config(env, store)
            categories = env['pos.category'].search_read([], ['id', 'name'])
            catname = {c['id']: (c['name'] or '') for c in categories}
            # Which categories carry the branch's own artwork, so a customer surface
            # can show it beside the name. Derived from the STORED `image_128`, not
            # from core's `has_image`, which declares `@api.depends('has_image')` --
            # it depends on itself, never recomputes and reads back as None. The
            # base64 is not shipped; the picture is fetched from /shop/categ_image.
            _art = set(env['pos.category'].search(
                [('id', 'in', [c['id'] for c in categories]),
                 ('image_128', '!=', False)]).ids)
            for c in categories:
                c['has_image'] = c['id'] in _art
            products = env['product.product'].search_read(
                self._menu_domain(env, config) + self._selforder_domain(env, channel),
                ['id', 'display_name', 'list_price', 'default_code',
                 'pos_categ_ids', 'type'])
            # One batched read for the customer-visible extras the kiosk shows on a
            # card and a detail screen. Read in one go, never per card: a menu is 200
            # products and a per-product query would be an N+1 on the first screen.
            extra = {}
            if channel == 'kiosk' and products:
                tmpl_fields = ['id', 'description_sale']
                if 'product_tag_ids' in env['product.template']._fields:
                    tmpl_fields.append('product_tag_ids')
                prods = env['product.product'].browse([p['id'] for p in products])
                tmpls = prods.product_tmpl_id
                tag_name = {}
                if 'product_tag_ids' in env['product.template']._fields:
                    tag_name = {t['id']: t['name'] for t in
                                env['product.tag'].sudo().search_read([], ['id', 'name'])}
                for row in tmpls.read(tmpl_fields):
                    extra[row['id']] = {
                        'description': (row.get('description_sale') or '').strip(),
                        'tags': [tag_name[t] for t in (row.get('product_tag_ids') or [])
                                 if t in tag_name][:3],
                    }
            blocked = self._eightysix_ids(env, config.id)
            products = [p for p in products if p['id'] not in blocked]
            half_options = []
            for p in products:
                p['name'] = p.pop('display_name')
                prod = env['product.product'].browse(p['id'])
                p['modifiers'] = self._product_modifiers(env, prod)
                p['combos'] = self._product_combos(env, prod)
                p['is_combo'] = p['type'] == 'combo'
                p['half_base'] = (p.get('default_code') == 'HALFHALF')
                p['has_image'] = bool(prod.image_256)
                if channel == 'kiosk':
                    e = extra.get(prod.product_tmpl_id.id) or {}
                    # display_name carries the internal reference ("[CONS_0001] Pen").
                    # A customer terminal shows the product's NAME; the reference is
                    # staff data and has no business on a menu card.
                    p['name'] = prod.name or p['name']
                    p['description'] = e.get('description') or ''
                    p['tags'] = e.get('tags') or []
                    # what the card's affordance says: a product that asks something
                    p['configurable'] = bool(p['modifiers'] or p['combos'])
                    p.pop('default_code', None)      # internal reference, not customer data
                is_pizza = any('pizza' in catname.get(cid, '').lower()
                               for cid in (p.get('pos_categ_ids') or []))
                if is_pizza and not p['half_base']:
                    half_options.append({'id': p['id'], 'name': p['name'],
                                         'price': p['list_price']})
            return {'ok': True, 'branch': config.name,
                    'currency': _display_currency(config),
                    'categories': categories, 'products': products,
                    'half_options': half_options}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze shop_menu failed")
            return self._json({'ok': False, 'error': 'shop_menu_failed', 'message': str(exc)}, status=400)

    @http.route([f'{API_PREFIX}/shop/image',
                 f'{API_PREFIX}/shop/image/<string:store>/<int:product>'],
                type='http', auth='none', methods=['GET'], csrf=False)
    def shop_image(self, store=None, product=None, **kw):
        """Public: stream a menu product's photo (store-token gated).

        Serves the native ``product.product`` image so the storefront can show
        real food photography. Only products actually available in POS are
        served; anything else (or a missing image) 404s so the front-end falls
        back to its illustrated tile. Cached for an hour."""
        try:
            env = self._api_env()
            config = self._store_config(env, store)     # validates the store token
            prod = env['product.product'].sudo().browse(int(product or 0))
            if not prod.exists() or not prod.available_in_pos:
                return request.not_found()
            data = prod.image_512 or prod.image_256 or prod.image_1920
            if not data:
                return request.not_found()
            img = base64.b64decode(data)
            return request.make_response(img, headers=[
                ('Content-Type', 'image/png'),
                ('Content-Length', str(len(img))),
                ('Cache-Control', 'public, max-age=3600'),
            ])
        except Exception:  # noqa: BLE001 - a broken image must never 500 the card
            return request.not_found()

    @http.route(f'{API_PREFIX}/shop/receipt', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*', readonly=False)
    def shop_receipt(self, token=None, receipt=None, **kw):
        """Public: record what a guest asked for their receipt, after the order exists.

        The confirmation screen asks AFTER the order has been placed and fired, so
        this cannot ride on /shop/order. It takes the same OPAQUE status token that
        /shop/status does -- never a sequential id -- so a guest can only ever answer
        for their own order, and the token is rate-limited the same way.

        Records a preference. It prints nothing and settles nothing.
        """
        env = self._api_env()
        try:
            ip = request.httprequest.remote_addr or 'anon'
            allowed, _r, _c = env['mezze.rate.limit'].hit(
                'shop_receipt:%s' % ip, limit=40, window_seconds=60, fail_mode='open')
            if not allowed:
                return self._json({'ok': False, 'error': 'rate_limited'}, status=429)
        except Exception:  # noqa: BLE001
            pass
        if receipt not in ('print', 'none'):
            return self._json({'ok': False, 'error': 'bad_receipt'}, status=400)
        tok = (token or '').strip()
        if not tok or len(tok) < 24:
            return self._json({'ok': False, 'error': 'bad_token'}, status=400)
        order = env['pos.order']._mezze_resolve_status_token(tok)
        if not order:
            return self._json({'ok': False, 'error': 'not_found'}, status=404)
        order.sudo().mezze_receipt_pref = receipt
        self._audit(env, 'shop.receipt', order,
                    detail=json.dumps({'receipt': receipt}, default=str))
        return {'ok': True, 'receipt': receipt}

    @http.route([f'{API_PREFIX}/shop/categ_image',
                 f'{API_PREFIX}/shop/categ_image/<string:store>/<int:categ>'],
                type='http', auth='none', methods=['GET'], csrf=False)
    def shop_categ_image(self, store=None, categ=None, **kw):
        """Public: stream a POS category's own picture (store-token gated).

        Same contract as ``shop_image`` one route above, for the same reason: the
        kiosk's category rail shows a glyph per category, and the honest source for
        it is the artwork the branch attached to the category itself. A category the
        branch left without a picture 404s and the rail falls back to its neutral
        mark -- no image is invented for it.

        Restricted to the categories this branch actually shows, so the token cannot
        be used to enumerate another branch's artwork."""
        try:
            env = self._api_env()
            config = self._store_config(env, store)     # validates the store token
            allowed = {c['id'] for c in self._menu_categories(env, config)}
            cid = int(categ or 0)
            if cid not in allowed:
                return request.not_found()
            rec = env['pos.category'].sudo().browse(cid)
            data = rec.exists() and (rec.image_128 or rec.image_512)
            if not data:
                return request.not_found()
            img = base64.b64decode(data)
            return request.make_response(img, headers=[
                ('Content-Type', 'image/png'),
                ('Content-Length', str(len(img))),
                ('Cache-Control', 'public, max-age=3600'),
            ])
        except Exception:  # noqa: BLE001 - a broken image must never 500 the rail
            return request.not_found()

    @http.route(f'{API_PREFIX}/shop/order', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*', readonly=False)
    def shop_order(self, store=None, lines=None, customer=None, phone=None,
                   fulfillment='pickup', address=None, zone_id=None, note=None,
                   uuid=None, promo_code=None, payment_mode='cod',
                   area=None, street=None, building=None, floor=None,
                   apartment=None, landmark=None, **kw):
        """Public: place an online order. ``pickup`` fires a draft to the kitchen
        (settled at the counter); ``delivery`` with ``payment_mode='cod'`` fires a
        real but UNPAID order (cash collected on delivery — never faked paid at
        checkout), while online delivery goes via /checkout/online/*. Auto-promotions
        + a valid ``promo_code`` are applied server-side. Returns a tracking number."""
        env = self._api_env()
        try:
            config = self._store_config(env, store)
            if not lines:
                return self._json({'ok': False, 'error': 'no_lines'}, status=400)
            lines = self._sanitize_customer_lines(lines)   # §63 no client price/discount
            session = env['pos.session'].search(
                [('config_id', '=', config.id), ('state', '=', 'opened')], limit=1)
            if not session:
                return self._json({'ok': False, 'error': 'store_closed',
                                   'message': 'The store is currently closed'}, status=409)
            # S4: staff can pause a self-order channel without closing the register.
            chan = 'kiosk' if fulfillment == 'kiosk' else fulfillment
            if self._selforder_paused(env, config, chan):
                return self._json({'ok': False, 'error': 'selforder_paused',
                                   'message': 'Ordering is temporarily unavailable.'}, status=409)
            env = env(context=dict(env.context, allowed_company_ids=[config.company_id.id],
                                   company_id=config.company_id.id))
            session = session.with_env(env)
            config = config.with_env(env)
            uuid = uuid or 'shop-%s-%s' % (config.id, os.urandom(4).hex())
            who = (customer or '').strip() or 'Online'

            # Resolve promotions server-side. A typed code that doesn't validate
            # blocks the order (so the customer sees why); auto-promotions just
            # apply. promo_specs carries the discount lines to graft below.
            _pi, promo_specs, promo_code_result = self._promo_for_cart(
                env, config, env['res.partner'], lines, promo_code)
            if promo_code and not (promo_code_result and promo_code_result.get('ok')):
                return self._json({'ok': False, 'error': 'promo_invalid',
                                   'message': (promo_code_result or {}).get('message', 'Invalid promo code')}, status=400)
            promo_discount = round(sum(s['amount'] for s in promo_specs), 2)

            if fulfillment == 'delivery':
                # Structured MENA address (§8). Compose an immutable display snapshot;
                # require at least an area or a legacy free-text address.
                Delivery = env['mezze.delivery']
                addr_parts = {'area': area, 'street': street, 'building': building,
                              'floor': floor, 'apartment': apartment, 'landmark': landmark}
                composed = address or Delivery._compose_address(addr_parts)
                if not (composed or '').strip():
                    return self._json({'ok': False, 'error': 'missing_address'}, status=400)
                mode = payment_mode if payment_mode in ('cod', 'prepaid') else 'cod'
                partner = env['res.partner']
                order_lines, base, incl = self._build_lines(env, config, partner, lines)
                for spec in promo_specs:
                    dl = self._promo_line_vals(config, spec)
                    order_lines.append(dl)
                    incl += dl[2]['price_subtotal_incl']
                    base += dl[2]['price_subtotal']
                # Server-authoritative zone: must exist, be active, belong to this
                # branch, accept COD, be within delivery hours, and meet the minimum.
                zone = env['mezze.delivery.zone'].browse(int(zone_id)) if zone_id \
                    else env['mezze.delivery.zone']
                if not (zone and zone.exists() and zone.active
                        and (not zone.config_id or zone.config_id.id == config.id)):
                    return self._json({'ok': False, 'error': 'out_of_zone',
                                       'message': 'Delivery is not available for this address.'}, status=409)
                if mode == 'cod' and not zone.cod_allowed:
                    return self._json({'ok': False, 'error': 'cod_not_allowed',
                                       'message': 'Cash on delivery is not available for this area.'}, status=409)
                if not zone._is_open(fields.Datetime.now()):
                    return self._json({'ok': False, 'error': 'delivery_closed',
                                       'message': 'Delivery is currently closed.'}, status=409)
                if zone.min_order and incl < zone.min_order:
                    return self._json({'ok': False, 'error': 'below_minimum',
                                       'remaining': round(zone.min_order - incl, 2),
                                       'message': "Add EGP %.2f more for delivery." % (zone.min_order - incl)},
                                      status=409)
                fee = zone.fee
                if fee > 0:
                    fp = self._delivery_fee_product(env)
                    order_lines.append((0, 0, {
                        'product_id': fp.id, 'qty': 1, 'price_unit': fee, 'discount': 0.0,
                        'tax_ids': [(6, 0, [])], 'price_subtotal': fee,
                        'price_subtotal_incl': fee, 'pack_lot_ids': []}))
                    incl += fee
                    base += fee
                # COD → a REAL but UNPAID order (cash collected on delivery, never
                # faked paid here, §30). prepaid → immediate tender (staff/manual only).
                order_dict = {
                    'uuid': uuid, 'session_id': session.id, 'company_id': config.company_id.id,
                    'user_id': env.uid, 'pricelist_id': config.pricelist_id.id or False,
                    'name': 'Mezze %s' % uuid,
                    'date_order': fields.Datetime.to_string(fields.Datetime.now()),
                    'lines': order_lines,
                    'amount_tax': incl - base, 'amount_total': incl,
                    'amount_return': 0.0, 'last_order_preparation_change': empty_preparation_change(), 'to_invoice': False,
                }
                if mode == 'prepaid':
                    pmid = config.payment_method_ids[:1].id
                    order_dict['payment_ids'] = [(0, 0, {'amount': incl, 'name': fields.Datetime.now(),
                                                         'payment_method_id': pmid})]
                    order_dict['amount_paid'] = incl
                else:
                    order_dict['amount_paid'] = 0.0
                env['pos.order'].sync_from_ui([order_dict])
                order = env['pos.order'].search([('uuid', '=', uuid)], limit=1)
                fee_pid = self._delivery_fee_product(env).id
                tickets = self._make_station_tickets(
                    env, order, [(l.product_id, l.qty, self._line_note(env, l.product_id, {}))
                                 for l in order.lines if l.product_id.id != fee_pid and l.qty > 0],
                    'shop:%s' % uuid, 1)
                self._publish_kds(env, tickets, order, natural_key='shop:%s' % uuid)
                dlv = Delivery.create({
                    'pos_order_id': order.id, 'customer_name': who, 'phone': phone or False,
                    'address': composed, 'area': area or False, 'street': street or False,
                    'building': building or False, 'floor': floor or False,
                    'apartment': apartment or False, 'landmark': landmark or False,
                    'fee': fee, 'zone_id': zone.id, 'eta_minutes': zone.eta_minutes,
                    'payment_mode': mode, 'cod_amount': incl if mode == 'cod' else 0.0,
                    'note': note or False, 'state': 'accepted'})
                self._promo_consume(env, order, promo_specs)
                order.mezze_channel = 'delivery'
                stok = order._mezze_ensure_status_token()
                self._audit(env, 'shop.order', order,
                            detail=json.dumps({'fulfillment': 'delivery', 'zone': dlv.zone_id.name,
                                               'payment_mode': mode}, default=str))
                return {'ok': True, 'fulfillment': 'delivery', 'order_id': order.id,
                        'tracking': order.tracking_number or order.pos_reference,
                        'status_token': stok, 'payment_mode': mode,
                        'total': round(order.amount_total, 2), 'fee': fee,
                        'discount': promo_discount, 'eta_minutes': zone.eta_minutes}

            # KIOSK (S4): same pay-at-counter engine as pickup — an UNPAID canonical
            # order that fires to the kitchen; the customer pays the cashier (never
            # faked paid; native Odoo kiosk = Adyen/Stripe-terminal-only, so Mezze
            # kiosk v1 is pay-at-counter). Records the eat-in/takeaway service mode.
            if fulfillment == 'kiosk':
                svc = kw.get('service_mode') if kw.get('service_mode') in ('eat_in', 'takeaway') else 'takeaway'
                # The kiosk is a public terminal: whatever it validated while the
                # customer tapped is a courtesy, not evidence. Re-derive availability,
                # the self-order gate, the offered options and the quantity here, before
                # a single row is written. Combo cardinality is re-checked inside
                # _do_fire on the same principle.
                for line in lines:
                    prod = env['product.product'].browse(int(line.get('product_id') or 0)).exists()
                    if not prod:
                        return self._json({'ok': False, 'error': 'unknown_product',
                                           'message': 'That item is no longer on the menu.'},
                                          status=400)
                    self._assert_available(env, config, prod)
                    self._assert_selforder_allowed(env, 'kiosk', prod)
                    self._assert_customer_config(env, prod, line)
                fire_uuid = 'kiosk:%s' % uuid
                result = self._do_fire(env, uuid, session, config, None, lines,
                                       None, None, fire_uuid, server_override='Kiosk')
                order = env['pos.order'].browse(result.get('order_id'))
                if promo_specs and order.exists():
                    self._promo_apply_to_order(env, config, order, promo_specs)
                stok = None
                if order.exists():
                    order.mezze_channel = 'kiosk'
                    order.mezze_service_mode = svc
                    # What else the guest told the terminal. Each is re-validated
                    # here: a public kiosk's word is a courtesy, not evidence.
                    # NOTE: the receipt preference is NOT read here. The guest is
                    # asked for it on the confirmation screen, after this order
                    # already exists, so it arrives later via /shop/receipt.
                    # the payment option must be one this BRANCH actually offers,
                    # not any code the terminal felt like sending
                    offered = {o.get('code') for o in self._kiosk_payment_options(env, config)}
                    pay_choice = kw.get('payment_code')
                    if pay_choice in offered:
                        order.mezze_pay_choice = pay_choice
                    # A phone number turns an anonymous kiosk order into a named one,
                    # which is what makes loyalty and a re-order history possible. An
                    # EXISTING customer is reused; a new one is created with the phone
                    # only -- a kiosk collects no name and must not invent one.
                    partner = self._kiosk_partner(env, phone)
                    if partner:
                        order.partner_id = partner.id
                    stok = order._mezze_ensure_status_token()
                self._audit(env, 'shop.order', order,
                            detail=json.dumps({'fulfillment': 'kiosk', 'service_mode': svc,
                                               'receipt': order.mezze_receipt_pref or None,
                                               'pay_choice': order.mezze_pay_choice or None,
                                               'partner': order.partner_id.id or None},
                                              default=str))
                return {'ok': True, 'fulfillment': 'kiosk', 'service_mode': svc,
                        'order_id': result.get('order_id'), 'payment_mode': 'pay_at_counter',
                        'tracking': result.get('tracking') or result.get('pos_reference'),
                        'status_token': stok,
                        'total': round(order.amount_total, 2) if order.exists() else result.get('amount_total'),
                        'discount': promo_discount, 'eta_minutes': 15}

            # pickup: draft fires to the kitchen; paid at the counter on collect
            fire_uuid = 'shop:%s' % uuid
            result = self._do_fire(env, uuid, session, config, None, lines,
                                   None, None, fire_uuid, server_override='Online pickup')
            order = env['pos.order'].browse(result.get('order_id'))
            # graft any promo discount onto the draft before it's collected/paid
            if promo_specs and order.exists():
                self._promo_apply_to_order(env, config, order, promo_specs)
            stok = None
            if order.exists():
                order.mezze_channel = 'pickup'
                stok = order._mezze_ensure_status_token()
            self._audit(env, 'shop.order', order,
                        detail=json.dumps({'fulfillment': 'pickup', 'who': who,
                                           'phone': phone}, default=str))
            return {'ok': True, 'fulfillment': 'pickup', 'order_id': result.get('order_id'),
                    'tracking': result.get('tracking') or result.get('pos_reference'),
                    'status_token': stok,
                    'total': round(order.amount_total, 2) if order.exists() else result.get('amount_total'),
                    'discount': promo_discount, 'eta_minutes': 20}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze shop_order failed")
            return self._json({'ok': False, 'error': 'shop_order_failed', 'message': str(exc)}, status=400)

    @http.route(f'{API_PREFIX}/shop/status', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def shop_status(self, token=None, **kw):
        """O1 §14 — the ONE customer order-status contract. Accepts only the OPAQUE
        status token (never a sequential id), returns a SAFE public status, and is
        rate-limited against token guessing. Never leaks staff/internal fields or
        another order's data."""
        env = self._api_env()
        # rate-limit status-token guessing per client (low-risk read -> fail open)
        try:
            ip = request.httprequest.remote_addr or 'anon'
            allowed, retry, _c = env['mezze.rate.limit'].hit(
                'shop_status:%s' % ip, limit=40, window_seconds=60, fail_mode='open')
            if not allowed:
                return self._json({'ok': False, 'error': 'rate_limited'}, status=429,
                                  )
        except Exception:  # noqa: BLE001
            pass
        tok = (token or '').strip()
        if not tok or len(tok) < 24:
            return self._json({'ok': False, 'error': 'bad_token'}, status=400)
        # P1: resolve via the HASH (expiry + revocation enforced); generic 404 on any miss.
        order = env['pos.order']._mezze_resolve_status_token(tok)
        if not order:
            return self._json({'ok': False, 'error': 'not_found'}, status=404)   # generic, no leak
        return {'ok': True, 'status': order.mezze_public_status(),
                'channel': order.mezze_channel or 'pos',
                'tracking': order.tracking_number or order.pos_reference or '',
                'total': round(order.amount_total, 2),
                'paid': round(order.amount_paid, 2)}

    # ------------------------------------------------------------------
    # S4 — self-order channel governance (pause/resume) + health + analytics
    # ------------------------------------------------------------------
    _SELFORDER_CHANNELS = ('qr', 'pickup', 'delivery', 'kiosk')

    def _selforder_paused_key(self, config):
        return 'mezze_bridge.selforder_paused_%s' % config.id

    def _selforder_paused_set(self, env, config):
        raw = env['ir.config_parameter'].sudo().get_param(self._selforder_paused_key(config)) or ''
        try:
            return set(json.loads(raw)) if raw else set()
        except (ValueError, TypeError):
            return set()

    def _selforder_paused(self, env, config, channel):
        """True if staff paused this self-order channel for the branch (register stays
        open for the cashier). Never trusts the client."""
        return channel in self._selforder_paused_set(env, config)

    @http.route(f'{API_PREFIX}/selforder/status', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def selforder_status(self, store=None, config_id=None, **kw):
        """Public self-order health: which customer channels are available right now
        (open session AND not paused). No branch internals leaked."""
        try:
            env = self._api_env()
            config = self._store_config(env, store) if store else (
                env['pos.config'].browse(int(config_id)) if config_id else env['pos.config'].search([], limit=1))
            if not config or not config.exists():
                return self._json({'ok': False, 'error': 'not_found'}, status=404)
            has_session = bool(env['pos.session'].sudo().search_count(
                [('config_id', '=', config.id), ('state', '=', 'opened')]))
            paused = self._selforder_paused_set(env, config)
            return {'ok': True, 'open': has_session,
                    'channels': {c: (has_session and c not in paused) for c in self._SELFORDER_CHANNELS}}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze selforder_status failed")
            return self._json({'ok': False, 'error': 'status_failed', 'message': str(exc)}, status=400)

    @http.route(f'{API_PREFIX}/selforder/pause', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*', readonly=False)
    def selforder_pause(self, config_id=None, channel=None, paused=True, **kw):
        """Staff: pause/resume a self-order channel (qr/pickup/delivery/kiosk) for a
        branch WITHOUT closing the register."""
        auth = self._authorize('selforder/pause')
        if auth:
            return auth
        try:
            env = self._api_env()
            config = env['pos.config'].browse(int(config_id)) if config_id else env['pos.config'].search([], limit=1)
            if not config.exists():
                return self._json({'ok': False, 'error': 'not_found'}, status=404)
            if channel not in self._SELFORDER_CHANNELS:
                return self._json({'ok': False, 'error': 'bad_channel'}, status=400)
            cur = self._selforder_paused_set(env, config)
            if str(paused).strip().lower() not in ('0', 'false', 'no'):
                cur.add(channel)
            else:
                cur.discard(channel)
            env['ir.config_parameter'].sudo().set_param(
                self._selforder_paused_key(config), json.dumps(sorted(cur)))
            self._audit(env, 'selforder.pause', **self._actor(env, kw),
                        detail=json.dumps({'channel': channel, 'paused': channel in cur}, default=str))
            return {'ok': True, 'channel': channel, 'paused': channel in cur, 'paused_channels': sorted(cur)}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze selforder_pause failed")
            return self._json({'ok': False, 'error': 'pause_failed', 'message': str(exc)}, status=400)

    @http.route(f'{API_PREFIX}/selforder/report', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def selforder_report(self, config_id=None, since=None, **kw):
        """Self-order analytics by channel (§68): orders / revenue / AOV / payment mix
        / cancellations, plus most-ordered items. Reuses mezze_channel; no ad-tech."""
        auth = self._authorize('selforder/report')
        if auth:
            return auth
        try:
            env = self._api_env()
            dom = self._mezze_scope_base(env, config_id) + \
                [('mezze_channel', 'in', list(self._SELFORDER_CHANNELS) + ['qr', 'pos'])]
            if since:
                dom.append(('date_order', '>=', since))
            orders = env['pos.order'].sudo().search(dom)
            by_channel, items = {}, {}
            paid = due = revenue = 0.0
            cancelled = 0
            fee_code = 'MEZZE_DELIVERY_FEE'
            for o in orders:
                ch = o.mezze_channel or 'pos'
                b = by_channel.setdefault(ch, {'orders': 0, 'revenue': 0.0})
                b['orders'] += 1
                b['revenue'] = round(b['revenue'] + o.amount_total, 2)
                revenue += o.amount_total
                if o.state == 'cancel':
                    cancelled += 1
                if round(o.amount_paid, 2) >= round(o.amount_total, 2) and o.amount_total:
                    paid += 1
                else:
                    due += 1
                for l in o.lines:
                    if l.product_id.default_code == fee_code or l.qty <= 0:
                        continue
                    items[l.product_id.display_name] = items.get(l.product_id.display_name, 0) + l.qty
            top = sorted(items.items(), key=lambda kv: kv[1], reverse=True)[:10]
            n = len(orders)
            return {'ok': True, 'total': n, 'revenue': round(revenue, 2),
                    'aov': round(revenue / n, 2) if n else 0.0,
                    'by_channel': by_channel, 'paid': paid, 'payment_due': due,
                    'cancellations': cancelled,
                    'top_items': [{'name': k, 'qty': v} for k, v in top]}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze selforder_report failed")
            return self._json({'ok': False, 'error': 'report_failed', 'message': str(exc)}, status=400)

    # ------------------------------------------------------------------
    # Customer feedback — post-order rating + comment (mezze.feedback)
    # ------------------------------------------------------------------
    @http.route(f'{API_PREFIX}/feedback/submit', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*', readonly=False)
    def feedback_submit(self, store=None, rating=None, comment=None, customer=None,
                        phone=None, order_ref=None, **kw):
        """Public (store-token gated): a shopper rates their order 1–5 with an
        optional comment. Optionally links to the order by its receipt/tracking."""
        env = self._api_env()
        try:
            config = self._store_config(env, store)
            r = int(rating or 0)
            if not (1 <= r <= 5):
                return self._json({'ok': False, 'error': 'bad_rating',
                                   'message': 'Rating must be between 1 and 5'}, status=400)
            order = env['pos.order']
            if order_ref:
                order = env['pos.order'].search(
                    ['|', ('pos_reference', '=', str(order_ref)),
                     ('tracking_number', '=', str(order_ref))], limit=1)
            fb = env['mezze.feedback'].create({
                'config_id': config.id, 'pos_order_id': order.id or False, 'rating': r,
                'comment': (comment or '').strip() or False,
                'customer_name': (customer or '').strip() or False,
                'phone': (phone or '').strip() or False})
            self._audit(env, 'feedback.submit',
                        detail=json.dumps({'rating': r, 'config_id': config.id}, default=str))
            return {'ok': True, 'id': fb.id, 'rating': r}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze feedback submit failed")
            return self._json({'ok': False, 'error': 'feedback_failed', 'message': str(exc)}, status=400)

    @http.route(f'{API_PREFIX}/feedback/list', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def feedback_list(self, config_id=None, limit=40, **kw):
        """Manager: recent feedback + average rating + star distribution."""
        auth = self._authorize()
        if auth:
            return auth
        env = self._api_env()
        try:
            config = self._resolve_config(env, config_id)
            allfb = env['mezze.feedback'].search([('config_id', '=', config.id)])
            n = len(allfb)
            avg = round(sum(allfb.mapped('rating')) / n, 2) if n else 0.0
            dist = {i: 0 for i in range(1, 6)}
            for f in allfb:
                dist[f.rating] = dist.get(f.rating, 0) + 1
            recent = allfb.sorted(lambda f: (f.create_date or fields.Datetime.now()),
                                  reverse=True)[:int(limit or 40)]
            return {'ok': True, 'count': n, 'avg': avg, 'distribution': dist,
                    'items': [{
                        'id': f.id, 'rating': f.rating, 'comment': f.comment or '',
                        'who': f.customer_name or 'Guest',
                        'order': f.pos_order_id.pos_reference or None,
                        'date': fields.Datetime.to_string(f.create_date) if f.create_date else None,
                    } for f in recent]}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze feedback list failed")
            return self._json({'ok': False, 'error': 'feedback_list_failed', 'message': str(exc)}, status=400)

    # ------------------------------------------------------------------
    # Marketing — customer campaigns over email / SMS / WhatsApp
    # ------------------------------------------------------------------
    SEGMENTS = ['all', 'loyalty', 'recent']

    def _mkt_field(self, channel):
        return 'email' if channel == 'email' else 'phone'   # sms/whatsapp → phone

    def _mkt_audience(self, env, segment, channel):
        """Reachable partners for a segment on a channel (must have the channel's
        contact field). Segments: all customers · loyalty members · recent diners."""
        field = self._mkt_field(channel)
        dom = [(field, '!=', False)]
        if segment == 'loyalty':
            cards = env['loyalty.card'].sudo().search([])
            dom.append(('id', 'in', cards.mapped('partner_id').ids))
        elif segment == 'recent':
            since = fields.Datetime.to_string(
                fields.Datetime.now() - datetime.timedelta(days=30))
            orders = env['pos.order'].sudo().search(
                [('date_order', '>=', since), ('partner_id', '!=', False)])
            dom.append(('id', 'in', orders.mapped('partner_id').ids))
        else:
            dom.append(('customer_rank', '>', 0))
        return env['res.partner'].sudo().search(dom)

    @http.route(f'{API_PREFIX}/marketing/segments', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def marketing_segments(self, config_id=None, channel='email', **kw):
        """Audience size per segment for a channel — so the composer previews reach."""
        auth = self._authorize()
        if auth:
            return auth
        env = self._api_env()
        try:
            out = {}
            for seg in self.SEGMENTS:
                out[seg] = len(self._mkt_audience(env, seg, channel))
            return {'ok': True, 'channel': channel, 'counts': out,
                    'whatsapp_ready': bool(env['ir.config_parameter'].sudo()
                                           .get_param('mezze_bridge.whatsapp_token'))}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze marketing_segments failed")
            return self._json({'ok': False, 'error': 'segments_failed', 'message': str(exc)}, status=400)

    @http.route(f'{API_PREFIX}/marketing/send', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*', readonly=False)
    def marketing_send(self, config_id=None, channel='email', segment='all',
                       subject=None, body=None, name=None, **kw):
        """Dispatch a campaign to a segment. Email → native mail.mail; SMS → native
        sms.sms (queued; needs a gateway to leave); WhatsApp → queued pending a
        Meta Cloud token. Records a mezze.campaign for the back-office history."""
        auth = self._authorize()
        if auth:
            return auth
        env = self._api_env()
        try:
            if channel not in ('email', 'sms', 'whatsapp'):
                raise ValueError("Unknown channel %s" % channel)
            if not (body or '').strip():
                raise ValueError("Message body is required")
            config = self._resolve_config(env, config_id)
            partners = self._mkt_audience(env, segment, channel)
            sent, state = 0, 'sent'
            if channel == 'email':
                for p in partners:
                    env['mail.mail'].sudo().create({
                        'subject': (subject or 'Mezze').strip(),
                        'body_html': '<p>%s</p>' % (body or '').strip(),
                        'email_to': p.email, 'auto_delete': False})
                    sent += 1
                state = 'sent'                          # queued to Odoo outbox
            elif channel == 'sms':
                for p in partners:
                    env['sms.sms'].sudo().create({'number': p.phone, 'body': (body or '').strip()})
                    sent += 1
                state = 'queued'                        # needs SMS gateway / IAP
            else:                                       # whatsapp — gated on Meta Cloud token
                sent, state = 0, 'queued'
            camp = env['mezze.campaign'].sudo().create({
                'name': (name or '').strip() or '%s · %s' % (channel.title(), segment),
                'config_id': config.id, 'channel': channel, 'segment': segment,
                'subject': (subject or '').strip() or False, 'body': (body or '').strip(),
                'state': state, 'audience_count': len(partners), 'sent_count': sent})
            self._audit(env, 'marketing.send', **self._actor(env, kw),
                        detail=json.dumps({'channel': channel, 'segment': segment,
                                           'audience': len(partners), 'sent': sent}, default=str))
            return {'ok': True, 'campaign_id': camp.id, 'channel': channel,
                    'audience': len(partners), 'sent': sent, 'state': state,
                    'note': ('Queued — needs a live gateway to leave' if state == 'queued'
                             else 'Queued to the Odoo mail outbox')}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze marketing_send failed")
            return self._json({'ok': False, 'error': 'marketing_send_failed', 'message': str(exc)}, status=400)

    @http.route(f'{API_PREFIX}/marketing/campaigns', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def marketing_campaigns(self, config_id=None, limit=30, **kw):
        """Recent campaigns for the back-office history."""
        auth = self._authorize()
        if auth:
            return auth
        env = self._api_env()
        try:
            config = self._resolve_config(env, config_id)
            camps = env['mezze.campaign'].sudo().search(
                [('config_id', '=', config.id)], order='create_date desc', limit=int(limit or 30))
            return {'ok': True, 'items': [{
                'id': c.id, 'name': c.name, 'channel': c.channel, 'segment': c.segment,
                'state': c.state, 'audience': c.audience_count, 'sent': c.sent_count,
                'date': fields.Datetime.to_string(c.create_date) if c.create_date else None,
            } for c in camps]}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze marketing_campaigns failed")
            return self._json({'ok': False, 'error': 'campaigns_failed', 'message': str(exc)}, status=400)

    # ------------------------------------------------------------------
    # Session close — reuse core close so accounting posts
    # ------------------------------------------------------------------
    @http.route(f'{API_PREFIX}/sessions/<int:session_id>/close/preview', type='json2',
                auth='none', methods=['POST'], csrf=False, cors='*', readonly=True)
    def session_close_preview(self, session_id, **kw):
        """What closing this session would post — read-only, and readable by the till.

        Deliberately a LOWER capability than the close itself. A cashier counting
        a drawer at 1am needs to see the numbers before fetching a manager; asking
        for a manager's PIN just to look would mean the PIN gets typed twice, and a
        PIN typed twice is a PIN learned by whoever is watching.

        Nothing here is a decision: the close endpoint re-authorises independently.
        """
        auth = self._authorize(endpoint='sessions/<int:session_id>/close/preview')
        if auth:
            return auth
        try:
            env = self._api_env()
            session = env['pos.session'].browse(int(session_id))
            if not session.exists():
                return self._json({'ok': False, 'error': 'unknown_session'}, status=404)
            denied = self._security_gate(
                env, 'sessions/<int:session_id>/close/preview', target=session)
            if denied:
                return denied

            orders = session.order_ids
            unpaid = orders.filtered(lambda o: o.state == 'draft')
            by_method = {}
            for pay in orders.mapped('payment_ids'):
                m = pay.payment_method_id
                row = by_method.setdefault(m.id, {
                    'id': m.id, 'name': m.name, 'is_cash': bool(m.is_cash_count),
                    'amount': 0.0, 'count': 0})
                row['amount'] += pay.amount
                row['count'] += 1

            cash_start, cash_payments, cash_expected = _cash_position(session)
            return {
                'ok': True,
                'session': session.name,
                'session_id': session.id,
                'state': session.state,
                'branch': {'id': session.config_id.id, 'name': session.config_id.name},
                'opened_at': fields.Datetime.to_string(session.start_at) if session.start_at else None,
                'orders': len(orders),
                # An open draft is the one thing that should stop a close, so it is
                # reported as a number the screen can refuse on, not buried.
                'orders_open': len(unpaid),
                'total': sum(orders.mapped('amount_total')),
                'payments': sorted(by_method.values(), key=lambda r: r['name'] or ''),
                'cash_opening': cash_start,
                'cash_payments': cash_payments,
                'cash_expected': cash_expected,
                'currency': session.config_id.currency_id.name or '',
                # The notes and coins this branch actually handles, so the drawer can
                # be counted IN the software instead of on a scrap of paper beside it.
                # `pos.bill` is core's model and this is core's own rule for which
                # ones apply: the ones attached to this config, plus the global ones.
                'denominations': [
                    {'id': b.id, 'name': b.name or ('%g' % b.value), 'value': b.value}
                    for b in env['pos.bill'].sudo().search(
                        ['|', ('id', 'in', session.config_id.default_bill_ids.ids),
                         ('pos_config_ids', '=', False)], order='value desc')
                ],
            }
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze close preview failed for session_id=%s", session_id)
            return self._json({'ok': False, 'error': 'preview_failed',
                               'message': str(exc)}, status=400)

    @http.route(f'{API_PREFIX}/sessions/<int:session_id>/z_report', type='json2',
                auth='none', methods=['POST'], csrf=False, cors='*', readonly=True)
    def session_z_report(self, session_id, **kw):
        """The shift's Z report — Odoo's own, not a second implementation.

        Mezze had no Z report. The only thing in the repository that looked like one
        was the design prototype in ``static/pos.html``, whose figures are literals
        ("EGP 38,940") — a picture of a report, not a report.

        Writing one from scratch would have meant re-deriving gross, refunds, tax per
        rate, discounts and per-method takings from the orders, which is exactly the
        arithmetic ``report.point_of_sale.report_saledetails`` already does and is
        already tested by Odoo. It splits refunds out from sales rather than netting
        them (a Z report that reports only the net hides the day's returns), reports
        tax per rate, and reports the cash count with its difference and every cash
        in/out. It is reused verbatim here.

        Read-only, and the SAME capability as the close preview — a cashier must be
        able to print the shift summary without holding the right to post the closing
        entry. The close endpoint re-authorises independently.
        """
        auth = self._authorize(endpoint='sessions/<int:session_id>/z_report')
        if auth:
            return auth
        try:
            env = self._api_env()
            session = env['pos.session'].browse(int(session_id))
            if not session.exists():
                return self._json({'ok': False, 'error': 'unknown_session'}, status=404)
            denied = self._security_gate(
                env, 'sessions/<int:session_id>/z_report', target=session)
            if denied:
                return denied

            details = env['report.point_of_sale.report_saledetails'].sudo() \
                .get_sale_details(session_ids=[session.id])
            config = session.config_id
            currency = config.currency_id

            # Gross and refunds SEPARATELY. `amount_total` on a refund order is
            # negative, so summing every order yields the net and silently reports a
            # day with heavy returns as a quiet day.
            orders = session.order_ids.filtered(lambda o: o.state in ('paid', 'done', 'invoiced'))
            sales = orders.filtered(lambda o: o.amount_total >= 0)
            refunds = orders - sales
            gross = sum(sales.mapped('amount_total'))
            refunded = abs(sum(refunds.mapped('amount_total')))
            tax_total = sum(o.amount_tax for o in orders)
            change_given = sum(o.amount_return for o in orders)

            def _tax_rows(key):
                return [{'name': t.get('name') or '',
                         'base': round(t.get('base_amount') or 0.0, 2),
                         'amount': round(t.get('tax_amount') or 0.0, 2)}
                        for t in (details.get(key) or [])]

            return {
                'ok': True,
                'session': session.name,
                'session_id': session.id,
                'state': session.state,
                'branch': {'id': config.id, 'name': config.name},
                'company': details.get('company_name') or env.company.name,
                'opened_at': fields.Datetime.to_string(session.start_at) if session.start_at else None,
                'closed_at': fields.Datetime.to_string(session.stop_at) if session.stop_at else None,
                'currency': currency.name or '',
                'orders': details.get('nbr_orders') or 0,
                'refund_orders': len(refunds),
                'gross': round(gross, 2),
                'refunds': round(refunded, 2),
                'net': round(gross - refunded, 2),
                'tax': round(tax_total, 2),
                'change_given': round(change_given, 2),
                'taxes': _tax_rows('taxes'),
                'refund_taxes': _tax_rows('refund_taxes'),
                'discount_orders': details.get('discount_number') or 0,
                'discount_amount': round(details.get('discount_amount') or 0.0, 2),
                # Per method, plus the cash count row core builds with its own
                # difference and cash in/out list.
                'payments': [{'name': p.get('name') or '',
                              'total': round(p.get('total') or 0.0, 2),
                              'is_cash_count': bool(p.get('count')),
                              'counted': round(p.get('money_counted') or 0.0, 2),
                              'expected': round(p.get('final_count') or 0.0, 2),
                              'difference': round(p.get('money_difference') or 0.0, 2),
                              'cash_moves': p.get('cash_moves') or []}
                             for p in (details.get('payments') or [])],
                'products': details.get('products') or [],
                'opening_note': details.get('opening_note') or '',
                'closing_note': details.get('closing_note') or '',
            }
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze z_report failed for session_id=%s", session_id)
            return self._json({'ok': False, 'error': 'z_report_failed',
                               'message': str(exc)}, status=400)

    @http.route(f'{API_PREFIX}/sessions/<int:session_id>/close', type='json2',
                auth='none', methods=['POST'], csrf=False, cors='*', readonly=False)
    def session_close(self, session_id, **kw):
        auth = self._authorize()
        if auth:
            return auth
        try:
            env = self._api_env()
            session = env['pos.session'].browse(int(session_id))
            if not session.exists():
                return self._json({'ok': False, 'error': 'unknown_session',
                                   'message': "Unknown session_id %s" % session_id},
                                  status=404)
            # object authorization: the session's authoritative branch/company must
            # be the principal's (a session id from another branch is denied).
            denied = self._security_gate(env, 'sessions/<int:session_id>/close', target=session)
            if denied:
                return denied
            env = env(context=dict(env.context, allowed_company_ids=[session.config_id.company_id.id], company_id=session.config_id.company_id.id))
            session = session.with_env(env)

            # ---- COUNTED CASH -------------------------------------------------
            # This endpoint used to accept no counted amount at all. It computed
            # what the drawer *should* hold and told the cashier to count it
            # outside the software — so Mezze could not reconcile its own till, and
            # ``cash_register_difference`` was only ever READ, in one GL report.
            counted = kw.get('counted_cash')
            # A DENOMINATION BREAKDOWN may be sent instead of, or alongside, the
            # total. Counting a drawer note by note is how the figure is actually
            # arrived at, and keeping the breakdown makes a variance investigable
            # afterwards — "short by 50" is a mystery, "one 50 note missing" is not.
            #
            # When both arrive they must AGREE. A total that does not match the notes
            # behind it is not a count, and silently trusting either one would hide
            # whichever is wrong.
            breakdown = kw.get('denominations')
            counted_from_notes = None
            if breakdown:
                try:
                    counted_from_notes = round(sum(
                        float(row['value']) * int(row['count'])
                        for row in breakdown if row.get('count')), 2)
                except (TypeError, ValueError, KeyError):
                    return self._json({'ok': False, 'error': 'bad_denominations',
                                       'message': 'The drawer count could not be read.'},
                                      status=400)
                if counted is None or counted == '':
                    counted = counted_from_notes
                else:
                    try:
                        stated = float(counted)
                    except (TypeError, ValueError):
                        return self._json({'ok': False, 'error': 'bad_counted_cash'},
                                          status=400)
                    if abs(stated - counted_from_notes) > 0.005:
                        return self._json(
                            {'ok': False, 'error': 'count_mismatch',
                             'message': 'The notes counted do not add up to the '
                                        'total entered.',
                             'counted': stated, 'from_notes': counted_from_notes},
                            status=400)
            cash_start, cash_payments, expected = _cash_position(session)
            difference = None
            if counted is not None and counted != '':
                try:
                    counted = float(counted)
                except (TypeError, ValueError):
                    return self._json({'ok': False, 'error': 'bad_counted_cash'},
                                      status=400)
                difference = round(counted - expected, 2)
                # Odoo's own ceiling, which Mezze never read. Over it, a manager
                # stands behind the variance in person — a drawer that is short by
                # more than the branch tolerates is an incident, not a rounding.
                if session.config_id.set_maximum_difference:
                    ceiling = abs(session.config_id.amount_authorized_diff or 0.0)
                    if ceiling and abs(difference) > ceiling:
                        approver, _err = self._verify_inline_approver(
                            env, kw.get('manager_code'), kw.get('manager_pin'),
                            min_rank=1)
                        if not approver:
                            self._audit(env, 'session.close_refused',
                                        severity='warning', **self._actor(env, kw),
                                        detail=json.dumps(
                                            {'session': session.name,
                                             'expected': expected, 'counted': counted,
                                             'difference': difference,
                                             'ceiling': ceiling}, default=str))
                            return self._json(
                                {'ok': False, 'error': 'variance_requires_approval',
                                 'message': 'The drawer is out by more than this '
                                            'branch allows. A manager must approve.',
                                 'expected': expected, 'counted': counted,
                                 'difference': difference, 'ceiling': ceiling},
                                status=403)
                        kw['approver_cashier_id'] = approver.id
                if 'cash_register_balance_end_real' in session._fields:
                    session.sudo().write(
                        {'cash_register_balance_end_real': counted})

            if session.state != 'closed':
                # Core close entry point: closing_control -> validate ->
                # _create_account_move -> post. Produces the journal entry.
                session.action_pos_session_closing_control()

            move = session.move_id
            # A close is the most consequential act of a shift and it wrote NO audit
            # row, while ~80 lesser events did.
            self._audit(env, 'session.close', severity='warning',
                        **self._actor(env, kw),
                        detail=json.dumps({
                            'session': session.name, 'session_id': session.id,
                            'orders': len(session.order_ids),
                            'cash_opening': cash_start,
                            'cash_payments': cash_payments,
                            'cash_expected': expected,
                            'cash_counted': counted if counted != '' else None,
                            'cash_difference': difference,
                            # Kept so a variance can be investigated rather than
                            # merely recorded: "short by 50" is a mystery, "one 50
                            # note missing" is somewhere to start.
                            'cash_denominations': [
                                {'value': r.get('value'), 'count': r.get('count')}
                                for r in (breakdown or []) if r.get('count')
                            ] or None,
                            'approver_cashier_id': kw.get('approver_cashier_id'),
                            'move_ids': move.ids}, default=str))
            return {
                'ok': True,
                'session': session.name,
                'session_id': session.id,
                'state': session.state,
                'cash_opening': cash_start,
                'cash_payments': cash_payments,
                'cash_expected': round(expected, 2),
                'cash_counted': counted if counted not in (None, '') else None,
                'cash_difference': difference,
                'account_move_ids': move.ids,
                'account_move_names': move.mapped('name'),
                'balance': sum(move.line_ids.mapped('balance')) if move else 0.0,
            }
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze session close failed for session_id=%s", session_id)
            return self._json({
                'ok': False,
                'error': 'close_failed',
                'session_id': session_id,
                'message': str(exc),
            }, status=400)

    @http.route(f'{API_PREFIX}/sessions/<int:session_id>/cash_move', type='json2',
                auth='none', methods=['POST'], csrf=False, cors='*', readonly=False)
    def session_cash_move(self, session_id, direction=None, amount=None, reason=None,
                          **kw):
        """Take money out of the drawer, or put money in.

        Mezze had no endpoint, no model and no screen for this — so a float top-up,
        a supplier paid in cash, or a till skim had nowhere to be recorded, and the
        drawer reconciled against a figure that had never heard of them.

        It delegates to Odoo's own ``pos.session.try_cash_in_out``, which writes a
        real ``account.bank.statement.line`` on the session's cash journal. Writing
        statement lines by hand here would produce money the session close does not
        know how to account for.
        """
        auth = self._authorize(endpoint='sessions/<int:session_id>/cash_move')
        if auth:
            return auth
        env = self._api_env()
        try:
            session = env['pos.session'].browse(int(session_id))
            if not session.exists():
                return self._json({'ok': False, 'error': 'unknown_session'}, status=404)
            denied = self._security_gate(
                env, 'sessions/<int:session_id>/cash_move', target=session)
            if denied:
                return denied
            if session.state == 'closed':
                return self._json({'ok': False, 'error': 'session_closed'}, status=400)
            direction = str(direction or '').lower()
            if direction not in ('in', 'out'):
                return self._json({'ok': False, 'error': 'bad_direction',
                                   'message': "direction must be 'in' or 'out'."},
                                  status=400)
            try:
                amount = float(amount)
            except (TypeError, ValueError):
                amount = 0.0
            if amount <= 0:
                return self._json({'ok': False, 'error': 'bad_amount',
                                   'message': 'A cash move needs a positive amount.'},
                                  status=400)
            reason = (reason or '').strip()
            if not reason:
                # Unexplained money leaving a till is the thing this record exists to
                # prevent, so the reason is required rather than encouraged.
                return self._json({'ok': False, 'error': 'reason_required',
                                   'message': 'Say what this cash move is for.'},
                                  status=400)
            env = env(context=dict(
                env.context,
                allowed_company_ids=[session.config_id.company_id.id],
                company_id=session.config_id.company_id.id))
            session = session.with_env(env)
            # ``extras['translatedType']`` is not optional: core composes the
            # statement line's payment_ref from it, so omitting it raises a KeyError
            # rather than defaulting.
            label = 'Cash In' if direction == 'in' else 'Cash Out'
            session.sudo().try_cash_in_out(
                direction, amount, reason, False,
                {'translatedType': label, 'formattedAmount': ''})
            self._audit(env, 'session.cash_move', severity='warning',
                        **self._actor(env, kw),
                        detail=json.dumps({'session': session.name,
                                           'session_id': session.id,
                                           'direction': direction, 'amount': amount,
                                           'reason': reason}, default=str))
            return {'ok': True, 'session_id': session.id, 'direction': direction,
                    'amount': round(amount, 2), 'reason': reason}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze cash move failed")
            return self._json({'ok': False, 'error': 'cash_move_failed',
                               'message': str(exc)}, status=400)

    #: A tip larger than this share of the bill is almost always a typo — a
    #: cashier meaning 5.00 and typing 500. Core warns at 25%; Mezze refuses above
    #: a configurable ceiling, because a warning on a busy till is a thing people
    #: learn to tap through.
    TIP_SANITY_RATIO = 1.0

    def _tip_ceiling(self, env, order):
        raw = env['ir.config_parameter'].sudo().get_param(
            'mezze_bridge.tip_max_ratio', '')
        try:
            ratio = float(raw) if str(raw).strip() else self.TIP_SANITY_RATIO
        except (TypeError, ValueError):
            ratio = self.TIP_SANITY_RATIO
        base = sum(l.price_subtotal_incl for l in order.lines
                   if l.product_id != order.config_id.tip_product_id)
        return round(max(0.0, base) * max(0.0, ratio), 2)

    @http.route(f'{API_PREFIX}/orders/tip', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*', readonly=False)
    def order_tip(self, order_id=None, uuid=None, amount=None,
                  expected_revision=None, **kw):
        """Take a tip at the till — before the tender, or after it.

        Mezze could already put a tip on a bill and only a GUEST could do it: the
        QR path took one and the cashier had no way to. On a card, that is the
        common case rather than the rare one — the slip comes back with a figure
        written on it, and somebody has to put it into the till.

        The mechanics are core's, deliberately: a line on the native tip product
        (so it reconciles as revenue through a real product and account) plus
        ``is_tipped``/``tip_amount``, which is what every Odoo report and the
        session close already read. Mezze adds the parts a browser cannot be
        trusted with.

        **Before payment** the tip simply joins the bill and the tender covers it.

        **After payment** the settling payment has to grow by the tip, and that is
        where this refuses to be casual. If the order was settled on an INTEGRATED
        terminal, the amount the provider captured is the authoritative one: writing
        a larger figure into Odoo would make the day's takings disagree with the
        settlement file, and the difference would surface a month later as an
        unexplained variance nobody can trace back to a Tuesday. So a post-payment
        tip is accepted on methods where the cashier IS the authority — cash and
        manual/external tenders — and refused on an integrated one with a reason
        that names the fix (capture it on the terminal).
        """
        auth = self._authorize(endpoint='orders/tip')
        if auth:
            return auth
        env = self._api_env()
        # ``_reward_order`` and not a new ``_resolve_order``: this addon already
        # learned that two same-named private helpers on two http.Controller classes
        # silently shadow each other and break an unrelated endpoint.
        order = self._reward_order(env, order_id, uuid)
        stale = self._assert_revision(order, expected_revision)
        if stale:
            return stale
        if not order:
            return self._json({'ok': False, 'error': 'unknown_order'}, status=404)
        denied = self._security_gate(env, 'orders/tip', target=order)
        if denied:
            return denied
        try:
            tip = round(float(amount), 2)
        except (TypeError, ValueError):
            return self._json({'ok': False, 'error': 'bad_amount'}, status=400)
        if tip < 0:
            return self._json({'ok': False, 'error': 'negative_tip'}, status=400)
        if order.state in ('cancel',):
            return self._json({'ok': False, 'error': 'order_cancelled'}, status=400)

        ceiling = self._tip_ceiling(env, order)
        if tip > ceiling and ceiling > 0:
            return self._json({'ok': False, 'error': 'tip_implausible',
                               'ceiling': ceiling, 'amount': tip,
                               'message': 'That tip is larger than the bill. '
                                          'Check the amount.'}, status=400)

        config = order.config_id
        tip_product = self._tip_product(env, config)
        paid_before = round(sum(order.payment_ids.mapped('amount')), 2)
        settled = order.state in ('paid', 'done', 'invoiced')

        # One tip per order: adjusting it REPLACES the line rather than stacking a
        # second one, or a cashier correcting 5.00 to 15.00 has given away 20.00.
        existing = order.lines.filtered(lambda l: l.product_id == tip_product)
        if settled and existing:
            return self._json({'ok': False, 'error': 'already_tipped',
                               'tip': round(sum(existing.mapped('price_subtotal_incl')), 2),
                               'message': 'This order already carries a tip.'},
                              status=409)

        if settled:
            # The payment that settled it has to grow. Only where the cashier is
            # the authority on what was collected.
            paylines = order.payment_ids.filtered(lambda p: p.amount > 0)
            target = paylines.sorted(lambda p: p.amount)[-1:] if paylines else paylines
            if not target:
                return self._json({'ok': False, 'error': 'no_payment_to_adjust'},
                                  status=400)
            method = target.payment_method_id
            integrated = (getattr(method, 'mezze_mode', '') == 'odoo_terminal'
                          or bool(getattr(method, 'use_payment_terminal', False)))
            if integrated:
                return self._json(
                    {'ok': False, 'error': 'tip_needs_provider_capture',
                     'method': method.name,
                     'message': 'This order was settled on a payment terminal. '
                                'Add the tip on the terminal so the captured '
                                'amount matches.'}, status=409)

        if existing:
            existing.unlink()
        if tip > 0:
            env['pos.order.line'].sudo().create({
                'order_id': order.id, 'product_id': tip_product.id, 'qty': 1,
                'price_unit': tip, 'discount': 0.0, 'tax_ids': [(6, 0, [])],
                'price_subtotal': tip, 'price_subtotal_incl': tip})
        order.sudo().write({'is_tipped': bool(tip), 'tip_amount': tip})

        if settled and tip > 0:
            target.sudo().write({'amount': round(target.amount + tip, 2)})

        # ``amount_total`` is a PLAIN stored field on pos.order, not a live compute
        # over the lines — core refreshes it through ``_compute_prices`` whenever it
        # changes an order's contents. Adding a line without that leaves the bill
        # showing the old total, which is the one number a guest checks.
        order.invalidate_recordset()
        order.sudo()._compute_prices()
        self._audit(env, 'order.tip', order, **self._actor(env, kw),
                    detail=json.dumps({'amount': tip, 'after_payment': settled,
                                       'paid_before': paid_before}, default=str))
        return {'ok': True, 'order_id': order.id, 'uuid': order.uuid or '',
                'tip': tip, 'after_payment': settled,
                'amount_total': round(order.amount_total, 2),
                'amount_paid': round(sum(order.payment_ids.mapped('amount')), 2)}

    @http.route(f'{API_PREFIX}/orders/note', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*', readonly=False)
    def order_note(self, order_id=None, order_uuid=None, session_id=None,
                   note=None, **kw):
        """The note that belongs to the ORDER rather than to one line.

        "Table is in a hurry", "birthday — bring the cake last", "allergy in the
        party" are facts about the check, not about a burger. Mezze had only a
        per-line note, so they were either attached to an arbitrary item or lost.
        Written to core's own ``internal_note``.
        """
        auth = self._authorize(endpoint='orders/note')
        if auth:
            return auth
        env = self._api_env()
        try:
            order = self._reward_order(env, order_id, order_uuid, session_id)
            if not order:
                return self._json({'ok': False, 'error': 'order_not_found'}, status=404)
            denied = self._security_gate(env, 'orders/note', target_order=order)
            if denied:
                return denied
            if order.state != 'draft':
                return self._json({'ok': False, 'error': 'order_not_open'}, status=400)
            text = (note or '').strip()[:500]
            field = 'internal_note' if 'internal_note' in order._fields else None
            if not field:
                return self._json({'ok': False, 'error': 'unsupported'}, status=400)
            order.sudo().write({field: text})
            self._audit(env, 'order.note', order, **self._actor(env, kw),
                        detail=json.dumps({'note': text}, default=str))
            return {'ok': True, 'order_id': order.id, 'note': text}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze order note failed")
            return self._json({'ok': False, 'error': 'note_failed',
                               'message': str(exc)}, status=400)

    @http.route(f'{API_PREFIX}/products/info', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*', readonly=True)
    def product_info(self, product_id=None, config_id=None, **kw):
        """What a cashier needs to answer a question about a product.

        Core has this behind an Actions button; Mezze had nothing, so "how many have
        we got left?" and "what does that cost us?" had no answer at the till.

        Margin and cost are shown only to a principal that holds finance rights —
        a cashier reading the shop's cost price off the till is not a feature.
        """
        auth = self._authorize(endpoint='products/info')
        if auth:
            return auth
        env = self._api_env()
        try:
            product = env['product.product'].browse(int(product_id)).exists()
            if not product:
                return self._json({'ok': False, 'error': 'not_found'}, status=404)
            config = self._resolve_config(env, config_id)
            pricelist, _fp = self._resolve_pricing(env, config, env['res.partner'])
            price = (pricelist._get_product_price(product, 1.0)
                     if pricelist else product.lst_price)
            out = {
                'ok': True, 'id': product.id, 'name': product.display_name,
                'default_code': product.default_code or '',
                'barcode': product.barcode or '',
                'price': round(price, 2),
                'list_price': round(product.lst_price, 2),
                'uom': product.uom_id.name or '',
                'taxes': product.taxes_id.mapped('name'),
                'available': product.id not in self._eightysix_ids(env, config.id),
                'pricelists': [
                    {'name': pl.name,
                     'price': round(pl._get_product_price(product, 1.0), 2)}
                    for pl in (config.available_pricelist_ids or config.pricelist_id)
                ],
            }
            if product.is_storable:
                out['qty_available'] = product.qty_available
                out['virtual_available'] = product.virtual_available
            role = self._acting_role(env)
            if role and authz.FINANCE_READ in authz.capabilities_for(role):
                cost = product.standard_price
                out['cost'] = round(cost, 2)
                out['margin'] = round(price - cost, 2)
                out['margin_pct'] = round((price - cost) / price * 100.0, 1) if price else 0.0
            return out
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze product info failed")
            return self._json({'ok': False, 'error': 'product_info_failed',
                               'message': str(exc)}, status=400)

    # ------------------------------------------------------------------
    # Recent orders — for the Refund flow's order picker
    # ------------------------------------------------------------------
    @http.route(f'{API_PREFIX}/orders/recent', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def orders_recent(self, session_id=None, limit=20, **kw):
        auth = self._authorize()
        if auth:
            return auth
        try:
            env = self._api_env()
            # CP9 — begin from the principal's AUTHORITATIVE branch scope (a client
            # session_id may only narrow within it, never widen it). Fail-closed if the
            # caller has no resolvable branch (and is not the scope-bypassing admin).
            scope, ok = self._mezze_scope_domain(env)
            if not ok:
                return {'ok': True, 'orders': []}
            dom = scope + [('state', 'in', ('paid', 'done', 'invoiced')), ('amount_total', '>', 0)]
            if session_id:
                dom.append(('session_id', '=', int(session_id)))
            orders = env['pos.order'].search(dom, order='date_order desc', limit=int(limit or 20))
            return {'ok': True, 'orders': [{
                'id': o.id, 'pos_reference': o.pos_reference, 'uuid': o.uuid,
                'amount_total': o.amount_total, 'session_id': o.session_id.id,
                'date_order': fields.Datetime.to_string(o.date_order),
                'partner': o.partner_id.name or '',
                'tender': ', '.join(o.payment_ids.mapped('payment_method_id.name')) or 'Cash',
                # ``refundable`` is what is LEFT, not what was sold. The server
                # enforces the per-line ceiling either way, but a till that does not
                # know about an earlier partial refund offers the whole quantity and
                # then shows the cashier a rejection they cannot explain to a guest.
                'lines': [{
                    'line_id': l.id, 'product_id': l.product_id.id,
                    'name': l.product_id.display_name, 'qty': l.qty,
                    'price': l.price_subtotal_incl,
                    'refunded': self._already_refunded(env, l),
                    'refundable': max(0.0, l.qty - self._already_refunded(env, l)),
                } for l in o.lines if l.qty > 0],
            } for o in orders]}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze orders_recent failed")
            return self._json({'ok': False, 'error': 'recent_failed', 'message': str(exc)}, status=400)

    def _mezze_stamp_actor(self, env, order):
        """Record WHO and WHAT made this sale on the native order.

        The audit log already knows, but an audit row is not a mapping: the
        backend order form, the POS reports and anyone reconciling a till at
        midnight all read ``pos.order``, and until now every Mezze sale showed the
        API identity as its salesperson because front-of-house staff have no
        res.users by design.

        Never raises into the money path — a missing attribution is a reporting
        problem, and rolling back a completed sale over one would be worse.
        """
        if not order:
            return False
        try:
            ctx = self._resolve_principal(env)
        except Exception:  # noqa: BLE001
            return False
        if not ctx.get('ok'):
            return False
        vals = {}
        cashier = ctx.get('cashier')
        terminal = ctx.get('terminal')
        # Only fill blanks: the cashier who OPENED the order keeps the sale even
        # if a supervisor later touches it from another terminal.
        if cashier and not order.mezze_cashier_id:
            vals['mezze_cashier_id'] = cashier.id
        if terminal and not order.mezze_terminal_id:
            vals['mezze_terminal_id'] = terminal.id
        if vals:
            order.sudo().write(vals)
        return bool(vals)

    def _mezze_principal_scope(self, env):
        """Resolve the caller's AUTHORITATIVE scope from the token (never client input).

        Returns ``{ok, is_admin, branch, company}``. ``branch`` is the pos.config id
        the principal is confined to; the scope-bypassing shared-admin has
        ``is_admin=True`` (no branch confinement). Used by every list/create/scope path.
        """
        try:
            ctx = self._resolve_principal(env)
        except Exception:  # noqa: BLE001
            return {'ok': False}
        if not ctx.get('ok'):
            return {'ok': False}
        return {'ok': True, 'is_admin': bool(ctx.get('is_admin')),
                'branch': ctx.get('branch_id'), 'company': ctx.get('company_id')}

    def _mezze_scope_domain(self, env):
        """CP9 — server-authoritative branch scope for LIST/lookup queries.

        Returns ``(domain_fragment, ok)``. The domain confines the query to the
        caller's own branch (``config_id``); the scope-bypassing shared-admin gets an
        empty (unrestricted) fragment. A non-admin principal with no resolvable branch
        fails closed (``ok=False``) so a list never leaks another tenant's rows.
        Client-supplied company/branch ids are NEVER trusted here.
        """
        s = self._mezze_principal_scope(env)
        if not s['ok']:
            return ([], False)
        if s['is_admin']:
            return ([], True)                       # shared-admin: not branch-scoped
        if not s['branch']:
            return ([], False)                      # fail closed — no resolvable scope
        return ([('config_id', '=', int(s['branch']))], True)

    def _mezze_scope_base(self, env, config_id=None):
        """CP11 — base domain for a STAFF collection query on a ``config_id``-bearing
        model (deliveries, drive-thru cars, aggregator orders, channel reports). The
        query begins from the caller's authoritative branch; a client ``config_id``
        may only narrow (admin), never widen. A non-admin without a branch, or an
        unresolved principal, matches NOTHING (no cross-branch enumeration)."""
        scope, ok = self._mezze_scope_domain(env)
        if not ok:
            return [('id', 'in', [])]               # fail closed
        if scope:                                   # non-admin: branch-pinned
            return list(scope)
        if config_id:                               # admin narrowing to one branch
            return [('config_id', '=', int(config_id))]
        return []                                   # admin, all branches

    def _mezze_table_in_branch(self, env, table, branch_id):
        """CP10 — True if ``table`` (restaurant.table) belongs to ``branch_id`` (a
        pos.config). Used so a reservation/seat can never bind a table from another
        branch. ``branch_id`` None means the caller is the unscoped admin (allow)."""
        if not branch_id:
            return True                             # unscoped admin
        if not table or not table.exists():
            return False
        floor = table.floor_id
        if floor and 'pos_config_ids' in floor._fields:
            return int(branch_id) in floor.pos_config_ids.ids
        return True     # link undeterminable in this schema — do not hard-block

    def _mezze_order_row(self, o):
        """Compact, cashier-safe Orders-workspace row (no internal ids/codes)."""
        total = round(o.amount_total, 2)
        paid = round(o.amount_paid, 2)
        completed = o.state in ('paid', 'done', 'invoiced')
        return {
            'uuid': o.uuid, 'pos_reference': o.pos_reference,
            'state': o.state, 'completed': completed,
            'parked': bool(o.mezze_parked) if 'mezze_parked' in o._fields else False,
            'order_type': self._mezze_order_type(o),
            'table': (str(o.table_id.table_number) if ('table_id' in o._fields and o.table_id) else None),
            'floor': (o.table_id.floor_id.name
                      if ('table_id' in o._fields and o.table_id and o.table_id.floor_id) else None),
            'guests': o.customer_count if 'customer_count' in o._fields else 0,
            'partner': o.partner_id.name or '',
            'amount_total': total, 'amount_paid': paid, 'remaining': round(total - paid, 2),
            'date_order': fields.Datetime.to_string(o.date_order),
        }

    @http.route(f'{API_PREFIX}/orders/list', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def orders_list(self, filter=None, query=None, limit=25, offset=0, **kw):
        """CP9 Orders workspace — ONE scoped, bounded list powering Open / Parked /
        Completed tabs + search. Server-authoritative branch scope; client params only
        narrow. Never returns another branch's orders. Not an order engine — a read.
        """
        auth = self._authorize()
        if auth:
            return auth
        try:
            env = self._api_env()
            scope, ok = self._mezze_scope_domain(env)
            if not ok:
                return {'ok': True, 'orders': [], 'has_more': False}
            filt = (filter or 'open').strip().lower()
            if filt == 'completed':
                dom = scope + [('state', 'in', ('paid', 'done', 'invoiced')), ('amount_total', '>', 0)]
                order_by = 'date_order desc'
            elif filt == 'parked':
                dom = scope + [('state', '=', 'draft'), ('mezze_parked', '=', True)]
                order_by = 'write_date desc'
            elif filt == 'all':
                dom = scope + ['|', ('state', '=', 'draft'), ('state', 'in', ('paid', 'done', 'invoiced'))]
                order_by = 'write_date desc'
            else:  # 'open' — active draft work NOT explicitly parked
                dom = scope + [('state', '=', 'draft'), ('mezze_parked', '=', False)]
                order_by = 'write_date desc'
            # search: order reference, table number, or customer name (scoped)
            q = (query or '').strip()
            if q:
                sub = ['|', '|', ('pos_reference', 'ilike', q), ('partner_id.name', 'ilike', q)]
                if q.isdigit() and 'table_id' in env['pos.order']._fields:
                    sub.append(('table_id.table_number', '=', q))
                else:
                    sub.append(('table_id.table_number', 'ilike', q))
                dom = dom + sub
            lim = max(1, min(int(limit or 25), 50))
            off = max(0, int(offset or 0))
            orders = env['pos.order'].search(dom, order=order_by, limit=lim + 1, offset=off)
            has_more = len(orders) > lim
            rows = [self._mezze_order_row(o) for o in orders[:lim]]
            return {'ok': True, 'orders': rows, 'has_more': has_more, 'filter': filt}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze orders_list failed")
            return self._json({'ok': False, 'error': 'list_failed', 'message': str(exc)}, status=400)

    @http.route(f'{API_PREFIX}/orders/park', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*', readonly=False)
    def orders_park(self, uuid=None, order_id=None, parked=True, **kw):
        """CP9 — TAG/untag an existing DRAFT order as parked. Pure cashier bookkeeping:
        it does NOT pay, cancel, move, unlink, clear the table, or change the order
        state. A non-draft (completed/cancelled) order can never be parked/resurrected.
        """
        auth = self._authorize()
        if auth:
            return auth
        try:
            env = self._api_env()
            order = (env['pos.order'].search([('uuid', '=', uuid)], limit=1)
                     if uuid else env['pos.order'].browse(int(order_id)))
            if not order.exists():
                return self._json({'ok': False, 'error': 'not_found'}, status=404)
            denied = self._security_gate(env, 'orders/park', target=order)
            if denied:
                return denied
            if order.state != 'draft':
                # never re-open a completed/cancelled order as a parked draft
                return self._json({'ok': False, 'error': 'order_not_draft',
                                   'state': order.state}, status=409)
            order.sudo().write({'mezze_parked': bool(parked)})
            self._audit(env, 'order.park', order, **self._actor(env, kw),
                        detail=json.dumps({'parked': bool(parked)}))
            return {'ok': True, 'uuid': order.uuid, 'parked': bool(parked), 'state': order.state}
        except Exception as exc:  # noqa: BLE001
            _reraise_if_retryable(exc)
            _logger.exception("Mezze order park failed")
            return self._json({'ok': False, 'error': 'park_failed', 'message': str(exc)}, status=400)

    def _refund_audit_reject(self, env, orig, refund_uuid, reason, extra=None):
        """PII-safe audit of a rejected refund + a ready-to-return rejection dict.
        Audit failure never weakens correctness."""
        base = {
            'endpoint': 'orders/refund', 'reason_code': reason,
            'original_order_id': orig.id if orig else None,
            'original_uuid': (getattr(orig, 'uuid', False) or None) if orig else None,
            'refund_uuid': refund_uuid,
            'company_id': orig.company_id.id if (orig and orig.company_id) else None,
            'branch_id': orig.config_id.id if (orig and orig.config_id) else None,
            'actor_uid': env.uid, 'correlation_id': self._correlation_id(),
            'ts': fields.Datetime.to_string(fields.Datetime.now()),
        }
        base.update(extra or {})
        try:
            env['mezze.audit.log'].sudo().log(
                'order.refund_rejected', severity='warning', res_model='pos.order',
                res_id=orig.id if orig else False,
                res_uuid=(getattr(orig, 'uuid', False) or False) if orig else False,
                detail=json.dumps(base, default=str))
        except Exception:  # noqa: BLE001 — audit failure must not decide correctness
            _logger.exception("Mezze refund-reject audit append failed")
        out = {'ok': False, 'error': reason}
        out.update(extra or {})
        return out

    def _lock_original(self, env, orig):
        """Transaction-scoped advisory lock keyed on the ORIGINAL order id (same
        mechanism as _do_fire). Serializes ALL refunds of this original (per-
        original; unrelated orders never block), then drops the ORM cache so the
        recompute reads a concurrent refund's just-committed state. Held to commit.
        Requires a writable cursor (route is readonly=False)."""
        env.cr.execute("SELECT pg_advisory_xact_lock(%s, %s)", (self._REFUND_LOCK_NS, orig.id))
        env.invalidate_all()

    def _already_refunded(self, env, line):
        """How much of this original line has already come back.

        Counted from the refund lines that point at it, so it survives a partial
        refund followed by another — which is exactly when a cashier is most likely
        to be told "no" without being told why.
        """
        if 'refunded_orderline_id' not in env['pos.order.line']._fields:
            return 0.0
        done = env['pos.order.line'].sudo().search(
            [('refunded_orderline_id', '=', line.id)])
        return abs(sum(done.mapped('qty')))

    def _resolve_refund_lines(self, env, orig, config, session, lines, refund_uuid, kw):
        """Authoritatively reconstruct + validate an ORIGINAL-order refund.

        Runs UNDER the per-original advisory lock. For every requested line it
        resolves the authoritative original line, validates ownership/product/
        quantity, and rebuilds the negative refund line from SERVER truth (price,
        tax, discount, uom) with a MANDATORY ``refunded_orderline_id`` link — so
        no missing/fake client field can create an uncounted or cross-order
        refund. Enforces BOTH the per-line quantity ceiling and the order-level
        monetary ceiling. Returns ``{'lines','total','total_base'}`` on success or
        a ready-to-return rejection dict (audited) — BEFORE any side effect.
        """
        cur = orig.currency_id
        if session.currency_id and cur and session.currency_id != cur:
            return self._refund_audit_reject(env, orig, refund_uuid,
                order_refund_rules.CURRENCY_MISMATCH,
                {'original_currency': cur.name, 'request_currency': session.currency_id.name})
        if orig.company_id and config.company_id and orig.company_id != config.company_id:
            return self._refund_audit_reject(env, orig, refund_uuid,
                order_refund_rules.COMPANY_MISMATCH,
                {'original_company': orig.company_id.id, 'request_company': config.company_id.id})
        self._lock_original(env, orig)
        if not lines:
            return self._refund_audit_reject(env, orig, refund_uuid, order_refund_rules.LINE_MISSING, {})
        orig_lines = {l.id: l for l in orig.lines}
        qdig = env['decimal.precision'].precision_get('Product Unit of Measure')
        # normalize: aggregate requested qty per source line so duplicate payload
        # entries cannot double-refund one source line.
        req_by_line = {}
        for line in lines:
            lid = line.get('line_id')
            if not lid:
                return self._refund_audit_reject(env, orig, refund_uuid, order_refund_rules.LINE_MISSING, {})
            try:
                lid = int(lid)
            except (TypeError, ValueError):
                return self._refund_audit_reject(env, orig, refund_uuid, order_refund_rules.LINE_MISSING, {})
            ol = orig_lines.get(lid)
            if ol is None:
                return self._refund_audit_reject(env, orig, refund_uuid,
                    order_refund_rules.LINE_NOT_IN_ORIGINAL, {'source_line_id': lid})
            if line.get('product_id') and int(line['product_id']) != ol.product_id.id:
                return self._refund_audit_reject(env, orig, refund_uuid,
                    order_refund_rules.PRODUCT_MISMATCH,
                    {'source_line_id': lid, 'original_product': ol.product_id.id,
                     'requested_product': int(line['product_id'])})
            try:
                qty = abs(float(line.get('qty', ol.qty)))
            except (TypeError, ValueError):
                return self._refund_audit_reject(env, orig, refund_uuid,
                    order_refund_rules.QTY_INVALID, {'source_line_id': lid})
            req_by_line[lid] = req_by_line.get(lid, 0.0) + qty

        order_lines, total, total_base = [], 0.0, 0.0
        for lid, req_qty in req_by_line.items():
            ol = orig_lines[lid]
            # already successfully refunded qty for THIS source line
            succ = ol.refund_orderline_ids.filtered(
                lambda rl: rl.order_id.state in ('paid', 'done', 'invoiced'))
            already_qty = -sum(succ.mapped('qty'))     # positive
            qv = order_refund_rules.check_line_quantity(
                order_refund_rules.qty_to_units(req_qty, qdig),
                order_refund_rules.qty_to_units(ol.qty, qdig),
                order_refund_rules.qty_to_units(already_qty, qdig))
            if not qv.ok:
                return self._refund_audit_reject(env, orig, refund_uuid, qv.reason,
                    {'source_line_id': lid, 'requested_qty': req_qty,
                     'remaining_units': qv.remaining_units,
                     'sold_units': order_refund_rules.qty_to_units(ol.qty, qdig),
                     'already_refunded_units': order_refund_rules.qty_to_units(already_qty, qdig)})
            # Reconstruct from the ORIGINAL line's ACTUALLY-PAID economics: refund
            # the proportional paid amount (incl. its discount + tax), so a full-
            # line refund returns exactly what was paid and is bounded by paid.
            ratio = (req_qty / ol.qty) if ol.qty else 0.0
            sub = -abs(ol.price_subtotal) * ratio
            sub_incl = -abs(ol.price_subtotal_incl) * ratio
            total += sub_incl
            total_base += sub
            order_lines.append((0, 0, {
                'product_id': ol.product_id.id, 'qty': -req_qty, 'price_unit': ol.price_unit,
                'discount': ol.discount, 'tax_ids': [(6, 0, ol.tax_ids.ids)],
                'price_subtotal': sub, 'price_subtotal_incl': sub_incl,
                'pack_lot_ids': [], 'refunded_orderline_id': ol.id,
            }))

        # order-level monetary ceiling (defense-in-depth; both gates must pass)
        dp = cur.decimal_places
        paid_minor = order_refund_rules.to_minor(orig.amount_paid, dp)
        refund_orders = orig.mapped('lines.refund_orderline_ids.order_id').filtered(
            lambda o: o.id != orig.id and o.state in ('paid', 'done', 'invoiced'))
        already_minor = order_refund_rules.to_minor(-sum(refund_orders.mapped('amount_total')), dp)
        requested_minor = order_refund_rules.to_minor(-total, dp)
        mv = order_refund_rules.check_refund(requested_minor, paid_minor, already_minor)
        if not mv.ok:
            return self._refund_audit_reject(env, orig, refund_uuid, mv.reason,
                {'requested_minor': requested_minor, 'refundable_minor': mv.refundable_minor,
                 'already_refunded_minor': already_minor, 'paid_minor': paid_minor,
                 'currency': cur.name})
        return {'lines': order_lines, 'total': round(total, dp), 'total_base': round(total_base, dp)}

    # ------------------------------------------------------------------
    # Refund — a real negative pos.order via sync_from_ui
    # ------------------------------------------------------------------
    @http.route(f'{API_PREFIX}/orders/refund', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*', readonly=False)
    def order_refund(self, uuid=None, session_id=None, original_order_id=None,
                     lines=None, reason=None, **kw):
        auth = self._authorize()
        if auth:
            return auth
        if not uuid:
            return self._json({'ok': False, 'error': 'missing_uuid'}, status=400)
        env = self._api_env()
        log = env['mezze.sync.log'].sudo().create({'name': 'Refund %s' % uuid, 'uuid': uuid, 'status': 'received'})
        try:
            existing = env['pos.order'].search([('uuid', '=', uuid)], limit=1)
            if existing:
                return {'ok': True, 'duplicate': True, 'order_id': existing.id,
                        'pos_reference': existing.pos_reference, 'amount_total': existing.amount_total}
            # W2: optional manager approval for refunds (config-gated so small
            # shops aren't forced into it). approver_cashier_id is a supervisor+
            # verified on the client via /w1/approve.
            if str(env['ir.config_parameter'].sudo().get_param(
                    'mezze_bridge.require_approval_refund', '')).strip().lower() in ('1', 'true'):
                # W2-1: verify a signed approval TOKEN (minted by /w1/approve after
                # a PIN check), not a client-supplied id — the client can't forge it.
                approver_id = approval.verify(env, kw.get('approval_token'), 'refund')
                approver = (env['mezze.cashier'].browse(approver_id)
                            if approver_id else env['mezze.cashier'])
                if not approver.exists() or approver.role not in ('supervisor', 'manager'):
                    return self._json({'ok': False, 'error': 'approval_required',
                                       'message': 'Refund requires a valid supervisor/manager approval.'}, status=403)
                kw['approver_cashier_id'] = approver.id   # record the VERIFIED approver
            session = env['pos.session'].browse(int(session_id))
            if not session.exists():
                raise ValueError("Unknown session_id %s" % session_id)
            config = session.config_id
            env = env(context=dict(env.context, allowed_company_ids=[config.company_id.id], company_id=config.company_id.id))
            session = session.with_env(env)
            config = config.with_env(env)
            orig = env['pos.order'].browse(int(original_order_id)) if original_order_id else env['pos.order']
            # P4 canonical security gate: authn + orders.refund capability +
            # branch/company scope + replay/signature (flag-gated, observe default).
            denied = self._security_gate(env, 'orders/refund', target_order=orig)
            if denied:
                return denied
            # Concurrency: same-uuid duplicate refunds are blocked at the DB by
            # pos.order's unique(uuid) constraint (verified: N concurrent same-uuid
            # refunds -> exactly one refund order); no explicit lock is added here.
            # FSM authority: a refund is legal only against a paid/finalized
            # original order. Runs before any refund line math, sync_from_ui,
            # ledger-impacting write, or side effect. Skips when no original is
            # linked (ad-hoc refund) so behaviour is preserved.
            blocked = self._fsm_guard(env, orig, 'refund', endpoint='orders/refund')
            if blocked:
                return blocked
            currency = session.currency_id
            if original_order_id:
                # ORIGINAL-order refund: authoritative server-side reconstruction
                # + mandatory line linkage + per-line quantity ceiling + order
                # monetary ceiling, all under the per-original advisory lock and
                # BEFORE any refund order / line / payment / stock / accounting /
                # loyalty / bus / success side effect. Client price/tax/product
                # cannot override server truth; missing/fake/cross-order linkage
                # fails closed.
                resolved = self._resolve_refund_lines(env, orig, config, session, lines, uuid, kw)
                if resolved.get('ok') is False:
                    try:
                        log.write({'status': 'error', 'message': resolved.get('error')})
                    except Exception:  # noqa: BLE001
                        pass
                    return resolved
                order_lines = resolved['lines']
                total = resolved['total']
                total_base = resolved['total_base']
            else:
                # Ad-hoc refund with NO original order: a separate product
                # behaviour (unlinked, unbounded) — preserved verbatim. It is NOT
                # treated as a linked original-order refund.
                order_lines = []
                total = 0.0
                total_base = 0.0
                fp = config.default_fiscal_position_id
                for line in (lines or []):
                    product = env['product.product'].browse(int(line['product_id']))
                    qty = -abs(float(line.get('qty', 1.0)))
                    price = float(line.get('price_unit', product.lst_price))
                    company_taxes = product.taxes_id.filtered(lambda t: t.company_id == config.company_id)
                    taxes = fp.map_tax(company_taxes) if fp else company_taxes
                    if taxes:
                        tv = taxes.compute_all(price, currency, qty, product=product, partner=False)
                        sub, sub_incl = tv['total_excluded'], tv['total_included']
                    else:
                        sub = sub_incl = price * qty
                    total += sub_incl
                    total_base += sub
                    order_lines.append((0, 0, {'product_id': product.id, 'qty': qty, 'price_unit': price,
                        'discount': 0.0, 'tax_ids': [(6, 0, taxes.ids)], 'price_subtotal': sub,
                        'price_subtotal_incl': sub_incl, 'pack_lot_ids': []}))
            # REFUND TO WHAT THEY PAID WITH.
            #
            # This took ``config.payment_method_ids[:1]`` — the branch's FIRST method
            # — regardless of how the customer actually paid, with no way to override
            # it. A card sale refunded against Cash whenever Cash happened to be
            # listed first, which silently misstates the drawer and the settlement.
            #
            # The original order knows the answer. When it was settled with one
            # tender, refund to that; with several, refund proportionally, so a bill
            # half on card and half in cash comes back the same way. An explicit
            # ``payment_method_id`` still wins for the case where the customer asks.
            payments = []
            orig_payments = orig.payment_ids.filtered(lambda p: p.amount > 0)
            explicit = kw.get('payment_method_id')
            if explicit:
                pm = env['pos.payment.method'].browse(int(explicit)).exists()
                if pm and pm in config.payment_method_ids:
                    payments = [(0, 0, {'amount': total, 'name': fields.Datetime.now(),
                                        'payment_method_id': pm.id})]
            if not payments and orig_payments:
                paid_total = sum(orig_payments.mapped('amount')) or 1.0
                running = 0.0
                usable = [p for p in orig_payments
                          if p.payment_method_id in config.payment_method_ids]
                # ``total`` is NEGATIVE here — a refund's lines are negative, and so
                # is the payment that returns the money. Splitting it proportionally
                # therefore has to compare on magnitude; a `> 0` test silently
                # discards every share and falls through to the branch default,
                # which is the very bug this block exists to fix.
                for idx, p in enumerate(usable):
                    if idx == len(usable) - 1:
                        share = round(total - running, 2)   # last absorbs the rounding
                    else:
                        share = round(total * (p.amount / paid_total), 2)
                        running += share
                    if abs(share) > 0:
                        payments.append((0, 0, {
                            'amount': share, 'name': fields.Datetime.now(),
                            'payment_method_id': p.payment_method_id.id}))
            if not payments:
                # No usable original tender (an unlinked refund, or a method the
                # branch no longer offers). Fall back to the branch's first method
                # rather than refusing — but this is now the exception, not the rule.
                pm = config.payment_method_ids[:1]
                payments = [(0, 0, {'amount': total, 'name': fields.Datetime.now(),
                                    'payment_method_id': pm.id})] if pm else []
            order_dict = {
                'uuid': uuid, 'session_id': session.id, 'company_id': config.company_id.id,
                'user_id': env.uid, 'partner_id': orig.partner_id.id or False,
                'pricelist_id': config.pricelist_id.id or False,
                'name': 'Refund of %s' % (orig.pos_reference or original_order_id or '-'),
                'date_order': fields.Datetime.to_string(fields.Datetime.now()),
                'lines': order_lines, 'payment_ids': payments,
                'amount_tax': round(total - total_base, 2),
                'amount_total': total, 'amount_paid': total, 'amount_return': 0.0,
                'last_order_preparation_change': empty_preparation_change(), 'to_invoice': False,
            }
            env['pos.order'].sync_from_ui([order_dict])
            order = env['pos.order'].search([('uuid', '=', uuid)], limit=1)
            log.write({'status': 'ok', 'pos_order_id': order.id, 'session_id': session.id,
                       'message': 'Refund (%s) via sync_from_ui' % (reason or 'n/a')})
            self._audit(env, 'order.refund', order, severity='warning',
                        **self._actor(env, kw),
                        detail=json.dumps({'reason': reason or '',
                                           'reason_code': kw.get('reason_code') or '',
                                           'original_order_id': original_order_id,
                                           'approver_cashier_id': kw.get('approver_cashier_id')}, default=str))
            # P5: the refund succeeded — publish the business event IN THIS
            # transaction, reusing the refund uuid as identity (a duplicate refund
            # of the same uuid maps to one logical event; the guard at the top
            # already returns early for an existing uuid).
            self._publish_order_refunded(env, order, uuid, orig if original_order_id else env['pos.order'])
            return {'ok': True, 'order_id': order.id, 'pos_reference': order.pos_reference,
                    'amount_total': order.amount_total}
        except (psycopg2.errors.SerializationFailure,
                psycopg2.errors.DeadlockDetected,
                psycopg2.errors.LockNotAvailable):
            # Let PostgreSQL concurrency errors propagate so Odoo's request-level
            # retry re-runs the handler; on retry the refund ceiling re-reads the
            # winner's committed refund and cleanly rejects. Swallowing them here
            # would abort the transaction (500) and defeat the retry.
            raise
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze refund failed for uuid=%s", uuid)
            try:
                log.write({'status': 'error', 'message': str(exc)})
            except Exception:  # noqa: BLE001
                pass
            return self._json({'ok': False, 'error': 'refund_failed', 'uuid': uuid, 'message': str(exc)}, status=400)

    # ------------------------------------------------------------------
    # Comp — a manager-approved, 100%-off giveaway tracked apart from discounts
    # ------------------------------------------------------------------
    @http.route(f'{API_PREFIX}/orders/comp', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*', readonly=False)
    def order_comp(self, session_id=None, order_uuid=None, order_id=None,
                   line_id=None, product_id=None, reason=None, reason_code=None, **kw):
        """Comp (make complimentary) a line on an OPEN order: a 100%-off,
        reason-coded giveaway recorded as its OWN ``order.comp`` audit event so
        it reports separately from ordinary discounts — comps are a classic
        shrinkage/theft vector, so a restaurant tracks (and caps) them apart.

        Distinct from a *void* (item never made) — a comp WAS made and served,
        just not charged, so the KDS ticket stands and only the money changes.
        Applied to the draft, it flows through /orders/pay at settle. Manager
        approval is required by DEFAULT (disable per-branch with the
        ``mezze_bridge.require_approval_comp=0`` config param)."""
        auth = self._authorize()
        if auth:
            return auth
        env = self._api_env()
        try:
            # approval gate — default ON for comps (unlike refund, which is opt-in)
            gate = str(env['ir.config_parameter'].sudo().get_param(
                'mezze_bridge.require_approval_comp', '1')).strip().lower()
            if gate not in ('0', 'false', 'no', 'off'):
                approver_id = approval.verify(env, kw.get('approval_token'), 'comp')
                approver = (env['mezze.cashier'].browse(approver_id) if approver_id
                            else env['mezze.cashier'])
                # A till cannot mint an approval token (that route is admin-only), so
                # the manager approves in person with their code + PIN. Verified
                # server-side, same model and same rank rule as the token path.
                if not approver.exists():
                    inline, _err = self._verify_inline_approver(
                        env, kw.get('manager_code'), kw.get('manager_pin'), min_rank=1)
                    if inline:
                        approver = inline
                if not approver.exists() or approver.role not in ('supervisor', 'manager'):
                    return self._json({'ok': False, 'error': 'approval_required',
                                       'message': 'Comp requires a valid supervisor/manager approval.'},
                                      status=403)
                kw['approver_cashier_id'] = approver.id
            session = env['pos.session'].browse(int(session_id))
            if not session.exists():
                raise ValueError("Unknown session_id %s" % session_id)
            config = session.config_id
            env = env(context=dict(env.context, allowed_company_ids=[config.company_id.id],
                                   company_id=config.company_id.id))
            Order = env['pos.order']
            order = (Order.browse(int(order_id)) if order_id
                     else Order.search([('uuid', '=', order_uuid),
                                        ('session_id', '=', session.id)], limit=1))
            if not order.exists():
                raise ValueError("Order not found")
            # A comp changes what the guest owes, so it must not be applied to a
            # check another terminal has since moved.
            stale = self._assert_revision(order, kw.get('expected_revision'))
            if stale:
                return stale
            # Concurrency: concurrent comps/comp-vs-pay on the same order serialize
            # via Odoo's request-level retry plus the pos_order total update; no
            # explicit lock is added here (see the note in order_pay).
            # P4 canonical security gate: authn + orders.comp capability + scope
            # (flag-gated, observe default).
            denied = self._security_gate(env, 'orders/comp', target_order=order)
            if denied:
                return denied
            # FSM authority: comp mutates the order, so it is legal only while the
            # order is open (immutable once paid). Runs before any line/price/tax
            # mutation. In 'enforce' rejects first; in 'observe' the legacy raise
            # below still governs behaviour.
            blocked = self._fsm_guard(env, order, 'comp', endpoint='orders/comp')
            if blocked:
                return blocked
            if order.state != 'draft':
                raise ValueError("Only an open (unpaid) order can be comped")
            # resolve the target line (explicit line_id, else first un-comped
            # line of the product)
            if line_id:
                line = order.lines.filtered(lambda l: l.id == int(line_id))[:1]
            elif product_id:
                line = order.lines.filtered(
                    lambda l: l.product_id.id == int(product_id) and l.discount < 100)[:1]
            else:
                line = env['pos.order.line']
            if not line:
                raise ValueError("Comp target line not found on the order")
            comped_incl = line.price_subtotal_incl
            note = 'COMP' + ((': ' + reason) if reason else '')
            vals = {'discount': 100.0, 'price_subtotal': 0.0, 'price_subtotal_incl': 0.0}
            if 'customer_note' in line._fields:
                vals['customer_note'] = ((line.customer_note + ' · ') if line.customer_note else '') + note
            line.write(vals)
            # recompute the order total across all lines
            tot_base = sum(order.lines.mapped('price_subtotal'))
            tot_incl = sum(order.lines.mapped('price_subtotal_incl'))
            order.write({'amount_tax': tot_incl - tot_base, 'amount_total': tot_incl})
            self._audit(env, 'order.comp', order, severity='warning',
                        **self._actor(env, kw),
                        detail=json.dumps({'reason': reason or '', 'reason_code': reason_code or '',
                                           'product': line.product_id.display_name,
                                           'line_id': line.id, 'comped_amount': comped_incl,
                                           'approver_cashier_id': kw.get('approver_cashier_id')},
                                          default=str))
            return {'ok': True, 'order_id': order.id, 'pos_reference': order.pos_reference,
                    'line_id': line.id, 'comped_amount': round(comped_incl, 2),
                    'amount_total': order.amount_total}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze comp failed")
            return self._json({'ok': False, 'error': 'comp_failed', 'message': str(exc)}, status=400)

    # ------------------------------------------------------------------
    # Discounts — tiered authority.
    #
    # ``pos.order.line.discount`` is a core Odoo field and _build_lines has always
    # honoured it, but nothing in the product ever sent one: there was no UI, no
    # ceiling, and no audit event. The only reachable markdown was a 100% comp.
    #
    # Authority is tiered rather than boolean (see domain/discount.py): the
    # capability decides WHETHER a principal may discount, the ceiling decides HOW
    # FAR before a manager has to stand behind it. Both are enforced here, on the
    # server, against the role the GATE authenticated — a client that posts 40%
    # with a cashier token is refused and audited, not trusted.
    # ------------------------------------------------------------------
    def _acting_role(self, env):
        """The role whose discount ceiling applies to this request.

        An IDENTIFIED cashier narrows to that person's role. A bare terminal token
        is the device with nobody named behind it, so it stays ``terminal`` — which
        domain/discount.py aliases to the cashier ceiling, because a till is never
        MORE trusted than the least-privileged human who stands at it. Resolved
        from the same credentials the gate authenticated; never claimed by the
        client.
        """
        try:
            ctx = self._resolve_principal(env)
        except Exception:  # noqa: BLE001
            return None
        if not ctx.get('ok'):
            return None
        cashier = ctx.get('cashier')
        if cashier and cashier.exists():
            return cashier.role
        return ctx.get('principal_type')

    def _discount_ceiling(self, env, role):
        """This role's ceiling, read through the branch's config parameters."""
        get_param = env['ir.config_parameter'].sudo().get_param
        return discount_policy.ceiling_for(role, get_param)

    def _reprice_discounted(self, line, percent, currency, partner=None):
        """Set a line's discount % and recompute its STORED subtotals.

        ``price_subtotal`` / ``price_subtotal_incl`` are plain stored columns, not
        computed fields — writing ``discount`` alone would change the percentage
        the receipt prints and leave the money exactly as it was. This mirrors the
        arithmetic in ``_build_lines`` exactly, so a discount applied here and the
        same discount sent through /orders/sync produce identical numbers.
        """
        price_after = line.price_unit * (1.0 - float(percent) / 100.0)
        taxes = line.tax_ids
        if taxes:
            tv = taxes.compute_all(price_after, currency, line.qty,
                                   product=line.product_id, partner=partner or None)
            sub, sub_incl = tv['total_excluded'], tv['total_included']
        else:
            sub = sub_incl = price_after * line.qty
        line.write({'discount': float(percent),
                    'price_subtotal': sub, 'price_subtotal_incl': sub_incl})
        return sub_incl

    def _discountable_lines(self, order, line_id=None, product_id=None):
        """The lines a discount may touch.

        A line is addressed by ``line_id`` when the caller has one, else by
        ``product_id`` — the standalone cashier holds a client-side cart whose lines
        carry no server id, so /orders/comp already resolves "the first eligible line
        of this product" and this does the same rather than inventing a second
        addressing scheme for the same panel.

        Excluded on purpose:
          * REWARD lines (``is_reward_line``) — a loyalty reward is already a
            markdown the guest paid points for; discounting it discounts a discount.
          * COMPED lines (discount >= 100) — already free; re-pricing them would
            quietly un-comp the giveaway a manager signed for.
        """
        def eligible(l):
            return ((l.discount or 0.0) < 100.0 and l.qty > 0
                    and not (('is_reward_line' in l._fields) and l.is_reward_line))

        lines = order.lines.filtered(eligible)
        if line_id:
            return lines.filtered(lambda l: l.id == int(line_id))[:1]
        if product_id:
            return lines.filtered(lambda l: l.product_id.id == int(product_id))[:1]
        return lines

    @http.route(f'{API_PREFIX}/orders/discount', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*', readonly=False)
    def order_discount(self, session_id=None, order_uuid=None, order_id=None,
                       line_id=None, product_id=None, percent=None, scope='line',
                       reason=None, reason_code=None, **kw):
        """Apply a percentage discount to one line or to the whole open order.

        ``scope='line'`` needs ``line_id``; ``scope='order'`` applies the same
        percentage to every eligible line, which keeps each line's own taxes
        correct by construction — the alternative (one negative "Discount" line,
        which is what native ``pos_discount`` does) has to pick a single tax for a
        mixed-tax basket and gets it wrong for at least one of them.

        Setting a discount REPLACES any previous one on that line rather than
        stacking, because ``discount`` is a field and not a ledger. The audit row
        records the old and new value so the trail is still complete.

        Authority (domain/discount.py): within the acting role's ceiling it just
        happens; over it, a supervisor/manager code + PIN is required in person,
        verified server-side through the same throttled path comp uses. Every
        discount writes a ``discount.override`` audit event either way — there was
        previously no discount event of any kind, so discounts could not be
        reported on at all.
        """
        auth = self._authorize()
        if auth:
            return auth
        env = self._api_env()
        try:
            session = env['pos.session'].browse(int(session_id))
            if not session.exists():
                raise ValueError("Unknown session_id %s" % session_id)
            config = session.config_id
            env = env(context=dict(env.context, allowed_company_ids=[config.company_id.id],
                                   company_id=config.company_id.id))
            Order = env['pos.order']
            order = (Order.browse(int(order_id)) if order_id
                     else Order.search([('uuid', '=', order_uuid),
                                        ('session_id', '=', session.id)], limit=1))
            if not order.exists():
                raise ValueError("Order not found")
            # Canonical gate with the AUTHORITATIVE order as the scope target, so a
            # branch-A till cannot discount a branch-B check.
            denied = self._security_gate(env, 'orders/discount', target_order=order)
            if denied:
                return denied
            # A discount mutates money on the order, so it is legal only while the
            # order is open. Same rule and the same event as comp.
            blocked = self._fsm_guard(env, order, 'discount', endpoint='orders/discount')
            if blocked:
                return blocked
            if order.state != 'draft':
                raise ValueError("Only an open (unpaid) order can be discounted")

            role = self._acting_role(env)
            ceiling = self._discount_ceiling(env, role)
            has_cap = authz.ORDERS_DISCOUNT in authz.capabilities_for(role) if role else False
            verdict, detail = discount_policy.evaluate(
                role, percent, ceiling=ceiling, has_capability=has_cap)

            if verdict == discount_policy.INVALID:
                return self._json({'ok': False, 'error': 'invalid_discount',
                                   'message': 'A discount must be greater than 0% and at most 100%.',
                                   **detail}, status=400)
            if verdict == discount_policy.REFUSED:
                self._audit(env, 'discount.override', order, severity='warning',
                            **self._actor(env, kw),
                            detail=json.dumps({'refused': 'no_capability', 'role': role,
                                               **detail}, default=str))
                return self._json({'ok': False, 'error': 'permission_denied',
                                   'message': 'This role cannot apply a discount.'}, status=403)

            approver = env['mezze.cashier']
            if verdict == discount_policy.NEEDS_APPROVAL:
                # Over the ceiling. A manager approves in person with code + PIN —
                # the same throttled, server-verified, non-self-approvable path comp
                # uses. The approver must genuinely HOLD orders.discount, so this can
                # never grant more authority than the approver already has.
                inline, _err = self._verify_inline_approver(
                    env, kw.get('manager_code'), kw.get('manager_pin'),
                    min_rank=discount_policy.APPROVER_MIN_RANK)
                if inline and authz.ORDERS_DISCOUNT not in authz.capabilities_for(inline.role):
                    inline = None
                if not inline:
                    self._audit(env, 'discount.override', order, severity='warning',
                                **self._actor(env, kw),
                                detail=json.dumps({'refused': 'over_ceiling', 'role': role,
                                                   **detail}, default=str))
                    return self._json(
                        {'ok': False, 'error': 'approval_required',
                         'message': 'A discount above %g%% needs a supervisor or manager.' % detail['ceiling'],
                         **detail}, status=403)
                approver = inline

            if str(scope) == 'line' and not (line_id or product_id):
                raise ValueError("A line discount needs a line_id or a product_id")
            targets = self._discountable_lines(
                order,
                line_id=line_id if str(scope) == 'line' else None,
                product_id=product_id if str(scope) == 'line' else None)
            if not targets:
                return self._json({'ok': False, 'error': 'no_discountable_lines',
                                   'message': 'Nothing on this order can take a discount.'},
                                  status=400)

            currency = config.currency_id
            partner = order.partner_id
            before_total = order.amount_total
            previous = {l.id: (l.discount or 0.0) for l in targets}
            for line in targets:
                self._reprice_discounted(line, detail['percent'], currency, partner)
            tot_base = sum(order.lines.mapped('price_subtotal'))
            tot_incl = sum(order.lines.mapped('price_subtotal_incl'))
            order.write({'amount_tax': tot_incl - tot_base, 'amount_total': tot_incl})

            self._audit(env, 'discount.override', order,
                        severity='warning' if approver.exists() else 'info',
                        **self._actor(env, kw),
                        detail=json.dumps({
                            'scope': str(scope), 'percent': detail['percent'],
                            'ceiling': detail['ceiling'], 'role': role,
                            'lines': len(targets), 'line_ids': targets.ids,
                            'previous_percent': previous,
                            'amount_before': round(before_total, 2),
                            'amount_after': round(order.amount_total, 2),
                            'discounted_amount': round(before_total - order.amount_total, 2),
                            'reason': reason or '', 'reason_code': reason_code or '',
                            'approver_cashier_id': approver.id or None,
                            'approver_role': approver.role or None,
                        }, default=str))
            return {'ok': True, 'order_id': order.id, 'pos_reference': order.pos_reference,
                    'scope': str(scope), 'percent': detail['percent'],
                    'lines': targets.ids,
                    'discounted_amount': round(before_total - order.amount_total, 2),
                    'amount_total': order.amount_total,
                    'approved_by': approver.name or None}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze discount failed")
            return self._json({'ok': False, 'error': 'discount_failed', 'message': str(exc)},
                              status=400)

    @http.route(f'{API_PREFIX}/orders/void', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*', readonly=False)
    def order_void(self, session_id=None, order_uuid=None, order_id=None, reason=None, **kw):
        """V2C Phase 0 — VOID an OPEN (unpaid) fired order: the item was NEVER made,
        so its live kitchen tickets must be cancelled. Unlike /orders/comp (made+
        served, money only), a void cascades an explicit CANCELLATION to the KDS so
        the kitchen stops cooking. Manager/supervisor capability (orders.void),
        object-scoped to the order, signature-required. Idempotent: a repeat void of
        the same order cancels nothing new. The cancellation is published through the
        transactional outbox (delivered after commit), so a rolled-back void never
        reaches the kitchen."""
        auth = self._authorize()
        if auth:
            return auth
        env = self._api_env()
        try:
            session = env['pos.session'].browse(int(session_id))
            if not session.exists():
                raise ValueError("Unknown session_id %s" % session_id)
            config = session.config_id
            env = env(context=dict(env.context, allowed_company_ids=[config.company_id.id],
                                   company_id=config.company_id.id))
            Order = env['pos.order']
            order = (Order.browse(int(order_id)) if order_id
                     else Order.search([('uuid', '=', order_uuid),
                                        ('session_id', '=', session.id)], limit=1))
            if not order.exists():
                raise ValueError("Order not found")
            denied = self._security_gate(env, 'orders/void', target_order=order)
            if denied:
                return denied
            if order.state != 'draft':
                raise ValueError("Only an open (unpaid) order can be voided; use refund after payment")
            blocked = self._fsm_guard(env, order, 'cancel', endpoint='orders/void')
            if blocked:
                return blocked
            # cascade the void to the kitchen (idempotent, terminal-safe) and publish
            # the cancellation batch once through the outbox.
            cancelled = env['mezze.kds.ticket'].cancel_for_order(order)
            self._publish_kds(env, cancelled, order, natural_key='void:%s' % order.uuid)
            # VOID THE ORDER ITSELF. This route told the kitchen to stop and then
            # left the bill exactly as it found it: state 'draft', still on its
            # table, still payable, still counted in the floor's occupancy and in
            # every open-orders list. The Register cleared the cashier's screen on
            # the 200, so the one person who could have noticed was shown an empty
            # till while the check stayed live behind them — and the table read as
            # occupied for the rest of service.
            #
            # Cancelling is what "void" means, and pos.order.state carries a
            # 'cancel' value for exactly this. The table is released in the same
            # write: a voided order does not hold a seat.
            vals = {'state': 'cancel'}
            if 'table_id' in order._fields and order.table_id:
                vals['table_id'] = False
            if 'mezze_fired' in order._fields:
                # nothing is with the kitchen any more; a later re-fire of a reused
                # uuid must not think these items were already sent.
                vals['mezze_fired'] = json.dumps({})
            order.sudo().write(vals)
            self._audit(env, 'order.void', order=order,
                        reason=reason, cancelled_tickets=len(cancelled))
            return self._json({'ok': True, 'order_id': order.id, 'state': order.state,
                               'cancelled_tickets': len(cancelled)})
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze void failed")
            return self._json({'ok': False, 'error': 'void_failed', 'message': str(exc)}, status=400)

    @http.route(f'{API_PREFIX}/orders/exchange', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*', readonly=False)
    def order_exchange(self, uuid=None, session_id=None, original_order_id=None,
                       return_lines=None, new_lines=None, payments=None,
                       partner_id=None, reason=None, **kw):
        """Exchange = refund the returned items + sell the replacement items, as
        two linked orders. Net cash movement = new_total − return_total (the
        replacement is paid in full; the return is refunded in full). Reuses the
        existing refund + sync flows verbatim, so tax/idempotency/audit all hold.
        Even exchange -> net ~0; price difference -> the payments settle the new
        side. The pair is linked by an 'order.exchange' audit row."""
        auth = self._authorize()
        if auth:
            return auth
        if not uuid:
            return self._json({'ok': False, 'error': 'missing_uuid'}, status=400)
        out = {'ok': True, 'exchange_ref': uuid}
        if return_lines:
            r = self.order_refund(uuid='%s-ret' % uuid, session_id=session_id,
                                  original_order_id=original_order_id, lines=return_lines,
                                  reason=reason or 'exchange', reason_code='exchange', **kw)
            out['refund'] = r if isinstance(r, dict) else {'ok': False}
        if new_lines:
            s = self.order_sync(uuid='%s-new' % uuid, session_id=session_id,
                                lines=new_lines, payments=payments, partner_id=partner_id, **kw)
            out['sale'] = s if isinstance(s, dict) else {'ok': False}
        try:
            env = self._api_env()
            env['mezze.audit.log'].log('order.exchange', **self._actor(env, kw),
                detail=json.dumps({'exchange_ref': uuid, 'original_order_id': original_order_id,
                                   'refund_ref': (out.get('refund') or {}).get('pos_reference'),
                                   'sale_ref': (out.get('sale') or {}).get('pos_reference'),
                                   'reason': reason}, default=str))
        except Exception:  # noqa: BLE001
            _logger.exception("Mezze exchange audit failed")
        return out

    # ------------------------------------------------------------------
    # Floors + tables (pos_restaurant) — gracefully degrades if absent
    # ------------------------------------------------------------------
    @http.route(f'{API_PREFIX}/floors', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def floors(self, config_id=None, **kw):
        auth = self._authorize()
        if auth:
            return auth
        try:
            env = self._api_env()
            if 'restaurant.floor' not in env:
                return {'ok': True, 'available': False, 'floors': []}
            Table = env['restaurant.table']
            name_field = 'table_number' if 'table_number' in Table._fields else 'name'
            has_count = 'customer_count' in env['pos.order']._fields
            cfg_id = int(config_id) if config_id else None
            floor_dom = [('pos_config_ids', 'in', cfg_id)] if cfg_id else []
            # live occupancy: open (draft) orders grouped by table (this branch)
            draft_dom = [('state', '=', 'draft'), ('table_id', '!=', False)]
            if cfg_id:
                draft_dom.append(('config_id', '=', cfg_id))
            drafts = env['pos.order'].search(draft_dom)
            by_table = {}
            for o in drafts:
                by_table.setdefault(o.table_id.id, env['pos.order'])
                by_table[o.table_id.id] |= o
            now = fields.Datetime.now()
            # upcoming reservations "holding" a table right now (arriving soon,
            # not yet seated) — earliest per table
            res_by_table = {}
            if 'mezze.reservation' in env:
                soon = now + datetime.timedelta(minutes=self.RES_LEAD_MIN)
                res_dom = [('state', '=', 'booked'),
                           ('start', '>=', fields.Datetime.to_string(now - datetime.timedelta(minutes=20))),
                           ('start', '<=', fields.Datetime.to_string(soon))]
                if cfg_id:
                    res_dom.append(('config_id', '=', cfg_id))
                for r in env['mezze.reservation'].search(res_dom, order='start asc'):
                    res_by_table.setdefault(r.table_id.id, r)
            out = []
            for fl in env['restaurant.floor'].search(floor_dom):
                tables = []
                for t in fl.table_ids:
                    if not t.active:
                        continue
                    td = {
                        'id': t.id, 'name': str(t[name_field]),
                        'seats': t.seats, 'shape': t.shape,
                        'x': t.position_h, 'y': t.position_v,
                        'w': t.width, 'h': t.height,
                        'status': 'available', 'total': 0.0, 'guests': 0,
                        'minutes': 0, 'server': None, 'order_uuid': None,
                        'reservation': None,
                    }
                    dorders = by_table.get(t.id)
                    if dorders:
                        first = min(dorders.mapped('date_order'))
                        td.update({
                            'status': 'occupied',
                            'total': round(sum(dorders.mapped('amount_total')), 2),
                            'guests': sum(dorders.mapped('customer_count')) if has_count else 0,
                            'minutes': int((now - first).total_seconds() / 60),
                            'server': dorders[0].user_id.name or None,
                            'order_uuid': dorders[0].uuid,
                        })
                    elif res_by_table.get(t.id):
                        r = res_by_table[t.id]
                        td.update({
                            'status': 'reserved',
                            'guests': r.guests,
                            'reservation': {
                                'id': r.id, 'who': r._who(),
                                'start': fields.Datetime.to_string(r.start),
                                'time': fields.Datetime.to_string(r.start)[11:16],
                                'guests': r.guests, 'phone': r.phone or '',
                            },
                        })
                    tables.append(td)
                out.append({'id': fl.id, 'name': fl.name, 'tables': tables})
            return {'ok': True, 'available': True, 'floors': out}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze floors failed")
            return self._json({'ok': False, 'error': 'floors_failed', 'message': str(exc)}, status=400)

    # ------------------------------------------------------------------
    # Table transfer / merge — full-service floor operations
    # ------------------------------------------------------------------
    def _open_table_order(self, env, session, table_id, order_uuid=None):
        """The single open (draft) order sitting on a table this session."""
        dom = [('table_id', '=', int(table_id)), ('state', '=', 'draft'),
               ('session_id', '=', session.id)]
        if order_uuid:
            dom.append(('uuid', '=', order_uuid))
        return env['pos.order'].search(dom, limit=1)

    def _lock_tables(self, env, *table_ids):
        """Advisory-lock a set of tables in a STABLE order (ascending id) so two
        transfers touching the same pair can never deadlock. Shares the fire
        lock namespace, so a move also serializes against concurrent fires/pays
        on those tables."""
        for k in sorted({int(t) for t in table_ids if t}):
            env.cr.execute("SELECT pg_advisory_xact_lock(%s, %s)", (self._FIRE_LOCK_NS, k))

    @staticmethod
    def _table_label(table):
        f = 'table_number' if 'table_number' in table._fields else 'name'
        return str(table[f])

    def _refire_snapshot(self, env, order):
        """Rebuild the cumulative fired-qty snapshot from the order's live lines
        (used after lines move between orders on a merge)."""
        current = {}
        for l in order.lines:
            if l.qty > 0:
                current[str(l.product_id.id)] = current.get(str(l.product_id.id), 0.0) + l.qty
        if 'mezze_fired' in order._fields:
            order.sudo().write({'mezze_fired': json.dumps(current)})

    @http.route(f'{API_PREFIX}/tables/transfer', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*', readonly=False)
    def table_transfer(self, session_id=None, from_table_id=None, to_table_id=None,
                       order_uuid=None, **kw):
        """Move an open order from one table to another. The destination must be
        FREE — a transfer onto an occupied table is rejected (use /tables/merge).
        KDS tickets follow the order; their table label is refreshed so the
        kitchen sees the new seat."""
        auth = self._authorize()
        if auth:
            return auth
        try:
            env = self._api_env()
            session = env['pos.session'].browse(int(session_id))
            if not session.exists():
                raise ValueError("Unknown session_id %s" % session_id)
            config = session.config_id
            env = env(context=dict(env.context, allowed_company_ids=[config.company_id.id],
                                   company_id=config.company_id.id))
            session = session.with_env(env)
            src_id, dst_id = int(from_table_id), int(to_table_id)
            if src_id == dst_id:
                raise ValueError("Source and destination tables are the same")
            dst = env['restaurant.table'].browse(dst_id)
            if not dst.exists():
                raise ValueError("Unknown destination table %s" % dst_id)
            self._lock_tables(env, src_id, dst_id)
            order = self._open_table_order(env, session, src_id, order_uuid)
            if not order:
                raise ValueError("No open order on the source table")
            if self._open_table_order(env, session, dst_id):
                raise ValueError("Destination table is occupied — merge instead")
            order.write({'table_id': dst_id})
            label = self._table_label(dst)
            env['mezze.kds.ticket'].search([('pos_order_id', '=', order.id)]).write(
                {'table_label': label})
            self._audit(env, 'table.transfer', order, **self._actor(env, kw),
                        detail=json.dumps({'from': src_id, 'to': dst_id}))
            return {'ok': True, 'order_id': order.id, 'order_uuid': order.uuid,
                    'from_table_id': src_id, 'to_table_id': dst_id,
                    'table_label': label, 'amount_total': order.amount_total}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze table transfer failed")
            return self._json({'ok': False, 'error': 'transfer_failed',
                               'message': str(exc)}, status=400)

    @http.route(f'{API_PREFIX}/tables/merge', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*', readonly=False)
    def table_merge(self, session_id=None, from_table_id=None, to_table_id=None, **kw):
        """Merge the open order on ``from_table`` INTO the open order on
        ``to_table``: all lines (combo parent+child links preserved, since they
        move together) and KDS tickets re-home onto the target, guest counts add
        up, the target keeps its own tracking number, and the emptied source
        draft is removed. If the target is free, this degrades to a transfer."""
        auth = self._authorize()
        if auth:
            return auth
        try:
            env = self._api_env()
            session = env['pos.session'].browse(int(session_id))
            if not session.exists():
                raise ValueError("Unknown session_id %s" % session_id)
            config = session.config_id
            env = env(context=dict(env.context, allowed_company_ids=[config.company_id.id],
                                   company_id=config.company_id.id))
            session = session.with_env(env)
            src_id, dst_id = int(from_table_id), int(to_table_id)
            if src_id == dst_id:
                raise ValueError("Source and destination tables are the same")
            self._lock_tables(env, src_id, dst_id)
            src = self._open_table_order(env, session, src_id)
            if not src:
                raise ValueError("No open order on the source table")
            # A merge folds one check into another. The caller is looking at the
            # SOURCE, so that is the version that must still be current — merging
            # a check somebody has just added to would carry lines the cashier
            # never saw into a bill they are about to close.
            stale = self._assert_revision(src, kw.get('expected_revision'))
            if stale:
                return stale
            dst = self._open_table_order(env, session, dst_id)
            if not dst:
                # target free → this is really a transfer
                src.write({'table_id': dst_id})
                dtab = env['restaurant.table'].browse(dst_id)
                label = self._table_label(dtab)
                env['mezze.kds.ticket'].search([('pos_order_id', '=', src.id)]).write(
                    {'table_label': label})
                self._audit(env, 'table.transfer', src, **self._actor(env, kw),
                            detail=json.dumps({'from': src_id, 'to': dst_id, 'via': 'merge'}))
                return {'ok': True, 'merged': False, 'order_id': src.id,
                        'order_uuid': src.uuid, 'to_table_id': dst_id,
                        'table_label': label, 'amount_total': src.amount_total}
            # R1.1 §8 — FINANCIAL SAFETY: merging combines two orders and unlinks the
            # emptied source. If either draft carries payments (partial/complete),
            # reversals or refunds, re-homing lines + unlinking the source would
            # silently destroy financial records. Block unless a deliberate, audited
            # combine is explicitly confirmed (and even then never move payments).
            def _financial(o):
                return bool(o.payment_ids) or (o.amount_paid or 0) > 0 or (o.amount_total or 0) < 0
            if (_financial(src) or _financial(dst)) and not kw.get('combine_confirm'):
                self._audit(env, 'table.merge_blocked', dst, **self._actor(env, kw),
                            detail=json.dumps({'from': src_id, 'to': dst_id,
                                               'src_paid': src.amount_paid, 'dst_paid': dst.amount_paid}))
                return self._json({'ok': False, 'error': 'merge_blocked_payments',
                                   'message': 'Cannot merge: one or both orders have payments/'
                                              'reversals. Settle or use an audited combine.',
                                   'src_paid': src.amount_paid, 'dst_paid': dst.amount_paid}, status=409)
            # re-home the source's lines and KDS tickets onto the target
            src.lines.write({'order_id': dst.id})
            env['mezze.kds.ticket'].search([('pos_order_id', '=', src.id)]).write(
                {'pos_order_id': dst.id})
            label = self._table_label(env['restaurant.table'].browse(dst_id))
            env['mezze.kds.ticket'].search([('pos_order_id', '=', dst.id)]).write(
                {'table_label': label})
            if 'customer_count' in dst._fields:
                dst.customer_count = (dst.customer_count or 0) + (src.customer_count or 0)
            # recompute the target total across the combined lines
            tot_base = sum(dst.lines.mapped('price_subtotal'))
            tot_incl = sum(dst.lines.mapped('price_subtotal_incl'))
            dst.write({'amount_tax': tot_incl - tot_base, 'amount_total': tot_incl})
            self._refire_snapshot(env, dst)
            src_ref = src.pos_reference
            src.unlink()                     # emptied draft — safe to remove
            self._audit(env, 'table.merge', dst, **self._actor(env, kw),
                        detail=json.dumps({'from': src_id, 'to': dst_id,
                                           'source_ref': src_ref}))
            return {'ok': True, 'merged': True, 'order_id': dst.id,
                    'order_uuid': dst.uuid, 'to_table_id': dst_id,
                    'table_label': label, 'amount_total': dst.amount_total}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze table merge failed")
            return self._json({'ok': False, 'error': 'merge_failed',
                               'message': str(exc)}, status=400)

    # ------------------------------------------------------------------
    # 86 — mark a menu item unavailable, live, per branch
    # ------------------------------------------------------------------
    # "86ing" is a temporary stockout ("we're out of the salmon"), not a permanent
    # catalog change — so we DON'T flip the global product.available_in_pos (that
    # would 86 the item across every branch). Instead we keep a per-config set of
    # 86'd product ids and broadcast it live, so one branch running out never
    # blanks the dish on another branch's menu.
    def _eightysix_key(self, config_id):
        return 'mezze_bridge.eightysix_%s' % int(config_id or 0)

    def _eightysix_ids(self, env, config_id):
        raw = env['ir.config_parameter'].sudo().get_param(self._eightysix_key(config_id), '[]')
        try:
            return set(int(i) for i in json.loads(raw))
        except Exception:  # noqa: BLE001
            return set()

    def _set_eightysix_ids(self, env, config_id, ids):
        env['ir.config_parameter'].sudo().set_param(
            self._eightysix_key(config_id), json.dumps(sorted(int(i) for i in ids)))

    def _assert_available(self, env, config, products):
        """Raise if any of ``products`` is currently 86'd on this config — a stale
        client can't push an order for an item the branch has run out of."""
        blocked = self._eightysix_ids(env, config.id)
        for p in products:
            if p.id in blocked:
                raise ValueError("'%s' is 86'd (out of stock) — remove it to continue"
                                 % p.display_name)

    @http.route(f'{API_PREFIX}/menu/eightysix', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*', readonly=False)
    def menu_eightysix(self, config_id=None, product_id=None, available=None, **kw):
        """One-tap 86 / restore for a menu item on THIS branch. ``available=false``
        86s it; ``available=true`` restores it. Broadcasts ``mezze_menu_86`` on the
        branch's waiter channel so every terminal greys (or un-greys) the tile
        instantly, and audits the call."""
        auth = self._authorize()
        if auth:
            return auth
        env = self._api_env()
        try:
            cfg = int(config_id or 0)
            pid = int(product_id)
            product = env['product.product'].browse(pid)
            if not product.exists():
                raise ValueError("Unknown product_id %s" % product_id)
            ids = self._eightysix_ids(env, cfg)
            make_unavailable = str(available).strip().lower() in ('0', 'false', 'no', 'none', '')
            if make_unavailable:
                ids.add(pid)
            else:
                ids.discard(pid)
            self._set_eightysix_ids(env, cfg, ids)
            payload = {'product_id': pid, 'available': not make_unavailable,
                       'name': product.display_name}
            env['bus.bus'].sudo()._sendone('mezze_waiter_%s' % cfg, 'mezze_menu_86', payload)
            self._audit(env, 'menu.86', **self._actor(env, kw),
                        detail=json.dumps({'product': product.display_name, 'product_id': pid,
                                           'action': '86' if make_unavailable else 'restore',
                                           'config_id': cfg}, default=str))
            return {'ok': True, 'product_id': pid, 'available': not make_unavailable,
                    'count_86': len(ids)}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze 86 failed")
            return self._json({'ok': False, 'error': 'eightysix_failed',
                               'message': str(exc)}, status=400)

    # ------------------------------------------------------------------
    # Customer-facing display (CFD) — a second screen mirroring the live cart
    # ------------------------------------------------------------------
    # The cashier terminal PUSHES a cart snapshot on every change; the snapshot
    # is stored per branch and broadcast on the CFD bus channel so a second
    # screen (cfd.html) reflects it instantly. No new model — the snapshot is a
    # small JSON blob in a config param, same pattern as 86 / quick keys.
    def _cfd_key(self, config_id):
        return 'mezze_bridge.cfd_%s' % int(config_id or 0)

    @http.route(f'{API_PREFIX}/cfd/push', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*', readonly=False)
    def cfd_push(self, config_id=None, lines=None, subtotal=0.0, tax=0.0,
                 total=0.0, state='building', change=0.0, **kw):
        """Cashier → CFD: store + broadcast the current cart snapshot."""
        auth = self._authorize()
        if auth:
            return auth
        env = self._api_env()
        try:
            cfg = int(config_id or 0)
            snap = {
                'lines': [{'name': str(l.get('name', '')), 'qty': float(l.get('qty', 0) or 0),
                           'price': float(l.get('price', 0) or 0)} for l in (lines or [])],
                'subtotal': round(float(subtotal or 0), 2), 'tax': round(float(tax or 0), 2),
                'total': round(float(total or 0), 2), 'state': state,
                'change': round(float(change or 0), 2),
            }
            env['ir.config_parameter'].sudo().set_param(self._cfd_key(cfg), json.dumps(snap))
            env['bus.bus'].sudo()._sendone('mezze_cfd_%s' % cfg, 'mezze_cfd_update', snap)
            return {'ok': True}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze cfd_push failed")
            return self._json({'ok': False, 'error': 'cfd_push_failed', 'message': str(exc)}, status=400)

    @http.route(f'{API_PREFIX}/cfd/state', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def cfd_state(self, config_id=None, **kw):
        """CFD screen → server: the last cart snapshot + branch identity + the bus
        channel to subscribe to for live updates."""
        auth = self._authorize()
        if auth:
            return auth
        env = self._api_env()
        try:
            config = self._resolve_config(env, config_id)
            cfg = config.id
            raw = env['ir.config_parameter'].sudo().get_param(self._cfd_key(cfg), '{}')
            try:
                snap = json.loads(raw)
            except Exception:  # noqa: BLE001
                snap = {}
            return {'ok': True, 'snapshot': snap or None,
                    'branch': config.name, 'currency': _display_currency(config),
                    'channel': 'mezze_cfd_%s' % cfg,
                    'last_bus_id': env['bus.bus'].sudo()._bus_last_id()}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze cfd_state failed")
            return self._json({'ok': False, 'error': 'cfd_state_failed', 'message': str(exc)}, status=400)

    # ------------------------------------------------------------------
    # Time clock — staff attendance (mezze.attendance on mezze.cashier)
    # ------------------------------------------------------------------
    def _day_start(self, env):
        """Start-of-today (UTC, naive) for 'today' attendance queries."""
        return fields.Datetime.to_string(fields.Datetime.now().replace(
            hour=0, minute=0, second=0, microsecond=0))

    @http.route(f'{API_PREFIX}/clock/toggle', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*', readonly=False)
    def clock_toggle(self, code=None, pin=None, config_id=None, **kw):
        """Staff clock in / out with their OWN code + PIN (so nobody clocks a
        colleague). Toggles: an open record → clock OUT; none → clock IN."""
        auth = self._authorize()
        if auth:
            return auth
        env = self._api_env()
        try:
            cashier = env['mezze.cashier'].sudo().search(
                [('code', '=', code), ('active', '=', True)], limit=1)
            if not cashier or not cashier.check_pin(pin):
                self._audit(env, 'clock.denied', severity='warning',
                            detail=json.dumps({'code': code}, default=str))
                return self._json({'ok': False, 'error': 'bad_credentials',
                                   'message': 'Wrong staff code or PIN'}, status=401)
            Att = env['mezze.attendance']
            openrec = Att._open_for(cashier)
            if openrec:
                openrec.write({'check_out': fields.Datetime.now()})
                action, rec = 'out', openrec
            else:
                rec = Att.create({'cashier_id': cashier.id,
                                  'config_id': int(config_id) if config_id else False})
                action = 'in'
            self._audit(env, 'clock.%s' % action, cashier_id=cashier.id,
                        detail=json.dumps({'name': cashier.name,
                                           'worked_hours': rec.worked_hours}, default=str))
            return {'ok': True, 'action': action, 'clocked_in': action == 'in',
                    'cashier': cashier.name, 'role': cashier.role,
                    'since': fields.Datetime.to_string(rec.check_in),
                    'worked_hours': round(rec.worked_hours, 2)}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze clock toggle failed")
            return self._json({'ok': False, 'error': 'clock_failed',
                               'message': str(exc)}, status=400)

    @http.route(f'{API_PREFIX}/clock/list', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def clock_list(self, config_id=None, **kw):
        """Today's attendance: who's on the clock now + hours worked per person."""
        auth = self._authorize()
        if auth:
            return auth
        env = self._api_env()
        try:
            Att = env['mezze.attendance']
            now = fields.Datetime.now()
            recs = Att.search([('check_in', '>=', self._day_start(env))])
            by_cashier = {}
            for a in recs:
                c = a.cashier_id
                d = by_cashier.setdefault(c.id, {
                    'cashier_id': c.id, 'name': c.name, 'role': c.role,
                    'clocked_in': False, 'since': None, 'hours_today': 0.0})
                if a.check_out:
                    d['hours_today'] += a.worked_hours
                else:                        # open shift → count elapsed so far
                    d['clocked_in'] = True
                    d['since'] = fields.Datetime.to_string(a.check_in)
                    d['hours_today'] += (now - a.check_in).total_seconds() / 3600.0
            staff = sorted(by_cashier.values(),
                           key=lambda s: (not s['clocked_in'], s['name']))
            for s in staff:
                s['hours_today'] = round(s['hours_today'], 2)
            return {'ok': True, 'staff': staff,
                    'on_clock': sum(1 for s in staff if s['clocked_in']),
                    'hours_total': round(sum(s['hours_today'] for s in staff), 2)}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze clock list failed")
            return self._json({'ok': False, 'error': 'clock_list_failed',
                               'message': str(exc)}, status=400)

    # ------------------------------------------------------------------
    # Quick keys — a manager-curated favourites strip, per branch
    # ------------------------------------------------------------------
    # Distinct from the AI "suggested" strip (which is data-driven market-basket):
    # these are hand-pinned fast movers a manager wants one tap away. Stored as an
    # ORDERED per-config list so the strip layout is stable.
    def _quickkeys_key(self, config_id):
        return 'mezze_bridge.quickkeys_%s' % int(config_id or 0)

    def _quickkeys(self, env, config_id):
        raw = env['ir.config_parameter'].sudo().get_param(self._quickkeys_key(config_id), '[]')
        try:
            return [int(i) for i in json.loads(raw)]
        except Exception:  # noqa: BLE001
            return []

    def _set_quickkeys(self, env, config_id, ids):
        env['ir.config_parameter'].sudo().set_param(
            self._quickkeys_key(config_id), json.dumps([int(i) for i in ids]))

    @http.route(f'{API_PREFIX}/menu/quickkeys', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def menu_quickkeys(self, config_id=None, product_id=None, pinned=None,
                       order=None, **kw):
        """Pin/unpin a product to this branch's quick-keys strip, or reorder it.

        - ``product_id`` + ``pinned`` (bool): add/remove that product.
        - ``order`` (list of product ids): replace the whole strip order.

        Returns the resulting ordered list. Broadcasts ``mezze_quickkeys`` so
        other terminals refresh their strip."""
        auth = self._authorize()
        if auth:
            return auth
        env = self._api_env()
        try:
            cfg = int(config_id or 0)
            ids = self._quickkeys(env, cfg)
            if order is not None:
                ids = [int(i) for i in order]
            elif product_id is not None:
                pid = int(product_id)
                want = str(pinned).strip().lower() not in ('0', 'false', 'no', 'none', '')
                if want and pid not in ids:
                    ids.append(pid)
                elif not want and pid in ids:
                    ids = [i for i in ids if i != pid]
            self._set_quickkeys(env, cfg, ids)
            env['bus.bus'].sudo()._sendone('mezze_waiter_%s' % cfg, 'mezze_quickkeys',
                                           {'quick_keys': ids})
            self._audit(env, 'menu.quickkeys', **self._actor(env, kw),
                        detail=json.dumps({'config_id': cfg, 'count': len(ids),
                                           'product_id': product_id}, default=str))
            return {'ok': True, 'quick_keys': ids}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze quickkeys failed")
            return self._json({'ok': False, 'error': 'quickkeys_failed',
                               'message': str(exc)}, status=400)

    def _recipe_cost(self, product):
        """Live *theoretical* recipe cost per unit, exploded from the product's
        BoM using current component standard_prices (one level). This is the
        ERP-native food cost Odoo only reconciles at session close — we compute
        it per sale. Falls back to the product's own standard_price when no BoM
        exists, so non-recipe items still cost cleanly."""
        env = product.env
        if 'mrp.bom' not in env:
            return product.standard_price
        bom = env['mrp.bom'].search([
            '|', ('product_id', '=', product.id),
            '&', ('product_id', '=', False),
            ('product_tmpl_id', '=', product.product_tmpl_id.id),
        ], limit=1)
        if bom and bom.product_qty:
            comp = sum(l.product_id.standard_price * l.product_qty for l in bom.bom_line_ids)
            return comp / bom.product_qty
        return product.standard_price

    # ------------------------------------------------------------------
    # Ops summary — real KPIs / top products / hourly sales / food-cost
    # ------------------------------------------------------------------
    @http.route(f'{API_PREFIX}/ops/summary', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def ops_summary(self, config_id=None, **kw):
        auth = self._authorize()
        if auth:
            return auth
        try:
            env = self._api_env()
            Order = env['pos.order']
            start = fields.Datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            dom = [('state', 'in', ('paid', 'done', 'invoiced')),
                   ('date_order', '>=', fields.Datetime.to_string(start))]
            if config_id:
                dom.append(('config_id', '=', int(config_id)))
            orders = Order.search(dom)
            net = sum(orders.mapped('amount_total'))
            tx = len(orders)
            rev = 0.0
            theo_cost = 0.0                    # live recipe (theoretical) COGS
            recipe_cache = {}
            bom_cache = {}
            comp_used = {}                     # component pid -> qty consumed today
            comp_prod = {}                     # component pid -> product record
            pstats = {}                        # pid -> live food-cost stats
            buckets = {}
            for o in orders:
                try:
                    hour = fields.Datetime.context_timestamp(o, o.date_order).hour
                except Exception:  # noqa: BLE001
                    hour = 0
                buckets[hour] = buckets.get(hour, 0.0) + o.amount_total
                for l in o.lines:
                    if l.qty <= 0:
                        continue
                    p = l.product_id
                    if p.id not in recipe_cache:
                        recipe_cache[p.id] = self._recipe_cost(p)
                    rc = recipe_cache[p.id]        # theoretical, per unit
                    bc = p.standard_price or 0.0   # actual booked, per unit
                    # explode the BoM to accumulate real component consumption
                    if p.id not in bom_cache:
                        bom_cache[p.id] = env['mrp.bom'].search([
                            '|', ('product_id', '=', p.id),
                            '&', ('product_id', '=', False),
                            ('product_tmpl_id', '=', p.product_tmpl_id.id),
                        ], limit=1) if 'mrp.bom' in env else env['pos.order'].browse()
                    bom = bom_cache[p.id]
                    if bom and bom.product_qty:
                        for bl in bom.bom_line_ids:
                            cid = bl.product_id.id
                            comp_used[cid] = comp_used.get(cid, 0.0) + (bl.product_qty / bom.product_qty) * l.qty
                            comp_prod[cid] = bl.product_id
                    sub = l.price_subtotal_incl
                    rev += sub
                    theo_cost += rc * l.qty
                    s = pstats.setdefault(p.id, {
                        'name': p.display_name, 'qty': 0.0, 'rev': 0.0,
                        'recipe': 0.0, 'booked': 0.0})
                    s['qty'] += l.qty
                    s['rev'] += sub
                    s['recipe'] += rc * l.qty
                    s['booked'] += bc * l.qty
            margin = ((rev - theo_cost) / rev * 100.0) if rev else 0.0
            top = sorted(pstats.values(), key=lambda x: -x['rev'])[:6]
            hourly = [{'h': h, 'v': round(buckets[h], 2)} for h in sorted(buckets)]
            # Burn-rate: project each ingredient's stock-out from real on-hand,
            # today's actual sales velocity, and the recipe consumption.
            now = fields.Datetime.now()
            first = min(orders.mapped('date_order')) if orders else now
            hours = max((now - first).total_seconds() / 3600.0, 0.5)
            burnrate = []
            for cid, used in comp_used.items():
                cp = comp_prod[cid]
                on_hand = cp.qty_available
                rate = used / hours                     # units consumed per hour
                if rate <= 0:
                    continue
                hto = on_hand / rate                    # hours to stock-out
                burnrate.append({
                    'name': cp.display_name, 'on_hand': round(on_hand, 1),
                    'used_today': round(used, 1), 'rate_per_hr': round(rate, 2),
                    'hours_to_out': round(hto, 1),
                })
            burnrate = sorted(burnrate, key=lambda x: x['hours_to_out'])
            foodcost = [{
                'name': s['name'], 'qty': s['qty'], 'revenue': round(s['rev'], 2),
                'theoretical': round(s['recipe'], 2),    # recipe cost, live
                'actual': round(s['booked'], 2),         # booked product cost
                'variance': round(s['booked'] - s['recipe'], 2),   # actual − theoretical
                'variance_pct': round((s['booked'] - s['recipe']) / s['recipe'] * 100, 1) if s['recipe'] else 0.0,
                'foodcost_pct': round(s['recipe'] / s['rev'] * 100, 1) if s['rev'] else 0.0,
            } for s in top]
            return {
                'ok': True,
                'net_sales': round(net, 2), 'tx': tx,
                'avg_ticket': round(net / tx, 2) if tx else 0.0,
                'margin': round(margin, 1),
                'theoretical_cost': round(theo_cost, 2),
                'top_products': [{'name': s['name'], 'revenue': round(s['rev'], 2)} for s in top],
                'hourly': hourly,
                'foodcost': foodcost,
                'burnrate': burnrate,
            }
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze ops_summary failed")
            return self._json({'ok': False, 'error': 'ops_failed', 'message': str(exc)}, status=400)

    # ------------------------------------------------------------------
    # Manager dashboard — live shift command centre (real data)
    # ------------------------------------------------------------------
    @http.route(f'{API_PREFIX}/manager/dashboard', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def manager_dashboard(self, config_id=None, sla_minutes=15, **kw):
        """A shift manager's command centre — everything the floor + kitchen +
        till say right now, from real Odoo records:

        * sales    — net / tx / avg ticket / live recipe margin (today, paid)
        * service  — open tabs (unpaid table drafts) + amount + oldest, occupancy
        * kitchen  — open tickets, avg prep time (fired→ready), oldest open,
                     SLA breaches, and a per-station breakdown, all from the
                     mezze.kds.ticket timestamps
        * servers  — today's paid orders grouped by user (sales + order count)
        * alerts   — derived exceptions ranked by urgency
        """
        auth = self._authorize()
        if auth:
            return auth
        try:
            env = self._api_env()
            Order = env['pos.order']
            Ticket = env['mezze.kds.ticket']
            now = fields.Datetime.now()
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            cfg_dom = [('config_id', '=', int(config_id))] if config_id else []

            # ---- Sales (today, finalised) ----
            paid = Order.search(cfg_dom + [
                ('state', 'in', ('paid', 'done', 'invoiced')),
                ('date_order', '>=', fields.Datetime.to_string(start))])
            net = sum(paid.mapped('amount_total'))
            tx = len(paid)
            rev = theo = 0.0
            rcache = {}
            servers = {}
            for o in paid:
                for l in o.lines:
                    if l.qty <= 0:
                        continue
                    p = l.product_id
                    if p.id not in rcache:
                        rcache[p.id] = self._recipe_cost(p)
                    rev += l.price_subtotal_incl
                    theo += rcache[p.id] * l.qty
                u = o.user_id
                s = servers.setdefault(u.id, {'name': u.name or '-', 'orders': 0, 'sales': 0.0})
                s['orders'] += 1
                s['sales'] += o.amount_total
            margin = ((rev - theo) / rev * 100.0) if rev else 0.0

            # ---- Service: open tabs (unpaid table drafts) + occupancy ----
            drafts = Order.search(cfg_dom + [('state', '=', 'draft')])
            table_drafts = drafts.filtered(lambda o: 'table_id' in o._fields and o.table_id)
            open_amount = sum(table_drafts.mapped('amount_total'))
            def _age_min(dt):
                return int((now - dt).total_seconds() / 60) if dt else 0
            oldest_tab = max((_age_min(o.date_order) for o in table_drafts), default=0)
            total_tables = env['restaurant.table'].search_count(
                [('active', '=', True)]) if 'restaurant.table' in env else 0
            occupied = len(table_drafts.mapped('table_id'))

            # ---- Kitchen performance from ticket timestamps ----
            tdom = cfg_dom + [('fired_at', '>=', fields.Datetime.to_string(start))]
            todays = Ticket.search(tdom)
            open_states = ('fired', 'accepted', 'preparing')
            open_tix = todays.filtered(lambda t: t.state in open_states)
            ready_waiting = todays.filtered(lambda t: t.state == 'ready')
            prep_samples = [(t.ready_at - t.fired_at).total_seconds()
                            for t in todays if t.ready_at and t.fired_at]
            avg_prep = sum(prep_samples) / len(prep_samples) if prep_samples else 0.0
            oldest_open = max((_age_min(t.fired_at) for t in open_tix), default=0)
            sla = int(sla_minutes or 15)
            breaches = open_tix.filtered(lambda t: _age_min(t.fired_at) >= sla)
            by_station = {}
            for t in todays:
                st = by_station.setdefault(t.station, {'station': t.station, 'open': 0, 'prep': [], 'breach': 0})
                if t.state in open_states:
                    st['open'] += 1
                    if _age_min(t.fired_at) >= sla:
                        st['breach'] += 1
                if t.ready_at and t.fired_at:
                    st['prep'].append((t.ready_at - t.fired_at).total_seconds())
            stations = [{
                'station': s['station'], 'open': s['open'], 'breach': s['breach'],
                'avg_prep_sec': int(sum(s['prep']) / len(s['prep'])) if s['prep'] else 0,
            } for s in sorted(by_station.values(), key=lambda x: (-x['open'], x['station']))]

            # ---- Derived alerts, most urgent first ----
            alerts = []
            for t in breaches.sorted(lambda t: t.fired_at)[:5]:
                alerts.append({'level': 'crit', 'kind': 'sla',
                               'label': '%s / %s' % (t.table_label or (t.pos_order_id.tracking_number or ''), t.station),
                               'minutes': _age_min(t.fired_at)})
            for o in table_drafts.sorted(lambda o: o.date_order)[:5]:
                mins = _age_min(o.date_order)
                if mins >= 45:
                    tbl = o.table_id
                    alerts.append({'level': 'warn', 'kind': 'long_tab',
                                   'label': 'T%s' % (tbl.table_number if 'table_number' in tbl._fields else tbl.id),
                                   'minutes': mins})
            alerts = sorted(alerts, key=lambda a: (0 if a['level'] == 'crit' else 1, -a['minutes']))[:6]

            return {
                'ok': True,
                'as_of': fields.Datetime.to_string(now),
                'sales': {'net': round(net, 2), 'tx': tx,
                          'avg_ticket': round(net / tx, 2) if tx else 0.0,
                          'margin': round(margin, 1)},
                'service': {'open_tabs': len(table_drafts), 'open_amount': round(open_amount, 2),
                            'occupied': occupied, 'total_tables': total_tables,
                            'oldest_tab_min': oldest_tab},
                'kitchen': {'open_tickets': len(open_tix), 'ready_waiting': len(ready_waiting),
                            'avg_prep_sec': int(avg_prep), 'oldest_open_min': oldest_open,
                            'sla_minutes': sla, 'sla_breaches': len(breaches),
                            'stations': stations},
                'servers': sorted(({'name': s['name'], 'orders': s['orders'],
                                    'sales': round(s['sales'], 2)} for s in servers.values()),
                                   key=lambda x: -x['sales']),
                'alerts': alerts,
            }
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze manager_dashboard failed")
            return self._json({'ok': False, 'error': 'manager_failed', 'message': str(exc)}, status=400)

    # ------------------------------------------------------------------
    # AI upsell — market-basket recommender over real order history
    # ------------------------------------------------------------------
    @http.route(f'{API_PREFIX}/ai/upsell', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def ai_upsell(self, config_id=None, cart=None, limit=3, **kw):
        """Suggest add-ons for the current cart from REAL sales history.

        Association mining over paid-order baskets: for a candidate Y and a cart
        item X we use the confidence P(Y|X) = (#baskets with X and Y)/(#baskets
        with X), and the lift P(Y|X)/P(Y) to favour genuinely-associated pairs
        over merely-popular ones. Items already in the cart are excluded. When the
        signal is thin (or the cart is empty) we fall back to overall popularity,
        so there's always a useful suggestion. Every suggestion is explainable.
        """
        auth = self._authorize()
        if auth:
            return auth
        try:
            env = self._api_env()
            cart_ids = set(int(x) for x in (cart or []))
            orders = env['pos.order'].search([('state', 'in', ('paid', 'done', 'invoiced'))])
            baskets, freq, pair = 0, {}, {}
            for o in orders:
                pset = {l.product_id.id for l in o.lines if l.qty > 0}
                if not pset:
                    continue
                baskets += 1
                for p in pset:
                    freq[p] = freq.get(p, 0) + 1
                for x in pset:
                    for y in pset:
                        if x != y:
                            pair[(x, y)] = pair.get((x, y), 0) + 1

            # Recommend from the CALLER's branch menu, not the whole database:
            # suggesting a product the till cannot sell is worse than not suggesting.
            _scope = self._mezze_principal_scope(env)
            _cfg = env['pos.config'].browse(_scope['branch']) if _scope.get('branch') else None
            candidates = env['product.product'].search(self._menu_domain(env, _cfg))
            prod_by_id = {p.id: p for p in candidates}
            cand_ids = [p.id for p in candidates if p.id not in cart_ids]

            scored = []
            for y in cand_ids:
                best_conf, driver = 0.0, None
                for x in cart_ids:
                    cx = freq.get(x, 0)
                    if cx:
                        conf = pair.get((x, y), 0) / cx
                        if conf > best_conf:
                            best_conf, driver = conf, x
                support_y = (freq.get(y, 0) / baskets) if baskets else 0.0
                lift = (best_conf / support_y) if support_y else 0.0
                if best_conf > 0:
                    scored.append({'y': y, 'kind': 'affinity', 'conf': best_conf,
                                   'lift': lift, 'driver': driver})
            scored.sort(key=lambda s: (-s['conf'], -s['lift']))

            # Fill (or fully seed, for an empty cart) with popular items.
            if len(scored) < int(limit):
                have = {s['y'] for s in scored}
                for y in sorted(cand_ids, key=lambda p: -freq.get(p, 0)):
                    if y in have or freq.get(y, 0) == 0:
                        continue
                    scored.append({'y': y, 'kind': 'popular',
                                   'conf': 0.0, 'lift': 0.0, 'driver': None})

            out = []
            for s in scored[:int(limit)]:
                p = prod_by_id.get(s['y'])
                if not p:
                    continue
                driver = prod_by_id.get(s['driver']) if s['driver'] else None
                out.append({
                    'product_id': p.id, 'name': p.display_name, 'price': p.lst_price,
                    'kind': s['kind'],
                    'with': driver.display_name if driver else None,
                    'confidence': round(s['conf'], 2), 'lift': round(s['lift'], 2),
                    'has_modifiers': bool(self._product_modifiers(env, p)),
                })
            return {'ok': True, 'baskets': baskets, 'suggestions': out}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze ai_upsell failed")
            return self._json({'ok': False, 'error': 'upsell_failed', 'message': str(exc)}, status=400)

    # ------------------------------------------------------------------
    # Loyalty — real Odoo loyalty.program / loyalty.card / loyalty.history
    # ------------------------------------------------------------------
    LOYALTY_PROGRAM = 'Mezze Rewards'

    def _loyalty_program(self, env, create=False):
        """The Mezze loyalty programme. NEVER creates it from a request.

        Provisioning lives in ``models/loyalty_bootstrap.py`` and runs on install and
        on upgrade. A lazy create here looks tidier and cannot work: several loyalty
        routes are read-only, Odoo runs them on a read-only cursor, and an INSERT
        there does not merely fail — it aborts the transaction, so the read that
        triggered it fails too.

        ``create`` is accepted so a genuinely writable caller can opt in, and defaults
        to False so the safe answer is the one you get by not thinking about it.
        """
        prog = env['loyalty.program'].sudo().search(
            [('name', '=', self.LOYALTY_PROGRAM), ('program_type', '=', 'loyalty')],
            limit=1)
        if prog or not create:
            return prog
        from ..models.loyalty_bootstrap import ensure_loyalty_program
        try:
            return ensure_loyalty_program(env)
        except Exception:  # noqa: BLE001
            _logger.exception("Mezze could not provision the loyalty programme")
            return env['loyalty.program'].sudo()

    def _loyalty_card(self, env, partner, create=True):
        """The partner's loyalty card for the Mezze programme (minted on first
        use). Returns an empty recordset if there is no programme."""
        prog = self._loyalty_program(env)
        if not prog or not partner:
            return env['loyalty.card'].sudo()
        Card = env['loyalty.card'].sudo()
        card = Card.search([('program_id', '=', prog.id), ('partner_id', '=', partner.id)], limit=1)
        if not card and create:
            card = Card.create({'program_id': prog.id, 'partner_id': partner.id, 'points': 0.0})
        return card

    def _loyalty_rewards(self, env, prog):
        return [{'id': r.id, 'points': r.required_points,
                 'discount': r.discount, 'mode': r.discount_mode,
                 'name': 'EGP %s off' % int(r.discount) if r.reward_type == 'discount'
                         else (r.reward_product_id.display_name or 'Reward')}
                for r in prog.reward_ids if r.reward_type == 'discount']

    def _loyalty_earn(self, env, order):
        """Award loyalty points for a finalised order (real loyalty.history +
        card balance). 1 point per currency unit spent, per the programme rule.
        No-op when the order has no partner or no programme. Returns (earned,
        balance) or (0, None)."""
        partner = order.partner_id
        if not partner:
            return 0.0, None
        prog = self._loyalty_program(env, create=True)
        if not prog:
            return 0.0, None
        rule = prog.rule_ids[:1]
        amount = order.amount_total
        rate = rule.reward_point_amount if rule else 1.0
        mode = rule.reward_point_mode if rule else 'money'
        earned = float(int(amount * rate)) if mode == 'money' else (rate if mode == 'order' else 0.0)
        if earned <= 0:
            return 0.0, self._loyalty_card(env, partner).points
        card = self._loyalty_card(env, partner)
        card.sudo().write({'points': card.points + earned})
        env['loyalty.history'].sudo().create({
            'card_id': card.id, 'issued': earned, 'used': 0.0,
            'description': 'Mezze order %s' % (order.pos_reference or order.id),
        })
        return earned, card.points

    @http.route(f'{API_PREFIX}/loyalty/search', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def loyalty_search(self, q=None, limit=8, **kw):
        """Find customers by name/phone with their REAL loyalty points, plus the
        programme's rewards catalogue."""
        auth = self._authorize()
        if auth:
            return auth
        try:
            env = self._api_env()
            prog = self._loyalty_program(env)
            domain = []
            if q:
                domain = ['|', ('name', 'ilike', q), ('phone', 'ilike', q)]
            else:
                # default: show customers who actually hold a card
                cards = env['loyalty.card'].sudo().search([('program_id', '=', prog.id)]) if prog else env['loyalty.card']
                domain = [('id', 'in', cards.mapped('partner_id').ids)] if prog else [('customer_rank', '>', 0)]
            partners = env['res.partner'].sudo().search(domain, limit=int(limit))
            bal = {}
            if prog:
                for c in env['loyalty.card'].sudo().search(
                        [('program_id', '=', prog.id), ('partner_id', 'in', partners.ids)]):
                    bal[c.partner_id.id] = c.points
            return {
                'ok': True,
                'program': prog.name if prog else None,
                'rewards': self._loyalty_rewards(env, prog) if prog else [],
                'customers': [{'id': p.id, 'name': p.name, 'phone': p.phone or '',
                               'points': bal.get(p.id, 0.0)} for p in partners],
            }
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze loyalty_search failed")
            return self._json({'ok': False, 'error': 'loyalty_search_failed', 'message': str(exc)}, status=400)

    # ------------------------------------------------------------------
    # Rewards as REAL reward lines.
    #
    # ``pos_loyalty`` is auto-installed in every Mezze database — it depends on
    # ``loyalty`` and ``point_of_sale``, both of which this addon already requires —
    # so ``pos.order.line`` has carried ``is_reward_line``, ``reward_id``,
    # ``coupon_id``, ``reward_identifier_code`` and ``points_cost`` all along.
    #
    # Mezze wrote anonymous negative lines instead. That is why ``sync_from_ui``
    # strips a redeemed order's discount line — it wants reward metadata and finds
    # none — and why the redeem path has to create a draft and then patch it through
    # the ORM. Writing the native fields makes native reporting, native reload and
    # the native session close see a reward for what it is.
    # ------------------------------------------------------------------
    def _reward_lines(self, order):
        """Existing reward lines on an order."""
        if not order or 'is_reward_line' not in order.lines._fields:
            return order.lines.browse() if order else order
        return order.lines.filtered(lambda l: l.is_reward_line)

    def _order_base_for_reward(self, order):
        """What a percentage reward applies to: the bill WITHOUT existing rewards.

        Discounting a discount is how a second reward quietly doubles the first.
        """
        rewards = self._reward_lines(order)
        return sum((order.lines - rewards).mapped('price_subtotal_incl'))

    def _reward_specific_total(self, order, rew):
        """Total of the lines a 'specific products' reward is allowed to touch."""
        allowed = rew.all_discount_product_ids
        if not allowed:
            return 0.0
        rewards = self._reward_lines(order)
        return sum((order.lines - rewards).filtered(
            lambda l: l.product_id in allowed).mapped('price_subtotal_incl'))

    def _reward_cheapest_price(self, order):
        rewards = self._reward_lines(order)
        prices = [l.price_subtotal_incl / (l.qty or 1.0)
                  for l in (order.lines - rewards) if l.qty > 0]
        return min(prices) if prices else 0.0

    def _write_reward_line(self, env, order, rew, card, points_spent, config):
        """Add the reward to the order as a NATIVE reward line. Returns the line."""
        code = 'mezze-%s-%s' % (rew.id, order.id)
        if rew.reward_type == 'product':
            product = rew.reward_product_id or rew.reward_product_ids[:1]
            if not product:
                return None
            qty = rew.reward_product_qty or 1.0
            # A free product is a real line at a full 100% discount, not a zero-priced
            # line: the price is what the guest would have paid and the discount is
            # what the reward gave them. Reporting needs both halves.
            vals = {
                'product_id': product.id, 'qty': qty, 'price_unit': product.lst_price,
                'discount': 100.0, 'price_subtotal': 0.0, 'price_subtotal_incl': 0.0,
                'tax_ids': [(6, 0, [])], 'pack_lot_ids': [],
            }
        else:
            base = reward_rules.discount_base(
                rew.discount_applicability,
                self._order_base_for_reward(order),
                cheapest_unit_price=self._reward_cheapest_price(order),
                specific_total=self._reward_specific_total(order, rew))
            amount = reward_rules.discount_amount(
                rew.discount_mode, rew.discount, base,
                points_spent=points_spent,
                max_amount=rew.discount_max_amount,
                remaining=max(0.0, order.amount_total))
            if amount <= 0:
                return None
            product = rew.discount_line_product_id
            if not product:
                rew.sudo()._create_missing_discount_line_products()
                product = rew.discount_line_product_id
            if not product:
                return None
            # A reward line carries no tax of its own: the discount already came off a
            # taxed basket, so taxing the reduction again double-counts it.
            vals = {
                'product_id': product.id, 'qty': 1, 'price_unit': -amount,
                'discount': 0.0, 'price_subtotal': -amount,
                'price_subtotal_incl': -amount,
                'tax_ids': [(6, 0, [])], 'pack_lot_ids': [],
            }
        line = env['pos.order.line'].sudo().create(dict(vals, order_id=order.id))
        native = {}
        if 'is_reward_line' in line._fields:
            native.update({'is_reward_line': True, 'reward_id': rew.id,
                           'points_cost': points_spent,
                           'reward_identifier_code': code})
            if card:
                native['coupon_id'] = card.id
        if native:
            line.sudo().write(native)
        return line

    def _reprice_order(self, order):
        base = sum(order.lines.mapped('price_subtotal'))
        incl = sum(order.lines.mapped('price_subtotal_incl'))
        order.sudo().write({'amount_tax': incl - base, 'amount_total': incl})
        return incl

    def _reward_order(self, env, order_id=None, order_uuid=None, session_id=None):
        """Resolve the order a reward acts on.

        Named ``_reward_order`` and not ``_resolve_order`` on purpose: another
        controller in this addon already owns that name with a different signature,
        and Odoo merges every http.Controller in a module into one dispatch surface —
        so two same-named private helpers silently shadow each other and an unrelated
        endpoint breaks. Per-controller helpers get unique names.
        """
        Order = env['pos.order']
        if order_id:
            return Order.browse(int(order_id)).exists()
        if order_uuid:
            dom = [('uuid', '=', order_uuid)]
            if session_id:
                dom.append(('session_id', '=', int(session_id)))
            return Order.search(dom, limit=1)
        return Order.browse()

    @http.route(f'{API_PREFIX}/loyalty/rewards', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*', readonly=True)
    def loyalty_rewards(self, partner_id=None, order_id=None, order_uuid=None,
                        session_id=None, **kw):
        """The rewards this guest can take on THIS order, each with a reason if not.

        A greyed-out reward with no explanation is how a cashier ends up telling a
        guest "the system won't let me", so every refusal names itself.
        """
        auth = self._authorize()
        if auth:
            return auth
        env = self._api_env()
        try:
            partner = (env['res.partner'].sudo().browse(int(partner_id))
                       if partner_id else env['res.partner'])
            prog = self._loyalty_program(env, create=False)
            if not prog:
                return {'ok': True, 'available': False, 'reason': 'no_programme',
                        'points': 0.0, 'rewards': []}
            card = self._loyalty_card(env, partner, create=False) if partner else None
            balance = card.points if card else 0.0
            order = self._reward_order(env, order_id, order_uuid, session_id)
            remaining = order.amount_total if order else 0.0
            applied = set(self._reward_lines(order).mapped('reward_id').ids) if order else set()
            out = []
            for rew in prog.reward_ids:
                spend = reward_rules.spend_for(rew.required_points, balance,
                                               bool(getattr(rew, 'clear_wallet', False)))
                ok, reason = reward_rules.claimable(
                    rew.required_points, balance, remaining,
                    reward_type=rew.reward_type, has_card=bool(card),
                    already=rew.id in applied,
                    eligible_products=bool(rew.reward_product_id or rew.reward_product_ids))
                out.append({'id': rew.id, 'description': rew.description,
                            'reward_type': rew.reward_type,
                            'required_points': rew.required_points,
                            'points_spent': spend,
                            'claimable': ok, 'reason': reason})
            return {'ok': True, 'available': True, 'points': balance, 'rewards': out}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze loyalty_rewards failed")
            return self._json({'ok': False, 'error': 'loyalty_rewards_failed',
                               'message': str(exc)}, status=400)

    @http.route(f'{API_PREFIX}/loyalty/apply', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*', readonly=False)
    def loyalty_apply(self, partner_id=None, reward_id=None, order_id=None,
                      order_uuid=None, session_id=None, **kw):
        """Take a reward, on the server, against a real order.

        The till names a REWARD; it never names an amount. That is the whole point —
        the old flow had the browser pick the number and a money route accept it.
        """
        auth = self._authorize()
        if auth:
            return auth
        env = self._api_env()
        try:
            order = self._reward_order(env, order_id, order_uuid, session_id)
            if not order:
                return self._json({'ok': False, 'error': 'order_not_found'}, status=404)
            denied = self._security_gate(env, 'loyalty/apply', target_order=order)
            if denied:
                return denied
            blocked = self._fsm_guard(env, order, 'modify', endpoint='loyalty/apply')
            if blocked:
                return blocked
            if order.state != 'draft':
                return self._json({'ok': False, 'error': 'order_not_open',
                                   'message': 'Only an open order can take a reward.'},
                                  status=400)
            rew = env['loyalty.reward'].sudo().browse(int(reward_id)).exists()
            partner = (env['res.partner'].sudo().browse(int(partner_id))
                       if partner_id else order.partner_id)
            if not rew or not partner:
                return self._json({'ok': False, 'error': 'not_found'}, status=404)
            card = self._loyalty_card(env, partner, create=False)
            if card:
                # Serialise concurrent redemptions of one card: two tills taking the
                # last reward must not both succeed.
                env.cr.execute("SELECT points FROM loyalty_card WHERE id = %s FOR UPDATE",
                               (card.id,))
                card.invalidate_recordset(['points'])
            balance = card.points if card else 0.0
            applied = set(self._reward_lines(order).mapped('reward_id').ids)
            ok, reason = reward_rules.claimable(
                rew.required_points, balance, order.amount_total,
                reward_type=rew.reward_type, has_card=bool(card),
                already=rew.id in applied,
                eligible_products=bool(rew.reward_product_id or rew.reward_product_ids))
            if not ok:
                return self._json({'ok': False, 'error': reason}, status=400)
            spend = reward_rules.spend_for(rew.required_points, balance,
                                           bool(getattr(rew, 'clear_wallet', False)))
            line = self._write_reward_line(env, order, rew, card, spend, order.config_id)
            if line is None:
                return self._json({'ok': False,
                                   'error': reward_rules.NOTHING_TO_DISCOUNT}, status=400)
            total = self._reprice_order(order)
            if card:
                card.sudo().write({'points': reward_rules.points_after(
                    balance, spend, bool(getattr(rew, 'clear_wallet', False)))})
                env['loyalty.history'].sudo().create({
                    'card_id': card.id, 'issued': 0.0, 'used': spend,
                    'description': 'Redeemed %s' % (rew.description or rew.id)})
            self._audit(env, 'loyalty.redeem', order, **self._actor(env, kw),
                        detail=json.dumps({'reward_id': rew.id,
                                           'reward': rew.description,
                                           'points_spent': spend, 'line_id': line.id,
                                           'amount_total': total}, default=str))
            return {'ok': True, 'order_id': order.id, 'line_id': line.id,
                    'reward_id': rew.id, 'points_spent': spend,
                    'points': card.points if card else 0.0, 'amount_total': total}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze loyalty_apply failed")
            return self._json({'ok': False, 'error': 'loyalty_apply_failed',
                               'message': str(exc)}, status=400)

    @http.route(f'{API_PREFIX}/loyalty/remove', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*', readonly=False)
    def loyalty_remove(self, line_id=None, order_id=None, order_uuid=None,
                       session_id=None, **kw):
        """Take a reward back off, and give the points back with it.

        Removing the line without refunding the points is how a guest pays twice for
        one reward — once in points, and again because the cashier undid it.
        """
        auth = self._authorize()
        if auth:
            return auth
        env = self._api_env()
        try:
            order = self._reward_order(env, order_id, order_uuid, session_id)
            if not order:
                return self._json({'ok': False, 'error': 'order_not_found'}, status=404)
            denied = self._security_gate(env, 'loyalty/remove', target_order=order)
            if denied:
                return denied
            if order.state != 'draft':
                return self._json({'ok': False, 'error': 'order_not_open'}, status=400)
            line = self._reward_lines(order).filtered(
                lambda l: l.id == int(line_id))[:1]
            if not line:
                return self._json({'ok': False, 'error': 'reward_line_not_found'},
                                  status=404)
            refund = line.points_cost or 0.0
            card = line.coupon_id if 'coupon_id' in line._fields else None
            rid = line.reward_id.id
            line.sudo().unlink()
            total = self._reprice_order(order)
            if card and refund:
                card.sudo().write({'points': card.points + refund})
                env['loyalty.history'].sudo().create({
                    'card_id': card.id, 'issued': refund, 'used': 0.0,
                    'description': 'Reward removed at the till'})
            self._audit(env, 'loyalty.reward_removed', order, **self._actor(env, kw),
                        detail=json.dumps({'reward_id': rid, 'points_returned': refund,
                                           'amount_total': total}, default=str))
            return {'ok': True, 'order_id': order.id, 'points_returned': refund,
                    'points': card.points if card else 0.0, 'amount_total': total}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze loyalty_remove failed")
            return self._json({'ok': False, 'error': 'loyalty_remove_failed',
                               'message': str(exc)}, status=400)

    @http.route(f'{API_PREFIX}/loyalty/redeem', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*', readonly=False)
    def loyalty_redeem(self, partner_id=None, reward_id=None, **kw):
        """Redeem a reward: deduct the required points (real loyalty.history
        'used' + card balance) and return the discount to apply to the order.
        The bridge applies the discount as a balanced order line at pay time."""
        auth = self._authorize()
        if auth:
            return auth
        try:
            env = self._api_env()
            partner = env['res.partner'].sudo().browse(int(partner_id))
            reward = env['loyalty.reward'].sudo().browse(int(reward_id))
            if not partner.exists() or not reward.exists():
                return self._json({'ok': False, 'error': 'not_found'}, status=404)
            card = self._loyalty_card(env, partner)
            if not card:
                return self._json({'ok': False, 'error': 'no_card'}, status=400)
            need = reward.required_points
            if card.points < need:
                return self._json({'ok': False, 'error': 'insufficient_points',
                                   'message': 'Needs %d, has %d' % (need, card.points)}, status=400)
            card.sudo().write({'points': card.points - need})
            env['loyalty.history'].sudo().create({
                'card_id': card.id, 'issued': 0.0, 'used': need,
                'description': 'Redeemed %s' % ('EGP %s off' % int(reward.discount)),
            })
            return {
                'ok': True, 'partner_id': partner.id, 'points': card.points,
                'reward_id': reward.id, 'discount': reward.discount,
                'discount_product_id': reward.discount_line_product_id.id or False,
                'label': 'EGP %s off' % int(reward.discount),
            }
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze loyalty_redeem failed")
            return self._json({'ok': False, 'error': 'loyalty_redeem_failed', 'message': str(exc)}, status=400)

    # ------------------------------------------------------------------
    # Gift cards / store credit — native loyalty gift_card program + card
    # ------------------------------------------------------------------
    # A gift card is a real ``loyalty.card`` on a ``gift_card`` programme
    # (points == currency, 1:1) with an auto-generated ``code``. Issuing mints a
    # card with a balance; redeeming is a TENDER (a pos.payment on the Gift Card
    # payment method) that decrements the card — not a discount, because a gift
    # card is money owed, not a markdown.
    GIFTCARD_PROGRAM = 'Mezze Gift Card'

    def _giftcard_program(self, env, create=True):
        prog = env['loyalty.program'].sudo().search(
            [('program_type', '=', 'gift_card')], limit=1)
        if not prog and create:
            prog = env['loyalty.program'].sudo().create({
                'name': self.GIFTCARD_PROGRAM, 'program_type': 'gift_card'})
        return prog

    def _giftcard_by_code(self, env, code):
        prog = self._giftcard_program(env, create=False)
        if not prog or not code:
            return env['loyalty.card'].sudo()
        return env['loyalty.card'].sudo().search(
            [('program_id', '=', prog.id), ('code', '=', str(code).strip())], limit=1)

    def _giftcard_pm(self, env, config):
        """The Gift Card pos.payment.method for this company (find-or-create).

        We try to link it to the config, but Odoo forbids editing a config's
        payment methods while a session is OPEN — so during service we skip the
        link (the pos.payment references the method directly, which is enough).
        Link it once with sessions closed (or via setup) so it shows in the UI."""
        PM = env['pos.payment.method'].sudo()
        pm = PM.search([('name', '=', 'Gift Card'),
                        ('company_id', '=', config.company_id.id)], limit=1)
        if not pm:
            # A journal MATTERS here. A pos.payment.method with none is typed
            # `pay_later` by Odoo, which Mezze classifies as `customer_account` —
            # so the credit gate demanded a customer before it would accept a gift
            # card, and an anonymous guest paying with one was refused outright.
            # A gift card is prepaid: the money arrived when the card was sold.
            journal = env['account.journal'].sudo().search(
                [('type', 'in', ('bank', 'cash')),
                 ('company_id', '=', config.company_id.id)], limit=1)
            vals = {'name': 'Gift Card', 'company_id': config.company_id.id}
            if journal:
                vals['journal_id'] = journal.id
            pm = PM.create(vals)
        if pm.id not in config.payment_method_ids.ids:
            has_open = env['pos.session'].sudo().search_count(
                [('config_id', '=', config.id), ('state', '!=', 'closed')])
            if not has_open:
                config.sudo().write({'payment_method_ids': [(4, pm.id)]})
        return pm

    def _mint_giftcards(self, env, order, kw, via='sale'):
        """Selling the gift-card product mints a card for the line amount.

        This used to live inline in the atomic-paid branch of ``/orders/sync`` — the
        one path that creates an order and settles it in a single call. The Owl till
        does not take that path: it syncs a DRAFT and then settles through
        ``/orders/pay``, so selling a gift card on the actual register collected the
        money and issued nothing. The customer paid for a card that was never created.

        Extracted so it can run wherever an order BECOMES paid, and made idempotent on
        the order's own audit trail: both settlement paths may legitimately call it,
        and a gift card minted twice is money invented twice. The audit row is the
        guard because it is written in the same transaction as the card, so there is
        no window in which a card exists without its evidence.
        """
        gc_sale = self._giftcard_sale_product(env)
        if not gc_sale:
            return []
        lines = order.lines.filtered(
            lambda x: x.product_id.id == gc_sale.id and x.price_subtotal_incl > 0)
        if not lines:
            return []
        already = env['mezze.audit.log'].sudo().search_count([
            ('event', '=', 'giftcard.issue'),
            ('res_model', '=', 'pos.order'),
            ('res_id', '=', order.id),
        ])
        if already:
            return []
        prog = self._giftcard_program(env)
        issued = []
        for line in lines:
            card = env['loyalty.card'].sudo().create({
                'program_id': prog.id, 'points': round(line.price_subtotal_incl, 2),
                'partner_id': order.partner_id.id or False})
            issued.append({'code': card.code, 'amount': card.points})
            self._audit(env, 'giftcard.issue', order, **self._actor(env, kw),
                        detail=json.dumps({'code': card.code, 'amount': card.points,
                                           'via': via}, default=str))
        return issued

    def _giftcard_sale_product(self, env):
        """Tax-free product whose SALE funds a gift card (default_code GIFTCARD).
        Selling it mints a card for the line amount — a gift-card sale is a
        liability, not taxable revenue, so it carries no tax."""
        Product = env['product.product'].sudo()
        prod = Product.search([('default_code', '=', 'GIFTCARD')], limit=1)
        if not prod:
            tmpl = env['product.template'].sudo().create({
                'name': 'Gift Card', 'default_code': 'GIFTCARD', 'type': 'service',
                'available_in_pos': True, 'list_price': 0.0, 'taxes_id': [(6, 0, [])],
            })
            prod = tmpl.product_variant_id
        # Cleared AFTER creation, not just in the values. A company with a default
        # sale tax has it applied on create regardless of what was passed, so the
        # "carries no tax" above was true only on companies that had no default —
        # elsewhere the branch charged tax on money merely being handed over, and
        # again when the card was spent.
        if prod.taxes_id:
            prod.sudo().write({'taxes_id': [(5, 0, 0)]})
        return prod

    # ------------------------------------------------------------------
    # eWallet — a PREPAID balance that belongs to a customer.
    #
    # Mechanically a gift card without a code: same loyalty.card, same "points are
    # currency" convention, same spend-at-payment rule. The differences are the ones
    # that matter to a cashier: it is found by WHO the guest is rather than by what
    # they are holding, so it needs a customer on the order and nothing to type, and
    # it is topped up by selling a product rather than issued as an object.
    # ------------------------------------------------------------------
    EWALLET_PROGRAM = 'Mezze eWallet'

    def _ewallet_program(self, env, create=True):
        prog = env['loyalty.program'].sudo().search(
            [('program_type', '=', 'ewallet')], limit=1)
        if not prog and create:
            prog = env['loyalty.program'].sudo().create({
                'name': self.EWALLET_PROGRAM, 'program_type': 'ewallet'})
        return prog

    def _ewallet_card(self, env, partner, create=False):
        """This customer's wallet. Never anonymous: a wallet with no owner is a
        balance nobody can claim and anybody can spend."""
        if not partner:
            return env['loyalty.card'].sudo()
        prog = self._ewallet_program(env, create=create)
        if not prog:
            return env['loyalty.card'].sudo()
        card = env['loyalty.card'].sudo().search(
            [('program_id', '=', prog.id), ('partner_id', '=', partner.id)], limit=1)
        if not card and create:
            card = env['loyalty.card'].sudo().create(
                {'program_id': prog.id, 'partner_id': partner.id, 'points': 0.0})
        return card

    def _ewallet_topup_product(self, env):
        """Tax-free product whose SALE credits the customer's wallet.

        Untaxed for the same reason the gift-card product is: taking money onto a
        wallet is a liability, not revenue. The tax is charged when the wallet is
        SPENT on something, and charging it at both ends would tax the guest twice.
        """
        Product = env['product.product'].sudo()
        prod = Product.search([('default_code', '=', 'EWALLET')], limit=1)
        if not prod:
            tmpl = env['product.template'].sudo().create({
                'name': 'eWallet top-up', 'default_code': 'EWALLET', 'type': 'service',
                'available_in_pos': True, 'list_price': 0.0, 'taxes_id': [(6, 0, [])],
            })
            prod = tmpl.product_variant_id
        if prod.taxes_id:
            prod.sudo().write({'taxes_id': [(5, 0, 0)]})
        return prod

    def _ewallet_pm(self, env, config):
        """The eWallet pos.payment.method for this company (find-or-create).

        A journal is set for the same reason the gift card's is: without one Odoo
        types the method ``pay_later``, Mezze reads that as a customer ACCOUNT, and
        the credit gate then demands a credit decision for money the customer has
        already handed over. Provisioned at install (see loyalty_bootstrap) because
        Odoo refuses to add a method to a config while a session is open.
        """
        PM = env['pos.payment.method'].sudo()
        pm = PM.search([('name', '=', 'eWallet'),
                        ('company_id', '=', config.company_id.id)], limit=1)
        if not pm:
            journal = env['account.journal'].sudo().search(
                [('type', 'in', ('bank', 'cash')),
                 ('company_id', '=', config.company_id.id)], limit=1)
            vals = {'name': 'eWallet', 'company_id': config.company_id.id}
            if journal:
                vals['journal_id'] = journal.id
            pm = PM.create(vals)
        if pm.id not in config.payment_method_ids.ids:
            has_open = env['pos.session'].sudo().search_count(
                [('config_id', '=', config.id), ('state', '!=', 'closed')])
            if not has_open:
                config.sudo().write({'payment_method_ids': [(4, pm.id)]})
        return pm

    def _ewallet_decrement(self, env, card, amount, ref):
        card.sudo().write({'points': card.points - amount})
        env['loyalty.history'].sudo().create({
            'card_id': card.id, 'issued': 0.0, 'used': amount,
            'description': 'eWallet spent on %s' % ref})

    def _ewallet_topup(self, env, order, kw):
        """Selling the top-up product puts money on the customer's wallet.

        Idempotent on the order's own audit trail, for the same reason the gift-card
        mint is: both settlement paths may reach the same order, and crediting twice
        invents money. Requires a customer — the wallet has to belong to somebody, and
        an anonymous top-up would take the guest's cash and credit nothing.
        """
        product = self._ewallet_topup_product(env)
        if not product:
            return None
        lines = order.lines.filtered(
            lambda l: l.product_id.id == product.id and l.price_subtotal_incl > 0)
        if not lines:
            return None
        if not order.partner_id:
            return None
        already = env['mezze.audit.log'].sudo().search_count([
            ('event', '=', 'ewallet.topup'),
            ('res_model', '=', 'pos.order'),
            ('res_id', '=', order.id),
        ])
        if already:
            return None
        amount = round(sum(lines.mapped('price_subtotal_incl')), 2)
        card = self._ewallet_card(env, order.partner_id, create=True)
        card.sudo().write({'points': card.points + amount})
        env['loyalty.history'].sudo().create({
            'card_id': card.id, 'issued': amount, 'used': 0.0,
            'description': 'eWallet topped up on %s' % (order.pos_reference or order.id)})
        self._audit(env, 'ewallet.topup', order, **self._actor(env, kw),
                    detail=json.dumps({'amount': amount, 'balance': card.points,
                                       'partner_id': order.partner_id.id}, default=str))
        return {'amount': amount, 'balance': round(card.points, 2)}

    @http.route(f'{API_PREFIX}/ewallet/balance', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*', readonly=True)
    def ewallet_balance(self, partner_id=None, **kw):
        """What this customer has on their wallet, if anything."""
        auth = self._authorize()
        if auth:
            return auth
        env = self._api_env()
        try:
            partner = env['res.partner'].sudo().browse(int(partner_id or 0))
            if not partner.exists():
                return self._json({'ok': False, 'error': 'customer_required',
                                   'message': 'A wallet belongs to a customer.'},
                                  status=400)
            card = self._ewallet_card(env, partner)
            return {'ok': True, 'partner_id': partner.id,
                    'balance': round(card.points, 2) if card else 0.0,
                    'has_wallet': bool(card)}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze ewallet_balance failed")
            return self._json({'ok': False, 'error': 'ewallet_balance_failed',
                               'message': str(exc)}, status=400)

    def _giftcard_decrement(self, env, card, amount, ref):
        card.sudo().write({'points': card.points - amount})
        env['loyalty.history'].sudo().create({
            'card_id': card.id, 'issued': 0.0, 'used': amount,
            'description': 'Gift card %s spent on %s' % (card.code, ref)})

    def _auto_promo_lines(self, order):
        """The order's existing AUTOMATIC promotion lines.

        Matched by their reward's programme where possible. Lines written before
        promotions were flagged as reward lines carry no ``reward_id``, so they are
        matched by their discount product instead — otherwise an upgraded database
        would accumulate a second copy of every promotion on the next reconcile.

        Lines from a TYPED code are deliberately not included: the guest presented a
        coupon to earn those, and removing one to re-derive it could drop a
        single-use coupon that has already been consumed.
        """
        lines = order.lines
        if 'is_reward_line' not in lines._fields:
            return lines.browse()
        auto_products = set()
        for prog in self._promo_active_programs(order.env):
            if prog.trigger != 'auto':
                continue
            auto_products |= set(prog.reward_ids.mapped('discount_line_product_id').ids)

        def is_auto(line):
            if not line.is_reward_line:
                return False
            rew = getattr(line, 'reward_id', False)
            if rew:
                prog = rew.program_id
                return (prog.trigger == 'auto'
                        and prog.program_type in self.PROMO_TYPES)
            return line.product_id.id in auto_products

        return lines.filtered(is_auto)

    @http.route(f'{API_PREFIX}/promo/auto', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*', readonly=False)
    def promo_auto(self, order_uuid=None, order_id=None, session_id=None, **kw):
        """Bring the order's automatic promotions up to date with what is in it.

        The branch's published promotions were applied on ``/shop/order`` — the
        storefront — and nowhere on the till. A guest ordering online got "buy two,
        get 20% off"; the same guest at the counter did not, and the cashier had no
        way to give it to them.

        This RECONCILES rather than adds: the existing automatic lines come off and
        the current ones go back on. That is what makes it safe to call after every
        change to the cart — adding would stack a fresh discount each time an item
        was rung up, which is the obvious implementation and quietly gives the order
        away.

        A typed coupon is left alone. The guest earned that by presenting it, and
        re-deriving it could drop a single-use code that is already consumed.
        """
        auth = self._authorize(endpoint='promo/auto')
        if auth:
            return auth
        env = self._api_env()
        try:
            order = self._reward_order(env, order_id, order_uuid, session_id)
            if not order:
                return self._json({'ok': False, 'error': 'order_not_found'}, status=404)
            denied = self._security_gate(env, 'promo/auto', target_order=order)
            if denied:
                return denied
            config = order.config_id

            stale = self._auto_promo_lines(order)
            if stale:
                stale.sudo().unlink()
                order.invalidate_recordset()

            items = order.lines.filtered(lambda l: not l.is_reward_line)
            cart = [{'product_id': l.product_id.id, 'qty': l.qty} for l in items]
            # What the guest is actually being asked for, from the order's own lines.
            incl = sum(items.mapped('price_subtotal_incl'))
            applied, discount = [], 0.0
            if cart:
                _incl, specs, _code = self._promo_for_cart(
                    env, config, order.partner_id, cart, incl=incl)
                auto = [sp for sp in (specs or []) if sp.get('auto')]
                if auto:
                    discount = self._promo_apply_to_order(env, config, order, auto)
                    applied = [{'name': sp.get('name'),
                                'amount': round(abs(sp.get('amount') or 0.0), 2)}
                               for sp in auto]
            # Totals are recomputed by _promo_apply_to_order; when nothing applied,
            # removing the stale lines still moved them.
            if not applied:
                base = sum(order.lines.mapped('price_subtotal'))
                incl = sum(order.lines.mapped('price_subtotal_incl'))
                order.write({'amount_tax': incl - base, 'amount_total': incl})
            order.invalidate_recordset()
            return {'ok': True, 'promotions': applied,
                    'discount': round(abs(discount or 0.0), 2),
                    'amount_total': round(order.amount_total, 2)}
        except Exception as exc:  # noqa: BLE001
            _reraise_if_retryable(exc)
            _logger.exception("Mezze promo_auto failed")
            return self._json({'ok': False, 'error': 'promo_auto_failed',
                               'message': str(exc)}, status=400)

    @http.route(f'{API_PREFIX}/orders/send_receipt', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*', readonly=False)
    def order_send_receipt(self, order_uuid=None, order_id=None, email=None,
                           phone=None, **kw):
        """Send the guest their receipt.

        Core's ``action_send_receipt`` takes JPEGs of the ticket that the native POS
        renders to a canvas in the browser. Mezze's till has no such canvas, and
        screenshotting a receipt to send it is a strange way to deliver text anyway —
        an image is unsearchable, unreadable to a screen reader, and large. What is
        sent here is the SAME ticket the printer gets, as text, so the paper copy and
        the emailed copy cannot disagree.

        SMS is offered only where a gateway actually exists. Odoo Community's ``sms``
        module sends through IAP, which is a paid service a branch may not have, and
        this addon does not depend on it — so the endpoint reports plainly that SMS
        is unavailable rather than accepting a number and dropping it.
        """
        auth = self._authorize(endpoint='orders/send_receipt')
        if auth:
            return auth
        env = self._api_env()
        try:
            order = self._reward_order(env, order_id, order_uuid, None)
            if not order:
                return self._json({'ok': False, 'error': 'order_not_found'}, status=404)
            denied = self._security_gate(env, 'orders/send_receipt', target_order=order)
            if denied:
                return denied

            to_email = (email or '').strip()
            to_phone = (phone or '').strip()
            if not to_email and not to_phone:
                return self._json(
                    {'ok': False, 'error': 'no_destination',
                     'message': 'Give an email address or a phone number.'},
                    status=400)

            from ..models.hardware_render import receipt_ticket
            text = receipt_ticket(order).to_text()
            sent = {'email': False, 'sms': False}
            problems = {}

            if to_email:
                if '@' not in to_email:
                    return self._json({'ok': False, 'error': 'bad_email',
                                       'message': 'That does not look like an email '
                                                  'address.'}, status=400)
                attachment = env['ir.attachment'].sudo().create({
                    'name': 'Receipt-%s.txt' % (order.pos_reference or order.id),
                    'type': 'binary',
                    'raw': text.encode('utf-8'),
                    'res_model': 'pos.order', 'res_id': order.id,
                    'mimetype': 'text/plain',
                })
                template = env.ref('point_of_sale.email_template_pos_receipt',
                                   raise_if_not_found=False)
                try:
                    if template:
                        # Core's own template, so the subject and branding are the
                        # ones a branch already configured.
                        template.sudo().send_mail(
                            order.id, force_send=True,
                            email_values={'email_to': to_email,
                                          'attachment_ids': [(4, attachment.id)]})
                    else:
                        env['mail.mail'].sudo().create({
                            'subject': 'Your receipt %s' % (order.pos_reference or ''),
                            'email_to': to_email,
                            'body_html': '<pre>%s</pre>' % escape(text),
                            'attachment_ids': [(4, attachment.id)],
                        }).send()
                    if 'email' in order._fields:
                        order.sudo().email = to_email
                    sent['email'] = True
                except Exception as exc:  # noqa: BLE001
                    _logger.warning("Mezze receipt email failed: %s", exc)
                    problems['email'] = str(exc)

            if to_phone:
                # Present only when the branch actually installed an SMS stack.
                if 'sms.sms' not in env:
                    problems['sms'] = 'no_gateway'
                else:
                    try:
                        env['sms.sms'].sudo().create({
                            'number': to_phone,
                            'body': text,
                        }).send()
                        if 'mobile' in order._fields:
                            order.sudo().mobile = to_phone
                        sent['sms'] = True
                    except Exception as exc:  # noqa: BLE001
                        _logger.warning("Mezze receipt SMS failed: %s", exc)
                        problems['sms'] = str(exc)

            if not any(sent.values()):
                return self._json({'ok': False, 'error': 'send_failed',
                                   'problems': problems}, status=400)
            self._audit(env, 'receipt.sent', order, **self._actor(env, kw),
                        detail=json.dumps({'email': bool(sent['email']),
                                           'sms': bool(sent['sms'])}, default=str))
            return {'ok': True, 'sent': sent, 'problems': problems or None}
        except Exception as exc:  # noqa: BLE001
            _reraise_if_retryable(exc)
            _logger.exception("Mezze send_receipt failed")
            return self._json({'ok': False, 'error': 'send_receipt_failed',
                               'message': str(exc)}, status=400)

    # ------------------------------------------------------------------
    # Floor plan authoring. The ONLY write Mezze ever made to restaurant.table
    # was the QR token, so laying out a room meant leaving the product for the
    # Odoo backend — during service, on a tablet, which is when a floor actually
    # changes: two tables pushed together for a party of eight, a terrace opened
    # because the weather turned.
    # ------------------------------------------------------------------
    def _branch_floors(self, env, config):
        """The floors this branch trades on. Scope, not decoration: a table id from
        another branch must not be movable from this till."""
        return config.floor_ids

    @http.route(f'{API_PREFIX}/floor/table/save', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*', readonly=False)
    def floor_table_save(self, table_id=None, floor_id=None, **kw):
        """Create or move/resize ONE table.

        Geometry is core's own (`position_h`, `position_v`, `width`, `height`,
        `shape`, `seats`), so a floor authored here is the same floor the native POS
        and the backend see — a second, parallel layout would be a second truth.
        """
        auth = self._authorize(endpoint='floor/table/save')
        if auth:
            return auth
        env = self._api_env()
        try:
            config = self._resolve_config(env, kw.get('config_id'))
            floors = self._branch_floors(env, config)
            if not floors:
                return self._json({'ok': False, 'error': 'no_floor',
                                   'message': 'This branch has no floor to lay out.'},
                                  status=400)
            Table = env['restaurant.table'].sudo()
            vals = {}
            for field, caster in (('table_number', int), ('seats', int),
                                  ('position_h', float), ('position_v', float),
                                  ('width', float), ('height', float)):
                if kw.get(field) is not None:
                    try:
                        vals[field] = caster(kw[field])
                    except (TypeError, ValueError):
                        return self._json({'ok': False, 'error': 'bad_geometry',
                                           'message': 'That is not a number: %s' % field},
                                          status=400)
            if kw.get('shape') in ('square', 'round'):
                vals['shape'] = kw['shape']
            if kw.get('color'):
                vals['color'] = str(kw['color'])[:64]
            # A table cannot be smaller than nothing, and a zero-sized table is one
            # nobody can tap.
            for dim in ('width', 'height'):
                if dim in vals and vals[dim] <= 0:
                    return self._json({'ok': False, 'error': 'bad_geometry',
                                       'message': 'A table needs a positive %s.' % dim},
                                      status=400)
            if 'seats' in vals and vals['seats'] < 0:
                return self._json({'ok': False, 'error': 'bad_geometry',
                                   'message': 'A table cannot have negative seats.'},
                                  status=400)

            if table_id:
                table = Table.browse(int(table_id)).exists()
                if not table or table.floor_id not in floors:
                    # Same answer for "does not exist" and "belongs to another
                    # branch": a different answer would tell a caller which table
                    # ids are real.
                    return self._json({'ok': False, 'error': 'unknown_table'}, status=404)
                if floor_id:
                    target = floors.filtered(lambda f: f.id == int(floor_id))[:1]
                    if not target:
                        return self._json({'ok': False, 'error': 'unknown_floor'},
                                          status=404)
                    vals['floor_id'] = target.id
                if vals:
                    table.write(vals)
                action = 'moved'
            else:
                target = (floors.filtered(lambda f: f.id == int(floor_id))[:1]
                          if floor_id else floors[:1])
                if not target:
                    return self._json({'ok': False, 'error': 'unknown_floor'}, status=404)
                vals['floor_id'] = target.id
                vals.setdefault('table_number', self._next_table_number(env, target))
                table = Table.create(vals)
                action = 'created'
            self._audit(env, 'floor.table_%s' % action, **self._actor(env, kw),
                        config_id=config.id,
                        detail=json.dumps({'table_id': table.id,
                                           'table_number': table.table_number,
                                           'floor': table.floor_id.name}, default=str))
            return {'ok': True, 'action': action, 'table': self._table_payload(table)}
        except Exception as exc:  # noqa: BLE001
            _reraise_if_retryable(exc)
            _logger.exception("Mezze floor_table_save failed")
            return self._json({'ok': False, 'error': 'floor_save_failed',
                               'message': str(exc)}, status=400)

    def _next_table_number(self, env, floor):
        """The next free number on this floor. Guests read table numbers aloud, so a
        duplicate is a real operational problem, not a cosmetic one."""
        used = env['restaurant.table'].sudo().search(
            [('floor_id', '=', floor.id)]).mapped('table_number')
        return (max(used) + 1) if used else 1

    def _table_payload(self, table):
        return {'id': table.id, 'table_number': table.table_number,
                'floor_id': table.floor_id.id, 'floor': table.floor_id.name,
                'shape': table.shape, 'seats': table.seats,
                'position_h': table.position_h, 'position_v': table.position_v,
                'width': table.width, 'height': table.height,
                'color': table.color or '', 'active': table.active}

    @http.route(f'{API_PREFIX}/floor/table/remove', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*', readonly=False)
    def floor_table_remove(self, table_id=None, **kw):
        """Take a table off the floor.

        DEACTIVATED, never deleted: past orders point at it, and a table that
        vanishes takes their history with it. Core's own field is `active` for
        exactly this reason.

        Refused while an order is open on it. A table can be removed from a plan and
        still have a bill sitting on it, and removing it then is how a table's money
        becomes unreachable from the floor it was taken on.
        """
        auth = self._authorize(endpoint='floor/table/remove')
        if auth:
            return auth
        env = self._api_env()
        try:
            config = self._resolve_config(env, kw.get('config_id'))
            floors = self._branch_floors(env, config)
            table = env['restaurant.table'].sudo().browse(int(table_id or 0)).exists()
            if not table or table.floor_id not in floors:
                return self._json({'ok': False, 'error': 'unknown_table'}, status=404)
            open_orders = env['pos.order'].sudo().search_count([
                ('table_id', '=', table.id), ('state', '=', 'draft')])
            if open_orders:
                return self._json(
                    {'ok': False, 'error': 'table_in_use',
                     'message': 'That table still has an open order. Settle or move '
                                'it before taking the table off the floor.',
                     'open_orders': open_orders}, status=409)
            table.write({'active': False})
            self._audit(env, 'floor.table_removed', severity='warning',
                        **self._actor(env, kw), config_id=config.id,
                        detail=json.dumps({'table_id': table.id,
                                           'table_number': table.table_number},
                                          default=str))
            return {'ok': True, 'table_id': table.id}
        except Exception as exc:  # noqa: BLE001
            _reraise_if_retryable(exc)
            _logger.exception("Mezze floor_table_remove failed")
            return self._json({'ok': False, 'error': 'floor_remove_failed',
                               'message': str(exc)}, status=400)

    @http.route(f'{API_PREFIX}/codes/resolve', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*', readonly=False)
    def codes_resolve(self, code=None, order_uuid=None, order_id=None,
                      session_id=None, **kw):
        """One box the cashier types ANY code into — Odoo's "Enter Code".

        A guest hands over a slip. It might be a gift card, a coupon, or a promo code
        the branch published; nothing on it says which, and the cashier should not
        have to know. Without this the till would have to guess — call the gift-card
        lookup, and on a 404 try the promo engine — which means the failure mode for a
        genuinely bad code is two round trips and an error from whichever guess ran
        last, phrased in that engine's vocabulary.

        The server knows what its own codes are, so it classifies the code and says
        so. A gift card is REPORTED, not spent: it is a tender, and it is spent at
        payment against the balance that exists then, not at the moment it is typed.
        A promo is applied to the order immediately, because that is what changes the
        price the guest is about to be quoted.
        """
        auth = self._authorize(endpoint='codes/resolve')
        if auth:
            return auth
        env = self._api_env()
        try:
            typed = (code or '').strip()
            if not typed:
                return self._json({'ok': False, 'error': 'empty_code',
                                   'message': 'Type a code first.'}, status=400)
            order = self._reward_order(env, order_id, order_uuid, session_id)
            if not order:
                return self._json({'ok': False, 'error': 'order_not_found'}, status=404)
            denied = self._security_gate(env, 'codes/resolve', target_order=order)
            if denied:
                return denied

            # 1. A gift card. Reported with its balance; spent at payment.
            card = self._giftcard_by_code(env, typed)
            if card:
                expired = bool(card.expiration_date
                               and card.expiration_date < fields.Date.today())
                return {'ok': True, 'kind': 'gift_card', 'code': card.code,
                        'balance': round(card.points, 2),
                        'expired': expired,
                        'usable': bool(not expired and card.points > 0),
                        'expiration_date': (str(card.expiration_date)
                                            if card.expiration_date else None)}

            # 2. A coupon or a promo code, evaluated against THIS order's lines by the
            #    same engine the storefront uses.
            lines = [{'product_id': l.product_id.id, 'qty': l.qty}
                     for l in order.lines if not l.is_reward_line]
            if lines:
                incl, specs, code_result = self._promo_for_cart(
                    env, order.config_id, order.partner_id, lines, code=typed)
                if code_result and code_result.get('ok'):
                    # ONLY the code's own promotion. `_promo_for_cart` returns the
                    # matching auto-promotions merged in with it, and grafting those
                    # here would silently discount an order for reasons the cashier
                    # did not ask for and cannot explain to the guest.
                    own = [sp for sp in (specs or [])
                           if sp.get('name') == code_result.get('name')]
                    discount = self._promo_apply_to_order(
                        env, order.config_id, order, own)
                    self._audit(env, 'promo.code_applied', order, **self._actor(env, kw),
                                detail=json.dumps({'code': typed,
                                                   'name': code_result.get('name'),
                                                   'discount': discount}, default=str))
                    order.invalidate_recordset()
                    return {'ok': True, 'kind': 'promo', 'code': typed,
                            'name': code_result.get('name') or typed,
                            'discount': round(abs(discount or 0.0), 2),
                            'amount_total': round(order.amount_total, 2)}
                # "invalid" means the promo engine does not know this code either,
                # which is not a rejection — it is the same "no such code" the gift
                # card lookup already returned, and reporting the last engine's
                # wording would tell the cashier a coupon was refused when no coupon
                # was ever involved. Every OTHER reason means the code IS real and
                # cannot be used, and that reason is worth repeating verbatim.
                if (code_result and code_result.get('message')
                        and code_result.get('error') != 'invalid'):
                    return self._json({'ok': False, 'error': 'code_rejected',
                                       'kind': 'promo',
                                       'message': code_result['message']}, status=400)

            return self._json({'ok': False, 'error': 'unknown_code',
                               'message': 'That code is not a gift card, '
                                          'a coupon or a promotion.'}, status=404)
        except Exception as exc:  # noqa: BLE001
            _reraise_if_retryable(exc)
            _logger.exception("Mezze codes_resolve failed")
            return self._json({'ok': False, 'error': 'codes_resolve_failed',
                               'message': str(exc)}, status=400)

    @http.route(f'{API_PREFIX}/giftcard/issue', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*', readonly=False)
    def giftcard_issue(self, amount=None, partner_id=None, code=None,
                       expiration_date=None, **kw):
        """Mint a gift card with a starting balance. The cash for it is collected
        by the sale that sells the Gift Card product; this call creates the card
        and returns its printable code. Optionally attach to a customer."""
        auth = self._authorize()
        if auth:
            return auth
        env = self._api_env()
        try:
            amt = round(float(amount or 0), 2)
            if amt <= 0:
                raise ValueError("Gift card amount must be positive")
            prog = self._giftcard_program(env)
            vals = {'program_id': prog.id, 'points': amt}
            if partner_id:
                vals['partner_id'] = int(partner_id)
            if code:
                vals['code'] = str(code).strip()
            if expiration_date:
                vals['expiration_date'] = expiration_date
            card = env['loyalty.card'].sudo().create(vals)
            self._audit(env, 'giftcard.issue', **self._actor(env, kw),
                        detail=json.dumps({'code': card.code, 'amount': amt,
                                           'partner_id': partner_id}, default=str))
            return {'ok': True, 'code': card.code, 'balance': card.points,
                    'partner_id': card.partner_id.id or None,
                    'expiration_date': str(card.expiration_date) if card.expiration_date else None}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze giftcard issue failed")
            return self._json({'ok': False, 'error': 'giftcard_issue_failed',
                               'message': str(exc)}, status=400)

    @http.route(f'{API_PREFIX}/giftcard/balance', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def giftcard_balance(self, code=None, **kw):
        """Look up a gift card's live balance by code."""
        auth = self._authorize()
        if auth:
            return auth
        env = self._api_env()
        try:
            card = self._giftcard_by_code(env, code)
            if not card:
                return self._json({'ok': False, 'error': 'not_found',
                                   'message': 'No gift card with that code'}, status=404)
            expired = bool(card.expiration_date and card.expiration_date < fields.Date.today())
            return {'ok': True, 'code': card.code, 'balance': card.points,
                    'partner': card.partner_id.name or None, 'expired': expired,
                    'expiration_date': str(card.expiration_date) if card.expiration_date else None}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze giftcard balance failed")
            return self._json({'ok': False, 'error': 'giftcard_balance_failed',
                               'message': str(exc)}, status=400)

    # ------------------------------------------------------------------
    # Promotions & coupons — native loyalty programs (promotion / promo_code /
    # coupons), evaluated server-side against a cart. A discount reward becomes a
    # balanced discount line (same mechanism as loyalty redemption). Managers
    # define promos in Odoo's Loyalty UI; this engine surfaces + applies them.
    # ------------------------------------------------------------------
    PROMO_TYPES = ('promotion', 'promo_code', 'coupons', 'buy_x_get_y')

    def _promo_active_programs(self, env):
        """Active promotion/coupon programs currently within their date window."""
        today = fields.Date.today()
        progs = env['loyalty.program'].sudo().search(
            [('active', '=', True), ('program_type', 'in', self.PROMO_TYPES)])
        return progs.filtered(
            lambda p: (not p.date_from or p.date_from <= today)
            and (not p.date_to or p.date_to >= today))

    def _promo_cart_stats(self, lines):
        """(total_qty, {product_id: qty}) from the raw cart lines."""
        qty_by_pid, total = {}, 0.0
        for l in (lines or []):
            if not l.get('product_id'):
                continue
            pid = int(l['product_id'])
            q = float(l.get('qty', 1) or 0)
            qty_by_pid[pid] = qty_by_pid.get(pid, 0.0) + q
            total += q
        return total, qty_by_pid

    def _promo_rule_ok(self, rule, incl, total_qty, qty_by_pid):
        """A loyalty.rule passes for this cart: min amount, min qty, and — if the
        rule is scoped to products — the presence/qty of those products."""
        if rule.minimum_amount and incl < rule.minimum_amount:
            return False
        prod_ids = rule.product_ids.ids
        if prod_ids:
            mq = sum(qty_by_pid.get(p, 0.0) for p in prod_ids)
            if mq <= 0:
                return False
            if rule.minimum_qty and mq < rule.minimum_qty:
                return False
        elif rule.minimum_qty and total_qty < rule.minimum_qty:
            return False
        return True

    def _promo_discount_amount(self, reward, incl):
        """Discount value for a 'discount' reward against a tax-inclusive base.
        Percentage and fixed ($/order) are supported; 'specific'/'cheapest'
        applicability is approximated at order level. Free-product / buy-x-get-y
        rewards are not applied here (they need a product line, not a discount)."""
        if reward.reward_type != 'discount':
            return 0.0
        if reward.discount_mode == 'percent':
            amt = incl * (reward.discount / 100.0)
        elif reward.discount_mode == 'per_order':
            amt = reward.discount
        else:
            return 0.0
        if reward.discount_max_amount:
            amt = min(amt, reward.discount_max_amount)
        return round(min(amt, incl), 2)   # a promo can never exceed the order

    def _promo_eval(self, env, program, incl, total_qty, qty_by_pid):
        """Return a discount spec for ``program`` if it applies to this cart, else
        None. A program applies when any of its rules pass (or it has no rules)
        and it carries a usable discount reward."""
        rules = program.rule_ids
        if rules and not any(self._promo_rule_ok(r, incl, total_qty, qty_by_pid) for r in rules):
            return None
        reward = program.reward_ids.filtered(lambda r: r.reward_type == 'discount')[:1]
        if reward and reward.discount_line_product_id:
            amt = self._promo_discount_amount(reward, incl)
            if amt <= 0:
                return None
            return {'program_id': program.id, 'name': program.name, 'amount': amt,
                    'kind': 'discount',
                    'discount_product_id': reward.discount_line_product_id.id,
                    'reward': reward}

        # A FREE PRODUCT reward — "buy two, get one".
        #
        # `buy_x_get_y` was already in PROMO_TYPES, so such a programme was being
        # evaluated on every cart and then silently thrown away here, because this
        # only ever accepted a discount reward. That is worse than not supporting it:
        # the branch publishes a promotion, it matches, and nothing happens, with
        # nothing said. The giveaway is expressed as the reward PRODUCT at 100% off
        # rather than as a negative discount line, because a guest reading the
        # receipt should see the free item named on it — "Buy 2 get 1: -60.00" tells
        # them a number, not what they were given.
        product_reward = program.reward_ids.filtered(
            lambda r: r.reward_type == 'product')[:1]
        if not product_reward:
            return None
        free = product_reward.reward_product_id or product_reward.reward_product_ids[:1]
        if not free:
            return None
        qty = max(1, int(product_reward.reward_product_qty or 1))
        value = round((free.lst_price or 0.0) * qty, 2)
        if value <= 0:
            return None
        return {'program_id': program.id, 'name': program.name, 'amount': value,
                'kind': 'product', 'free_product_id': free.id, 'free_qty': qty,
                'reward': product_reward}

    def _promo_resolve_code(self, env, code):
        """Resolve a typed code to (program, coupon_card|None). A promo_code lives
        on a rule; a single-use coupon is a loyalty.card carrying the code."""
        code = (code or '').strip()
        if not code:
            return (env['loyalty.program'], None)
        rule = env['loyalty.rule'].sudo().search(
            [('code', '=', code), ('mode', '=', 'with_code')], limit=1)
        if rule and rule.program_id.program_type in self.PROMO_TYPES:
            return (rule.program_id, None)
        card = env['loyalty.card'].sudo().search([('code', '=', code)], limit=1)
        if card and card.program_id.program_type in self.PROMO_TYPES:
            return (card.program_id, card)
        return (env['loyalty.program'], None)

    def _promo_for_cart(self, env, config, partner, lines, code=None, incl=None):
        """Evaluate every applicable promo for a cart. Returns
        (incl, applied_specs, code_result). ``applied_specs`` = auto-promotions
        that match + a valid code's promo; ``code_result`` reports the code.

        ``incl`` overrides the cart's value. The storefront sends product ids and
        quantities and nothing else, so the amount MUST be derived from the pricelist
        there. An existing order is different: its lines carry the prices actually
        charged, which a manual override or a line discount may have moved. Re-pricing
        those from the product would test a spend threshold — and compute a percentage
        — against money nobody is paying.
        """
        if incl is None:
            _ol, _base, incl = self._build_lines(env, config, partner, lines)
        total_qty, qty_by_pid = self._promo_cart_stats(lines)
        applied, seen = [], set()
        for p in self._promo_active_programs(env):
            if p.trigger == 'auto':
                spec = self._promo_eval(env, p, incl, total_qty, qty_by_pid)
                if spec:
                    spec['auto'] = True
                    applied.append(spec)
                    seen.add(p.id)
        code_result = None
        if code:
            prog, card = self._promo_resolve_code(env, code)
            if not prog:
                code_result = {'ok': False, 'error': 'invalid', 'message': 'Unknown code'}
            elif card and (card.points or 0) <= 0:
                code_result = {'ok': False, 'error': 'used', 'message': 'Coupon already used'}
            elif card and card.expiration_date and card.expiration_date < fields.Date.today():
                code_result = {'ok': False, 'error': 'expired', 'message': 'Coupon expired'}
            else:
                spec = self._promo_eval(env, prog, incl, total_qty, qty_by_pid)
                if not spec:
                    code_result = {'ok': False, 'error': 'not_applicable',
                                   'message': 'This code does not apply to your cart'}
                elif prog.id in seen:
                    code_result = {'ok': False, 'error': 'already',
                                   'message': 'This promotion is already applied'}
                else:
                    spec['auto'] = False
                    spec['code'] = code
                    spec['card_id'] = card.id if card else None
                    applied.append(spec)
                    code_result = {'ok': True, 'name': spec['name'], 'amount': spec['amount']}
        return incl, applied, code_result

    def _promo_line_vals(self, config, spec):
        """The order line one promo spec becomes.

        A discount reward becomes a negative, tax-consistent discount line. A FREE
        PRODUCT becomes the product itself at 100% off — so the guest sees what they
        were given, and so the kitchen sees an item to make rather than a number.
        """
        if spec.get('kind') == 'product':
            free = config.env['product.product'].sudo().browse(spec['free_product_id'])
            qty = spec.get('free_qty') or 1
            vals = {
                'product_id': free.id, 'qty': qty,
                'price_unit': free.lst_price or 0.0,
                # 100% off, not price_unit 0: the receipt then shows what the item
                # normally costs next to what the guest paid for it, which is the
                # difference between a gift and a mystery.
                'discount': 100.0,
                'tax_ids': [(6, 0, free.taxes_id.ids)],
                'price_subtotal': 0.0, 'price_subtotal_incl': 0.0,
                'pack_lot_ids': [],
            }
            fields_ = config.env['pos.order.line']._fields
            if 'is_reward_line' in fields_:
                vals['is_reward_line'] = True
                if 'reward_id' in fields_:
                    vals['reward_id'] = spec['reward'].id
            return (0, 0, vals)
        reward = spec['reward']
        dp = reward.discount_line_product_id
        amt = spec['amount']
        dtax = dp.taxes_id
        tv = dtax.compute_all(-amt, config.currency_id, 1, product=dp) if dtax else None
        vals = {
            'product_id': dp.id, 'qty': 1, 'price_unit': -amt, 'discount': 0.0,
            'tax_ids': [(6, 0, dtax.ids)],
            'price_subtotal': tv['total_excluded'] if tv else -amt,
            'price_subtotal_incl': tv['total_included'] if tv else -amt,
            'pack_lot_ids': []}
        # A promotion's line IS a reward line, and saying so makes three existing
        # rules apply to it that were silently skipping it:
        #   * the KDS drops reward lines — a discount is not something anybody cooks,
        #     and this line carries a product id like any other;
        #   * /orders/discount refuses to mark down a reward line, so a promo could
        #     not be discounted a second time;
        #   * anything re-reading a cart (the code entry below) stops counting the
        #     negative discount line as an item the guest is buying.
        # Loyalty reward lines were already flagged; promotions were not, purely
        # because they were written by a different helper.
        fields_ = config.env['pos.order.line']._fields
        if 'is_reward_line' in fields_:
            vals['is_reward_line'] = True
            if reward and 'reward_id' in fields_:
                vals['reward_id'] = reward.id
        return (0, 0, vals)

    def _promo_consume(self, env, order, specs):
        """Mark any single-use coupons consumed and audit each applied promo."""
        for spec in specs:
            if spec.get('card_id'):
                card = env['loyalty.card'].sudo().browse(spec['card_id'])
                card.write({'points': max(0.0, (card.points or 0) - 1)})   # single-use
            self._audit(env, 'promo.apply', order,
                        detail=json.dumps({'program': spec['name'], 'amount': spec['amount'],
                                           'code': spec.get('code')}, default=str))

    def _promo_apply_to_order(self, env, config, order, specs):
        """Graft each promo's discount line onto an existing (draft) order, mark
        coupons consumed, and recompute the totals. Returns the total discount."""
        if not specs:
            return 0.0
        order.write({'lines': [self._promo_line_vals(config, s) for s in specs]})
        self._promo_consume(env, order, specs)
        tot_base = sum(order.lines.mapped('price_subtotal'))
        tot_incl = sum(order.lines.mapped('price_subtotal_incl'))
        order.write({'amount_tax': tot_incl - tot_base, 'amount_total': tot_incl})
        return round(sum(s['amount'] for s in specs), 2)

    def _promo_config(self, env, store=None, config_id=None):
        """Resolve a config from a store token (public storefront) or, failing
        that, the authenticated staff config."""
        if store:
            return self._store_config(env, store)
        return self._resolve_config(env, config_id)

    @http.route(f'{API_PREFIX}/promo/apply', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*', readonly=False)
    def promo_apply(self, store=None, config_id=None, lines=None, code=None, **kw):
        """Preview the promos for a cart: auto-promotions that match + a typed
        code. Public via a store token (storefront) or staff-token'd (POS).
        Read-only — nothing is consumed until the order is actually placed."""
        env = self._api_env()
        try:
            if not store:
                auth = self._authorize()
                if auth:
                    return auth
            config = self._promo_config(env, store, config_id)
            if not lines:
                return self._json({'ok': False, 'error': 'no_lines'}, status=400)
            incl, specs, code_result = self._promo_for_cart(
                env, config, env['res.partner'], lines, code)
            return {'ok': True, 'subtotal': round(incl, 2),
                    'total_discount': round(sum(s['amount'] for s in specs), 2),
                    'promos': [{'program_id': s['program_id'], 'name': s['name'],
                                'amount': s['amount'], 'auto': s.get('auto', False)} for s in specs],
                    'code': code_result}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze promo_apply failed")
            return self._json({'ok': False, 'error': 'promo_apply_failed', 'message': str(exc)}, status=400)

    @http.route(f'{API_PREFIX}/promo/list', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def promo_list(self, store=None, config_id=None, **kw):
        """Active offers for a branch — auto-promotions (always-on) and the
        existence of code-based promos (label only, never the codes)."""
        env = self._api_env()
        try:
            if not store:
                auth = self._authorize()
                if auth:
                    return auth
            self._promo_config(env, store, config_id)
            offers = []
            for p in self._promo_active_programs(env):
                reward = p.reward_ids.filtered(lambda r: r.reward_type == 'discount')[:1]
                if not reward:
                    continue
                label = ('%g%% off' % reward.discount) if reward.discount_mode == 'percent' \
                    else ('%g off' % reward.discount)
                rule = p.rule_ids[:1]
                offers.append({'name': p.name, 'label': label,
                               'auto': p.trigger == 'auto',
                               'min_amount': rule.minimum_amount if rule else 0.0})
            return {'ok': True, 'offers': offers}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze promo_list failed")
            return self._json({'ok': False, 'error': 'promo_list_failed', 'message': str(exc)}, status=400)

    # ------------------------------------------------------------------
    # Waste / spoilage — native stock.scrap + reason tags, with cost impact
    # ------------------------------------------------------------------
    # Waste is a real ``stock.scrap`` (so on-hand stock drops and the loss books
    # through inventory), tagged with a native ``stock.scrap.reason.tag``. The
    # cost impact is the ingredient/dish cost (BoM-exploded when a recipe exists),
    # so a manager sees money lost, not just quantities.
    WASTE_REASONS = ['Spoilage', 'Expiry', 'Breakage', 'Over-prep', 'Dropped', 'Return']

    def _waste_reason_tag(self, env, name):
        Tag = env['stock.scrap.reason.tag'].sudo()
        name = (name or 'Spoilage').strip().title()
        tag = Tag.search([('name', '=', name)], limit=1)
        return tag or Tag.create({'name': name})

    def _stock_location(self, env, company):
        wh = env['stock.warehouse'].sudo().search(
            [('company_id', '=', company.id)], limit=1) or \
            env['stock.warehouse'].sudo().search([], limit=1)
        return wh.lot_stock_id

    @http.route(f'{API_PREFIX}/waste/log', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*', readonly=False)
    def waste_log(self, config_id=None, product_id=None, qty=None, reason=None, **kw):
        """Record waste against a real stock.scrap (executes the move, tagged with
        the reason). Returns the scrap reference + the money impact. Managers +
        supervisors only-ish: audited so shrinkage is attributable."""
        auth = self._authorize()
        if auth:
            return auth
        env = self._api_env()
        # Bind the REQUEST env to the api user too: a scrap posts stock-valuation
        # rows that get flushed at request-end through the request's default env —
        # which under auth='none' has no user and fails the access check. (Other
        # endpoints don't hit this because they don't leave valuation rows dirty.)
        request.update_env(user=env.uid)
        try:
            config = (env['pos.config'].browse(int(config_id)) if config_id
                      else env['pos.config'].search([], limit=1))
            company = config.company_id or env.company
            product = env['product.product'].browse(int(product_id))
            if not product.exists():
                raise ValueError("Unknown product_id %s" % product_id)
            q = float(qty or 0)
            if q <= 0:
                raise ValueError("Waste quantity must be positive")
            tag = self._waste_reason_tag(env, reason)
            loc = self._stock_location(env, company)
            # Use the api_user env (has POS/stock rights) — NOT sudo: the scrap's
            # stock-move flush does access checks that trip on SUPERUSER.
            wenv = env(context=dict(env.context, allowed_company_ids=[company.id]))
            scrap = wenv['stock.scrap'].create({
                'product_id': product.id, 'product_uom_id': product.uom_id.id,
                'scrap_qty': q, 'location_id': loc.id,
                'scrap_reason_tag_ids': [(6, 0, tag.ids)],
                'company_id': company.id,
                'origin': 'Mezze POS waste',
            })
            # execute directly so it records even when tracked stock is short
            # (waste happened regardless); non-storable products just log. Run in a
            # savepoint so a valuation/move hiccup degrades to a draft record
            # (waste still tracked) rather than 500-ing the request.
            try:
                with env.cr.savepoint():
                    scrap.do_scrap()
                    env.cr.flush()
            except Exception:  # noqa: BLE001 - keep the waste record even if the move can't post
                _logger.exception("Waste scrap move failed for %s; kept as draft", product.display_name)
            unit_cost = self._recipe_cost(product)
            cost = round(unit_cost * q, 2)
            self._audit(env, 'waste.log', **self._actor(env, kw),
                        detail=json.dumps({'product': product.display_name, 'qty': q,
                                           'reason': tag.name, 'cost': cost,
                                           'scrap': scrap.name, 'config_id': company.id}, default=str))
            return {'ok': True, 'scrap_id': scrap.id, 'reference': scrap.name,
                    'state': scrap.state, 'product': product.display_name, 'qty': q,
                    'reason': tag.name, 'unit_cost': round(unit_cost, 2), 'cost': cost}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze waste log failed")
            return self._json({'ok': False, 'error': 'waste_failed',
                               'message': str(exc)}, status=400)

    @http.route(f'{API_PREFIX}/waste/products', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def waste_products(self, q=None, limit=12, **kw):
        """Products a manager can waste: storable ingredients (the BoM components
        that are the real waste) UNION menu items (a dropped dish). Returns name +
        uom + live on-hand so the picker shows what's actually stockable."""
        auth = self._authorize()
        if auth:
            return auth
        env = self._api_env()
        try:
            dom = ['|', ('is_storable', '=', True), ('available_in_pos', '=', True)]
            if q:
                dom = ['&'] + dom + ['|', ('name', 'ilike', q), ('default_code', 'ilike', q)]
            prods = env['product.product'].sudo().search(dom, limit=int(limit or 12))
            return {'ok': True, 'products': [{
                'id': p.id, 'name': p.display_name, 'uom': p.uom_id.name,
                'storable': p.is_storable, 'on_hand': p.qty_available if p.is_storable else None,
            } for p in prods]}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze waste products failed")
            return self._json({'ok': False, 'error': 'waste_products_failed',
                               'message': str(exc)}, status=400)

    @http.route(f'{API_PREFIX}/waste/list', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def waste_list(self, config_id=None, limit=30, **kw):
        """Recent waste with per-line cost + a day/total roll-up for the ops view."""
        auth = self._authorize()
        if auth:
            return auth
        env = self._api_env()
        try:
            company = (env['pos.config'].browse(int(config_id)).company_id if config_id
                       else env.company)
            dom = [('origin', '=', 'Mezze POS waste')]
            if company:
                dom.append(('company_id', '=', company.id))
            scraps = env['stock.scrap'].sudo().search(dom, order='create_date desc',
                                                      limit=int(limit or 30))
            items, total = [], 0.0
            today = fields.Date.today()
            today_cost = 0.0
            for s in scraps:
                unit = self._recipe_cost(s.product_id)
                cost = round(unit * s.scrap_qty, 2)
                total += cost
                created = s.create_date.date() if s.create_date else None
                if created == today:
                    today_cost += cost
                items.append({
                    'id': s.id, 'reference': s.name or '(draft)',
                    'product': s.product_id.display_name, 'qty': s.scrap_qty,
                    'uom': s.product_uom_id.name, 'state': s.state,
                    'reason': ', '.join(s.scrap_reason_tag_ids.mapped('name')) or '—',
                    'cost': cost,
                    'date': fields.Datetime.to_string(s.create_date) if s.create_date else None,
                })
            return {'ok': True, 'items': items,
                    'total_cost': round(total, 2), 'today_cost': round(today_cost, 2),
                    'reasons': self.WASTE_REASONS}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze waste list failed")
            return self._json({'ok': False, 'error': 'waste_list_failed',
                               'message': str(exc)}, status=400)

    # ------------------------------------------------------------------
    # Reservations — mezze.reservation over real restaurant.table
    # ------------------------------------------------------------------
    # A booked reservation "holds" its table from ``lead`` minutes before the
    # start until the end of its window; the floor shows it reserved in that span.
    RES_LEAD_MIN = 90

    def _res_window(self, r):
        start = r.start
        end = start + datetime.timedelta(hours=r.duration or 1.5)
        return start, end

    def _res_conflict(self, env, table_id, start_dt, duration, exclude_id=None):
        """True if a live (booked/seated) reservation on the table overlaps the
        proposed [start, start+duration] window."""
        end_dt = start_dt + datetime.timedelta(hours=duration or 1.5)
        dom = [('table_id', '=', int(table_id)), ('state', 'in', ('booked', 'seated'))]
        if exclude_id:
            dom.append(('id', '!=', int(exclude_id)))
        for r in env['mezze.reservation'].search(dom):
            rs, re = self._res_window(r)
            if rs < end_dt and start_dt < re:      # windows intersect
                return r
        return False

    def _res_payload(self, r):
        start = r.start
        return {
            'id': r.id, 'state': r.state,
            'who': r._who(), 'phone': r.phone or (r.partner_id.phone or ''),
            'partner_id': r.partner_id.id or None,
            'table_id': r.table_id.id,
            'table': 'T%s' % (r.table_id.table_number if 'table_number' in r.table_id._fields else r.table_id.id),
            'start': fields.Datetime.to_string(start) if start else None,
            'time': fields.Datetime.to_string(start)[11:16] if start else '',
            'duration': r.duration, 'guests': r.guests, 'note': r.note or '',
            'order_id': r.pos_order_id.id or None,
            'is_vip': r.is_vip, 'occasion': r.occasion or '',
            'arrival_note': r.arrival_note or '',
            'arrived_at': fields.Datetime.to_string(r.arrived_at) if r.arrived_at else None,
            # a booking whose slot has passed but who hasn't arrived/seated yet
            'late': bool(start and start < fields.Datetime.now()
                         and r.state in ('booked', 'confirmed')),
        }

    @http.route(f'{API_PREFIX}/reservations/list', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def reservations_list(self, config_id=None, date=None, scope='today', q=None, **kw):
        """Reservations for a day (default today) or all upcoming. Optional ``q``
        searches by guest name / phone / reservation reference (id or #id)."""
        auth = self._authorize()
        if auth:
            return auth
        try:
            env = self._api_env()
            now = fields.Datetime.now()
            # CP10 — scope-first: the query BEGINS from the principal's authoritative
            # branch (a client config_id may only narrow, never widen it). Fail-closed
            # if the caller has no resolvable branch (and is not the bypass admin).
            scope, ok = self._mezze_scope_domain(env)
            if not ok:
                return {'ok': True, 'reservations': []}
            dom = list(scope)
            if config_id and not scope:            # admin may still narrow by a branch
                dom.append(('config_id', '=', int(config_id)))
            if q and str(q).strip():
                term = str(q).strip()
                sub = ['|', '|', ('customer_name', 'ilike', term), ('phone', 'ilike', term),
                       ('partner_id.name', 'ilike', term)]
                ref = term.lstrip('#')
                if ref.isdigit():
                    sub = ['|'] + sub + [('id', '=', int(ref))]
                dom += sub                              # search ignores the day window
            elif scope == 'upcoming':
                dom.append(('start', '>=', fields.Datetime.to_string(now - datetime.timedelta(hours=2))))
            else:
                day = fields.Datetime.to_datetime(date + ' 00:00:00') if date else \
                    now.replace(hour=0, minute=0, second=0, microsecond=0)
                dom += [('start', '>=', fields.Datetime.to_string(day)),
                        ('start', '<', fields.Datetime.to_string(day + datetime.timedelta(days=1)))]
            res = env['mezze.reservation'].search(dom, limit=200)
            return {'ok': True, 'reservations': [self._res_payload(r) for r in res]}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze reservations_list failed")
            return self._json({'ok': False, 'error': 'res_list_failed', 'message': str(exc)}, status=400)

    @http.route(f'{API_PREFIX}/reservations/availability', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def reservations_availability(self, config_id=None, start=None, duration=1.5, guests=None, **kw):
        """Tables free at ``start`` (no overlapping reservation), seats permitting."""
        auth = self._authorize()
        if auth:
            return auth
        try:
            env = self._api_env()
            start_dt = fields.Datetime.to_datetime(start)
            # CP10 — availability is scoped to the caller's own branch tables only
            # (never enumerate another branch's floor).
            s = self._mezze_principal_scope(env)
            if not s['ok']:
                return {'ok': True, 'tables': []}
            tdom = [('active', '=', True)]
            if not s['is_admin']:
                if not s['branch']:
                    return {'ok': True, 'tables': []}
                tdom.append(('floor_id.pos_config_ids', 'in', int(s['branch'])))
            elif config_id:
                tdom.append(('floor_id.pos_config_ids', 'in', int(config_id)))
            tables = env['restaurant.table'].search(tdom)
            free = []
            for t in tables:
                if guests and t.seats and t.seats < int(guests):
                    continue
                if self._res_conflict(env, t.id, start_dt, float(duration)):
                    continue
                free.append({'id': t.id,
                             'table': 'T%s' % (t.table_number if 'table_number' in t._fields else t.id),
                             'seats': t.seats, 'floor': t.floor_id.name})
            return {'ok': True, 'tables': free}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze reservations_availability failed")
            return self._json({'ok': False, 'error': 'res_avail_failed', 'message': str(exc)}, status=400)

    @http.route(f'{API_PREFIX}/reservations/create', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*', readonly=False)
    def reservations_create(self, table_id=None, start=None, guests=2, duration=1.5,
                            name=None, phone=None, partner_id=None, note=None, config_id=None, **kw):
        """Book a table, rejecting a clash with an existing booking on it."""
        auth = self._authorize()
        if auth:
            return auth
        try:
            env = self._api_env()
            if not table_id or not start:
                return self._json({'ok': False, 'error': 'missing_table_or_time'}, status=400)
            table = env['restaurant.table'].browse(int(table_id))
            if not table.exists():
                return self._json({'ok': False, 'error': 'table_not_found'}, status=404)
            # CP10 — the chosen table must belong to the caller's branch (no booking a
            # cross-branch table); the branch itself is SERVER-derived, never trusted
            # from the client config_id.
            s = self._mezze_principal_scope(env)
            if not s['ok']:
                return self._json({'ok': False, 'error': authz.AUTHENTICATION_REQUIRED}, status=401)
            if not self._mezze_table_in_branch(env, table, None if s['is_admin'] else s['branch']):
                return self._json({'ok': False, 'error': 'table_not_found'}, status=404)
            start_dt = fields.Datetime.to_datetime(start)
            clash = self._res_conflict(env, table.id, start_dt, float(duration))
            if clash:
                return self._json({'ok': False, 'error': 'table_unavailable',
                                   'message': 'Table already booked for %s at %s'
                                   % (clash._who(), fields.Datetime.to_string(clash.start)[11:16])}, status=409)
            # branch is authoritative from the principal (admin may pass one, else the
            # table's own floor config).
            cfg = (s['branch'] if not s['is_admin'] else int(config_id)) if (
                s['branch'] or config_id) else (
                table.floor_id.pos_config_ids[:1].id if 'pos_config_ids' in table.floor_id._fields
                and table.floor_id.pos_config_ids else False)
            partner = env['res.partner'].browse(int(partner_id)) if partner_id else False
            res = env['mezze.reservation'].create({
                'table_id': table.id, 'config_id': cfg, 'start': start_dt,
                'duration': float(duration), 'guests': int(guests),
                'customer_name': name or (partner.name if partner else None),
                'phone': phone or (partner.phone if partner else None),
                'partner_id': partner.id if partner else False,
                'note': note or False,
            })
            return {'ok': True, 'reservation': self._res_payload(res)}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze reservations_create failed")
            return self._json({'ok': False, 'error': 'res_create_failed', 'message': str(exc)}, status=400)

    @http.route(f'{API_PREFIX}/reservations/state', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*', readonly=False)
    def reservations_state(self, reservation_id=None, action=None, guests=None,
                           arrival_note=None, table_id=None, session_id=None, **kw):
        """Advance a reservation through the guarded arrival lifecycle:
        confirm | arrive | wait | late | seat | no_show | cancel | complete | restore.
        Illegal moves (e.g. seating a completed/cancelled reservation, or re-seating
        one already at a live table) are REJECTED (invalid_transition), never written.
        On ``seat`` the reservation is idempotently attached to the table's single
        open draft order (no duplicate order on retry)."""
        auth = self._authorize()
        if auth:
            return auth
        from odoo.exceptions import UserError
        try:
            env = self._api_env()
            res = env['mezze.reservation'].sudo().browse(int(reservation_id))
            if not res.exists():
                return self._json({'ok': False, 'error': 'not_found'}, status=404)
            # CP10 — OBJECT-SCOPE: this reservation must belong to the caller's branch
            # (a host from Branch B cannot transition/seat a Branch A reservation by id).
            denied = self._security_gate(env, 'reservations/state', target=res)
            if denied:
                return denied
            s = self._mezze_principal_scope(env)
            # optional party-size update (manager permission enforced by the gate cap)
            if guests not in (None, '') and str(guests).isdigit():
                res.write({'guests': int(guests)})
            if table_id and str(table_id).isdigit():
                dest = env['restaurant.table'].browse(int(table_id))
                if not self._mezze_table_in_branch(env, dest, None if s.get('is_admin') else s.get('branch')):
                    return self._json({'ok': False, 'error': 'invalid_table'}, status=400)
                res.write({'table_id': int(table_id)})
            try:
                res.apply_transition(action, arrival_note=arrival_note)
            except UserError as ue:
                return self._json({'ok': False, 'error': 'invalid_transition',
                                   'message': str(ue)}, status=409)
            order_info = None
            if res.state == 'seated':
                order_info = self._seat_attach_order(env, res, session_id)
            self._audit(env, 'reservation.%s' % action, **self._actor(env, kw),
                        detail=json.dumps({'who': res._who(), 'state': res.state,
                                           'table_id': res.table_id.id or None}, default=str))
            return {'ok': True, 'reservation': self._res_payload(res), 'order': order_info}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze reservations_state failed")
            return self._json({'ok': False, 'error': 'res_state_failed', 'message': str(exc)}, status=400)

    def _seat_attach_order(self, env, res_or_wl, session_id):
        """Idempotently link a seated reservation/waitlist entry to the table's ONE
        open draft order (reuses ``_open_table_order`` — never creates a second
        order). Returns {order_id, order_uuid, attached} or None when no order exists
        yet (the durable pos.order is created on the first synced line and links back)."""
        table = res_or_wl.table_id
        if not table:
            return None
        session = None
        if session_id and str(session_id).isdigit():
            session = env['pos.session'].sudo().browse(int(session_id))
            if not session.exists():
                session = None
        if session is None:
            session = env['pos.session'].sudo().search(
                [('config_id', '=', res_or_wl.config_id.id), ('state', '=', 'opened')], limit=1) \
                if res_or_wl.config_id else env['pos.session'].sudo().search([('state', '=', 'opened')], limit=1)
        order = self._open_table_order(env, session, table.id) if session else None
        if order:
            if res_or_wl.pos_order_id.id != order.id:
                res_or_wl.sudo().write({'pos_order_id': order.id})
            self._mezze_propagate_seat_context(res_or_wl, order)
            return {'order_id': order.id, 'order_uuid': order.uuid, 'attached': True}
        return None

    @staticmethod
    def _mezze_propagate_seat_context(rec, order):
        """Carry a reservation/waitlist's guest count + customer onto its order,
        without overwriting values the cashier already set. Idempotent."""
        upd = {}
        guests = getattr(rec, 'guests', None) or getattr(rec, 'party_size', None)
        if guests and 'customer_count' in order._fields and not order.customer_count:
            upd['customer_count'] = int(guests)
        if getattr(rec, 'partner_id', False) and not order.partner_id:
            upd['partner_id'] = rec.partner_id.id
        if upd:
            order.sudo().write(upd)

    def _mezze_link_seated_order(self, env, order):
        """Back-link a table's live order to the seated reservation/waitlist waiting
        for it (fills an empty pos_order_id) and propagates guest/customer context.
        Idempotent; never raises into the sync/money path."""
        if not order.table_id:
            return
        try:
            for _m in ('mezze.reservation', 'mezze.waitlist'):
                if _m not in env:
                    continue
                rec = env[_m].sudo().search(
                    [('table_id', '=', order.table_id.id), ('state', '=', 'seated'),
                     ('pos_order_id', '=', False)], limit=1)
                if rec:
                    rec.write({'pos_order_id': order.id})
                    self._mezze_propagate_seat_context(rec, order)
        except Exception:  # noqa: BLE001
            _logger.exception("Mezze seat->order back-link failed (non-fatal)")

    # ------------------------------------------------------------------
    # Waitlist — the host-stand walk-in queue (mezze.waitlist)
    # ------------------------------------------------------------------
    def _waitlist_payload(self, w):
        now = fields.Datetime.now()
        waited = int((now - w.create_date).total_seconds() / 60) if w.create_date else 0
        return {
            'id': w.id, 'who': w._who(), 'phone': w.phone or '',
            'party_size': w.party_size, 'quoted_wait': w.quoted_wait, 'waited': waited,
            'state': w.state, 'note': w.note or '',
            'table': (str(w.table_id.table_number) if w.table_id else None),
            'over': (w.state in ('waiting', 'notified') and w.quoted_wait
                     and waited > w.quoted_wait),
        }

    def _waitlist_quote(self, env, config, party_size=2):
        """A rough wait estimate (minutes): free tables now → 0, else ~12 min per
        party already ahead in the queue, nudged up when the floor is full."""
        Table = env['restaurant.table']
        floor_dom = [('pos_config_ids', 'in', config.id)] if config else []
        tables = env['restaurant.floor'].search(floor_dom).table_ids.filtered('active') \
            if 'restaurant.floor' in env else Table.search([('active', '=', True)])
        total = len(tables) or 1
        occ = env['pos.order'].search_count(
            [('state', '=', 'draft'), ('config_id', '=', config.id), ('table_id', '!=', False)])
        waiting = env['mezze.waitlist'].search_count(
            [('config_id', '=', config.id), ('state', 'in', ('waiting', 'notified'))])
        free = max(0, total - occ)
        if free > 0 and waiting == 0:
            return 0
        est = 10 + waiting * 12 + (10 if free <= 0 else 0)
        return int(min(est, 120))

    @http.route(f'{API_PREFIX}/waitlist/list', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def waitlist_list(self, config_id=None, **kw):
        """The live queue (waiting + notified) oldest-first, plus a next-party
        quote and simple stats for the host stand."""
        auth = self._authorize()
        if auth:
            return auth
        env = self._api_env()
        try:
            # CP10 — scope-first: begin from the principal's branch, not a client id.
            scope, ok = self._mezze_scope_domain(env)
            if not ok:
                return {'ok': True, 'items': [], 'waiting': 0, 'covers': 0, 'quote': 0}
            config = self._resolve_config(env, config_id) if scope == [] else \
                env['pos.config'].browse(scope[0][2])
            dom = list(scope) + [('state', 'in', ('waiting', 'notified'))]
            parties = env['mezze.waitlist'].search(dom, order='create_date asc')
            items = [self._waitlist_payload(w) for w in parties]
            covers = sum(w.party_size for w in parties)
            return {'ok': True, 'items': items, 'waiting': len(items), 'covers': covers,
                    'quote': self._waitlist_quote(env, config, 2)}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze waitlist_list failed")
            return self._json({'ok': False, 'error': 'waitlist_list_failed',
                               'message': str(exc)}, status=400)

    @http.route(f'{API_PREFIX}/waitlist/add', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*', readonly=False)
    def waitlist_add(self, config_id=None, name=None, party_size=2, phone=None,
                     quoted_wait=None, partner_id=None, note=None, **kw):
        """Add a walk-in party to the queue. Quotes the wait automatically when
        one isn't supplied."""
        auth = self._authorize()
        if auth:
            return auth
        env = self._api_env()
        try:
            # CP10 — the queue entry is created in the caller's OWN branch (server-derived).
            s = self._mezze_principal_scope(env)
            if not s['ok']:
                return self._json({'ok': False, 'error': authz.AUTHENTICATION_REQUIRED}, status=401)
            config = (env['pos.config'].browse(int(s['branch'])) if s['branch']
                      else self._resolve_config(env, config_id)) if not s['is_admin'] \
                else self._resolve_config(env, config_id)
            size = max(1, int(party_size or 1))
            quote = int(quoted_wait) if quoted_wait not in (None, '') \
                else self._waitlist_quote(env, config, size)
            vals = {'config_id': config.id, 'party_size': size, 'quoted_wait': quote,
                    'customer_name': (name or '').strip() or False,
                    'phone': (phone or '').strip() or False,
                    'note': (note or '').strip() or False, 'state': 'waiting'}
            if partner_id:
                vals['partner_id'] = int(partner_id)
            w = env['mezze.waitlist'].create(vals)
            self._audit(env, 'waitlist.add', **self._actor(env, kw),
                        detail=json.dumps({'who': w._who(), 'size': size,
                                           'quoted_wait': quote}, default=str))
            return {'ok': True, 'waitlist': self._waitlist_payload(w)}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze waitlist_add failed")
            return self._json({'ok': False, 'error': 'waitlist_add_failed',
                               'message': str(exc)}, status=400)

    @http.route(f'{API_PREFIX}/waitlist/state', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*', readonly=False)
    def waitlist_state(self, waitlist_id=None, action=None, table_id=None, **kw):
        """Advance a party through the guarded queue lifecycle: notify | seating |
        seat | cancel | left | no_response | restore. Illegal moves are REJECTED.
        Seating records the table AND idempotently attaches the party to the table's
        single open draft order (no duplicate order on retry)."""
        auth = self._authorize()
        if auth:
            return auth
        from odoo.exceptions import UserError
        env = self._api_env()
        try:
            w = env['mezze.waitlist'].sudo().browse(int(waitlist_id))
            if not w.exists():
                return self._json({'ok': False, 'error': 'not_found'}, status=404)
            # CP10 — OBJECT-SCOPE: the queue entry must belong to the caller's branch.
            denied = self._security_gate(env, 'waitlist/state', target=w)
            if denied:
                return denied
            if table_id and str(table_id).isdigit():
                s = self._mezze_principal_scope(env)
                dest = env['restaurant.table'].browse(int(table_id))
                if not self._mezze_table_in_branch(env, dest, None if s.get('is_admin') else s.get('branch')):
                    return self._json({'ok': False, 'error': 'invalid_table'}, status=400)
            try:
                w.apply_transition(action, table_id=table_id)
            except UserError as ue:
                return self._json({'ok': False, 'error': 'invalid_transition',
                                   'message': str(ue)}, status=409)
            order_info = None
            if w.state == 'seated':
                order_info = self._seat_attach_order(env, w, kw.get('session_id'))
            self._audit(env, 'waitlist.%s' % action, **self._actor(env, kw),
                        detail=json.dumps({'who': w._who(), 'state': w.state,
                                           'table_id': w.table_id.id or None}, default=str))
            return {'ok': True, 'waitlist': self._waitlist_payload(w),
                    'table_id': w.table_id.id or None, 'order': order_info}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze waitlist_state failed")
            return self._json({'ok': False, 'error': 'waitlist_state_failed',
                               'message': str(exc)}, status=400)

    # ------------------------------------------------------------------
    # Delivery — mezze.delivery last-mile leg over a paid pos.order
    # ------------------------------------------------------------------
    def _delivery_fee_product(self, env):
        """The 'Delivery' fee product — a POS-available service with NO category
        so it's a valid order line but never shows on the menu (_menu_domain
        requires a pos category). Created on first use."""
        Product = env['product.product'].sudo()
        p = Product.search([('default_code', '=', 'MEZZE_DELIVERY_FEE')], limit=1)
        if not p:
            p = Product.create({
                'name': 'Delivery', 'default_code': 'MEZZE_DELIVERY_FEE',
                'type': 'service', 'available_in_pos': True,
                'taxes_id': [(6, 0, [])], 'list_price': 0.0,
            })
        return p

    def _delivery_payload(self, d, ready_map=None):
        """One delivery, as the board draws it. ``ready_map`` — same batched
        readiness contract the lane board uses; single-record callers omit it."""
        order = d.pos_order_id
        fee_pid = self._delivery_fee_product(d.env).id
        items = [{'name': l.product_id.display_name, 'qty': l.qty}
                 for l in order.lines if l.product_id.id != fee_pid and l.qty > 0]
        now = fields.Datetime.now()
        return {
            'id': d.id, 'state': d.state, 'who': d._who(), 'phone': d.phone or '',
            'address': d.address or '', 'area': d.area or '', 'fee': d.fee,
            'rider': d.rider or '', 'courier': d.courier_id.name or d.rider or '',
            'courier_id': d.courier_id.id or False,
            'zone': d.zone_id.name if d.zone_id else None,
            'note': d.note or '', 'order_id': order.id,
            'payment_mode': d.payment_mode, 'cod_collected': d.cod_collected,
            'cod_amount': round(d.cod_amount, 2) if d.payment_mode == 'cod' else 0.0,
            'paid': round(sum(order.payment_ids.mapped('amount')), 2),
            'cancel_reason': d.cancel_reason or '',
            'tracking': order.tracking_number or order.pos_reference or '',
            'total': round(order.amount_total, 2), 'items': items,
            'kitchen_ready': (ready_map[d.id] if ready_map is not None
                              else d._kitchen_ready()),
            'eta_minutes': d.eta_minutes,
            'placed_at': fields.Datetime.to_string(d.placed_at) if d.placed_at else None,
            'minutes': int((now - d.placed_at).total_seconds() / 60) if d.placed_at else 0,
        }

    def _zone_payload(self, z):
        return {'id': z.id, 'name': z.name, 'fee': z.fee, 'min_order': z.min_order,
                'eta_minutes': z.eta_minutes, 'active': z.active,
                'cod_allowed': z.cod_allowed, 'online_allowed': z.online_allowed,
                'priority': z.priority}

    @http.route(f'{API_PREFIX}/delivery/zones', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def delivery_zones(self, config_id=None, all=False, **kw):
        """Delivery zones for a branch (active only unless ``all``)."""
        auth = self._authorize()
        if auth:
            return auth
        env = self._api_env()
        try:
            config = self._resolve_config(env, config_id)
            dom = ['|', ('config_id', '=', config.id), ('config_id', '=', False)]
            if not all:
                dom = ['&', ('active', '=', True)] + dom
            zones = env['mezze.delivery.zone'].search(dom)
            return {'ok': True, 'zones': [self._zone_payload(z) for z in zones]}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze delivery_zones failed")
            return self._json({'ok': False, 'error': 'zones_failed', 'message': str(exc)}, status=400)

    @http.route(f'{API_PREFIX}/delivery/zone/save', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*', readonly=False)
    def delivery_zone_save(self, zone_id=None, config_id=None, name=None, fee=None,
                           min_order=None, eta_minutes=None, active=None, **kw):
        """Create or update a delivery zone (manager back-office)."""
        auth = self._authorize()
        if auth:
            return auth
        env = self._api_env()
        try:
            config = self._resolve_config(env, config_id)
            vals = {}
            if name is not None:
                vals['name'] = (name or '').strip()
            if fee is not None:
                vals['fee'] = float(fee)
            if min_order is not None:
                vals['min_order'] = float(min_order)
            if eta_minutes is not None:
                vals['eta_minutes'] = int(eta_minutes)
            if active is not None:
                vals['active'] = str(active).strip().lower() not in ('0', 'false', 'no')
            if zone_id:
                zone = env['mezze.delivery.zone'].browse(int(zone_id))
                if not zone.exists():
                    raise ValueError("Unknown zone %s" % zone_id)
                zone.write(vals)
            else:
                if not vals.get('name'):
                    raise ValueError("Zone name is required")
                vals.setdefault('config_id', config.id)
                zone = env['mezze.delivery.zone'].create(vals)
            self._audit(env, 'delivery.zone', **self._actor(env, kw),
                        detail=json.dumps({'zone': zone.name, 'fee': zone.fee,
                                           'min_order': zone.min_order}, default=str))
            return {'ok': True, 'zone': self._zone_payload(zone)}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze delivery_zone_save failed")
            return self._json({'ok': False, 'error': 'zone_save_failed', 'message': str(exc)}, status=400)

    @http.route(f'{API_PREFIX}/delivery/create', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*', readonly=False)
    def delivery_create(self, uuid=None, session_id=None, lines=None, fee=0.0,
                        customer=None, phone=None, address=None, partner_id=None,
                        note=None, payment_method_id=None, zone_id=None, **kw):
        """Create a delivery: a paid pos.order (food + delivery fee) that fires to
        the kitchen, plus the mezze.delivery tracking record."""
        auth = self._authorize()
        if auth:
            return auth
        if not lines:
            return self._json({'ok': False, 'error': 'no_lines'}, status=400)
        if not address:
            return self._json({'ok': False, 'error': 'missing_address'}, status=400)
        env = self._api_env()
        try:
            session = env['pos.session'].browse(int(session_id))
            if not session.exists():
                raise ValueError("Unknown session_id %s" % session_id)
            config = session.config_id
            env = env(context=dict(env.context, allowed_company_ids=[config.company_id.id], company_id=config.company_id.id))
            session = session.with_env(env)
            config = config.with_env(env)
            partner = env['res.partner'].browse(int(partner_id)) if partner_id else env['res.partner']
            order_lines, base, incl = self._build_lines(env, config, partner, lines)
            # Resolve the fee from the ZONE server-side (don't trust a client fee)
            # and enforce the zone's minimum order on the food subtotal.
            zone = env['mezze.delivery.zone'].browse(int(zone_id)) if zone_id \
                else env['mezze.delivery.zone']
            if zone and zone.exists():
                if zone.min_order and incl < zone.min_order:
                    raise ValueError("Order EGP %.2f is below the %s minimum of EGP %.2f"
                                     % (incl, zone.name, zone.min_order))
                fee = zone.fee
            else:
                fee = float(fee or 0.0)
            if fee > 0:
                fp = self._delivery_fee_product(env)
                order_lines.append((0, 0, {
                    'product_id': fp.id, 'qty': 1, 'price_unit': fee, 'discount': 0.0,
                    'tax_ids': [(6, 0, [])], 'price_subtotal': fee,
                    'price_subtotal_incl': fee, 'pack_lot_ids': []}))
                incl += fee
                base += fee
            uuid = uuid or 'dlv-%s' % session.id
            pmid = int(payment_method_id) if payment_method_id else (config.payment_method_ids[:1].id)
            order_dict = {
                'uuid': uuid, 'session_id': session.id, 'company_id': config.company_id.id,
                'user_id': env.uid, 'partner_id': partner.id or False,
                'pricelist_id': config.pricelist_id.id or False,
                'name': 'Mezze %s' % uuid,
                'date_order': fields.Datetime.to_string(fields.Datetime.now()),
                'lines': order_lines,
                'payment_ids': [(0, 0, {'amount': incl, 'name': fields.Datetime.now(),
                                        'payment_method_id': pmid})],
                'amount_tax': incl - base, 'amount_total': incl, 'amount_paid': incl,
                'amount_return': 0.0, 'last_order_preparation_change': empty_preparation_change(), 'to_invoice': False,
            }
            env['pos.order'].sync_from_ui([order_dict])
            order = env['pos.order'].search([('uuid', '=', uuid)], limit=1)
            if not order:
                raise ValueError("delivery order did not persist")
            # fire the food to the kitchen (station tickets)
            fee_pid = self._delivery_fee_product(env).id
            tickets = self._make_station_tickets(
                env, order,
                [(l.product_id, l.qty, '') for l in order.lines if l.product_id.id != fee_pid],
                'dlv:%s' % uuid, 1)
            self._publish_kds(env, tickets, order, natural_key='dlv:%s' % uuid)
            dlv = env['mezze.delivery'].create({
                'pos_order_id': order.id, 'partner_id': partner.id or False,
                'customer_name': customer or (partner.name if partner else None),
                'phone': phone or (partner.phone if partner else None),
                'address': address, 'fee': fee, 'note': note or False,
                'zone_id': (zone.id if zone and zone.exists() else False),
                'state': 'preparing',
            })
            earned, balance = self._loyalty_earn(env, order)
            return {'ok': True, 'delivery': self._delivery_payload(dlv),
                    'loyalty_earned': earned, 'loyalty_balance': balance}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze delivery_create failed")
            return self._json({'ok': False, 'error': 'delivery_create_failed', 'message': str(exc)}, status=400)

    @http.route(f'{API_PREFIX}/delivery/list', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def delivery_list(self, config_id=None, scope='active', done_minutes=30, **kw):
        """The delivery board. ``active`` = not delivered/failed + recently
        finished; ``all`` = everything today."""
        auth = self._authorize()
        if auth:
            return auth
        try:
            env = self._api_env()
            dom = self._mezze_scope_base(env, config_id)     # CP11 branch-scoped
            if scope == 'active':
                cutoff = fields.Datetime.now() - datetime.timedelta(minutes=int(done_minutes or 30))
                dom += ['|', ('state', 'not in', ('delivered', 'cancelled', 'rejected')),
                        ('placed_at', '>=', fields.Datetime.to_string(cutoff))]
            deliveries = env['mezze.delivery'].search(dom)
            # same batched readiness contract as the lane board: the delivery board
            # carried the identical per-row KDS search and scaled the same way
            ready_map = deliveries._kitchen_ready_map()
            return {'ok': True,
                    'deliveries': [self._delivery_payload(d, ready_map=ready_map)
                                   for d in deliveries]}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze delivery_list failed")
            return self._json({'ok': False, 'error': 'delivery_list_failed', 'message': str(exc)}, status=400)

    # Legacy action names (from the existing dispatch board) → new FSM actions.
    _DLV_ACTION_ALIAS = {'dispatch': 'out', 'failed': 'cancel'}

    @http.route(f'{API_PREFIX}/delivery/state', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*', readonly=False)
    def delivery_state(self, delivery_id=None, action=None, rider=None, courier_id=None,
                       reason=None, override=False, manager_code=None, manager_pin=None, **kw):
        """Server-authoritative delivery lifecycle step (§40). Actions:
        accept | reject | start_prep | ready | assign | unassign | out | delivered |
        cancel (legacy: dispatch→out, failed→cancel). Illegal jumps are refused unless
        a manager override is supplied. Cancelling/rejecting once the food has fired
        (past 'accepted') needs a manager (§44). Reasons are required for cancel/reject."""
        auth = self._authorize()
        if auth:
            return auth
        try:
            env = self._api_env()
            d = env['mezze.delivery'].browse(int(delivery_id))
            if not d.exists():
                return self._json({'ok': False, 'error': 'not_found'}, status=404)
            act = self._DLV_ACTION_ALIAS.get(action, action)
            if not act:
                return self._json({'ok': False, 'error': 'bad_action'}, status=400)
            # manager gate: override an illegal jump, OR cancel/reject after the food
            # has fired (state past 'accepted') — the customer can never self-cancel a
            # fired order; a manager must act (§44).
            manager = None
            need_manager = bool(override) or (
                act in ('cancel', 'reject') and d.state not in ('placed', 'accepted'))
            if need_manager:
                manager, mgr_err = self._verify_delivery_manager(env, manager_code, manager_pin)
                if not manager:
                    return self._json({'ok': False, 'error': mgr_err}, status=403)
            courier = env['mezze.courier'].browse(int(courier_id)) if courier_id else None
            actor = (self._actor(env, kw) or {}).get('cashier_name') or (manager.name if manager else '')
            # dispatch straight out with a free-text rider (no courier record)
            if act == 'out' and rider and not courier:
                d.rider = rider
            if act == 'cancel' and not reason:
                reason = 'other'
            try:
                d._transition(act, actor=actor, reason=(reason or rider),
                              courier=courier, override=bool(override) or need_manager)
            except UserError as te:
                return self._json({'ok': False, 'error': 'illegal_transition',
                                   'message': str(te)}, status=409)
            return {'ok': True, 'delivery': self._delivery_payload(d)}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze delivery_state failed")
            return self._json({'ok': False, 'error': 'delivery_state_failed', 'message': str(exc)}, status=400)

    def _elevated_approver(self, env, capability):
        """The supervisor/manager who authorised THIS request, or None.

        Reads the manager credential off the current request, verifies it, and
        checks that the approver's own role actually holds ``capability`` — an
        elevation can never conjure a permission its approver does not have.
        Returns None when the branch has not enabled elevation, when no credential
        was supplied, or when the credential does not carry the capability.
        """
        enabled = str(env['ir.config_parameter'].sudo().get_param(
            'mezze_bridge.allow_manager_elevation', '0')).strip().lower()
        if enabled in ('0', 'false', 'no', 'off', ''):
            return None
        try:
            params = request.get_json_data() or {}
        except Exception:  # noqa: BLE001 — a non-JSON body simply carries no credential
            return None
        approver, _err = self._verify_inline_approver(
            env, params.get('manager_code'), params.get('manager_pin'), min_rank=1)
        if not approver:
            return None
        if capability not in authz.ROLE_CAPS.get(approver.role, frozenset()):
            return None
        return approver

    def _pin_budget_source(self, env):
        """Whose budget an at-the-till PIN attempt is counted against.

        The authenticated TERMINAL, so each till carries its own ceiling. Never the
        IP: a restaurant sits behind one address, so an IP key would let a single
        attacked till lock out every other one.
        """
        try:
            ctx = self._resolve_principal(env)
            term = ctx.get('terminal')
            if term:
                return 'till:%s' % term.id
            return 'principal:%s' % (ctx.get('principal') or 'unknown')
        except Exception:  # noqa: BLE001
            return 'principal:unknown'

    def _verify_inline_approver(self, env, code, pin, min_rank=1):
        """(approver | None, error) for an approval given AT THE TILL.

        /orders/comp originally accepted only an ``approval_token`` minted by
        /w1/approve — but that route requires ADMIN_SETTINGS, which a terminal
        principal does not hold, so a till could never obtain the token its own
        comp needed. The approval could not be given at the place it is always
        given: a manager standing at the counter typing their PIN.

        This verifies the SAME mezze.cashier code + PIN + role rank the token path
        verifies, server-side, and is the pattern already used by /orders/pay and
        /delivery/state. The approver is a DIFFERENT credential from the operating
        terminal, so a cashier still cannot self-approve — they do not know a
        supervisor's PIN, and rank is checked here, not claimed by the client.
        """
        if not (code and pin):
            return None, 'manager_required'
        # THROTTLED. This is the most exposed PIN prompt in the product: it is
        # reachable from a till, on money routes (comp, pay, delivery state, and
        # now the session close), and it used to verify with a bare check_pin —
        # ten thousand guesses at a counter overnight. Same ceiling and the same
        # failure-only counting as the shift login; keyed on the terminal so one
        # attacked till cannot lock out the shop.
        c, err, retry = env['mezze.cashier'].sudo().authenticate_pin(
            code, pin,
            station_surface.approval_keys(self._pin_budget_source(env), code),
            station_surface.APPROVAL_WINDOW_SECONDS)
        if err:
            return None, err
        if {'cashier': 0, 'supervisor': 1, 'manager': 2}.get(c.role, 0) < min_rank:
            return None, 'insufficient_role'
        return c, None

    def _verify_delivery_manager(self, env, code, pin):
        """(manager | None, error). A cashier PIN can never authorise (rank < manager)."""
        if not (code and pin):
            return None, 'manager_required'
        c = env['mezze.cashier'].sudo().search([('code', '=', code), ('active', '=', True)], limit=1)
        if not c or not c.check_pin(pin):
            return None, 'bad_credentials'
        if {'cashier': 0, 'supervisor': 1, 'manager': 2}.get(c.role, 0) < 2:
            return None, 'insufficient_role'
        return c, None

    @http.route(f'{API_PREFIX}/delivery/collect', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*', readonly=False)
    def delivery_collect(self, delivery_id=None, **kw):
        """Record the ONE real cash pos.payment for a COD delivery when the cashier/
        driver confirms collection (§31). Never fakes receipt before this; idempotent."""
        auth = self._authorize()
        if auth:
            return auth
        try:
            env = self._api_env()
            d = env['mezze.delivery'].browse(int(delivery_id))
            if not d.exists():
                return self._json({'ok': False, 'error': 'not_found'}, status=404)
            actor = (self._actor(env, kw) or {}).get('cashier_name') or ''
            try:
                pay = d._collect_cod(actor=actor)
            except UserError as ce:
                return self._json({'ok': False, 'error': 'collect_rejected', 'message': str(ce)}, status=409)
            self._audit(env, 'delivery.collect', d.pos_order_id, **self._actor(env, kw))
            return {'ok': True, 'delivery': self._delivery_payload(d),
                    'payment_id': pay.id if pay else False}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze delivery_collect failed")
            return self._json({'ok': False, 'error': 'delivery_collect_failed', 'message': str(exc)}, status=400)

    @http.route(f'{API_PREFIX}/delivery/availability', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def delivery_availability(self, store=None, config_id=None, zone_id=None,
                              subtotal=0.0, payment_mode='cod', **kw):
        """Server-authoritative delivery availability (§12): given a branch + chosen
        zone + food subtotal, return eligible / fee / minimum / ETA / allowed payment
        methods / open. The browser NEVER decides any of these; it only supplies the
        context. Public (store-scoped) — exposes no branch internals."""
        try:
            env = self._api_env()
            config = self._store_config(env, store) if store else (
                env['pos.config'].browse(int(config_id)) if config_id else env['pos.config'].search([], limit=1))
            if not config or not config.exists():
                return self._json({'ok': False, 'error': 'not_found'}, status=404)
            sub = round(float(subtotal or 0.0), 2)
            zone = env['mezze.delivery.zone'].sudo().browse(int(zone_id)) if zone_id else env['mezze.delivery.zone']
            if not (zone and zone.exists() and zone.active
                    and (not zone.config_id or zone.config_id.id == config.id)):
                return {'ok': True, 'eligible': False, 'reason': 'out_of_zone'}
            now = fields.Datetime.now()
            if not zone._is_open(now):
                return {'ok': True, 'eligible': False, 'reason': 'closed', 'zone': zone.name}
            below = zone.min_order and sub < zone.min_order
            pay_ok = zone.cod_allowed if payment_mode == 'cod' else zone.online_allowed
            return {'ok': True, 'eligible': bool(pay_ok and not below),
                    'zone': zone.name, 'zone_id': zone.id,
                    'fee': round(zone.fee, 2), 'min_order': round(zone.min_order, 2),
                    'eta_minutes': zone.eta_minutes,
                    'below_minimum': bool(below),
                    'remaining': round(zone.min_order - sub, 2) if below else 0.0,
                    'cod_allowed': zone.cod_allowed, 'online_allowed': zone.online_allowed,
                    'total_with_fee': round(sub + zone.fee, 2)}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze delivery_availability failed")
            return self._json({'ok': False, 'error': 'availability_failed', 'message': str(exc)}, status=400)

    @http.route(f'{API_PREFIX}/delivery/report', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def delivery_report(self, config_id=None, since=None, **kw):
        """Delivery KPIs (§58): counts, revenue, AOV, fees, COD vs prepaid,
        cancellations by reason, avg prep/delivery minutes, by zone + by courier."""
        auth = self._authorize()
        if auth:
            return auth
        try:
            env = self._api_env()
            dom = self._mezze_scope_base(env, config_id)     # CP11 branch-scoped
            if since:
                dom.append(('placed_at', '>=', since))
            ds = env['mezze.delivery'].search(dom)
            done = ds.filtered(lambda d: d.state == 'delivered')
            revenue = sum(d.pos_order_id.amount_total for d in done)
            fees = sum(d.fee for d in done)
            cancels = ds.filtered(lambda d: d.state in ('cancelled', 'rejected'))
            by_reason = {}
            for d in cancels:
                r = d.cancel_reason or (d.reject_reason and 'rejected') or 'other'
                by_reason[r] = by_reason.get(r, 0) + 1

            def _avg(recs, a, b):
                vals = [(getattr(d, b) - getattr(d, a)).total_seconds() / 60
                        for d in recs if getattr(d, a) and getattr(d, b)]
                return round(sum(vals) / len(vals), 1) if vals else 0.0
            by_zone, by_courier = {}, {}
            for d in ds:
                by_zone.setdefault(d.zone_id.name or '—', 0)
                by_zone[d.zone_id.name or '—'] += 1
                if d.courier_id:
                    by_courier.setdefault(d.courier_id.name, 0)
                    by_courier[d.courier_id.name] += 1
            return {'ok': True,
                    'total': len(ds), 'delivered': len(done),
                    'revenue': round(revenue, 2), 'fees': round(fees, 2),
                    'aov': round(revenue / len(done), 2) if done else 0.0,
                    'cod': len(ds.filtered(lambda d: d.payment_mode == 'cod')),
                    'prepaid_or_online': len(ds.filtered(lambda d: d.payment_mode in ('online', 'prepaid'))),
                    'cod_uncollected': len(ds.filtered(
                        lambda d: d.payment_mode == 'cod' and not d.cod_collected and d.state != 'cancelled')),
                    'cancellations': len(cancels), 'cancel_reasons': by_reason,
                    'avg_prep_minutes': _avg(ds, 'accepted_at', 'ready_at'),
                    'avg_delivery_minutes': _avg(done, 'dispatched_at', 'delivered_at'),
                    'by_zone': by_zone, 'by_courier': by_courier}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze delivery_report failed")
            return self._json({'ok': False, 'error': 'report_failed', 'message': str(exc)}, status=400)

    @http.route(f'{API_PREFIX}/delivery/couriers', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*', readonly=False)
    def delivery_couriers(self, config_id=None, name=None, phone=None, courier_id=None,
                          status=None, **kw):
        """List couriers for a branch, or create/update one (manual dispatch pool)."""
        auth = self._authorize()
        if auth:
            return auth
        try:
            env = self._api_env()
            Courier = env['mezze.courier']
            if name or courier_id:
                vals = {}
                if name:
                    vals['name'] = name
                if phone is not None:
                    vals['phone'] = phone
                if status in ('available', 'on_delivery', 'offline'):
                    vals['status'] = status
                if courier_id:
                    c = Courier.browse(int(courier_id))
                    if not c.exists():
                        return self._json({'ok': False, 'error': 'not_found'}, status=404)
                    c.write(vals)
                else:
                    vals.setdefault('config_id', int(config_id) if config_id else False)
                    c = Courier.create(vals)
                return {'ok': True, 'courier': c._safe()}
            dom = [('active', '=', True)]
            if config_id:
                dom += ['|', ('config_id', '=', int(config_id)), ('config_id', '=', False)]
            return {'ok': True, 'couriers': [c._safe() for c in Courier.search(dom)]}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze delivery_couriers failed")
            return self._json({'ok': False, 'error': 'couriers_failed', 'message': str(exc)}, status=400)

    # ------------------------------------------------------------------
    # Drive-thru lane — cars queued through order -> window -> collect
    # ------------------------------------------------------------------
    def _dt_payload(self, d, position=None, ready_map=None):
        """One car, as the board draws it.

        ``ready_map`` is the board's single batched readiness answer (see
        ``mezze.kitchen.readiness.mixin``). Passing it is what keeps a 36-car board
        at one KDS query instead of 36. Single-car callers — create, stage — leave it
        out and get the scalar form, which is one record and therefore already bounded.
        """
        order = d.pos_order_id
        # `name`, not display_name: the latter carries the internal reference
        # ("[GIFTCARD] Gift Card"), which is noise on a lane board where the
        # operator is matching a bag to a car. Scoped to this payload — the shared
        # menu list keeps display_name, so the Register is untouched.
        items = [{'name': l.product_id.name, 'qty': l.qty}
                 for l in order.lines if l.qty > 0 and l.product_id.type != 'combo'
                 and not l.combo_parent_id]
        now = fields.Datetime.now()
        return {
            'id': d.id, 'lane': d.lane or 1, 'position': position,
            'vehicle': d.vehicle or '', 'who': d._who(), 'state': d.state,
            'order_id': order.id, 'note': d.note or '',
            'tracking': order.tracking_number or order.pos_reference or '',
            'total': round(order.amount_total, 2), 'items': items,
            'kitchen_ready': (ready_map[d.id] if ready_map is not None
                              else d._kitchen_ready()),
            'paid': d._paid(),
            # DT-CORE6 physical truth. `state` stays for compatibility; these are
            # what a client should reason about when it needs to know WHERE a car
            # is, as opposed to how long it has waited.
            'vehicle_stage': d.vehicle_stage,
            'lane_sequence': d.lane_sequence or 0,
            'service_sequence': d.service_sequence or 0,
            'placed_at': fields.Datetime.to_string(d.placed_at) if d.placed_at else None,
            'minutes': int((now - d.placed_at).total_seconds() / 60) if d.placed_at else 0,
        }

    @http.route(f'{API_PREFIX}/drivethru/create', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*', readonly=False)
    def drivethru_create(self, uuid=None, session_id=None, lines=None, lane=1,
                         vehicle=None, customer=None, partner_id=None, note=None,
                         fire_uuid=None, **kw):
        """Add a car to the lane: fire its order to the kitchen as a DRAFT (kitchen
        starts immediately; payment is taken at the window) and create the
        mezze.drivethru tracking record. Reuses the shared fire core, so combos,
        half-&-half and station routing all work."""
        auth = self._authorize()
        if auth:
            return auth
        if not lines:
            return self._json({'ok': False, 'error': 'no_lines'}, status=400)
        env = self._api_env()
        try:
            session = env['pos.session'].browse(int(session_id))
            if not session.exists():
                raise ValueError("Unknown session_id %s" % session_id)
            config = session.config_id
            env = env(context=dict(env.context, allowed_company_ids=[config.company_id.id],
                                   company_id=config.company_id.id))
            session = session.with_env(env)
            config = config.with_env(env)
            uuid = uuid or 'dt-%s-%s' % (session.id, os.urandom(4).hex())
            fire_uuid = fire_uuid or uuid
            # fire to kitchen as a draft (table_id=None -> counter/off-table order)
            res = self._do_fire(env, uuid, session, config, None, lines,
                                partner_id, None, fire_uuid,
                                server_override='Drive-thru')
            order = env['pos.order'].browse(res['order_id'])
            partner = env['res.partner'].browse(int(partner_id)) if partner_id else env['res.partner']
            # CHANNEL. Delivery, kiosk, pickup and aggregator all stamp
            # pos.order.mezze_channel; drive-thru was the one flow that never did, so
            # its orders read as plain counter orders everywhere downstream — the KDS
            # badge, reporting by channel, analytics. The field already documents
            # 'drivethru' as a value, so this is using the canonical mechanism, not
            # extending it. Stamped on the ORDER so the identity survives reload,
            # serialization, payment, collection and reporting.
            if 'mezze_channel' in order._fields and not order.mezze_channel:
                order.sudo().write({'mezze_channel': 'drivethru'})
            dt = env['mezze.drivethru'].create({
                'pos_order_id': order.id, 'partner_id': partner.id or False,
                'customer_name': customer or (partner.name if partner else None),
                'lane': int(lane or 1), 'vehicle': (vehicle or '').strip() or False,
                'note': (note or '').strip() or False, 'state': 'preparing',
            })
            self._audit(env, 'drivethru.create', order, **self._actor(env, kw),
                        detail=json.dumps({'lane': dt.lane, 'vehicle': dt.vehicle}, default=str))
            return {'ok': True, 'car': self._dt_payload(dt)}
        except Exception as exc:  # noqa: BLE001
            _reraise_if_retryable(exc)
            _logger.exception("Mezze drivethru_create failed")
            return self._json({'ok': False, 'error': 'drivethru_create_failed', 'message': str(exc)}, status=400)

    @http.route(f'{API_PREFIX}/drivethru/board', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def drivethru_board(self, config_id=None, done_minutes=10, **kw):
        """The lane board: every live car (preparing/ready/at_window) plus cars
        collected/cancelled within ``done_minutes``, ordered by lane then FIFO.
        Each car carries its 1-based position within its lane. A car whose
        kitchen is done auto-advances preparing -> ready so the operator sees it
        light up without a manual bump."""
        auth = self._authorize()
        if auth:
            return auth
        try:
            env = self._api_env()
            DT = env['mezze.drivethru']
            live = ('preparing', 'ready', 'at_window')
            dom = ['|', ('state', 'in', live)]
            cutoff = fields.Datetime.now() - datetime.timedelta(minutes=int(done_minutes or 10))
            dom += ['&', ('state', 'in', ('collected', 'cancelled')),
                    ('placed_at', '>=', fields.Datetime.to_string(cutoff))]
            dom = self._mezze_scope_base(env, config_id) + dom   # CP11 branch-scoped
            cars = DT.search(dom)
            # ONE readiness answer for the whole board. The request has two consumers
            # of it — the legacy auto-advance below and every card's payload — and
            # each of them used to ask the KDS per car, so a queue of N cars cost the
            # kitchen O(N) searches to draw one screen. Both now read this map.
            ready_map = cars._kitchen_ready_map()
            # auto-advance preparing -> ready when the kitchen is done
            stale = cars.filtered(lambda x: x.state == 'preparing' and ready_map.get(x.id))
            if stale:
                stale.write({'state': 'ready', 'ready_at': fields.Datetime.now()})
            # position within each lane (live cars only, FIFO)
            pos = {}
            out = []
            for c in cars:
                if c.state in live:
                    pos.setdefault(c.lane, 0)
                    pos[c.lane] += 1
                    out.append(self._dt_payload(c, position=pos[c.lane], ready_map=ready_map))
                else:
                    out.append(self._dt_payload(c, ready_map=ready_map))
            lanes = sorted(set(cars.mapped('lane')) | {1})
            # The board's timers must be anchored to the SERVER clock, not the
            # browser's: a till with a skewed clock would otherwise show a car as
            # late (or on time) when it is not, and speed-of-service is the number
            # this screen exists to report. `now` lets the client tick smoothly
            # between polls while staying anchored to server truth.
            target = int(env['ir.config_parameter'].sudo().get_param(
                'mezze_bridge.drivethru_target_seconds', '180') or 180)
            # NEXT PHYSICAL car, derived from authoritative sequence rather than
            # from a timer. It is deliberately separate from "most delayed": with
            # two lanes those are routinely different cars, and reordering physical
            # truth to make urgency look tidy is how the wrong car gets served.
            active = [c for c in out if c['vehicle_stage'] in
                      ('lane', 'called', 'payment_window', 'pickup_window', 'holding')]
            merged = sorted([c for c in active if c['service_sequence']],
                            key=lambda c: c['service_sequence'])
            waiting = sorted([c for c in active if not c['service_sequence']],
                             key=lambda c: (c['lane_sequence'], c['id']))
            return {'ok': True, 'lanes': lanes, 'cars': out,
                    'now': fields.Datetime.to_string(fields.Datetime.now()),
                    'target_seconds': target,
                    'topology': DT._topology() if DT else 'combined',
                    # the merged path, in the order the cars actually entered it
                    'service_order': [c['id'] for c in merged],
                    # still in lane, in arrival order — who to call forward next
                    'next_to_call': waiting[0]['id'] if waiting else None}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze drivethru_board failed")
            return self._json({'ok': False, 'error': 'drivethru_board_failed', 'message': str(exc)}, status=400)

    @http.route(f'{API_PREFIX}/drivethru/quote', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def drivethru_quote(self, config_id=None, lines=None, **kw):
        """What does the cart the operator is typing actually cost?

        The order panel shows subtotal / tax / total, and none of those may be a
        number the browser worked out for itself. This prices the cart through
        `mezze.cart.pricing` — the SAME pass the customer's confirmation board uses,
        so the two screens can never disagree — and returns only rows that exist: a
        branch with no tax gets no tax row rather than an invented one.

        Read-only, and deliberately independent of whether the lane has a customer
        display. The operator's totals must not depend on an appliance being present.
        """
        auth = self._authorize()
        if auth:
            return auth
        try:
            env = self._api_env()
            config = self._resolve_config(env, config_id)
            rows, money = env['mezze.cart.pricing']._price_cart(config, lines or [])
            # The BRANCH's currency, matching what the pricing pass just rounded at.
            # Quoting a lane in the company's currency labels a real bill with the
            # wrong symbol and the wrong number of decimals.
            currency = config.sudo().currency_id or config.sudo().company_id.currency_id
            return {'ok': True, 'lines': rows, 'money': money,
                    'currency': {'name': currency.name,
                                 'symbol': currency.symbol or currency.name,
                                 'position': currency.position,
                                 'decimals': currency.decimal_places}}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze drivethru_quote failed")
            return self._json({'ok': False, 'error': 'drivethru_quote_failed',
                               'message': str(exc)}, status=400)

    @http.route(f'{API_PREFIX}/drivethru/stage', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*', readonly=False)
    def drivethru_stage(self, drivethru_id=None, action=None, payment_method_id=None, **kw):
        """Advance a car through the lane:
          ready    — mark the food ready (usually auto from the KDS)
          window   — call the car forward to the payment/pickup window
          pay       — settle the draft order at the window
          collected — hand off (requires the order to be paid)
          cancel    — remove the car from the lane
        """
        auth = self._authorize()
        if auth:
            return auth
        try:
            env = self._api_env()
            d = env['mezze.drivethru'].browse(int(drivethru_id))
            if not d.exists():
                return self._json({'ok': False, 'error': 'not_found'}, status=404)
            order = d.pos_order_id
            config = order.config_id
            env = env(context=dict(env.context, allowed_company_ids=[config.company_id.id],
                                   company_id=config.company_id.id))
            d = d.with_env(env)
            order = order.with_env(env)
            # TERMINAL LIFECYCLE. A departed car has its food and is gone; a cancelled
            # visit is void. Until now this endpoint only checked that the record
            # existed, so `cancel` -> `window` -> `collected` walked a cancelled visit
            # back to the window and handed food out against it. Every action is
            # refused on a finished visit — including `pay`, because taking money for
            # a cancelled order is the same defect wearing a different hat.
            #
            # The one exception is repeating the action that ENDED the visit: a stale
            # board will do that, and it should quietly agree rather than alarm. It
            # changes nothing, which `unchanged` says out loud.
            if d._is_terminal():
                if d._stage_ended_by(action) == d.vehicle_stage:
                    return {'ok': True, 'unchanged': True, 'car': self._dt_payload(d)}
                return self._json({'ok': False, 'error': 'invalid_transition',
                                   'vehicle_stage': d.vehicle_stage,
                                   'message': 'This car has already left the lane'},
                                  status=409)
            now = fields.Datetime.now()
            if action == 'ready':
                d.write({'state': 'ready', 'ready_at': d.ready_at or now})
            elif action == 'window':
                # CALL FORWARD is a physical movement, and nothing else: it must not
                # mark paid, ready or collected — those have their own authorities.
                # It claims the car's place in the MERGED path, which is the number
                # Payment and Pickup can trust when two lanes feed one window.
                d._claim_service_sequence()
                topology = d._topology()
                stage = ('payment_window' if topology == 'two_window'
                         else 'payment_window')   # combined: one window serves both
                d._set_stage(stage, called_at=now, window_at=now)
            elif action == 'pickup':
                # TWO-WINDOW topology only: the car leaves payment and moves up.
                # In a combined branch the same window serves both, so there is no
                # second position to move to and the action is a no-op by design.
                if d._topology() == 'two_window':
                    d._set_stage('pickup_window', pickup_window_at=now)
            elif action == 'hold':
                # reserved: parking / pull-forward. Recorded so the sequence model
                # can carry it later without renumbering; no UX in this phase.
                d._set_stage('holding', held_at=now)
            elif action == 'pay':
                if order.state == 'draft':
                    pm = (env['pos.payment.method'].browse(int(payment_method_id))
                          if payment_method_id else config.payment_method_ids[:1])
                    order.add_payment({'amount': order.amount_total, 'payment_method_id': pm.id,
                                       'name': now, 'pos_order_id': order.id})
                    order.action_pos_order_paid()
                    self._loyalty_earn(env, order)
                    self._audit(env, 'order.pay', order, **self._actor(env, kw),
                                detail=json.dumps({'via': 'drivethru'}))
            elif action == 'collected':
                # HANDOFF GATE. Payment was already required; kitchen readiness was
                # not, so a car could be marked collected while its food was still
                # being cooked — the expensive error at a lane window, and one the
                # operator cannot undo by handing the bag back.
                #
                # Both checks run HERE, inside the request transaction, against live
                # state: _paid() reads the order and _kitchen_ready() reads the KDS
                # tickets at mutation time. A client that fetched a stale board and
                # then clicked cannot smuggle a handoff past this, which is why the
                # gate is not merely a disabled button.
                if not d._paid():
                    return self._json({'ok': False, 'error': 'unpaid',
                                       'message': 'Take payment before handing off'}, status=409)
                if not d._kitchen_ready():
                    # Semantic code, not prose: the client maps it to localized
                    # operational copy rather than matching on English text.
                    return self._json({'ok': False, 'error': 'kitchen_not_ready',
                                       'message': 'Kitchen is still preparing this order'},
                                      status=409)
                # PHYSICAL POSITION. The model documents the lifecycle as
                # preparing -> ready -> at_window -> collected, and `at_window` means
                # the car has actually reached the window. Nothing enforced that, so
                # a mis-tap could hand off a car still back in the lane — food out of
                # the window to nobody. Handing off is the one irreversible step here,
                # so it requires the car to be where the food is.
                #
                # This is not a dead end: Call forward is one tap on the pickup screen
                # and on the board. If a branch ever needs curb/pull-forward handoff
                # without calling a car to the window, that is a business decision to
                # take deliberately, not something to leave open by omission.
                # The car must be at the position where food physically leaves —
                # the PICKUP window in a two-window branch, the single window in a
                # combined one. A car still at payment in a two-window branch has
                # not reached the handoff point yet.
                if not d._at_handoff_position():
                    return self._json({'ok': False, 'error': 'not_at_window',
                                       'message': 'Call the car forward before handing off'},
                                      status=409)
                d._set_stage('departed', collected_at=now)
            elif action == 'cancel':
                # terminal: the car leaves the ACTIVE queue but keeps its historical
                # sequence numbers, so the audit trail stays intact and the numbers
                # of cars behind it are never rewritten
                d._set_stage('cancelled')
            else:
                return self._json({'ok': False, 'error': 'bad_action'}, status=400)
            return {'ok': True, 'car': self._dt_payload(d)}
        except Exception as exc:  # noqa: BLE001
            _reraise_if_retryable(exc)
            _logger.exception("Mezze drivethru_stage failed")
            return self._json({'ok': False, 'error': 'drivethru_stage_failed', 'message': str(exc)}, status=400)

    # ------------------------------------------------------------------
    # Multi-branch — each pos.config is a branch; HQ consolidates them
    # ------------------------------------------------------------------
    def _branch_stats(self, env, config, full=False):
        """Live snapshot for one branch (pos.config). ``full`` adds occupancy,
        open kitchen tickets and margin for the HQ view."""
        now = fields.Datetime.now()
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        Order = env['pos.order']
        paid = Order.search([('config_id', '=', config.id),
                             ('state', 'in', ('paid', 'done', 'invoiced')),
                             ('date_order', '>=', fields.Datetime.to_string(start))])
        net = sum(paid.mapped('amount_total'))
        tx = len(paid)
        drafts = Order.search([('config_id', '=', config.id), ('state', '=', 'draft')])
        table_drafts = drafts.filtered(lambda o: 'table_id' in o._fields and o.table_id)
        deliveries = env['mezze.delivery'].search(
            [('config_id', '=', config.id), ('state', 'not in', ('delivered', 'failed'))]) \
            if 'mezze.delivery' in env else env['pos.order'].browse()
        session = config.current_session_id
        stats = {
            'id': config.id, 'name': config.name,
            'company': config.company_id.name,
            'session_open': bool(session and session.state == 'opened'),
            'session_id': session.id if session else None,
            'net_sales': round(net, 2), 'tx': tx,
            'avg_ticket': round(net / tx, 2) if tx else 0.0,
            'open_tabs': len(table_drafts),
            'active_deliveries': len(deliveries),
        }
        if full:
            tables = env['restaurant.table'].search(
                [('floor_id.pos_config_ids', 'in', config.id), ('active', '=', True)]) \
                if 'restaurant.table' in env else env['pos.order'].browse()
            occ = len(table_drafts.mapped('table_id'))
            rev = theo = 0.0
            rcache = {}
            for o in paid:
                for l in o.lines:
                    if l.qty <= 0:
                        continue
                    p = l.product_id
                    if p.id not in rcache:
                        rcache[p.id] = self._recipe_cost(p)
                    rev += l.price_subtotal_incl
                    theo += rcache[p.id] * l.qty
            open_tix = env['mezze.kds.ticket'].search_count(
                [('config_id', '=', config.id),
                 ('state', 'in', ('fired', 'accepted', 'preparing'))]) if 'mezze.kds.ticket' in env else 0
            stats.update({
                'occupied': occ, 'total_tables': len(tables),
                'margin': round(((rev - theo) / rev * 100.0), 1) if rev else 0.0,
                'open_tickets': open_tix,
            })
        return stats

    @http.route(f'{API_PREFIX}/branches', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def branches(self, **kw):
        """List the chain's branches (pos.config) with light live status — used
        by the branch switcher."""
        auth = self._authorize()
        if auth:
            return auth
        try:
            env = self._api_env()
            configs = env['pos.config'].search([], order='id asc')
            return {'ok': True, 'branches': [self._branch_stats(env, c) for c in configs]}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze branches failed")
            return self._json({'ok': False, 'error': 'branches_failed', 'message': str(exc)}, status=400)

    @http.route(f'{API_PREFIX}/hq/summary', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def hq_summary(self, **kw):
        """Consolidated chain view: full per-branch KPIs + chain totals."""
        auth = self._authorize()
        if auth:
            return auth
        try:
            env = self._api_env()
            configs = env['pos.config'].search([], order='id asc')
            branches = [self._branch_stats(env, c, full=True) for c in configs]
            total = {
                'net_sales': round(sum(b['net_sales'] for b in branches), 2),
                'tx': sum(b['tx'] for b in branches),
                'open_tabs': sum(b['open_tabs'] for b in branches),
                'active_deliveries': sum(b['active_deliveries'] for b in branches),
                'open_tickets': sum(b.get('open_tickets', 0) for b in branches),
                'occupied': sum(b.get('occupied', 0) for b in branches),
                'total_tables': sum(b.get('total_tables', 0) for b in branches),
                'branches': len(branches),
                'open_branches': sum(1 for b in branches if b['session_open']),
            }
            total['avg_ticket'] = round(total['net_sales'] / total['tx'], 2) if total['tx'] else 0.0
            return {'ok': True, 'as_of': fields.Datetime.to_string(fields.Datetime.now()),
                    'total': total, 'branches': branches}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze hq_summary failed")
            return self._json({'ok': False, 'error': 'hq_failed', 'message': str(exc)}, status=400)

    # ------------------------------------------------------------------
    # Central Kitchen — real mrp.production + stock.picking over branches
    # ------------------------------------------------------------------
    def _ck_warehouse(self, env):
        return env['stock.warehouse'].search([('company_id', '=', env.company.id)], limit=1)

    def _ck_central(self, env, ensure=True):
        """Central Kitchen stock location.

        ``ensure=False`` NEVER creates. Looking at a board is a READ, and a read runs on
        a readonly cursor: provisioning a warehouse location as a side effect of
        rendering a screen both fails on a fresh database ("cannot execute INSERT in a
        read-only transaction") and is wrong in principle. Creation belongs to the CK
        write paths (request / produce / receive).
        """
        loc = env['stock.location'].search(
            [('name', '=', 'Central Kitchen'), ('usage', '=', 'internal')], limit=1)
        if not loc and ensure:
            loc = env['stock.location'].create({
                'name': 'Central Kitchen', 'usage': 'internal',
                'location_id': self._ck_warehouse(env).view_location_id.id})
        return loc

    def _ck_branch_location(self, env, config, ensure=True):
        """Per-branch CK location. See ``_ck_central`` for why ``ensure=False`` matters."""
        name = 'Branch/%s' % config.name
        loc = env['stock.location'].search([('name', '=', name), ('usage', '=', 'internal')], limit=1)
        if not loc and ensure:
            loc = env['stock.location'].create({
                'name': name, 'usage': 'internal',
                'location_id': self._ck_warehouse(env).view_location_id.id})
        return loc

    def _ck_prep_products(self, env):
        return env['product.product'].search([('default_code', 'like', 'CK\\_%')])

    def _ck_stock(self, product, location):
        if not location:
            return 0.0        # nothing provisioned there yet => nothing on hand
        return product.with_context(location=location.id).qty_available

    def _ck_req_payload(self, r):
        return {
            'id': r.id, 'state': r.state, 'qty': r.qty,
            'branch_id': r.branch_id.id, 'branch': r.branch_id.name,
            'product_id': r.product_id.id,
            'product': r.product_id.display_name, 'code': r.product_id.default_code or '',
            'note': r.note or '',
            'mo': r.production_id.name if r.production_id else None,
            'picking': r.picking_id.name if r.picking_id else None,
            'requested_at': fields.Datetime.to_string(r.requested_at) if r.requested_at else None,
        }

    @http.route(f'{API_PREFIX}/ck/board', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def ck_board(self, **kw):
        """Central Kitchen board: prep stock (central + per branch) + live requests."""
        auth = self._authorize()
        if auth:
            return auth
        try:
            env = self._api_env()
            # READ ONLY: the board must not provision locations just to be looked at.
            central = self._ck_central(env, ensure=False)
            branches = env['pos.config'].search([], order='id asc')
            preps = self._ck_prep_products(env)
            stock = []
            for p in preps:
                stock.append({
                    'product_id': p.id, 'code': p.default_code or '', 'name': p.display_name,
                    'central': round(self._ck_stock(p, central), 1),
                    'branches': [{'branch_id': b.id, 'branch': b.name,
                                  'qty': round(self._ck_stock(p, self._ck_branch_location(env, b, ensure=False)), 1)}
                                 for b in branches],
                })
            reqs = env['mezze.ck.request'].search(
                ['|', ('state', 'not in', ('received', 'cancelled')),
                 ('requested_at', '>=', fields.Datetime.to_string(
                     fields.Datetime.now() - datetime.timedelta(hours=6)))])
            return {'ok': True,
                    'branches': [{'id': b.id, 'name': b.name} for b in branches],
                    'products': stock,
                    'requests': [self._ck_req_payload(r) for r in reqs]}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze ck_board failed")
            return self._json({'ok': False, 'error': 'ck_board_failed', 'message': str(exc)}, status=400)

    @http.route(f'{API_PREFIX}/ck/request', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*', readonly=False)
    def ck_request(self, branch_id=None, product_id=None, qty=1, note=None, **kw):
        auth = self._authorize()
        if auth:
            return auth
        try:
            env = self._api_env()
            if not branch_id or not product_id:
                return self._json({'ok': False, 'error': 'missing_fields'}, status=400)
            r = env['mezze.ck.request'].create({
                'branch_id': int(branch_id), 'product_id': int(product_id),
                'qty': float(qty), 'note': note or False, 'state': 'requested'})
            return {'ok': True, 'request': self._ck_req_payload(r)}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze ck_request failed")
            return self._json({'ok': False, 'error': 'ck_request_failed', 'message': str(exc)}, status=400)

    @http.route(f'{API_PREFIX}/ck/produce', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*', readonly=False)
    def ck_produce(self, request_id=None, **kw):
        """Fulfil production with a REAL manufacturing order at the Central
        Kitchen (create → confirm → mark done), yielding real central stock."""
        auth = self._authorize()
        if auth:
            return auth
        try:
            env = self._api_env()
            r = env['mezze.ck.request'].browse(int(request_id))
            if not r.exists():
                return self._json({'ok': False, 'error': 'not_found'}, status=404)
            central = self._ck_central(env)
            mo = env['mrp.production'].create({
                'product_id': r.product_id.id, 'product_qty': r.qty,
                'location_src_id': central.id, 'location_dest_id': central.id})
            mo.action_confirm()
            mo.qty_producing = r.qty
            mo.button_mark_done()
            r.write({'state': 'produced', 'production_id': mo.id})
            return {'ok': True, 'request': self._ck_req_payload(r),
                    'central_stock': round(self._ck_stock(r.product_id, central), 1)}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze ck_produce failed")
            return self._json({'ok': False, 'error': 'ck_produce_failed', 'message': str(exc)}, status=400)

    @http.route(f'{API_PREFIX}/ck/dispatch', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*', readonly=False)
    def ck_dispatch(self, request_id=None, **kw):
        """Ship to the branch with a REAL internal transfer (Central Kitchen →
        the branch's stock location), moving real stock between locations."""
        auth = self._authorize()
        if auth:
            return auth
        try:
            env = self._api_env()
            r = env['mezze.ck.request'].browse(int(request_id))
            if not r.exists():
                return self._json({'ok': False, 'error': 'not_found'}, status=404)
            central = self._ck_central(env)
            if self._ck_stock(r.product_id, central) < r.qty:
                return self._json({'ok': False, 'error': 'no_stock',
                                   'message': 'Produce it first'}, status=400)
            wh = self._ck_warehouse(env)
            dest = self._ck_branch_location(env, r.branch_id)
            pick = env['stock.picking'].create({
                'picking_type_id': wh.int_type_id.id,
                'location_id': central.id, 'location_dest_id': dest.id,
                'move_ids': [(0, 0, {'product_id': r.product_id.id, 'product_uom_qty': r.qty,
                                     'location_id': central.id, 'location_dest_id': dest.id})]})
            pick.action_confirm()
            pick.action_assign()
            for m in pick.move_ids:
                m.quantity = r.qty
            pick.button_validate()
            r.write({'state': 'dispatched', 'picking_id': pick.id})
            return {'ok': True, 'request': self._ck_req_payload(r),
                    'central_stock': round(self._ck_stock(r.product_id, central), 1),
                    'branch_stock': round(self._ck_stock(r.product_id, dest), 1)}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze ck_dispatch failed")
            return self._json({'ok': False, 'error': 'ck_dispatch_failed', 'message': str(exc)}, status=400)

    @http.route(f'{API_PREFIX}/ck/receive', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*', readonly=False)
    def ck_receive(self, request_id=None, **kw):
        auth = self._authorize()
        if auth:
            return auth
        try:
            env = self._api_env()
            r = env['mezze.ck.request'].browse(int(request_id))
            if not r.exists():
                return self._json({'ok': False, 'error': 'not_found'}, status=404)
            r.state = 'received'
            return {'ok': True, 'request': self._ck_req_payload(r)}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze ck_receive failed")
            return self._json({'ok': False, 'error': 'ck_receive_failed', 'message': str(exc)}, status=400)

    # ------------------------------------------------------------------
    # KDS — recent orders as kitchen tickets (read-only live view)
    # ------------------------------------------------------------------
    @http.route(f'{API_PREFIX}/orders/kds', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def orders_kds(self, limit=12, **kw):
        auth = self._authorize()
        if auth:
            return auth
        try:
            env = self._api_env()
            has_table = 'table_id' in env['pos.order']._fields
            # kitchen sees FIRED work: draft (fired) orders + recently paid
            orders = env['pos.order'].search(
                [('state', 'in', ('draft', 'paid', 'done', 'invoiced'))],
                order='date_order desc', limit=int(limit or 12))
            out = []
            for o in orders:
                tbl = ''
                if has_table and o.table_id:
                    t = o.table_id
                    tbl = str(t.table_number if 'table_number' in t._fields else t.id)
                # what has actually been fired: the mezze_fired snapshot for
                # draft orders; every line for finalized (café) orders.
                if o.state == 'draft':
                    snap = json.loads(o.mezze_fired or '{}')
                    fired = [(env['product.product'].browse(int(pid)), qty)
                             for pid, qty in snap.items() if qty > 0]
                else:
                    fired = [(l.product_id, l.qty) for l in o.lines if l.qty > 0]
                if not fired:
                    continue
                # route each item to its prep station
                stations = {}
                for product, qty in fired:
                    st = self._station_of(product)
                    stations.setdefault(st, []).append({'qty': qty, 'name': product.display_name})
                out.append({
                    'id': o.id, 'ref': o.pos_reference, 'table': tbl,
                    'server': o.user_id.name or '',
                    'state': o.state,
                    'date_order': fields.Datetime.to_string(o.date_order),
                    'stations': [{'station': s, 'items': its} for s, its in stations.items()],
                    'lines': [it for its in stations.values() for it in its],
                })
            return {'ok': True, 'tickets': out}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze orders_kds failed")
            return self._json({'ok': False, 'error': 'kds_failed', 'message': str(exc)}, status=400)

    # ------------------------------------------------------------------
    # KDS state-machine board — real mezze.kds.ticket records
    # ------------------------------------------------------------------
    @http.route(f'{API_PREFIX}/kds/state', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def kds_state(self, config_id=None, done_minutes=10, **kw):
        """Full KDS board snapshot for a config.

        Returns every live ticket (fired/accepted/preparing/ready) plus tickets
        that went served/cancel within the last ``done_minutes`` (so the board
        shows what just cleared). Also returns ``last_bus_id`` so the client can
        seed its websocket/poll cursor and never miss an event between snapshot
        and subscribe. Waiter tablets read the same feed, filtering state==ready.
        """
        auth = self._authorize()
        if auth:
            return auth
        try:
            env = self._api_env()
            Ticket = env['mezze.kds.ticket']
            domain = ['|',
                      ('state', 'in', ('fired', 'accepted', 'preparing', 'ready'))]
            cutoff = fields.Datetime.now() - datetime.timedelta(minutes=int(done_minutes or 10))
            domain += ['&', ('state', 'in', ('served', 'cancel')),
                       ('fired_at', '>=', fields.Datetime.to_string(cutoff))]
            if config_id:
                domain = [('config_id', '=', int(config_id))] + domain
            tickets = Ticket.search(domain)
            channel_cfg = int(config_id) if config_id else 0
            return {
                'ok': True,
                'last_bus_id': env['bus.bus'].sudo()._bus_last_id(),
                'kds_channel': 'mezze_kds_%s' % channel_cfg,
                'waiter_channel': 'mezze_waiter_%s' % channel_cfg,
                # one query for every ticket's car, instead of one per ticket
                'tickets': [t._payload() for t in
                            tickets.with_context(mezze_dt_map=tickets._drivethru_map())],
            }
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze kds_state failed")
            return self._json({'ok': False, 'error': 'kds_state_failed', 'message': str(exc)}, status=400)

    # ------------------------------------------------------------------
    # BDS / Coffee queue — the barista's beverage lane + pickup board
    # ------------------------------------------------------------------
    @http.route(f'{API_PREFIX}/bds/queue', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def bds_queue(self, config_id=None, stations=None, **kw):
        """Barista beverage queue + customer pickup board.

        ``queue`` = live beverage-station tickets (Barista/Bar by default) in
        FIFO order — the barista makes them top-to-bottom. ``pickup`` groups the
        live tickets by order and reports each order's ``tracking`` number as
        ``ready`` (every beverage ticket ready) or ``preparing`` — that's the
        customer-facing "now serving / ready for pickup" display.
        """
        auth = self._authorize()
        if auth:
            return auth
        try:
            env = self._api_env()
            Ticket = env['mezze.kds.ticket']
            bev = list(stations) if stations else list(self._BEVERAGE_STATIONS)
            domain = [('station', 'in', bev),
                      ('state', 'in', ('fired', 'accepted', 'preparing', 'ready'))]
            if config_id:
                domain = [('config_id', '=', int(config_id))] + domain
            tickets = Ticket.search(domain, order='fired_at asc, id asc')
            by_order = {}
            for t in tickets:
                o = t.pos_order_id
                e = by_order.setdefault(o.id, {
                    'order_id': o.id,
                    'tracking': o.tracking_number or o.pos_reference or str(o.id),
                    'table': next((tk.table_label for tk in tickets
                                   if tk.pos_order_id.id == o.id and tk.table_label), None),
                    'states': []})
                e['states'].append(t.state)
            pickup = [{
                'order_id': e['order_id'], 'tracking': e['tracking'], 'table': e['table'],
                'state': 'ready' if all(s == 'ready' for s in e['states']) else 'preparing',
            } for e in by_order.values()]
            channel_cfg = int(config_id) if config_id else 0
            return {
                'ok': True,
                'last_bus_id': env['bus.bus'].sudo()._bus_last_id(),
                'kds_channel': 'mezze_kds_%s' % channel_cfg,
                'waiter_channel': 'mezze_waiter_%s' % channel_cfg,
                'queue': [t._payload() for t in tickets],
                'pickup': pickup,
            }
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze bds_queue failed")
            return self._json({'ok': False, 'error': 'bds_queue_failed', 'message': str(exc)}, status=400)

    @http.route(f'{API_PREFIX}/kds/transition', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*', readonly=False)
    def kds_transition(self, ticket_id=None, action=None, **kw):
        """Advance / recall one KDS ticket. Persists + broadcasts on the bus.

        ``action`` in accept|preparing|ready|served|cancel|recall. The move is
        applied under a row lock so two KDS screens bumping the same ticket at
        once can't double-advance it.
        """
        auth = self._authorize()
        if auth:
            return auth
        ACTIONS = {'accept': 'accepted', 'preparing': 'preparing', 'prepare': 'preparing',
                   'ready': 'ready', 'served': 'served', 'serve': 'served', 'cancel': 'cancel'}
        try:
            env = self._api_env()
            ticket = env['mezze.kds.ticket'].browse(int(ticket_id))
            if not ticket.exists():
                return self._json({'ok': False, 'error': 'not_found'}, status=404)
            if action == 'recall':
                changed, reason = ticket.action_recall()
            elif action in ACTIONS:
                changed, reason = ticket._set_state(ACTIONS[action])
            else:
                return self._json({'ok': False, 'error': 'bad_action', 'message': str(action)}, status=400)
            return {'ok': True, 'changed': changed, 'reason': reason,
                    'ticket': ticket._payload()}
        except Exception as exc:  # noqa: BLE001
            # Two KDS screens bumping the same ticket → let PG concurrency errors
            # retry rather than swallowing them (the FOR UPDATE lock serializes).
            _reraise_if_retryable(exc)
            _logger.exception("Mezze kds_transition failed")
            return self._json({'ok': False, 'error': 'transition_failed', 'message': str(exc)}, status=400)

    @http.route(f'{API_PREFIX}/bus/poll', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def bus_poll(self, channels=None, last=0, **kw):
        """Poll-reconcile fallback: read the REAL Odoo bus since ``last``.

        The frontend prefers a live ``/websocket`` push, but polls this every few
        seconds as a safety net so a dropped socket never leaves the board stale.
        Consumes the same ``bus.bus`` notifications the websocket delivers.
        """
        auth = self._authorize()
        if auth:
            return auth
        try:
            env = self._api_env()
            chans = channels or []
            notifs = env['bus.bus'].sudo()._poll(chans, last=int(last or 0))
            max_id = max([n['id'] for n in notifs], default=int(last or 0))
            return {'ok': True, 'last': max_id, 'notifications': notifs}
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Mezze bus_poll failed")
            return self._json({'ok': False, 'error': 'poll_failed', 'message': str(exc)}, status=400)
