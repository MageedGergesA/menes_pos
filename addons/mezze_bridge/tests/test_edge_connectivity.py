"""S1.1A — Edge connectivity contract tests. No test touches the real Internet:
the single reachability probe (`_http_ok`) is always patched/injected."""
import json
from unittest.mock import patch

from odoo.tests import tagged

from .common import MezzeHttpCase, MezzePosCase
from ..models import edge_connectivity as EC


def _clear_cache():
    EC._WAN_CACHE.clear()


@tagged('post_install', '-at_install', 'mezze_runtime')
class TestEdgeConnectivityModel(MezzePosCase):
    fixture_profile = 'POS'

    def setUp(self):
        super().setUp()
        _clear_cache()
        self.C = self.env['mezze.edge.connectivity']
        self.ICP = self.env['ir.config_parameter'].sudo()
        # hermetic external-service baseline: the canonical DB carries ambient aggregator
        # channels from earlier increments — deactivate them so each test controls the set.
        self.env['mezze.aggregator'].sudo().search([('active', '=', True)]).write({'active': False})
        self.ICP.set_param('mezze_bridge.offsite_backup_enabled', 'false')

    # --- deployment mode (1,2) ---
    def test_deployment_mode_cloud_default(self):
        self.ICP.set_param('mezze_bridge.deployment_mode', '')
        with patch.dict('os.environ', {}, clear=False):
            import os
            os.environ.pop('MEZZE_DEPLOYMENT_MODE', None)
            self.assertEqual(self.C.deployment_mode(), 'cloud')

    def test_deployment_mode_edge_explicit(self):
        self.ICP.set_param('mezze_bridge.deployment_mode', 'edge')
        self.assertEqual(self.C.deployment_mode(), 'edge')

    # --- WAN states (3,4,5,6) ---
    def test_wan_online_any_target_ok(self):
        self.ICP.set_param('mezze_bridge.wan_probe_urls', 'https://a.example,https://b.example')
        with patch.object(type(self.C), '_http_ok', lambda self, u, t: u.endswith('b.example')):
            self.assertEqual(self.C._probe_wan(force=True)['state'], 'online')

    def test_wan_offline_all_fail(self):
        self.ICP.set_param('mezze_bridge.wan_probe_urls', 'https://a.example,https://b.example')
        with patch.object(type(self.C), '_http_ok', lambda self, u, t: False):
            r = self.C._probe_wan(force=True)
            self.assertEqual(r['state'], 'offline')

    def test_wan_unknown_no_targets(self):
        self.ICP.set_param('mezze_bridge.wan_probe_urls', '')
        import os
        os.environ.pop('MEZZE_WAN_PROBE_URLS', None)
        self.assertEqual(self.C._probe_wan(force=True)['state'], 'unknown')

    def test_wan_unknown_on_probe_exception(self):
        self.ICP.set_param('mezze_bridge.wan_probe_urls', 'https://a.example')

        def boom(self, u, t):
            raise RuntimeError('probe subsystem failure')
        with patch.object(type(self.C), '_http_ok', boom):
            self.assertEqual(self.C._probe_wan(force=True)['state'], 'unknown')

    # --- cache prevents probe storm (7) ---
    def test_cache_prevents_probe_storm(self):
        self.ICP.set_param('mezze_bridge.wan_probe_urls', 'https://a.example')
        self.ICP.set_param('mezze_bridge.wan_probe_interval', '999')
        calls = {'n': 0}

        def counting(self2, u, t):
            calls['n'] += 1
            return True
        with patch.object(type(self.C), '_http_ok', counting):
            self.C._probe_wan(force=True)   # first real probe
            self.C.status(); self.C.status()  # cached — no new probe
        self.assertEqual(calls['n'], 1, 'probe must be cached within the interval')

    def test_last_success_timestamp_retained(self):
        self.ICP.set_param('mezze_bridge.wan_probe_urls', 'https://a.example')
        with patch.object(type(self.C), '_http_ok', lambda self, u, t: True):
            ok = self.C._probe_wan(force=True)
        self.assertTrue(ok['last_success_at'])
        with patch.object(type(self.C), '_http_ok', lambda self, u, t: False):
            off = self.C._probe_wan(force=True)
        self.assertEqual(off['state'], 'offline')
        self.assertEqual(off['last_success_at'], ok['last_success_at'], 'last success retained across an outage')

    # --- external services (12,13,14,15) ---
    def test_external_na_when_none_configured(self):
        self.assertEqual(self.C.external_services('online')['state'], 'n/a')

    def test_external_paused_when_wan_offline(self):
        self._make_aggregator()
        self.assertEqual(self.C.external_services('offline')['state'], 'paused')

    def test_external_online_when_wan_online_healthy(self):
        self._make_aggregator()
        self.assertEqual(self.C.external_services('online')['state'], 'online')

    def test_external_degraded_when_service_unhealthy(self):
        chan = self._make_aggregator()
        # simulate misconfiguration: clear the encrypted secret -> unhealthy
        chan.sudo().write({'secret_enc': False})
        self.env.flush_all()
        self.assertEqual(self.C.external_services('online')['state'], 'degraded')

    def test_external_unknown_when_wan_unknown(self):
        self._make_aggregator()
        self.assertEqual(self.C.external_services('unknown')['state'], 'unknown')

    # --- capability: WAN status never blocks local ops (16) ---
    def test_wan_offline_does_not_block_local_order(self):
        self.ICP.set_param('mezze_bridge.wan_probe_urls', 'https://a.example')
        with patch.object(type(self.C), '_http_ok', lambda self, u, t: False):
            self.assertEqual(self.C._probe_wan(force=True)['state'], 'offline')
        # a purely local order still succeeds while WAN is offline
        order = self.create_order_in_test_session(price=10.0)
        self.assertTrue(order.exists())
        self.assertEqual(order.state, 'draft')

    def _make_aggregator(self):
        from . import factories
        return factories.make_aggregator(
            self.env, self.pos_config, self.cash_payment_method, self.product, code='conntest')['channel']


