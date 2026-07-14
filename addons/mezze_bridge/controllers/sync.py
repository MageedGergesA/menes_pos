# Part of the Mezze POS platform. See LICENSE (LGPL-3).
"""Offline ⇄ cloud sync endpoints (SCAFFOLD).

See ``docs/SYNC.md`` for the full design. These endpoints are a working
skeleton:

  * ``/mezze/sync/v1/register`` — mint/return a terminal identity + token
  * ``/mezze/sync/v1/push``     — ingest a terminal's outbox batch, ack up_to_seq
  * ``/mezze/sync/v1/pull``     — return config/state changed since a watermark

``register`` + ``push`` are LIVE: ``push`` applies each outbox event (sales
upsert-by-uuid, commutative stock/loyalty deltas) exactly-once, dead-lettering
poison events — see the apply dispatcher below and ``docs/SYNC.md``. ``pull``
(config-down watermark query) is still the skeleton. ``reconcile`` is the
staff-facing read of the ``mezze.sync.applied`` ledger (terminal health +
flagged/failed events) that backs the manager reconcile view.
"""
import datetime
import json
import logging
import secrets

from odoo import SUPERUSER_ID, fields, http
from odoo.http import request

from .main import MezzeBridgeController, _reraise_if_retryable

_logger = logging.getLogger(__name__)

SYNC_PREFIX = '/mezze/sync/v1'
TOKEN_PARAM = 'mezze_bridge.api_token'

# Config models a terminal mirrors down from the cloud (pull watermarks).
PULL_MODELS = (
    'product.product', 'account.tax', 'pos.category',
    'restaurant.floor', 'restaurant.table', 'res.partner',
    'loyalty.program', 'loyalty.reward',
)


