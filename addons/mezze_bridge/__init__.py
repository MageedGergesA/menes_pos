# Part of the Mezze POS platform. See LICENSE (LGPL-3).
import secrets

from . import models
from . import wizard
from . import controllers

TOKEN_PARAM = 'mezze_bridge.api_token'


def post_init_generate_token(env):
    """On install, replace an unset or weak (`test123`) shared API token with a
    strong random secret, so the guessable default can never authenticate in a
    real deployment. Admins can rotate it any time via the ir.config_parameter."""
    icp = env['ir.config_parameter'].sudo()
    current = icp.get_param(TOKEN_PARAM)
    if not current or current == 'test123':
        icp.set_param(TOKEN_PARAM, secrets.token_urlsafe(32))
    # Loyalty needs a programme to exist before any of it means anything. It is
    # created here, on a writable install cursor, rather than lazily on first read —
    # see models/loyalty_bootstrap.py for why the lazy version cannot work.
    from .models.loyalty_bootstrap import (
        ensure_giftcard_payment_method, ensure_loyalty_program)
    try:
        ensure_loyalty_program(env)
        ensure_giftcard_payment_method(env)
    except Exception:  # noqa: BLE001 — a sale must never be blocked by a programme
        import logging
        logging.getLogger(__name__).exception(
            "Mezze could not provision the loyalty programme")
