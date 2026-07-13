# Part of the Mezze POS platform. See LICENSE (LGPL-3).
import secrets

from . import models
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
