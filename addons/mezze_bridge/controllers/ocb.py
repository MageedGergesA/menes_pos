# -*- coding: utf-8 -*-
"""Order Confirmation Board — the two ends of a customer-facing display.

STAFF end (`/ocb/publish`, `/ocb/status`) is authenticated like every other lane
endpoint and carries the operator's cart to the server.

CUSTOMER end (`/mezze/ocb/<token>` and `/ocb/state`) is public, because a display
appliance in a lane cannot log in. That makes the credential the whole security
boundary, so it is treated like one: an opaque token resolves to exactly ONE display,
and the read endpoint takes no lane, no id and no order reference. There is nothing
to increment and nothing to substitute — a Lane 1 credential cannot express a request
for Lane 2's order.
"""
import json
import os
import re

import markupsafe

from odoo import fields, http
from odoo.http import request

from .main import API_PREFIX, MezzeBridgeController


class MezzeOcb(MezzeBridgeController):

    # ==================================================================
    # STAFF — publish the cart the operator is typing
    # ==================================================================
    @http.route(f'{API_PREFIX}/ocb/publish', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*', readonly=False)
    def ocb_publish(self, config_id=None, lane=1, lines=None, action=None, **kw):
        """Project the operator's in-progress cart onto that lane's display.

        ``action`` — ``update`` (default), ``clear`` when the operator abandons the
        order, ``confirm`` when it has been sent. There is no partial protocol: each
        call carries the WHOLE cart, so a dropped request cannot leave the customer
        looking at half an order, and the next keystroke repairs it.
        """
        auth = self._authorize()
        if auth:
            return auth
        try:
            env = self._api_env()
            config = self._resolve_config(env, config_id)
            display = env['mezze.ocb.display']._for_lane(config, lane)
            if not display:
                # Not an error: a branch may simply have no board on this lane, and
                # order taking must never stop because a screen is missing.
                return {'ok': True, 'display': False}
            if action == 'clear':
                display._clear()
            elif action == 'confirm':
                order = None
                if kw.get('order_id'):
                    order = env['pos.order'].sudo().browse(int(kw['order_id'])).exists()
                display._confirm(order)
            else:
                display._publish(lines or [])
            return {'ok': True, 'display': True, 'state': display.state,
                    'revision': display.revision}
        except Exception as exc:  # noqa: BLE001
            _l = __import__('logging').getLogger(__name__)
            _l.exception("Mezze ocb_publish failed")
            return self._json({'ok': False, 'error': 'ocb_publish_failed',
                               'message': str(exc)}, status=400)

    @http.route(f'{API_PREFIX}/ocb/status', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def ocb_status(self, config_id=None, lane=1, **kw):
        """Is this lane's board configured, and has it asked for state recently?

        The operator gets a small indicator, not a device dashboard. A board that
        exists but has not polled is reported OFFLINE rather than assumed visible —
        a confirmation nobody can see is worse than none, because the operator stops
        double-checking.
        """
        auth = self._authorize()
        if auth:
            return auth
        env = self._api_env()
        config = self._resolve_config(env, config_id)
        display = env['mezze.ocb.display']._for_lane(config, lane)
        if not display:
            return {'ok': True, 'configured': False, 'online': False}
        seen = display.last_seen
        online = bool(seen and (fields.Datetime.now() - seen).total_seconds() <= 15)
        return {'ok': True, 'configured': True, 'online': online,
                'name': display.name, 'lane': display.lane}

    # ==================================================================
    # CUSTOMER — read one display's own state
    # ==================================================================
    @http.route(f'{API_PREFIX}/ocb/state', type='json2', auth='none',
                methods=['POST'], csrf=False, readonly=False)
    def ocb_state(self, token=None, **kw):
        """The current confirmation state for the display holding this token.

        The token is the only input. Rate-limited like the other public customer
        endpoint, because a public route that resolves a credential is a route
        somebody will try to guess at.
        """
        env = self._api_env()
        try:
            allowed, _retry, _c = env['mezze.rate.limit'].hit(
                'ocb_state:%s' % (token or '')[:16], 240, 60)
            if not allowed:
                return self._json({'ok': False, 'error': 'rate_limited'}, status=429)
        except Exception:  # noqa: BLE001
            pass
        display = env['mezze.ocb.display']._resolve_token(token)
        if not display:
            # One answer for unknown, disabled and revoked. Distinguishing them tells
            # a prober which guesses were closer.
            return self._json({'ok': False, 'error': 'display_unavailable'}, status=404)
        display.sudo().write({'last_seen': fields.Datetime.now()})
        return dict({'ok': True}, **display._snapshot())

    @http.route('/mezze/ocb/<string:display_token>', type='http', auth='public',
                methods=['GET'], website=False, sitemap=False)
    def ocb_page(self, display_token=None, **kw):
        """The customer's screen. A standalone appliance surface: no staff rail, no
        Odoo shell, no admin chrome, 100vw x 100vh."""
        display = request.env['mezze.ocb.display']._resolve_token(display_token)
        if not display:
            return request.not_found()
        boot = {'token': display_token, 'api_prefix': API_PREFIX,
                'lang': display.lang or 'en_US', 'lane': display.lane}
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            'static', 'ocb.html')
        with open(path, encoding='utf-8') as fh:
            html = fh.read()
        payload = json.dumps(boot).replace('<', '\\u003c').replace('>', '\\u003e')
        html = html.replace('</head>',
                            '<script type="application/json" id="mezze-boot">%s</script>\n</head>'
                            % payload, 1)
        # The display's configured language decides direction, never the operator's.
        direction = 'rtl' if str(display.lang or '').lower().startswith('ar') else 'ltr'
        html = re.sub(r'<html\b([^>]*)>',
                      lambda m: '<html%s lang="%s" dir="%s">'
                                % (m.group(1),
                                   (display.lang or 'en_US').replace('_', '-'), direction),
                      html, count=1)
        html = re.sub(r'(href|src)="(?!/|https?:|data:)([^"]+)"',
                      r'\1="/mezze_bridge/static/\2"', html)
        headers = [
            ('Content-Type', 'text/html; charset=utf-8'),
            # A customer's order is on this page. Back, reload or a shared kiosk must
            # not resurrect the previous guest's transaction from cache.
            ('Cache-Control', 'no-store, no-cache, must-revalidate, private'),
            ('Pragma', 'no-cache'),
            ('Referrer-Policy', 'no-referrer'),
        ]
        return request.make_response(markupsafe.Markup(html), headers=headers)
