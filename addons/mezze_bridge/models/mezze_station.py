# Part of the Mezze POS platform. See LICENSE (LGPL-3).
"""WS-0 — Mezze Station device identity, enrolment and short-lived sessions.

Mezze already has a device registry (``mezze.terminal``): identity, branch, a
least-privilege role, key rotation, fingerprinted secrets and revocation. A Windows
station is one of those devices, so this EXTENDS it rather than starting a second,
competing registry. What Windows adds is the part the existing model cannot express:

* a **public key** — the trust root is a private key that never leaves the machine
  (TPM through the Windows Platform Crypto Provider, else DPAPI-protected), not a
  shared bearer secret shipped with the install;
* the **security level** actually achieved on that machine, recorded honestly
  (A = TPM, B = DPAPI, C = unprotected) instead of pretending software storage is
  hardware-backed;
* a **station role** — the same physical app on different counters, told by the
  server which surface it owns;
* **one-time activation codes**, **server-issued challenges** and **short-lived
  sessions**, so nothing on disk is sufficient to clone a licensed station.

The existing bearer/HMAC machinery downstream is untouched: a station's short-lived
session token is presented exactly like a terminal token, so it flows through the one
canonical security gate with the terminal's least-privilege capability set.
"""
import base64
import logging
import secrets

from odoo import api, fields, models
from odoo.tools import config

from ..domain import station_crypto

_logger = logging.getLogger(__name__)

# A station role is what the counter DOES. It maps to the existing capability role
# (least privilege) and to the surface the station is allowed to open.
STATION_ROLES = [
    ('register', 'Register'),
    ('kds', 'Kitchen Display'),
    ('floor', 'Floor / Staff'),
    ('drivethru_order', 'Drive-Thru — Order Taker'),
    ('drivethru_ops', 'Drive-Thru — Operations'),
    ('drivethru_payment', 'Drive-Thru — Payment'),
    ('drivethru_pickup', 'Drive-Thru — Pickup'),
    ('kiosk', 'Self-Order Kiosk'),
    ('ocb', 'Customer Display (OCB)'),
]

# station role -> (capability role on mezze.terminal, surface template)
# Surfaces are REPOSITORY TRUTH: every path below is a real @http.route in this
# addon (controllers/cashier.py, kds.py, floor.py, drivethru.py, ocb.py) or the
# kiosk's static entry. Nothing here is invented.
ROLE_SURFACE = {
    'register':          ('terminal', '/mezze/pos'),
    'kds':               ('kitchen',  '/mezze/kds'),
    'floor':             ('terminal', '/mezze/floor'),
    'drivethru_order':   ('terminal', '/mezze/drivethru?mode=order'),
    'drivethru_ops':     ('terminal', '/mezze/drivethru?mode=ops'),
    'drivethru_payment': ('terminal', '/mezze/drivethru?mode=payment'),
    'drivethru_pickup':  ('terminal', '/mezze/drivethru?mode=pickup'),
    'kiosk':             ('terminal', '/mezze_bridge/static/kiosk.html'),
    'ocb':               ('terminal', '/mezze/ocb'),
}

SECURITY_LEVELS = [
    ('a_tpm', 'A — TPM-backed, non-exportable'),
    ('b_dpapi', 'B — DPAPI-protected software key'),
    ('c_software', 'C — unprotected software key (reduced security)'),
]

# How long a station session lives. Deliberately short: the station re-proves
# possession of its key rather than holding a long-lived secret.
SESSION_TTL_SECONDS = 900
CHALLENGE_TTL_SECONDS = 120
ACTIVATION_TTL_MINUTES = 60
LEASE_DAYS = 7
LEASE_GRACE_DAYS = 3

PROTOCOL = 'mezze-station-auth-v1'

# How long a station may be quiet before the console stops calling it online.
STALE_AFTER_MINUTES = 15


