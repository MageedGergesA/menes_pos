from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import float_compare


class PosOrder(models.Model):
    _inherit = 'pos.order'

    # JSON {product_id: qty} of what Mezze has already fired to the kitchen for
    # this (draft) order. Lets a re-fire send ONLY the newly-added items to the
    # stations instead of resending the whole ticket. Kept in our own field so
    # Odoo's native ``last_order_preparation_change`` merge logic never touches
    # it.
    mezze_fired = fields.Char(string='Mezze fired snapshot', copy=False)

    # R2A CP9 — "Parked" is a cashier-facing TAG on a still-DRAFT order (the order
    # stays `state='draft'`; the FSM/lifecycle/table binding are untouched). It only
    # drives the Orders workspace Open/Parked split — a parked table order is still a
    # draft bound to its table, so the floor still shows it occupied. NOT a new state.
    mezze_parked = fields.Boolean(string='Parked (cashier)', default=False, copy=False, index=True)

    # O1/P1 — omnichannel customer status. The customer holds a high-entropy RAW
    # token (128-bit); the server stores only its SHA-256 HASH, so a DB read never
    # discloses a usable token. Lookup hashes the presented token. The token
    # (never the sequential id) is the only key a status lookup accepts, expires,
    # and can be revoked.
    mezze_channel = fields.Char(string='Order channel', index=True, copy=False,
                                help="qr | pickup | delivery | drivethru | aggregator | kiosk | pos")
    mezze_service_mode = fields.Selection(
        [('eat_in', 'Eat in'), ('takeaway', 'Takeaway')], string='Service mode', copy=False,
        help="S4 kiosk/self-order eat-in vs takeaway (for tax/packaging semantics).")
    # What the guest asked for at a self-service terminal, beyond the food itself.
    # Both are the GUEST's stated choice, recorded so the counter and the reports can
    # honour it; neither is a payment record and neither settles anything.
    mezze_receipt_pref = fields.Selection(
        [('print', 'Printed at the counter'), ('none', 'No receipt')],
        string='Receipt preference', copy=False,
        help="What a kiosk guest asked for when the order was placed.")
    mezze_pay_choice = fields.Char(
        string='Chosen payment option', copy=False,
        help="The payment option code the guest selected at a self-service terminal, "
             "validated against the options that branch actually offers. The kiosk is "
             "pay-at-counter, so this records the CHOICE, not a settlement.")

    mezze_status_token = fields.Char(string='Public status token hash', index=True, copy=False,
                                     help="SHA-256 of the customer's raw status token (never the raw token).")
    mezze_status_expiry = fields.Datetime(string='Status token expiry', copy=False)
    mezze_status_revoked = fields.Boolean(string='Status token revoked', copy=False)

    # ---------------------------------------------------------- backend mapping
    # Who and what actually made this sale, on the NATIVE order rather than only
    # in the audit log.
    #
    # ``user_id`` cannot answer this. Front-of-house staff deliberately have no
    # res.users (that is the mezze.cashier design), so every Mezze order carried
    # the API/service identity as its salesperson and the backend could not say
    # who sold anything. Reporting, disputes and end-of-day cash all need a name,
    # and reading the audit log to find one is not a mapping.
    mezze_cashier_id = fields.Many2one(
        'mezze.cashier', string='Cashier', index=True, copy=False, ondelete='set null',
        help="The till operator who made this sale, as identified by their PIN.")
    # ------------------------------------------------------------ split family
    # Native Odoo splits a bill entirely in the browser and remembers the
    # relationship in ``uiState.splittedOrderUuid`` — UI state, not a column. Reload
    # the page and the family is gone. There is therefore nothing to extend here,
    # which is why these are real fields: payment, receipts, refunds, reporting and
    # audit all need the relation to survive a browser.
    #
    # The ROOT carries no root_id (it is one); children point at it. "Family" is the
    # root plus everyone pointing at it, so reconstruction never depends on walking a
    # chain that a deleted middle order could break.
    mezze_split_root_id = fields.Many2one(
        'pos.order', string='Split root', index=True, copy=False, ondelete='set null',
        help="The original check this one was split from. Empty on the original itself.")
    mezze_split_parent_id = fields.Many2one(
        'pos.order', string='Split parent', index=True, copy=False, ondelete='set null',
        help="The check these items came from — the root, or another child when a "
             "check is split again.")
    mezze_split_seq = fields.Integer(
        string='Split #', copy=False,
        help="1-based position within the family, for display only. Never the "
             "accounting sequence.")
    mezze_split_uuid = fields.Char(
        string='Split family', index=True, copy=False,
        help="Stable id shared by every check in one dining event.")
    mezze_split_by_id = fields.Many2one(
        'mezze.cashier', string='Split by', copy=False, ondelete='set null')
    mezze_split_at = fields.Datetime(string='Split at', copy=False)

    # Optimistic concurrency. Two terminals may hold the same table open; the client
    # sends the revision it based its selection on, and a commit against a stale one
    # is refused rather than silently applied to quantities that have since moved.
    mezze_revision = fields.Integer(
        string='Revision', default=0, copy=False,
        help="Bumped on every authoritative change to this order's composition.")

    mezze_split_child_ids = fields.One2many(
        'pos.order', 'mezze_split_root_id', string='Split checks')
    mezze_split_count = fields.Integer(compute='_compute_split_family', string='Checks')
    mezze_is_split_root = fields.Boolean(compute='_compute_split_family')

    @api.depends('mezze_split_root_id', 'mezze_split_child_ids')
    def _compute_split_family(self):
        for rec in self:
            rec.mezze_is_split_root = bool(rec.mezze_split_child_ids) and not rec.mezze_split_root_id
            root = rec.mezze_split_root_id or rec
            rec.mezze_split_count = (1 + len(root.mezze_split_child_ids)) if (
                root.mezze_split_child_ids) else 0

    def mezze_split_family(self):
        """Every check in this dining event, root first, then children in order.

        Callable from either end — give it a child and you still get the family,
        because a cashier who opens Check 2 should see the same picture as one who
        opened the original.
        """
        self.ensure_one()
        root = self.mezze_split_root_id or self
        return root + root.mezze_split_child_ids.sorted(lambda o: o.mezze_split_seq)

    def mezze_bump_revision(self):
        """One place to move the revision, so no caller can forget."""
        for rec in self:
            rec.sudo().mezze_revision = (rec.mezze_revision or 0) + 1
        return True

    mezze_terminal_id = fields.Many2one(
        'mezze.terminal', string='Terminal / Station', index=True, copy=False,
        ondelete='set null',
        help="The device that submitted this order — a Register instance or an "
             "enrolled Windows station.")

    @staticmethod
    def _mezze_status_hash(raw):
        import hashlib
        return hashlib.sha256((raw or '').encode()).hexdigest()

    def _mezze_status_ttl_hours(self):
        try:
            return int(self.env['ir.config_parameter'].sudo().get_param(
                'mezze_bridge.status_token_ttl_hours', 24) or 24)
        except Exception:  # noqa: BLE001
            return 24

    def _mezze_ensure_status_token(self):
        """Mint a high-entropy RAW status token, store ONLY its hash + an expiry,
        and RETURN the raw token exactly once (idempotent: an order that already has
        a hash returns None). 128 bits of entropy (32 hex)."""
        import os as _os
        self.ensure_one()
        if self.mezze_status_token:
            return None                                  # already minted; raw is not recoverable
        raw = _os.urandom(16).hex()
        self.write({'mezze_status_token': self._mezze_status_hash(raw),
                    'mezze_status_expiry': fields.Datetime.now() + timedelta(hours=self._mezze_status_ttl_hours()),
                    'mezze_status_revoked': False})
        return raw

    def mezze_revoke_status_token(self):
        """Immediate manual revocation of the public status token."""
        self.write({'mezze_status_revoked': True})
        return True

    @api.model
    def _mezze_resolve_status_token(self, raw):
        """Return the order for a presented RAW token, or an empty recordset if the
        hash is unknown, expired or revoked. Constant-ish: hash then indexed lookup."""
        if not raw or len(str(raw)) < 24:
            return self.browse()
        o = self.sudo().search([('mezze_status_token', '=', self._mezze_status_hash(str(raw)))], limit=1)
        if not o or o.mezze_status_revoked:
            return self.browse()
        if o.mezze_status_expiry and o.mezze_status_expiry < fields.Datetime.now():
            return self.browse()
        return o

    def mezze_public_status(self):
        """SAFE public status for a customer-status page — never leaks internal
        workflow/staff data. One of: received | confirmed | preparing | ready |
        out_for_delivery | completed | cancelled | action_required."""
        self.ensure_one()
        if self.state == 'cancel':
            return 'cancelled'
        # delivery leg (own delivery) takes precedence for the public label
        dlv = self.env['mezze.delivery'].sudo().search([('pos_order_id', '=', self.id)], limit=1)
        if dlv:
            if dlv.state in ('delivered',):
                return 'completed'
            if dlv.state in ('dispatched', 'out'):
                return 'out_for_delivery'
        tickets = self.env['mezze.kds.ticket'].sudo().search([('pos_order_id', '=', self.id)])
        active = tickets.filtered(lambda t: t.state not in ('served', 'cancel'))
        if tickets and not active:
            # everything served/collected
            return 'completed' if self.state in ('paid', 'done', 'invoiced') else 'ready'
        if active.filtered(lambda t: t.state == 'ready'):
            return 'ready'
        if active.filtered(lambda t: t.state in ('preparing', 'fired', 'accepted')):
            return 'preparing'
        if self.state in ('paid', 'done', 'invoiced'):
            return 'confirmed'
        return 'received'


