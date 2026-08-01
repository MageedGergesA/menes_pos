"""S1.1A — Edge connectivity status endpoint.

Authenticated, read-only. Returns deployment mode + WAN + external-service status
(no ``local_server`` field — the frontend derives that from whether this RPC
succeeds). No DB mutation, no secrets in the response.
"""
from odoo import http

from .main import MezzeBridgeController, API_PREFIX


class MezzeEdgeController(MezzeBridgeController):

    @http.route(f'{API_PREFIX}/edge/status', type='json2', auth='none',
                methods=['POST'], csrf=False)   # readonly (default) — no writes
    def edge_status(self, **kw):
        auth = self._authorize(endpoint='edge.status')
        if auth:
            return auth
        env = self._api_env()
        return {'ok': True, **env['mezze.edge.connectivity'].status()}
