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
import secrets

import markupsafe

from odoo import http
from odoo.http import request

from .main import API_PREFIX


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

    def _mint_terminal_token(self, env, config, user):
        """Find-or-create a dedicated 'Cashier Web' terminal for this branch and
        set a fresh bearer token on it, returning the plaintext ONCE for the page.
        The server keeps only a non-reversible fingerprint (or degraded plaintext
        in dev without a master key). role='terminal' ⇒ least privilege."""
        Term = env['mezze.terminal'].sudo()
        identifier = 'cashier-web-%s' % config.id
        term = Term.with_context(active_test=False).search(
            [('identifier', '=', identifier)], limit=1)
        token = secrets.token_urlsafe(24)
        vals = {'token': token, 'branch_id': config.id, 'active': True, 'role': 'terminal'}
        if term:
            term.write(vals)
        else:
            term = Term.create(dict(vals, name='Cashier Web — %s' % config.name,
                                    identifier=identifier))
        return token, term

    @http.route('/mezze/pos', type='http', auth='user', methods=['GET'],
                website=False, readonly=False)
    def cashier(self, **kw):
        env = request.env
        config = self._resolve_config(env)
        user = env.user
        lang = (user.lang or env.context.get('lang') or 'en_US')
        if not config:
            # No POS configured: render the app in an explicit error state (never demo).
            boot = {'ok': False, 'error': 'no_pos_config', 'api_prefix': API_PREFIX,
                    'user': {'id': user.id, 'name': user.name}, 'lang': lang}
        else:
            token, _term = self._mint_terminal_token(env, config, user)
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
        # Safe embed inside <script type="application/json">: escape '<' so a name
        # containing '</script>' cannot break out. Values are server-sourced.
        payload = json.dumps(boot).replace('<', '\\u003c')
        # Odoo's NATIVE debug state (set by the framework from the ?debug= param /
        # session). Sanitised to a safe token set so it can be emitted into an
        # inline <script> without escaping concerns; module_loader.js then
        # reconciles it against the URL. Drives the dev-only debug handle.
        raw_debug = getattr(request.session, 'debug', '') or ''
        mz_debug = re.sub(r'[^a-z0-9,]', '', str(raw_debug).lower())
        return request.render('mezze_bridge.cashier_page', {
            'boot_json': markupsafe.Markup(payload),
            'mz_lang': lang,
            'mz_debug': mz_debug,
        })
