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
    mezze_status_token = fields.Char(string='Public status token hash', index=True, copy=False,
                                     help="SHA-256 of the customer's raw status token (never the raw token).")
    mezze_status_expiry = fields.Datetime(string='Status token expiry', copy=False)
    mezze_status_revoked = fields.Boolean(string='Status token revoked', copy=False)

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
