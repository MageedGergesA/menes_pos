# Part of the Mezze POS platform. See LICENSE (LGPL-3).
"""Kitchen readiness — one algorithm, answered for a whole recordset at once.

Every off-premise channel asks the KDS the same question: *is the food for this
order done?* Drive-thru and delivery each carried their own byte-identical copy of
the answer, and each copy asked it **one order at a time**. A lane board holding 36
cars therefore ran 36 KDS searches to draw one screen, and the count grew with the
queue — the one moment you least want the board to slow down.

This mixin makes that question batched and shared:

* :meth:`_kitchen_ready_map` answers for the whole recordset in ONE grouped query;
* :meth:`_kitchen_ready` keeps the existing single-record API, delegating to the
  batch so there is exactly one definition of "ready" in the product.

Deliberately NOT done here: storing readiness on the row. The KDS tickets are the
authority, and a persisted mirror would need invalidating from every ticket
transition, recall and cancel — trading a measured query cost for an unbounded
correctness cost. This batches the authoritative lookup instead of replacing it.

A consumer joins in by inheriting this mixin and having a ``pos_order_id``.
"""
from odoo import models

#: Ticket states that mean the station has finished its slice of the order.
KITCHEN_DONE_STATES = ('ready', 'served')


class MezzeKitchenReadinessMixin(models.AbstractModel):
    _name = 'mezze.kitchen.readiness.mixin'
    _description = 'Mezze Kitchen Readiness'

    def _kitchen_ready_map(self):
        """``{record_id: bool}`` — kitchen readiness for the whole recordset.

        Semantics are the ones audited in ``docs/drive_thru/KITCHEN-READINESS-BATCH-AUDIT.md``
        and are unchanged from the per-record version:

        * every ticket of the order must be ``ready``/``served``;
        * an order with no tickets at all is ready (nothing was asked of the kitchen);
        * a ``cancel``\\ led ticket blocks readiness, because ``cancel`` is not a done
          state. That behaviour is inherited on purpose — whether a cancelled station
          slice should stop a handoff is a product question, not something to settle
          inside a performance refactor.

        Expressed as "no ticket is outstanding" rather than "all tickets are done",
        the three cases collapse into a single grouped query and the empty-order case
        stops needing a special branch.

        Isolation: the domain is built from ``self``'s own orders, so a caller that
        was branch-scoped stays branch-scoped. The search is deliberately **not**
        sudoed — making a query cheaper must never make it see more.
        """
        if not self:
            return {}
        order_ids = [oid for oid in self.mapped('pos_order_id').ids if oid]
        blocked = set()
        if order_ids:
            groups = self.env['mezze.kds.ticket']._read_group(
                [('pos_order_id', 'in', order_ids),
                 ('state', 'not in', KITCHEN_DONE_STATES)],
                groupby=['pos_order_id'])
            blocked = {order.id for (order,) in groups}
        return {rec.id: rec.pos_order_id.id not in blocked for rec in self}

    def _kitchen_ready(self):
        """True when the kitchen is done with this record's order.

        Kept as the single-record API every existing caller already uses; it now
        delegates so there is one algorithm rather than two that can drift apart.
        """
        self.ensure_one()
        return self._kitchen_ready_map()[self.id]