class MezzeSyncController(http.Controller):

    # reuse the main bridge's order-building / session / loyalty helpers
    _bridge = MezzeBridgeController()

    # -- helpers (kept minimal; mirror MezzeBridgeController semantics) --------
    def _json(self, payload, status=200):
        return request.make_json_response(payload, status=status)

    def _auth(self):
        """Validate the shared admin token (register/bootstrap). Per-terminal
        token auth on push/pull is checked against ``mezze.terminal.token``."""
        expected = request.env['ir.config_parameter'].sudo().get_param(TOKEN_PARAM)
        provided = (request.httprequest.headers.get('X-Mezze-Token')
                    or request.params.get('token'))
        if not expected:
            return self._json({'ok': False, 'error': 'server_token_unset'}, status=503)
        if not provided or provided != expected:
            return self._json({'ok': False, 'error': 'unauthorized'}, status=401)
        return None

    def _env(self):
        # Bind to the configured API user (a real POS user), NOT SUPERUSER, so
        # record rules apply. Mirrors MezzeBridgeController._api_env.
        su = request.env(user=SUPERUSER_ID)
        uid_param = su['ir.config_parameter'].get_param('mezze_bridge.api_user_id')
        if uid_param and str(uid_param).isdigit():
            uid = int(uid_param)
        else:
            api_user = (su.ref('base.user_admin', raise_if_not_found=False)
                        or su['res.users'].search([('share', '=', False), ('active', '=', True)], limit=1))
            uid = api_user.id
        return request.env(user=uid)

    def _terminal(self, env, terminal_id, token):
        """Resolve + authenticate a terminal by its own sync token."""
        term = env['mezze.terminal'].search(
            [('identifier', '=', terminal_id), ('active', '=', True)], limit=1)
        if not term or not token or term.token != token:
            return None
        return term

    # -- register --------------------------------------------------------------
    @http.route(f'{SYNC_PREFIX}/register', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def register(self, name=None, identifier=None, branch_id=None, **kw):
        """Mint (or return) a terminal identity + per-terminal sync token."""
        auth = self._auth()
        if auth:
            return auth
        env = self._env()
        Term = env['mezze.terminal']
        term = None
        if identifier:
            term = Term.search([('identifier', '=', identifier)], limit=1)
        if not term:
            ident = identifier or ('term-' + secrets.token_urlsafe(9))
            term = Term.create({
                'name': name or ident,
                'identifier': ident,
                'token': secrets.token_urlsafe(24),
                'branch_id': int(branch_id) if branch_id else False,
            })
        term.last_seen = fields.Datetime.now()
        return {
            'ok': True,
            'terminal_id': term.identifier,
            'token': term.token,
            'branch_id': term.branch_id.id or None,
            'last_acked_seq': term.last_acked_seq,
        }

    # -- push (terminal -> cloud) ---------------------------------------------
    @http.route(f'{SYNC_PREFIX}/push', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def push(self, terminal_id=None, token=None, events=None, **kw):
        """Ingest and APPLY an ordered outbox batch. Exactly-once by two guards:
        the ``last_acked_seq`` cursor (events at/below it are skipped) AND a
        per-(terminal, res_uuid) ledger (`mezze.sync.applied`) so a replayed
        event after a partial batch is recognised. Each event applies inside its
        own savepoint: a poison event is rolled back, dead-lettered, and the
        cursor advances PAST it so one bad event never blocks the terminal.
        Postgres concurrency errors abort the whole batch so the request retries.
        Idempotent — safe to replay the same batch."""
        env = self._env()
        term = self._terminal(env, terminal_id, token)
        if not term:
            return self._json({'ok': False, 'error': 'unauthorized_terminal'}, status=401)

        events = sorted(events or [], key=lambda e: int(e.get('seq', 0)))
        Applied = env['mezze.sync.applied'].sudo()
        acked = term.last_acked_seq
        applied = skipped = flagged = failed = 0
        for ev in events:
            seq = int(ev.get('seq', 0))
            if seq <= term.last_acked_seq:
                continue  # already ingested (cursor dedupe)
            res_uuid = ev.get('res_uuid')
            if not res_uuid:
                failed += 1
                Applied.create({'terminal_id': term.id, 'seq': seq, 'res_uuid': '(none)',
                                'model': ev.get('model'), 'op': ev.get('op'), 'state': 'failed',
                                'error': 'missing res_uuid', 'payload': json.dumps(ev)[:4000]})
                acked = max(acked, seq)
                continue
            if Applied.search_count([('terminal_id', '=', term.id), ('res_uuid', '=', res_uuid)]):
                skipped += 1  # already applied in an earlier (partial) batch
                acked = max(acked, seq)
                continue
            try:
                with env.cr.savepoint():
                    result = self._apply_event(env, term, ev)
            except Exception as exc:  # noqa: BLE001
                _reraise_if_retryable(exc)  # PG concurrency -> abort batch, request retries clean
                _logger.exception("Mezze sync apply failed: %s / %s", ev.get('model'), res_uuid)
                failed += 1
                Applied.create({'terminal_id': term.id, 'seq': seq, 'res_uuid': res_uuid,
                                'model': ev.get('model'), 'op': ev.get('op'), 'state': 'failed',
                                'error': str(exc)[:2000], 'payload': self._payload_text(ev)})
                acked = max(acked, seq)
                continue
            st = result.get('state', 'applied')
            if st == 'skipped':
                skipped += 1
            elif st == 'flagged':
                flagged += 1
                applied += 1
            else:
                applied += 1
            Applied.create({'terminal_id': term.id, 'seq': seq, 'res_uuid': res_uuid,
                            'model': ev.get('model'), 'op': ev.get('op'), 'state': st,
                            'note': result.get('note'), 'pos_order_id': result.get('pos_order_id')})
            acked = max(acked, seq)

        if acked > term.last_acked_seq:
            term.last_acked_seq = acked
        term.last_seen = fields.Datetime.now()
        return {'ok': True, 'up_to_seq': acked, 'applied': applied, 'skipped': skipped,
                'flagged': flagged, 'failed': failed, 'applied_events': True}

    # -- apply dispatcher ------------------------------------------------------
    def _payload_text(self, ev):
        p = ev.get('payload')
        return (p if isinstance(p, str) else json.dumps(p))[:4000]

    def _ev_payload(self, ev):
        p = ev.get('payload')
        if isinstance(p, str):
            return json.loads(p or '{}')
        return p or {}

    def _apply_event(self, env, term, ev):
        """Route an outbox event to its handler. Returns a dict with at least
        ``state`` ('applied'|'skipped'|'flagged'); may carry ``note`` /
        ``pos_order_id``. Raising means dead-letter (poison event)."""
        model = ev.get('model')
        payload = self._ev_payload(ev)
        if model == 'pos.order':
            return self._apply_sale(env, term, ev.get('res_uuid'), payload)
        if model in ('stock', 'stock.delta', 'mezze.stock.delta'):
            return self._apply_stock_delta(env, term, payload)
        if model in ('loyalty', 'loyalty.history'):
            return self._apply_loyalty_txn(env, term, payload)
        raise ValueError("unknown sync model %r" % model)

    def _term_config(self, env, term):
        config = term.branch_id or env['pos.config'].search([], limit=1)
        if not config:
            raise ValueError("no pos.config for terminal %s" % term.identifier)
        env2 = env(context=dict(env.context, allowed_company_ids=[config.company_id.id],
                                company_id=config.company_id.id))
        return env2, config.with_env(env2)

    def _apply_sale(self, env, term, res_uuid, payload):
        """Upsert an offline sale by uuid into the branch's cloud session. No
        loyalty earn here — loyalty rides its own transaction event so it isn't
        double-counted. Idempotent: an existing uuid short-circuits to skipped."""
        Order = env['pos.order']
        existing = Order.search([('uuid', '=', res_uuid)], limit=1)
        if existing:
            return {'state': 'skipped', 'pos_order_id': existing.id}
        env, config = self._term_config(env, term)
        session = self._bridge._ensure_open_session(env, config)
        partner = (env['res.partner'].browse(int(payload['partner_id']))
                   if payload.get('partner_id') else env['res.partner'])
        order_lines, base, incl = self._bridge._build_lines(env, config, partner, payload.get('lines') or [])
        plist = payload.get('payments') or []
        if plist:
            pay_ids = [(0, 0, {'amount': float(p['amount']), 'name': fields.Datetime.now(),
                               'payment_method_id': int(p['payment_method_id'])}) for p in plist]
        else:
            pay_ids = [(0, 0, {'amount': incl, 'name': fields.Datetime.now(),
                               'payment_method_id': config.payment_method_ids[:1].id})]
        order_dict = {
            'uuid': res_uuid, 'session_id': session.id, 'company_id': config.company_id.id,
            'user_id': env.uid, 'partner_id': partner.id or False,
            'pricelist_id': config.pricelist_id.id or False, 'name': 'Mezze %s' % res_uuid,
            'date_order': payload.get('date_order') or fields.Datetime.to_string(fields.Datetime.now()),
            'lines': order_lines, 'payment_ids': pay_ids,
            'amount_tax': incl - base, 'amount_total': incl, 'amount_paid': incl,
            'amount_return': 0.0, 'last_order_preparation_change': '{}', 'to_invoice': False,
        }
        env['pos.order'].sync_from_ui([order_dict])
        order = Order.search([('uuid', '=', res_uuid)], limit=1)
        if not order:
            raise ValueError("offline sale %s did not persist" % res_uuid)
        return {'state': 'applied', 'pos_order_id': order.id}

    def _branch_stock_location(self, env, config):
        wh = env['stock.warehouse'].search([('company_id', '=', config.company_id.id)], limit=1)
        return wh.lot_stock_id if wh else env['stock.location']

    def _apply_stock_delta(self, env, term, payload):
        """Commutative inventory delta (never absolute on-hand). Applying all
        terminals' deltas converges to true global stock. A resulting negative
        quant is real (two branches sold the last unit offline) — flag it as a
        business event rather than reject it."""
        env, config = self._term_config(env, term)
        product = env['product.product'].browse(int(payload['product_id']))
        if not product.exists():
            raise ValueError("unknown product_id %s" % payload.get('product_id'))
        loc = (env['stock.location'].browse(int(payload['location_id']))
               if payload.get('location_id') else self._branch_stock_location(env, config))
        if not loc:
            raise ValueError("no stock location for branch")
        delta = float(payload.get('delta', 0.0))
        env['stock.quant'].sudo()._update_available_quantity(product, loc, delta)
        onhand = sum(env['stock.quant'].sudo().search(
            [('product_id', '=', product.id), ('location_id', '=', loc.id)]).mapped('quantity'))
        if onhand < 0:
            return {'state': 'flagged', 'note': 'negative_stock'}
        return {'state': 'applied'}

    def _apply_loyalty_txn(self, env, term, payload):
        """Commutative loyalty transaction (signed points), never the balance.
        Earn is always safe; an offline double-redeem can drive points negative —
        flag it for claw-back/comp rather than reject."""
        partner = (env['res.partner'].browse(int(payload['partner_id']))
                   if payload.get('partner_id') else env['res.partner'])
        if not partner or not partner.exists():
            raise ValueError("unknown partner for loyalty txn")
        prog = self._bridge._loyalty_program(env)
        if not prog:
            raise ValueError("no loyalty programme configured")
        card = self._bridge._loyalty_card(env, partner)
        points = float(payload.get('points', 0.0))
        env['loyalty.history'].sudo().create({
            'card_id': card.id, 'issued': points if points > 0 else 0.0,
            'used': -points if points < 0 else 0.0,
            'description': payload.get('description') or ('Mezze sync %s' % (payload.get('order_uuid') or '')),
        })
        card.sudo().write({'points': card.points + points})
        if card.points < 0:
            return {'state': 'flagged', 'note': 'negative_points'}
        return {'state': 'applied'}

    # -- pull (cloud -> terminal) ---------------------------------------------
    @http.route(f'{SYNC_PREFIX}/pull', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def pull(self, terminal_id=None, token=None, since=None, **kw):
        """Return config/state changed since the terminal's per-model watermark.
        ``since`` maps model -> ISO datetime. Response echoes new watermarks the
        terminal should persist. Query is ``TODO``; shape is stable."""
        env = self._env()
        term = self._terminal(env, terminal_id, token)
        if not term:
            return self._json({'ok': False, 'error': 'unauthorized_terminal'}, status=401)

        since = since or {}
        changes = {}
        watermarks = {}
        for model in PULL_MODELS:
            # TODO(sync): search_read(model, [('write_date','>',since[model])])
            # scoped to the terminal's branch, and return the delta rows here.
            changes[model] = []
            watermarks[model] = since.get(model)

        term.last_seen = fields.Datetime.now()
        return {'ok': True, 'changes': changes, 'watermarks': watermarks,
                'complete': True}

    # -- reconcile (staff-facing oversight of the apply ledger) ----------------
    @http.route(f'{SYNC_PREFIX}/reconcile', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def reconcile(self, config_id=None, online_minutes=5, limit=60, **kw):
        """Manager reconcile view: terminal health + the exceptions from the
        cloud apply ledger (`mezze.sync.applied`). Read-only. Auth: shared token
        (staff), NOT a terminal token."""
        auth = self._bridge._authenticate()
        if auth:
            return auth
        env = self._env()
        now = fields.Datetime.now()
        cutoff = now - datetime.timedelta(minutes=int(online_minutes or 5))
        tdom = [('branch_id', '=', int(config_id))] if config_id else []
        terminals = []
        for tm in env['mezze.terminal'].search(tdom, order='last_seen desc'):
            failed = env['mezze.sync.applied'].search_count(
                [('terminal_id', '=', tm.id), ('state', '=', 'failed')])
            terminals.append({
                'id': tm.id, 'name': tm.name, 'identifier': tm.identifier,
                'branch': tm.branch_id.display_name or '—',
                'last_seen': fields.Datetime.to_string(tm.last_seen) if tm.last_seen else None,
                'minutes': int((now - tm.last_seen).total_seconds() / 60) if tm.last_seen else None,
                'online': bool(tm.last_seen and tm.last_seen >= cutoff),
                'acked_seq': tm.last_acked_seq, 'failed': failed,
            })
        edom = [('state', 'in', ('flagged', 'failed'))]
        if config_id:
            edom.append(('config_id', '=', int(config_id)))
        events = []
        for a in env['mezze.sync.applied'].search(edom, limit=int(limit or 60)):
            events.append({
                'id': a.id, 'terminal': a.terminal_id.name, 'model': a.model,
                'op': a.op, 'res_uuid': a.res_uuid, 'state': a.state,
                'note': a.note or None, 'error': (a.error or None),
                'order_id': a.pos_order_id.id or None,
                'seq': a.seq,
                'at': fields.Datetime.to_string(a.create_date) if a.create_date else None,
            })
        cdom = [('config_id', '=', int(config_id))] if config_id else []
        counts = {
            'terminals': len(terminals),
            'online': sum(1 for t in terminals if t['online']),
            'flagged': env['mezze.sync.applied'].search_count([('state', '=', 'flagged')] + cdom),
            'failed': env['mezze.sync.applied'].search_count([('state', '=', 'failed')] + cdom),
        }
        return {'ok': True, 'config_id': config_id, 'summary': counts,
                'terminals': terminals, 'events': events}
