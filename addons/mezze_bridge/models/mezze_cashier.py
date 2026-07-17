# Part of the Mezze POS platform. See LICENSE (LGPL-3).
import hashlib
import hmac
import secrets

from odoo import fields, models


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
        selection=[('cashier', "Cashier"), ('supervisor', "Supervisor"), ('manager', "Manager")],
        default='cashier', required=True,
        help="Drives which actions require approval (voids, discounts, refunds).")
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
