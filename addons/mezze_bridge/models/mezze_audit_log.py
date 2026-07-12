# Part of the Mezze POS platform. See LICENSE (LGPL-3).
from odoo import api, fields, models


class MezzeAuditLog(models.Model):
    """Append-only audit trail for money-affecting and privileged actions.

    Every sale, void, refund, discount override, drawer open, cashier login, and
    price/config change writes one row here, attributed to the acting cashier,
    user, and terminal. Rows are create-only (the ACL denies write/unlink) so the
    trail cannot be altered after the fact. See ``docs/W1.md``.
    """
    _name = 'mezze.audit.log'
    _description = "Mezze Audit Log"
    _order = 'id desc'

    event = fields.Char(
        required=True, index=True,
        help="Event type, e.g. 'order.pay', 'order.void', 'refund', "
             "'discount.override', 'drawer.open', 'cashier.login', 'config.change'.")
    severity = fields.Selection(
        selection=[('info', "Info"), ('warning', "Warning"), ('critical', "Critical")],
        default='info', index=True)
    cashier_id = fields.Many2one('mezze.cashier', string="Cashier",
                                 ondelete='set null', index=True)
    user_id = fields.Many2one('res.users', string="User", ondelete='set null', index=True)
    terminal_id = fields.Many2one('mezze.terminal', string="Terminal",
                                  ondelete='set null', index=True)
    config_id = fields.Many2one('pos.config', string="Branch", ondelete='set null', index=True)
    res_model = fields.Char(string="Record Model", index=True)
    res_id = fields.Integer(string="Record ID", index=True)
    res_uuid = fields.Char(string="Record UUID", index=True)
    amount = fields.Float(string="Amount")
    detail = fields.Text(help="JSON context (before/after, reason code, approver).")
    # create_date / create_uid (ORM) are the immutable timestamp + author.

    @api.model
    def log(self, event, **vals):
        """Best-effort append. Never raises into the caller's money flow — a
        failed audit write must not roll back a completed sale, but it is logged
        server-side for follow-up."""
        try:
            vals['event'] = event
            return self.sudo().create(vals)
        except Exception:  # noqa: BLE001
            import logging
            logging.getLogger(__name__).exception("Mezze audit append failed: %s", event)
            return self.browse()
