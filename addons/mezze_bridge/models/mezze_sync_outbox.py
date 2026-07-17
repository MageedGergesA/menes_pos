# Part of the Mezze POS platform. See LICENSE (LGPL-3).
from odoo import fields, models


class MezzeSyncOutbox(models.Model):
    """Durable, ordered change journal on the TERMINAL side.

    Every syncable mutation appends one row; the sync worker drains it in ``seq``
    order and flips ``synced`` on cloud ack. It survives crashes and offline
    stretches because it is a Postgres table. ``res_uuid`` is the idempotency key
    (exactly-once apply on the cloud); ``seq`` is the ordering key.

    Payloads carry DELTAS, not absolute state (e.g. ``{"delta": -1}``), so events
    commute and reconcile order-independently. See ``docs/SYNC.md``.
    """
    _name = 'mezze.sync.outbox'
    _description = "Mezze Sync Outbox (terminal change journal)"
    _order = 'seq asc'

    seq = fields.Integer(string="Sequence", required=True, index=True,
                         help="Monotonic per-terminal ordering key.")
    model = fields.Char(required=True, index=True,
                        help="Source model, e.g. 'pos.order', 'loyalty.history', 'mezze.stock.delta'.")
    res_uuid = fields.Char(string="Record UUID", required=True, index=True,
                           help="Global idempotency key for exactly-once apply on the cloud.")
    op = fields.Selection(
        selection=[('create', "Create"), ('write', "Write"), ('unlink', "Unlink")],
        required=True, default='create')
    payload = fields.Text(help="JSON event body — a delta, not absolute state.")
    synced = fields.Boolean(default=False, index=True,
                            help="Set once the cloud has acked this seq.")

    _seq_uniq = models.Constraint(
        'unique(seq)',
        "Outbox seq must be unique per terminal DB.",
    )


class MezzeSyncCursor(models.Model):
    """Pull watermark: the highest ``write_date`` already pulled+applied per model.

    On the terminal the worker advances one row per config model it mirrors from
    the cloud (products, taxes, floor, users, loyalty definitions). The cloud's
    push cursor lives on ``mezze.terminal.last_acked_seq`` instead. See
    ``docs/SYNC.md``.
    """
    _name = 'mezze.sync.cursor'
    _description = "Mezze Sync Cursor (pull watermark)"
    _order = 'model'

    model = fields.Char(required=True, index=True,
                        help="Model this watermark tracks.")
    last_pulled = fields.Datetime(
        help="Highest write_date pulled + applied for this model.")

    _model_uniq = models.Constraint(
        'unique(model)',
        "One watermark row per model.",
    )