class MezzeStationActivation(models.Model):
    """A one-time, short-lived, scoped code that lets ONE device enrol.

    It is not a credential: it authorises the creation of an identity and is burned
    on first use. Stolen after use it is worthless; stolen before use it can enrol a
    device the operator can see and revoke, and only into the branch/role it was cut
    for.
    """
    _name = 'mezze.station.activation'
    _description = 'Mezze Station activation code'
    _order = 'id desc'

    code_fingerprint = fields.Char(required=True, index=True, copy=False,
                                   help="Keyed HMAC of the code; the code itself is never stored.")
    company_id = fields.Many2one('res.company', required=True, ondelete='cascade')
    branch_id = fields.Many2one('pos.config', string='Branch', required=True, ondelete='cascade')
    station_role = fields.Selection(STATION_ROLES, required=True)
    label = fields.Char(help="What this code is for, e.g. 'Front counter 2'.")
    expires_at = fields.Datetime(required=True, index=True)
    consumed_at = fields.Datetime(index=True)
    consumed_by_id = fields.Many2one('mezze.terminal', ondelete='set null')
    created_uid = fields.Many2one('res.users', default=lambda self: self.env.uid)

    _code_fp_uniq = models.Constraint('unique(code_fingerprint)',
                                      'This activation code already exists.')

    @api.model
    def issue(self, branch, station_role, label=None, ttl_minutes=ACTIVATION_TTL_MINUTES):
        """Cut a new code. Returns ``(record, plaintext)`` — the plaintext is shown
        to the operator ONCE and never persisted."""
        if station_role not in dict(STATION_ROLES):
            raise ValueError('unknown station role %r' % station_role)
        raw = '-'.join(secrets.token_hex(2).upper() for _ in range(4))   # XXXX-XXXX-XXXX-XXXX
        rec = self.sudo().create({
            'code_fingerprint': self._fingerprint(raw),
            'company_id': branch.company_id.id,
            'branch_id': branch.id,
            'station_role': station_role,
            'label': label or dict(STATION_ROLES)[station_role],
            'expires_at': fields.Datetime.add(fields.Datetime.now(), minutes=ttl_minutes),
        })
        return rec, raw

    @api.model
    def _fingerprint(self, raw):
        """Non-reversible id for a code. Uses the master-key HMAC where configured
        so a database dump contains no usable codes; falls back to a plain digest in
        development, which is still non-reversible."""
        Store = self.env['mezze.secret.store']
        h = Store.token_hash(raw) if hasattr(Store, 'token_hash') else None
        if h:
            return h
        from hashlib import sha256
        return 'sha256:' + sha256((raw or '').encode()).hexdigest()

    @api.model
    def claim(self, raw):
        """Atomically consume a code. Returns the record or None.

        Single-use is enforced by writing ``consumed_at`` inside the same
        transaction the caller uses to create the station, so two racing enrolments
        cannot both succeed with one code.
        """
        if not raw:
            return None
        rec = self.sudo().search([('code_fingerprint', '=', self._fingerprint(raw))], limit=1)
        if not rec:
            return None
        if rec.consumed_at:
            return None
        if rec.expires_at and rec.expires_at <= fields.Datetime.now():
            return None
        return rec


class MezzeStationChallenge(models.Model):
    """A server-issued, single-use nonce a station signs to prove key possession."""
    _name = 'mezze.station.challenge'
    _description = 'Mezze Station authentication challenge'
    _order = 'id desc'

    terminal_id = fields.Many2one('mezze.terminal', required=True, ondelete='cascade', index=True)
    nonce = fields.Char(required=True, index=True, copy=False)
    expires_at = fields.Datetime(required=True, index=True)
    consumed_at = fields.Datetime(index=True)

    _nonce_uniq = models.Constraint('unique(nonce)', 'Challenge nonce must be unique.')

    @api.model
    def issue(self, terminal):
        return self.sudo().create({
            'terminal_id': terminal.id,
            'nonce': base64.urlsafe_b64encode(secrets.token_bytes(24)).decode().rstrip('='),
            'expires_at': fields.Datetime.add(fields.Datetime.now(),
                                              seconds=CHALLENGE_TTL_SECONDS),
        })

    @api.model
    def consume(self, terminal, nonce):
        """Burn the nonce. Returns True only for a live challenge issued to THIS
        device; every later presentation of the same nonce is a replay and fails."""
        rec = self.sudo().search([('nonce', '=', nonce or ''),
                                  ('terminal_id', '=', terminal.id)], limit=1)
        if not rec or rec.consumed_at:
            return False
        if rec.expires_at and rec.expires_at <= fields.Datetime.now():
            return False
        rec.write({'consumed_at': fields.Datetime.now()})
        return True

    @api.model
    def gc(self, keep_hours=24):
        cutoff = fields.Datetime.subtract(fields.Datetime.now(), hours=keep_hours)
        old = self.sudo().search([('expires_at', '<', cutoff)])
        count = len(old)
        old.unlink()
        return count


