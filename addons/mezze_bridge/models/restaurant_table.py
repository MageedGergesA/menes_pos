# Part of the Mezze POS platform. See LICENSE (LGPL-3).
import secrets

from odoo import fields, models


class RestaurantTable(models.Model):
    _inherit = 'restaurant.table'

    # Per-table secret printed inside the table's QR code. It scopes a public,
    # customer-facing ordering session to THIS table only — a phone that scans
    # it can read the menu and fire courses to this table, but never holds the
    # admin API token or can touch any other table. Generated lazily the first
    # time staff surface the QR link.
    mezze_qr_token = fields.Char(string='Mezze QR token', copy=False, index=True)

    def _mezze_ensure_qr_token(self):
        """Return this table's QR token, minting one on first use."""
        self.ensure_one()
        if not self.mezze_qr_token:
            self.sudo().mezze_qr_token = secrets.token_urlsafe(12)
        return self.mezze_qr_token
