# Part of the Mezze POS platform. See LICENSE (LGPL-3).
from odoo import fields, models


class MezzeSyncLog(models.Model):
    """Idempotency / audit ledger for the Mezze Bridge API.

    One row is written for every inbound order-sync attempt so we can trace a
    frontend request end to end and prove why a duplicate uuid was skipped.
    """
    _name = 'mezze.sync.log'
    _description = "Mezze Bridge Sync Log"
    _order = 'id desc'

    name = fields.Char(string="Reference", index=True)
    uuid = fields.Char(string="Order UUID", index=True)
    pos_order_id = fields.Many2one('pos.order', string="POS Order", ondelete='set null')
    session_id = fields.Many2one('pos.session', string="POS Session", ondelete='set null')
    status = fields.Selection(
        selection=[
            ('received', "Received"),
            ('ok', "OK"),
            ('error', "Error"),
        ],
        string="Status",
        default='received',
        index=True,
    )
    message = fields.Text(string="Message")
    payload_hash = fields.Char(string="Payload Hash", index=True)
    # create_date is provided automatically by the ORM (log/audit timestamp).