class MezzeStationSession(models.Model):
    """A short-lived station session minted after a successful challenge/response.

    The plaintext is returned once and never stored; only its keyed fingerprint is
    kept, exactly like the terminal bearer. Expiry is short by design — a stolen
    session is a limited-time problem, and revoking the device kills renewal.
    """
    _name = 'mezze.station.session'
    _description = 'Mezze Station session'
    _order = 'id desc'

    terminal_id = fields.Many2one('mezze.terminal', required=True, ondelete='cascade', index=True)
    token_fingerprint = fields.Char(required=True, index=True, copy=False)
    issued_at = fields.Datetime(default=fields.Datetime.now, index=True)
    expires_at = fields.Datetime(required=True, index=True)
    revoked_at = fields.Datetime(index=True)
    app_version = fields.Char()
    remote_addr = fields.Char()

    @api.model
    def mint(self, terminal, app_version=None, remote_addr=None,
             ttl_seconds=SESSION_TTL_SECONDS):
        raw = secrets.token_urlsafe(32)
        self.sudo().create({
            'terminal_id': terminal.id,
            'token_fingerprint': self._fingerprint(raw),
            'expires_at': fields.Datetime.add(fields.Datetime.now(), seconds=ttl_seconds),
            'app_version': app_version or '',
            'remote_addr': remote_addr or '',
        })
        return raw, ttl_seconds

    @api.model
    def _fingerprint(self, raw):
        Store = self.env['mezze.secret.store']
        h = Store.token_hash(raw) if hasattr(Store, 'token_hash') else None
        if h:
            return h
        from hashlib import sha256
        return 'sha256:' + sha256((raw or '').encode()).hexdigest()

    @api.model
    def resolve(self, raw):
        """Return the live session for this token, or an empty recordset.

        Expired, revoked, and sessions whose device was revoked all resolve to
        nothing — the device's state is checked here so revocation reaches an
        already-issued session, not only the next authentication.
        """
        if not raw:
            return self.browse()
        rec = self.sudo().search([('token_fingerprint', '=', self._fingerprint(raw))], limit=1)
        if not rec or rec.revoked_at:
            return self.browse()
        if rec.expires_at and rec.expires_at <= fields.Datetime.now():
            return self.browse()
        term = rec.terminal_id.sudo().with_context(active_test=False)
        if not term or not term.active or term.station_revoked_at:
            return self.browse()
        return rec

    def revoke(self):
        return self.sudo().write({'revoked_at': fields.Datetime.now()})


