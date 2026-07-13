# Part of the Mezze POS platform. See LICENSE (LGPL-3).
from odoo import fields, models


class MezzeReversal(models.Model):
    """A card charge that must be reconciled because its sale wasn't recorded.

    Created by ``/w1/payment/void`` whenever a captured (or unconfirmed) charge
    is reversed or flagged. ``open`` = a manager must reverse it manually in the
    acquirer dashboard (the acquirer has no Odoo auto-refund); ``reversed`` = Odoo
    auto-refunded it; ``resolved`` = a manager confirmed the manual reversal.
    Surfacing the OPEN ones on the manager dashboard closes the "captured but
    finalize-fails" residual — money can't be stranded silently. See docs/W2.md.
    """
    _name = 'mezze.reversal'
    _description = "Mezze Payment Reversal"
    _order = 'id desc'

    transaction_id = fields.Many2one('payment.transaction', string="Payment Transaction",
                                     ondelete='set null', index=True)
    reference = fields.Char(index=True)
    amount = fields.Float()
    reason = fields.Char(help="Why the sale couldn't finalize, e.g. order_finalize_failed.")
    provider = fields.Char()
    config_id = fields.Many2one('pos.config', string="Branch", ondelete='set null', index=True)
    state = fields.Selection(
        selection=[('open', "Open — needs manual reversal"),
                   ('reversed', "Auto-reversed"),
                   ('resolved', "Resolved")],
        default='open', required=True, index=True)
    resolved_by = fields.Char()
    resolved_note = fields.Text()
