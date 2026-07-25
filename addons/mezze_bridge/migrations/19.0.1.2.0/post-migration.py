# Part of the Mezze POS platform. See LICENSE (LGPL-3).
"""Pilot P6.5 — fingerprint any legacy plaintext terminal bearer token and blank
the plaintext. Idempotent; fails closed (no-op) without the master key; never
logs a token value."""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    try:
        n = env['mezze.terminal']._migrate_plaintext_tokens()
        if n:
            _logger.warning("Pilot: fingerprinted %d legacy terminal token(s)", n)
    except Exception:
        _logger.exception("Terminal token migration failed — aborting (fail closed)")
        raise
