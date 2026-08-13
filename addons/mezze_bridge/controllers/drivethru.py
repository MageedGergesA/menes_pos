# -*- coding: utf-8 -*-
"""Drive-thru lane board — served, authenticated, at /mezze/drivethru.

The board itself already existed (static/drivethru.html) and already spoke to real
endpoints (drivethru/board, drivethru/create, drivethru/stage). What it did not have
was a way to be reached: no Odoo route served it, so it was an unreachable file, and
its only means of authenticating was ``?token=`` in the query string — which puts a
bearer token into access logs, browser history and any link an operator shares.

This route closes both gaps the same way the Register, Floor and Kitchen do: the
Odoo user is authenticated first, a least-privilege per-branch terminal token is
minted server-side, and the plaintext is handed to the page ONCE through an injected
boot payload. The server keeps only a non-reversible fingerprint.
"""
import json
import os
import secrets

import markupsafe

from odoo import http
from odoo.http import request

from .main import API_PREFIX


class MezzeDriveThru(http.Controller):

    def _resolve_config(self, env):
        """Authoritative branch for this lane: explicit ?config_id=, else the
        configured default branch, else the first config."""
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

    def _mint_lane_token(self, env, config):
        """Find-or-create a 'Drive-thru' terminal for this branch and set a fresh
        bearer token on it. role='terminal' — the lane takes orders and fires them,
        so it needs the same selling capabilities a till has, and no more."""
        Term = env['mezze.terminal'].sudo()
        identifier = 'drivethru-%s' % config.id
        term = Term.with_context(active_test=False).search(
            [('identifier', '=', identifier)], limit=1)
        token = secrets.token_urlsafe(24)
        vals = {'token': token, 'branch_id': config.id, 'active': True, 'role': 'terminal'}
        if term:
            term.write(vals)
        else:
            term = Term.create(dict(vals, name='Drive-thru — %s' % config.name,
                                    identifier=identifier))
        return token, term

    @http.route('/mezze/drivethru', type='http', auth='user', methods=['GET'],
                website=False, readonly=False)
    def drivethru(self, **kw):
        env = request.env
        config = self._resolve_config(env)
        if not config:
            boot = {'ok': False, 'error': 'no_pos_config', 'api_prefix': API_PREFIX}
        else:
            token, _term = self._mint_lane_token(env, config)
            boot = {
                'ok': True,
                'api_prefix': API_PREFIX,
                'token': token,
                'config_id': config.id,
                'branch': {'id': config.id, 'name': config.name},
                'lang': (env.user.lang or env.context.get('lang') or 'en_US'),
            }
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            'static', 'drivethru.html')
        with open(path, encoding='utf-8') as fh:
            html = fh.read()
        # The page reads its credentials from this element. json.dumps is escaped for
        # a <script> context so a branch name can never break out of the tag.
        payload = json.dumps(boot).replace('<', '\\u003c').replace('>', '\\u003e')
        tag = '<script type="application/json" id="mezze-boot">%s</script>' % payload
        html = html.replace('</head>', tag + '\n</head>', 1)
        # Relative asset hrefs (design/foundation.css) resolve against /mezze/, so
        # point them at the addon's static root instead of a path that does not exist.
        html = html.replace('href="design/', 'href="/mezze_bridge/static/design/')
        headers = [
            ('Content-Type', 'text/html; charset=utf-8'),
            # A minted bearer token is in this response — it must never be cached.
            ('Cache-Control', 'no-store, no-cache, must-revalidate, private'),
            ('Pragma', 'no-cache'),
        ]
        return request.make_response(markupsafe.Markup(html), headers=headers)
