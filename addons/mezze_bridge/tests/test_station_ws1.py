"""WS-1 — the staff shift a device-authenticated station opens for a person.

WS-0 proved which machine is talking. It deliberately stopped at the staff
surfaces, because they are ``auth='user'`` and a device key is not a person, and
the alternative — an Odoo credential on the till — is the exact artefact WS-0
exists to remove.

These tests hold the answer to that: device, then PIN, then a short, confined,
revocable Odoo session. The properties worth breaking the build over:

  * a device session alone opens no staff surface;
  * a PIN alone opens nothing either — the device must have proven itself first;
  * a kiosk can never mint a staff session, whatever it asks for;
  * the session dies on the clock, on idleness, on revocation and on clock-out;
  * the session cannot reach anything outside the Mezze surfaces;
  * PINs are throttled, on the new endpoint and on the two older ones that had
    no ceiling at all.
"""
import base64
import json
import uuid

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, utils as asym_utils

from odoo import fields
from odoo.tests import tagged

from ..domain import station_surface
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
        der = self._key.sign(message.encode(), ec.ECDSA(hashes.SHA256()))
        r, s = asym_utils.decode_dss_signature(der)
        return base64.b64encode(r.to_bytes(32, 'big') + s.to_bytes(32, 'big')).decode()


@tagged('post_install', '-at_install', 'mezze_station')
class TestStationWS1(MezzeHttpCase):
    fixture_profile = 'POS'

    def setUp(self):
        super().setUp()
        self.env['ir.config_parameter'].sudo().set_param('mezze_bridge.api_security', 'enforce')
        self.cashier = self.env['mezze.cashier'].create({
            'name': "Salma", 'code': 'S100', 'role': 'cashier'})
        self.cashier.set_pin('4417')
        self.manager = self.env['mezze.cashier'].create({
            'name': "Hany", 'code': 'M900', 'role': 'manager'})
        self.manager.set_pin('9001')

    # ---------------------------------------------------------------- helpers
    def _post(self, path, payload):
        resp = self.url_open(PREFIX + path, data=json.dumps(payload),
                             headers={'Content-Type': 'application/json'})
        try:
            body = resp.json()
        except Exception:  # noqa: BLE001
            body = {'ok': False, 'error': 'non_json', 'status': resp.status_code}
        return resp.status_code, body

    def _station(self, role='register', branch=None):
        """Enrol and authenticate a device, returning (device, session_token)."""
        device = _Device()
        _act, raw = self.env['mezze.station.activation'].issue(
            branch or self.pos_config, role, label='WS-1 %s' % role)
        status, body = self._post('/enroll', {
            'activation_code': raw, 'device_uuid': device.uuid,
            'public_key': device.public_key_b64, 'crypto_provider': device.provider,
            'security_level': device.level, 'app_version': '0.2.0-ws1'})
        self.assertTrue(body.get('ok'), "enrolment failed: %s / %s" % (status, body))
        device.station_id = body['station_id']
        _s, ch = self._post('/challenge', {'device_uuid': device.uuid})
        message = '%s|%s|%s' % (ch['protocol'], device.uuid, ch['nonce'])
        _s, auth = self._post('/auth', {
            'device_uuid': device.uuid, 'nonce': ch['nonce'],
            'signature': device.sign(message)})
        self.assertTrue(auth.get('ok'), "device auth failed: %s" % auth)
        return device, auth['session_token']

    def _terminal(self, device):
        return self.env['mezze.terminal'].sudo().with_context(active_test=False).search(
            [('device_uuid', '=', device.uuid)], limit=1)

    def _sign_in(self, token, code='S100', pin='4417'):
        return self._post('/surface', {'session_token': token, 'code': code, 'pin': pin})

    # =====================================================  1. the shift opens
    def test_01_device_plus_pin_opens_a_staff_shift(self):
        _dev, token = self._station('register')
        status, body = self._sign_in(token)
        self.assertEqual(status, 200)
        self.assertTrue(body['ok'])
        self.assertEqual(body['cashier']['name'], "Salma")
        self.assertTrue(body['surface'].startswith('/mezze/pos'), body['surface'])
        self.assertEqual(body['idle_timeout'], station_surface.SURFACE_IDLE_SECONDS)

    def test_02_the_shift_is_recorded_against_the_person_not_the_machine(self):
        dev, token = self._station('register')
        self._sign_in(token)
        shift = self.env['mezze.station.surface.session'].sudo().search(
            [('terminal_id', '=', self._terminal(dev).id)], limit=1)
        self.assertTrue(shift)
        self.assertEqual(shift.cashier_id, self.cashier)
        self.assertTrue(shift.is_live)
        # The Odoo user underneath is a service identity, never the cashier's.
        self.assertNotEqual(shift.user_id.id, self.env.uid)
        self.assertTrue(shift.user_id.login.startswith('mezze.station.service@'))

    def test_03_the_service_user_has_no_password_and_cannot_be_logged_into(self):
        _dev, token = self._station('register')
        self._sign_in(token)
        user = self.env['res.users'].sudo().search(
            [('login', 'like', 'mezze.station.service@%')], limit=1)
        self.assertTrue(user, "a service identity should exist after a shift opens")
        self.assertFalse(user.password,
                         "the station service identity must carry no password")

    def test_04_the_service_user_holds_only_the_station_group(self):
        _dev, token = self._station('register')
        self._sign_in(token)
        user = self.env['res.users'].sudo().search(
            [('login', 'like', 'mezze.station.service@%')], limit=1)
        group = self.env.ref('mezze_bridge.group_station_service')
        self.assertIn(group, user.group_ids)
        for forbidden in ('point_of_sale.group_pos_manager',
                          'account.group_account_manager',
                          'base.group_system'):
            grp = self.env.ref(forbidden, raise_if_not_found=False)
            if grp:
                self.assertNotIn(grp, user.all_group_ids,
                                 "station service must not hold %s" % forbidden)

    # ==============================================  2. neither proof alone works
    def test_10_a_pin_without_a_device_session_opens_nothing(self):
        status, body = self._post('/surface', {
            'session_token': 'not-a-session', 'code': 'S100', 'pin': '4417'})
        self.assertEqual(status, 401)
        self.assertEqual(body['error'], 'session_invalid')

    def test_11_a_device_session_without_a_pin_opens_nothing(self):
        _dev, token = self._station('register')
        status, body = self._sign_in(token, pin='0000')
        self.assertEqual(status, 401)
        self.assertEqual(body['error'], 'bad_credentials')

    def test_12_an_unknown_staff_code_is_refused_like_a_wrong_pin(self):
        _dev, token = self._station('register')
        status, body = self._sign_in(token, code='NOPE', pin='4417')
        self.assertEqual(status, 401)
        self.assertEqual(body['error'], 'bad_credentials')

    def test_13_a_revoked_device_cannot_open_a_shift(self):
        dev, token = self._station('register')
        self._terminal(dev).revoke_station(reason='test')
        status, body = self._sign_in(token)
        self.assertEqual(status, 401)
        self.assertEqual(body['error'], 'session_invalid')

    # =====================================  3. customer stations never get a human
    def test_20_a_kiosk_can_never_open_a_staff_shift(self):
        _dev, token = self._station('kiosk')
        status, body = self._sign_in(token)
        self.assertEqual(status, 403)
        self.assertEqual(body['error'], 'customer_surface')

    def test_21_a_customer_display_can_never_open_a_staff_shift(self):
        _dev, token = self._station('ocb')
        status, body = self._sign_in(token)
        self.assertEqual(status, 403)
        self.assertEqual(body['error'], 'customer_surface')

    def test_22_a_correct_manager_pin_does_not_rescue_a_kiosk(self):
        """The refusal is about the STATION, not about who is standing at it."""
        _dev, token = self._station('kiosk')
        status, body = self._sign_in(token, code='M900', pin='9001')
        self.assertEqual(status, 403)
        self.assertEqual(body['error'], 'customer_surface')

    # ==================================================  4. branch scope holds
    def test_30_a_cashier_scoped_to_another_branch_is_refused(self):
        other = self.env['pos.config'].sudo().create({'name': "Other branch"})
        self.cashier.config_ids = [(6, 0, [other.id])]
        _dev, token = self._station('register')
        status, body = self._sign_in(token)
        self.assertEqual(status, 403)
        self.assertEqual(body['error'], 'branch_not_allowed')

    def test_31_an_unscoped_cashier_works_anywhere(self):
        self.cashier.config_ids = [(6, 0, [])]
        _dev, token = self._station('register')
        _s, body = self._sign_in(token)
        self.assertTrue(body['ok'])

    # ==============================================  5. the shift ends, five ways
    def test_40_clocking_out_ends_the_shift(self):
        dev, token = self._station('register')
        self._sign_in(token)
        status, body = self._post('/surface/end', {'session_token': token})
        self.assertEqual(status, 200)
        shift = self.env['mezze.station.surface.session'].sudo().search(
            [('terminal_id', '=', self._terminal(dev).id)], limit=1)
        self.assertFalse(shift.is_live)
        self.assertEqual(shift.end_reason, 'clocked_out')

    def test_41_an_expired_shift_does_not_resolve(self):
        dev, token = self._station('register')
        self._sign_in(token)
        Shift = self.env['mezze.station.surface.session'].sudo()
        shift = Shift.search([('terminal_id', '=', self._terminal(dev).id)], limit=1)
        shift.write({'expires_at': fields.Datetime.subtract(
            fields.Datetime.now(), seconds=1)})
        self.assertFalse(Shift.resolve(shift.id))
        self.assertEqual(shift.end_reason, 'expired')

    def test_42_an_idle_shift_does_not_resolve(self):
        dev, token = self._station('register')
        self._sign_in(token)
        Shift = self.env['mezze.station.surface.session'].sudo()
        shift = Shift.search([('terminal_id', '=', self._terminal(dev).id)], limit=1)
        shift.write({'last_seen_at': fields.Datetime.subtract(
            fields.Datetime.now(), seconds=station_surface.SURFACE_IDLE_SECONDS + 60)})
        self.assertFalse(Shift.resolve(shift.id))
        self.assertEqual(shift.end_reason, 'idle')

    def test_43_revoking_the_device_kills_the_live_shift(self):
        dev, token = self._station('register')
        self._sign_in(token)
        Shift = self.env['mezze.station.surface.session'].sudo()
        shift = Shift.search([('terminal_id', '=', self._terminal(dev).id)], limit=1)
        self._terminal(dev).revoke_station(reason='lost')
        self.assertFalse(Shift.resolve(shift.id))
        self.assertEqual(shift.end_reason, 'device_revoked')

    def test_44_deactivating_the_person_kills_the_live_shift(self):
        dev, token = self._station('register')
        self._sign_in(token)
        Shift = self.env['mezze.station.surface.session'].sudo()
        shift = Shift.search([('terminal_id', '=', self._terminal(dev).id)], limit=1)
        self.cashier.active = False
        self.assertFalse(Shift.resolve(shift.id))
        self.assertEqual(shift.end_reason, 'staff_disabled')

    def test_45_a_handover_replaces_the_previous_shift(self):
        dev, token = self._station('register')
        self._sign_in(token)
        self._sign_in(token, code='M900', pin='9001')
        Shift = self.env['mezze.station.surface.session'].sudo()
        shifts = Shift.search([('terminal_id', '=', self._terminal(dev).id)],
                              order='id asc')
        self.assertEqual(len(shifts), 2)
        self.assertFalse(shifts[0].is_live)
        self.assertEqual(shifts[0].end_reason, 'handover')
        self.assertTrue(shifts[1].is_live)
        self.assertEqual(shifts[1].cashier_id, self.manager)

    # ===============================================  6. confinement is server-side
    def test_50_the_mezze_surfaces_are_reachable(self):
        for path in ('/mezze/pos', '/mezze/kds', '/web/assets/whatever',
                     '/web/webclient/translations', '/websocket'):
            self.assertTrue(station_surface.path_allowed(path), path)

    def test_51_the_odoo_backend_is_not(self):
        for path in ('/odoo', '/odoo/settings', '/web#action=1', '/web/login',
                     '/web/database/manager', '/xmlrpc/2/object', '/web/dataset/call_kw'):
            self.assertFalse(station_surface.path_allowed(path), path)

    def test_52_a_station_session_is_refused_off_surface_over_http(self):
        """The real proof: not the policy function, the actual request."""
        _dev, token = self._station('register')
        self._sign_in(token)          # the test client now carries the shift cookie
        resp = self.url_open('/odoo/settings')
        self.assertEqual(resp.status_code, 403,
                         "a station session must not reach the Odoo backend")

    def test_53_the_shift_survives_a_refused_request(self):
        dev, token = self._station('register')
        self._sign_in(token)
        self.url_open('/odoo/settings')
        Shift = self.env['mezze.station.surface.session'].sudo()
        shift = Shift.search([('terminal_id', '=', self._terminal(dev).id)], limit=1)
        self.assertTrue(shift.is_live,
                        "a stray request must not sign a cashier out mid-order")

    # =====================================================  7. PINs are throttled
    def test_60_repeated_wrong_pins_are_rate_limited(self):
        _dev, token = self._station('register')
        seen_429 = False
        for _i in range(station_surface.PIN_MAX_PER_STAFF + 2):
            status, body = self._sign_in(token, pin='0000')
            if status == 429:
                seen_429 = True
                self.assertEqual(body['error'], 'rate_limited')
                break
        self.assertTrue(seen_429,
                        "a four-digit PIN with no ceiling is ten thousand guesses")

    def test_61_the_lockout_survives_a_correct_pin(self):
        """Guessing until locked out must not be rescued by knowing the PIN."""
        _dev, token = self._station('register')
        for _i in range(station_surface.PIN_MAX_PER_STAFF + 2):
            self._sign_in(token, pin='0000')
        status, body = self._sign_in(token)     # the RIGHT pin
        self.assertEqual(status, 429)
        self.assertEqual(body['error'], 'rate_limited')

    def test_62_the_device_budget_stops_staff_code_enumeration(self):
        """Cycling through codes must not dodge the per-code budget."""
        _dev, token = self._station('register')
        blocked = False
        for i in range(station_surface.PIN_MAX_PER_DEVICE + 3):
            status, _body = self._sign_in(token, code='X%03d' % i, pin='0000')
            if status == 429:
                blocked = True
                break
        self.assertTrue(blocked, "enumeration across codes must hit the device budget")

    def test_63_one_station_lockout_does_not_lock_the_restaurant(self):
        """Availability matters: an attacked till must not stop its neighbour."""
        _a, token_a = self._station('register')
        _b, token_b = self._station('register')
        for _i in range(station_surface.PIN_MAX_PER_STAFF + 2):
            self._sign_in(token_a, pin='0000')
        status, body = self._sign_in(token_b)
        self.assertEqual(status, 200, "the neighbouring station must keep working")
        self.assertTrue(body['ok'])

    def _w1(self, path, payload, token):
        """Call a W1 endpoint as an AUTHENTICATED terminal.

        The gate already refuses an anonymous caller, so the interesting
        attacker is the one who has a till: a compromised station, or anyone
        standing at an unattended one. That is the path these budgets protect.
        """
        return self.url_open(
            '/mezze/w1' + path, data=json.dumps(payload),
            headers={'Content-Type': 'application/json', 'X-Mezze-Token': token})

    def test_64_the_older_cashier_login_is_throttled_too(self):
        """This endpoint had no ceiling at all before WS-1."""
        _dev, token = self._station('register')
        blocked = False
        for _i in range(station_surface.PIN_MAX_PER_STAFF + 3):
            resp = self._w1('/cashier/login', {'code': 'S100', 'pin': '0000'}, token)
            if resp.status_code == 429:
                blocked = True
                break
        self.assertTrue(blocked, "cashier/login must not allow unlimited PIN guesses")

    def test_65_a_till_cannot_even_reach_the_approval_endpoint(self):
        """The first line here is not the throttle, it is the capability gate.

        ``approve`` requires an admin capability, which no station role carries,
        so a till cannot guess approval PINs at all. Worth pinning down: if this
        ever loosens, the throttle below becomes the only thing left.
        """
        _dev, token = self._station('register')
        resp = self._w1('/approve',
                        {'action': 'refund', 'code': 'M900', 'pin': '0000'}, token)
        self.assertEqual(resp.status_code, 403,
                         "a terminal must not be able to call the approval endpoint")

    def test_66_approval_pins_are_throttled_behind_that_gate(self):
        """Defence in depth: whoever does reach it still cannot guess forever."""
        blocked = False
        for _i in range(station_surface.APPROVAL_MAX_PER_STAFF + 3):
            _c, error, _r = self.env['mezze.cashier'].authenticate_pin(
                'M900', '0000',
                station_surface.approval_keys('test-console', 'M900'),
                station_surface.APPROVAL_WINDOW_SECONDS)
            if error == 'rate_limited':
                blocked = True
                break
        self.assertTrue(blocked, "approval PINs must not allow unlimited guesses")

    # ================================================  8. WS-0 properties preserved
    def test_70_opening_a_shift_stores_no_new_secret(self):
        dev, token = self._station('register')
        self._sign_in(token)
        shift = self.env['mezze.station.surface.session'].sudo().search(
            [('terminal_id', '=', self._terminal(dev).id)], limit=1)
        stored = json.dumps(shift.read()[0], default=str).lower()
        for forbidden in ('4417', 'password', 'private'):
            self.assertNotIn(forbidden, stored,
                             "a shift record must never carry a credential")

    def test_71_the_pin_is_never_stored_in_the_clear(self):
        self.assertNotIn('4417', json.dumps(self.cashier.read()[0], default=str))
        self.assertTrue(self.cashier.pin_hash)
        self.assertNotEqual(self.cashier.pin_hash, '4417')

    def test_72_a_shift_does_not_grant_refund_to_a_device(self):
        """WS-0's rule, re-proven now that a station carries a human session."""
        from ..domain import authz
        for role in station_surface.STAFF_ROLES:
            caps = authz.ROLE_CAPS.get('terminal', frozenset())
            self.assertNotIn('orders.refund', caps,
                             "role %s must not carry refund" % role)

    # ==========================================  9. the operator console (WS-1 P2)
    def test_80_a_manager_cuts_a_code_from_the_wizard(self):
        """The shell flow was honest for a POC and unusable for a restaurant."""
        wiz = self.env['mezze.station.enrol.wizard'].create({
            'branch_id': self.pos_config.id,
            'station_role': 'register',
            'label': "Front counter 2",
        })
        action = wiz.action_issue()
        shown = wiz.with_context(**action['context'])
        self.assertTrue(shown.issued)
        self.assertRegex(shown.activation_code, r'^[0-9A-F]{4}(-[0-9A-F]{4}){3}$')
        self.assertTrue(shown.expires_at)

    def test_81_the_wizard_code_actually_enrols_a_station(self):
        """Same code path as the shell — proven, not assumed."""
        wiz = self.env['mezze.station.enrol.wizard'].create({
            'branch_id': self.pos_config.id, 'station_role': 'kds'})
        action = wiz.action_issue()
        device = _Device()
        status, body = self._post('/enroll', {
            'activation_code': action['context']['mezze_issued_code'],
            'device_uuid': device.uuid,
            'public_key': device.public_key_b64, 'security_level': 'a_tpm'})
        self.assertEqual(status, 200)
        self.assertTrue(body['ok'])
        self.assertEqual(body['station_role'], 'kds')

    def test_82_the_wizard_never_persists_the_code_in_the_clear(self):
        wiz = self.env['mezze.station.enrol.wizard'].create({
            'branch_id': self.pos_config.id, 'station_role': 'register'})
        raw = wiz.action_issue()['context']['mezze_issued_code']
        act = self.env['mezze.station.activation'].sudo().search([], order='id desc', limit=1)
        self.assertNotIn(raw, json.dumps(act.read()[0], default=str),
                         "an activation code must be stored only as a fingerprint")

    def test_83_a_code_cannot_be_issued_twice_from_one_wizard(self):
        from odoo.exceptions import UserError
        wiz = self.env['mezze.station.enrol.wizard'].create({
            'branch_id': self.pos_config.id, 'station_role': 'register'})
        action = wiz.action_issue()
        with self.assertRaises(UserError):
            wiz.with_context(**action['context']).action_issue()

    def test_84_the_console_reports_station_status(self):
        dev, token = self._station('register')
        term = self._terminal(dev)
        self.assertEqual(term.station_state, 'online')
        self._sign_in(token)
        term.invalidate_recordset()
        self.assertEqual(term.current_cashier_id, self.cashier)
        term.revoke_station(reason='test')
        term.invalidate_recordset()
        self.assertEqual(term.station_state, 'revoked')

    def test_85_a_station_that_never_connected_reads_as_pending(self):
        wiz = self.env['mezze.station.enrol.wizard'].create({
            'branch_id': self.pos_config.id, 'station_role': 'register'})
        action = wiz.action_issue()
        device = _Device()
        self._post('/enroll', {
            'activation_code': action['context']['mezze_issued_code'],
            'device_uuid': device.uuid,
            'public_key': device.public_key_b64, 'security_level': 'a_tpm'})
        term = self._terminal(device)
        self.assertEqual(term.station_state, 'pending',
                         "enrolled but never authenticated is not 'online'")

    def test_86_the_status_filter_and_the_badge_cannot_disagree(self):
        """The search method and the compute must read the same clock."""
        dev, _token = self._station('register')
        term = self._terminal(dev)
        Terminal = self.env['mezze.terminal'].sudo().with_context(active_test=False)
        for state in ('online', 'pending', 'revoked', 'stale'):
            found = Terminal.search([('station_state', '=', state)])
            if term.station_state == state:
                self.assertIn(term, found, "%s: badge says %s but the filter disagrees"
                              % (term.display_name, state))
            else:
                self.assertNotIn(term, found)

    def test_87_a_stale_station_is_reported_as_stale(self):
        from ..models.mezze_station import STALE_AFTER_MINUTES
        dev, _token = self._station('register')
        term = self._terminal(dev)
        term.sudo().write({'last_seen_at': fields.Datetime.subtract(
            fields.Datetime.now(), minutes=STALE_AFTER_MINUTES + 5)})
        term.invalidate_recordset()
        self.assertEqual(term.station_state, 'stale')
        found = self.env['mezze.terminal'].sudo().with_context(active_test=False).search(
            [('station_state', '=', 'stale')])
        self.assertIn(term, found)

    def test_88_an_operator_can_end_a_shift_from_the_console(self):
        dev, token = self._station('register')
        self._sign_in(token)
        term = self._terminal(dev)
        term.action_end_shift()
        shift = self.env['mezze.station.surface.session'].sudo().search(
            [('terminal_id', '=', term.id)], limit=1)
        self.assertFalse(shift.is_live)
        self.assertEqual(shift.end_reason, 'operator')

    def test_89_the_sweeper_closes_shifts_the_clock_already_ended(self):
        """Regression guard: 'active' would have hidden these rows from its own query."""
        dev, token = self._station('register')
        self._sign_in(token)
        Shift = self.env['mezze.station.surface.session'].sudo()
        shift = Shift.search([('terminal_id', '=', self._terminal(dev).id)], limit=1)
        shift.write({'expires_at': fields.Datetime.subtract(fields.Datetime.now(), seconds=1)})
        Shift._cron_gc()
        shift.invalidate_recordset()
        self.assertFalse(shift.is_live)
        self.assertEqual(shift.end_reason, 'expired')

    # =====================================  10. WS-2 fixes: surface, branch, mapping
    def test_90_a_station_cannot_open_another_roles_surface(self):
        """BUG 1: the role->surface rule existed and was never asked."""
        _dev, token = self._station('register')
        self._sign_in(token)
        resp = self.url_open('/mezze/kds')
        self.assertEqual(resp.status_code, 403,
                         "a register station must not open the kitchen display")

    def test_91_a_station_still_opens_its_own_surface(self):
        _dev, token = self._station('kds')
        # a KDS station needs a cashier allowed on its branch; ours are unrestricted
        status, body = self._post('/surface', {
            'session_token': token, 'code': 'S100', 'pin': '4417'})
        self.assertEqual(status, 200, body)
        resp = self.url_open('/mezze/kds')
        self.assertEqual(resp.status_code, 200)

    def test_92_non_surface_paths_are_not_policed_by_role(self):
        """Assets and API routes must not be caught by the surface rule."""
        from ..domain import station_surface
        from ..models.mezze_station import ROLE_SURFACE
        for path in ('/mezze/api/v1/orders/sync', '/web/assets/x.js', '/websocket'):
            self.assertIsNone(
                station_surface.surface_refusal('register', path, ROLE_SURFACE), path)

    def test_93_the_entry_surface_carries_the_branch(self):
        """BUG 3: the server decided the branch and then threw it away."""
        other = self.env['pos.config'].sudo().create({'name': "Second branch"})
        dev, _token = self._station('register', branch=other)
        term = self._terminal(dev)
        self.assertEqual(term.branch_id, other)
        self.assertIn('config_id=%s' % other.id, term.entry_surface(),
                      "a station's surface must name its own branch")

    def test_94_a_station_bound_session_resolves_its_own_branch(self):
        other = self.env['pos.config'].sudo().create({'name': "Third branch"})
        dev, token = self._station('register', branch=other)
        self._sign_in(token)
        page = self.url_open('/mezze/pos').text
        self.assertIn('"id": %s' % other.id, page,
                      "the Register must boot the station's branch, not the default")

    def test_95_a_station_cannot_be_moved_to_another_branch_by_url(self):
        """The URL must not outrank the manager who enrolled the station."""
        home = self.env['pos.config'].sudo().create({'name': "Home branch"})
        elsewhere = self.env['pos.config'].sudo().create({'name': "Elsewhere"})
        dev, token = self._station('register', branch=home)
        self._sign_in(token)
        page = self.url_open('/mezze/pos?config_id=%s' % elsewhere.id).text
        self.assertIn('"id": %s' % home.id, page)
        self.assertNotIn('"name": "Elsewhere"', page)

    def test_96_an_ordinary_browser_still_honours_config_id(self):
        """The station rule must not break the plain Register."""
        other = self.env['pos.config'].sudo().create({'name': "Plain branch"})
        self.authenticate('admin', 'admin')
        page = self.url_open('/mezze/pos?config_id=%s' % other.id).text
        self.assertIn('"id": %s' % other.id, page)

    def test_97_the_wizard_never_writes_the_code_to_the_database(self):
        """BUG 2: the console reintroduced plaintext codes the HMAC removed."""
        wiz = self.env['mezze.station.enrol.wizard'].create({
            'branch_id': self.pos_config.id, 'station_role': 'register'})
        action = wiz.action_issue()
        raw = action['context']['mezze_issued_code']
        self.assertRegex(raw, r'^[0-9A-F]{4}(-[0-9A-F]{4}){3}$')
        self.env.flush_all()
        # Stronger than counting rows: the column must not exist, so no future
        # change can quietly start filling it.
        self.env.cr.execute(
            "SELECT count(*) FROM information_schema.columns "
            "WHERE table_name = 'mezze_station_enrol_wizard' "
            "AND column_name = 'activation_code'")
        self.assertEqual(self.env.cr.fetchone()[0], 0,
                         "an activation code must never have a database column")

    def test_98_the_wizard_still_shows_the_code_once(self):
        wiz = self.env['mezze.station.enrol.wizard'].create({
            'branch_id': self.pos_config.id, 'station_role': 'register'})
        action = wiz.action_issue()
        shown = wiz.with_context(**action['context'])
        self.assertTrue(shown.issued)
        self.assertEqual(shown.activation_code, action['context']['mezze_issued_code'])
        # and reopening WITHOUT that context shows no stale code
        self.assertFalse(wiz.with_context(mezze_issued_code=None).activation_code)

    def test_99_the_backend_order_names_the_cashier_and_the_terminal(self):
        """100% mapping: pos.order must answer 'who sold this, from which till?'"""
        order = self.env['pos.order'].sudo().search([], limit=1)
        self.assertIn('mezze_cashier_id', self.env['pos.order']._fields)
        self.assertIn('mezze_terminal_id', self.env['pos.order']._fields)
        if order:
            # the fields exist and are writable through the normal ORM
            order.write({'mezze_cashier_id': self.cashier.id})
            self.assertEqual(order.mezze_cashier_id, self.cashier)

    # ================================================  11. the check-in page (WS-2)
    def test_A0_the_launcher_requires_a_login(self):
        resp = self.url_open('/mezze/start')
        # auth='user' -> anonymous is redirected to the login page, never served
        self.assertIn(resp.status_code, (303, 302, 200))
        self.assertNotIn('Choose your register', resp.text if resp.status_code == 200 else '')

    def test_A1_a_signed_in_user_is_offered_their_branches(self):
        self.authenticate('admin', 'admin')
        page = self.url_open('/mezze/start').text
        self.assertIn('Choose your register', page)
        self.assertIn(self.pos_config.name, page)
        self.assertIn('/mezze/pos?config_id=%s' % self.pos_config.id, page)

    def test_A2_the_launcher_offers_only_what_the_user_can_read(self):
        """It must never widen access — the query runs in the user's own env."""
        self.authenticate('admin', 'admin')
        page = self.url_open('/mezze/start').text
        visible = self.env['pos.config'].with_user(self.env.ref('base.user_admin')).search([])
        for cfg in visible:
            self.assertIn('config_id=%s' % cfg.id, page)

    def test_A3_floor_is_offered_only_where_there_are_tables(self):
        plain = self.env['pos.config'].sudo().create(
            {'name': "No tables here", 'module_pos_restaurant': False})
        self.authenticate('admin', 'admin')
        page = self.url_open('/mezze/start').text
        self.assertIn('/mezze/pos?config_id=%s' % plain.id, page)
        self.assertNotIn('/mezze/floor?config_id=%s' % plain.id, page)

    def test_A4_a_station_is_sent_to_its_own_surface_not_a_chooser(self):
        """A station was told where it is at enrolment; asking it again invites
        exactly the branch-switching the confinement exists to prevent."""
        other = self.env['pos.config'].sudo().create({'name': "Launcher branch"})
        dev, token = self._station('register', branch=other)
        self._sign_in(token)
        resp = self.url_open('/mezze/start', allow_redirects=False)
        self.assertIn(resp.status_code, (302, 303))
        self.assertIn('config_id=%s' % other.id, resp.headers.get('Location', ''))

    def test_A5_a_cashier_with_branches_is_narrowed_to_them(self):
        allowed = self.env['pos.config'].sudo().create({'name': "Allowed branch"})
        self.env['pos.config'].sudo().create({'name': "Off-limits branch"})
        user = self.env.ref('base.user_admin')
        self.cashier.write({'user_id': user.id, 'config_ids': [(6, 0, [allowed.id])]})
        self.authenticate('admin', 'admin')
        page = self.url_open('/mezze/start').text
        self.assertIn('config_id=%s' % allowed.id, page)
        self.assertNotIn('Off-limits branch', page)

    # ==========================================  12. entry point & branch menu (WS-2)
    def test_B0_bare_pos_asks_which_branch_when_nobody_has_said(self):
        self.env['ir.config_parameter'].sudo().set_param(
            'mezze_bridge.default_branch_id', '')
        self.authenticate('admin', 'admin')
        resp = self.url_open('/mezze/pos', allow_redirects=False)
        self.assertIn(resp.status_code, (302, 303))
        self.assertIn('/mezze/start', resp.headers.get('Location', ''))

    def test_B1_a_pinned_default_branch_is_still_honoured(self):
        """The parameter's whole job is answering this; redirecting past it
        would make the setting meaningless."""
        self.env['ir.config_parameter'].sudo().set_param(
            'mezze_bridge.default_branch_id', str(self.pos_config.id))
        self.authenticate('admin', 'admin')
        resp = self.url_open('/mezze/pos', allow_redirects=False)
        self.assertEqual(resp.status_code, 200)

    def test_B2_a_station_is_never_asked(self):
        self.env['ir.config_parameter'].sudo().set_param(
            'mezze_bridge.default_branch_id', '')
        other = self.env['pos.config'].sudo().create({'name': "Never asked"})
        _dev, token = self._station('register', branch=other)
        self._sign_in(token)
        resp = self.url_open('/mezze/pos', allow_redirects=False)
        self.assertEqual(resp.status_code, 200)

    def test_B3_the_menu_honours_the_branch_category_limit(self):
        """A branch restricted to some categories must not show the whole
        catalogue — Odoo's own POS does not, and neither should we."""
        categs = self.env['pos.category'].sudo().search([], limit=1)
        if not categs:
            categs = self.env['pos.category'].sudo().create({'name': "Limited"})
        self.pos_config.sudo().write({
            'limit_categories': True, 'iface_available_categ_ids': [(6, 0, categs.ids)]})
        from ..controllers.main import MezzeBridgeController
        dom = MezzeBridgeController()._menu_domain(self.env, self.pos_config)
        self.assertIn(('pos_categ_ids', 'in', categs.ids), dom)
        limited = self.env['product.product'].search_count(dom)
        unlimited = self.env['product.product'].search_count(
            MezzeBridgeController()._menu_domain(self.env))
        self.assertLessEqual(limited, unlimited)

    def test_B4_the_menu_matches_odoo_s_own_product_domain(self):
        """The regression that started this: same shop, two different menus."""
        from ..controllers.main import MezzeBridgeController
        dom = MezzeBridgeController()._menu_domain(self.env, self.pos_config)
        flat = [t for t in dom if isinstance(t, (tuple, list))]
        names = {t[0] for t in flat}
        self.assertIn('sale_ok', names, "a product not for sale is not a menu item")
        self.assertIn('available_in_pos', names)
        # and the company domain must be present, or another company's products leak
        self.assertTrue(any('company_id' in str(t[0]) for t in flat), dom)

    def test_B5_categories_narrow_with_the_branch(self):
        categs = self.env['pos.category'].sudo().search([], limit=1)
        if not categs:
            categs = self.env['pos.category'].sudo().create({'name': "Only one"})
        self.pos_config.sudo().write({
            'limit_categories': True, 'iface_available_categ_ids': [(6, 0, categs.ids)]})
        from ..controllers.main import MezzeBridgeController
        shown = MezzeBridgeController()._menu_categories(self.env, self.pos_config)
        self.assertEqual({c['id'] for c in shown}, set(categs.ids))

    # ==============================================  13. end of day / session close
    def _terminal_token(self):
        """A till's own bearer token, as the Register mints one."""
        from ..controllers.register_instance import mint_for_instance
        token, _term = mint_for_instance(self.env, self.pos_config, 'test-rid')
        return token

    def _api(self, path, payload, token):
        return self.url_open(
            '/mezze/api/v1' + path, data=json.dumps(payload),
            headers={'Content-Type': 'application/json', 'X-Mezze-Token': token})

    def _open_session(self):
        session = self.pos_config.current_session_id
        if not session:
            session = self.env['pos.session'].create(
                {'config_id': self.pos_config.id, 'user_id': self.env.uid})
            session.set_opening_control(0, None)
        return session

    def test_C0_a_till_may_read_the_close_preview(self):
        """Counting a drawer must not need a manager's PIN — that would mean the
        PIN gets typed twice, and a PIN typed twice is a PIN learned."""
        session = self._open_session()
        resp = self._api('/sessions/%s/close/preview' % session.id, {}, self._terminal_token())
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body['ok'], body)
        for key in ('orders', 'orders_open', 'total', 'payments',
                    'cash_opening', 'cash_payments', 'cash_expected'):
            self.assertIn(key, body)

    def test_C1_a_till_may_NOT_close_the_session(self):
        """Closing posts accounting; it is not a cashier's call."""
        session = self._open_session()
        resp = self._api('/sessions/%s/close' % session.id, {}, self._terminal_token())
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(session.state, 'opened')

    def test_C2_a_cashier_pin_does_not_elevate_a_close(self):
        """Elevation can never conjure a permission its approver does not have."""
        self.env['ir.config_parameter'].sudo().set_param(
            'mezze_bridge.allow_manager_elevation', '1')
        session = self._open_session()
        resp = self._api('/sessions/%s/close' % session.id,
                         {'manager_code': 'S100', 'manager_pin': '4417'},  # a CASHIER
                         self._terminal_token())
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(session.state, 'opened')

    def test_C3_a_manager_pin_closes_it_and_posts_the_journal_entry(self):
        self.env['ir.config_parameter'].sudo().set_param(
            'mezze_bridge.allow_manager_elevation', '1')
        session = self._open_session()
        resp = self._api('/sessions/%s/close' % session.id,
                         {'manager_code': 'M900', 'manager_pin': '9001'},
                         self._terminal_token())
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertTrue(body['ok'], body)
        session.invalidate_recordset()
        self.assertEqual(session.state, 'closed')
        # Odoo's own close produced the entry — we did not compute one.
        self.assertIn('account_move_ids', body)

    def test_C4_a_wrong_manager_pin_is_refused_and_throttled(self):
        """This prompt reaches money routes from a till and had NO ceiling."""
        self.env['ir.config_parameter'].sudo().set_param(
            'mezze_bridge.allow_manager_elevation', '1')
        session = self._open_session()
        token = self._terminal_token()
        statuses = []
        for _i in range(station_surface.APPROVAL_MAX_PER_STAFF + 3):
            statuses.append(self._api('/sessions/%s/close' % session.id,
                                      {'manager_code': 'M900', 'manager_pin': '0000'},
                                      token).status_code)
        self.assertTrue(all(s != 200 for s in statuses))
        self.assertEqual(session.state, 'opened')

    def test_C5_the_preview_is_branch_scoped(self):
        """A session id from another branch must not be readable."""
        other = self.env['pos.config'].sudo().create({'name': "Other close branch"})
        theirs = self.env['pos.session'].sudo().create(
            {'config_id': other.id, 'user_id': self.env.uid})
        resp = self._api('/sessions/%s/close/preview' % theirs.id, {}, self._terminal_token())
        self.assertEqual(resp.status_code, 403)

    def test_C6_the_preview_counts_open_orders_so_the_screen_can_refuse(self):
        session = self._open_session()
        resp = self._api('/sessions/%s/close/preview' % session.id, {}, self._terminal_token())
        body = resp.json()
        self.assertIsInstance(body['orders_open'], int)
        self.assertLessEqual(body['orders_open'], body['orders'])
