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
    # TRANSPORT. Epson's ePOS printers (TM-i series, ePOS interface boards) do not
    # listen on 9100 at all — they take an HTTP envelope — so a shop that already
    # owns Epson hardware could not use Mezze. What travels inside that envelope is
    # the SAME ESC/POS stream: ePOS-Print XML can describe a receipt in its own
    # elements, and rendering through them would give Mezze two receipt renderers
    # that drift apart until a customer compares two pieces of paper.
    transport = fields.Selection(
        [('raw', 'Raw ESC/POS over TCP (port 9100)'),
         ('epos', 'Epson ePOS-Print (HTTP)'),
         ('iot', 'Odoo IoT / Hardware Proxy (HTTP)')],
        default='raw', required=True, string="Connection",
        help="How Odoo reaches this printer.\n\n"
             "Most network thermal printers accept raw ESC/POS on port 9100. Epson's "
             "ePOS models (TM-i series, and TM printers behind an ePOS interface) "
             "instead take an HTTP request and answer with a print result — choose "
             "ePOS-Print for those.\n\n"
             "Hardware Proxy is Odoo's own IoT box (the LGPL `iot_drivers` module): "
             "point Mezze at the box and it posts the receipt to the printer "
             "attached to it. Useful where a printer is USB or serial rather than "
             "networked.\n\n"
             "The receipt itself is identical whichever transport carries it.")
    host = fields.Char(help="Printer IP / hostname.")
    port = fields.Integer(default=9100,
                          help="Raw-print port (JetDirect = 9100). For ePOS leave "
                               "blank to use the web port (80, or 443 over TLS).")
    epos_device_id = fields.Char(
        string="ePOS device ID", default='local_printer',
        help="The device this print goes to on an ePOS box. A TM-i hosting several "
             "printers gives each one its own id; a single printer answers to "
             "'local_printer'.")
    epos_https = fields.Boolean(
        string="ePOS over TLS",
        help="Use https for the ePOS endpoint. Only switch this on for a printer "
             "that actually serves TLS — most shop-floor units do not.")
    iot_url = fields.Char(
        string='IoT box address',
        help="Base address of the Hardware Proxy, e.g. http://10.0.0.5:8069 . "
             "Mezze posts the same ESC/POS bytes it would have sent down a socket.")
    epos_timeout_ms = fields.Integer(
        string="ePOS timeout (ms)", default=10000,
        help="How long the printer may take to report a result before it gives up. "
             "This is the printer's own timeout, sent with the request.")
    width = fields.Integer(string="Chars/line", default=48,
                           help="48 for 80mm paper, 32 for 58mm.")
    codepage = fields.Selection(
        [('cp437', 'CP437 — Latin (default)'),
         ('cp850', 'CP850 — Latin-1'),
         ('cp858', 'CP858 — Latin-1 + euro'),
         ('cp1252', 'Windows-1252 — Western European'),
         ('cp864', 'CP864 — Arabic (presentation forms only)'),
         ('cp1256', 'Windows-1256 — Arabic')],
        default='cp437', required=True, string="Character set",
        help="The code page the receipt text is encoded in. On CP437 every Arabic "
             "character prints as '?'.\n\n"
             "For Arabic use Windows-1256: it maps the Arabic letters as they are "
             "written in Odoo. CP864 maps only the PRESENTATION forms, so ordinary "
             "Arabic text cannot be encoded into it without being shaped first — "
             "choose it only for a printer that supports nothing else, and expect "
             "substitutions.\n\n"
             "The printer must also SUPPORT the page — check its self-test printout.")
    codepage_id = fields.Integer(
        string="Code page number",
        help="The ESC/POS 'ESC t n' number for the character set above. Left empty "
             "it uses the usual value for that set. Vendors disagree about these "
             "numbers — Arabic especially — so set it explicitly if the printer "
             "produces the wrong glyphs on a set it claims to support.")

    open_drawer = fields.Boolean(
        string="Controls cash drawer",
        help="This receipt printer kicks the cash drawer on a cash sale.")
    active = fields.Boolean(default=True)

    _name_config_uniq = models.Constraint(
        'unique(name, config_id)',
        "Printer name must be unique per branch.",
    )


class MezzeScale(models.Model):
    """A shop scale on the branch network.

    Mezze could already SELL by weight — the catalogue ships ``to_weight``, the
    quantity survives as a measurement, the pad takes a decimal — but the weight was
    whatever a cashier read off a display and typed. That is the one number on a line
    nobody can check afterwards, and the typo is not always in the guest's favour.

    Driven server-side for the same reason printers are: Community has no IoT Box,
    and a browser cannot open a socket to a bench scale.
    """
    _name = 'mezze.scale'
    _description = "Mezze Network Scale"
    _order = 'config_id, id'

    name = fields.Char(required=True)
    config_id = fields.Many2one('pos.config', string="Branch", required=True,
                                ondelete='cascade', index=True)
    host = fields.Char(help="Scale IP / hostname, or the address of the serial-to-"
                            "Ethernet adapter it is plugged into.")
    port = fields.Integer(default=4001,
                          help="TCP port. Serial device servers commonly use 4001.")
    protocol = fields.Selection(
        [('toledo', 'Toledo 8217 (and compatibles)'),
         ('line', 'ASCII line — CAS / AND / Excell'),
         ('iot', 'Odoo IoT / Hardware Proxy (HTTP)')],
        default='toledo', required=True,
        help="Toledo 8217 is the closest thing to a standard: the host sends 'W' "
             "and the scale answers a framed reading.\n\n"
             "The ASCII line protocol is what most generic bench scales send: a "
             "stability word, then the weight, e.g. 'ST,GS,   0.400kg'.")
    iot_url = fields.Char(
        string='IoT box address',
        help="Base address of the Hardware Proxy, e.g. http://10.0.0.5:8069 . "
             "Mezze asks it for the weight instead of opening a socket to the "
             "scale — the box owns the serial cable.")
    uom_name = fields.Char(
        string="Reads in", default='kg',
        help="The unit this scale is set to. It is COMPARED against the product's "
             "unit, never converted into it — a scale left in pounds against a "
             "product priced per kilo is a 2.2x error on the bill, and refusing is "
             "a cashier weighing it by hand rather than a wrong number nobody sees.")
    active = fields.Boolean(default=True)

    _scale_name_config_uniq = models.Constraint(
        'unique(name, config_id)',
        "Scale name must be unique per branch.",
    )
