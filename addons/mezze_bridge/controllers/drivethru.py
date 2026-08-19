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
import re
import secrets

import markupsafe

from odoo import http
from odoo.http import request

from .main import API_PREFIX


class MezzeDriveThru(http.Controller):

    def _resolve_config(self, env):
        """Authoritative branch for this lane: explicit ?config_id=, else the
        configured default branch, else the first config."""
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

    def _appearance(self, env, config, term_ident):
        """The branch's chosen appearance, as attributes for <html>.

        Resolved from the SAME settings the Register and Kitchen read, through the
        same scope hierarchy — so "Whole branch" really does mean this screen too.
        Falls back to the catalogue defaults if anything is missing; appearance must
        never be able to stop a lane board from opening.
        """
        # data-mz-source marks this as the BRANCH's answer, so the client-side
        # appearance engines (which only know this browser) leave it alone.
        out = {'data-appearance': 'mezze', 'data-mz-source': 'server'}
        try:
            ctx = {'company_id': config.company_id.id if config else None,
                   'branch_id': config.id if config else None,
                   'role': 'terminal', 'user_ref': 'terminal:%s' % term_ident}
            eff = env['mezze.settings'].sudo().resolve(ctx)['effective']
        except Exception:  # noqa: BLE001 — a themeless board still works
            return out
        mode = eff.get('app_mode') or 'system'
        if mode not in ('light', 'dark'):
            mode = 'light'          # no OS preference server-side; the script may refine it
        hc = str(eff.get('ac_contrast')).lower() in ('true', '1')
        theme = ('highcontrast' if hc
                 else (eff.get('app_dark_theme') or 'lounge') if mode == 'dark'
                 else (eff.get('app_theme') or 'classic'))
        out.update({
            'data-theme': mode, 'data-mz-mode': mode, 'data-mz-theme': theme,
            'data-mz-accent': eff.get('app_accent') or 'terracotta',
            'data-mz-density': eff.get('app_density') or 'standard',
            'data-mz-scale': str(eff.get('app_scale') or '100'),
            # The workspace settings. These were missing, and the omission was visible:
            # the canonical panel narrows to a 320px basis under 1100px, and the Register
            # never reaches that rule because its own stamp (data-mz-panel-w) carries
            # higher specificity. So at 1024 the till showed a 341px order panel and the
            # lane showed 321 — the same component, two widths, because one screen was
            # told the branch's preference and the other was not.
            'data-mz-panel': eff.get('ws_panel_side') or 'right',
            'data-mz-panel-w': eff.get('ws_panel_width') or 'standard',
        })
        d = eff.get('ac_dir')
        if d in ('ltr', 'rtl'):
            out['dir'] = d
        return out

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
        appearance = self._appearance(env, config, term_ident='drivethru-%s' % (config.id if config else 0))
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            'static', 'drivethru.html')
        with open(path, encoding='utf-8') as fh:
            html = fh.read()
        # The page reads its credentials from this element. json.dumps is escaped for
        # a <script> context so a branch name can never break out of the tag.
        payload = json.dumps(boot).replace('<', '\\u003c').replace('>', '\\u003e')
        tag = '<script type="application/json" id="mezze-boot">%s</script>' % payload
        html = html.replace('</head>', tag + '\n</head>', 1)
        # Stamp the BRANCH's appearance on <html> server-side. The page's own
        # pre-paint script guesses from localStorage, which is per-browser and knows
        # nothing about the branch — so a branch on Forest showed a classic orange
        # board. Stamping here also removes the flash: the first paint is already
        # the right theme, and the script below only fills in what is missing.
        attrs = ' '.join('%s="%s"' % (k, v) for k, v in appearance.items())
        html = re.sub(r'<html\b([^>]*)>', lambda m: '<html%s %s>' % (m.group(1), attrs), html, count=1)
        # The page lives at /mezze_bridge/static/ but is SERVED from /mezze/, so every
        # relative asset href resolves to a path that does not exist. Rewriting only
        # "design/" left mezze-design.css 404ing silently — which is why the board had
        # no theme tokens at all and fell back to its own palette. Rewrite them all.
        html = re.sub(r'(href|src)="(?!/|https?:|data:)([^"]+)"',
                      r'\1="/mezze_bridge/static/\2"', html)
        headers = [
            ('Content-Type', 'text/html; charset=utf-8'),
            # A minted bearer token is in this response — it must never be cached.
            ('Cache-Control', 'no-store, no-cache, must-revalidate, private'),
            ('Pragma', 'no-cache'),
        ]
        return request.make_response(markupsafe.Markup(html), headers=headers)