class MezzeTerminalStation(models.Model):
    """Windows-station identity on the EXISTING device registry."""
    _inherit = 'mezze.terminal'

    device_uuid = fields.Char(index=True, copy=False,
                              help="Client-generated install id. A LOCATOR, never a credential: "
                                   "knowing it authenticates nothing.")
    public_key = fields.Text(copy=False,
                             help="Base64 SubjectPublicKeyInfo (ECDSA P-256). The private half "
                                  "never leaves the station.")
    public_key_fp = fields.Char(index=True, copy=False, help="SHA-256 of the SPKI (non-secret id).")
    key_algorithm = fields.Char(default=station_crypto.ALGORITHM)
    crypto_provider = fields.Char(help="e.g. 'Microsoft Platform Crypto Provider' (TPM) or "
                                       "'DPAPI/CurrentUser'. Reported by the station, recorded "
                                       "as claimed — the SECURITY LEVEL is what policy reads.")
    security_level = fields.Selection(SECURITY_LEVELS, index=True)
    station_role = fields.Selection(STATION_ROLES, index=True)
    app_version = fields.Char()
    os_version = fields.Char()
    hostname = fields.Char(help="Telemetry only. Never part of the trust root.")
    activated_at = fields.Datetime()
    last_seen_at = fields.Datetime()
    station_revoked_at = fields.Datetime(index=True)
    activation_id = fields.Many2one('mezze.station.activation', ondelete='set null')

    _device_uuid_uniq = models.Constraint('unique(device_uuid)',
                                          'This device is already enrolled.')

    # ------------------------------------------------- console-facing status (WS-1)
    # An operator asks three questions about a till: is it enrolled, is anybody on
    # it, and is it still talking to us. These answer them without asking the
    # operator to interpret four timestamps.
    station_state = fields.Selection(
        [('none', "Not a station"), ('pending', "Never connected"), ('online', "Online"),
         ('stale', "Not seen recently"), ('revoked', "Revoked")],
        compute='_compute_station_state', search='_search_station_state', string="Status")
    current_shift_id = fields.Many2one(
        'mezze.station.surface.session', compute='_compute_current_shift',
        string="Open shift")
    current_cashier_id = fields.Many2one(
        'mezze.cashier', compute='_compute_current_shift', string="Signed in")

    @api.depends('device_uuid', 'station_revoked_at', 'active', 'last_seen_at')
    def _compute_station_state(self):
        # "Recently" is generous on purpose: a kitchen display that is quiet for a
        # few minutes is not a problem worth colouring red on a manager's screen.
        cutoff = fields.Datetime.subtract(fields.Datetime.now(), minutes=STALE_AFTER_MINUTES)
        for rec in self:
            if not rec.device_uuid:
                rec.station_state = 'none'
            elif rec.station_revoked_at or not rec.active:
                rec.station_state = 'revoked'
            elif not rec.last_seen_at:
                rec.station_state = 'pending'
            elif rec.last_seen_at < cutoff:
                rec.station_state = 'stale'
            else:
                rec.station_state = 'online'

    def _search_station_state(self, operator, value):
        """Make the computed status searchable without storing it.

        Storing it is the obvious alternative and the wrong one: "not seen
        recently" is a statement about the clock, so a stored column would be
        stale by definition and would need a cron to keep lying less often. The
        cutoff is computed here instead, from the one constant, so the filters and
        the badge can never disagree.
        """
        cutoff = fields.Datetime.subtract(fields.Datetime.now(), minutes=STALE_AFTER_MINUTES)
        domains = {
            'none': [('device_uuid', '=', False)],
            'revoked': ['&', ('device_uuid', '!=', False),
                        '|', ('station_revoked_at', '!=', False), ('active', '=', False)],
            'pending': ['&', '&', ('device_uuid', '!=', False),
                        ('station_revoked_at', '=', False), ('last_seen_at', '=', False)],
            'stale': ['&', '&', '&', ('device_uuid', '!=', False),
                      ('station_revoked_at', '=', False),
                      ('last_seen_at', '!=', False), ('last_seen_at', '<', cutoff)],
            'online': ['&', '&', ('device_uuid', '!=', False),
                       ('station_revoked_at', '=', False), ('last_seen_at', '>=', cutoff)],
        }
        if operator not in ('=', '!=', 'in', 'not in'):
            raise NotImplementedError("station_state supports equality searches only.")
        # Odoo 19 normalises an '=' leaf into operator='in' with an OrderedSet,
        # not a list — an isinstance check against (list, tuple) silently turns
        # every filter into "match nothing", which looks exactly like an empty
        # fleet. Accept any non-string iterable instead.
        if isinstance(value, str) or not hasattr(value, '__iter__'):
            wanted = [value]
        else:
            wanted = list(value)
        negate = operator in ('!=', 'not in')
        keys = [k for k in domains if (k in wanted) != negate]
        if not keys:
            return [('id', '=', False)]
        result = domains[keys[0]]
        for key in keys[1:]:
            result = ['|'] + result + domains[key]
        return result

    def _compute_current_shift(self):
        Shift = self.env['mezze.station.surface.session'].sudo()
        for rec in self:
            shift = Shift.search([('terminal_id', '=', rec.id), ('is_live', '=', True)],
                                 limit=1) if rec.id else Shift.browse()
            rec.current_shift_id = shift.id or False
            rec.current_cashier_id = shift.cashier_id.id or False

    def action_end_shift(self):
        """End whoever is signed in here. Used when a till is left open."""
        self.env['mezze.station.surface.session'].sudo().search([
            ('terminal_id', 'in', self.ids), ('is_live', '=', True),
        ]).end('operator')
        return True

    # ---------------------------------------------------------------- helpers
    def entry_surface(self):
        """Where this station is allowed to open. Server decides, not the client."""
        self.ensure_one()
        surface = ROLE_SURFACE.get(self.station_role or '', (None, None))[1]
        if not surface:
            return None
        if self.station_role == 'kiosk':
            return surface  # the store token is added by the controller at auth time
        return surface

    def revoke_station(self, reason=None):
        """Revoke ONE station. Its sessions die now; its next authentication fails;
        every other station in the restaurant is untouched."""
        self.ensure_one()
        self.sudo().write({'station_revoked_at': fields.Datetime.now(), 'active': False})
        self.env['mezze.station.session'].sudo().search(
            [('terminal_id', '=', self.id), ('revoked_at', '=', False)]).revoke()
        self.env['mezze.audit.log'].sudo().log(
            'station.revoked', severity='warning', res_model=self._name, res_id=self.id,
            detail='{"station": "%s", "reason": "%s"}' % (self.identifier, reason or ''))
        return True

    def station_lease(self):
        """A signed, offline-verifiable statement of what this station may do.

        The station keeps working through a licensing outage because the lease it
        already holds is still valid — the server is the authority for *services*,
        the lease is the authority for *starting up*. It is signed with the server's
        own key so a patched client cannot mint one, and it is not a substitute for
        server authorization: a forged lease still fails every API call.
        """
        self.ensure_one()
        now = fields.Datetime.now()
        payload = {
            'v': 1,
            'station': self.identifier,
            'device_uuid': self.device_uuid or '',
            'company': self.branch_id.company_id.id if self.branch_id else None,
            'branch': self.branch_id.id if self.branch_id else None,
            'role': self.station_role,
            'security_level': self.security_level,
            'features': sorted(self._station_features()),
            'issued_at': fields.Datetime.to_string(now),
            'expires_at': fields.Datetime.to_string(fields.Datetime.add(now, days=LEASE_DAYS)),
            'grace_days': LEASE_GRACE_DAYS,
        }
        return self.env['mezze.station.lease.signer'].sign(payload)

    def _station_features(self):
        """Feature entitlement for this role. Deliberately coarse in WS-0 — the
        point is that entitlement travels in a signed lease, not that the catalogue
        is final."""
        self.ensure_one()
        base = {'ordering'}
        if self.station_role in ('register', 'floor'):
            base |= {'payments', 'refunds_with_authorization'}
        if self.station_role == 'kds':
            base = {'kitchen'}
        if self.station_role.startswith('drivethru') if self.station_role else False:
            base |= {'drivethru'}
        if self.station_role in ('kiosk', 'ocb'):
            base = {'self_order'} if self.station_role == 'kiosk' else {'display'}
        return base


