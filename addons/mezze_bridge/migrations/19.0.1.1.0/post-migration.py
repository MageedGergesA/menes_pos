# Part of the Mezze POS platform. See LICENSE (LGPL-3).
"""P6.2 — migrate legacy plaintext aggregator HMAC secrets to envelope ciphertext
and drop the orphan plaintext column. Idempotent; fails closed (raises) only if
plaintext secrets exist AND the master key is unavailable — never stores plaintext."""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    try:
        n = env['mezze.aggregator']._migrate_plaintext_secrets()
        if n:
            _logger.warning("P6.2: encrypted %d legacy aggregator secret(s)", n)
    except Exception:
        _logger.exception("P6.2 secret migration failed — aborting (fail closed)")
        raise
