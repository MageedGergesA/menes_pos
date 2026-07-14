# Part of the Mezze POS platform. See LICENSE (LGPL-3).
"""POS hardware — network ESC/POS printers + cash drawer.

The Mezze front-end is a web app, and Odoo Community has no IoT Box, so hardware
is driven **server-side**: Odoo renders an ESC/POS byte stream and sends it over
raw TCP (port 9100) to a network thermal printer. A cash drawer is kicked through
the receipt printer's drawer pin. USB barcode scanners are keyboard-HID and are
handled entirely in the front-end (no server model needed).

A ``mezze.printer`` is one network printer bound to a branch: a receipt printer
(optionally controlling the cash drawer) or a per-station kitchen printer.
"""
from odoo import fields, models


class MezzePrinter(models.Model):
    _name = 'mezze.printer'
    _description = "Mezze Network Printer"
    _order = 'config_id, printer_type, id'

    name = fields.Char(required=True)
    printer_type = fields.Selection(
        [('receipt', 'Receipt'), ('kitchen', 'Kitchen'), ('label', 'Label')],
        required=True, default='receipt', index=True)
    config_id = fields.Many2one('pos.config', string="Branch", required=True,
                                ondelete='cascade', index=True)
    station = fields.Char(help="For a kitchen printer: the prep station it serves "
                               "(Barista/Pastry/Kitchen…). Blank = all stations.")
    host = fields.Char(help="Printer IP / hostname (raw ESC/POS over TCP).")
    port = fields.Integer(default=9100, help="Raw-print port (JetDirect = 9100).")
    width = fields.Integer(string="Chars/line", default=48,
                           help="48 for 80mm paper, 32 for 58mm.")
    open_drawer = fields.Boolean(
        string="Controls cash drawer",
        help="This receipt printer kicks the cash drawer on a cash sale.")
    active = fields.Boolean(default=True)

    _name_config_uniq = models.Constraint(
        'unique(name, config_id)',
        "Printer name must be unique per branch.",
    )
