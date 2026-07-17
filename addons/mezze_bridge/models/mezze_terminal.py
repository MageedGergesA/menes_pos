# Part of the Mezze POS platform. See LICENSE (LGPL-3).
from odoo import fields, models


class MezzeTerminal(models.Model):
    """A registered POS terminal (an offline-capable install).

    Each terminal owns its local sales and syncs to cloud HQ. Identity is minted
    at first ``/mezze/sync/v1/register``; ``token`` authenticates that terminal's
    push/pull. ``identifier`` also namespaces the terminal's ``pos_reference``
    sequence so two offline terminals never mint the same receipt number.

    See ``docs/SYNC.md``.
    """
    _name = 'mezze.terminal'
    _description = "Mezze POS Terminal"
    _order = 'id desc'

    name = fields.Char(required=True, index=True,
                       help="Human label, e.g. 'Front counter 1'.")
    identifier = fields.Char(string="Terminal ID", index=True, copy=False,
                             help="Stable global id; also the pos_reference namespace.")
    token = fields.Char(string="Sync Token", copy=False,
                        help="Per-terminal secret for push/pull auth.")
    branch_id = fields.Many2one('pos.config', string="Branch", ondelete='set null',
                                help="The pos.config (branch) this terminal belongs to.")
    last_seen = fields.Datetime(string="Last Sync")
    last_acked_seq = fields.Integer(
        string="Last Acked Outbox Seq", default=0,
        help="Highest terminal outbox seq the cloud has ingested (exactly-once cursor).")
    active = fields.Boolean(default=True)

    _identifier_uniq = models.Constraint(
        'unique(identifier)',
        "Terminal ID must be unique.",
    )
