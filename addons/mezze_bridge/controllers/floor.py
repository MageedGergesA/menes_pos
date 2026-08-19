# Part of the Mezze POS platform. See LICENSE (LGPL-3).
"""R2A — production Floor / Tables page controller.

Serves the standalone Owl Floor app at ``/mezze/floor``. It is the SAME Mezze
Restaurant POS as ``/mezze/pos`` (shared shell/theme/tokens/boot pattern, branch
context, manager-approval UX) — only the workspace differs. Authentication is
Odoo's own session (``auth='user'``): an unauthenticated visitor is redirected to
``/web/login`` — the real *authentication-required* state, never demo data.

Like the cashier, the page carries a freshly minted, least-privilege PER-TERMINAL
token (``mezze.terminal``, ``role='terminal'``, branch-scoped). It reuses the
cashier's own ``cashier-web-<cfg>`` terminal so the Floor and the Register share
one least-privilege identity — NO broader/host token is minted, and the JSON API
authority (``_authorize`` / ``_security_gate``) is untouched. Sensitive floor
operations (transfer / merge / seat) go through the EXISTING manager-approval
flow, never a wider grant.

Helper names are floor-scoped (``_floor_*``) so they can never shadow the cashier
/ kds / api controllers' private helpers in the shared controller registry.
"""
import json
import re

import markupsafe

from odoo import http
from odoo.http import request

from .main import API_PREFIX
from .register_instance import mint_for_instance, resolve_rid, stamp_rid


class MezzeFloorUI(http.Controller):

    def _floor_resolve_config(self, env):
        """Authoritative branch (pos.config) for this page: explicit ?config_id=,
        else the configured default branch, else the first config. Mirrors the
        cashier so Floor and Register resolve the SAME branch context."""
        # WS-2: a station's branch is SERVER truth and outranks the URL. An
        # ordinary browser gets an empty recordset and falls through to the
        # usual ?config_id= / default-branch resolution below.
        bound = env['mezze.station.surface.session'].sudo().branch_for_request()
        if bound:
            return bound
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

    def _floor_mint_token(self, env, config, rid):
        """Hand THIS browsing context's terminal a fresh bearer token, returning the
        plaintext ONCE for the page. role='terminal' => least privilege - the same
        identity the Register on this client uses, so the Floor and the Register still
        share one principal per client and no broader principal is introduced.

        RC6 DEFECT-01: keyed on (config, register instance) rather than the config
        alone, so opening the Floor no longer evicts another device's Register.
        """
        token, _term = mint_for_instance(env, config, rid)
        return token

    @http.route('/mezze/floor', type='http', auth='user', methods=['GET'],
                website=False, readonly=False)
    def floor(self, **kw):
        env = request.env
        config = self._floor_resolve_config(env)
        user = env.user
        rid, rid_is_new = resolve_rid(request)
        lang = (user.lang or env.context.get('lang') or 'en_US')
        if not config:
            boot = {'ok': False, 'error': 'no_pos_config', 'api_prefix': API_PREFIX,
                    'user': {'id': user.id, 'name': user.name}, 'lang': lang}
        else:
            token = self._floor_mint_token(env, config, rid)
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
        raw_debug = getattr(request.session, 'debug', '') or ''
        mz_debug = re.sub(r'[^a-z0-9,]', '', str(raw_debug).lower())
        response = request.render('mezze_bridge.floor_page', {
            'boot_json': markupsafe.Markup(payload),
            'mz_lang': lang,
            'mz_debug': mz_debug,
        })
        return stamp_rid(response, rid, rid_is_new)