class MezzeStationLeaseSigner(models.AbstractModel):
    """Signs leases with a server-held key so a station can verify one offline.

    The private key lives in the server's configuration (never in the client, never
    in the package); stations ship only the public half. WS-0 generates a key on
    first use so the flow is provable end to end; production supplies one through
    configuration like any other server secret.
    """
    _name = 'mezze.station.lease.signer'
    _description = 'Mezze Station lease signer'

    PARAM_PRIV = 'mezze_bridge.station_lease_key'
    PARAM_PUB = 'mezze_bridge.station_lease_pubkey'

    @api.model
    def _keypair(self):
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import ec
        icp = self.env['ir.config_parameter'].sudo()
        priv_b64 = config.get('mezze_station_lease_key') or icp.get_param(self.PARAM_PRIV)
        if priv_b64:
            priv = serialization.load_der_private_key(base64.b64decode(priv_b64), password=None)
        else:
            priv = ec.generate_private_key(ec.SECP256R1())
            icp.set_param(self.PARAM_PRIV, base64.b64encode(priv.private_bytes(
                encoding=serialization.Encoding.DER,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption())).decode())
        pub_b64 = base64.b64encode(priv.public_key().public_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo)).decode()
        icp.set_param(self.PARAM_PUB, pub_b64)
        return priv, pub_b64

    @api.model
    def public_key(self):
        return self._keypair()[1]

    @api.model
    def sign(self, payload):
        import json
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import ec
        priv, pub = self._keypair()
        body = json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()
        der = priv.sign(body, ec.ECDSA(hashes.SHA256()))
        return {
            'payload': payload,
            'payload_b64': base64.b64encode(body).decode(),
            'signature': base64.b64encode(der).decode(),
            'algorithm': station_crypto.ALGORITHM,
            'signature_format': 'der',
            'public_key': pub,
        }
