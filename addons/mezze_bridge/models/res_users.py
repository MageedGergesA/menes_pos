# Part of the Mezze POS platform. See LICENSE (LGPL-3).
"""Who the signed-in Odoo user is, as far as the Mezze surfaces need to know.

This exists so a controller never has to ask a group question itself. The
structural security guard forbids ``has_group(`` inside ``controllers/`` — not
because a display hint is dangerous, but because "this one is only cosmetic" is
an argument that has to be re-litigated at every review, and the guard's value is
that it never has to be. Group questions belong with the security stack; the
controller asks a named question and gets a boolean.
"""
from odoo import api, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    @api.model
    def _mezze_is_pos_manager(self):
        """True when this user may be shown manager-only affordances.

        A display hint ONLY — nothing is authorized on the strength of it. Every
        privileged operation goes through the Mezze gate (capability + scope) or
        Odoo's own record rules, both of which re-check on the server.
        """
        return self.env.user.has_group('point_of_sale.group_pos_manager')
