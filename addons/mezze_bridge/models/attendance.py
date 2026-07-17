# Part of the Mezze POS platform. See LICENSE (LGPL-3).
"""Staff time-clock — attendance on the Mezze cashier identity.

Mezze front-of-house staff are ``mezze.cashier`` records (deliberately NOT
``hr.employee`` / ``res.users`` — they don't need Odoo backend accounts), so the
time-clock lives on the cashier, mirroring the shape of ``hr.attendance``
(check_in / check_out / worked_hours). One OPEN record per cashier at a time.
"""
from odoo import api, fields, models


class MezzeAttendance(models.Model):
    _name = 'mezze.attendance'
    _description = 'Mezze Staff Attendance'
    _order = 'check_in desc, id desc'

    cashier_id = fields.Many2one('mezze.cashier', required=True, ondelete='cascade', index=True)
    config_id = fields.Many2one('pos.config', index=True)
    check_in = fields.Datetime(required=True, default=fields.Datetime.now, index=True)
    check_out = fields.Datetime()
    worked_hours = fields.Float(compute='_compute_worked_hours', store=True, string='Worked hours')

    @api.depends('check_in', 'check_out')
    def _compute_worked_hours(self):
        for a in self:
            if a.check_in and a.check_out and a.check_out > a.check_in:
                a.worked_hours = (a.check_out - a.check_in).total_seconds() / 3600.0
            else:
                a.worked_hours = 0.0

    def _open_for(self, cashier):
        """The cashier's currently-open (clocked-in, not yet out) record, if any."""
        return self.search([('cashier_id', '=', cashier.id), ('check_out', '=', False)],
                           order='check_in desc', limit=1)
