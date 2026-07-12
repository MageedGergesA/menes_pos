# Part of the Mezze POS platform. See LICENSE (LGPL-3).
"""Offline ⇄ cloud sync endpoints (SCAFFOLD).

See ``docs/SYNC.md`` for the full design. These endpoints are a working
skeleton:

  * ``/mezze/sync/v1/register`` — mint/return a terminal identity + token
  * ``/mezze/sync/v1/push``     — ingest a terminal's outbox batch, ack up_to_seq
  * ``/mezze/sync/v1/pull``     — return config/state changed since a watermark

``register`` is functional. ``push`` dedupes + acks idempotently by outbox
``seq`` but does NOT yet APPLY events (the upsert-by-uuid + commutative
inventory/loyalty delta-merge from SYNC.md) — that reconcile is marked ``TODO``.
``pull`` returns the response shape with an empty change set; the per-model
``write_date > watermark`` query is ``TODO``.
"""
import json
import logging
import secrets

from odoo import SUPERUSER_ID, fields, http
from odoo.http import request

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
        # Scaffold: bind to superuser. Production should reuse the bridge's
        # ``_api_env`` (a real POS user) to avoid SUPERUSER edge cases.
        return request.env(user=SUPERUSER_ID)

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
        """Ingest an ordered outbox batch. Exactly-once by (terminal, seq):
        events at or below ``last_acked_seq`` are ignored; the rest are applied
        in ``seq`` order and the cursor advances. Idempotent — safe to replay."""
        env = self._env()
        term = self._terminal(env, terminal_id, token)
        if not term:
            return self._json({'ok': False, 'error': 'unauthorized_terminal'}, status=401)

        events = sorted(events or [], key=lambda e: e.get('seq', 0))
        acked = term.last_acked_seq
        applied = 0
        for ev in events:
            seq = int(ev.get('seq', 0))
            if seq <= term.last_acked_seq:
                continue  # already ingested — dedupe
            # TODO(sync): APPLY the event by model. Sales -> upsert pos.order by
            # res_uuid (reuse orders/sync); inventory/loyalty -> commutative
            # delta-merge (see docs/SYNC.md §"three conflict cases"). For now we
            # only advance the cursor so the transport/idempotency layer is live.
            acked = max(acked, seq)
            applied += 1

        if acked > term.last_acked_seq:
            term.last_acked_seq = acked
        term.last_seen = fields.Datetime.now()
        return {'ok': True, 'up_to_seq': acked, 'applied': applied,
                'applied_events': False}  # applied_events flips true once reconcile lands

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
