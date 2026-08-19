# Part of the Mezze POS platform. See LICENSE (LGPL-3).
"""Split Bill V2 — the authoritative half.

The client's selection is an *intent*. This is where it becomes true, or is refused.

Three endpoints, and deliberately no more:

    POST /mezze/api/v1/split/state    what is on this bill, and what is still movable
    POST /mezze/api/v1/split/commit   move it, under a lock, exactly once
    POST /mezze/api/v1/split/family   the whole dining event, root and children

There is no ``preview`` endpoint. Exploring a split creates nothing and asks the
server nothing: the workspace previews locally, because a cashier dragging
quantities around while a guest decides must not be writing to a database. The
server sees one call, at the moment the cashier commits.

Why a split cannot be done in the browser, which is how Odoo's own POS does it:

* **Availability is a race.** Two terminals hold the same table; both see three
  burgers; both move two. Only a server holding a row lock can refuse the second.
* **Money must not be transferred.** The client sends line ids and quantities and
  nothing else — no price, no tax, no total. Amounts come from copying the origin
  lines and letting Odoo compute, so a tampered client cannot invent a discount.
* **The kitchen must not hear about it.** A financial split of already-fired food
  is not new demand, and the only place that can be guaranteed is where the fired
  snapshot lives.
"""
import json
import logging
import uuid as uuid_lib

from odoo import fields, http
from odoo.http import request

from ..domain import authz, split_bill
from .main import API_PREFIX, MezzeBridgeController

_logger = logging.getLogger(__name__)


