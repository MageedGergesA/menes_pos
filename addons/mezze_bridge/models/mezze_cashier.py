# Part of the Mezze POS platform. See LICENSE (LGPL-3).
import hashlib
import hmac
import secrets

from odoo import api, fields, models

from ..domain import rate_policy


class MezzeCashier(models.Model):
    """A till operator identity for terminal login + transaction attribution.

    A cashier clocks in at the terminal with a PIN (stored only as a salted
    PBKDF2 hash); every subsequent money event is attributed to them in the audit
    log. Distinct from ``res.users`` so front-of-house staff don't need Odoo
    backend accounts. See ``docs/W1.md``.
    """
    _name = 'mezze.cashier'
    _description = "Mezze Cashier"
    _order = 'name'

    name = fields.Char(required=True, index=True)
    code = fields.Char(string="Staff Code", index=True, copy=False,
                       help="Short login code entered before the PIN.")
    config_ids = fields.Many2many('pos.config', string="Allowed Branches")
    user_id = fields.Many2one('res.users', string="Linked User", ondelete='set null',
                              help="Optional link to an Odoo user for backend access.")
    role = fields.Selection(
        selection=[('host', "Host"), ('server', "Server"), ('cashier', "Cashier"),
                   ('bar', "Bar"), ('kitchen', "Kitchen"), ('rider', "Rider"),
                   ('supervisor', "Supervisor"), ('manager', "Manager"),
                   ('admin', "Administrator"), ('auditor', "Auditor")],
        default='cashier', required=True,
        help="Drives which actions require approval (voids, discounts, refunds) and, for "
             "admin/manager/auditor, human administrative access to the Admin Console.")
    pin_hash = fields.Char(string="PIN Hash", copy=False,
                           help="Salted PBKDF2 hash. The PIN itself is never stored.")
    pin_salt = fields.Char(copy=False)
    active = fields.Boolean(default=True)

    _code_uniq = models.Constraint(
        'unique(code)',
        "Staff code must be unique.",
    )

    def _hash_pin(self, pin, salt):
        return hashlib.pbkdf2_hmac(
            'sha256', (pin or '').encode(), (salt or '').encode(), 100000).hex()

    def set_pin(self, pin):
        """Store a new PIN as salt + hash (never the plaintext)."""
        self.ensure_one()
        salt = secrets.token_hex(16)
        self.write({'pin_salt': salt, 'pin_hash': self._hash_pin(pin, salt)})

    def check_pin(self, pin):
        self.ensure_one()
        if not self.pin_hash or not self.pin_salt:
            return False
        return hmac.compare_digest(self.pin_hash, self._hash_pin(pin, self.pin_salt))

    # ------------------------------------------------------------- throttled auth
    # WS-1. A PIN is four digits, so the only thing standing between an
    # unattended till and every possible PIN is a ceiling on attempts. There was
    # none: ``cashier/login`` and ``approve`` both audited a failure and invited
    # the next one. Since WS-1 lets a PIN open an Odoo session, that gap stops
    # being theoretical, so the check lives here — one implementation, used by
    # the station sign-in AND by the older W1 endpoints, rather than a rule the
    # newest caller happens to remember.
    @api.model
    def authenticate_pin(self, code, pin, keys, window_seconds):
        """Resolve a staff code + PIN under a rate limit.

        ``keys`` is a sequence of ``(limit_key, max_hits)`` from
        ``domain/station_surface.py`` — typically one budget for this staff code
        on this device and a wider one for the device itself, so an attacker
        cannot dodge the first by cycling through codes.

        Returns ``(cashier, error, retry_after)``. ``error`` is one of
        ``rate_limited``, ``bad_credentials``, or None on success. The two
        failures are reported distinctly on purpose: a locked-out till needs to
        say so, and telling an attacker they are rate-limited costs nothing they
        could not measure anyway.
        """
        Limit = self.env['mezze.rate.limit'].sudo()
        worst_retry = 0
        for key, max_hits in keys:
            count, retry_after = Limit.peek(key, window_seconds)
            # FAIL CLOSED: an unreadable limiter must not become an unlimited
            # guessing window.
            if count < 0 or count >= max_hits:
                return (self.browse(), 'rate_limited', retry_after)
            worst_retry = max(worst_retry, retry_after)

        cashier = self.search([('code', '=', code), ('active', '=', True)], limit=1)
        # Verify even when the code is unknown, so a wrong code and a wrong PIN
        # cost the same time. Otherwise the response time enumerates staff codes.
        ok = bool(cashier) and cashier.check_pin(pin)
        if ok:
            return (cashier, None, 0)
        if not cashier:
            self.browse()._dummy_pin_work(pin)
        # Only FAILURES are counted. Counting every attempt is simpler and wrong:
        # a manager approving ten comps in a busy quarter-hour would be locked out
        # of the eleventh, which turns a security control into an outage.
        for key, _max_hits in keys:
            Limit.hit(key, 10 ** 9, window_seconds, fail_mode=rate_policy.FAIL_OPEN)
        return (self.browse(), 'bad_credentials', 0)

    def _dummy_pin_work(self, pin):
        """Burn the same PBKDF2 work an unknown staff code would have skipped."""
        hashlib.pbkdf2_hmac('sha256', (pin or '').encode(), b'unknown-code', 100000)
        return False
