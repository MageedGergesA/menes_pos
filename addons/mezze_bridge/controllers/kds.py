# Part of the Mezze POS platform. See LICENSE (LGPL-3).
"""V2C — production Kitchen Display (KDS) page controller.

Serves the standalone Owl KDS app at ``/mezze/kds``. Authentication is Odoo's own
session (``auth='user'``): an unauthenticated visitor is redirected to
``/web/login`` — the real *authentication-required* state, never demo data. For the
JSON API (``/mezze/api/v1/*``) the page carries a freshly minted, LEAST-PRIVILEGE
per-terminal token with ``role='kitchen'`` → it holds ONLY ``kitchen.read`` +
``kitchen.update`` (+ ``orders.read``): a KDS screen can VIEW the board and BUMP a
ticket, but can never pay, refund, void, comp, or reach admin settings.

Authority is ``mezze.kds.ticket`` (NOT the Odoo Enterprise Preparation Display —
see docs/project-truth-audit/KDS-REUSE-DECISION.md). No Enterprise/OEEL dependency.
"""
import json
import re
import secrets

import markupsafe

from odoo import http
from odoo.http import request

from .main import API_PREFIX


class MezzeKdsUI(http.Controller):

    def _resolve_config(self, env):
        """Authoritative branch (pos.config) for this display: explicit ?config_id=,
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

    def _mint_kitchen_token(self, env, config):
        """Find-or-create a dedicated 'Kitchen Display' terminal for this branch and
        set a fresh bearer token on it, returning the plaintext ONCE for the page.
        The server keeps only a non-reversible fingerprint. role='kitchen' ⇒ least
        privilege (kitchen.read + kitchen.update only)."""
        Term = env['mezze.terminal'].sudo()
        identifier = 'kitchen-display-%s' % config.id
        term = Term.with_context(active_test=False).search(
            [('identifier', '=', identifier)], limit=1)
        token = secrets.token_urlsafe(24)
        vals = {'token': token, 'branch_id': config.id, 'active': True, 'role': 'kitchen'}
        if term:
            term.write(vals)
        else:
            term = Term.create(dict(vals, name='Kitchen Display — %s' % config.name,
                                    identifier=identifier))
        return token, term

    @http.route('/mezze/kds', type='http', auth='user', methods=['GET'],
                website=False, readonly=False)
    def kds(self, **kw):
        env = request.env
        config = self._resolve_config(env)
        user = env.user
        lang = (user.lang or env.context.get('lang') or 'en_US')
        # Optional station pin (?station=Kitchen). The board shows every station's
        # tickets by default; a pinned station just pre-filters the display. No
        # parallel station model — station is the product-routing label on the ticket.
        station = (request.params.get('station') or '').strip() or None
        # Late threshold (minutes): branch/deployment config, NOT a hardcoded JS SLA.
        late_min = env['ir.config_parameter'].sudo().get_param(
            'mezze_bridge.kds_late_minutes', '15')
        try:
            late_min = max(1, int(str(late_min).strip() or 15))
        except (TypeError, ValueError):
            late_min = 15
        if not config:
            boot = {'ok': False, 'error': 'no_pos_config', 'api_prefix': API_PREFIX,
                    'user': {'id': user.id, 'name': user.name}, 'lang': lang}
        else:
            token, _term = self._mint_kitchen_token(env, config)
            boot = {
                'ok': True,
                'api_prefix': API_PREFIX,
                'token': token,
                'config_id': config.id,
                'user': {'id': user.id, 'name': user.name},
                'branch': {'id': config.id, 'name': config.name},
                'company_id': config.company_id.id,
                'station': station,
                'late_minutes': late_min,
                'lang': lang,
            }
        # Safe embed inside <script type="application/json">: escape '<' so a name
        # containing '</script>' cannot break out. Values are server-sourced.
        payload = json.dumps(boot).replace('<', '\\u003c')
        raw_debug = getattr(request.session, 'debug', '') or ''
        mz_debug = re.sub(r'[^a-z0-9,]', '', str(raw_debug).lower())
        return request.render('mezze_bridge.kds_page', {
            'boot_json': markupsafe.Markup(payload),
            'mz_lang': lang,
            'mz_debug': mz_debug,
        })
