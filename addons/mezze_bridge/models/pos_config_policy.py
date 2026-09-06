# Part of the Mezze POS platform. See LICENSE (LGPL-3).
"""Branch staffing policy on the till (design v3 `tillBarred`).

A branch can decide that its Servers do not work the till. The prototype puts
this in Settings as "Keep servers off the till", and states what it closes:

    Register, Orders, Drive-thru, reports and End of day are closed to the
    Server role. Their own shift, tables and handheld stay open.

It lives on ``pos.config`` rather than in ``domain/settings_catalog`` because
that catalog is a FROZEN authoritative mirror of Settings.html, pinned at 101
ids by an import-time assertion and by the bootstrap tests. Widening it to carry
a policy it never described would make its name a lie. This is branch scope by
its own wording -- "THIS branch keeps servers off the till" -- which is exactly
what pos.config is.

A STAFFING policy, never a capability: the same person signed in as a cashier
reaches the till normally, and nothing here changes what a token may do.
"""
from odoo import fields, models


class PosConfig(models.Model):
    _inherit = 'pos.config'

    mezze_servers_off_till = fields.Boolean(
        string="Keep servers off the till",
        help="Register, Orders, Drive-thru, reports and End of day are closed to "
             "the Server role. Their own shift, tables and handheld stay open.")