@tagged('post_install', '-at_install', 'mezze_runtime')
class TestEdgeStatusEndpoint(MezzeHttpCase):
    fixture_profile = 'POS'

    def setUp(self):
        super().setUp()
        _clear_cache()
        self.env['ir.config_parameter'].sudo().set_param('mezze_bridge.deployment_mode', 'edge')
        self.env['ir.config_parameter'].sudo().set_param('mezze_bridge.wan_probe_urls', 'https://a.example')
        self.env['ir.config_parameter'].sudo().set_param('mezze_bridge.api_token', 'conn-tok')
        self.env['ir.config_parameter'].sudo().set_param('mezze_bridge.api_security', 'observe')
        self.env['ir.config_parameter'].sudo().set_param('mezze_bridge.env_profile', 'development')
        self.env.flush_all()

    def _post(self, body):
        r = self.url_open('/mezze/api/v1/edge/status', data=json.dumps(body),
                          headers={'Content-Type': 'application/json'}, timeout=30)
        try:
            return r.status_code, r.json()
        except Exception:
            return r.status_code, {'_raw': r.text[:200]}

    def test_authorized_status_read(self):
        with patch.object(type(self.env['mezze.edge.connectivity']), '_http_ok', lambda self, u, t: True):
            st, b = self._post({'token': 'conn-tok'})
        self.assertEqual(st, 200)
        self.assertTrue(b.get('ok'), b)
        self.assertEqual(b.get('deployment_mode'), 'edge')
        self.assertIn(b['wan']['state'], ('online', 'offline', 'unknown'))
        self.assertIn('external_services', b)

    def test_no_local_server_field(self):
        with patch.object(type(self.env['mezze.edge.connectivity']), '_http_ok', lambda self, u, t: True):
            st, b = self._post({'token': 'conn-tok'})
        self.assertNotIn('local_server', b, 'local server is client-derived, not a backend field')

    def test_unauthorized_rejected(self):
        st, b = self._post({'token': 'WRONG'})
        self.assertIn(st, (401, 403))
        self.assertFalse(b.get('ok'))

    def test_response_has_no_secrets(self):
        with patch.object(type(self.env['mezze.edge.connectivity']), '_http_ok', lambda self, u, t: True):
            st, b = self._post({'token': 'conn-tok'})
        blob = json.dumps(b).lower()
        for leak in ('password', 'secret', 'master_key', 'api_token', 'private'):
            self.assertNotIn(leak, blob, 'no secret-ish key in the status payload')
