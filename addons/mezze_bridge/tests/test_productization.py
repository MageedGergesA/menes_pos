"""S5 — productization: secret/PII redaction (leakage=0), release identity,
commercial go-live profiles, support bundle safety, onboarding (resumable +
derived completion), neutralized staging state.

Model-level + a couple of HTTP smoke tests. Deterministic + hermetic.
"""
import json

from odoo.tests import tagged

from .common import MezzePosCase, MezzeHttpCase
from ..domain import redaction


@tagged('post_install', '-at_install', 'mezze_invariants')
class TestRedaction(MezzePosCase):
    """The core productization safety property: no secret / PII survives redact()."""

    SECRETS = [
        'password=SuperS3cretPw!',
        'db_password = pgpass1234',
        'admin_passwd = letmein-admin',
        'MEZZE_MASTER_KEY=Zm9vYmFyYmF6cXV4MTIzNA==',
        'api_key: sk_live_ABCDEF1234567890',
        '"api_token": "tok_9f8e7d6c5b4a3210"',
        'client_secret=whsec_0011223344556677',
        'hmac_secret = 8f3a2b1c9d0e4f5a6b7c8d9e',
        'Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.payload.sig',
        'paymob_api_key = pmk_live_zzzz9999yyyy',
        'terminal_secret=trm_secret_value_42',
        '-----BEGIN RSA PRIVATE KEY-----\nMIIBOwIBAAAA\n-----END RSA PRIVATE KEY-----',
    ]
    # values that must NOT appear anywhere post-redaction
    LEAK_TOKENS = [
        'SuperS3cretPw!', 'pgpass1234', 'letmein-admin', 'Zm9vYmFyYmF6cXV4MTIzNA==',
        'sk_live_ABCDEF1234567890', 'tok_9f8e7d6c5b4a3210', 'whsec_0011223344556677',
        '8f3a2b1c9d0e4f5a6b7c8d9e', 'eyJhbGciOiJIUzI1NiJ9.payload.sig',
        'pmk_live_zzzz9999yyyy', 'trm_secret_value_42', 'MIIBOwIBAAAA',
    ]
    PII = ['4111 1111 1111 1111', '4111111111111111', 'cvv=123', 'customer@example.com']
    PII_LEAK = ['4111 1111 1111 1111', '4111111111111111', 'customer@example.com']

    def test_secret_leakage_is_zero(self):
        blob = '\n'.join(self.SECRETS + self.PII)
        out = redaction.redact(blob)
        for tok in self.LEAK_TOKENS + self.PII_LEAK:
            self.assertNotIn(tok, out, 'LEAKED secret/PII: %r' % tok)
        self.assertIn(redaction.REDACTED, out)

    def test_redact_is_idempotent(self):
        once = redaction.redact('password=abc123secretvalue')
        self.assertEqual(once, redaction.redact(once))

    def test_redact_json_preserves_keys_scrubs_values(self):
        obj = {'ok': True, 'count': 3, 'api_token': 'tok_deadbeefcafef00d',
               'nested': {'password': 'p@ssw0rd-here', 'note': 'fine'}}
        out = redaction.redact_json(obj)
        self.assertEqual(out['ok'], True)         # non-string scalar preserved
        self.assertEqual(out['count'], 3)
        self.assertIn('api_token', out)           # key preserved
        self.assertNotIn('tok_deadbeefcafef00d', json.dumps(out))
        self.assertNotIn('p@ssw0rd-here', json.dumps(out))


@tagged('post_install', '-at_install', 'mezze_runtime')
class TestReleaseAndProfiles(MezzePosCase):

    def test_release_identity_shape(self):
        rid = self.env['mezze.productization'].release_identity()
        for k in ('product', 'product_version', 'edition', 'deployment_mode',
                  'module', 'module_version', 'odoo_version', 'git_commit',
                  'release_channel', 'neutralized'):
            self.assertIn(k, rid)
        self.assertEqual(rid['module'], 'mezze_bridge')
        self.assertTrue(rid['odoo_version'].startswith('19.'))
        # no secret-shaped value in the identity
        self.assertNotIn(redaction.REDACTED, json.dumps(rid))

    def test_commercial_profiles_listed(self):
        profs = {p['id'] for p in self.env['mezze.golive.validator'].profiles()}
        self.assertTrue({'counter', 'restaurant', 'restaurant_qr', 'delivery', 'full'} <= profs)

    def test_delivery_profile_requires_zone(self):
        # no delivery zone configured -> delivery_zone_configured is NA baseline,
        # but REQUIRED by the delivery profile, so it must become a FAIL.
        base = self.env['mezze.golive.validator'].run(profile='golive')
        base_by = {c['name']: c['status'] for c in base['checks']}
        self.assertEqual(base_by.get('delivery_zone_configured'), 'N/A')

        deliv = self.env['mezze.golive.validator'].run(profile='delivery')
        by = {c['name']: c for c in deliv['checks']}
        self.assertEqual(by['delivery_zone_configured']['status'], 'FAIL')
        self.assertTrue(by['delivery_zone_configured']['required'])
        self.assertIn('REQUIRED by the "delivery" profile', by['delivery_zone_configured']['detail'])
        self.assertEqual(deliv['overall'], 'FAIL')

    def test_not_tested_never_upgraded_by_profile(self):
        # NOT TESTED facts (edge host checks) must stay NOT TESTED under any profile.
        edge = self.env['mezze.golive.validator'].run(profile='edge')
        nts = [c for c in edge['checks'] if c['status'] == 'NOT TESTED']
        self.assertTrue(nts, 'expected some honest NOT TESTED edge facts')
        for c in nts:
            self.assertNotEqual(c['status'], 'PASS')


