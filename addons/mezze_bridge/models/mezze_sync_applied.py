# Part of the Mezze POS platform. See LICENSE (LGPL-3).
from odoo import fields, models


class MezzeSyncApplied(models.Model):
    """Cloud-side reconcile ledger for offline outbox events.

    One row per event the cloud has processed from a terminal's push batch. It
    serves three jobs:

      * **Exactly-once** — unique ``(terminal, res_uuid)`` means a replayed event
        (partial batch, crash-then-resend) is recognised and skipped, on top of
        the ``last_acked_seq`` cursor.
      * **Dead-letter** — a poison event that can't apply is recorded ``failed``
        (with the error + payload) and the cursor advances past it, so one bad
        event never blocks a terminal's whole queue. Managers can inspect/replay.
      * **Reconcile flags** — commutative stock/loyalty merges that drove a
        balance negative are recorded ``flagged`` (``note`` = why) so the manager
        reconcile surface can show "sold offline past zero" as a business event.

    See ``docs/SYNC.md``.
    """
    _name = 'mezze.sync.applied'
    _description = "Mezze Sync Applied Event (cloud reconcile ledger)"
    _order = 'id desc'

    terminal_id = fields.Many2one('mezze.terminal', required=True,
                                  ondelete='cascade', index=True)
    config_id = fields.Many2one('pos.config', related='terminal_id.branch_id',
                                store=True, index=True)
    seq = fields.Integer(index=True, help="The terminal outbox seq this event carried.")
    res_uuid = fields.Char(required=True, index=True,
                           help="Global idempotency key of the event.")
    model = fields.Char(index=True, help="Event source model, e.g. pos.order.")
    op = fields.Char()
    state = fields.Selection(
        [('applied', 'Applied'), ('skipped', 'Skipped (duplicate)'),
         ('flagged', 'Applied — flagged'), ('failed', 'Failed (dead-letter)')],
        required=True, default='applied', index=True)
    note = fields.Char(help="Reconcile flag reason, e.g. negative_stock / negative_points.")
    error = fields.Text(help="Traceback/message for a dead-lettered event.")
    pos_order_id = fields.Many2one('pos.order', ondelete='set null')
    payload = fields.Text(help="The raw event body (kept for failed events so they can be replayed).")

    _term_uuid_uniq = models.Constraint(
        'unique(terminal_id, res_uuid)',
        "An outbox event is applied once per terminal (idempotency).",
    )
