"""WS-0 — Mezze Station enrolment, device authentication and the attack proofs.

Each test drives the real HTTP protocol with real ECDSA P-256 keys, exactly as the
Windows client will: the private key never leaves the "device", the server only ever
sees a public key and a signature over a nonce it issued itself.

The four proofs the phase is judged on are here, not in prose:
  * copy attack     — copying the install to another machine authenticates nothing
  * replay          — a captured (nonce, signature) is worthless the second time
  * role escalation — a station cannot claim a role the server did not grant it
  * revocation      — one station dies, its neighbour keeps selling
"""
import base64
import json
import uuid

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, utils as asym_utils

from odoo.tests import tagged

from .common import MezzeHttpCase

PREFIX = '/mezze/station/v1'


class _Device:
    """A simulated station: a keypair that stays here and never crosses the wire."""

    def __init__(self, provider='Microsoft Platform Crypto Provider', level='a_tpm'):
        self.uuid = str(uuid.uuid4())
        self._key = ec.generate_private_key(ec.SECP256R1())
        self.provider = provider
        self.level = level
        self.station_id = None

    @property
    def public_key_b64(self):
        return base64.b64encode(self._key.public_key().public_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo)).decode()

    def sign(self, message):
        """Sign like Windows CNG does — raw r||s, not DER."""
        der = self._key.sign(message.encode(), ec.ECDSA(hashes.SHA256()))
        r, s = asym_utils.decode_dss_signature(der)
        return base64.b64encode(r.to_bytes(32, 'big') + s.to_bytes(32, 'big')).decode()