class PosOrderLine(models.Model):
    _inherit = 'pos.order.line'

    # WHO ordered it. Neither Odoo POS nor Mezze had a seat model, which is why
    # "By seat" was offered and permanently disabled: a table's bill knew what was
    # eaten but not by whom, so the commonest request at the end of a shared meal —
    # "can we pay separately?" — could only be answered by a cashier reading the
    # order aloud and guessing.
    #
    # Zero is not seat zero, it is UNASSIGNED, and it is the default because most
    # orders never need seats and nobody should have to say so. Sharing is the
    # honest meaning of unassigned: a bottle of wine at the middle of the table
    # belongs to nobody in particular, and a split by seat must not quietly hand it
    # to whoever happens to be first.
    mezze_seat = fields.Integer(
        string='Seat', default=0, copy=False, index='btree_not_null',
        help="Which seat at the table ordered this line. 0 means it was not "
             "assigned to anyone — a shared item.")

    _mezze_seat_not_negative = models.Constraint(
        'CHECK(mezze_seat >= 0)',
        "A seat number cannot be negative.",
    )

    # Provenance. Reporting reconstructs a family from the ORDER relation, so this
    # is not load-bearing for money — it is here so a receipt or a dispute can answer
    # "which original line did this come from" without inference.
    mezze_split_origin_line_id = fields.Many2one(
        'pos.order.line', string='Split from line', index='btree_not_null',
        copy=False, ondelete='set null')

    @api.constrains('refunded_orderline_id', 'qty')
    def _mezze_check_refund_not_over_source(self):
        """Authoritative per-line refund-quantity backstop for EVERY path.

        The Mezze controller enforces this (with server-side reconstruction and a
        per-original advisory lock), but core `sync_from_ui` has no hard limit — a
        crafted or offline payload can over-refund a source line. This model
        constraint closes that bypass at the single mutation point every refund
        path (controller, core POS UI, offline sync, back-office, direct
        `sync_from_ui`) must pass: the cumulative non-cancelled refunded quantity
        against an original line may never exceed the quantity sold.

        Fires only when a refund line links to a source line, and only rejects a
        genuine over-refund — legitimate core/UI refunds (which cap to remaining)
        never trip it, so standard Odoo flows are unaffected.
        """
        for line in self:
            src = line.refunded_orderline_id
            if not src:
                continue
            refunds = src.refund_orderline_ids.filtered(
                lambda rl: rl.order_id.state != 'cancel')
            refunded_qty = -sum(refunds.mapped('qty'))          # positive
            rounding = src.product_uom_id.rounding or 0.01
            if float_compare(refunded_qty, src.qty, precision_rounding=rounding) > 0:
                raise ValidationError(_(
                    "Refund quantity (%(ref)s) exceeds the sold quantity "
                    "(%(sold)s) for %(product)s.",
                    ref=refunded_qty, sold=src.qty,
                    product=src.product_id.display_name))
