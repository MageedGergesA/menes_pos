# Part of the Mezze POS platform. See LICENSE (LGPL-3).
"""WS-0 — the Mezze Station protocol.

Five endpoints, and none of them ever hands out a permanent secret:

  POST /mezze/station/v1/enroll     one-time activation code + public key -> identity
  POST /mezze/station/v1/challenge  device id -> single-use server nonce
  POST /mezze/station/v1/auth       signed nonce -> SHORT-LIVED session + role + surface
  POST /mezze/station/v1/lease      session -> signed, offline-verifiable entitlement
  GET  /mezze/station/v1/health     server time, minimum client version, lease public key

They are `auth='none'` because the caller is a machine proving possession of a
private key, not an Odoo user — the same reason ``cashier/login`` is classified
public: they ARE the authentication. Everything a station does afterwards goes
through the one canonical security gate with the terminal's least-privilege
capabilities, so nothing here widens the authorised surface.

What deliberately does NOT exist here: any route that returns a long-lived token,
any route that trusts a client-asserted role, branch or company, and any route that
accepts a hardware serial as identity.
"""
import logging

from odoo import SUPERUSER_ID, fields, http
from odoo.http import request

from ..domain import station_crypto, station_surface
from ..models.mezze_station import PROTOCOL, ROLE_SURFACE, SECURITY_LEVELS
from .main import MezzeBridgeController

_logger = logging.getLogger(__name__)

STATION_PREFIX = '/mezze/station/v1'   # documented here; routes spell it out
                                       # literally so the structural endpoint
                                       # inventory can classify them

# What a station may claim about its own key protection. The server records the
# claim and the POLICY reads it; it never upgrades a claim on the station's word.
_CLAIMED_LEVELS = {code for code, _label in SECURITY_LEVELS}


