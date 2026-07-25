"""Pilot emergency access (P6.5 §7) — the smallest acceptable break-glass.

Replaces the global ``breakglass`` flag with an activation RECORD: disabled by
default, manually activated by an authorised admin, with a mandatory reason,
explicit company/branch scope, a narrow capability list, and an expiry of at most
one hour. While an activation is live the shared-admin principal is admitted in
production BUT narrowed to the activation's scope + capabilities (not all caps).
Every activation/use/revocation is durably audited; revocation is immediate.
"""
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError

MAX_HOURS = 1.0


class MezzeEmergencyAccess(models.Model):
    _name = 'mezze.emergency.access'
    _description = 'Mezze emergency (break-glass) access activation'
    _order = 'id desc'

    active = fields.Boolean(default=False, index=True)
    reason = fields.Char(required=True)
    actor = fields.Char(help="Administrator who activated it.")
    approver = fields.Char(help="Privileged approver.")
    company_id = fields.Many2one('res.company', index=True)
    branch_id = fields.Many2one('pos.config', index=True)
    capabilities = fields.Char(help="Comma-separated capability allowlist for the incident.")
    activated_at = fields.Datetime()
    expires_at = fields.Datetime(index=True)
    revoked = fields.Boolean(default=False, index=True)

    @api.model
    def current(self):
        """The single live activation (active, not revoked, not expired), if any."""
        return self.sudo().search(
            [('active', '=', True), ('revoked', '=', False),
             ('expires_at', '>', fields.Datetime.now())], limit=1)

    @api.model
    def is_active(self):
        return bool(self.current())

    @api.model
    def activate(self, reason=None, hours=1.0, company_id=None, branch_id=None,
                 capabilities=None, actor=None, approver=None):
        """Activate emergency access. Requires a reason + approver; expiry is capped
        at one hour; scope + capabilities are explicit. Durably audited."""
        if not reason:
            raise UserError("Emergency access requires a reason.")
        if not approver:
            raise UserError("Emergency access requires a privileged approver.")
        hours = min(max(0.05, float(hours or 1.0)), MAX_HOURS)
        now = fields.Datetime.now()
        rec = self.sudo().create({
            'active': True, 'reason': reason, 'actor': actor, 'approver': approver,
            'company_id': company_id, 'branch_id': branch_id,
            'capabilities': capabilities or '', 'activated_at': now,
            'expires_at': now + timedelta(hours=hours), 'revoked': False,
        })
        self.env['mezze.audit.log'].sudo().log(
            'security.emergency_activated', severity='warning',
            detail='{"actor": "%s", "approver": "%s", "reason": "%s", "expires": "%s", '
                   '"company": %s, "branch": %s}'
                   % (actor or '', approver or '', (reason or '').replace('"', "'"),
                      fields.Datetime.to_string(rec.expires_at),
                      company_id or 'null', branch_id or 'null'))
        return rec

    def revoke(self):
        for r in self:
            r.sudo().write({'active': False, 'revoked': True})
            self.env['mezze.audit.log'].sudo().log(
                'security.emergency_revoked', severity='warning',
                res_model=self._name, res_id=r.id, detail='{"id": %s}' % r.id)
        return True

    def caps(self):
        self.ensure_one()
        return frozenset(c.strip() for c in (self.capabilities or '').split(',') if c.strip())

    @api.model
    def _cron_expire(self):
        """Auto-revoke expired activations (no silent renewal)."""
        stale = self.sudo().search(
            [('active', '=', True), ('expires_at', '<=', fields.Datetime.now())])
        stale.write({'active': False})
        return len(stale)