class MezzeSplitBill(MezzeBridgeController):

    # ------------------------------------------------------------------ helpers
    def _root(self, env, order_id):
        order = env['pos.order'].browse(int(order_id or 0))
        return order if order.exists() else env['pos.order'].browse()

    def _line_state(self, order):
        """The movable picture of an order, as the workspace needs it.

        ``allocated`` is what earlier splits already took from this line. It is
        derived from the children rather than stored, so it cannot drift out of
        step with the orders it describes.
        """
        allocated = {}
        root = order.mezze_split_root_id or order
        for child in root.mezze_split_child_ids:
            for line in child.lines:
                origin = line.mezze_split_origin_line_id
                if origin:
                    allocated[origin.id] = allocated.get(origin.id, 0.0) + line.qty
        out = {}
        for line in order.lines:
            out[line.id] = {
                'qty': line.qty,
                'allocated': allocated.get(line.id, 0.0),
                'combo_parent_id': line.combo_parent_id.id or None,
                'combo_children': line.combo_line_ids.ids,
                'paid': order.state not in ('draft',),
            }
        return out

    def _line_payload(self, order):
        state = self._line_state(order)
        rows = []
        for line in order.lines:
            st = state[line.id]
            # A combo CHILD is shown as part of its parent, never as its own
            # selectable row: the commercial unit is the configured parent.
            rows.append({
                'id': line.id,
                'product_id': line.product_id.id,
                'name': line.full_product_name or line.product_id.display_name,
                'note': line.customer_note or '',
                'qty': line.qty,
                'allocated': st['allocated'],
                'available': split_bill.available(st),
                'price_unit': line.price_unit,
                'price_subtotal_incl': line.price_subtotal_incl,
                'discount': line.discount,
                'combo_parent_id': st['combo_parent_id'],
                'combo_children': st['combo_children'],
                'is_combo_child': bool(st['combo_parent_id']),
            })
        return rows

    def _order_payload(self, order):
        return {
            'id': order.id,
            'reference': order.pos_reference,
            'tracking': order.tracking_number or '',
            'state': order.state,
            'amount_total': order.amount_total,
            'amount_paid': order.amount_paid,
            'revision': order.mezze_revision or 0,
            'split_seq': order.mezze_split_seq or 0,
            'split_uuid': order.mezze_split_uuid or '',
            'table': {'id': order.table_id.id, 'name': order.table_id.table_number}
                     if order.table_id else None,
            'covers': order.customer_count or 0,
        }

    # ------------------------------------------------------------------- state
    @http.route(f'{API_PREFIX}/split/state', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*', readonly=True)
    def split_state(self, order_id=None, **kw):
        """Everything the workspace needs to open, in ONE call.

        Deliberately one round trip regardless of how many lines the bill has: a
        fifty-line table must not become fifty requests, and the whole selection
        experience afterwards is local.
        """
        env = self._api_env()
        order = self._root(env, order_id)
        if not order:
            return self._json({'ok': False, 'error': 'unknown_order'}, status=404)
        denied = self._security_gate(env, 'split/state', target=order)
        if denied:
            return denied
        root = order.mezze_split_root_id or order
        return {
            'ok': True,
            'order': self._order_payload(order),
            'root': self._order_payload(root),
            'lines': self._line_payload(order),
            'family': [self._order_payload(o) for o in order.mezze_split_family()]
                      if (root.mezze_split_child_ids) else [],
            # By seat is not offered, and the reason is told rather than hidden.
            'modes': {
                'items': True,
                'seat': False,
                'seat_reason': 'no_seat_model',
                'even': True,
            },
        }

    # ------------------------------------------------------------------ commit
    @http.route(f'{API_PREFIX}/split/commit', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*', readonly=False)
    def split_commit(self, order_id=None, allocations=None, expected_revision=None,
                     idempotency_key=None, **kw):
        """Move the selected quantities onto a new child check.

        Everything that can refuse this happens before anything is written, and the
        row is locked first so the picture cannot change underneath the checks.
        """
        env = self._api_env()
        order = self._root(env, order_id)
        if not order:
            return self._json({'ok': False, 'error': 'unknown_order'}, status=404)
        denied = self._security_gate(env, 'split/commit', target=order)
        if denied:
            return denied

        if not idempotency_key:
            return self._json({'ok': False, 'error': 'idempotency_key_required'}, status=400)

        # A double tap is one split. The key is claimed BEFORE the work, so the
        # second request loses the race rather than doing the work twice and
        # discovering the conflict afterwards.
        prior = env['pos.order'].sudo().search(
            [('mezze_split_uuid', '=', str(idempotency_key))], limit=1)
        if prior:
            root = prior.mezze_split_root_id or prior
            return {'ok': True, 'duplicate': True,
                    'child': self._order_payload(prior),
                    'root': self._order_payload(root),
                    'lines': self._line_payload(root),
                    'family': [self._order_payload(o) for o in prior.mezze_split_family()]}

        # LOCK the root for the rest of the transaction. Everything after this reads
        # quantities nobody else can be changing.
        env.cr.execute("SELECT id FROM pos_order WHERE id = %s FOR UPDATE", (order.id,))
        order.invalidate_recordset()

        if expected_revision is not None and int(expected_revision) != int(order.mezze_revision or 0):
            # Another station changed this bill. Not an error to log with a stack —
            # a normal thing that happens on a busy floor, and the client redraws.
            return self._json({'ok': False, 'error': 'stale_revision',
                               'revision': order.mezze_revision or 0}, status=409)

        allocations = allocations or []
        state = self._line_state(order)
        allocations = split_bill.expand_combo_selection(state, allocations)
        reason = split_bill.validate(state, allocations)
        if reason:
            return self._json({'ok': False, 'error': reason,
                               'revision': order.mezze_revision or 0}, status=400)

        child = self._create_child(env, order, allocations, idempotency_key)
        order.invalidate_recordset()
        root = order.mezze_split_root_id or order
        return {
            'ok': True,
            'duplicate': False,
            'child': self._order_payload(child),
            'root': self._order_payload(order),
            'lines': self._line_payload(order),
            'family': [self._order_payload(o) for o in child.mezze_split_family()],
        }

    def _create_child(self, env, root_order, allocations, family_key):
        """Create the child check and take the quantities off the original.

        Lines are COPIED, not rebuilt from the product: a split moves the item that
        was actually sold, with the price and line discount it was actually sold at.
        Taxes are not transferred — the copy carries the same ``tax_ids`` and Odoo
        computes the amounts, so the child's VAT is Odoo's answer, not ours.
        """
        Order = env['pos.order'].sudo()
        root = root_order.mezze_split_root_id or root_order
        seq = 1 + len(root.mezze_split_child_ids)
        now = fields.Datetime.now()

        principal = {}
        try:
            principal = self._resolve_principal(env) or {}
        except Exception:  # noqa: BLE001
            principal = {}
        cashier = principal.get('cashier')

        child = Order.create({
            'session_id': root_order.session_id.id,
            'company_id': root_order.company_id.id,
            'user_id': root_order.user_id.id,
            'partner_id': False,           # a split check is anonymous until someone claims it
            'pricelist_id': root_order.pricelist_id.id or False,
            'fiscal_position_id': root_order.fiscal_position_id.id or False,
            'table_id': root_order.table_id.id or False,
            # Covers stay with the ORIGINAL. Four people who split four ways are still
            # four covers, and native's decrement is exactly how a family ends up
            # reporting sixteen.
            'customer_count': 0,
            'amount_tax': 0.0, 'amount_total': 0.0,
            'amount_paid': 0.0, 'amount_return': 0.0,
            'mezze_split_root_id': root.id,
            'mezze_split_parent_id': root_order.id,
            'mezze_split_seq': seq,
            'mezze_split_uuid': str(family_key),
            'mezze_split_by_id': cashier.id if cashier else False,
            'mezze_split_at': now,
            'mezze_channel': root_order.mezze_channel or False,
            'mezze_service_mode': root_order.mezze_service_mode or False,
            'mezze_terminal_id': (principal.get('terminal').id
                                  if principal.get('terminal') else False),
            'mezze_cashier_id': cashier.id if cashier else False,
        })

        # Parents before children, so a combo child can point at its new parent.
        by_id = {int(a['origin_line_id']): float(a['quantity']) for a in allocations}
        origin_lines = env['pos.order.line'].sudo().browse(sorted(by_id)).exists()
        # Read the line -> product map BEFORE anything is mutated: a line that is
        # fully moved gets unlinked below, and asking a deleted record for its
        # product is how the drain case turned into a 404.
        product_of_line = {line.id: line.product_id.id for line in origin_lines}
        parents_first = origin_lines.sorted(lambda l: (bool(l.combo_parent_id), l.id))
        new_by_origin = {}
        drained = env['pos.order.line'].sudo().browse()

        for line in parents_first:
            qty = by_id[line.id]
            vals = {
                'order_id': child.id,
                'qty': qty,
                'mezze_split_origin_line_id': line.id,
                'combo_parent_id': False,
            }
            if line.combo_parent_id and line.combo_parent_id.id in new_by_origin:
                vals['combo_parent_id'] = new_by_origin[line.combo_parent_id.id].id
            new_line = line.copy(vals)
            new_by_origin[line.id] = new_line
            remaining = line.qty - qty
            if remaining <= split_bill.EPS:
                drained |= line
            else:
                line.write({'qty': remaining})

        if drained:
            drained.unlink()

        # KDS: move the FIRED quantities, do not create demand. A bill divided after
        # the food was sent is not a second order for the kitchen.
        try:
            fired = json.loads(root_order.mezze_fired or '{}')
        except Exception:  # noqa: BLE001
            fired = {}
        root_fired, child_fired = split_bill.transfer_fired(fired, allocations, product_of_line)
        root_order.sudo().write({'mezze_fired': json.dumps(root_fired)})
        child.sudo().write({'mezze_fired': json.dumps(child_fired)})

        root_order.mezze_bump_revision()
        child.mezze_bump_revision()

        self._audit(env, 'order.split', order=child,
                    detail='root=%s seq=%s lines=%s' % (root_order.id, seq, len(allocations)))
        return child

    # ------------------------------------------------------------------ family
    @http.route(f'{API_PREFIX}/split/family', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*', readonly=True)
    def split_family(self, order_id=None, **kw):
        """One dining event, every check on it.

        Reachable from any member, because a cashier who opens Check 2 should see
        the same picture as one who opened the original.
        """
        env = self._api_env()
        order = self._root(env, order_id)
        if not order:
            return self._json({'ok': False, 'error': 'unknown_order'}, status=404)
        denied = self._security_gate(env, 'split/family', target=order)
        if denied:
            return denied
        family = order.mezze_split_family()
        checks = []
        for member in family:
            payments = [{'method': p.payment_method_id.name, 'amount': p.amount}
                        for p in member.payment_ids]
            checks.append({
                **self._order_payload(member),
                'is_root': not member.mezze_split_root_id,
                'payments': payments,
                'paid': member.state in ('paid', 'done', 'invoiced'),
            })
        return {
            'ok': True,
            'family_total': sum(m.amount_total for m in family),
            'covers': (family[0].customer_count or 0) if family else 0,
            'checks': checks,
        }