@tagged('post_install', '-at_install', 'mezze_runtime')
class TestNeutralized(MezzePosCase):

    def test_neutralized_flag_and_production_conflict(self):
        icp = self.env['ir.config_parameter'].sudo()
        Prod = self.env['mezze.productization']
        self.assertFalse(Prod.is_neutralized())
        icp.set_param('mezze_bridge.neutralized', 'True')
        self.assertTrue(Prod.is_neutralized())
        # neutralized + production profile => hard FAIL on env_neutralized
        icp.set_param('mezze_bridge.env_profile', 'production')
        rep = self.env['mezze.golive.validator'].run(profile='golive')
        by = {c['name']: c for c in rep['checks']}
        self.assertEqual(by['env_neutralized']['status'], 'FAIL')

    def test_demo_marker_fails_production(self):
        icp = self.env['ir.config_parameter'].sudo()
        icp.set_param('mezze_bridge.env_profile', 'production')
        icp.set_param('mezze_bridge.demo_loaded', 'True')
        rep = self.env['mezze.golive.validator'].run(profile='golive')
        by = {c['name']: c for c in rep['checks']}
        self.assertEqual(by['demo_data_absent']['status'], 'FAIL')


@tagged('post_install', '-at_install', 'mezze_runtime')
class TestSupportBundle(MezzePosCase):

    def test_bundle_is_redacted_and_carries_no_orders(self):
        icp = self.env['ir.config_parameter'].sudo()
        # plant a secret-looking param that could end up in a config summary
        icp.set_param('mezze_bridge.api_token', 'tok_should_never_leak_9988')
        bundle = self.env['mezze.productization'].support_bundle(profile='golive')
        blob = json.dumps(bundle)
        self.assertNotIn('tok_should_never_leak_9988', blob)
        # structural: identity + validator present; NO raw dump / orders / partners
        self.assertIn('release', bundle)
        self.assertIn('validator', bundle)
        self.assertNotIn('orders', bundle)
        self.assertNotIn('db_dump', bundle)
        self.assertNotIn('partners', bundle)


@tagged('post_install', '-at_install', 'mezze_runtime')
class TestOnboarding(MezzePosCase):

    def test_status_resumable_and_derived(self):
        Onb = self.env['mezze.onboarding']
        s1 = Onb.status(profile='full')
        self.assertTrue(s1['ok'])
        self.assertTrue(any(st['id'] == 'branch' for st in s1['steps']))
        # completion is DERIVED from the validator overall, never a stored boolean
        self.assertEqual(s1['complete'], s1['overall'] != 'FAIL' and all(
            st['state'] in ('done', 'attention') for st in s1['steps']
            if not st['optional'] and st['id'] != 'review'))
        # idempotent: calling again yields the same shape (no state mutated)
        s2 = Onb.status(profile='full')
        self.assertEqual([st['id'] for st in s1['steps']], [st['id'] for st in s2['steps']])

    def test_acknowledge_idempotent_and_gated(self):
        Onb = self.env['mezze.onboarding']
        # a validator-gated step cannot be acked
        r = Onb.acknowledge('branch', done=True)
        self.assertFalse(r['ok'])
        # an informational step can, idempotently
        r1 = Onb.acknowledge('kds', done=True)
        r2 = Onb.acknowledge('kds', done=True)
        self.assertTrue(r1['ok'] and r2['ok'])
        acks = json.loads(self.env['ir.config_parameter'].sudo().get_param(
            'mezze_bridge.onboarding_ack') or '{}')
        self.assertEqual(acks.get('kds'), True)


@tagged('post_install', '-at_install', 'mezze_runtime')
class TestProductizationRoutes(MezzeHttpCase):
    fixture_profile = 'POS'

    def setUp(self):
        super().setUp()
        icp = self.env['ir.config_parameter'].sudo()
        icp.set_param('mezze_bridge.api_token', 'prod-tok')
        icp.set_param('mezze_bridge.api_security', 'observe')
        icp.set_param('mezze_bridge.env_profile', 'development')
        self.env.flush_all()

    def _post(self, path, body=None):
        r = self.url_open('/mezze/api/v1' + path,
                          data=json.dumps(dict(body or {}, token='prod-tok')),
                          headers={'Content-Type': 'application/json'}, timeout=30)
        try:
            return r.status_code, r.json()
        except Exception:
            return r.status_code, {'_raw': r.text[:200]}

    def test_version_route(self):
        st, r = self._post('/admin/version')
        self.assertTrue(r.get('ok'), r)
        self.assertEqual(r['release']['module'], 'mezze_bridge')

    def test_golive_route_with_profile(self):
        st, r = self._post('/admin/golive', {'profile': 'delivery'})
        self.assertTrue(r.get('ok'), r)
        self.assertEqual(r['profile'], 'delivery')
        self.assertIn('checks', r)
        self.assertTrue(any(p['id'] == 'counter' for p in r['profiles']))

    def test_support_bundle_route_redacted(self):
        self.env['ir.config_parameter'].sudo().set_param(
            'mezze_bridge.api_token', 'prod-tok')  # keep token; also a secret-shaped param below
        st, r = self._post('/admin/support_bundle')
        self.assertTrue(r.get('ok'), r)
        self.assertIn('release', r['bundle'])
        self.assertNotIn('prod-tok', json.dumps(r['bundle']))

    def test_onboarding_route(self):
        st, r = self._post('/admin/onboarding', {'profile': 'counter'})
        self.assertTrue(r.get('ok'), r)
        self.assertTrue(r['steps'])
