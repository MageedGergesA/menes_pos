# Part of the Mezze POS platform. See LICENSE (LGPL-3).
"""Give existing branches a gift-card payment method they can actually use.

The method was found-or-created inside the payment call, and Odoo refuses to change
a ``pos.config``'s payment methods while one of its sessions is open — so on a live
till it existed but was never linked, and every gift-card payment was rejected with
"The payment method selected is not allowed in the config of the POS session."

An upgrade is the right moment: it is a structural one-off, and it is not inside the
request that needs it.
"""
from odoo import api, SUPERUSER_ID

from odoo.addons.mezze_bridge.models.loyalty_bootstrap import (
    ensure_giftcard_payment_method)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    ensure_giftcard_payment_method(env)
