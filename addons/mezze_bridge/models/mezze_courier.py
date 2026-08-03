# Part of the Mezze POS platform. See LICENSE (LGPL-3).
"""S3 — delivery courier (manual dispatch only).

A minimal operational courier record for MANUAL assignment. This is deliberately
NOT a fleet/driver-management or GPS system (out of S3 scope): no route
optimization, no live tracking, no payroll. Just enough to assign a named courier
to a delivery and see who is out. Reuses an existing hr.employee / res.partner when
linked, so we never duplicate the workforce identity.
"""
from odoo import fields, models


class MezzeCourier(models.Model):
    _name = 'mezze.courier'
    _description = 'Mezze Delivery Courier'
    _order = 'name asc'

    name = fields.Char(required=True)
    config_id = fields.Many2one('pos.config', string='Branch', index=True, ondelete='cascade')
    phone = fields.Char()
    # Optional link to an existing identity — never a duplicate workforce model.
    # (hr.employee intentionally not referenced: mezze_bridge does not depend on hr.)
    partner_id = fields.Many2one('res.partner', ondelete='set null')
    status = fields.Selection(
        [('available', 'Available'), ('on_delivery', 'On delivery'), ('offline', 'Offline')],
        default='available', required=True, index=True)
    active = fields.Boolean(default=True)

    def _safe(self):
        """PII-safe projection for the staff dashboard."""
        self.ensure_one()
        return {'id': self.id, 'name': self.name, 'phone': self.phone or '',
                'status': self.status}
