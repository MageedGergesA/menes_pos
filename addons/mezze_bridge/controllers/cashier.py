# Part of the Mezze POS platform. See LICENSE (LGPL-3).
"""S2C-1 — production cashier page controller.

Serves the standalone Owl cashier app at ``/mezze/pos``. Authentication is
Odoo's own session (``auth='user'``): an unauthenticated visitor is redirected
to ``/web/login`` — that is the real *authentication-required* state, never demo
data. For the JSON API (``/mezze/api/v1/*``) the page carries a freshly minted,
least-privilege PER-TERMINAL token (``mezze.terminal``, ``role='terminal'`` →
holds ``orders.pay``, branch-scoped). No shared-admin token is exposed to the
browser and no new bearer architecture is introduced.
"""
import json
import re

import markupsafe

from odoo import http
from odoo.http import request

from .main import API_PREFIX
from .register_instance import mint_for_instance, resolve_rid, stamp_rid


class MezzeCashierUI(http.Controller):

    def _resolve_config(self, env):
        """Authoritative branch (pos.config) for this page: explicit ?config_id=,
        else the configured default branch, else the first config."""
        Config = env['pos.config'].sudo()
        raw = request.params.get('config_id')
        if raw and str(raw).isdigit():
            cfg = Config.browse(int(raw))
            if cfg.exists():
                return cfg
        default = env['ir.config_parameter'].sudo().get_param('mezze_bridge.default_branch_id')
        if default and str(default).isdigit():
            cfg = Config.browse(int(default))
            if cfg.exists():
                return cfg
        return Config.search([], limit=1)

    def _mint_terminal_token(self, env, config, rid):
        """Hand THIS register instance a fresh bearer token, returning the plaintext
        ONCE for the page. The server keeps only a non-reversible fingerprint.
        role='terminal' ⇒ least privilege, branch-scoped.

        RC6 DEFECT-01: the terminal is keyed on (config, register instance), not on
        the config alone, so a second browser opening the Register no longer evicts
        the first. See ``register_instance.py`` for the locator contract.
        """
        return mint_for_instance(env, config, rid)

    def _resolve_table_context(self, env, config):
        """R2A CP5 — resolve ?table_id= into a validated, branch-scoped restaurant
        context for a table-bound Register. Returns one of:
          * None                              → no table_id given (counter mode)
          * {'error': 'invalid_table'}        → unknown / inactive / cross-branch table
          * {id, name, floor, order_uuid, guests}
        The server stays authoritative: the open draft order (if any) is resolved HERE
        from pos.order, so the browser never invents which order sits on a table. No
        order/table state is created or mutated by opening the Register."""
        raw = request.params.get('table_id')
        if not raw or not str(raw).isdigit():
            return None
        if 'restaurant.table' not in env:
            return {'error': 'invalid_table'}
        Table = env['restaurant.table'].sudo()
        table = Table.with_context(active_test=False).browse(int(raw))
        # existence + active + belongs to a floor served by THIS branch (config) —
        # a stale or cross-branch table id never resolves (no unauthorized exposure).
        if (not table.exists() or not table.active or not table.floor_id
                or config.id not in table.floor_id.pos_config_ids.ids):
            return {'error': 'invalid_table'}
        name_field = 'table_number' if 'table_number' in Table._fields else 'name'
        ctx = {
            'id': table.id, 'name': str(table[name_field]),
            'floor': table.floor_id.name, 'order_uuid': None, 'guests': 0,
        }
        # the single OPEN (draft) order sitting on this table for this branch — the
        # authoritative order to resume (no new order is created here).
        draft = env['pos.order'].sudo().search(
            [('table_id', '=', table.id), ('state', '=', 'draft'),
             ('config_id', '=', config.id)], order='date_order asc', limit=1)
        if draft:
            ctx['order_uuid'] = draft.uuid
            if 'customer_count' in draft._fields:
                ctx['guests'] = draft.customer_count or 0
        return ctx

    @http.route('/mezze/pos', type='http', auth='user', methods=['GET'],
                website=False, readonly=False)
    def cashier(self, **kw):
        env = request.env
        config = self._resolve_config(env)
        user = env.user
        rid, rid_is_new = resolve_rid(request)
        lang = (user.lang or env.context.get('lang') or 'en_US')
        if not config:
            # No POS configured: render the app in an explicit error state (never demo).
            boot = {'ok': False, 'error': 'no_pos_config', 'api_prefix': API_PREFIX,
                    'user': {'id': user.id, 'name': user.name}, 'lang': lang}
        else:
            token, _term = self._mint_terminal_token(env, config, rid)
            currency = config.currency_id
            boot = {
                'ok': True,
                'api_prefix': API_PREFIX,
                'token': token,
                'config_id': config.id,
                'user': {'id': user.id, 'name': user.name},
                'branch': {'id': config.id, 'name': config.name},
                'company_id': config.company_id.id,
                'currency': {
                    'id': currency.id, 'name': currency.name,
                    'symbol': currency.symbol or currency.name,
                    'position': currency.position or 'after',
                    'decimals': currency.decimal_places,
                },
                'lang': lang,
            }
            # R2A CP5: table-bound Register context (None in counter mode).
            boot['table'] = self._resolve_table_context(env, config)
        # Safe embed inside <script type="application/json">: escape '<' so a name
        # containing '</script>' cannot break out. Values are server-sourced.
        payload = json.dumps(boot).replace('<', '\\u003c')
        # Odoo's NATIVE debug state (set by the framework from the ?debug= param /
        # session). Sanitised to a safe token set so it can be emitted into an
        # inline <script> without escaping concerns; module_loader.js then
        # reconciles it against the URL. Drives the dev-only debug handle.
        raw_debug = getattr(request.session, 'debug', '') or ''
        mz_debug = re.sub(r'[^a-z0-9,]', '', str(raw_debug).lower())
        response = request.render('mezze_bridge.cashier_page', {
            'boot_json': markupsafe.Markup(payload),
            'mz_lang': lang,
            'mz_debug': mz_debug,
        })
        return stamp_rid(response, rid, rid_is_new)
