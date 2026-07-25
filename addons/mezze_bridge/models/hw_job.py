"""Hardware job ledger — durable acknowledgement for print/drawer operations.

Gives the physically non-idempotent hardware consumers a persistent dedup key: a
print job is executed at most once per idempotency key (a duplicate outbox
delivery finds an existing 'done' row and is suppressed), and every drawer command
is recorded with its authorization evidence for audit + replay safety.

This is a LEDGER, not a queue — the transactional outbox remains the only queue.
"""

from odoo import api, fields, models


class MezzeHwJob(models.Model):
    _name = 'mezze.hw.job'
    _description = 'Mezze hardware job (print / drawer) acknowledgement ledger'
    _order = 'id desc'

    idempotency_key = fields.Char(required=True, index=True, copy=False)
    kind = fields.Selection([('print', 'Print'), ('drawer', 'Drawer')], required=True, index=True)
    status = fields.Selection(
        [('queued', 'Queued'), ('done', 'Done'), ('duplicate', 'Duplicate suppressed'),
         ('failed', 'Failed'), ('expired', 'Expired')],
        default='queued', required=True, index=True)
    attempts = fields.Integer(default=0)
    printer_id = fields.Many2one('mezze.printer', ondelete='set null', index=True)
    terminal = fields.Char(index=True)
    company_id = fields.Many2one('res.company', index=True)
    branch_id = fields.Many2one('pos.config', index=True)
    order_ref = fields.Char(help="Authoritative business reference (order id/uuid).")
    purpose = fields.Char()
    reason = fields.Char(help="Business reason (drawer).")
    principal = fields.Char(help="Cashier/principal that authorised the operation.")
    executed_at = fields.Datetime()
    last_error = fields.Char()

    _key_uniq = models.Constraint('unique(idempotency_key)',
                                  "One hardware job per idempotency key.")

    @api.model
    def claim(self, idempotency_key, kind, vals=None):
        """Atomically claim a job for execution. Returns (job, is_new). If a 'done'
        job already exists for this key, is_new is False and the caller must NOT
        re-execute (physical dedup). Uses a savepoint so a unique-violation race
        resolves to the existing row."""
        existing = self.sudo().search([('idempotency_key', '=', idempotency_key)], limit=1)
        if existing:
            return (existing, False)
        try:
            with self.env.cr.savepoint():
                rec = self.sudo().create(dict(vals or {}, idempotency_key=idempotency_key, kind=kind))
            return (rec, True)
        except Exception:  # noqa: BLE001 — concurrent create -> use the winner
            return (self.sudo().search([('idempotency_key', '=', idempotency_key)], limit=1), False)
