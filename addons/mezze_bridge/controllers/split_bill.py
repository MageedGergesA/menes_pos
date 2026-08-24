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

    # A ceiling on "split evenly". Not arithmetic — the maths is fine at any size —
    # but a bill divided into hundreds of shares is a mis-typed number, and each
    # share still has to be tendered by hand.
    EVEN_MAX_WAYS = 50

    # ------------------------------------------------------------------ helpers
    def _root(self, env, order_id=None, uuid=None):
        """Resolve a bill by whichever identity the caller actually holds.

        The Register tracks orders by ``uuid`` (that is what ``/orders/get`` takes),
        while a backend or a test holds the database id. Accepting both keeps the
        client from having to learn a second identity for one screen.
        """
        Order = env['pos.order']
        if order_id:
            order = Order.browse(int(order_id))
            if order.exists():
                return order
        if uuid:
            return Order.search([('uuid', '=', str(uuid))], limit=1)
        return Order.browse()

    def _line_state(self, order):
        """The movable picture of an order, as the workspace needs it.

        ``moved_away`` is what earlier splits already took, derived from the
        children rather than stored so it cannot drift out of step with the orders
        it describes. It is INFORMATION, not a reservation: when units move, the
        root's own ``qty`` is decremented, so subtracting them again would strand
        the remainder — a bill split once would show its last item as unavailable
        and no second guest could ever take it.
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
                # Nothing is held back ON this line: what left is already off it.
                'allocated': 0.0,
                'moved_away': allocated.get(line.id, 0.0),
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
                'allocated': st['moved_away'],
                'available': split_bill.available(st),
                'price_unit': line.price_unit,
                'price_subtotal_incl': line.price_subtotal_incl,
                'discount': line.discount,
                'combo_parent_id': st['combo_parent_id'],
                'combo_children': st['combo_children'],
                'is_combo_child': bool(st['combo_parent_id']),
                # 0 is UNASSIGNED, not seat zero.
                'seat': int(line.mezze_seat or 0),
            })
        return rows

    def _order_payload(self, order):
        return {
            'id': order.id,
            # The Register pays by uuid (/orders/pay takes one), so a child that
            # cannot name itself that way cannot be handed to Payment — which is the
            # whole point of Split & Pay.
            'uuid': order.uuid or '',
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
    def split_state(self, order_id=None, uuid=None, **kw):
        """Everything the workspace needs to open, in ONE call.

        Deliberately one round trip regardless of how many lines the bill has: a
        fifty-line table must not become fifty requests, and the whole selection
        experience afterwards is local.
        """
        # AUTHENTICATE before touching the database. Resolving the bill first meant
        # an anonymous caller learned whether an order id existed — a 404 for a
        # stranger's order and something else for a real one is an oracle — and it
        # did that work before establishing who was asking. The house order is:
        # authenticate, resolve, then gate the resolved target for scope.
        auth = self._authorize()
        if auth:
            return auth
        env = self._api_env()
        order = self._root(env, order_id, uuid)
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
            'modes': self._modes(order),
        }

    # --------------------------------------------------------------- by seat
    def _seat_groups(self, order):
        """What each seat still owes, computed HERE.

        The same rule as "split evenly": the shares are the server's arithmetic, not
        the browser's, because they have to reconcile back to the bill. A seat's
        total is built from the line's own ``price_subtotal_incl`` scaled by what is
        still movable, so a line already half-moved onto another check contributes
        half — the seat is shown what is left of it, not what was ordered.

        Unassigned lines are returned separately and are NEVER folded into a seat.
        A bottle of wine in the middle of the table belongs to nobody in particular,
        and quietly attaching it to seat 1 is the kind of thing a guest notices at
        the moment they are handed a card machine.
        """
        state = self._line_state(order)
        seats, shared = {}, []
        for line in order.lines:
            st = state[line.id]
            if st['combo_parent_id']:
                continue          # travels with its parent; never its own row
            avail = split_bill.available(st)
            if avail <= 0:
                continue
            qty = float(line.qty or 0.0)
            share = (line.price_subtotal_incl or 0.0) * (avail / qty) if qty else 0.0
            row = {'line_id': line.id,
                   'name': line.full_product_name or line.product_id.display_name,
                   'qty': avail, 'amount': round(share, 2)}
            seat = int(line.mezze_seat or 0)
            if seat:
                bucket = seats.setdefault(seat, {'seat': seat, 'lines': [], 'amount': 0.0})
                bucket['lines'].append(row)
                bucket['amount'] = round(bucket['amount'] + share, 2)
            else:
                shared.append(row)
        return ([seats[k] for k in sorted(seats)],
                shared,
                round(sum(r['amount'] for r in shared), 2))

    def _modes(self, order):
        """Which ways this bill can be divided, and why not.

        "By seat" was permanently disabled with the reason ``no_seat_model`` — true
        at the time, and useless to a cashier, because there was nothing they could
        do about it. Now the reason is actionable: it is off when nothing on this
        bill has been assigned to a seat yet, which is a thing the cashier can fix
        on the order panel.
        """
        seated = any(int(l.mezze_seat or 0) for l in order.lines)
        return {
            'items': True,
            'seat': bool(seated),
            'seat_reason': '' if seated else 'no_seats_assigned',
            'even': True,
        }

    @http.route(f'{API_PREFIX}/split/seats', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*', readonly=True)
    def split_seats(self, order_id=None, uuid=None, **kw):
        """What each seat at this table owes.

        A preview, so it writes nothing: the cashier turns it into checks through
        the ordinary ``/split/commit``, one call per seat, which keeps every
        invariant that already holds — availability under a row lock, combos moving
        whole, idempotency, and the kitchen hearing nothing.
        """
        auth = self._authorize()
        if auth:
            return auth
        env = self._api_env()
        order = self._root(env, order_id, uuid)
        if not order:
            return self._json({'ok': False, 'error': 'unknown_order'}, status=404)
        denied = self._security_gate(env, 'split/seats', target=order)
        if denied:
            return denied
        seats, shared, shared_total = self._seat_groups(order)
        return {
            'ok': True,
            'order': self._order_payload(order),
            'seats': seats,
            'shared': shared,
            'shared_total': shared_total,
            'modes': self._modes(order),
        }

    # -------------------------------------------------------------------- even
    @http.route(f'{API_PREFIX}/split/even', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*', readonly=True)
    def split_even(self, order_id=None, uuid=None, ways=None, **kw):
        """"Four people, one bill" — the shares, computed by the SERVER.

        ``domain.split_bill.even_amounts`` has existed and been unit-tested all along,
        and nothing in the product called it: ``split/state`` even advertised
        ``modes.even = True``, which was a promise the till could not keep.

        Splitting evenly is a PAYMENT pattern, not a restructuring of the order. The
        items are not moved and no child checks are created — four people paying a
        quarter each still ate one meal, and the kitchen, the reports and the audit
        trail should go on seeing one order. Each share is then tendered through the
        ordinary payment route, which brings its own ceilings and approvals with it.

        The arithmetic is done here rather than in the browser because the shares must
        provably sum back to the bill: 100 into 3 is 33.34 / 33.33 / 33.33, never
        99.99 and never 100.01, with the odd cents going to the earliest shares
        deterministically so the same bill always divides the same way.
        """
        auth = self._authorize()
        if auth:
            return auth
        env = self._api_env()
        order = self._root(env, order_id, uuid)
        if not order:
            return self._json({'ok': False, 'error': 'unknown_order'}, status=404)
        denied = self._security_gate(env, 'split/even', target=order)
        if denied:
            return denied
        try:
            n = int(ways or 0)
        except (TypeError, ValueError):
            n = 0
        if n < 2:
            return self._json(
                {'ok': False, 'error': 'invalid_ways',
                 'message': 'Split evenly needs at least two people.'}, status=400)
        if n > self.EVEN_MAX_WAYS:
            return self._json(
                {'ok': False, 'error': 'too_many_ways',
                 'message': 'That is more shares than this bill can be split into.',
                 'max': self.EVEN_MAX_WAYS}, status=400)

        precision = order.currency_id.decimal_places or 2
        paid = sum(p.amount for p in order.payment_ids)
        # Divide what is LEFT, not the original total. A table that already put down
        # a deposit is not four equal shares of the whole bill any more, and quoting
        # them as if it were over-collects.
        remaining = round(order.amount_total - paid, precision)
        if remaining <= 0:
            return self._json({'ok': False, 'error': 'nothing_due',
                               'message': 'This order is already settled.'}, status=400)
        parts = split_bill.even_amounts(remaining, n, precision)
        return {
            'ok': True,
            'order_id': order.id,
            'uuid': order.uuid,
            'ways': n,
            'amount_total': round(order.amount_total, precision),
            'amount_paid': round(paid, precision),
            'remaining': remaining,
            'parts': parts,
            # Stated, not assumed: the caller can check the promise this endpoint
            # exists to keep.
            'reconciles': split_bill.reconciles(remaining, parts, precision),
            'currency': order.currency_id.name or '',
        }

    # ------------------------------------------------------------------ commit
    @http.route(f'{API_PREFIX}/split/commit', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*', readonly=False)
    def split_commit(self, order_id=None, uuid=None, allocations=None,
                     expected_revision=None, idempotency_key=None, **kw):
        """Move the selected quantities onto a new child check.

        Everything that can refuse this happens before anything is written, and the
        row is locked first so the picture cannot change underneath the checks.
        """
        # AUTHENTICATE before touching the database. Resolving the bill first meant
        # an anonymous caller learned whether an order id existed — a 404 for a
        # stranger's order and something else for a real one is an oracle — and it
        # did that work before establishing who was asking. The house order is:
        # authenticate, resolve, then gate the resolved target for scope.
        auth = self._authorize()
        if auth:
            return auth
        env = self._api_env()
        order = self._root(env, order_id, uuid)
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

    def _reprice_lines(self, lines):
        """Recompute the STORED per-line money after a quantity changes.

        pos.order.line.price_subtotal / price_subtotal_incl are stored fields the
        normal flow fills from the UI payload — they do not recompute when qty is
        written. Splitting therefore left the root's line claiming the money for a
        quantity it no longer has: a line showing qty 1 and a subtotal for 2, which
        is how "the tax is right in some places and wrong in others" happens. The
        order total was correct (it is derived from qty x price) while every
        line-level figure disagreed with it.

        Uses Odoo's own per-line computation so the tax engine, not this file,
        decides the numbers.
        """
        for line in lines:
            if not line.exists():
                continue
            line.write(line._compute_amount_line_all())
        return True

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
                # The seat travels. ``mezze_seat`` is copy=False — right for an
                # ordinary duplicate of an order, wrong here: a check handed to seat
                # 1 that has forgotten it is seat 1 cannot be reconciled with the
                # table afterwards, and a second split of the remainder would offer
                # that seat all over again.
                'mezze_seat': line.mezze_seat,
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

        # The root's surviving lines and every copied child line now hold money for
        # the wrong quantity until they are recomputed.
        self._reprice_lines(child.lines)
        self._reprice_lines(root_order.lines)

        # pos.order.amount_total is a PLAIN STORED field, not a computed one — the
        # normal flow fills it through sync_from_ui. A child assembled by copying
        # lines therefore starts at zero, which quietly breaks payment ("overpay,
        # remaining 0.00"), the receipt and every report. Recompute both sides
        # through Odoo's own _compute_prices so the tax engine, not this file,
        # decides the numbers.
        (child | root_order)._compute_prices()

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

    # --------------------------------------------------------------- recombine
    @http.route(f'{API_PREFIX}/split/recombine', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*', readonly=False)
    def split_recombine(self, child_id=None, uuid=None, idempotency_key=None, **kw):
        """Undo a split: fold a child check back into the bill it came from.

        Before payment this should be easy, because a cashier who mis-taps needs a
        way back that is not a refund. After payment it is not a split question at
        all — money has moved, and unpicking it is a correction that belongs to
        refund/reopen with a human behind it. So a PAID child is refused here,
        loudly, rather than quietly reversed.

        Lines go back to the line they came from where that line still exists, and
        are re-parented onto the root where it does not — a fully drained line was
        unlinked, so provenance is the only way home.
        """
        # AUTHENTICATE before touching the database. Resolving the bill first meant
        # an anonymous caller learned whether an order id existed — a 404 for a
        # stranger's order and something else for a real one is an oracle — and it
        # did that work before establishing who was asking. The house order is:
        # authenticate, resolve, then gate the resolved target for scope.
        auth = self._authorize()
        if auth:
            return auth
        env = self._api_env()
        child = self._root(env, child_id, uuid)
        if not child:
            return self._json({'ok': False, 'error': 'unknown_order'}, status=404)
        denied = self._security_gate(env, 'split/recombine', target=child)
        if denied:
            return denied
        root = child.mezze_split_root_id
        if not root:
            return self._json({'ok': False, 'error': 'not_a_split_child'}, status=400)

        env.cr.execute("SELECT id FROM pos_order WHERE id IN %s FOR UPDATE",
                       (tuple({root.id, child.id}),))
        child.invalidate_recordset()

        # Paid value is not moved by an ordinary split screen.
        if child.state not in ('draft',) or (child.amount_paid or 0) > split_bill.EPS:
            return self._json({'ok': False, 'error': split_bill.REASON_PAID}, status=403)

        moved = 0
        for line in child.lines:
            origin = line.mezze_split_origin_line_id
            if origin and origin.exists() and origin.order_id.id == root.id:
                origin.write({'qty': origin.qty + line.qty})
            else:
                # The seat comes home with the item, for the same reason it left
                # with it: a check recombined by mistake must not cost the table its
                # seat assignments.
                line.copy({'order_id': root.id, 'mezze_split_origin_line_id': False,
                           'combo_parent_id': False, 'mezze_seat': line.mezze_seat})
            moved += 1

        # The fired snapshot goes home with the food.
        try:
            root_fired = json.loads(root.mezze_fired or '{}')
            child_fired = json.loads(child.mezze_fired or '{}')
        except Exception:  # noqa: BLE001
            root_fired, child_fired = {}, {}
        for key, qty in child_fired.items():
            root_fired[key] = root_fired.get(key, 0.0) + qty
        root.sudo().write({'mezze_fired': json.dumps(root_fired)})

        self._reprice_lines(root.lines)
        child.lines.unlink()
        child.sudo().write({'state': 'cancel', 'mezze_fired': json.dumps({})})
        # Same reason as the commit: the totals are stored, not computed, so an undo
        # that did not recompute would leave the bill claiming the split-away money
        # was still gone.
        (root | child)._compute_prices()
        root.mezze_bump_revision()
        self._audit(env, 'order.split_recombined', order=root,
                    detail='child=%s lines=%s' % (child.id, moved))
        root.invalidate_recordset()
        return {
            'ok': True,
            'root': self._order_payload(root),
            'lines': self._line_payload(root),
            'family': [self._order_payload(o) for o in root.mezze_split_family()],
        }

    # ------------------------------------------------------------------ family
    @http.route(f'{API_PREFIX}/split/family', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*', readonly=True)
    def split_family(self, order_id=None, uuid=None, **kw):
        """One dining event, every check on it.

        Reachable from any member, because a cashier who opens Check 2 should see
        the same picture as one who opened the original.
        """
        # AUTHENTICATE before touching the database. Resolving the bill first meant
        # an anonymous caller learned whether an order id existed — a 404 for a
        # stranger's order and something else for a real one is an oracle — and it
        # did that work before establishing who was asking. The house order is:
        # authenticate, resolve, then gate the resolved target for scope.
        auth = self._authorize()
        if auth:
            return auth
        env = self._api_env()
        order = self._root(env, order_id, uuid)
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
