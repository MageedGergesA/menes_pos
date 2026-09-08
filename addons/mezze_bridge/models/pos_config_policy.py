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

    # ---- Service charge (design v3 totals: "Service charge 12%") -------------
    # A real branch levy, so it is a real PRICED LINE on the order — never a row
    # the panel adds to a total it then charges without.
    #
    # That distinction is the whole design of this feature. A service charge that
    # exists only in the browser would show the guest 12% they are not billed,
    # reach neither the receipt nor the journal nor ETA, and vanish on a refund or
    # a split. It is money, so it goes where the money is: one more line the
    # server prices, taxed like the food it is charged on.
    mezze_service_pct = fields.Float(
        string="Service charge %", digits=(5, 2), default=0.0,
        help="Percentage added to the food value of every order at this branch. "
             "0 disables it. Posted as its own order line, taxed with the same "
             "taxes as the service-charge product.")
    mezze_service_product_id = fields.Many2one(
        'product.product', string="Service-charge product", ondelete='restrict',
        help="The product the service charge posts to. Created on first use if "
             "empty, mirroring how the native tip product is provisioned.")

    def mezze_service_rate(self):
        """The branch's rate as a fraction, or 0. Clamped: a negative service
        charge is a discount wearing the wrong name, and anything above 100% is a
        typo that would otherwise double a bill."""
        self.ensure_one()
        pct = self.mezze_service_pct or 0.0
        if pct <= 0.0:
            return 0.0
        return min(pct, 100.0) / 100.0
