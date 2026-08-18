# Part of the Mezze POS platform. See LICENSE (LGPL-3).
"""WS-1 — cutting an activation code from the interface instead of the shell.

Until now the only way to enrol a station was ``odoo-bin shell``:

    rec, code = env['mezze.station.activation'].issue(branch, 'register')

That is honest for a proof of concept and unusable for a restaurant. The rules the
shell flow enforced are all still enforced here, because this wizard calls the very
same ``issue`` — it adds an operator, not a second code path:

* the code is generated server-side and stored only as a keyed HMAC;
* it is shown exactly once, on screen, and never persisted in the clear;
* it is scoped to one company, one branch and one role, and expires.

The one thing the wizard adds is the reason a manager would ever want it: a code
they can read out over the phone to whoever is standing at the till.
"""
from odoo import api, fields, models
from odoo.exceptions import UserError

from ..models.mezze_station import ACTIVATION_TTL_MINUTES, STATION_ROLES


class MezzeStationEnrolWizard(models.TransientModel):
    _name = 'mezze.station.enrol.wizard'
    _description = "Enrol a Mezze Station"

    branch_id = fields.Many2one('pos.config', string="Branch", required=True,
                                help="The counter this station belongs to. A code cut for one "
                                     "branch cannot enrol a station anywhere else.")
    station_role = fields.Selection(STATION_ROLES, required=True, default='register',
                                    string="What is this station for?",
                                    help="Decides which surface the station opens and which "
                                         "capabilities it will hold. The station cannot change it.")
    label = fields.Char(string="Label",
                        help="How this till is known on the floor, e.g. 'Front counter 2'.")
    ttl_minutes = fields.Integer(string="Valid for (minutes)", default=ACTIVATION_TTL_MINUTES,
                                 help="Keep this short. An unused code is the one thing here "
                                      "worth stealing.")

    activation_code = fields.Char(string="Activation code", readonly=True,
                                  help="Shown once. It is stored only as a non-reversible "
                                       "fingerprint, so it cannot be recovered — cut a new one "
                                       "if it is lost.")
    expires_at = fields.Datetime(readonly=True)
    issued = fields.Boolean(default=False)

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        if 'branch_id' in fields_list and not values.get('branch_id'):
            default = self.env['ir.config_parameter'].sudo().get_param(
                'mezze_bridge.default_branch_id')
            if default and str(default).isdigit():
                config = self.env['pos.config'].browse(int(default))
                if config.exists():
                    values['branch_id'] = config.id
        return values

    def action_issue(self):
        """Cut the code and show it. Deliberately keeps the wizard open."""
        self.ensure_one()
        if self.issued:
            raise UserError(
                "This code has already been issued. Close the dialog and start again "
                "to cut another one — codes are single-use by design.")
        if self.ttl_minutes <= 0:
            raise UserError("A code has to be valid for at least a minute.")
        record, raw = self.env['mezze.station.activation'].issue(
            self.branch_id, self.station_role,
            label=self.label or None, ttl_minutes=self.ttl_minutes)
        self.write({
            'activation_code': raw,
            'expires_at': record.expires_at,
            'issued': True,
        })
        self.env['mezze.audit.log'].sudo().log(
            'station.code_issued', severity='info', config_id=self.branch_id.id,
            detail='role=%s label=%s' % (self.station_role, self.label or ''))
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'name': "Activation code",
        }
