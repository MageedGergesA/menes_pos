# Part of the Mezze POS platform. See LICENSE (LGPL-3).
from odoo import fields, models


class MezzeEinvoice(models.Model):
    """E-invoice envelope + clearance state for a POS order.

    One row per fiscal document submitted to a tax authority (Egypt ETA now; KSA
    ZATCA later). Tracks the submission lifecycle and stores the authority's
    returned UUID / signed QR so the receipt is REAL, not simulated. The actual
    authority API call is a TODO seam in ``controllers/w1.py`` — until it lands,
    documents stay ``draft`` and the UI must not print a 'cleared' badge.

    See ``docs/W1.md``.
    """
    _name = 'mezze.einvoice'
    _description = "Mezze E-Invoice"
    _order = 'id desc'

    order_id = fields.Many2one('pos.order', string="POS Order",
                               ondelete='cascade', index=True)
    authority = fields.Selection(
        selection=[('eta', "Egypt ETA"), ('zatca', "KSA ZATCA")],
        default='eta', required=True, index=True)
    state = fields.Selection(
        selection=[('draft', "Draft"), ('submitted', "Submitted"),
                   ('cleared', "Cleared"), ('rejected', "Rejected"), ('error', "Error")],
        default='draft', required=True, index=True)
    authority_uuid = fields.Char(
        string="Authority UUID", index=True, copy=False,
        help="The cleared document id returned by ETA/ZATCA.")
    submission_uuid = fields.Char(string="Submission UUID", copy=False)
    qr_payload = fields.Text(help="Signed QR content per the authority spec.")
    error_message = fields.Text()
    submitted_at = fields.Datetime()
    cleared_at = fields.Datetime()
