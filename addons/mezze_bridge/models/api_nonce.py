from odoo import api, fields, models


class MezzeApiNonce(models.Model):
    """Durable single-use nonce store for API replay protection.

    A signed request carries a nonce; the first time (principal, nonce) is seen
    it is claimed, and any later request with the same pair is a replay. The
    unique DB constraint makes the claim atomic and race-safe across workers.
    """
    _name = 'mezze.api.nonce'
    _description = 'Mezze API request nonce (replay protection)'

    principal = fields.Char(required=True, index=True)
    nonce = fields.Char(required=True, index=True)
    seen_at = fields.Datetime(default=fields.Datetime.now, index=True)

    _principal_nonce_uniq = models.Constraint(
        'unique(principal, nonce)',
        'This API request nonce has already been used (replay).')

    @api.model
    def claim(self, principal, nonce):
        """Atomically claim (principal, nonce). Returns True if first use, False
        if it was already claimed (a replay). Race-safe via the unique
        constraint: a concurrent duplicate hits the constraint and returns False.
        """
        if not principal or not nonce:
            return False
        try:
            with self.env.cr.savepoint():
                self.sudo().create({'principal': str(principal), 'nonce': str(nonce)})
            return True
        except Exception:  # noqa: BLE001 — unique violation == replay
            return False

    @api.model
    def gc(self, before_dt, limit=None):
        """Prune nonces older than ``before_dt`` (bounded by ``limit``). Returns the
        count deleted. Safe: once the replay window has passed, the timestamp check
        rejects the request regardless of nonce history, so an old nonce is never
        needed for replay protection."""
        stale = self.sudo().search([('seen_at', '<', before_dt)], limit=limit or 0)
        n = len(stale)
        stale.unlink()
        return n

    @api.model
    def _cron_gc(self):
        """Scheduled cleanup. Retention (default 1h) is deliberately GREATER than
        the replay window (300s), so an in-window nonce is never removed. Bounded
        per run; idempotent; failure is logged and never blocks business requests."""
        icp = self.env['ir.config_parameter'].sudo()
        retention = int(icp.get_param('mezze_bridge.nonce_retention_seconds', 3600) or 3600)
        limit = int(icp.get_param('mezze_bridge.nonce_gc_limit', 10000) or 10000)
        cutoff = fields.Datetime.subtract(fields.Datetime.now(), seconds=retention)
        return self.gc(cutoff, limit=limit)