@tagged('post_install', '-at_install', 'mezze_station')
class TestStationWS0(MezzeHttpCase):
    fixture_profile = 'POS'

    def setUp(self):
        super().setUp()
        self.env['ir.config_parameter'].sudo().set_param('mezze_bridge.api_security', 'enforce')

    # ------------------------------------------------------------- helpers
    def _post(self, path, payload):
        resp = self.url_open(PREFIX + path, data=json.dumps(payload),
                             headers={'Content-Type': 'application/json'})
        try:
            body = resp.json()
        except Exception:  # noqa: BLE001
            body = {'ok': False, 'error': 'non_json', 'status': resp.status_code}
        return resp.status_code, body

    def _code(self, role='register', branch=None):
        act, raw = self.env['mezze.station.activation'].issue(
            branch or self.pos_config, role, label='Test %s' % role)
        return act, raw

    def _enroll(self, device, role='register', code=None, branch=None):
        _act, raw = (None, code) if code else self._code(role, branch)
        status, body = self._post('/enroll', {
            'activation_code': raw,
            'device_uuid': device.uuid,
            'public_key': device.public_key_b64,
            'crypto_provider': device.provider,
            'security_level': device.level,
            'app_version': '0.1.0-ws0',
            'os_version': 'Windows 11 26100',
            'hostname': 'TEST-PC',
        })
        if body.get('ok'):
            device.station_id = body['station_id']
        return status, body, raw

    def _authenticate(self, device):
        _s, ch = self._post('/challenge', {'device_uuid': device.uuid})
        if not ch.get('ok'):
            return _s, ch, None
        message = '%s|%s|%s' % (ch['protocol'], device.uuid, ch['nonce'])
        status, body = self._post('/auth', {
            'device_uuid': device.uuid, 'nonce': ch['nonce'],
            'signature': device.sign(message), 'app_version': '0.1.0-ws0'})
        return status, body, ch

    # ------------------------------------------------------- 1. enrolment
    def test_01_health_publishes_the_lease_key_and_no_secret(self):
        resp = self.url_open(PREFIX + '/health')
        body = resp.json()
        self.assertTrue(body['ok'])
        self.assertTrue(body['lease_public_key'], 'stations need the lease public key')
        blob = json.dumps(body).lower()
        for forbidden in ('private', 'token', 'secret', 'password'):
            self.assertNotIn(forbidden, blob, 'health leaked %s' % forbidden)

    def test_02_a_device_enrols_with_a_one_time_code(self):
        dev = _Device()
        status, body, _raw = self._enroll(dev, 'register')
        self.assertEqual(status, 200, body)
        self.assertTrue(body['ok'], body)
        self.assertEqual(body['station_role'], 'register')
        self.assertEqual(body['entry_surface'], '/mezze/pos', 'the server picks the surface')
        self.assertEqual(body['branch']['id'], self.pos_config.id)
        # nothing that survives a copy comes back
        for forbidden in ('session_token', 'token', 'api_key', 'password', 'private_key'):
            self.assertNotIn(forbidden, body, 'enrolment returned %s' % forbidden)

    def test_03_the_activation_code_is_one_time(self):
        dev_a, dev_b = _Device(), _Device()
        _status, body, raw = self._enroll(dev_a, 'register')
        self.assertTrue(body['ok'])
        status, body2, _ = self._enroll(dev_b, code=raw)
        self.assertEqual(status, 403)
        self.assertEqual(body2['error'], 'activation_invalid',
                         'a burnt code must never enrol a second device')

    def test_04_an_expired_code_is_refused(self):
        act, raw = self._code('register')
        act.sudo().write({'expires_at': '2020-01-01 00:00:00'})
        status, body, _ = self._enroll(_Device(), code=raw)
        self.assertEqual(status, 403)
        self.assertEqual(body['error'], 'activation_invalid')

    def test_05_only_a_p256_public_key_is_accepted(self):
        from cryptography.hazmat.primitives.asymmetric import rsa
        rsa_pub = base64.b64encode(rsa.generate_private_key(
            public_exponent=65537, key_size=2048).public_key().public_bytes(
                encoding=serialization.Encoding.DER,
                format=serialization.PublicFormat.SubjectPublicKeyInfo)).decode()
        _act, raw = self._code('register')
        status, body = self._post('/enroll', {
            'activation_code': raw, 'device_uuid': str(uuid.uuid4()),
            'public_key': rsa_pub, 'security_level': 'a_tpm'})
        self.assertEqual(status, 400)
        self.assertEqual(body['error'], 'invalid_public_key')

    def test_06_the_server_records_the_public_key_and_the_honest_level(self):
        dev = _Device(provider='DPAPI/CurrentUser', level='b_dpapi')
        self._enroll(dev, 'kds')
        station = self.env['mezze.terminal'].sudo().search([('device_uuid', '=', dev.uuid)])
        self.assertEqual(len(station), 1)
        self.assertEqual(station.public_key, dev.public_key_b64)
        self.assertEqual(station.security_level, 'b_dpapi',
                         'the server records what the device really achieved')
        self.assertEqual(station.station_role, 'kds')
        self.assertEqual(station.role, 'kitchen', 'KDS gets the kitchen capability set')

    def test_07_a_claimed_security_level_is_recorded_never_upgraded(self):
        dev = _Device(level='nonsense')
        self._enroll(dev, 'register')
        station = self.env['mezze.terminal'].sudo().search([('device_uuid', '=', dev.uuid)])
        self.assertEqual(station.security_level, 'c_software',
                         'an unrecognised claim falls to the least trusted level')

    # ------------------------------------------------- 2. challenge / auth
    def test_10_challenge_response_authenticates_and_returns_a_short_session(self):
        dev = _Device()
        self._enroll(dev, 'register')
        status, body, _ch = self._authenticate(dev)
        self.assertEqual(status, 200, body)
        self.assertTrue(body['ok'], body)
        self.assertTrue(body['session_token'])
        self.assertLessEqual(body['expires_in'], 3600, 'a station session must be short-lived')
        self.assertEqual(body['station_role'], 'register')
        self.assertEqual(body['entry_surface'], '/mezze/pos')

    def test_11_a_wrong_signature_is_refused(self):
        dev, other = _Device(), _Device()
        self._enroll(dev, 'register')
        _s, ch = self._post('/challenge', {'device_uuid': dev.uuid})
        message = '%s|%s|%s' % (ch['protocol'], dev.uuid, ch['nonce'])
        status, body = self._post('/auth', {
            'device_uuid': dev.uuid, 'nonce': ch['nonce'],
            'signature': other.sign(message)})     # signed by the WRONG key
        self.assertEqual(status, 403)
        self.assertEqual(body['error'], 'invalid_signature')

    def test_12_a_signature_over_another_devices_nonce_is_refused(self):
        a, b = _Device(), _Device()
        self._enroll(a, 'register')
        self._enroll(b, 'kds')
        _s, cha = self._post('/challenge', {'device_uuid': a.uuid})
        # B signs A's nonce with B's own key and presents it as B
        message = '%s|%s|%s' % (cha['protocol'], b.uuid, cha['nonce'])
        status, body = self._post('/auth', {'device_uuid': b.uuid, 'nonce': cha['nonce'],
                                            'signature': b.sign(message)})
        self.assertEqual(status, 403)
        self.assertEqual(body['error'], 'replayed_challenge',
                         "a nonce is bound to the device it was issued to")

    def test_13_replay_is_denied(self):
        dev = _Device()
        self._enroll(dev, 'register')
        _s, ch = self._post('/challenge', {'device_uuid': dev.uuid})
        message = '%s|%s|%s' % (ch['protocol'], dev.uuid, ch['nonce'])
        signature = dev.sign(message)
        first = self._post('/auth', {'device_uuid': dev.uuid, 'nonce': ch['nonce'],
                                     'signature': signature})
        self.assertTrue(first[1]['ok'], first)
        # the very same captured pair, replayed
        status, body = self._post('/auth', {'device_uuid': dev.uuid, 'nonce': ch['nonce'],
                                            'signature': signature})
        self.assertEqual(status, 403)
        self.assertEqual(body['error'], 'replayed_challenge')

    def test_14_an_expired_challenge_is_refused(self):
        dev = _Device()
        self._enroll(dev, 'register')
        _s, ch = self._post('/challenge', {'device_uuid': dev.uuid})
        self.env['mezze.station.challenge'].sudo().search(
            [('nonce', '=', ch['nonce'])]).write({'expires_at': '2020-01-01 00:00:00'})
        message = '%s|%s|%s' % (ch['protocol'], dev.uuid, ch['nonce'])
        status, body = self._post('/auth', {'device_uuid': dev.uuid, 'nonce': ch['nonce'],
                                            'signature': dev.sign(message)})
        self.assertEqual(status, 403)
        self.assertEqual(body['error'], 'replayed_challenge')

    # --------------------------------------------------- 3. the copy attack
    def test_20_copying_the_installation_authenticates_nothing(self):
        """PC B gets everything on PC A's disk EXCEPT the private key, because the
        key is in PC A's TPM (or behind PC A's DPAPI). It cannot authenticate."""
        a = _Device()
        self._enroll(a, 'register')
        status, ok_body, _ = self._authenticate(a)
        self.assertTrue(ok_body['ok'], 'the real device works')

        # everything a thief could copy off the disk: identity, config, station id
        copied_uuid, copied_station = a.uuid, a.station_id
        thief = _Device()                      # PC B: a different key, same files
        thief.uuid = copied_uuid

        _s, ch = self._post('/challenge', {'device_uuid': copied_uuid})
        message = '%s|%s|%s' % (ch['protocol'], copied_uuid, ch['nonce'])
        status, body = self._post('/auth', {'device_uuid': copied_uuid, 'nonce': ch['nonce'],
                                            'signature': thief.sign(message)})
        self.assertEqual(status, 403)
        self.assertEqual(body['error'], 'invalid_signature',
                         'a copied install must not become a licensed station')
        self.assertTrue(copied_station, 'the copied files did contain the station id')

    def test_21_a_copied_session_token_dies_with_its_clock(self):
        """A stolen session is a bounded problem: it is short-lived and revocable."""
        dev = _Device()
        self._enroll(dev, 'register')
        _s, body, _ = self._authenticate(dev)
        token = body['session_token']
        session = self.env['mezze.station.session'].sudo().resolve(token)
        self.assertTrue(session)
        session.write({'expires_at': '2020-01-01 00:00:00'})
        self.assertFalse(self.env['mezze.station.session'].sudo().resolve(token),
                         'an expired session must resolve to nothing')

    # ------------------------------------------------ 4. role authorization
    def test_30_the_role_comes_from_the_code_not_from_the_client(self):
        dev = _Device()
        _act, raw = self._code('kds')                      # the operator cut a KDS code
        status, body = self._post('/enroll', {
            'activation_code': raw, 'device_uuid': dev.uuid,
            'public_key': dev.public_key_b64, 'security_level': 'a_tpm',
            # the client asks for more than it was granted:
            'station_role': 'register', 'branch_id': 999, 'company_id': 999,
            'role': 'administrator'})
        self.assertTrue(body['ok'], body)
        self.assertEqual(body['station_role'], 'kds', 'the client cannot choose its role')
        self.assertEqual(body['entry_surface'], '/mezze/kds')
        station = self.env['mezze.terminal'].sudo().search([('device_uuid', '=', dev.uuid)])
        self.assertEqual(station.role, 'kitchen')
        self.assertEqual(station.branch_id, self.pos_config, 'nor its branch')

    def test_31_editing_the_local_config_does_not_change_the_server_role(self):
        dev = _Device()
        self._enroll(dev, 'kds')
        # the attacker edits their local station.json to say 'register' and re-auths
        _s, ch = self._post('/challenge', {'device_uuid': dev.uuid})
        message = '%s|%s|%s' % (ch['protocol'], dev.uuid, ch['nonce'])
        _st, body = self._post('/auth', {'device_uuid': dev.uuid, 'nonce': ch['nonce'],
                                         'signature': dev.sign(message),
                                         'station_role': 'register',
                                         'entry_surface': '/mezze/pos'})
        self.assertEqual(body['station_role'], 'kds')
        self.assertEqual(body['entry_surface'], '/mezze/kds',
                         'the server tells the station what it is, every time')

    def test_32_a_kds_station_holds_only_kitchen_capabilities(self):
        from ..domain import authz
        dev = _Device()
        self._enroll(dev, 'kds')
        station = self.env['mezze.terminal'].sudo().search([('device_uuid', '=', dev.uuid)])
        caps = authz.capabilities_for(station.role)
        self.assertIn(authz.KITCHEN_READ, caps)
        for forbidden in (authz.ORDERS_REFUND, authz.ORDERS_PAY, authz.ADMIN_SETTINGS):
            self.assertNotIn(forbidden, caps,
                             'a kitchen screen must not hold %s' % forbidden)

    # ---------------------------------------------------- 5. revocation
    def test_40_revoking_one_station_leaves_its_neighbour_selling(self):
        a, b = _Device(), _Device()
        self._enroll(a, 'register')
        self._enroll(b, 'kds')
        self.assertTrue(self._authenticate(a)[1]['ok'])
        self.assertTrue(self._authenticate(b)[1]['ok'])

        station_a = self.env['mezze.terminal'].sudo().search([('device_uuid', '=', a.uuid)])
        station_a.revoke_station(reason='ws0 test')

        status, body, _ = self._authenticate(a)
        self.assertEqual(status, 403)
        self.assertEqual(body['error'], 'device_revoked')

        status_b, body_b, _ = self._authenticate(b)
        self.assertEqual(status_b, 200, body_b)
        self.assertTrue(body_b['ok'], 'revoking A must not touch B')

    def test_41_revocation_kills_a_live_session_immediately(self):
        dev = _Device()
        self._enroll(dev, 'register')
        _s, body, _ = self._authenticate(dev)
        token = body['session_token']
        self.assertTrue(self.env['mezze.station.session'].sudo().resolve(token))
        self.env['mezze.terminal'].sudo().search(
            [('device_uuid', '=', dev.uuid)]).revoke_station()
        self.assertFalse(self.env['mezze.station.session'].sudo().resolve(token),
                         'a revoked device must not keep an issued session alive')

    def test_42_a_revoked_device_cannot_re_enrol_with_a_fresh_code(self):
        dev = _Device()
        self._enroll(dev, 'register')
        self.env['mezze.terminal'].sudo().search(
            [('device_uuid', '=', dev.uuid)]).revoke_station()
        _act, raw = self._code('register')
        status, body, _ = self._enroll(dev, code=raw)
        self.assertEqual(status, 403)
        self.assertEqual(body['error'], 'device_revoked')

    # -------------------------------------------------------- 6. the lease
    def test_50_a_lease_is_signed_and_verifies_offline(self):
        dev = _Device()
        self._enroll(dev, 'register')
        _s, auth, _ = self._authenticate(dev)
        status, body = self._post('/lease', {'session_token': auth['session_token']})
        self.assertEqual(status, 200, body)
        lease = body['lease']
        payload = lease['payload']
        self.assertEqual(payload['role'], 'register')
        self.assertIn('payments', payload['features'])
        self.assertTrue(payload['expires_at'] > payload['issued_at'])
        self.assertGreaterEqual(payload['grace_days'], 1,
                                'a licensing outage must not stop a restaurant')
        # verified with the PUBLIC key alone, exactly as the station will offline
        pub = serialization.load_der_public_key(base64.b64decode(lease['public_key']))
        pub.verify(base64.b64decode(lease['signature']),
                   base64.b64decode(lease['payload_b64']), ec.ECDSA(hashes.SHA256()))

    def test_51_a_tampered_lease_fails_verification(self):
        dev = _Device()
        self._enroll(dev, 'register')
        _s, auth, _ = self._authenticate(dev)
        _st, body = self._post('/lease', {'session_token': auth['session_token']})
        lease = body['lease']
        forged = dict(lease['payload'], features=['payments', 'admin_everything'])
        forged_b64 = base64.b64encode(
            json.dumps(forged, sort_keys=True, separators=(',', ':')).encode())
        pub = serialization.load_der_public_key(base64.b64decode(lease['public_key']))
        from cryptography.exceptions import InvalidSignature
        with self.assertRaises(InvalidSignature):
            pub.verify(base64.b64decode(lease['signature']),
                       base64.b64decode(forged_b64), ec.ECDSA(hashes.SHA256()))

    def test_52_a_lease_cannot_be_fetched_for_another_station(self):
        a, b = _Device(), _Device()
        self._enroll(a, 'register')
        self._enroll(b, 'kds')
        _s, auth_b, _ = self._authenticate(b)
        _st, body = self._post('/lease', {'session_token': auth_b['session_token'],
                                          'device_uuid': a.uuid,
                                          'station_id': a.station_id})
        self.assertEqual(body['lease']['payload']['role'], 'kds',
                         'the session decides whose entitlement is returned')

    def test_53_no_session_no_lease(self):
        status, body = self._post('/lease', {'session_token': 'not-a-real-token'})
        self.assertEqual(status, 401)
        self.assertEqual(body['error'], 'session_invalid')

    # ------------------------------------------- 7. three stations, one server
    def test_60_three_independent_stations_on_one_server(self):
        register, kds, kiosk = _Device(), _Device(), _Device(level='b_dpapi')
        self._enroll(register, 'register')
        self._enroll(kds, 'kds')
        self._enroll(kiosk, 'kiosk')

        results = {}
        for name, dev in (('register', register), ('kds', kds), ('kiosk', kiosk)):
            _s, body, _ = self._authenticate(dev)
            self.assertTrue(body['ok'], body)
            results[name] = body

        self.assertEqual(results['register']['entry_surface'], '/mezze/pos')
        self.assertEqual(results['kds']['entry_surface'], '/mezze/kds')
        self.assertTrue(results['kiosk']['entry_surface'].startswith(
            '/mezze_bridge/static/kiosk.html'), results['kiosk']['entry_surface'])

        keys = self.env['mezze.terminal'].sudo().search(
            [('device_uuid', 'in', [register.uuid, kds.uuid, kiosk.uuid])])
        self.assertEqual(len(keys), 3)
        self.assertEqual(len(set(keys.mapped('public_key'))), 3, 'three distinct keys')
        self.assertEqual(len(set(keys.mapped('identifier'))), 3, 'three distinct identities')
        self.assertEqual(len(set(keys.mapped('device_uuid'))), 3)

    # ------------------------------------- 8. the station session at the gate
    def test_70_a_station_session_authenticates_a_normal_mezze_api_call(self):
        """The short-lived session is presented like any device token, so it flows
        through the ONE canonical gate — no second authorization path exists."""
        dev = _Device()
        self._enroll(dev, 'register')
        _s, auth, _ = self._authenticate(dev)
        resp = self.url_open('/mezze/api/v1/bootstrap',
                             data=json.dumps({}),
                             headers={'Content-Type': 'application/json',
                                      'X-Mezze-Token': auth['session_token']})
        self.assertEqual(resp.status_code, 200, resp.text[:200])
        self.assertNotIn('authentication_required', resp.text)

    def test_71_a_revoked_stations_session_is_refused_at_the_gate(self):
        dev = _Device()
        self._enroll(dev, 'register')
        _s, auth, _ = self._authenticate(dev)
        self.env['mezze.terminal'].sudo().search(
            [('device_uuid', '=', dev.uuid)]).revoke_station()
        resp = self.url_open('/mezze/api/v1/bootstrap',
                             data=json.dumps({}),
                             headers={'Content-Type': 'application/json',
                                      'X-Mezze-Token': auth['session_token']})
        self.assertIn(resp.status_code, (401, 403), resp.text[:200])

    def test_72_a_kitchen_station_cannot_take_money_by_calling_the_route_directly(self):
        """Server authority, stated as an attack.

        The KDS station has a valid session, a valid device key and a valid lease. It
        skips the UI entirely and posts to the payment route. Hiding a button is not the
        control — the capability check is, and it does not care which client called.

        The register station is the control: the SAME call from a station whose role
        holds ORDERS_PAY gets past authorization and fails later, on the business data,
        which is the correct place to fail.
        """
        kds, register = _Device(), _Device()
        self._enroll(kds, 'kds')
        self._enroll(register, 'register')
        _s, kds_auth, _ = self._authenticate(kds)
        _s, reg_auth, _ = self._authenticate(register)

        def pay_as(token):
            return self.url_open(
                '/mezze/api/v1/orders/pay',
                data=json.dumps({'order_id': 0, 'payments': []}),
                headers={'Content-Type': 'application/json', 'X-Mezze-Token': token})

        denied = pay_as(kds_auth['session_token'])
        self.assertIn('permission_denied', denied.text,
                      'a kitchen screen must not take a payment: %s' % denied.text[:200])

        allowed = pay_as(reg_auth['session_token'])
        self.assertNotIn('permission_denied', allowed.text,
                         'a register station holds ORDERS_PAY: %s' % allowed.text[:200])

    def test_73_no_station_role_can_refund_without_a_human_approver(self):
        """Refund is not a device capability in Mezze — it needs a supervisor's
        elevation. A Windows station changes nothing about that, which is exactly the
        property a productization layer must not quietly erode."""
        from ..domain import authz
        for station_role in ('register', 'kds', 'drivethru_payment'):
            dev = _Device()
            self._enroll(dev, station_role)
            station = self.env['mezze.terminal'].sudo().search([('device_uuid', '=', dev.uuid)])
            self.assertNotIn(authz.ORDERS_REFUND, authz.capabilities_for(station.role),
                             '%s must not hold refund on its own' % station_role)

    # --------------------------------------------------- 9. what is stored
    def test_80_no_permanent_station_secret_is_stored_on_the_server_either(self):
        dev = _Device()
        self._enroll(dev, 'register')
        _s, auth, _ = self._authenticate(dev)
        station = self.env['mezze.terminal'].sudo().search([('device_uuid', '=', dev.uuid)])
        self.assertFalse(station.token, 'a station never gets a permanent bearer token')
        session = self.env['mezze.station.session'].sudo().search(
            [('terminal_id', '=', station.id)], limit=1)
        self.assertTrue(session.token_fingerprint)
        self.assertNotIn(auth['session_token'], session.token_fingerprint,
                         'only a non-reversible fingerprint of the session is stored')

    def test_81_the_activation_code_is_not_stored_in_the_clear(self):
        _act, raw = self._code('register')
        rec = self.env['mezze.station.activation'].sudo().search([], order='id desc', limit=1)
        self.assertNotIn(raw, rec.code_fingerprint or '')
        self.assertNotIn(raw, json.dumps(rec.read()[0], default=str))
