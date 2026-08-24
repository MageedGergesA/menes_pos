# Part of the Mezze POS platform. See LICENSE (LGPL-3).
"""Give existing branches an eWallet payment method.

Same reasoning as the gift card one version earlier: Odoo refuses to change a
``pos.config``'s payment methods while a session is open, so a method created lazily
inside the payment call exists but is never linked, and every wallet payment is
rejected. An upgrade is the moment to do it.
"""
from odoo import api, SUPERUSER_ID

from odoo.addons.mezze_bridge.models.loyalty_bootstrap import (
    ensure_giftcard_payment_method)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    ensure_giftcard_payment_method(env)