class MezzeStationController(http.Controller):

    _bridge = MezzeBridgeController()

    # ------------------------------------------------------------------ utils
    def _env(self):
        return request.env(su=True)

    def _staff_env(self):
        """An environment with an acting user, for the routes that WRITE.

        The protocol routes are auth='none' by necessity, which leaves env.uid
        as None. That is harmless while only simple Mezze rows are written, and
        it is not harmless once a shift creates a user and an avatar.
        """
        # update_env, not just env(...): it also re-points
        # transaction.default_env, which is the environment that runs deferred
        # recomputes at flush time. Returning a bare superuser env would leave
        # the flush running as nobody, which is how creating the service user
        # fails several frames away from the code that caused it.
        request.update_env(user=SUPERUSER_ID, su=True)
        return request.env

    def _json(self, payload, status=200):
        return request.make_json_response(payload, status=status)

    def _deny(self, reason, status=403):
        """One shape for every refusal: a stable machine-readable reason and no
        detail that would help an attacker tell 'unknown device' from 'wrong
        signature'."""
        return self._json({'ok': False, 'error': reason}, status=status)

    def _remote_addr(self):
        try:
            return request.httprequest.remote_addr
        except Exception:  # noqa: BLE001
            return ''

    def _audit(self, event, severity='info', detail=''):
        try:
            self._env()['mezze.audit.log'].sudo().log(
                event, severity=severity, res_model='mezze.terminal', res_id=0, detail=detail)
        except Exception:  # noqa: BLE001 — auditing must never break the protocol
            _logger.debug('station audit failed for %s', event, exc_info=True)

    def _station(self, env, device_uuid):
        """Resolve a station by its locator, revoked ones included, so revocation is
        reported rather than looking like an unknown device."""
        if not device_uuid:
            return env['mezze.terminal'].browse()
        return env['mezze.terminal'].sudo().with_context(active_test=False).search(
            [('device_uuid', '=', device_uuid)], limit=1)

    # ----------------------------------------------------------------- health
    @http.route('/mezze/station/v1/health', type='http', auth='none', methods=['GET'],
                csrf=False, sitemap=False, readonly=False)
    def station_health(self, **kw):
        """Liveness + the two facts a station needs before it trusts anything:
        the server's clock and the public key its leases are signed with."""
        env = self._env()
        icp = env['ir.config_parameter'].sudo()
        return self._json({
            'ok': True,
            'server_time': fields.Datetime.to_string(fields.Datetime.now()),
            'protocol': PROTOCOL,
            'min_app_version': icp.get_param('mezze_bridge.station_min_version', '0.1.0'),
            'lease_public_key': env['mezze.station.lease.signer'].public_key(),
        })

    # ---------------------------------------------------------------- enroll
    @http.route('/mezze/station/v1/enroll', type='json2', auth='none', methods=['POST'],
                csrf=False, readonly=False)
    def station_enroll(self, activation_code=None, device_uuid=None, public_key=None,
                       crypto_provider=None, security_level=None, app_version=None,
                       os_version=None, hostname=None, key_algorithm=None, **kw):
        """Trade a one-time code for an identity.

        The code says WHICH restaurant, branch and role; the public key says WHICH
        device. Neither the client's claimed company/branch/role nor its hostname is
        trusted — every scope value comes from the code the operator cut.
        """
        env = self._env()
        if not device_uuid or not public_key or not activation_code:
            return self._deny('enrollment_incomplete', status=400)
        if key_algorithm and key_algorithm != station_crypto.ALGORITHM:
            return self._deny('unsupported_algorithm', status=400)
        try:
            station_crypto.load_public_key(public_key)          # proves it is P-256
        except station_crypto.StationKeyError:
            return self._deny('invalid_public_key', status=400)

        Activation = env['mezze.station.activation']
        act = Activation.claim(activation_code)
        if not act:
            self._audit('station.enroll_rejected', 'warning', '{"reason": "activation_invalid"}')
            return self._deny('activation_invalid', status=403)

        level = security_level if security_level in _CLAIMED_LEVELS else 'c_software'
        Term = env['mezze.terminal'].sudo()
        existing = self._station(env, device_uuid)
        if existing:
            # Re-enrolment of a device that already exists is only allowed while it
            # is not revoked; it rotates the key rather than creating a twin.
            if existing.station_revoked_at:
                return self._deny('device_revoked', status=403)
            station = existing
            station.write({
                'public_key': public_key,
                'public_key_fp': station_crypto.public_key_fingerprint(public_key),
                'crypto_provider': crypto_provider or '',
                'security_level': level,
                'app_version': app_version or '',
                'os_version': os_version or '',
                'hostname': hostname or '',
                'activated_at': fields.Datetime.now(),
                'activation_id': act.id,
            })
        else:
            cap_role = ROLE_SURFACE.get(act.station_role, ('terminal', None))[0]
            station = Term.create({
                'name': act.label or dict(ROLE_SURFACE).get(act.station_role, act.station_role),
                'identifier': 'station-%s' % (device_uuid[:24]),
                'branch_id': act.branch_id.id,
                'role': cap_role,
                'station_role': act.station_role,
                'device_uuid': device_uuid,
                'public_key': public_key,
                'public_key_fp': station_crypto.public_key_fingerprint(public_key),
                'key_algorithm': station_crypto.ALGORITHM,
                'crypto_provider': crypto_provider or '',
                'security_level': level,
                'app_version': app_version or '',
                'os_version': os_version or '',
                'hostname': hostname or '',
                'activated_at': fields.Datetime.now(),
                'activation_id': act.id,
                'active': True,
            })
        # burn the code in the same transaction that created the identity
        act.sudo().write({'consumed_at': fields.Datetime.now(), 'consumed_by_id': station.id})
        self._audit('station.enrolled', 'info',
                    '{"station": "%s", "role": "%s", "level": "%s"}'
                    % (station.identifier, station.station_role, level))
        return {
            'ok': True,
            'station_id': station.identifier,
            'station_role': station.station_role,
            'branch': {'id': station.branch_id.id, 'name': station.branch_id.name},
            'company': {'id': station.branch_id.company_id.id,
                        'name': station.branch_id.company_id.name},
            'security_level': station.security_level,
            'entry_surface': station.entry_surface(),
            # no token, no key, nothing that survives a copy
        }

    # -------------------------------------------------------------- challenge
    @http.route('/mezze/station/v1/challenge', type='json2', auth='none', methods=['POST'],
                csrf=False, readonly=False)
    def station_challenge(self, device_uuid=None, **kw):
        """Hand out a single-use nonce bound to this device."""
        env = self._env()
        station = self._station(env, device_uuid)
        if not station or not station.public_key:
            return self._deny('unknown_device', status=403)
        if station.station_revoked_at or not station.active:
            self._audit('station.challenge_rejected', 'warning',
                        '{"station": "%s", "reason": "revoked"}' % station.identifier)
            return self._deny('device_revoked', status=403)
        ch = env['mezze.station.challenge'].issue(station)
        return {
            'ok': True,
            'nonce': ch.nonce,
            'protocol': PROTOCOL,
            'expires_at': fields.Datetime.to_string(ch.expires_at),
            'server_time': fields.Datetime.to_string(fields.Datetime.now()),
        }

    # ------------------------------------------------------------------ auth
    @http.route('/mezze/station/v1/auth', type='json2', auth='none', methods=['POST'],
                csrf=False, readonly=False)
    def station_auth(self, device_uuid=None, nonce=None, signature=None,
                     app_version=None, **kw):
        """Verify possession of the enrolled private key and mint a short session.

        Order matters: the nonce is burned BEFORE the session is minted, so a
        captured (nonce, signature) pair is worthless the moment it is used once —
        including by its rightful owner.
        """
        env = self._env()
        station = self._station(env, device_uuid)
        if not station or not station.public_key:
            return self._deny('unknown_device', status=403)
        if station.station_revoked_at or not station.active:
            self._audit('station.auth_rejected', 'warning',
                        '{"station": "%s", "reason": "revoked"}' % station.identifier)
            return self._deny('device_revoked', status=403)
        message = station_crypto.auth_message(PROTOCOL, device_uuid, nonce)
        if not station_crypto.verify(station.public_key, message, signature):
            self._audit('station.auth_rejected', 'warning',
                        '{"station": "%s", "reason": "bad_signature"}' % station.identifier)
            return self._deny('invalid_signature', status=403)
        # single use: this is what defeats replay, and it must happen even though
        # the signature verified
        if not env['mezze.station.challenge'].consume(station, nonce):
            self._audit('station.auth_rejected', 'warning',
                        '{"station": "%s", "reason": "replay"}' % station.identifier)
            return self._deny('replayed_challenge', status=403)

        token, ttl = env['mezze.station.session'].mint(
            station, app_version=app_version, remote_addr=self._remote_addr())
        station.sudo().write({'last_seen_at': fields.Datetime.now(),
                              'app_version': app_version or station.app_version})
        surface = station.entry_surface()
        if station.station_role == 'kiosk' and station.branch_id:
            try:
                surface = '%s?store=%s' % (
                    surface, self._bridge._store_token(env, station.branch_id))
            except Exception:  # noqa: BLE001 — a missing store token is not fatal to auth
                _logger.debug('kiosk store token unavailable', exc_info=True)
        self._audit('station.authenticated', 'info',
                    '{"station": "%s", "role": "%s"}' % (station.identifier, station.station_role))
        return {
            'ok': True,
            'session_token': token,          # SHORT-LIVED; returned once, stored as a hash
            'expires_in': ttl,
            'station_id': station.identifier,
            'station_role': station.station_role,
            'entry_surface': surface,
            'branch': {'id': station.branch_id.id, 'name': station.branch_id.name},
            'security_level': station.security_level,
        }

    # ----------------------------------------------------------------- lease
    @http.route('/mezze/station/v1/lease', type='json2', auth='none', methods=['POST'],
                csrf=False, readonly=False)
    def station_lease(self, session_token=None, **kw):
        """Return a freshly signed lease for the session's own station.

        Authenticated by the short-lived session, never by a client-asserted id: a
        station cannot ask for somebody else's entitlement.
        """
        env = self._env()
        session = env['mezze.station.session'].resolve(session_token)
        if not session:
            return self._deny('session_invalid', status=401)
        station = session.terminal_id.sudo()
        station.write({'last_seen_at': fields.Datetime.now()})
        return {'ok': True, 'lease': station.station_lease()}

    # --------------------------------------------------------- staff shift (WS-1)
    @http.route('/mezze/station/v1/surface', type='json2', auth='none', methods=['POST'],
                csrf=False, readonly=False)
    def station_surface(self, session_token=None, code=None, pin=None, **kw):
        """Open a staff shift on a device-authenticated station.

        This is the WS-0 gap closed. The staff surfaces are ``auth='user'``, and a
        device key is not a person, so WS-0 stopped at the door rather than storing
        an Odoo credential on the till. The answer is two proofs, in order:

          1. the DEVICE, by the short-lived session it earned with its private key;
          2. the PERSON, by a PIN against ``mezze.cashier`` — the identity
             front-of-house staff already use, throttled here for the first time.

        Only then does the server mint an Odoo session, as a least-privilege
        service identity, confined by path, expiring on a shift ceiling and an
        idle cut-off, and killable from the console. No user password is typed on
        a till and nothing on disk is sufficient to re-open the shift.
        """
        # Bound to a real acting user rather than the route's anonymous env.
        # Opening a shift creates ORM records (a service user, its partner and
        # avatar, an audit row) whose computes and flushes need somebody to be
        # acting; with auth='none' that is nobody, and the failure surfaces late,
        # at flush, as an unrelated singleton error.
        env = self._staff_env()
        session = env['mezze.station.session'].resolve(session_token)
        if not session:
            return self._deny('session_invalid', status=401)
        station = session.terminal_id.sudo()

        # A kiosk or customer display must never mint a staff session: it is the
        # least supervised device in the building and it needs no human at all.
        refusal = station_surface.may_open_staff_session(station.station_role)
        if refusal:
            self._audit('station.shift_rejected', 'warning',
                        '{"station": "%s", "reason": "%s"}' % (station.identifier, refusal))
            return self._deny(refusal, status=403)

        cashier, error, retry_after = env['mezze.cashier'].authenticate_pin(
            code, pin,
            station_surface.pin_keys(station.device_uuid, code),
            station_surface.PIN_WINDOW_SECONDS)
        if error:
            env['mezze.audit.log'].sudo().log(
                'station.shift_denied', severity='warning',
                config_id=station.branch_id.id or False,
                detail='station=%s code=%s reason=%s' % (
                    station.device_uuid or '', code or '', error))
            payload = {'ok': False, 'error': error}
            if retry_after:
                payload['retry_after'] = retry_after
            return self._json(payload, status=429 if error == 'rate_limited' else 401)

        # Branch scope: a cashier limited to certain branches cannot open a shift
        # on a station belonging to another one. An empty list means unrestricted,
        # which is the existing meaning of the field and not ours to redefine.
        if cashier.config_ids and station.branch_id and station.branch_id not in cashier.config_ids:
            env['mezze.audit.log'].sudo().log(
                'station.shift_denied', severity='warning', cashier_id=cashier.id,
                config_id=station.branch_id.id or False,
                detail='station=%s reason=branch_scope' % (station.device_uuid or ''))
            return self._deny('branch_not_allowed', status=403)

        company = station.branch_id.company_id or env.company
        user = env['mezze.station.surface.session']._service_user_for(company)
        shift = env['mezze.station.surface.session'].open_for(
            station, cashier, user,
            surface=station.entry_surface(), remote_addr=self._remote_addr())

        # Odoo's own no-password session mint. ``finalize`` sets uid, login,
        # context and session token and rotates the sid — we do not hand-roll any
        # of that. The station stamp travels in the session dict, so it survives
        # the rotation and is what every later request is validated against.
        request.session['pre_login'] = user.login
        request.session['pre_uid'] = user.id
        request.session.finalize(env(user=user.id))
        request.session['mezze_surface_id'] = shift.id
        request.session['mezze_station_uuid'] = station.device_uuid or ''

        station.write({'last_seen_at': fields.Datetime.now()})
        env['mezze.audit.log'].sudo().log(
            'station.shift_opened', severity='info', cashier_id=cashier.id,
            config_id=station.branch_id.id or False,
            detail='station=%s role=%s' % (station.device_uuid or '', station.station_role))
        return {
            'ok': True,
            'surface': shift.surface,
            'cashier': {'id': cashier.id, 'name': cashier.name, 'role': cashier.role},
            'expires_in': station_surface.SURFACE_TTL_SECONDS,
            'idle_timeout': station_surface.SURFACE_IDLE_SECONDS,
        }

    @http.route('/mezze/station/v1/surface/end', type='json2', auth='none', methods=['POST'],
                csrf=False, readonly=False)
    def station_surface_end(self, session_token=None, **kw):
        """Clock out. Ends the shift record AND the Odoo session, in that order.

        Authenticated by the DEVICE session rather than the staff cookie, so a
        station can always close a shift it opened — including after the browser
        state has been lost, which is exactly when an abandoned till matters.
        """
        env = self._staff_env()
        session = env['mezze.station.session'].resolve(session_token)
        if not session:
            return self._deny('session_invalid', status=401)
        station = session.terminal_id.sudo()
        env['mezze.station.surface.session'].sudo().search([
            ('terminal_id', '=', station.id), ('is_live', '=', True),
        ]).end('clocked_out')
        try:
            request.session.logout(keep_db=True)
        except Exception:  # noqa: BLE001 — the record is already closed, which is what counts
            _logger.debug('station surface logout failed', exc_info=True)
        return {'ok': True}
